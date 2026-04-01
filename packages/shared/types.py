from typing import Literal, TypedDict


JobStatus = Literal["pending", "running", "success", "failed"]


class SourceItem(TypedDict, total=False):
    source_url: str
    title: str
    body: str
    published_at: str
    media_name: str
