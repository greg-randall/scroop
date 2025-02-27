
# Standard library imports
import hashlib
import os
import random
import re
import time
from urllib.parse import urlparse, quote, unquote, urljoin, urlunparse


# Related third party imports
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from termcolor import cprint
from trafilatura import extract
from webdriver_manager.chrome import ChromeDriverManager


from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re



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


def get_page_content(driver, url, cache_age=72, debug=False):
    
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
    output = selenium_get_raw_page(driver, url, debug)

    #print("we are sleeping the long sleeps seconds since this is a first run it'll get lots and lots of links")
    #time.sleep(60)

    # If the output is not None or empty, save it to a file and return it
    if output:
        with open(filepath, 'w') as file:
            file.write(str(output))
        if debug:
            print(f"writing out data for future cache {filepath}")
        return output

    # If the output is None or empty, return False
    return False



def extract_links(page_content: str, debug: bool = False) -> list:

    # Parse the HTML content with Beautiful Soup
    soup = BeautifulSoup(page_content, 'html.parser')

    # Use a list comprehension to extract all href attributes from 'a' tags
    # The 'if href' condition filters out any 'None' values
    urls = [a_tag.get('href') for a_tag in soup.find_all('a') if (href := a_tag.get('href'))]

    # Print the number of links found if debug mode is on
    if debug:
        print(f"Found {len(urls)} href links")

    # Unescape HTML entities
    page_content = re.sub('&amp;', '&', page_content)

    # Remove linebreaks and existing tildes
    page_content = re.sub('\n|~', ' ', page_content)

    # Add a newline and a tilde before each opening link tag and a newline after each closing link tag
    page_content = re.sub('<link>', '\n~<link>', page_content)
    page_content = re.sub('</link>', '</link>\n', page_content)

    # Remove all the HTML tags
    soup = BeautifulSoup(page_content, 'html.parser')
    page_content = soup.get_text()

    # Remove leading whitespace, lines that don't start with a tilde, lines that are only a single character, and extra newlines
    page_content = re.sub('^\s+|^[^~].+|^.$|\n+', '', page_content)

    # Remove the tildes
    page_content = re.sub('~', '', page_content)

    # Split the page content into lines and strip any whitespace
    lines = [line.strip() for line in page_content.split('\n')]

    # Use a list comprehension to parse each line as a URL and add it to the list if it's a valid URL
    urls += [line for line in lines if urlparse(line).scheme and urlparse(line).netloc]

    # Print the number of link tags found if debug mode is on
    if debug:
        print(f"Found {len(urls) - len(lines)} link tags")

    # Return the list of URLs
    return urls




def link_cleaner(links, search_sites, debug=False):
    if debug:
        print("link_cleaner")

    extensions = ['js', 'jpg', 'jpeg', 'png', 'gif', 'html', 'css', 'svg', 'pdf', 'mp4', 'mp3', 'json', 'xml', 'ico', 'webp' ]

    # Extract the domain from each search site using the urlparse function
    search_domains = {urlparse(site).netloc for site in search_sites}

    # Initialize an empty list to store the clean links
    clean_links = []

    # Loop over each link in the list of links
    for url in links:

        url = url.strip()

        url = url.replace('http://', 'https://')

        # The link is a tuple, and the actual URL is the first element
        #url = link[0]

        # Skip links that contain 'keywords='
        if 'keywords=' in url.lower() or 'academiccareers.com/ajax' in url.lower():
            continue

        # Skip links that end with one of the extensions
        skip_link = False
        for ext in extensions:
            if url.endswith('.' + ext):
                skip_link = True
                break
        if skip_link:
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


def find_keywords(page_content, search_words, must_have_words, anti_kewords, debug=False):
    # Convert the page content to lowercase once, to avoid doing it for each word
    page_content = page_content.lower()

    removal_words = [] # maybe words like "facebook"

    # Remove the removal words from the page content.
    # In case there are collsions between parts of the searchwords, ie searching for "book" but the page contains "facebook"
    for word in removal_words:
        page_content = page_content.replace(word.lower(), "")


    keyword_found_match = False
    # Loop through each word in the search words
    for word in search_words:
        # Remove the double quotes from the search word and convert it to lowercase
        word = word.replace('"', '').lower()

        # Check if the search word appears in the page content
        if word in page_content:
            # If the search word is found, and debug mode is on, print a message
            if debug:
                print(f"\tFound search word '{word}' in page content")
            keyword_found_match = True
            break

    # Check if there are any must-have words
    if len(must_have_words) > 0:
        if debug:
            print(f"Must have words: {must_have_words}")
        # Initialize a counter for the must-have words found in the page content
        must_have_words_match = 0
        # Loop through each word in the must-have words
        for word in must_have_words:
            # Check if the must-have word appears in the page content
            if word in page_content:
                # If the must-have word is found, increment the counter
                must_have_words_match += 1
        if debug:
            print(f"Must have words match: {must_have_words_match} of {len(must_have_words)}")
        # If not all must-have words are found in the page content, return False
        if must_have_words_match < len(must_have_words):
            return False
        # If all must-have words are found and the keyword is found, return True
        elif must_have_words_match == len(must_have_words) and keyword_found_match == True:
            return True
        
    #if we find any anti-words, we should return false
    if len(anti_kewords):
        for word in anti_kewords:
            if word in page_content:
                return False

    # If there are no must-have words, return True if the keyword is found, False otherwise
    return keyword_found_match


