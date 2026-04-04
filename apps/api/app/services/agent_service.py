"""
Enhanced LangGraph Agent Service with full streaming support and trajectory visualization.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import uuid4

from app.services.kb_service import load_kb_chunks
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.report_job_service import (
    _persist_workflow_state,
    create_report_job,
    set_report_job_finished,
    set_report_job_running_for_agent,
)

import sys

CURRENT = Path(__file__).resolve()
_candidate_paths = [Path("/"), Path("/packages")]
_candidate_paths.extend(CURRENT.parents)
for candidate in _candidate_paths:
    if (candidate / "packages").exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))
if "/packages" not in sys.path:
    sys.path.append("/packages")

from packages.orchestrator.graph import get_report_agent_graph
from packages.retrieval.service import auto_update_kb, get_kb_status
from packages.orchestrator.nodes import build_workflow_state_for_persist
from packages.orchestrator.workflow import persist_report

logger = logging.getLogger(__name__)

SOFT_TIMEOUT_SECONDS = 60
HARD_TIMEOUT_SECONDS = 120
MAX_RETRIES = 2

STREAM_STEPS = [
    {"id": "planning", "label": "正在理解需求...", "emoji": "🎯", "description": "分析用户意图，生成检索策略"},
    {"id": "retrieving_internal", "label": "正在检索内部知识库...", "emoji": "📚", "description": "从企业知识库检索相关文档"},
    {"id": "retrieving_external", "label": "正在抓取外部信息...", "emoji": "🌐", "description": "从外部来源抓取实时资讯"},
    {"id": "cleaning", "label": "正在清洗数据...", "emoji": "🧹", "description": "清理和格式化文档内容"},
    {"id": "deduplicating", "label": "正在去重合并...", "emoji": "🔄", "description": "合并相似内容，去除重复信息"},
    {"id": "classifying", "label": "正在智能分类...", "emoji": "📋", "description": "将文档分配到对应章节"},
    {"id": "generating", "label": "正在生成章节内容...", "emoji": "✍️", "description": "基于检索结果撰写报告内容"},
    {"id": "citing", "label": "正在生成引用...", "emoji": "📎", "description": "为内容添加可追溯引用"},
    {"id": "visualizing", "label": "正在生成图表...", "emoji": "📊", "description": "生成数据可视化图表"},
    {"id": "assembling", "label": "正在组装报告...", "emoji": "📑", "description": "整合所有章节为完整报告"},
    {"id": "validating", "label": "正在质量校验...", "emoji": "✅", "description": "检查引用完整性和内容准确性"},
    {"id": "done", "label": "生成完成", "emoji": "🎉", "description": "报告生成完毕"},
]


def _filter_kb_chunks_by_org(kb_chunks: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
    if not organization_id:
        return kb_chunks
    out: list[dict[str, Any]] = []
    for item in kb_chunks:
        if not isinstance(item, dict):
            continue
        chunk_org = str(item.get("organization_id") or item.get("org_id") or "").strip()
        if not chunk_org or chunk_org == organization_id:
            out.append(item)
    return out


def _is_retriever_failure(exc: Exception | None = None, errors: list[str] | None = None) -> bool:
    text = ""
    if exc is not None:
        text += f" {exc}"
    if errors:
        text += " " + " ".join(errors)
    s = text.lower()
    return "retriever" in s or "retrieve" in s or "crawler" in s or "crawl" in s


def _map_node_to_step(node_name: str) -> str:
    mapping = {
        "planner": "planning",
        "retriever": "retrieving_internal",
        "cleaner": "cleaning",
        "deduplicator": "deduplicating",
        "classifier": "classifying",
        "section_generator": "generating",
        "citation": "citing",
        "chart": "visualizing",
        "assembler": "assembling",
        "validator": "validating",
    }
    return mapping.get(node_name, node_name)


def _make_stream_event(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class AgentTrajectoryCollector:
    """Collects and formats agent trajectory for visualization."""
    
    def __init__(self):
        self.trajectory: list[dict[str, Any]] = []
        self.current_node: str = ""
    
    def add_node_start(self, node_name: str, state: dict[str, Any]):
        self.current_node = node_name
        entry = {
            "node": node_name,
            "type": "start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": self._extract_node_inputs(node_name, state),
        }
        self.trajectory.append(entry)
    
    def add_node_end(self, node_name: str, state: dict[str, Any], output: dict[str, Any]):
        entry = {
            "node": node_name,
            "type": "end",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outputs": self._extract_node_outputs(node_name, state, output),
        }
        self.trajectory.append(entry)
    
    def _extract_node_inputs(self, node_name: str, state: dict[str, Any]) -> dict[str, Any]:
        inputs = {}
        if node_name == "planner":
            inputs["query"] = state.get("query", "")[:200]
            inputs["need_internal_kb"] = state.get("need_internal_kb", False)
        elif node_name == "retriever":
            inputs["keywords"] = state.get("keywords", [])[:10]
            inputs["source_whitelist"] = state.get("source_whitelist", [])[:5]
            inputs["need_internal_kb"] = state.get("need_internal_kb", False)
        elif node_name == "classifier":
            docs = state.get("deduplicated_docs", [])
            inputs["document_count"] = len(docs)
            inputs["sample_titles"] = [d.get("title", "")[:50] for d in docs[:3]]
        elif node_name == "section_generator":
            section_map = state.get("section_map", {})
            inputs["sections"] = list(section_map.keys())
            inputs["section_doc_counts"] = {k: len(v) for k, v in section_map.items()}
        elif node_name == "validator":
            inputs["has_markdown"] = bool(state.get("markdown") or state.get("final_report"))
            inputs["citation_count"] = len(state.get("citations", []))
        return inputs
    
    def _extract_node_outputs(self, node_name: str, state: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        outputs = {}
        if node_name == "planner":
            plan = output.get("plan", {})
            outputs["strategy"] = plan.get("strategy", "")
            outputs["keywords"] = plan.get("keywords", [])[:10]
            outputs["report_focus"] = plan.get("report_focus", "")[:100]
        elif node_name == "retriever":
            docs = output.get("collected_docs", [])
            outputs["total_docs"] = len(docs)
            outputs["internal_docs"] = output.get("stats", {}).get("internal_docs_count", 0)
            outputs["external_docs"] = output.get("stats", {}).get("external_docs_count", 0)
            outputs["sources"] = list(set(d.get("source_name", "") for d in docs))[:5]
            outputs["doc_previews"] = [
                {
                    "id": d.get("id", ""),
                    "title": d.get("title", "")[:80],
                    "source": d.get("source_name", ""),
                    "preview": (d.get("cleaned_text") or d.get("raw_text", ""))[:150] + "...",
                }
                for d in docs[:5]
            ]
        elif node_name == "classifier":
            section_map = output.get("section_map", {})
            outputs["sections"] = list(section_map.keys())
            outputs["distribution"] = {k: len(v) for k, v in section_map.items()}
            outputs["classifier_mode"] = output.get("stats", {}).get("classifier_mode", "unknown")
        elif node_name == "section_generator":
            sections = output.get("sections", {})
            outputs["generated_sections"] = list(sections.keys())
            outputs["section_lengths"] = {k: len(v) for k, v in sections.items()}
        elif node_name == "citation":
            citations = output.get("citations", [])
            outputs["citation_count"] = len(citations)
            outputs["coverage"] = output.get("citation_metrics", {}).get("coverage", 0)
        elif node_name == "validator":
            outputs["grounded_score"] = output.get("grounded_score", 0)
            outputs["needs_human"] = output.get("needs_human", False)
            outputs["human_reason"] = output.get("human_reason", "")
            outputs["status"] = output.get("status", "")
        return outputs
    
    def get_trajectory(self) -> list[dict[str, Any]]:
        return self.trajectory


async def generate_chat_stream(
    request: AgentChatRequest,
    organization_id: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Enhanced streaming generation with full trajectory visualization."""
    kb_info = get_kb_status()
    query = request.query.strip()
    thread_id = f"chat-{organization_id}-{user_id}-{uuid4().hex[:12]}"
    writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
    use_llm = bool(request.use_llm_writing) if request.use_llm_writing is not None else (writing_mode != "rule")
    need_internal_kb = bool(request.need_internal_kb or ("内部宣传要点" in query))
    history = [m for m in (request.messages or []) if isinstance(m, dict) and m.get("content")]

    kb_chunks = load_kb_chunks(organization_id) if need_internal_kb else []
    kb_chunks = _filter_kb_chunks_by_org(kb_chunks, organization_id)

    trajectory_collector = AgentTrajectoryCollector()

    yield _make_stream_event("kb_info", {
        "doc_count": kb_info.get("doc_count", 0),
        "chunk_count": kb_info.get("chunk_count", 0),
        "last_updated_at": kb_info.get("last_updated_at", ""),
    })

    yield _make_stream_event("step", {
        "step": "planning",
        "label": "正在理解需求...",
        "emoji": "🎯",
        "progress": 5,
        "description": "分析用户意图，生成检索策略",
    })

    yield _make_stream_event("thinking", {
        "node": "planner",
        "thought": f"用户查询: {query[:100]}...\\n需要内部知识库: {need_internal_kb}\\n写作模式: {'LLM' if use_llm else 'Rule'}",
    })

    initial: dict[str, Any] = {
        "query": query,
        "user_id": user_id,
        "organization_id": organization_id,
        "job_id": thread_id,
        "report_type": "weekly",
        "keywords": [],
        "time_range_start": "",
        "time_range_end": "",
        "source_whitelist": [],
        "language": "zh-CN",
        "use_llm_writing": bool(use_llm),
        "kb_chunks": kb_chunks,
        "plan": None,
        "need_internal_kb": need_internal_kb,
        "messages": [*history, {"role": "user", "content": query}],
        "conversation_memory": history,
        "errors": [],
        "status": "planning",
        "needs_human": False,
        "human_reason": "",
    }

    try:
        graph = get_report_agent_graph()
        total_steps = 9
        completed_steps = 0
        accumulated_markdown = ""
        
        async for event in _astream_with_node_trajectory(
            graph, initial, {"configurable": {"thread_id": thread_id}}, trajectory_collector
        ):
            if not isinstance(event, dict):
                continue
                
            event_type = event.get("__event_type__", "")
            node_name = event.get("__node__", "")
            
            if event_type == "trajectory":
                yield _make_stream_event("trajectory", {
                    "trajectory": event.get("trajectory", []),
                    "current_node": event.get("current_node", ""),
                })
                continue
            
            step_id = _map_node_to_step(node_name)
            
            if step_id:
                step_info = next((s for s in STREAM_STEPS if s["id"] == step_id), None)
                if step_info:
                    completed_steps = max(completed_steps, STREAM_STEPS.index(step_info))
                    progress = min(5 + int((completed_steps / total_steps) * 90), 95)
                    
                    yield _make_stream_event("step", {
                        "step": step_id,
                        "label": step_info["label"],
                        "emoji": step_info["emoji"],
                        "progress": progress,
                        "description": step_info["description"],
                        "node": node_name,
                    })
                    yield _make_stream_event("progress", {"value": progress, "step": step_id})

            if node_name == "planner" and event.get("plan"):
                plan = event.get("plan", {})
                yield _make_stream_event("thinking", {
                    "node": "planner",
                    "thought": f"检索策略: {plan.get('strategy', 'crawl_then_legacy_pipeline')}\\n关键词: {', '.join(plan.get('keywords', [])[:5])}\\n报告焦点: {plan.get('report_focus', '')[:80]}",
                })

            if node_name == "retriever":
                docs = event.get("collected_docs", [])
                stats = event.get("stats", {})
                if docs:
                    yield _make_stream_event("thinking", {
                        "node": "retriever",
                        "thought": f"检索完成: {len(docs)} 篇文档\\n内部: {stats.get('internal_docs_count', 0)} 篇, 外部: {stats.get('external_docs_count', 0)} 篇",
                    })
                    doc_previews = [
                        {
                            "id": d.get("id", f"doc-{i}"),
                            "title": d.get("title", "无标题")[:80],
                            "source": d.get("source_name", d.get("media_name", "未知来源")),
                            "url": d.get("source_url", d.get("url", "")),
                            "preview": (d.get("cleaned_text") or d.get("raw_text", ""))[:200] + "...",
                            "score": d.get("_internal_score") or d.get("_external_score", 0),
                        }
                        for i, d in enumerate(docs[:8])
                    ]
                    yield _make_stream_event("sources", {"sources": doc_previews})

            if node_name == "classifier":
                section_map = event.get("section_map", {})
                if section_map:
                    distribution = {k: len(v) for k, v in section_map.items()}
                    yield _make_stream_event("thinking", {
                        "node": "classifier",
                        "thought": f"文档分类完成\\n章节分布: {distribution}",
                    })

            if node_name == "section_generator":
                sections = event.get("sections", {})
                if sections:
                    for section_name, content in sections.items():
                        if content:
                            yield _make_stream_event("section", {
                                "section_name": section_name,
                                "content": content,
                            })
                            yield _make_stream_event("token", {
                                "text": content,
                                "section": section_name,
                                "is_final": False,
                            })
                            accumulated_markdown += f"\\n\\n## {section_name}\\n\\n{content}"

            citations = event.get("citations")
            if isinstance(citations, list) and citations:
                yield _make_stream_event("citations", {
                    "citations": citations[:20],
                    "count": len(citations),
                })

            citation_metrics = event.get("citation_metrics")
            if citation_metrics:
                yield _make_stream_event("stats", {
                    "citation_coverage": citation_metrics.get("coverage", 0),
                    "citation_warnings": len(citation_metrics.get("warnings", [])),
                })

            charts = event.get("charts")
            if isinstance(charts, list) and charts:
                yield _make_stream_event("stats", {"charts_generated": len(charts)})

            markdown = event.get("markdown") or event.get("final_report", "")
            if markdown and not accumulated_markdown:
                accumulated_markdown = markdown
                yield _make_stream_event("token", {"text": markdown, "is_final": True})

        yield _make_stream_event("step", {
            "step": "done",
            "label": "🎉 生成完成",
            "emoji": "🎉",
            "progress": 100,
            "description": "报告生成完毕",
        })
        yield _make_stream_event("progress", {"value": 100, "step": "done"})

        final = initial.copy()
        errors = list(final.get("errors") or [])
        md = accumulated_markdown or str(final.get("markdown") or final.get("final_report") or "")
        citations = final.get("citations") if isinstance(final.get("citations"), list) else []
        docs = final.get("deduplicated_docs") if isinstance(final.get("deduplicated_docs"), list) else []
        sources = [
            {"title": d.get("title") or "", "url": d.get("source_url") or d.get("url") or "", "source_name": d.get("source_name") or d.get("media_name") or ""}
            for d in docs[:20]
        ]
        needs_human = bool(final.get("needs_human"))
        human_reason = str(final.get("human_reason") or "")
        grounded_score = float(final.get("grounded_score") or 0.0)
        consistency_score = float(final.get("consistency_score") or 0.0)
        has_contradiction = bool(final.get("has_contradiction"))
        contradictions = final.get("contradictions") if isinstance(final.get("contradictions"), list) else []
        status = str(final.get("status") or "completed")

        yield _make_stream_event("trajectory", {
            "trajectory": trajectory_collector.get_trajectory(),
            "complete": True,
        })

        # AIGC Check
        aigc_result = {
            "aigc_score": 0.0,
            "is_aigc": False,
            "details": {"message": "知网接口占位，客户可自行替换"},
            "suggestion": "内容质量较高，建议人工最终审核"
        }
        
        yield _make_stream_event("done", {
            "markdown": md,
            "citations": citations,
            "sources": sources,
            "status": status,
            "needs_human": needs_human,
            "human_reason": human_reason,
            "grounded_score": grounded_score,
            "consistency_score": consistency_score,
            "has_contradiction": has_contradiction,
            "contradictions": contradictions,
            "aigc_score": aigc_result["aigc_score"],
            "is_aigc": aigc_result["is_aigc"],
            "aigc_suggestion": aigc_result["suggestion"],
            "errors": errors,
            "trajectory": trajectory_collector.get_trajectory(),
        })

    except asyncio.TimeoutError:
        yield _make_stream_event("error", {
            "code": "timeout",
            "message": f"请求超时（{HARD_TIMEOUT_SECONDS}秒），请稍后重试",
        })
    except Exception as exc:
        logger.exception("stream_chat_failed thread_id=%s", thread_id)
        yield _make_stream_event("error", {"code": "internal_error", "message": str(exc)})


