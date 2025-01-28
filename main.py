from contextlib import asynccontextmanager
import logging
import os
from fastapi import BackgroundTasks, FastAPI, HTTPException

from db.api_models import (
    GetDownloadedPapersResponse,
    Paper,
    TriggerPaperDownloadRequest,
)
from paper_downloader.paper_downloader import PaperDownloader
from paper_summariser.paper_summariser import PaperSummariser
from setup_logger import setup_logger
from table_extracter.table_extracter import TableExtracter
from utils.util import get_paper_id, run_async_task

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # setup the logger
    setup_logger()

    yield


app = FastAPI(
    title="Paper Analyzer API",
    description="API for analyzing academic papers.",
    lifespan=lifespan,
)


@app.get("/trigger_all_paper_download")
async def trigger_all_paper_download(background_tasks: BackgroundTasks):
    papers: list[Paper] = []
    with open("data/pubmed_paper_links.txt", "r") as file:
        urls = [line.strip() for line in file.readlines()]
        for url in urls:
            paper_id, is_paper_id_present = get_paper_id(url)
            if is_paper_id_present:
                papers.append(Paper(paper_id=paper_id, paper_url=url))
    downloader = PaperDownloader(papers=papers)
    # Wrap the coroutine in a synchronous wrapper
    background_tasks.add_task(run_async_task, downloader.download())
    return {"message": "All Paper downloads started in the background"}


@app.post("/trigger_paper_download")
async def trigger_paper_download(
    trigger_paper_download_requests: TriggerPaperDownloadRequest,
    background_tasks: BackgroundTasks,
):
    papers: list[Paper] = []
    for paper_id in trigger_paper_download_requests.paper_ids:
        paper_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper_id}"
        papers.append(Paper(paper_id=paper_id, paper_url=paper_url))
    downloader = PaperDownloader(papers=papers)
    # Wrap the coroutine in a synchronous wrapper
    background_tasks.add_task(run_async_task, downloader.download())
    return {"message": "Paper download started in the background"}


@app.get("/get_downloaded_papers")
async def get_downloaded_papers() -> GetDownloadedPapersResponse:
    logger.info("Getting available papers")
    directory = "data/downloaded_papers"
    if not os.path.exists(directory):
        return {"paper_ids": []}

    papers: list[Paper] = []
    for filename in os.listdir(directory):
        if filename.endswith(".pdf"):
            paper_id = os.path.splitext(filename)[0]
            paper_url = f"https://pubmed.ncbi.nlm.nih.gov/{paper_id}"
            papers.append(Paper(paper_id=int(paper_id), paper_url=paper_url))

    return GetDownloadedPapersResponse(papers=papers)


@app.get("/get_paper_summary/{paper_id}")
async def get_paper_summary(paper_id: int) -> str:
    try:
        # Define the path to the summary file
        summary_path = f"data/summaries/{paper_id}.md"

        # Check if the file exists
        if os.path.exists(summary_path):
            # If the file exists, read and return its content
            with open(summary_path, "r") as file:
                return file.read()

        # If the file doesn't exist, generate the summary
        paper_summary = await PaperSummariser(paper_id=paper_id).get_summary()

        # Ensure the directory exists
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)

        # Write the paper summary to the file
        with open(summary_path, "w") as file:
            file.write(paper_summary)

        return paper_summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_primary_result_table/{paper_id}")
async def get_primary_result_table(paper_id: int):
    try:
        # Define the path to the table file
        table_path = f"data/extracted_tables/{paper_id}.csv"

        # Check if the file exists
        if os.path.exists(table_path):
            # If the file exists, return its path
            return table_path

        # If the file doesn't exist, generate the table
        table_path = await TableExtracter(paper_id=paper_id).get_primary_result_table()

        return table_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
