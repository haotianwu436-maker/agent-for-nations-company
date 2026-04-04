from pydantic import BaseModel, Field


class KBInfo(BaseModel):
    doc_count: int = 0
    chunk_count: int = 0
    last_updated_at: str = ""


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


class AgentChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000, description="用户聊天输入")
    user_id: str = Field(default="", description="用户ID（前端可选覆盖）")
    organization_id: str = Field(default="", description="组织ID（前端可选覆盖）")
    use_llm_writing: bool = Field(default=True, description="是否启用 LLM 写作")
    need_internal_kb: bool = Field(default=False, description="是否启用内部知识库检索")
    messages: list[dict] = Field(default_factory=list, description="历史多轮消息")


class AgentChatResponse(BaseModel):
    markdown: str = ""
    citations: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    status: str
    needs_human: bool = False
    human_reason: str = ""
    grounded_score: float = 0.0
    consistency_score: float = 0.0
    has_contradiction: bool = False
    contradictions: list[dict] = Field(default_factory=list)
    repeated_content: list[dict] = Field(default_factory=list)
    consistency_suggestions: list[str] = Field(default_factory=list)
    # AIGC Detection
    aigc_score: float = 0.0
    is_aigc: bool = False
    aigc_suggestion: str = ""
    errors: list[str] = Field(default_factory=list)
    kb_info: KBInfo = Field(default_factory=KBInfo)
