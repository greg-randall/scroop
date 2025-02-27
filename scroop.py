"""

Scroop is used to automate a job search process. It works by searching a list of job sites for a list of keywords, extracting relevant links, and then scanning those links for job relevance using an LLM. The search terms and sites are defined in the config.py file. As is the resume that is used to compare the job descriptions to.


"""

import hashlib
import os
import random
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import itertools
from operator import itemgetter
import shutil
import csv
import pandas as pd

from termcolor import cprint
from tqdm import tqdm

from config import *
from functions import *

import subprocess


# Define the output filenames
timestamp = datetime.now().strftime('%m-%d-%Y_%I-%M-%p')
output_csv_filename = f"job_search_{timestamp}.csv"
output_summary_filename = f"job_match_summaries_{timestamp}.txt"


# The log file is used to keep track of which sites have been scanned, Create the log file if it doesn't exist
with open("scanned_sites.log", 'a') as _:
    pass

# Create the cache folder if it doesn't exist
os.makedirs('cached_pages', exist_ok=True)



####
#Search the sites for jobs
####

# Generate list of search URLs, combining each site with each search word
site_search_list = [f"{site}{quote(word)}" for site in search_sites for word in search_words]

# Randomize the order
random.shuffle(site_search_list)

print(f"Getting Searches in parallel from {len(site_search_list)} URLs using {threads} threads...")

if debug: #this debug will record the time it takes to perform the searches/gpts/etc so that you can determine the correct number fo threads to use
    # Get current date and time
    now = datetime.now()
    # Format datetime object to a pretty string
    pretty_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    # Append the pretty_timestamp to the file 'threads.log'
    with open('threads.log', 'a') as f:
        f.write(pretty_timestamp + '\n')
    now = datetime.now()
    before_timestamp = now.timestamp()


split_site_search_list = split_list(site_search_list, threads)

# Get the search links from the search sites
with ThreadPoolExecutor(max_workers=threads) as executor:
    # Create a progress bar with more detailed information
    progress_bar = tqdm(
        total=len(split_site_search_list),
        desc="Searching job sites",
        unit="batch",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} batches [{elapsed}<{remaining}, {rate_fmt}]"
    )
    
    # Process each batch and update the progress bar
    all_links = []
    for result in executor.map(get_search_links, split_site_search_list, itertools.repeat(search_sites, len(split_site_search_list))):
        all_links.append(result)
        progress_bar.update(1)
        progress_bar.set_postfix({"links found": sum(len(batch) for batch in all_links)})
    
    progress_bar.close()
    links = all_links

if debug:
    now = datetime.now()
    after_timestamp = now.timestamp()

    site_search_log = f"get_search_links {threads} - {(after_timestamp - before_timestamp)/len(site_search_list)} seconds per thread"

    with open('threads.log', 'a') as f:
        f.write(site_search_log + '\n')


# Flatten the list of lists of links into a single list of links
links = [link for sublist in links for link in sublist]

print(f"\nTotal Links Found: {len(links)}")


####
#Basic clean on the links, removing previously scanned sites and duplicates  
####

# Read the file 'scanned_sites.log' into a set for faster lookup
with open('scanned_sites.log', 'r') as file:
    scanned_sites = set(file.read().splitlines())

# Use a list comprehension to filter out links that have been scanned
links = [link for link in links if link not in scanned_sites]
print(f"Links Remaining after Previously Scanned removed: {len(links)}")

# Use a set to remove duplicate links, then convert back to a list
links = list(set(links))
print(f"Links Remaining after Duplicates Removed: {len(links)}\n")



####
#Cache pages and skip links without the keyword in the body of the page
###

random.shuffle(links)

if debug:
    print("Debug Mode: Only processing 10 links")
    links = random.sample(links, 10)

print("Make Sure Pages are Cached & Remove Pages without Keywords...")
if debug:
    if len(links) > 0:
        now = datetime.now()
        before_timestamp = now.timestamp()

