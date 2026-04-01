from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateReportJobRequest(BaseModel):
    report_type: Literal["weekly", "monthly"]
    keywords: list[str] = Field(default_factory=list)
    time_range_start: datetime
    time_range_end: datetime
    source_whitelist: list[str] = Field(default_factory=list)
    template_name: str
    language: str = "zh-CN"


class ReportJobResponse(BaseModel):
    id: str
    status: str
    report_type: str
    created_at: datetime | None = None
