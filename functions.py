
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
from pprint import pprint

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

    # Use BeautifulSoup to parse the HTML if full_text is True, otherwise use the extract function
    text = BeautifulSoup(raw_page, 'html.parser').get_text() if full_text else extract(raw_page)

    # If text is None or empty, or not a string, or blank return False
    if not text or not isinstance(text, str) or not text.strip():
        return False

    # Strip HTML tags and remove extra linebreaks and whitespace
    clean_text = re.sub('\s*\n+\s*', '\n\n', text)

    # Unsmarten quotes
    clean_text = clean_text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    # Return the cleaned text
    return clean_text


def get_page_content(url, cache_age=72, debug=False):
    # Convert cache age to seconds
    cache_age *= 60 * 60

    if debug:
        print("get_page_content")
        print(f"cache age set to {cache_age} seconds")

    # Create a directory called 'cached_pages' if it doesn't exist
    os.makedirs('cached_pages', exist_ok=True)

    # Convert the URL to a filename by hashing it
    filename = hashlib.md5(url.encode()).hexdigest()

    # Construct the full file path
    filepath = os.path.join('cached_pages', filename)

    # If the file exists and is not older than the cache age, return its content
    if os.path.exists(filepath) and (cache_age < 0 or time.time() - os.path.getmtime(filepath) <= cache_age):
        if debug:
            print(f"cache {filepath} exists and is younger than {cache_age} seconds, using cached data")
        with open(filepath, 'r') as file:
            return file.read()

    if debug:
        print(f"cache {filepath} doesn't exist or is older than {cache_age} seconds, getting fresh data")

    # Get the raw page content
    output = selenium_get_raw_page(url, debug)

    # If the output is not None or empty, save it to a file and return it
    if output:
        with open(filepath, 'w') as file:
            file.write(str(output))
        if debug:
            print(f"writing out data for future cache {filepath}")
        return output

    # If the output is None or empty, return False
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




def link_cleaner(links, search_sites, debug=False):
    if debug:
        print("link_cleaner")

    # Extract the domain from each search site using the urlparse function
    search_domains = {urlparse(site).netloc for site in search_sites}

    # Initialize an empty list to store the clean links
    clean_links = []

    # Loop over each link in the list of links
    for link in links:
        # The link is a tuple, and the actual URL is the first element
        url = link[0]

        # Skip links that contain 'keywords='
        if 'keywords=' in url:
            continue

        # Handle LinkedIn links that are forwarders
        if 'externalApply'.lower() in url.lower():
            # Extract the actual URL from the forwarder
            url = unquote(url.split("?url=")[1].split("&urlHash=")[0])

        # Remove GET arguments from the URL
        url = urlunparse(urlparse(url)._replace(query="", fragment=""))

        # Skip links that have a domain that doesn't match the search sites
        if urlparse(url).netloc not in search_domains:
            continue

        # Add the cleaned link to the list
        clean_links.append(url)

    # Remove duplicates and return the cleaned list of links
    return list(set(clean_links))


def find_keywords(page_content, search_words, debug=False):
    # Convert the page content to lowercase once, to avoid doing it for each word
    page_content = page_content.lower()

    # Loop through each word in the search words
    for word in search_words:
        # Remove the double quotes from the search word and convert it to lowercase
        word = word.replace('"', '').lower()

        # Check if the search word appears in the page content
        if word in page_content:
            # If the search word is found, and debug mode is on, print a message
            if debug:
                print(f"\tFound search word '{word}' in page content")
            return True

    # If no search word is found in the page content after checking all the words, return False
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


# Maximum number of tokens for the compression tool
MAX_TOKENS = 450

