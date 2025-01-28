## DEMO VIDEO
https://drive.google.com/file/d/1biXg6oKDgnNDYzATa_wcstsg3Co6hG97/view?usp=sharing

## Setup Instructions

1. Clone the Repository First, clone the repository to your local machine:
```bash
git clone <repository_url>
```

2. Create a .env File In the root directory, create a .env file and copy the contents from .env.template into it. Fill in the environment variables with the appropriate values (e.g., API keys, paths, etc.).

3. Install Dependencies Open your terminal and navigate to the project directory. Then, activate the virtual environment using:
```
pipenv shell
pipenv install
```

4. Select Python Interpreter in VS Code In VS Code, ensure you select the correct Python interpreter that corresponds to the virtual environment. You can do this by opening the Command Palette (Ctrl+Shift+P), then selecting Python: Select Interpreter and choosing the one linked to your pipenv environment.

5. Run the FastAPI Server You can now run the FastAPI server directly from VS Code. A launch.json configuration is already provided for ease of execution. Press F5 or use the Run button to start the server.

## Approach

### Paper Download Task

When an API call is made for downloading a paper, the download task is added to a background process for concurrent execution. The number of concurrent download tasks can be controlled with the MAX_CONCURRENT_DOWNLOAD_TASK in const.py.

The approach works as follows:

1. A request is made to the PubMed URL.
2. The response content is parsed to find the full-text link.
3. Currently, two patterns have been identified for the full-text link: PubMed Central and Silverchair Information Systems.
4. The task can download around 161 papers using these patterns.
5. You can trigger a download for all papers with the /trigger_all_paper_download endpoint, or download a specific paper using /trigger_paper_download/{paper_id}.

### Summarization Task

For the summarization task, the endpoint /get_paper_summary/{paper_id} takes a paper_id parameter. Here's how it works:

1. The task parses through each page of the paper and summarizes it in approximately 100-150 words using the OpenAI GPT-4o-mini model.
2. The summaries from all pages are then combined to generate a final summary.
3. Summarization of pages occurs concurrently, and the number of concurrent tasks can be controlled via the MAX_CONCURRENT_PAGE_SUMMARISATION_TASK in const.py.
4. If the summary already exists, it is served from the data/summaries/{paper_id}.md file.

### Table Extraction Task

For the table extraction task, the /get_primary_result_table/{paper_id} endpoint is used:

1. The task goes through each page of the paper's PDF, converts it to an image, and passes the image to OpenAI GPT-4o to extract tables.
2. The tables extracted from each page are combined into a JSON format.
3. Function calling is leveraged with OpenAI's LLM to identify the primary result table. The model is asked to reason out the headers, rows, and columns of the CSV where the primary result table will be stored.
4. The table extraction happens concurrently for each page, and the number of concurrent tasks can be controlled via the MAX_CONCURRENT_PAGE_TABLE_EXTRACTION_TASK in const.py.
5. If the table is already available, it will be served from the data/extracted_tables/{paper_id}.csv file.