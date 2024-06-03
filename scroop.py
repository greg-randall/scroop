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
import shutil
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import hashlib



debug = False

#timestamp 
now = datetime.now()
timestamp = now.strftime("%m-%d-%Y_%I-%M-%p")

output_filename = f"job_search_{timestamp}.csv"

# Check if the log file exists, if it doesn't, create it
# The log file is used to keep track of which sites have been scanned
if not os.path.exists("scanned_sites.log"):
    open("scanned_sites.log", 'w').close()

#create the cache folder if it doesn't exist
if not os.path.exists('cached_pages'):
    os.makedirs('cached_pages')


# Initialize an empty list to store the links
links = []

#randomize the search sites and search words
random.shuffle(search_sites)
random.shuffle(search_words)


####
#Search the sites for jobs
####

print("Searching for jobs...\n")

# Loop over each site in the list of search sites
# The enumerate function is used to get the count of the current iteration (starting from 1)
# A list comprehension is used to generate pairs of search sites and search words
for count, (search_site, search_word) in enumerate([(site, word) for site in search_sites for word in search_words], start=1):
    # Construct the page URL by appending the urlencoded search word to the search site URL
    page = f"{search_site}{quote(search_word)}"
    
    # Print a message indicating that the page is being fetched
    # The total number of pages is the product of the number of search sites and search words
    #print(f"\r{count}/{len(search_sites)*len(search_words)} -- {page}", end="", flush=True)
    print(f"\r\033[K{count}/{len(search_sites)*len(search_words)} -- {page}", end="", flush=True)

    
    # Fetch the content of the page
    # The second argument to get_page_content is the maximum age of cached content in hours
    # If the cached content is older than this, it will be refreshed
    page_content = get_page_content(page, 23.5)

    # If the page content was successfully fetched
    if page_content:
        # Extract the links from the page content and add them to the list of links
        fresh_links = extract_links(page_content, page)
        # Clean the extracted links by making sure they contain the search site URL and removing duplicates
        fresh_links = link_cleaner(fresh_links, search_sites)
        # Extend the list of links with the fresh links
        links.extend(fresh_links)

        # Print a success message with the number of links extracted
        if debug:
            cprint(f"\tPage Collected! {len(fresh_links)} links","green")
    else:
        # If the page content was not successfully fetched, print an error message
        if debug:
            cprint("\tNo page content retrieved","red")

# Print the total number of links collected, in green
print(f"\n\nTotal Links Found: {len(links)}")

# Read the file 'scanned_sites.log' into a list
with open('scanned_sites.log', 'r') as file:
    scanned_sites = file.read().splitlines()
# Remove any items from 'links' that exist in 'scanned_sites'
links = [link for link in links if link not in scanned_sites]


print(f"Links Remaining after Previously Scanned removed: {len(links)}\n\n")


# Shuffle the list of links to ensure randomness
random.shuffle(links)

####
#Make sure pages are cached in parallel
####
print("Caching pages in parallel...\n")

# Create a ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as executor:
    # Use the executor to start a new thread for each link
    # Wrap the call to executor.map with tqdm to show a progress bar
    page_contents = list(tqdm(executor.map(get_page_content, links, [720]*len(links)), total=len(links)))
del page_contents

####
#generate summaries in parallel

####
#Scan the generated links for job relevance
####

print("\nScanning for jobs relevance...\n")

# Check if the output file exists, if it doesn't, create it
# The output file is used to store the results of the job search
if not os.path.exists(output_filename):
    with open(output_filename, 'w') as file:
        # Write the header row to the output file
        file.write('timestamp,url,job is a good match with resume\n')


# Loop through the shuffled links
for count, link in enumerate(links, start=1):

    # Print the current link number and the link itself and make sure the link is not too long
    columns, _ = shutil.get_terminal_size()
    max_link_length = columns - len(f"{count}/{len(links)} - ")
    print(f"\r\033[K{count}/{len(links)} - {link[:max_link_length]}", end="", flush=True)

    # Open the log file and read its content
    with open("scanned_sites.log", 'r') as file:
        previously_scanned_sites = file.read()

    # Check if the link is not in the log file, does not start with any of the search sites, and does not contain "keywords"
    if link not in previously_scanned_sites: #and not any(link.startswith(search_site) for search_site in search_sites) and "keywords" not in link:
        # Fetch the content of the page at the link
        page_content_raw = get_page_content(link, 720) # keep reusing cached pages for 30 days (720 hours = 30 days)
        # Extract the body text from the page content
        page_content = get_page_body_text(page_content_raw)

        
        # If there is page content
        if page_content:

            #make sure at least one of our keywords is in the page content
            found_word = find_keywords(page_content, search_words)

            if found_word:
  
                # Ask the user to read the job listing and write a summary of required skills and degrees
                prompt = f"Please read this job listing and write a consise summary of required skills, degrees, etc:\n\n{compress_prompt(page_content)}"

                filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
                filepath = os.path.join('cached_pages', filename)
                if not os.path.exists(filepath):
                    # Use the LLM to generate a summary of the job listing
                    job_summary = gpt_me(prompt,"gpt-3.5-turbo",open_ai_key)
                    with open(filepath, 'w') as file:
                        file.write(job_summary)
                else:
                    with open(filepath, 'r') as file:
                        job_summary = file.read()


                #print("looking at good fit")
                # Ask the user to determine if the job is a good match with the resume
                prompt = f"Read the applicant's RESUME and JOB SUMMARY below and determine if the applicant is a good fit for this job on a scale of 1 to 10. 1 is a bad fit, 10 is a perfect fit. REPLY WITH AN INTEGER 1-10!!!\n\nJOB SUMMARY:  {compress_prompt(bullet_resume)}\n\nJOB SUMMARY:  {compress_prompt(job_summary)}"
                #print(f"looking at good fit:\n{prompt}\n\n")

                filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
                filepath = os.path.join('cached_pages', filename)
                if not os.path.exists(filepath):
                    # Use the LLM to generate a summary of the job listing
                    job_is_a_good_match = gpt_range(prompt,"gpt-4o", open_ai_key,True)
                    with open(filepath, 'w') as file:
                        file.write(str(job_is_a_good_match))
                else:
                    with open(filepath, 'r') as file:
                        job_is_a_good_match = file.read()

                


                if isinstance(job_is_a_good_match,int):

                    with open(filepath, 'w') as file:
                        file.write(str(job_is_a_good_match))
                    # If the job is relevant and a good match, print a success message
                    if job_is_a_good_match>=5:
                        cprint(f"\n\nJOB FOUND!!! -- {link}\n","green")
                    with open(output_filename, 'a') as file:
                        file.write(f'{datetime.now().strftime("%m/%d/%Y %I:%M %p")},{link},{job_is_a_good_match}\n')

            # Append the link to the log file, so we know to skip it in the future, and to avoid duplicates
            with open("scanned_sites.log", 'a') as file:
                file.write(f"{link}\n")
    else:
        # If the link is in the log file, starts with a search site, or contains "keywords", skip it 
        if debug:
            cprint(f"\tSkipping -- Link invalid or already scanned", "yellow")
        with open("scanned_sites.log", 'a') as file:
            file.write(f"{link}\n")

print("\n\n\n")