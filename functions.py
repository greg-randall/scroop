
"""
get_page_body_text
    Variables: raw_page, full_text, debug
    This function takes raw HTML page content and optionally returns the full text or the main text. It cleans the text by removing HTML tags, extra linebreaks, whitespace, and smart quotes.

    
ollama_me
    Variables: prompt, debug
    This function sends a user message to the Ollama LLM API and returns the API's response. If an error occurs while sending the message, it returns None.

    
page_content_valid
    Variables: page_content, debug
    This function checks if the page content is valid. It uses the Ollama LLM to validate the content. If the content is not valid or if a valid response is not received from the Ollama function after 3 tries, it returns False. Otherwise, it returns True.

    
basic_pull
    Variables: url, debug
    This function sends a GET request to the provided URL and returns the text content of the response if it is valid. If an error occurs during the request or if the page content is not valid, it returns False.

    
lynx_pull
    Variables: url, debug
    This function uses the 'lynx' command to fetch the HTML content of the page at the provided URL. If the page content is valid, it returns the content; otherwise, it returns False. If an error occurs during the command execution, it prints the error and returns False.

    
pyppeteer_get_page_raw
    Variables: url, debug
    This function launches a new browser instance, opens a new page, applies stealth measures to avoid being detected as a bot, navigates to the provided URL, and returns the HTML content of the page.

    
pyppeteer_pull
    Variables: url, debug
    This function uses the pyppeteer_get_page_raw function to fetch the HTML content of the page at the provided URL. If the page content is valid, it returns the content; otherwise, it returns False. If an error occurs during the page fetching, it prints the error and returns False.


get_page_content
    Variables: url, cache_age, debug
    This function checks if the content of the page at the provided URL is cached. If the cached content is older than the cache age, or if there is no cached content, it fetches the page content using one of the available methods (basic_pull, lynx_pull, pyppeteer_pull) and caches it. If the cached content is younger than the cache age, it returns the cached content.


extract_links
    Variables: page_content, current_page, debug
    This function extracts all URLs from the content of a webpage, excluding the URL of the current page. It uses a regular expression to find the URLs.


link_cleaner
    Variables: links, search_sites, debug
    This function cleans a list of links by removing any that have a domain that is in a list of search sites. It returns the cleaned list of links.


make_list_human_readable
    Variables: words, debug
    This function takes a list of words and formats it into a human-readable string. It returns the formatted string. ie ['thing1', 'thing2', 'thing3'] to 'thing1, thing2, and thing3'


ollama_true_or_false
    Variables: prompt, retries, debug
    This function checks if a job is relevant by asking the Ollama API. It tries up to 'retries' times to get a clear "true" or "false" response. If it gets a "true" response, it returns True; if it gets a "false" response, it returns False; if it doesn't get a clear response after 'retries' times, it returns None.


find_keywords
    Variables: page_content, search_words, debug
    This function checks if any of the search words appear in the page content. If a search word is found, it returns True; if no search word is found after checking all the words, it returns False.

"""




from bs4 import BeautifulSoup
from pyppeteer import launch
from pyppeteer_stealth import stealth
from termcolor import cprint
from trafilatura import extract
from urllib.parse import urlparse, quote
import asyncio
import hashlib
from llmlingua import PromptCompressor
import nltk
import ollama
from openai import OpenAI
import os
import random
import re
import requests
import subprocess
import time
from transformers import AutoTokenizer
import xml.etree.ElementTree as ET





    
def get_page_body_text(raw_page, full_text=False, debug=False):
    if debug:
        cprint("get_page_body_text","yellow")

    # If raw_page is None or empty, return False
    if not raw_page or not isinstance(raw_page, str):
        return False

    if full_text:
        soup = BeautifulSoup(raw_page, 'html.parser')
        # Use the get_text method to extract all the text, stripping away the HTML
        text = soup.get_text()
    else:
        # Extract the main text from the raw page
        text = extract(raw_page)

    # Strip HTML tags and remove extra linebreaks and whitespace
    clean_text = re.sub('\s*\n+\s*', '\n\n', text)

    # Unsmarten quotes
    clean_text = clean_text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')

    # Return the cleaned text
    return clean_text

