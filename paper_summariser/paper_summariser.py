import asyncio
import logging
from openai import AsyncOpenAI
import pymupdf

from config import OPENAI_APIKEY
from utils.const import MAX_CONCURRENT_PAGE_SUMMARISATION_TASK
from utils.util import schedule_task

logger = logging.getLogger(__name__)


class PaperSummariser:
    def __init__(self, paper_id: int):
        self.paper_id = paper_id
        self.paper_path = f"data/downloaded_papers/{paper_id}.pdf"

    async def get_final_summary(self, pdf_page_summaries: str) -> str:
        try:
            combined_summaries = "\n\n".join(
                f"Page {i + 1}: {summary}"
                for i, summary in enumerate(pdf_page_summaries)
            )

            # Construct the prompt
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert scientific summarizer.",
                },
                {
                    "role": "user",
                    "content": f"""
                Below are summaries of individual pages from a scientific paper. Your task is to generate a final consolidated summary 
                in a structured format with approximately 250 words. 

                The final summary must be presented in three clear sections:

                1. **Main Objectives**: Clearly outline the purpose of the study, including the goals or research questions the paper aimed to address.

                2. **Methods**: Provide a concise description of the techniques, experimental setups, or data collection approaches used in the study.

                3. **Key Findings**: Highlight the most significant results, observations, or conclusions drawn from the study.

                Ensure the final summary is cohesive, avoids redundancy, and captures the core essence of the paper.

                Here are the summaries of individual pages:
                {combined_summaries}

                Please provide the consolidated final summary in the format mentioned above:
                """,
                },
            ]

            # Call the OpenAI API
            async with AsyncOpenAI(api_key=OPENAI_APIKEY, max_retries=0) as aclient:
                response = await aclient.chat.completions.create(
                    model="gpt-4o-mini",  # Chat-based model
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7,
                )

            # Extract the consolidated summary from the response
            final_summary = response.choices[0].message.content.strip()
            return final_summary
        except Exception as e:
            raise Exception(
                f"An error occurred while generating the final summary for paper: {self.paper_id}: {e}"
            )

    async def get_pdf_page_summary(self, pdf_page_number: int, page_text: str) -> str:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert scientific summarizer.",
                },
                {
                    "role": "user",
                    "content": f"""
                You are given the content of a page from a scientific paper. Your task is to summarize the following text by identifying the key objectives, methods, and key findings. Write a concise summary (approximately 100-150 words) that includes the following:

                - The **main objectives** of the study: What is the study trying to achieve or investigate?
                - The **methods** used in the study: Briefly describe the techniques, experiments, or data collection methods used.
                - The **key findings**: What were the most important results or conclusions of the study?

                Here is the content of the page:
                {page_text}
                """,
                },
            ]

            # Use the chat completions endpoint
            async with AsyncOpenAI(api_key=OPENAI_APIKEY, max_retries=0) as aclient:
                response = await aclient.chat.completions.create(
                    model="gpt-4o-mini",  # Chat-based model
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7,
                )
                page_summary = response.choices[0].message.content
                return page_summary
        except Exception as e:
            logger.exception(
                f"An error occurred while summarizing the page number: {pdf_page_number}: {e}"
            )
            return ""

    async def get_summary(self) -> str:
        """
        1. Summarize each page of the paper into 100-200 words using GPT-4o-mini.
        2. Combine all the page summaries.
        3. Make a final LLM call to extract the main objectives, methods, and key findings.
        """

        pdf_doc = pymupdf.open(self.paper_path)
        tasks: list[asyncio.Task[str]] = list()

        semaphore = asyncio.Semaphore(value=MAX_CONCURRENT_PAGE_SUMMARISATION_TASK)
        async with asyncio.TaskGroup() as tg:
            for pdf_page_number, pdf_page in enumerate(pdf_doc):
                pdf_page_text = str(pdf_page.get_text())
                tasks.append(
                    tg.create_task(
                        schedule_task(
                            semaphore,
                            self.get_pdf_page_summary,
                            pdf_page_number + 1,
                            pdf_page_text,
                        )
                    )
                )
        pdf_page_summaries = [task.result() for task in tasks]

        return await self.get_final_summary(pdf_page_summaries)