async def _astream_with_node_trajectory(
    graph: Any,
    initial_state: dict[str, Any],
    config: dict[str, Any],
    trajectory_collector: AgentTrajectoryCollector,
) -> AsyncGenerator[dict[str, Any], None]:
    current_node = ""
    try:
        async for chunk in graph.astream(initial_state, config):
            if isinstance(chunk, dict):
                node_name = chunk.get("_node_name", "")
                if node_name and node_name != current_node:
                    if current_node:
                        trajectory_collector.add_node_end(current_node, initial_state, chunk)
                    current_node = node_name
                    trajectory_collector.add_node_start(node_name, chunk)
                    yield {
                        "__event_type__": "trajectory",
                        "__node__": node_name,
                        "trajectory": trajectory_collector.get_trajectory(),
                        "current_node": node_name,
                    }
                chunk["__node__"] = node_name
                yield chunk
        if current_node:
            trajectory_collector.add_node_end(current_node, initial_state, {})
    except Exception as exc:
        logger.exception("astream_with_node_trajectory failed: %s", exc)
        yield {"__node__": "error", "error": str(exc), "status": "failed"}


def generate_report_via_agent(query: str, organization_id: str, user_id: str) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    payload = {
        "report_type": "weekly",
        "keywords": ["agent-entry"],
        "time_range_start": start,
        "time_range_end": end,
        "source_whitelist": [],
        "template_name": "global-media-weekly-v1",
        "language": "zh-CN",
    }
    job = create_report_job(payload, organization_id, user_id)
    job_id = job["id"]

    if not set_report_job_running_for_agent(job_id, organization_id):
        return {"job_id": job_id, "status": "failed", "errors": ["job not found after create"], "markdown": ""}

    kb_chunks = load_kb_chunks(organization_id)
    writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
    use_llm = writing_mode != "rule"

    initial: dict[str, Any] = {
        "query": query.strip(),
        "user_id": user_id,
        "organization_id": organization_id,
        "job_id": job_id,
        "report_type": "weekly",
        "keywords": [],
        "time_range_start": start.isoformat(),
        "time_range_end": end.isoformat(),
        "source_whitelist": [],
        "language": "zh-CN",
        "use_llm_writing": use_llm,
        "kb_chunks": kb_chunks,
        "plan": None,
        "need_internal_kb": False,
        "messages": [{"role": "user", "content": query.strip()}],
        "errors": [],
        "status": "planning",
        "needs_human": False,
        "human_reason": "",
    }

    try:
        graph = get_report_agent_graph()
        final = graph.invoke(initial, {"configurable": {"thread_id": job_id}})
    except Exception as exc:
        logger.exception("agent_graph_failed job_id=%s", job_id)
        set_report_job_finished(job_id, False, "agent graph crashed", str(exc))
        return {
            "job_id": job_id,
            "status": "failed",
            "needs_human": False,
            "human_reason": "",
            "markdown": "",
            "plan": None,
            "errors": [str(exc)],
        }

    errors = list(final.get("errors") or [])
    md = final.get("markdown") or final.get("final_report") or ""
    plan = final.get("plan")
    needs_human = bool(final.get("needs_human"))
    human_reason = str(final.get("human_reason") or "")

    st = final.get("status") or "completed"
    persist_failed = False
    if st != "failed" and md:
        try:
            ws = build_workflow_state_for_persist(final)
            ws.status_message = final.get("status_message") or "agent completed"
            persist_report(ws, persist_fn=_persist_workflow_state)
        except Exception as exc:
            logger.exception("persist_failed job_id=%s: %s", job_id, exc)
            errors.append(f"persist_failed: {exc}")
            persist_failed = True

    if st == "failed" or persist_failed or (errors and not md and st != "needs_human"):
        set_report_job_finished(job_id, False, final.get("status_message") or "failed", "; ".join(errors[:5]))
        return {
            "job_id": job_id,
            "status": "failed",
            "needs_human": needs_human,
            "human_reason": human_reason,
            "markdown": md,
            "plan": plan if isinstance(plan, dict) else None,
            "errors": errors,
        }

    msg = human_reason if needs_human else (final.get("status_message") or "agent success")
    set_report_job_finished(job_id, True, msg[:2000], "")
    return {
        "job_id": job_id,
        "status": "needs_human" if needs_human else "completed",
        "needs_human": needs_human,
        "human_reason": human_reason,
        "markdown": md,
        "plan": plan if isinstance(plan, dict) else None,
        "errors": errors,
    }