def gpt_me(prompt, model, key, debug=False):
    # If debug mode is on, print the function name
    if debug:
        cprint("gpt_me", "yellow")

    try:
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
    except Exception as e:
        # If an error occurs, print the error and return an empty string
        print(f"A ChatGPT error occurred: {e}\n\t{prompt}\n\n\n\n")
        return False

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


def initialize_selenium_browser(debug=False):
    # Create a UserAgent object
    ua = UserAgent()

    # List of possible screen sizes
    screen_sizes = ["1024x768", "1280x800", "1366x768", "1440x900", "1920x1080", "3840x2160"]
    # Choose a random screen size from the list
    screen_size = random.choice(screen_sizes)

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={ua.random}")  # Set the user agent to a random one
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disable automation detection
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Disable automation detection
    chrome_options.add_argument(f"--window-size={screen_size}")

    # Set page load strategy to 'none' to make navigation faster
    chrome_options.page_load_strategy = 'none'

    if not debug:
        chrome_options.add_argument("--headless")  # Run in headless mode if not in debug mode

    # Create a WebDriver object
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    return driver

def selenium_get_raw_page(driver, page_url, debug=False):
    # If debug mode is on, print a message
    if debug:
        print("selenium_get_raw_page")
        time_to_get_page = time.time()

    try:
        # Navigate to the page
        driver.get(url=page_url)

        # Wait for the page to load
        time.sleep(5)

 
        for _ in range(5):
            if debug:
                print("scrolling down")
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

        # Return the page source
        if debug:
            cprint(f"Time to get page: {round(time.time()-time_to_get_page)} seconds\n\n","yellow")
        return str(soup)
    except Exception as e:
        # If an error occurs, print the error and return False
        print(f"selenium_get_raw_page - An error occurred: {e}\n\t{page_url}")
        if debug:
            cprint(f"Time to fail to get page: {round(time.time()-time_to_get_page)} seconds\n\n","yellow")
        return False

def get_search_links(urls, search_sites, debug=False):
    # Initialize an empty list to store all the links
    all_links = []

    driver = initialize_selenium_browser(debug)

    for url in urls:
        if debug:
            cprint("get_search_links","yellow")
            print(f"\t{url}")

        # Fetch the page content
        if debug:
            print(f"Fetching page content")

        if debug:
            page_content = get_page_content(driver, url, 0, False)  # for debug disable cache
        else:
            page_content = get_page_content(driver, url, 2, False)  # 2 hours
        
        if debug:
            print(f"Got page content")
            print(f"Type of 'page_content': {type(page_content)}")
            if isinstance(page_content, str):
                print(f"Length of 'page_content': {len(page_content)}")

        # If the page content was successfully fetched
        if page_content:
            # Extract the links from the page content
            if debug:
                print(f"Extracting links")
            fresh_links = extract_links(page_content)
            if debug:
                print(f"Extracted {len(fresh_links)} links")

            # Clean the extracted links by making sure they contain the search site URL and removing duplicates
            fresh_links = link_cleaner(fresh_links, search_sites)
            if debug:
                print(f"Cleaned {len(fresh_links)} links")

            # Add the cleaned links to the all_links list
            all_links.extend(fresh_links)

    # Close the browser
    driver.quit()

    # Return the list of all links
    return all_links


def process_links(links, search_words, must_have_words, anti_kewords):

    return_count = 0

    # Initialize the Selenium browser
    driver = initialize_selenium_browser()

    for link in links:
        # Fetch the page content and cache it for 30 days (720 hours = 30 days)
        page_content_raw = get_page_content(driver, link, 720)

        # Extract the body text from the page content
        page_content = get_page_body_text(page_content_raw)

        # If there is body text
        if page_content:
            # Check if any of the search words are in the body text
            found_word = find_keywords(page_content, search_words, must_have_words, anti_kewords)

            # If a search word was not found
            if not found_word:
                # Log the link
                with open("scanned_sites.log", 'a') as file:
                    file.write(f"{link}\n")

                return_count += 1

    # Quit the driver after processing all links
    driver.quit()

    return return_count

