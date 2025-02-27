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
import concurrent.futures
from operator import itemgetter
import shutil
import csv
import pandas as pd

from termcolor import cprint
from tqdm import tqdm

from config import *
from functions import *
import subprocess
import time


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

# Calculate total number of search URLs for better progress tracking
total_search_urls = len(site_search_list)
print(f"Processing {total_search_urls} search URLs...")

# Create a shared counter for progress tracking
processed_urls = 0
found_links = 0
failed_urls = 0

# Import threading Lock for thread-safe counter updates
import threading
progress_lock = threading.Lock()

# Function to process a single URL and handle errors
def process_single_url(url, search_sites):
    global processed_urls, found_links, failed_urls, cached_pages_used
    
    # Check if we have a recent cached version of this search page
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = os.path.join('cached_pages', f"{url_hash}_search.html")
    
    # Check if cache file exists and is less than 12 hours old
    use_cache = False
    if os.path.exists(cache_file):
        file_time = os.path.getmtime(cache_file)
        current_time = datetime.now().timestamp()
        hours_old = (current_time - file_time) / 3600
        
        if hours_old < 12:
            use_cache = True
            
    try:
        if use_cache:
            # Read links from cache
            with open(cache_file, 'r', encoding='utf-8', errors='ignore') as f:
                page_content = f.read()
            
            # Extract links from cached content
            all_links = extract_links(page_content)
            result = link_cleaner(all_links, search_sites)
            
            # Update progress with cache info
            with progress_lock:
                processed_urls += 1
                found_links += len(result)
                cached_pages_used += 1
                progress_bar.update(1)
                progress_bar.set_postfix({
                    "processed": f"{processed_urls}/{total_search_urls}",
                    "links": found_links,
                    "cached": f"{cached_pages_used}/{processed_urls}",
                    "failed": failed_urls
                })
        else:
            # Get links from this URL
            result = get_search_links([url], search_sites)
            
            # Save the page content to cache
            driver = initialize_selenium_browser()
            try:
                raw_page = selenium_get_raw_page(driver, url)
                # Save to cache
                os.makedirs('cached_pages', exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(raw_page)
            except Exception as e:
                print(f"Warning: Could not cache search page: {url}\n{str(e)}")
            finally:
                driver.quit()
            
            # Update progress
            with progress_lock:
                processed_urls += 1
                found_links += len(result)
                progress_bar.update(1)
                progress_bar.set_postfix({
                    "processed": f"{processed_urls}/{total_search_urls}",
                    "links": found_links,
                    "cached": f"{cached_pages_used}/{processed_urls}",
                    "failed": failed_urls
                })
                
        success = True
    except Exception as e:
        print(f"Error processing URL: {url}\n{str(e)}")
        result = []
        success = False
        
        # Update counters for failed URLs
        with progress_lock:
            processed_urls += 1
            failed_urls += 1
            progress_bar.update(1)
            progress_bar.set_postfix({
                "processed": f"{processed_urls}/{total_search_urls}",
                "links": found_links,
                "failed": failed_urls
            })
    
    return result

# Get the search links from the search sites
print("Starting search process - this may take a while...")
all_links = []

# Create a progress bar with more detailed information
progress_bar = tqdm(
    total=total_search_urls,
    desc="Searching job sites",
    unit="URL",
    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} URLs [{elapsed}<{remaining}, {rate_fmt}]"
)

# Track how many pages we get from cache
cached_pages_used = 0

with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit all tasks and get futures
    futures = [
        executor.submit(process_single_url, url, search_sites)
        for url in site_search_list
    ]
    
    # Process futures as they complete
    for future in concurrent.futures.as_completed(futures):
        try:
            result = future.result()
            all_links.extend(result)
        except Exception as e:
            print(f"Error in future: {str(e)}")

progress_bar.close()
links = all_links

print(f"\nSearch complete: {processed_urls} URLs processed, {found_links} links found, {cached_pages_used} from cache, {failed_urls} failed")

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

# Process individual links instead of batches for better progress tracking
total_links_to_process = len(links)
processed_links_count = 0
skipped_links_count = 0
failed_links_count = 0

print(f"Processing {total_links_to_process} links for caching and filtering...")

