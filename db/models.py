from pydantic import BaseModel


class Paper(BaseModel):
    paper_id: int
    paper_url: str
