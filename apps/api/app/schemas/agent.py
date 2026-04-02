from pydantic import BaseModel, Field


class AgentGenerateRequest(BaseModel):
    query: str = Field(..., min_length=4, max_length=4000, description="自然语言需求，例如周报主题")


class AgentGenerateResponse(BaseModel):
    job_id: str
    status: str
    needs_human: bool = False
    human_reason: str = ""
    markdown: str = ""
    plan: dict | None = None
    errors: list[str] = Field(default_factory=list)