# This function sends a message to the Ollama API and returns the response
def ollama_me(prompt, debug=False):
    # If debug is True, print the function name and the first 250 characters of the prompt
    if debug:
        cprint("ollama_me","yellow")
        cprint(f"prompt: {prompt[:250]}","yellow")
    
    try:
        # Send a message to the Ollama API using the 'llama3' model
        # The message content is the 'prompt' parameter
        #response = ollama.chat(model='llama3', messages=[
        response = ollama.chat(model='dolphin-llama3', messages=[
        {
            'role': 'user',
            'content': prompt,
        },
        ])
    except Exception as e:
        # If an exception occurs while sending the message, print the error message if debug is True
        # and return None
        if debug:
            cprint(f"ollama_me Error:\n\t{e}","magenta")
        return None
    
    if debug:
        cprint(f"-----------------------------------------\nresponse: {response['message']['content']}","yellow")
    

    # If the message was sent successfully, return the content of the response
    return response['message']['content']


def page_content_valid(page_content, debug=False):
    if debug:
        cprint("page_content_valid","yellow")
    # If page_content is not a string or contains 'incapsula' or 'about lynx', return False
    if not isinstance(page_content, str) or 'incapsula' in page_content.lower() or "about lynx" in page_content.lower():
        return False

    try: # check to see if the page is an RSS feed, if it is return True
        root = ET.fromstring(page_content)
        if root.tag == "rss" or root.tag == "feed":
            return True
    except ET.ParseError:
        if debug:
            cprint("\tPage content is not valid XML","yellow")  
    
    # Get the first 2000 characters of the cleaned page content (just to save time and resources)
    clean_page_content = get_page_body_text(page_content)[:2000]

    # Construct the prompt for the Ollama function
    prompt = "Does this look an actual page of content? Reply with TRUE or FALSE!!!!!\n\n" + clean_page_content

    # Try to get a valid response from the Ollama function up to 3 times
    for _ in range(3):
        # Call the Ollama function and convert its output to a lowercase string
        ollama_output = str(ollama_me(prompt)).lower()
        # If the output contains 'true', return True
        if "true" in ollama_output:
            return True
        # If the output contains 'false', return False
        elif "false" in ollama_output:
            return False
        # If the output doesn't contain either 'true' or 'false', print a message and try again
        else:
            if debug:
                cprint(f"\tOllama didn't answer the validation prompt with a True or False. Retrying...","red")

    # If no valid response was received after 3 tries, return False
    return False


def basic_pull(url, debug=False):
    try:
        # Send a GET request to the URL and get the text content of the response
        page_content = requests.get(url).text
        # If debug is True, print the first 250 characters of the page content
        if debug:
            print(f"basic pull =={page_content[:250]}")
        # If the page content is valid, return it; otherwise, return False
        return page_content if page_content_valid(page_content) else False
    except Exception as e:
        # If an error occurs during the request, print the error and return False
        if debug:
            print(f"\tBasic Pull - An error occurred: {e}")
        return False
    
    
def lynx_pull(url, debug=False):
    try:
        # Run the 'lynx' command with the '-source' option and the URL, and capture the output
        result = subprocess.run(['lynx', '-source', url], stdout=subprocess.PIPE)
        # Decode the output from bytes to a string
        page_content = result.stdout.decode('utf-8')
        # If debug is True, print the first 250 characters of the page content
        if debug:
            print(f"lynx pull =={page_content[:250]}")
        # If the page content is valid, return it; otherwise, return False
        return page_content if page_content_valid(page_content) else False
    except Exception as e:
        # If an error occurs during the command execution, print the error and return False
        if debug:
            print(f"\tLynx Pull - An error occurred: {e}")
        return False



async def pyppeteer_get_page_raw(url,debug=False):
    if debug:
        cprint("pyppeteer_get_page_raw","yellow")
    browser = await launch()
    try:
        # Open a new page in the browser
        page = await browser.newPage()
        # Apply stealth measures to the page to avoid being detected as a bot
        await stealth(page)
        # Return the HTML content of the page
        return await page.content()
    
    except Exception as e:
        # If an error occurs during the process, print the error and return False
        if debug:
            cprint(f"\tPyppeteer Get Page Raw - An error occurred: {e}","yellow")
        return False
    
    finally:
        if debug:
            cprint(f"\tPyppeteer Get Page Raw - Something crashed, hit the 'finally' block.","yellow")
        await browser.close()

    return False
