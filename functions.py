
# Standard library imports
import hashlib
import os
import random
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, quote, unquote, urljoin, urlunparse

# Related third party imports
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from llmlingua import PromptCompressor
import nltk
from nltk import download
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from termcolor import cprint
from trafilatura import extract
from transformers import AutoTokenizer
from webdriver_manager.chrome import ChromeDriverManager

# Local application/library specific imports
import selenium.webdriver.support.ui as ui
from selenium.common.exceptions import NoSuchElementException
import secrets


    
def get_page_body_text(raw_page, full_text=False, debug=False):
    if debug:
        cprint("get_page_body_text","yellow")

    # If raw_page is None or empty, or not a string, return False
    if not raw_page or not isinstance(raw_page, str):
        return False

    if full_text:
        soup = BeautifulSoup(raw_page, 'html.parser')
        # Use the get_text method to extract all the text, stripping away the HTML
        text = soup.get_text()
    else:
        # Extract the main text from the raw page
        text = extract(raw_page)

    # If text is None or empty, or not a string, or blank return False
    if not text or not isinstance(text, str) or text.strip() == "":
        return False

    # Strip HTML tags and remove extra linebreaks and whitespace
    clean_text = re.sub('\s*\n+\s*', '\n\n', text)

    # Unsmarten quotes
    clean_text = clean_text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    # Return the cleaned text
    return clean_text



def get_page_content(url, cache_age=72, debug=False): #default cache age is 72 hours, set to zero or a negative number to always get fresh data
    cache_age = cache_age * 60 * 60 #convert cache age to seconds
    if debug:
        cprint("get_page_content","yellow")
        cprint(f"cache age set to {cache_age} seconds","yellow")
    # Create a directory called 'cached_pages' if it doesn't exist
    if not os.path.exists('cached_pages'):
        os.makedirs('cached_pages')

    # Convert the URL to a filename by dropping non-filename-stuff
    filename = hashlib.md5(url.encode()).hexdigest()

    # Check if the file exists in the 'cached_pages' directory
    filepath = os.path.join('cached_pages', filename)
    if os.path.exists(filepath):
        if debug:
            print(f"\tcache {filepath} exists")

        if cache_age >= 0:
            # Get the time the file was last modified
            file_time = os.path.getmtime(filepath)
            # Get the current time
            current_time = time.time()
            # Calculate the difference in seconds
            difference = current_time - file_time
            # If the difference is greater than the cache age, return False
            if difference > cache_age:
                if debug:
                    print(f"\tcache {filepath} is older than {cache_age} seconds, getting fresh data")
            else:
                if debug:
                    print(f"\tcache {filepath} is younger than {cache_age} seconds, using cached data")
                with open(filepath, 'r') as file:
                    return file.read()
    if debug:
        print(f"\tcache {filepath} doesn't exist, collecting")

    output = selenium_get_raw_page(url, debug)
    if output:
        # Save the output to a file in the 'cached_pages' directory
        with open(filepath, 'w') as file:
            file.write(str(output))
        if debug:
            cprint(f"writing out data for future cache {filepath}","blue")
        return output
    return False


# This function extracts all URLs from the content of a webpage
def extract_links(page_content, debug=False):
    # If debug mode is on, print the function name
    if debug:
        cprint("extract_links","yellow")
    
    # This is a regular expression (regex) that matches URLs
    url_regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"

    # Use the regex to find all URLs in the page content
    urls = re.findall(url_regex, page_content)

    # Return the list of URLs
    return urls


# This function cleans a list of links by removing any that have a domain dont match the search sites (ie link is facebook.com but search site is linkedin.com)
def link_cleaner(links, search_sites, debug=False):
    # If debug mode is on, print a message indicating that the function is running
    if debug:
        cprint("link_cleaner","yellow")
    
    # Extract the domain from each search site using the urlparse function
    search_domains = [urlparse(site).netloc for site in search_sites]
    
    # Initialize an empty list to store the clean links
    clean_links = []
    
    # Loop over each link in the list of links
    for link in links:

        # Assume that the link should be saved until proven otherwise
        save_link = True

        # The link is a tuple, and the actual URL is the first element
        first_value = link[0]

        #check if the string 'keywords=', keeps the search page from being scanned (lots of false positives on good job matches)
        if 'keywords=' in first_value:
            save_link = False
        
        #some linkedin links are funny forwarders, we'll deal with those here/
        #for reference thy look like this:
        # https://www.linkedin.com/jobs/view/externalApply/3908274991?url=https%3A%2F%2Fawe%2Ewd1%2Emyworkdayjobs%2Ecom%2FArt_and_Wellness%2Fjob%2FBentonville-AR%2FTechnical-Services-Librarian\u002d\u002dLibrary-and-Archives_JR960%3Fsource%3DLinkedin&urlHash=2ghE
        if 'externalApply'.lower() in first_value.lower():
            # Split the link at "?url="
            parts = first_value.split("?url=")
            # Keep only the second half
            second_half = parts[1]
            # Run urldecode on the second half
            decoded_url = unquote(second_half)
            # Split the decoded URL at "&urlHash="
            decoded_url  = decoded_url.split("&urlHash=")
            # Keep only the first part
            decoded_url  = decoded_url [0]
            first_value = decoded_url
            
        # Removing GET arguments from the urls in case they change and don't match the sites we've already scanned
        # ie asdf.com/page.html?hash=1234 and asdf.com/page.html?hash=5678 would be the same page, but would be scanned twice
        # Parse the URL and remove the GET arguments
        parsed_url = urlparse(first_value)
        first_value = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "", ""))
        
        # Extract the domain from the link
        link_domain = urlparse(first_value).netloc
        
        # Check if the domain is in the list of search domains
        # If it is, set save_link to False
        if link_domain not in search_domains:
            save_link = False




        # If save_link is still True, add the link to the list of clean links
        if save_link:
            clean_links.append(first_value)

    # Remove any duplicates from the list of clean links
    clean_links = list(set(clean_links))
    
    # Return the list of clean links
    return clean_links


