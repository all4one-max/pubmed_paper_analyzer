import asyncio
import logging
import os
import backoff
from bs4 import BeautifulSoup
from fastapi import status
import httpx

from db.models import Paper
from utils.const import MAX_CONCURRENT_DOWNLOAD_TASK
from utils.exception import TooManyRequestsException
from utils.util import get_paper_id, schedule_task

logger = logging.getLogger(__name__)


class PaperDownloader:
    def __init__(self, papers: list[Paper]):
        self.papers = papers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }

    @classmethod
    def get_full_text_pdf_link(cls, html_text: str) -> str:
        soup = BeautifulSoup(html_text, "html.parser")

        # List of possible title names to check for anchor tags
        title_names = [
            "See full text options at Silverchair Information Systems",
            "Free full text at PubMed Central",
            # Add any other title names you have identified
        ]

        # Try to find the link with any of the title names
        for title in title_names:
            link = soup.find("a", title=title)
            if link:
                return link["href"]

        # If no valid link is found, raise an exception
        raise Exception("This link type is not handled or not found.")

    @classmethod
    def get_pdf_url(cls, html_text: str) -> str:
        soup = BeautifulSoup(html_text, "html.parser")
        pdf_url = soup.find("meta", attrs={"name": "citation_pdf_url"})["content"]
        if not pdf_url:
            raise Exception("PDF URL not found in the page.")
        return pdf_url

    async def fetch_pdf_download_link(self, client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url, follow_redirects=True, headers=self.headers)
        if response.status_code != status.HTTP_200_OK:
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                raise TooManyRequestsException()
            raise Exception(
                f"Failed to fetch the page url: {url}, {response.status_code}"
            )

        full_text_pdf_link = PaperDownloader.get_full_text_pdf_link(response.text)

        response = await client.get(
            url=full_text_pdf_link,
            follow_redirects=True,
            headers=self.headers,
        )
        if response.status_code != status.HTTP_200_OK:
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                raise TooManyRequestsException()
            raise Exception(
                f"Failed to fetch the full text page: {full_text_pdf_link}, {response.status_code}"
            )

        pdf_url = PaperDownloader.get_pdf_url(response.text)
        return pdf_url

    @backoff.on_exception(
        backoff.expo,  # Exponential backoff
        TooManyRequestsException,  # Retry on TooManyRequestsException
        max_tries=5,  # Retry up to 5 times
        on_giveup=lambda details: logger.error(
            f"retry give up after 5 retries: {details['exception']}"
        ),  # Log error after 5 retries
    )
    async def download_helper(
        self, client: httpx.AsyncClient, paper_url: str, save_path: str
    ) -> None:
        try:
            download_link = await self.fetch_pdf_download_link(client, paper_url)

            response = await client.get(
                url=download_link, follow_redirects=True, headers=self.headers
            )
            if response.status_code != status.HTTP_200_OK:
                if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    raise TooManyRequestsException()
                raise Exception(
                    f"Failed to download the PDF from: {download_link}, {response.status_code}"
                )

            # Ensure the directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Write the PDF content to a file
            with open(save_path, "wb") as pdf_file:
                pdf_file.write(response.content)
        except Exception as e:
            logger.error(
                f"An error occurred while downloading the paper from {paper_url}: {e}"
            )

    async def download(self):
        async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
            # could not leverage concurrent calls here as i was getting 429 error code, therefore MAX_CONCURRENT_DOWNLOAD_TASK value is 1
            semaphore = asyncio.Semaphore(value=MAX_CONCURRENT_DOWNLOAD_TASK)
            tasks: dict[str, asyncio.Task[str]] = dict()
            async with asyncio.TaskGroup() as tg:
                for paper in self.papers:
                    save_path = f"data/downloaded_papers/{paper.paper_id}.pdf"
                    if not os.path.exists(save_path):
                        tasks[save_path] = tg.create_task(
                            schedule_task(
                                semaphore,
                                self.download_helper,
                                client,
                                paper.paper_url,
                                save_path,
                            )
                        )