def pyppeteer_pull(url, debug=False):
    if debug:
        cprint("pyppeteer_pull","yellow")
    try:
        # Get the HTML content of the page at the URL using the pyppeteer_get_page_raw function
        page_content = asyncio.get_event_loop().run_until_complete(pyppeteer_get_page_raw(url))
        # If debug is True, print the first 250 characters of the page content
        if debug:
            print(f"pyppeteer pull == {page_content[:250]}")
        # If the page content is valid, return it; otherwise, return False
        return page_content if page_content_valid(page_content) else False
    except Exception as e:
        # If an error occurs during the page fetching, print the error and return False
        if debug:
            print(f"Pyppeteer Pull - An error occurred: {e}")
        return False
    

def get_page_content(url, cache_age=24, debug=False): #default cache age is 24 hours, set to zero or a negative number to always get fresh data
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
    # If the file doesn't exist, continue with the methods
    #methods = [basic_pull, lynx_pull, pyppeteer_pull]
    #for method in methods:
    #    if debug:
    #        print(f"\ttrying {method.__name__.replace('_', ' ').title()} download method")        
    #    output = method(url, debug)
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
def extract_links(page_content, current_page, debug=False):
    # If debug mode is on, print the function name
    if debug:
        cprint("extract_links","yellow")
    
    # This is a regular expression (regex) that matches URLs
    url_regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"

    # Use the regex to find all URLs in the page content
    urls = re.findall(url_regex, page_content)

    # Remove the current page's URL from the list of URLs
    urls = [url for url in urls if url != current_page]

    # Return the list of URLs
    return urls


# This function cleans a list of links by removing any that have a domain that is in a list of search sites
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


# This function takes a list of words and formats it into a human-readable string
def make_list_human_readable(words, debug=False):
    # If there are more than two words, join all but the last with commas,
    # and append the last word with an 'and' before it
    if len(words) > 2:
        human_readable_list = ', '.join(words[:-1]) + ', and ' + words[-1]
    # If there are exactly two words, join them with 'and'
    elif len(words) == 2:
        human_readable_list = ' and '.join(words)
    # If there's only one word, just use that word. If there are no words, use an empty string
    else:
        human_readable_list = words[0] if words else ''

    # Remove any double quotes from the string
    human_readable_list = human_readable_list.replace('"','')
    
    # Return the human-readable string
    return human_readable_list


# This function checks if a job is relevant by asking the Ollama API
def ollama_true_or_false(prompt, retries=3, debug=False):
    if debug:
        cprint("ollama_true_or_false","yellow")

    if prompt.strip() == "" or prompt == None or prompt == False:
        if debug:
            cprint("\tPrompt is empty or None","red")
        return None
    
    # It tries up to 'retries' times
    for _ in range(retries):
        # It sends the prompt to the Ollama API and gets a response
        job_info = ollama_me(prompt)
        # If the response contains "true", it returns True and "green"
        if "true" in job_info.lower():
            return True
        # If the response contains "false", it returns False and "yellow"
        elif "false" in job_info.lower():
            return False
        # If the response contains neither "true" nor "false", it prints the first 500 characters of the response
        # and a message saying it's retrying, then continues to the next iteration of the loop
        else:
            if debug:
                print(f"Prompt: {prompt[:500]}")
                print(f"Ollama reply: {job_info[:500]}")
            if debug:
                cprint("\tRetrying, didn't get True or False...","red")
    # If it's tried 'retries' times and still hasn't gotten a clear "true" or "false", it returns None and "red"
    return None

# This function checks if any of the search words appear in the page content
def find_keywords(page_content, search_words, debug=False):
    # Initialize a flag to False. This flag will be set to True if a search word is found in the page content
    found_word = False

    # Loop through each word in the search words
    for word in search_words:
        # Remove the double quotes from the search word
        word = word.replace('"', '')
        
        # Check if the search word appears in the page content
        if word in page_content:
            # If the search word is found, and debug mode is on, print a message
            if debug:
                print(f"\tFound search word '{word}' in page content")
            
            # Set the flag to True and return it
            return True

    # If no search word is found in the page content after checking all the words, return the flag (which is False)
    return False










