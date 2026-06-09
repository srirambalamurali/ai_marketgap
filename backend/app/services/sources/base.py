from pydantic import BaseModel, Field


class Signal(BaseModel):
    source: str
    source_id: str
    title: str
    content: str = ""
    url: str = ""
    author: str = ""
    score: int = 0
    comments_count: int = 0
