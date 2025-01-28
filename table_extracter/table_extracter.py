import asyncio
import base64
import csv
import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI
import pymupdf

from config import OPENAI_APIKEY
from utils.const import MAX_CONCURRENT_PAGE_TABLE_EXTRACTION_TASK
from utils.util import schedule_task

logger = logging.getLogger(__name__)


class TableExtracter:
    def __init__(self, paper_id: int):
        self.paper_id = paper_id
        self.paper_path = f"data/downloaded_papers/{paper_id}.pdf"

    async def get_tables_from_pdf_page(
        self, pdf_page_number: int, pdf_page_pix_map: pymupdf.Pixmap
    ) -> Optional[str]:
        """
        Extract tables from the image of a PDF page using OpenAI GPT-4o in JSON.
        """
        try:
            async with AsyncOpenAI(api_key=OPENAI_APIKEY, max_retries=0) as aclient:
                pdf_page_image_path = (
                    f"data/temp/pdf_page_{self.paper_id}_{pdf_page_number}.png"
                )
                # Ensure the directory exists
                os.makedirs(os.path.dirname(pdf_page_image_path), exist_ok=True)
                pdf_page_pix_map.save(pdf_page_image_path)

                # Read the image and encode it in base64
                with open(pdf_page_image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode("utf-8")

                # Define the enhanced prompt for table extraction
                prompt_text = (
                    "Analyze the image provided and extract all tables, presenting the results in **JSON format**. "
                    "Each table should include its headers, rows, and any associated metadata (e.g., table captions or titles if visible). "
                    "Ensure the JSON is well-structured and clearly differentiates between headers and data rows. "
                    "If no tables are found, respond with exactly: 'No tables found in this image.' Avoid providing any additional information or commentary."
                )

                # Make the request to the chat model
                response = await aclient.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt_text,
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                )

                os.remove(pdf_page_image_path)

                # Parse the response and handle cases with or without tables
                extracted_content = response.choices[0].message.content.strip()
                if extracted_content == "No tables found in this image.":
                    logger.exception(
                        f"No tables found in page number {pdf_page_number} of paer id {self.paper_id}"
                    )
                    return None
                else:
                    return extracted_content
        except Exception as e:
            os.remove(pdf_page_image_path)
            logger.exception(
                f"An error occurred while extracting tables from page number {pdf_page_number} of paper id {self.paper_id}: {e}"
            )
            return None

    async def get_primary_result_table_helper(
        self, pdf_page_tables: list[str]
    ) -> Optional[str]:
        """
        Processes a list of tables, identifies the main result table, and exports it to a CSV file.
        """
        try:
            # Prompt text to identify main result table
            prompt_text = (
                "From the following list of tables, choose the main result table. "
                "Provide the table columns and rows in a structured format suitable for CSV export. "
                "Tables:\n" + "\n".join(pdf_page_tables)
            )

            # Define the function for creating a CSV
            functions = [
                {
                    "type": "function",
                    "function": {
                        "name": "create_result_table_csv",
                        "description": "Create a CSV file from the main result table",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "columns": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of column names",
                                },
                                "rows": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "description": "2D array of row data",
                                },
                            },
                            "required": ["columns", "rows"],
                        },
                    },
                }
            ]

            # Make the OpenAI request
            async with AsyncOpenAI(api_key=OPENAI_APIKEY, max_retries=0) as aclient:
                response = await aclient.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_text}],
                    tools=functions,
                )

            if response.choices[0].message.tool_calls:
                # Parse the arguments
                args = json.loads(
                    response.choices[0].message.tool_calls[0].function.arguments
                )

                csv_save_path = f"data/extracted_tables/{self.paper_id}.csv"

                columns = args.get("columns", [])
                rows = args.get("rows", [])

                os.makedirs(os.path.dirname(csv_save_path), exist_ok=True)

                # Write to CSV
                with open(csv_save_path, "w", newline="") as csvfile:
                    csvwriter = csv.writer(csvfile)
                    csvwriter.writerow(columns)
                    csvwriter.writerows(rows)

                return csv_save_path

        except Exception as e:
            logger.exception(f"An error occurred while processing tables: {e}")
            return None

    async def get_primary_result_table(self):
        """
        1. Iterate through all pages of the PDF document.
        2. Convert each page into an image.
        3. Use OpenAI GPT-4o to extract tables from the image of each page in JSON format.
        4. Concatenate all the extracted tables.
        5. Create an OpenAI function call that processes the concatenated tables using a tool LLM.
        6. The LLM will return the columns and rows of the primary result table.
        7. Save the primary result table as a CSV file.
        """
        pdf_doc = pymupdf.open(self.paper_path)
        tasks: list[asyncio.Task[str]] = list()

        semaphore = asyncio.Semaphore(value=MAX_CONCURRENT_PAGE_TABLE_EXTRACTION_TASK)
        async with asyncio.TaskGroup() as tg:
            for pdf_page_number, pdf_page in enumerate(pdf_doc):
                pdf_page_pix_map: pymupdf.Pixmap = pdf_page.get_pixmap()
                tasks.append(
                    tg.create_task(
                        schedule_task(
                            semaphore,
                            self.get_tables_from_pdf_page,
                            pdf_page_number + 1,
                            pdf_page_pix_map,
                        )
                    )
                )

        pdf_page_tables = [task.result() for task in tasks if task.result() is not None]

        if not pdf_page_tables or len(pdf_page_tables) == 0:
            raise Exception(
                f"No tables found in the PDF document with paper id {self.paper_id}"
            )

        pdf_result_table_path = await self.get_primary_result_table_helper(
            pdf_page_tables
        )

        if not pdf_result_table_path:
            raise Exception(
                f"Failed to extract the primary result table from the PDF document with paper id {self.paper_id}"
            )

        return pdf_result_table_path