OPEN_AI_COST = {
    'gpt-4o':                       {'input': 5.00/1000000, 'output': 5.00/1000000},
    'gpt-4-0125-preview':           {'input': .01/1000,     'output': 0.03/1000},
    'gpt-4-1106-preview':           {'input': .01/1000,     'output': 0.03/1000},
    'gpt-4-1106-vision-preview':    {'input': .01/1000,     'output': 0.03/1000},
    'gpt-4':                        {'input': .03/1000,     'output': 0.06/1000},
    'gpt-4-32k':                    {'input': .06/1000,     'output': 0.12/1000},
    'gpt-3.5-turbo-0125':           {'input': .0005/1000,   'output': 0.0015/1000},
    'gpt-3.5-turbo-instruct':       {'input': .0015/1000,   'output': 0.0020/1000},
    'gpt-3.5-turbo-1106':           {'input': .0010/1000,   'output': 0.0020/1000},
    'gpt-3.5-turbo-0613':           {'input': .0015/1000,   'output': 0.0020/1000},
    'gpt-3.5-turbo-16k-0613':       {'input': .0030/1000,   'output': 0.0040/1000},
    'gpt-3.5-turbo-0301':           {'input': .0015/1000,   'output': 0.0020/1000},
}

def calculate_cost(prompt_tokens, completion_tokens, input_cost, output_cost):
    return (prompt_tokens * input_cost) + (completion_tokens * output_cost)

def open_ai_cost(response):
    model = response.model if not response.model.startswith('gpt-4o') else 'gpt-4o'
    model = model if model in OPEN_AI_COST else 'gpt-4-32k'

    if model == 'gpt-4-32k':
        print("Model not found, using the most expensive model")

    input_cost = OPEN_AI_COST[model]['input']
    output_cost = OPEN_AI_COST[model]['output']

    cost = calculate_cost(response.usage.prompt_tokens, response.usage.completion_tokens, input_cost, output_cost)

    return cost


def gpt_me(prompt,model,key, debug=False):
    if debug:
        cprint("gpt_me","yellow")
    client = OpenAI(
        api_key=key
    )
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
    )
    if debug:
        cprint(f"cost: {open_ai_cost(chat_completion)*100}c","yellow")
        print(f"chat_completion:\n{chat_completion}\n")
    return chat_completion.choices[0].message.content




# Disable parallelism for tokenizers to avoid potential issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Define a constant for the maximum number of tokens
MAX_TOKENS = 500

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
        # If adding the sentence to the buffer doesn't exceed the maximum number of tokens
        if len(tokenizer.encode(f"{buffer}{sentence}", truncation=False, max_length=MAX_TOKENS)) <= MAX_TOKENS:
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


# This function checks if a job is relevant by asking the Ollama API
def gpt_true_or_false(prompt, model, open_ai_key, retries=3, debug=False):
    if debug:
        cprint("gpt_true_or_false","yellow")

    if prompt.strip() == "" or prompt == None or prompt == False:
        if debug:
            cprint("\tPrompt is empty or None","red")
        return None
    
    # It tries up to 'retries' times
    for _ in range(retries):
        # It sends the prompt to the Ollama API and gets a response
        job_info = gpt_me(prompt, model, open_ai_key, debug)
        # If the response contains "true", it returns True and "green"
        if "true" in job_info.lower():
            return True
        # If the response contains "false", it returns False and "yellow"
        elif "false" in job_info.lower():
            return False
        # If the response contains neither "true" nor "false", it prints the first 500 characters of the response
        # and a message saying it's retrying, then continues to the next iteration of the loop
        else:
            if debug:
                print(f"Prompt: {prompt[:500]}")
                print(f"gpt reply: {job_info[:500]}")
            if debug:
                cprint("\tRetrying, didn't get True or False...","red")
    # If it's tried 'retries' times and still hasn't gotten a clear "true" or "false", it returns None and "red"
    return None




from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import selenium.webdriver.support.ui as ui
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from fake_useragent import UserAgent
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import urljoin


def selenium_get_raw_page(page_url, debug=False):
    if debug:
        cprint("selenium_get_raw_page","yellow")

    
    ua = UserAgent()
    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={ua.random}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    if not debug:
        chrome_options.add_argument("--headless")  # Run in headless mode
    #chrome_options.add_argument(f'--proxy-server=socks5://{proxy_picker()}')
    #chrome_options.add_argument("--proxy-server=socks5://199.102.106.94:4145")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url=page_url)
    time.sleep(5)

    for _ in range(20):
        # Add some random mouse movements
        action = ActionChains(driver)
        action.move_by_offset(random.randint(1, 10), random.randint(1, 10))
        action.perform()

        if len(get_page_body_text(driver.page_source,True,False))>=250:
            break
        time.sleep(1)

    # Convert all relative links to absolute
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    for a in soup.find_all('a', href=True):
        a['href'] = urljoin(page_url, a['href'])

    driver.quit()

    return str(soup)