# Disable parallelism for tokenizers to avoid potential issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def divide_sentence(sentence, n):

    # Split the sentence at spaces or commas
    pieces = re.split('[ ,]', sentence)

    # If there are fewer pieces than N
    if len(pieces) < n:
        # Return the pieces as they are
        return pieces

    # If there are at least N pieces
    else:
        # Initialize an empty list for the final pieces
        final_pieces = []

        # Calculate the size of each piece
        piece_size = len(pieces) // n

        # For each index in the range 0 to N
        for i in range(n):
            # If this is the last index
            if i == n - 1:
                # Add the remaining pieces to the final pieces
                final_pieces.append(' '.join(pieces[i * piece_size:]))
            else:
                # Add the next piece_size pieces to the final pieces
                final_pieces.append(' '.join(pieces[i * piece_size:(i + 1) * piece_size]))

        # Return the final pieces
        return final_pieces

def compress_prompt(text, debug=False):
    if debug:
        cprint("compress_prompt","yellow")
        print(f"Compressing prompt with {len(text)} characters")

    # Replace certain characters with periods to help sentence splitting
    text = re.sub(r'\n\n|[:;]', '. ', text, flags=re.MULTILINE)
    text = re.sub(r'^-\s+', '. ', text, flags=re.MULTILINE)
    text = re.sub(r'\n+', ' ', text, flags=re.MULTILINE)
    text = re.sub(r'\s+-\s+', ' . ', text, flags=re.MULTILINE)

    # Initialize the llm_lingua model and tokenizer
    llm_lingua = PromptCompressor(
        model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        use_llmlingua2=True,
    )
    tokenizer = AutoTokenizer.from_pretrained("microsoft/llmlingua-2-xlm-roberta-large-meetingbank")
    llm_lingua.tokenizer = tokenizer

    # Split the text into sentences
    sentences = nltk.sent_tokenize(text)

    sentences_shortened = []

    for sentence in sentences:
        if len(tokenizer.encode(sentence, truncation=False)) > MAX_TOKENS:
            peices = round(len(tokenizer.encode(sentence, truncation=False))/MAX_TOKENS)
            splits = divide_sentence(sentence, peices)
            sentences_shortened.extend(splits)
            print(f"Splitting sentence into {peices} pieces")
        else:
            sentences_shortened.append(sentence)
            #print(f"splitting not needed for sentence")

    # Loop over the sentences
    compressed_text = ""
    for sentence in sentences_shortened:
        compressed = llm_lingua.compress_prompt(sentence, rate=0.5, force_tokens = ['?','.','!'])
        compressed_text += compressed['compressed_prompt'] + ' '

    compressed_text = re.sub(r'\s+', ' ', compressed_text, flags=re.MULTILINE)

    # Return the compressed text, removing any trailing whitespace
    return compressed_text.strip()


import time

def gpt_true_or_false(prompt, model, open_ai_key, retries=3, debug=False):
    if debug:
        cprint("gpt_true_or_false","yellow")
    # Return None if the prompt is empty or None
    if not prompt.strip():
        if debug:
            print("\tPrompt is empty or None")
        return None

    # Try up to 'retries' times
    for i in range(retries):
        # Send the prompt to the Ollama API and get a response
        job_info = gpt_me(prompt, model, open_ai_key, debug)

        # Return True if the response contains "true", False if it contains "false"
        job_info_lower = job_info.lower()
        if "true" in job_info_lower:
            return True
        elif "false" in job_info_lower:
            return False
        else:
            # If the response contains neither "true" nor "false", print the first 500 characters of the response
            # and a message saying it's retrying, then continue to the next iteration of the loop
            if debug:
                print(f"Prompt: {prompt[:500]}")
                print(f"gpt reply: {job_info[:500]}")
                print("\tRetrying, didn't get True or False...")

        # Sleep for a progressively longer time with each retry
        time.sleep(5 * i)

    # If it's tried 'retries' times and still hasn't gotten a clear "true" or "false", return None
    return None