def generate_gpt_summary(link, open_ai_key, debug=False):
    # Fetch the page content and cache it for 30 days (720 hours = 30 days)
    driver = initialize_selenium_browser()
    try:
        page_content_raw = get_page_content(driver, link, 720, debug)

        # Extract the body text from the page content
        page_content = get_page_body_text(page_content_raw, False, debug)

        if page_content == False:
            print(f"page content is false for {link}")
            # Create a placeholder summary to avoid errors in the job match phase
            filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
            filepath = os.path.join('cached_pages', filename)
            with open(filepath, 'w') as file:
                file.write("No content could be extracted from this page.")
                
            # Create a placeholder rating to avoid errors in the results phase
            rating_filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
            rating_filepath = os.path.join('cached_pages', rating_filename)
            with open(rating_filepath, 'w') as file:
                file.write("1")  # Low rating for pages with no content
                
            return "No content could be extracted from this page."

        # If there is page content and it's at least 50 characters long
        if page_content and len(page_content) >= 50:
            # Generate the filename for the summary file
            filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
            filepath = os.path.join('cached_pages', filename)

            # If the summary file doesn't exist
            if not os.path.exists(filepath):
                # Generate a summary of the page content using the GPT model
                prompt = f"Please read this job listing and write a concise summary of required skills, degrees, etc:\n\n{page_content}"
                job_summary = gpt_me(prompt, "gpt-4o-mini", open_ai_key, debug)

                if job_summary == False:
                    print(f"Error: job summary is false for {link}")
                    # Create a placeholder summary
                    job_summary = "Failed to generate summary for this job listing."
                
                # Save the summary to the file
                with open(filepath, 'w') as file:
                    file.write(job_summary)
            else:
                # If the summary file exists, read the summary from the file
                with open(filepath, 'r') as file:
                    job_summary = file.read()

            # Return the summary
            return job_summary
        else:
            # If content is too short, create placeholder files
            filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
            filepath = os.path.join('cached_pages', filename)
            with open(filepath, 'w') as file:
                file.write("Content too short to generate a meaningful summary.")
                
            # Create a placeholder rating
            rating_filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
            rating_filepath = os.path.join('cached_pages', rating_filename)
            with open(rating_filepath, 'w') as file:
                file.write("1")  # Low rating for pages with short content
                
            return "Content too short to generate a meaningful summary."
    finally:
        # Always close the driver
        driver.quit()


def generate_gpt_job_match(link, bullet_resume, open_ai_key, debug=False):
    if debug:
        cprint("generate_gpt_job_match","yellow")

    filename = f"{hashlib.md5(link.encode()).hexdigest()}_summary.txt"
    filepath = os.path.join('cached_pages', filename)

    # Check if summary file exists
    if not os.path.exists(filepath):
        # Create a placeholder summary and rating
        with open(filepath, 'w') as file:
            file.write("No summary available for this job.")
        
        rating_filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
        rating_filepath = os.path.join('cached_pages', rating_filename)
        with open(rating_filepath, 'w') as file:
            file.write("1")  # Default low rating
        
        return 1
    
    # Read the job summary
    with open(filepath, 'r') as file:
        job_summary = file.read()
    
    # Check if job summary has enough content
    if len(job_summary) >= 25:
        rating_filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
        rating_filepath = os.path.join('cached_pages', rating_filename)

        if not os.path.exists(rating_filepath):
            try:
                # Use the LLM to generate a job match rating
                prompt = f"Read the applicant's RESUME and JOB SUMMARY below and determine if the applicant is a good fit for this job on a scale of 1 to 10. 1 is a bad fit, 10 is a perfect fit. REPLY WITH AN INTEGER 1-10!!!\n\nRESUME:  {bullet_resume}\n\nJOB SUMMARY:  {job_summary}"
                job_is_a_good_match = gpt_range(prompt, "gpt-4o-mini", open_ai_key, debug)
                
                # Handle case where gpt_range returns None
                if job_is_a_good_match is None:
                    job_is_a_good_match = 1  # Default low rating
                
                # Write the rating to file
                with open(rating_filepath, 'w') as file:
                    file.write(str(job_is_a_good_match))
            except Exception as e:
                # If there's an error, create a default rating
                print(f"Error generating job match: {e}")
                job_is_a_good_match = 1
                with open(rating_filepath, 'w') as file:
                    file.write(str(job_is_a_good_match))
        else:
            # Read existing rating
            with open(rating_filepath, 'r') as file:
                job_is_a_good_match = file.read().strip()
                try:
                    job_is_a_good_match = int(job_is_a_good_match)
                except ValueError:
                    # If rating can't be converted to int, use default
                    job_is_a_good_match = 1
                    with open(rating_filepath, 'w') as file:
                        file.write(str(job_is_a_good_match))

        return job_is_a_good_match
    else:
        # If summary is too short, create a default rating
        rating_filename = f"{hashlib.md5(link.encode()).hexdigest()}_rating.txt"
        rating_filepath = os.path.join('cached_pages', rating_filename)
        with open(rating_filepath, 'w') as file:
            file.write("1")  # Default low rating
        
        return 1


def split_list(input_list, size):
    # Calculate the length of the input list
    length = len(input_list)

    # Calculate the base size and the number of lists that will get an extra item
    base_size = length // size
    remainder = length % size

    # Initialize the output list
    output = []

    # Initialize the iterator over the input list
    iterator = iter(input_list)

    # Create the lists
    for i in range(size):
        # Determine the size of the current list
        current_size = base_size + (i < remainder)
        
        # Create the current list
        current_list = [next(iterator) for _ in range(current_size)]
        
        # Add the current list to the output
        output.append(current_list)

    # Return the output
    return output