# This function checks if any of the search words appear in the page content
def find_keywords(page_content, search_words, debug=False):
    # Loop through each word in the search words
    for word in search_words:
        # Remove the double quotes from the search word
        word = word.replace('"', '')
        
        # Check if the search word appears in the page content
        if word.lower() in page_content.lower():
            # If the search word is found, and debug mode is on, print a message
            if debug:
                print(f"\tFound search word '{word}' in page content")
            return True

    # If no search word is found in the page content after checking all the words return False
    return False


def gpt_me(prompt, model, key, debug=False):
    # If debug mode is on, print the function name
    if debug:
        cprint("gpt_me", "yellow")

    # Initialize the OpenAI client with the provided API key
    client = OpenAI(api_key=key)

    # Create a chat completion with the OpenAI API using the provided prompt and model
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
    )

    # If debug mode is on, print the first 250 characters of the response
    if debug:
        print(chat_completion.choices[0].message.content[:250])

    # Return the full response
    return chat_completion.choices[0].message.content



# Code to compress text for making the OpenAI API calls cheaper.
# The maximum number of tokens for the compression tool is 512, so we'll set it to 450 to be safe.
# Many of the job descriptions are longer than 512 tokens, so we'll need to split them into smaller chunks. 
# We'll also disable parallelism for the tokenizers to avoid potential issues.
MAX_TOKENS = 450
# Disable parallelism for tokenizers to avoid potential issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Function to compress a buffer of text
def compress_buffer(llm_lingua, buffer, debug=False):
    # If debug mode is on, print the number of tokens in the buffer
    if debug:
        print(f"Compressing buffer with {len(tokenizer.encode(buffer, truncation=False, max_length=MAX_TOKENS))} tokens")
    # Compress the buffer using the llm_lingua model
    compressed = llm_lingua.compress_prompt(buffer, rate=0.5, force_tokens = ['?','.','!'])
    # Return the compressed text
    return compressed['compressed_prompt']

