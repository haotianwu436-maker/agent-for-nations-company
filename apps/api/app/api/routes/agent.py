from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.agent import AgentGenerateRequest, AgentGenerateResponse
from app.services.agent_service import generate_report_via_agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/generate", response_model=AgentGenerateResponse)
def agent_generate_api(payload: AgentGenerateRequest, current_user: dict = Depends(get_current_user)):
    """
    自然语言一键生成报告（LangGraph 编排 + 内嵌原流水线）。
    同步执行，耗时取决于爬取与 LLM；生产环境建议后续改为队列异步。
    """
    out = generate_report_via_agent(
        payload.query,
        current_user["organization_id"],
        current_user["id"],
    )
    return AgentGenerateResponse(**out)