# Function to process a single link and handle errors
def process_single_link(link, search_words, must_have_words, anti_keywords):
    global processed_links_count, skipped_links_count, failed_links_count
    try:
        # Check if this link should be skipped
        should_skip = process_links([link], search_words, must_have_words, anti_keywords)
        success = True
        skipped = should_skip
    except Exception as e:
        print(f"Error processing link: {link}\n{str(e)}")
        success = False
        skipped = 0
    
    # Update counters
    with progress_lock:
        processed_links_count += 1
        if not success:
            failed_links_count += 1
        else:
            skipped_links_count += skipped
        
        # Update progress bar
        cache_progress_bar.update(1)
        cache_progress_bar.set_postfix({
            "processed": f"{processed_links_count}/{total_links_to_process}",
            "skipped": skipped_links_count,
            "failed": failed_links_count
        })
    
    return skipped

# Create a progress bar for caching and filtering
cache_progress_bar = tqdm(
    total=total_links_to_process,
    desc="Caching & filtering pages",
    unit="link",
    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} links [{elapsed}<{remaining}, {rate_fmt}]"
)

skipped = 0

with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit all tasks and get futures
    futures = [
        executor.submit(process_single_link, link, search_words, must_have_words, anti_kewords)
        for link in links
    ]
    
    # Process futures as they complete
    for future in concurrent.futures.as_completed(futures):
        try:
            result = future.result()
            skipped += result
        except Exception as e:
            print(f"Error in future: {str(e)}")

cache_progress_bar.close()
print(f"\nCaching complete: {processed_links_count} links processed, {skipped_links_count} skipped, {failed_links_count} failed")
    
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

# Create a progress bar for GPT summary generation
total_links_for_gpt = len(links)
processed_gpt_count = 0
failed_gpt_count = 0

print(f"Generating summaries for {total_links_for_gpt} jobs...")

# Function to process a single link for GPT summary and handle errors
def process_gpt_summary(link, api_key):
    global processed_gpt_count, failed_gpt_count
    try:
        result = generate_gpt_summary(link, api_key)
        success = True
    except Exception as e:
        print(f"Error generating summary for: {link}\n{str(e)}")
        result = None
        success = False
    
    # Update counters
    with progress_lock:
        processed_gpt_count += 1
        if not success:
            failed_gpt_count += 1
        
        # Update progress bar
        gpt_progress_bar.update(1)
        gpt_progress_bar.set_postfix({
            "processed": f"{processed_gpt_count}/{total_links_for_gpt}",
            "failed": failed_gpt_count,
            "success_rate": f"{(processed_gpt_count-failed_gpt_count)/processed_gpt_count:.1%}" if processed_gpt_count > 0 else "0%"
        })
    
    return result

gpt_progress_bar = tqdm(
    total=total_links_for_gpt,
    desc="Generating job summaries",
    unit="job",
    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} jobs [{elapsed}<{remaining}, {rate_fmt}]"
)

with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit all tasks and get futures
    futures = [
        executor.submit(process_gpt_summary, link, open_ai_key)
        for link in links
    ]
    
    # Process futures as they complete
    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()  # Get the result (or exception)
        except Exception as e:
            print(f"Error in future: {str(e)}")

gpt_progress_bar.close()
print(f"\nSummary generation complete: {processed_gpt_count} jobs processed, {failed_gpt_count} failed")

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

# Create a progress bar for job match generation
total_links_for_match = len(links)
processed_match_count = 0
failed_match_count = 0

print(f"Generating job matches for {total_links_for_match} jobs...")

# Function to process a single link for job match and handle errors
def process_job_match(link, resume, api_key):
    global processed_match_count, failed_match_count
    try:
        result = generate_gpt_job_match(link, resume, api_key)
        success = True
    except Exception as e:
        print(f"Error generating job match for: {link}\n{str(e)}")
        result = None
        success = False
    
    # Update counters
    with progress_lock:
        processed_match_count += 1
        if not success:
            failed_match_count += 1
        
        # Update progress bar
        match_progress_bar.update(1)
        match_progress_bar.set_postfix({
            "processed": f"{processed_match_count}/{total_links_for_match}",
            "failed": failed_match_count,
            "success_rate": f"{(processed_match_count-failed_match_count)/processed_match_count:.1%}" if processed_match_count > 0 else "0%"
        })
    
    return result

match_progress_bar = tqdm(
    total=total_links_for_match,
    desc="Generating job matches",
    unit="job",
    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} jobs [{elapsed}<{remaining}, {rate_fmt}]"
)

results = []

with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit all tasks and get futures
    futures = [
        executor.submit(process_job_match, link, bullet_resume, open_ai_key)
        for link in links
    ]
    
    # Process futures as they complete
    for future in concurrent.futures.as_completed(futures):
        try:
            result = future.result()
            if result is not None:
                results.append(result)
        except Exception as e:
            print(f"Error in future: {str(e)}")

match_progress_bar.close()
print(f"\nJob match generation complete: {processed_match_count} jobs processed, {failed_match_count} failed")
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
