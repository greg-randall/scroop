"""

Scroop is used to automate a job search process. It works by searching a list of job sites for a list of keywords, extracting relevant links, and then scanning those links for job relevance using an LLM.

----------------

Phase one: searching the sites for jobs. It constructs a URL for each combination of search site and search word, fetches the page content, extracts links from the page content, cleans the links, and adds them to a master list of links.

Phase two: scanning the generated links for job relevance. For each link, the script fetches the page content, extracts the body text, and uses the LLM to read the job listing and write a summary of required skills and degrees. Using the summary the LLM determines if the job is relevant to the search words and determines if the job is a good match with the resume. If the job is relevant and a good match, the script prints a success message. The results are appended to the output csv file.

"""

from functions import *
from config import *


from datetime import datetime
from termcolor import cprint
from urllib.parse import quote
import os
import random
from datetime import datetime




debug = False

#timestamp 
now = datetime.now()
timestamp = now.strftime("%m-%d-%Y_%I-%M-%p")

output_filename = f"job_search_{timestamp}.csv"

# Initialize an empty list to store the links
links = []

#randomize the search sites and search words
random.shuffle(search_sites)
random.shuffle(search_words)


####
#Search the sites for jobs
####

# Loop over each site in the list of search sites
# The enumerate function is used to get the count of the current iteration (starting from 1)
# A list comprehension is used to generate pairs of search sites and search words
for count, (search_site, search_word) in enumerate([(site, word) for site in search_sites for word in search_words], start=1):
    # Construct the page URL by appending the urlencoded search word to the search site URL
    page = f"{search_site}{quote(search_word)}"
    
    # Print a message indicating that the page is being fetched
    # The total number of pages is the product of the number of search sites and search words
    cprint(f"{count}/{len(search_sites)*len(search_words)} Getting page: {page}","cyan")
    
    # Fetch the content of the page
    # The second argument to get_page_content is the maximum age of cached content in hours
    # If the cached content is older than this, it will be refreshed
    page_content = get_page_content(page, 24)

    # If the page content was successfully fetched
    if page_content:
        # Extract the links from the page content and add them to the list of links
        fresh_links = extract_links(page_content, page)
        # Clean the extracted links by making sure they contain the search site URL and removing duplicates
        fresh_links = link_cleaner(fresh_links, search_sites)
        # Extend the list of links with the fresh links
        links.extend(fresh_links)

        # Print a success message with the number of links extracted
        cprint(f"\tPage Collected! {len(fresh_links)} links","green")
    else:
        # If the page content was not successfully fetched, print an error message
        cprint("\tNo page content retrieved","red")

# Print the total number of links collected, in green
cprint(f"\n\nTotal Links: {len(links)}\n\n","green")

####
#Scan the generated links for job relevance
####

# Shuffle the list of links to ensure randomness
random.shuffle(links)


# Check if the output file exists, if it doesn't, create it
# The output file is used to store the results of the job search
if not os.path.exists(output_filename):
    with open(output_filename, 'w') as file:
        # Write the header row to the output file
        file.write('timestamp,job match,url,job is relevant to keywords,job is a good match with resume\n')

# Check if the log file exists, if it doesn't, create it
# The log file is used to keep track of which sites have been scanned
if not os.path.exists("scanned_sites.log"):
    open("scanned_sites.log", 'w').close()

# Loop through the shuffled links
for count, link in enumerate(links, start=1):

    job_match = False #initialize job_match to False
    add_job_to_csv = False

    # Print the current link number and the link itself
    cprint(f"{count}/{len(links)} - {link}","cyan")

    # Open the log file and read its content
    with open("scanned_sites.log", 'r') as file:
        content = file.read()

    # Check if the link is not in the log file, does not start with any of the search sites, and does not contain "keywords"
    if link not in content and not any(link.startswith(search_site) for search_site in search_sites) and "keywords" not in link:
        # Fetch the content of the page at the link
        page_content_raw = get_page_content(link, 720) # keep reusing cached pages for 30 days (720 hours = 30 days)
        # Extract the body text from the page content
        page_content = get_page_body_text(page_content_raw)

        

        # If there is page content
        if page_content:

            #make sure at least one of our keywords is in the page content
            found_word = find_keywords(page_content, search_words)

            if found_word:
                add_job_to_csv = True

                # Ask the user to read the job listing and write a summary of required skills and degrees
                job_summary = ollama_me(f"Please read this job listing and write a consise summary of required skills and degrees:\n\n{page_content}")
                # Ask the user to determine if the job is relevant to the search words
                job_is_relevant = ollama_true_or_false(f"Read the job summary below and determine if it has anything to do with {make_list_human_readable(search_words)}. !!!Reply with a single word, TRUE or FALSE!!!\n\nJOB SUMMARY:  {job_summary}")
                # Ask the user to determine if the job is a good match with the resume
                job_is_a_good_match = ollama_true_or_false(f"You are a hiring commitee, read the RESUME and JOB SUMMARY below and determine if you would hire the applicant for this job. !!!Reply with a single word, TRUE or FALSE!!!\n\nJOB SUMMARY:  {bullet_resume}\n\nJOB SUMMARY:  {job_summary}")

                # If the job is relevant and a good match, print a success message
                if job_is_relevant and job_is_a_good_match:
                    cprint(f"\tJOB FOUND!!!","green")
                    job_match = True                 

            if add_job_to_csv: # We'll only add the job to the csv if we've determined it's relevant, meaning it has at least one keyword and the other checks above
                # Append the results to the output file
                with open(output_filename, 'a') as file:
                    file.write(f'{datetime.now().strftime("%m/%d/%Y %I:%M %p")},{job_match},{link},{job_is_relevant},{job_is_a_good_match}\n')

            # Append the link to the log file, so we know to skip it in the future, and to avoid duplicates
            with open("scanned_sites.log", 'a') as file:
                file.write(f"{link}\n")
    else:
        # If the link is in the log file, starts with a search site, or contains "keywords", skip it 
        if debug:
            cprint(f"\tSkipping -- Link invalid or already scanned", "yellow")
        with open("scanned_sites.log", 'a') as file:
            file.write(f"{link}\n")