# Assuming links and threads are defined somewhere above
split_links = split_list(links, threads)

with ThreadPoolExecutor(max_workers=threads) as executor:
    skipped = sum(tqdm(executor.map(process_links, split_links, itertools.repeat(search_words, len(split_links)), itertools.repeat(must_have_words, len(split_links)), itertools.repeat(anti_kewords, len(split_links))), total=len(split_links)))
    
if debug:
    if len(links) > 0:
        now = datetime.now()
        after_timestamp = now.timestamp()
        site_search_log = f"process_links {threads} - {(after_timestamp - before_timestamp)/len(links)} seconds per thread"
        with open('threads.log', 'a') as f:
            f.write(site_search_log + '\n')


# Read the file 'scanned_sites.log' into a set for faster lookup
with open('scanned_sites.log', 'r') as file:
    scanned_sites = set(file.read().splitlines())

# Use a list comprehension to filter out links that have been scanned
links = [link for link in links if link not in scanned_sites]

print(f"Links Remaining after Pages without Keywords removed: {len(links)}")




####
#Generate job description summaries
####

print("\nGenerating GPT Summaries of Jobs...")

if debug:
    if len(links) > 0:
        now = datetime.now()
        before_timestamp = now.timestamp()

random.shuffle(links)
with ThreadPoolExecutor(max_workers=threads) as executor:
    list(tqdm(executor.map(generate_gpt_summary, links, itertools.repeat(open_ai_key, len(links))), total=len(links)))

if debug:
    if len(links) > 0:
        now = datetime.now()
        after_timestamp = now.timestamp()

        site_search_log = f"generate_gpt_summary {threads} - {(after_timestamp - before_timestamp)/len(links)} seconds per thread"

        with open('threads.log', 'a') as f:
            f.write(site_search_log + '\n')




####
#Generate job match numbers for how well each job matches the resume
####
print("\nGenerating Job Match Number...")
random.shuffle(links)

if debug:
    if len(links) > 0:
        now = datetime.now()
        before_timestamp = now.timestamp()

with ThreadPoolExecutor(max_workers=threads) as executor:
    results = list(tqdm(executor.map(generate_gpt_job_match, links, [bullet_resume]*len(links), [open_ai_key]*len(links)), total=len(links)))
if debug:
    if len(links) > 0:
        now = datetime.now()
        after_timestamp = now.timestamp()

        site_search_log = f"generate_gpt_job_match {threads} - {(after_timestamp - before_timestamp)/len(links)} seconds per thread"

        with open('threads.log', 'a') as f:
            f.write(site_search_log + '\n\n\n')

 

####
#Generate the output file
####
print("\nGenerating Results...")


# Initialize an empty list to store the output data
output_csv = []
output_summary = []