def gpt_range(prompt, model, open_ai_key, retries=3, debug=False):
    # Return None if the prompt is empty or None
    if not prompt.strip():
        if debug:
            print("\tPrompt is empty or None")
        return None

    # Try up to 'retries' times
    for i in range(retries):
        # Send the prompt to the Ollama API and get a response
        job_info = gpt_me(prompt, model, open_ai_key, debug)

        # Remove all non-digit characters from the response and convert it to an integer
        job_info = re.sub(r'\D', '', job_info)
        job_info = int(job_info) if job_info else None

        if debug:
            print(f"Prompt: {prompt[:500]}")
            print(f"gpt reply: {job_info}")

        # If the response is a number between 1 and 10, return it
        if 1 <= job_info <= 10:
            return job_info
        else:
            # If the response isn't a number between 1 and 10, print a message saying it's retrying,
            # then continue to the next iteration of the loop
            if debug:
                print("\tRetrying, didn't get a number between 1 and 10...")

        # Sleep for a progressively longer time with each retry
        time.sleep(5 * i)

    # If it's tried 'retries' times and still hasn't gotten a number between 1 and 10, return None
    return None


def selenium_get_raw_page(page_url, debug=False):
    # If debug mode is on, print a message
    if debug:
        print("selenium_get_raw_page")

    try:
        # Create a UserAgent object
        ua = UserAgent()

        # List of possible screen sizes
        screen_sizes = ["1024x768", "1280x800", "1366x768", "1440x900", "1920x1080", "3840x2160"]
        # Choose a random screen size from the list
        screen_size = random.choice(screen_sizes)
        # Set the window size to the chosen screen size

        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument(f"user-agent={ua.random}")  # Set the user agent to a random one
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disable automation detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Disable automation detection
        chrome_options.add_argument(f"--window-size={screen_size}")

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
    except Exception as e:
        # If an error occurs, print the error and return False
        print(f"An error occurred: {e}")
        return False

def get_search_links(url, search_sites):
    # Fetch the page content
    page_content = get_page_content(url, 8)

    # If the page content was successfully fetched
    if page_content:
        # Extract the links from the page content
        fresh_links = extract_links(page_content)

        # Clean the extracted links by making sure they contain the search site URL and removing duplicates
        fresh_links = link_cleaner(fresh_links, search_sites)

        # Return the cleaned links
        return fresh_links

    # If the page content could not be fetched, return an empty list
    return []

def process_link(link, search_words):
    # Fetch the page content and cache it for 30 days (720 hours = 30 days)
    page_content_raw = get_page_content(link, 720)

    # Extract the body text from the page content
    page_content = get_page_body_text(page_content_raw)

    # If there is body text
    if page_content:
        # Check if any of the search words are in the body text
        found_word = find_keywords(page_content, search_words)

        # If a search word was not found
        if not found_word:
            # Log the link
            with open("scanned_sites.log", 'a') as file:
                file.write(f"{link}\n")
            return 1
    return 0


def generate_gpt_summary(link, open_ai_key, debug=False):
    # Fetch the page content and cache it for 30 days (720 hours = 30 days)
    page_content_raw = get_page_content(link, 720)

    # Extract the body text from the page content
    page_content = get_page_body_text(page_content_raw)

    # If there is page content and it's at least 50 characters long
    if page_content and len(page_content) >= 50:
        # Generate the filename for the summary file
        filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
        filepath = os.path.join('cached_pages', filename)

        # If the summary file doesn't exist
        if not os.path.exists(filepath):
            # Generate a summary of the page content using the GPT-3.5-turbo model
            prompt = f"Please read this job listing and write a concise summary of required skills, degrees, etc:\n\n{compress_prompt(page_content)}"
            job_summary = gpt_me(prompt, "gpt-3.5-turbo", open_ai_key, debug)

            # Save the summary to the file
            with open(filepath, 'w') as file:
                file.write(job_summary)
        else:
            # If the summary file exists, read the summary from the file
            with open(filepath, 'r') as file:
                job_summary = file.read()

        # Return the summary
        return job_summary

    # If there is no page content or it's less than 50 characters long, return False
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