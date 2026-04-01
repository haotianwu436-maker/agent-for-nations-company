from pydantic import BaseModel, Field


class UploadKnowledgeRequest(BaseModel):
    title: str
    content: str = Field(min_length=50)
    source_name: str = ""


class SearchKnowledgeResponse(BaseModel):
    chunk_text: str
    score: float
    source_name: str
    title: str
