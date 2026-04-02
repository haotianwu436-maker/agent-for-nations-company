"""
LangGraph 报告 Agent 编排。

Phase 1：planner → legacy_pipeline（内嵌原 execute_workflow）→ validator
Phase 2+：拆分 pipeline 节点并增加条件边 / Human-in-the-loop。

Checkpoint：默认 MemorySaver；若安装 langgraph-checkpoint-postgres 且设置 LANGGRAPH_CHECKPOINT_PG_URI，可换 PostgresSaver。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from packages.orchestrator.nodes import (
    assembler_node,
    citation_node,
    chart_node,
    cleaner_node,
    deduplicator_node,
    classifier_node,
    planner_node,
    retriever_node,
    section_generator_node,
    validator_node,
    route_after_retriever,
    route_after_classifier,
)
from packages.orchestrator.state import ReportState

logger = logging.getLogger(__name__)


def _make_checkpointer() -> Any:
    uri = os.getenv("LANGGRAPH_CHECKPOINT_PG_URI", "").strip()
    if not uri:
        return MemorySaver()
    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore

        return PostgresSaver.from_conn_string(uri)
    except Exception as exc:
        logger.warning("PostgresSaver 不可用，回退 MemorySaver: %s", exc)
        return MemorySaver()


_compiled_graph = None


def get_report_agent_graph():
    global _compiled_graph
    if _compiled_graph is None:
        workflow = StateGraph(ReportState)
        workflow.add_node("planner", planner_node)
        workflow.add_node("retriever", retriever_node)
        workflow.add_node("cleaner", cleaner_node)
        workflow.add_node("deduplicator", deduplicator_node)
        workflow.add_node("classifier", classifier_node)
        workflow.add_node("section_generator", section_generator_node)
        workflow.add_node("citation", citation_node)
        workflow.add_node("chart", chart_node)
        workflow.add_node("assembler", assembler_node)
        workflow.add_node("validator", validator_node)
        workflow.set_entry_point("planner")

        workflow.add_edge("planner", "retriever")
        workflow.add_edge("cleaner", "deduplicator")
        workflow.add_edge("deduplicator", "classifier")
        workflow.add_edge("section_generator", "citation")
        workflow.add_edge("citation", "chart")
        workflow.add_edge("chart", "assembler")
        workflow.add_edge("assembler", "validator")
        workflow.add_edge("validator", END)

        workflow.add_conditional_edges(
            "retriever",
            route_after_retriever,
            {"planner": "planner", "cleaner": "cleaner"},
        )
        workflow.add_conditional_edges(
            "classifier",
            route_after_classifier,
            {"retriever": "retriever", "section_generator": "section_generator"},
        )
        _compiled_graph = workflow.compile(checkpointer=_make_checkpointer())
    return _compiled_graph


def reset_report_agent_graph() -> None:
    global _compiled_graph
    _compiled_graph = None