# Iterate over each link in the list of links
for i, link in enumerate(links, start=1):
    # Generate a filename based on the MD5 hash of the link
    filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
    # Construct the full file path
    filepath = os.path.join('cached_pages', filename)

    try:
        # Attempt to open the file and read the job match rating
        with open(filepath, 'r') as file:
            job_match = file.read()

        job_match = int(job_match.strip())

        # Print the current link and its job match rating
        progress_list = f"{i}/{len(links)}: {link} - {job_match}"
        if job_match >= 8:
            cprint(progress_list, 'green')

            summary_string_temp = ""
            # Write the job match, job URL, and job description to the file
            summary_string_temp += f"{job_match} -- {link}\n"
            # Read the summary from the summary file
            filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
            filepath = os.path.join('cached_pages', filename)
            with open(filepath, 'r') as summary_file:
                summary = summary_file.read()

            summary_string_temp +=f"Job Description:\n{summary}\n\n\n\n"

            output_summary.append(summary_string_temp)
        elif job_match >= 6:
            cprint(f" {progress_list}", 'blue')
        elif job_match >= 4:
            cprint(f"    {progress_list}", 'yellow')
        else:
            print(f"      {progress_list}")

        # Append the timestamp, link, and job match rating to the output data
        output_csv.append([datetime.now().strftime("%m-%d-%Y_%I-%M-%p"), job_match, link])

        # Append the link to the scanned sites log file
        with open('scanned_sites.log', 'a') as file:
            file.write(f"{link}\n")
    except Exception as e:
        # In case something went wrong we're going to drop the link from the sites 
        # log as well as remove the content from the cache, in the hopes that it goes 
        # right the next time around

        # If an error occurs, print the link in red
        cprint(f"Error: {e}\n\t{link}", 'red')
        
        # Remove the link from the scanned sites log file, so we'll try again next time
        with open('scanned_sites.log', 'r') as file:
            lines = [line for line in file if line.strip("\n") != link]
        with open('scanned_sites.log', 'w') as file:
            file.writelines(lines)
        print("\tRemoved from scanned sites log")
        
        # Generate a filename based on the MD5 hash of the link
        filename_hash = hashlib.md5(link.encode()).hexdigest()
        # Get a list of all files in the directory
        files = os.listdir('cached_pages')

        # Iterate over the files
        for file in files:
            # If the filename_hash is in the file name
            if filename_hash in file:
                # Check if the 'cached_pages/removed' directory exists, create it if it doesn't
                removed_dir = 'cached_pages/removed'
                if not os.path.exists(removed_dir):
                    os.makedirs(removed_dir)
                # Construct the full file path
                file_path = os.path.join('cached_pages', file)

                # Construct the destination path
                dest_path = os.path.join(removed_dir, file)

                # Move the file
                shutil.move(file_path, dest_path)

                print(f"\tMoved cached file to - {dest_path}")


# Sort the output data by the job match rating highest to lowest


if len(output_csv)>0: # Only write the output data to a CSV file if there is data to write
    output_csv.sort(key=itemgetter(1), reverse=True)
    # Write the output data to the CSV file
    with open(output_csv_filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp','Job Match Rating', 'Link'])  # Write the header
        writer.writerows(output_csv)  # Write the data

        # Assuming output_csv is a list of lists
    df = pd.DataFrame(output_csv, columns=['Timestamp','Job Match Rating', 'Link'])
    # Convert the DataFrame to an HTML table
    csv_table = df.to_html(index=False)

    csv_table =csv_table.replace('"', '\\"') 

    csv_blank=False
else:
    csv_blank=True

if len(output_summary)>0: # Only write the output data to a file if there is data to write
    output_summary.sort(reverse=True)    
    # Write the output data to the file
    with open(output_summary_filename, 'w', newline='') as file:
        file.writelines(output_summary)
    summary_blank=False
else:
    summary_blank=True


# Get today's date
today = datetime.today()
# Format the date
formatted_date = today.strftime("%m-%d-%Y")


if not csv_blank and not summary_blank:

    
    output_summary = '<hr>'.join(output_summary)

    output_summary = output_summary.replace('"', '\\"')

    command = f"""echo -e "To: {email}\nMIME-Version: 1.0\nContent-Type: text/html\nSubject: {formatted_date} Scroop\n<html>\n<body>\n<pre>\n{output_summary}\n</pre>\n<hr/>\n{csv_table}\n</body>\n</html>\n" | ssmtp {email}"""

elif not csv_blank:
    command = f"""echo -e "To: {email}\nMIME-Version: 1.0\nContent-Type: text/html\nSubject: {formatted_date} Scroop\n<html>\n<body>\n<pre>\n{csv_table}\n</pre>\n</body>\n</html>\n" | ssmtp {email}"""
else:
    command = f"echo -e \"To: {email}\nSubject: {formatted_date} Scroop Ran But Found Nothing\nBLANK\n\" |  ssmtp {email}"

# Write the command to a file
with open('command.txt', 'w') as file:
    file.write(command)

subprocess.run(command, shell=True, check=True)
