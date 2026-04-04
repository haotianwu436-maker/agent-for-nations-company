import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentGenerateRequest,
    AgentGenerateResponse,
)
from app.services.agent_service import (
    generate_pure_chat,
    generate_report_via_agent,
    generate_chat_stream,
    get_internal_kb_status,
    refresh_internal_kb,
)

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


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat_api(payload: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    标准聊天接口（非流式）。
    """
    payload.user_id = (payload.user_id or "").strip() or current_user["id"]
    payload.organization_id = (payload.organization_id or "").strip() or current_user["organization_id"]
    try:
        return await asyncio.wait_for(
            generate_pure_chat(request=payload),
            timeout=125,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="chat request timeout") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"chat service error: {exc}") from exc


@router.post("/chat/stream")
async def agent_chat_stream_api(payload: AgentChatRequest, current_user: dict = Depends(get_current_user)):
    """
    流式聊天接口（Server-Sent Events）。
    
    返回 SSE 流，包含以下事件类型：
    - step: 执行步骤更新
    - progress: 进度百分比
    - token: 增量文本片段
    - citations: 引用列表
    - sources: 来源列表
    - stats: 统计信息
    - done: 完成事件
    - error: 错误事件
    """
    payload.user_id = (payload.user_id or "").strip() or current_user["id"]
    payload.organization_id = (payload.organization_id or "").strip() or current_user["organization_id"]

    organization_id = payload.organization_id or "anonymous-org"
    user_id = payload.user_id or "anonymous-user"

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in generate_chat_stream(
                request=payload,
                organization_id=organization_id,
                user_id=user_id,
            ):
                yield chunk
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            yield f"event: error\ndata: {{\"code\": \"internal_error\", \"message\": \"{str(exc)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/kb/status")
async def agent_kb_status_api(current_user: dict = Depends(get_current_user)):
    _ = current_user
    return get_internal_kb_status()


@router.post("/kb/refresh")
async def agent_kb_refresh_api(current_user: dict = Depends(get_current_user)):
    _ = current_user
    try:
        return await asyncio.wait_for(refresh_internal_kb(), timeout=180)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="kb refresh timeout") from exc
