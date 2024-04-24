Install relevant Python Libraries.

You must install Ollama (https://ollama.com/download) and then run the model dolphin-llama3 (https://ollama.com/library/dolphin-llama3).

Duplicate "blank_config.py" and rename it to "config.py". Generate a bulleted list style resume for yourself and pick out some search words.

The search sites listed all return an xml file which makes them easy to scrape as they're expecting to be downloaded by a computer. You can add other sites, make sure to format them like "https://example-job-site.com/?keyword=" so that the code can append a keyword on the end. Also, note no attempt is made to go to the next page on any of the search sites, with the idea that the code would be run once a day to get new jobs. 

I'm running Ollama on Windows Subsystem for Linux 2 (WSL2) using an Nvidia RTX 2060.