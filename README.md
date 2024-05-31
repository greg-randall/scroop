# Job Search Automation with Ollama/OpenAi

Scroop automates the job search process by scraping job listings from various websites and filtering them based on user-defined keywords. It then uses Ollama or OpenAi to determine the relevance of each job to the keywords and to your resume.

## Installation

1. Clone this repository to your local machine.
2. Install the required Python libraries by running `pip install -r requirements.txt` in your terminal.
3. Download and install [Ollama](https://ollama.com/download) or skip and use OpenAi.
4. Start the Ollama server `ollama serve` or skip and use OpenAi.
5. Run the Dolphin-llama3 model `ollama run dolphin-llama3` from the [Ollama library](https://ollama.com/library/dolphin-llama3) or skip and use OpenAi.

## Configuration

1. Duplicate the `blank_config.py` file and rename it to `config.py`.
2. Generate a bulleted list style resume for yourself and pick out some search words.
3. Add the search words and resume to the `config.py` file.

## Running the Project

You can run the project by executing the main Python script in your terminal. 

I'm running on Windows Subsystem for Linux 2 (WSL2) using an Nvidia RTX 2060. I get pretty good performance generally

## Notes

You can add other search sites to `config.py`, make sure to format them like "https://example-job-site.com/?keyword=" so that the code can append a keyword on the end. 

No attempt is made to go to the next page on any of the search sites, with the idea that the code would be run once a day to get new jobs.

Also, the scrape on these pages is very generic looking for links, and then later relying on the LLM to determine if a link is a valid job listing.
