# Job Search Automation with OpenAi

Scroop automates the job search process by scraping job listings from various websites and filtering them based on user-defined keywords. It then uses OpenAi to determine the relevance of each job to your resume. Finally it outputs a CSV file sorted by how well the job matches your resume. 

## Installation

1. Clone this repository to your local machine.
2. Install the required Python libraries by running `pip install -r requirements.txt` in your terminal.

## Configuration

1. Duplicate the `blank_config.py` file and rename it to `config.py`.
2. Generate a bulleted list style resume for yourself and pick out some search words.
3. Add the search words, resume, and api key to the `config.py` file.


## Running the Project

You can run the project by executing the main Python script in your terminal.

I'm running on Windows Subsystem for Linux 2 (WSL2) with no issues.

## Notes

You can add other search sites to `config.py`, make sure to format them like "https://example-job-site.com/?keyword=" so that the code can append a keyword on the end. If you do find more search sites, please send me a message or pull request, would love to add more!

No attempt is made to go to the next page on any of the search sites, with the idea that the code would be run once a day to get new jobs.

The search page scrape on these pages is using a regex to extract links since. There's a small amount of filtering to remove bogus links, but mostly the code errs on the side of scanning an extra link or two.

In the config there's a varyable "threads", which determines how many threads of data collection/processing will occur at one time. I generated the table below using my 8 core 16 thread AMD processor, Nvidia RTX2060, 128gb of ram, with reasonably fast internet. Your numbers will probably vary widely. The default thread count is 8, which seems like most computers would be able to handle and gets pretty far down the performance curve. I currently use 16 threads since it's almost as fast as the higher thread counts and uses far fewer resources (48 nearly maxes out my ram).

Threads | Seconds/Item | Faster Than 1 Thread
-------- | -------- | --------
1 | 6.860044713 | 
2 | 3.399884831 | ~2x
4 | 1.764798535 | ~3.9x
6 | 1.208233375 | ~5.7x
8 | 0.9485352102 | ~7.2x
12 | 0.6946216856 | ~9.9x
16 | 0.5979100998 | ~11.5x
20 | 0.5314742403 | ~12.9x
24 | 0.5160333074 | ~13.3x
32 | 0.4798605708 | ~14.3x
48 | 0.5467411784 | ~12.5x
