"""
LangGraph 节点：Planner + 复用 legacy execute_workflow + 轻量校验。
后续 Phase 可将 monolithic pipeline 拆成 retriever / cleaner / section_generator 等独立节点。
"""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable

from packages.orchestrator.prompts import MEDIA_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT
from packages.orchestrator.state import ReportState
from packages.orchestrator.workflow import (
    WorkflowState,
    execute_workflow,
    plan_sources,
    crawl_sources,
    clean_documents,
    deduplicate_documents,
    classify_documents,
    generate_sections,
    generate_citations,
    generate_charts,
    assemble_report,
)

logger = logging.getLogger(__name__)

PersistFn = Callable[[WorkflowState], None]

persist_fn_var: ContextVar[PersistFn | None] = ContextVar("report_agent_persist_fn", default=None)


@contextmanager
def with_persist_fn(fn: PersistFn | None):
    token = persist_fn_var.set(fn)
    try:
        yield
    finally:
        persist_fn_var.reset(token)


def _call_llm_json(user_prompt: str) -> dict[str, Any] | None:
    model_name = os.getenv("LITELLM_MODEL", "").strip()
    api_key = os.getenv("LITELLM_API_KEY", "").strip()
    if not model_name or not api_key or api_key == "replace_me":
        return None
    try:
        from litellm import completion  # type: ignore

        resp = completion(
            model=model_name,
            api_key=api_key,
            base_url=os.getenv("LITELLM_BASE_URL") or None,
            messages=[
                {"role": "system", "content": f"{MEDIA_SYSTEM_PROMPT}\n{PLANNER_SYSTEM_PROMPT}"},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
            timeout=45,
        )
        raw = (resp.choices[0].message.content or "").strip()  # type: ignore[index]
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("planner_llm_failed: %s", exc)
        return None


def _heuristic_keywords(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return ["AI", "媒体", "AIGC"]
    parts = re.split(r"[,，、;；\s]+", q)
    kws = [p.strip() for p in parts if len(p.strip()) >= 2][:12]
    if len(kws) < 3:
        kws.extend(["人工智能", "传媒", "技术趋势"])
    return list(dict.fromkeys(kws))[:12]


def _default_sources() -> list[str]:
    raw = os.getenv("AGENT_DEFAULT_SOURCES", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data if x]
        except json.JSONDecodeError:
            pass
    return [
        "https://arstechnica.com/",
        "https://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy",
    ]


def planner_node(state: ReportState) -> dict[str, Any]:
    """根据 query 生成 plan，并写回 keywords / whitelist（后续可接结构化输出）。"""
    query = state.get("query") or ""
    plan: dict[str, Any] = {
        "strategy": "crawl_then_legacy_pipeline",
        "keywords": _heuristic_keywords(query),
        "report_focus": query[:200] or "媒体行业 AI 动态",
        "need_kb": True,
    }
    llm_plan = _call_llm_json(f"用户需求：\n{query}\n请输出规划 JSON。")
    if llm_plan and isinstance(llm_plan, dict):
        if isinstance(llm_plan.get("keywords"), list):
            merged = [str(x) for x in llm_plan["keywords"] if str(x).strip()]
            if merged:
                plan["keywords"] = merged[:12]
        if llm_plan.get("report_focus"):
            plan["report_focus"] = str(llm_plan["report_focus"])[:500]
        ps = llm_plan.get("prefer_sources")
        if isinstance(ps, list) and ps:
            plan["prefer_sources"] = [str(x) for x in ps if str(x).strip().startswith("http")]
        else:
            plan["prefer_sources"] = []
    else:
        plan["prefer_sources"] = []

    keywords = plan["keywords"]
    whitelist = state.get("source_whitelist") or []
    if plan.get("prefer_sources"):
        whitelist = list(dict.fromkeys([*plan["prefer_sources"], *whitelist]))
    if not whitelist:
        whitelist = _default_sources()

    return {
        "plan": plan,
        "keywords": keywords,
        "source_whitelist": whitelist,
        "status": "running",
        "status_message": "planner_done",
    }


def _to_workflow(state: ReportState) -> WorkflowState:
    writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
    use_llm = state.get("use_llm_writing")
    if use_llm is None:
        use_llm = writing_mode != "rule"
    return WorkflowState(
        job_id=state["job_id"],
        organization_id=state["organization_id"],
        report_type=state.get("report_type") or "weekly",
        keywords=state.get("keywords") or [],
        time_range_start=state.get("time_range_start") or "",
        time_range_end=state.get("time_range_end") or "",
        source_whitelist=state.get("source_whitelist") or [],
        use_llm_writing=bool(use_llm),
        language=state.get("language") or "zh-CN",
        kb_chunks=state.get("kb_chunks") or [],
    )


def _from_workflow(ws: WorkflowState) -> dict[str, Any]:
    st = "completed" if ws.status == "success" else ("failed" if ws.status == "failed" else ws.status)
    return {
        "collected_docs": ws.documents,
        "cleaned_docs": ws.cleaned_documents,
        "deduplicated_docs": ws.deduplicated_documents,
        "section_map": ws.section_map,
        "sections": ws.section_markdown,
        "section_paragraphs": ws.section_paragraphs,
        "citations": ws.citations,
        "citation_metrics": ws.citation_metrics,
        "charts": ws.charts,
        "markdown": ws.markdown,
        "final_report": ws.markdown,
        "stats": ws.stats,
        "errors": list(ws.errors),
        "status": st,
        "status_message": ws.status_message,
    }


def legacy_pipeline_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 1：整段调用 execute_workflow，等价于原固定流水线，便于稳定交付；
    Phase 2+：拆分为 retriever / cleaner / section_generator 等节点并加条件边。
    """
    persist_fn = persist_fn_var.get()
    ws = _to_workflow(state)
    final = execute_workflow(ws, persist_fn=persist_fn)
    out = _from_workflow(final)
    if final.status != "success" and final.errors:
        out["needs_human"] = False
    return out


def validator_node(state: ReportState) -> dict[str, Any]:
    """Groundedness 轻量门槛：引用校验告警过多则标记需人工复核。"""
    metrics = state.get("citation_metrics") or {}
    warnings = metrics.get("warnings") if isinstance(metrics, dict) else None
    n_warn = len(warnings) if isinstance(warnings, list) else 0
    strict = os.getenv("AGENT_CITATION_WARN_THRESHOLD", "8").strip()
    try:
        threshold = int(strict)
    except ValueError:
        threshold = 8
    if n_warn >= threshold:
        return {
            "needs_human": True,
            "human_reason": f"引用校验告警过多（{n_warn}），建议人工复核后再发布。",
            "status": "needs_human",
            "status_message": "validator_needs_human",
        }
    if state.get("status") == "failed":
        return {
            "needs_human": True,
            "human_reason": "流水线失败：" + "; ".join((state.get("errors") or [])[:3]),
            "status": "failed",
            "status_message": "validator_failed_pipeline",
        }
    return {
        "needs_human": False,
        "human_reason": "",
        "status": state.get("status") or "completed",
        "status_message": state.get("status_message") or "validator_ok",
    }


def report_state_to_workflow(state: ReportState) -> WorkflowState:
    """将 LangGraph 的 ReportState 转成 legacy WorkflowState（给步骤函数/持久化使用）。"""
    return _to_workflow(state)


def build_workflow_state_for_persist(state: ReportState) -> WorkflowState:
    """
    Phase 2：节点只负责生成/渲染，不做落库；
    这里把 Graph 最终状态重建成 WorkflowState，然后由 agent_service 统一 persist。
    """
    ws = _to_workflow(state)

    ws.documents = state.get("collected_docs") or []
    ws.cleaned_documents = state.get("cleaned_docs") or []
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.dedupe_meta = state.get("dedupe_meta") or {}
    ws.section_map = state.get("section_map") or {}
    ws.section_markdown = state.get("sections") or {}
    ws.section_paragraphs = state.get("section_paragraphs") or {}
    ws.citations = state.get("citations") or []
    ws.citation_metrics = state.get("citation_metrics") or {}
    ws.charts = state.get("charts") or []
    ws.structured_signals = state.get("structured_signals") or []

    ws.markdown = state.get("markdown") or state.get("final_report") or ""
    ws.stats = state.get("stats") or {}
    ws.errors = state.get("errors") or []
    ws.status_message = state.get("status_message") or "agent completed"

    if state.get("status") == "failed":
        ws.status = "failed"
    else:
        ws.status = "success"

    return ws


def _count_non_empty_text_items(docs: list[dict[str, Any]]) -> int:
    cnt = 0
    for d in docs:
        t = d.get("cleaned_text") or d.get("raw_text") or ""
        if len(str(t).strip()) >= 120:
            cnt += 1
    return cnt


def retriever_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 2 retriever：复用 legacy plan_sources + crawl_by_whitelist。
    如果内容不足则加 errors['insufficient_docs']，Graph 条件边会回到 planner 重抓。
    """
    ws = _to_workflow(state)
    ws = plan_sources(ws)
    ws = crawl_sources(ws)

    collected = ws.documents or []
    non_empty = _count_non_empty_text_items(collected)

    prev_attempt = int(state.get("retriever_attempt") or 0)
    attempt = prev_attempt + 1
    min_docs = int(os.getenv("AGENT_MIN_DOCS", "8"))
    max_retries = int(os.getenv("AGENT_RETRIEVER_MAX_RETRIES", "3"))

    errors = list(state.get("errors") or [])
    if non_empty < min_docs and attempt <= max_retries:
        errors.append("insufficient_docs")

    stats = {**(state.get("stats") or {}), **(ws.stats or {}), "retriever_attempt": attempt, "retriever_non_empty": non_empty}

    return {
        "collected_docs": collected,
        "stats": stats,
        "errors": errors,
        "retriever_attempt": attempt,
        "status": "running",
        "status_message": f"retriever_done (attempt {attempt})",
    }


def cleaner_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.documents = state.get("collected_docs") or []
    ws = clean_documents(ws)
    return {
        "cleaned_docs": ws.cleaned_documents,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "cleaner_done",
    }


def deduplicator_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.cleaned_documents = state.get("cleaned_docs") or []
    ws = deduplicate_documents(ws)
    return {
        "deduplicated_docs": ws.deduplicated_documents,
        "dedupe_meta": ws.dedupe_meta,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "deduplicator_done",
    }


def classifier_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 2 classifier：默认 rule，保证稳。
    llm 模式作为可选（当环境变量开时才触发）。
    """
    mode = os.getenv("AGENT_CLASSIFIER_MODE", "rule").lower().strip() or "rule"
    errors = list(state.get("errors") or [])

    ws = _to_workflow(state)
    ws.deduplicated_documents = state.get("deduplicated_docs") or []

    if mode == "rule":
        ws = classify_documents(ws)
        return {
            "section_map": ws.section_map,
            "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
            "errors": errors,
            "status": "running",
            "status_message": "classifier_done(rule)",
        }

    # llm 模式：先生成 rule 兜底，再视情况更新 errors
    try:
        ws = classify_documents(ws)
        warnings: list[str] = []
        # 当前 Phase2：不给 llm mapping 强制开启（避免影响稳定性）
        if os.getenv("AGENT_CLASSIFIER_LLM_ENABLED", "false").lower().strip() == "true":
            # TODO: 这里可以再按你给的 assignment JSON mapping 方式接入 llm classifier
            warnings.append("llm_mapping_not_implemented_in_phase2")
        if warnings:
            errors.append("classifier_llm_skipped")
    except Exception:
        errors.append("classifier_failed")
        ws = classify_documents(ws)

    return {
        "section_map": ws.section_map,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "errors": errors,
        "status": "running",
        "status_message": f"classifier_done({mode})",
    }


def section_generator_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_map = state.get("section_map") or {}
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.kb_chunks = state.get("kb_chunks") or []
    ws = generate_sections(ws)
    return {
        "sections": ws.section_markdown,
        "section_paragraphs": ws.section_paragraphs,
        "structured_signals": ws.structured_signals,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "errors": state.get("errors") or [],
        "status": "running",
        "status_message": "section_generator_done",
    }


def citation_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_map = state.get("section_map") or {}
    ws.section_paragraphs = state.get("section_paragraphs") or {}
    ws = generate_citations(ws)
    return {
        "citations": ws.citations,
        "citation_metrics": ws.citation_metrics,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "citation_done",
    }


def chart_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.section_map = state.get("section_map") or {}
    ws.structured_signals = state.get("structured_signals") or []
    ws = generate_charts(ws)
    return {
        "charts": ws.charts,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "chart_done",
    }


def assembler_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_markdown = state.get("sections") or {}
    ws.citations = state.get("citations") or []
    ws = assemble_report(ws)
    return {
        "markdown": ws.markdown,
        "final_report": ws.markdown,
        "status": "completed",
        "status_message": "assembler_done",
    }


def route_after_retriever(state: ReportState) -> str:
    errors = state.get("errors") or []
    attempt = int(state.get("retriever_attempt") or 0)
    max_retries = int(os.getenv("AGENT_RETRIEVER_MAX_RETRIES", "3"))
    if "insufficient_docs" in errors and attempt <= max_retries:
        return "planner"
    return "cleaner"


def route_after_classifier(state: ReportState) -> str:
    errors = state.get("errors") or []
    if "classifier_failed" in errors or "classifier_low_conf" in errors:
        return "retriever"
    return "section_generator"
