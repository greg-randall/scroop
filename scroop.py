"""

Scroop is used to automate a job search process. It works by searching a list of job sites for a list of keywords, extracting relevant links, and then scanning those links for job relevance using an LLM.


"""

import concurrent.futures
import hashlib
import os
import random
import shutil
import time
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

from termcolor import cprint
from tqdm import tqdm

from config import *
from functions import *



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





####
#Search the sites for jobs
####

# generate list of search urls
# puts together the search sites and search words from the config file
site_search_list = []
for site in search_sites:
    for word in search_words:
        site_search_list.append(f"{site}{quote(word)}")  # Adjust the formatting as needed

#randomize so the order of is different each time
random.shuffle(site_search_list)

print("Getting Searches in parallel...")
# Get the search links from the search sites
links = []
with ThreadPoolExecutor(max_workers=8) as executor:
    links = list(tqdm(executor.map(get_search_links, site_search_list, [search_sites]*len(site_search_list)), total=len(site_search_list)))

# Flatten the list of lists of links into a single list of links
links = [link for sublist in links for link in sublist]
print(f"\nTotal Links Found: {len(links)}")


####
#Basic clean on the links, removing previously scanned sites and duplicates  
####
random.shuffle(links)

# Read the file 'scanned_sites.log' into a list
with open('scanned_sites.log', 'r') as file:
    scanned_sites = file.read().splitlines()
# Remove any items from 'links' that exist in 'scanned_sites'
links = [link for link in links if link not in scanned_sites]

print(f"Links Remaining after Previously Scanned removed: {len(links)}")

# Remove any duplicate links from the list
links = list(set(links))
print(f"Links Remaining after Duplicates Removed: {len(links)}\n")



####
#Cache pages and skip links without the keyword in the body of the page
###
random.shuffle(links)
if debug:
    print("Debug Mode: Only processing 10 links")
    import random
    links = random.sample(links, 10)

print("Make Sure Pages are Cached & Remove Pages without Keywords...")
with ThreadPoolExecutor(max_workers=8) as executor:
    skipped = sum(tqdm(executor.map(process_link, links, [search_words]*len(links)), total=len(links)))

# Read the file 'scanned_sites.log' into a list
with open('scanned_sites.log', 'r') as file:
    scanned_sites = file.read().splitlines()
# Remove any items from 'links' that exist in 'scanned_sites'
links = [link for link in links if link not in scanned_sites]

print(f"Links Remaining after Pages without Keywords removed: {len(links)}")




####
#Generate job description summaries
####
print("\nGenerating GPT Summaries of Jobs...")
random.shuffle(links)

with ThreadPoolExecutor(max_workers=8) as executor:
    list(tqdm(executor.map(generate_gpt_summary, links, [open_ai_key]*len(links)), total=len(links)))


####
#Generate job match numbers for how well each job matches the resume
####
print("\nGenerating Job Match Number...")
random.shuffle(links)

with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(tqdm(executor.map(generate_gpt_job_match, links, [bullet_resume]*len(links), [open_ai_key]*len(links)), total=len(links)))

 
####
#Generate the output file
####
print("\nGenerating Results...")

# Initialize a counter
i = 1

# Iterate over each link in the list of links
for link in links:


    # Generate a filename based on the MD5 hash of the link
    filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
    # Construct the full file path
    filepath = os.path.join('cached_pages', filename)

    try:
        # Attempt to open the file and read the job match rating
        with open(filepath, 'r') as file:
            job_match = file.read()

        # Get the current timestamp
        now = datetime.now()
        timestamp = now.strftime("%m-%d-%Y_%I-%M-%p")

        # Print the current link and its job match rating
        print(f"{i}/{len(links)}: {link} - {job_match}")

        # Check if the output file exists, if it doesn't, create it
        # The output file is used to store the results of the job search
        if not os.path.exists(output_filename):
            with open(output_filename, 'w') as file:
                # Write the header row to the output file
                file.write('timestamp,url,resume match\n')

        # Append the timestamp, link, and job match rating to the output file
        with open(output_filename, 'a') as file:
            file.write(f"{timestamp},{link},{job_match}\n")

        # Append the link to the scanned sites log file
        with open('scanned_sites.log', 'a') as file:
            file.write(f"{link}\n")
    except:
        # If an error occurs, print the link in red
        cprint(f"Error: {link}", 'red')
        
        # Remove the link from the scanned sites log file, so we'll try again next time
        with open('scanned_sites.log', 'r') as file:
            lines = file.readlines()
        with open('scanned_sites.log', 'w') as file:
            for line in lines:
                if line.strip("\n") != link:
                    file.write(line)
        print("\tRemoved from scanned sites log")
        
        # In case something went wrong with the cache, summary or rating, remove the cached data
        # Generate a filename based on the MD5 hash of the link
        filename_hash = hashlib.md5(link.encode()).hexdigest()
        # Get a list of all files in the directory
        files = os.listdir('cached_pages')

        # Iterate over the files
        for file in files:
            # If the filename_hash is in the file name
            if filename_hash in file:
                # Construct the full file path
                file_path = os.path.join('cached_pages', file)
                # Remove the file
                os.remove(file_path)
                print(f"\tRemoved cached file - {file_path}")
        

    # Increment the counter
    i += 1