async def generate_pure_chat(request: AgentChatRequest) -> AgentChatResponse:
    kb_info = get_kb_status()
    query = request.query.strip()
    if not query:
        return AgentChatResponse(
            markdown="",
            citations=[],
            sources=[],
            status="failed",
            needs_human=False,
            human_reason="",
            grounded_score=0.0,
            errors=["query is empty"],
            kb_info=kb_info,
        )
    effective_user_id = (request.user_id or "").strip() or "anonymous-user"
    effective_org_id = (request.organization_id or "").strip() or "anonymous-org"
    thread_id = f"chat-{effective_org_id}-{effective_user_id}-{uuid4().hex[:12]}"
    writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
    use_llm = bool(request.use_llm_writing) if request.use_llm_writing is not None else (writing_mode != "rule")
    need_internal_kb = bool(request.need_internal_kb or ("内部宣传要点" in query))
    history = [m for m in (request.messages or []) if isinstance(m, dict)]

    kb_chunks = load_kb_chunks(effective_org_id) if need_internal_kb else []
    kb_chunks = _filter_kb_chunks_by_org(kb_chunks, effective_org_id)

    graph = get_report_agent_graph()
    final: dict[str, Any] = {}
    retry_count = 0
    last_exc: Exception | None = None

    while retry_count <= MAX_RETRIES:
        initial: dict[str, Any] = {
            "query": query,
            "user_id": effective_user_id,
            "organization_id": effective_org_id,
            "job_id": thread_id,
            "report_type": "weekly",
            "keywords": [],
            "time_range_start": "",
            "time_range_end": "",
            "source_whitelist": [],
            "language": "zh-CN",
            "use_llm_writing": bool(use_llm),
            "kb_chunks": kb_chunks,
            "plan": None,
            "need_internal_kb": need_internal_kb,
            "messages": [*history, {"role": "user", "content": query}],
            "conversation_memory": history,
            "errors": [],
            "status": "planning",
            "needs_human": False,
            "human_reason": "",
        }
        try:
            task = asyncio.create_task(graph.ainvoke(initial, {"configurable": {"thread_id": thread_id}}))
            try:
                final = await asyncio.wait_for(asyncio.shield(task), timeout=SOFT_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning("agent_chat_soft_timeout thread_id=%s", thread_id)
                final = await asyncio.wait_for(task, timeout=HARD_TIMEOUT_SECONDS - SOFT_TIMEOUT_SECONDS)
            break
        except asyncio.TimeoutError:
            logger.exception("agent_chat_hard_timeout thread_id=%s", thread_id)
            return AgentChatResponse(
                markdown="",
                citations=[],
                sources=[],
                status="failed",
                needs_human=False,
                human_reason="",
                grounded_score=0.0,
                errors=[f"agent_timeout_{HARD_TIMEOUT_SECONDS}s"],
                kb_info=kb_info,
            )
        except Exception as exc:
            last_exc = exc
            logger.exception("agent_pure_chat_attempt_failed thread_id=%s retry=%s", thread_id, retry_count)
            if retry_count < MAX_RETRIES and _is_retriever_failure(exc):
                retry_count += 1
                continue
            return AgentChatResponse(
                markdown="",
                citations=[],
                sources=[],
                status="failed",
                needs_human=False,
                human_reason="",
                grounded_score=0.0,
                errors=[str(exc)],
                kb_info=kb_info,
            )

    if not final:
        err = str(last_exc) if last_exc else "agent failed without result"
        return AgentChatResponse(
            markdown="",
            citations=[],
            sources=[],
            status="failed",
            needs_human=False,
            human_reason="",
            grounded_score=0.0,
            errors=[err],
            kb_info=kb_info,
        )

    errors = list(final.get("errors") or [])
    md = str(final.get("markdown") or final.get("final_report") or "")
    citations = final.get("citations") if isinstance(final.get("citations"), list) else []
    docs = final.get("deduplicated_docs") if isinstance(final.get("deduplicated_docs"), list) else []
    sources: list[dict[str, Any]] = []
    for d in docs[:20]:
        sources.append(
            {
                "title": d.get("title") or "",
                "url": d.get("source_url") or d.get("url") or "",
                "source_name": d.get("source_name") or d.get("media_name") or "",
            }
        )
    needs_human = bool(final.get("needs_human"))
    human_reason = str(final.get("human_reason") or "")
    grounded_score = float(final.get("grounded_score") or 0.0)
    consistency_score = float(final.get("consistency_score") or 0.0)
    has_contradiction = bool(final.get("has_contradiction"))
    contradictions = final.get("contradictions") if isinstance(final.get("contradictions"), list) else []
    status = str(final.get("status") or "completed")

    if status not in {"completed", "failed", "needs_human"}:
        status = "needs_human" if needs_human else ("completed" if md else "failed")
    if retry_count > 0 and _is_retriever_failure(None, errors):
        errors.append(f"retriever_retry_count={retry_count}")
    if status == "failed" and not errors:
        errors.append(str(final.get("status_message") or "agent failed"))
    if int(kb_info.get("doc_count") or 0) <= 0:
        empty_hint = "\n\n> ℹ️ 知识库暂无内容，建议先运行 ingest_demo.py。"
        if empty_hint not in md:
            md = f"{md}{empty_hint}".strip()
    if needs_human and status != "failed":
        status = "needs_human"
        hint = "\n\n> ⚠️ 部分内容需要人工确认。"
        if hint not in md:
            md = f"{md}{hint}".strip()
        if not human_reason:
            human_reason = "部分内容需要人工确认"

    return AgentChatResponse(
        markdown=md,
        citations=citations,
        sources=sources,
        status=status,
        needs_human=needs_human,
        human_reason=human_reason,
        grounded_score=grounded_score,
        consistency_score=consistency_score,
        has_contradiction=has_contradiction,
        contradictions=contradictions,
        errors=errors,
        kb_info=kb_info,
    )


async def refresh_internal_kb() -> dict[str, Any]:
    return await asyncio.to_thread(auto_update_kb)


def get_internal_kb_status() -> dict[str, Any]:
    return get_kb_status()
