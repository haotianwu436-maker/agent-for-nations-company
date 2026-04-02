"""
LangGraph Agent 共享状态（与 legacy WorkflowState 字段对齐，便于逐步拆节点）。
"""
from __future__ import annotations

from typing import Any, TypedDict


class ReportState(TypedDict, total=False):
    # —— 用户与任务 ——
    query: str
    user_id: str
    organization_id: str
    job_id: str
    report_type: str
    language: str
    use_llm_writing: bool

    # —— Planner 产出（JSON 或可序列化 dict）——
    plan: dict[str, Any] | None

    # —— 检索 / 流水线 ——
    keywords: list[str]
    time_range_start: str
    time_range_end: str
    source_whitelist: list[str]
    kb_chunks: list[dict[str, Any]]

    collected_docs: list[dict[str, Any]]
    cleaned_docs: list[dict[str, Any]]
    deduplicated_docs: list[dict[str, Any]]
    # deduplicate_documents 的附加输出
    dedupe_meta: dict[str, Any]
    section_map: dict[str, list[dict[str, Any]]]
    sections: dict[str, str]
    section_paragraphs: dict[str, list[dict[str, Any]]]
    citations: list[dict[str, Any]]
    citation_metrics: dict[str, Any]
    charts: list[dict[str, Any]]
    # generate_sections 会填充（用于 generate_charts 的 theme/org/region 统计）
    structured_signals: list[dict[str, Any]]
    markdown: str
    final_report: str

    stats: dict[str, Any]
    errors: list[str]
    status: str
    status_message: str

    # 用于条件边循环控制
    retriever_attempt: int

    # 多轮对话（后续 Phase 扩展）
    messages: list[dict[str, Any]]

    # Supervisor / 合规
    needs_human: bool
    human_reason: str
