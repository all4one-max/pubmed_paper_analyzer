from pydantic import BaseModel

from db.models import Paper


class GetDownloadedPapersResponse(BaseModel):
    papers: list[Paper] = []


class TriggerPaperDownloadRequest(BaseModel):
    paper_ids: list[int] = []