# Function to compress a prompt
def compress_prompt(text, debug=False):
    # If debug mode is on, print the number of characters in the text
    if debug:
        print(f"Compressing prompt with {len(text)} characters")

    # helping the sentence splitting, replace some characters with periods
    text = re.sub(r'\n\n', '. ', text, flags=re.MULTILINE) # replace double linebreaks with a period, since it's a seperate thought
    text = re.sub(r'^-\n', '.\n', text, flags=re.MULTILINE) # make it so lists that start with a dash are split into seperate sentences
    text = re.sub(r'\n+', ' ', text, flags=re.MULTILINE) # replace linebreaks with spaces
    text = re.sub(r'\s+-\s+', ' . ', text, flags=re.MULTILINE) # replace dashes with spaces with periods
    text = re.sub(r'[:;]', '. ', text, flags=re.MULTILINE) # replace semicolons and colons with periods
    

    # Initialize the llm_lingua model
    llm_lingua = PromptCompressor(
        model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        use_llmlingua2=True,
    )
    
    # Initialize the tokenizer
    tokenizer = AutoTokenizer.from_pretrained("microsoft/llmlingua-2-xlm-roberta-large-meetingbank")

    # Split the text into sentences
    sentences = nltk.sent_tokenize(text)
    
    # Initialize the compressed text and buffer
    compressed_text = ""
    buffer = ""
    # Loop over the sentences
    for sentence in sentences:
        # Check if the sentence itself exceeds MAX_TOKENS
        if len(tokenizer.encode(sentence, truncation=False, max_length=MAX_TOKENS)) > MAX_TOKENS:
            
            mid_index = len(sentence) // 2
            for i in range(mid_index, len(sentence)):
                if sentence[i] == ' ':
                    middle_space =  i
                if sentence[mid_index - (i - mid_index)] == ' ':
                    middle_space = mid_index - (i - mid_index)
            
            print(f"middle_space: {middle_space}, trying to split:\n\n{sentence}\n")
            # Split the sentence into two parts at the middle space
            compressed_text += f"{compress_buffer(llm_lingua, sentence[:middle_space], debug)} {compress_buffer(llm_lingua, sentence[middle_space:], debug)} "


        # If adding the sentence to the buffer doesn't exceed the maximum number of tokens
        elif len(tokenizer.encode(f"{buffer}{sentence}", truncation=False, max_length=MAX_TOKENS)) <= MAX_TOKENS:
            # If debug mode is on, print the number of tokens in the sentence and the total number of tokens
            if debug:
                print(f"Adding sentence with {len(tokenizer.encode(sentence, truncation=False, max_length=MAX_TOKENS))} tokens total = {len(tokenizer.encode(f'{buffer}{sentence}', truncation=False, max_length=MAX_TOKENS))} tokens")
            # Add the sentence to the buffer
            buffer += f"{sentence} "
        else:
            # If adding the sentence to the buffer would exceed the maximum number of tokens, compress the buffer and add it to the compressed text
            compressed_text += f"{compress_buffer(llm_lingua, buffer, debug)} "
            # Start a new buffer with the current sentence
            buffer = f"{sentence} "
    
    # If there's any text left in the buffer, compress it and add it to the compressed text
    if buffer:
        compressed_text += f"{compress_buffer(llm_lingua, buffer, debug)} "
    
    # If debug mode is on, print the compressed text
    if debug:
        print(compressed_text)
    # Return the compressed text, removing any trailing whitespace
    return compressed_text.strip()


# This function checks if a job is relevant by asking the chatgpt API
def gpt_true_or_false(prompt, model, open_ai_key, retries=3, debug=False):
    if debug:
        cprint("gpt_true_or_false","yellow")

    if prompt.strip() == "" or prompt == None or prompt == False:
        if debug:
            cprint("\tPrompt is empty or None","red")
        return None
    
    # It tries up to 'retries' times
    for i in range(retries):
        # It sends the prompt to the Ollama API and gets a response
        job_info = gpt_me(prompt, model, open_ai_key, debug)
        # If the response contains "true", it returns True and "green"
        if "true" in job_info.lower():
            return True
        elif "false" in job_info.lower():
            return False
        # If the response contains neither "true" nor "false", it prints the first 500 characters of the response
        # and a message saying it's retrying, then continues to the next iteration of the loop
        else:
            if debug:
                print(f"Prompt: {prompt[:500]}")
                print(f"gpt reply: {job_info[:500]}")
                cprint("\tRetrying, didn't get True or False...","red")
        time.sleep(5*i)
    # If it's tried 'retries' times and still hasn't gotten a clear "true" or "false", it returns None and "red"
    return None


# This function checks if a job is relevant by asking the chatgpt API
def gpt_range(prompt, model, open_ai_key, retries=3, debug=False):
    if debug:
        cprint("gpt_range","yellow")

    if prompt.strip() == "" or prompt == None or prompt == False:
        if debug:
            cprint("\tPrompt is empty or None","red")
        return None
    
    # It tries up to 'retries' times
    for i in range(retries):
        # It sends the prompt to the Ollama API and gets a response
        job_info = gpt_me(prompt, model, open_ai_key, debug)
        job_info = re.sub(r'\D', '', job_info)
        job_info = int(job_info)

        if debug:
            print(f"Prompt: {prompt[:500]}")
            print(f"gpt reply: {job_info[:500]}")
            cprint("\tRetrying, didn't get a number...","red")

        # If the response contains "true", it returns True and "green"
        if 1 <= job_info <= 10:
            return job_info
        # If the response isn't an integer it retries
        # and a message saying it's retrying, then continues to the next iteration of the loop
        else:
            if debug:
                print(f"Prompt: {prompt[:500]}")
                print(f"gpt reply: {job_info[:500]}")
                cprint("\tRetrying, didn't get True or False...","red")
        time.sleep(5*i)
    # If it's tried 'retries' times and still hasn't gotten a clear "true" or "false", it returns None and "red"
    return None


def selenium_get_raw_page(page_url, debug=False):
    # If debug mode is on, print a message
    if debug:
        cprint("selenium_get_raw_page","yellow")

    try:
        # Create a UserAgent object
        ua = UserAgent()

        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument(f"user-agent={ua.random}")  # Set the user agent to a random one
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disable automation detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Disable automation detection
        if not debug:
            chrome_options.add_argument("--headless")  # Run in headless mode if not in debug mode

        # Create a WebDriver object
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        # Navigate to the page
        driver.get(url=page_url)

        # Wait for the page to load
        time.sleep(5)

        for _ in range(20):
            # Add some random mouse movements
            action = ActionChains(driver)
            action.move_by_offset(random.randint(1, 10), random.randint(1, 10))
            action.perform()

            # Get the page content
            page_content = get_page_body_text(driver.page_source,True,False)

            # If the page content is not found or is too short, wait and try again
            if page_content == False:
                continue
            elif len(page_content)>=250:
                break

            time.sleep(1)

        # Convert all relative links to absolute
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for a in soup.find_all('a', href=True):
            a['href'] = urljoin(page_url, a['href'])

        # Close the browser
        driver.quit()

        # Return the page source
        return str(soup)
    except:
        # If an error occurs, return False
        return False


def get_search_links(url,search_sites):
    page_content = get_page_content(url, 8)

    # If the page content was successfully fetched
    if page_content:
        # Extract the links from the page content and add them to the list of links
        fresh_links = extract_links(page_content)
        # Clean the extracted links by making sure they contain the search site URL and removing duplicates
        fresh_links = link_cleaner(fresh_links, search_sites)
        # Extend the list of links with the fresh links
        return(fresh_links)
    else:
        return([])

def process_link(link, search_words):
    page_content_raw = get_page_content(link, 720) # keep reusing cached pages for 30 days (720 hours = 30 days)
    page_content = get_page_body_text(page_content_raw)

    # If there is page content
    if page_content:
        #make sure at least one of our keywords is in the page content
        found_word = find_keywords(page_content, search_words)
        if not found_word:
            with open("scanned_sites.log", 'a') as file:
                file.write(f"{link}\n")
            return 1
    return 0

def generate_gpt_summary(link, open_ai_key, debug=False):
    if debug:
        cprint("generate_gpt_summary","yellow")

    page_content_raw = get_page_content(link, 720) # keep reusing cached pages for 30 days (720 hours = 30 days)
    # Extract the body text from the page content
    page_content = get_page_body_text(page_content_raw)
    

    # If there is page content
    if page_content and len(page_content)>=50:
        if debug:
            print(f"page_content: {page_content[:250]}")

        filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
        filepath = os.path.join('cached_pages', filename)
        if debug:
            print(filepath)
        if not os.path.exists(filepath):
            # Use the LLM to generate a summary of the job listing
            prompt = f"Please read this job listing and write a consise summary of required skills, degrees, etc:\n\n{compress_prompt(page_content)}"
            job_summary = gpt_me(prompt,"gpt-3.5-turbo",open_ai_key,debug)
            with open(filepath, 'w') as file:
                file.write(job_summary)
        else:
            with open(filepath, 'r') as file:
                job_summary = file.read()
                
        return job_summary
    
    return False

def generate_gpt_job_match(link, bullet_resume, open_ai_key, debug=False):
    if debug:
        random_number = secrets.randbelow(999) + 1
        debug_timestamp = time.time()

        cprint("generate_gpt_job_match","yellow")

    filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
    filepath = os.path.join('cached_pages', filename)

    if debug:
        print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- hash and filepath")
        debug_timestamp = time.time()
    if not os.path.exists(filepath):
        return False
    else:
        with open(filepath, 'r') as file:
            job_summary = file.read()
    if debug:        
        print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- read job summary")
        debug_timestamp = time.time()
    if len(job_summary) >=50:
        filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
        filepath = os.path.join('cached_pages', filename)
        if debug:
            print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- hash and filepath 2")
            debug_timestamp = time.time()
        if not os.path.exists(filepath):
            # Use the LLM to generate a summary of the job listing
            prompt = f"Read the applicant's RESUME and JOB SUMMARY below and determine if the applicant is a good fit for this job on a scale of 1 to 10. 1 is a bad fit, 10 is a perfect fit. REPLY WITH AN INTEGER 1-10!!!\n\nJOB SUMMARY:  {compress_prompt(bullet_resume)}\n\nJOB SUMMARY:  {compress_prompt(job_summary)}"
            job_is_a_good_match = gpt_range(prompt,"gpt-4o", open_ai_key,True)
            with open(filepath, 'w') as file:
                file.write(str(job_is_a_good_match))
            if debug:    
                print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- gpt and write job match")
                debug_timestamp = time.time()
        else:
            with open(filepath, 'r') as file:
                job_is_a_good_match = file.read()
            if debug:
                print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- read job match cache")
                debug_timestamp = time.time()
        if debug:
            print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- returning job match\n\n\n\n\n")
            debug_timestamp = time.time()
        return job_is_a_good_match
    if debug:
        print(f"{random_number} - {round(time.time()-debug_timestamp,1)} -- returning False\n\n\n\n\n")
        debug_timestamp = time.time()
    
    return False