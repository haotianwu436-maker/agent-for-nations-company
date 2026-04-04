"""
LangGraph 报告 Agent 编排。

Phase 1：planner → legacy_pipeline（内嵌原 execute_workflow）→ validator
Phase 2+：拆分 pipeline 节点并增加条件边 / Human-in-the-loop。

支持流式输出（astream），每个节点执行后会 yield 包含 __node__ 标识的状态。
"""
from __future__ import annotations

import logging
import os
from typing import Any, AsyncGenerator

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
        from langgraph.checkpoint.postgres import PostgresSaver

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


async def _astream_with_node_name(
    graph: Any,
    initial_state: dict[str, Any],
    config: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """
    包装 graph.astream，在每个输出中注入 _node_name 标识。
    用于流式 SSE 时的步骤识别。
    """
    current_node = ""
    try:
        async for chunk in graph.astream(initial_state, config):
            if isinstance(chunk, dict):
                # Try to extract node name from different sources
                node_name = chunk.get("_node_name", "")
                
                # If not present, try to infer from state changes
                if not node_name:
                    # Check which keys changed to infer the node
                    if "plan" in chunk and chunk["plan"] is not None and "collected_docs" not in chunk:
                        node_name = "planner"
                    elif "collected_docs" in chunk:
                        node_name = "retriever"
                    elif "cleaned_docs" in chunk:
                        node_name = "cleaner"
                    elif "deduplicated_docs" in chunk:
                        node_name = "deduplicator"
                    elif "section_map" in chunk:
                        node_name = "classifier"
                    elif "sections" in chunk:
                        node_name = "section_generator"
                    elif "citations" in chunk:
                        node_name = "citation"
                    elif "charts" in chunk:
                        node_name = "chart"
                    elif "markdown" in chunk or "final_report" in chunk:
                        node_name = "assembler"
                    elif "grounded_score" in chunk or "needs_human" in chunk:
                        node_name = "validator"
                
                if node_name and node_name != current_node:
                    current_node = node_name
                
                chunk["_node_name"] = current_node
                chunk["__node__"] = current_node
            yield chunk
    except Exception as exc:
        logger.exception("astream_with_node_name failed: %s", exc)
        yield {"_node_name": "error", "__node__": "error", "error": str(exc), "status": "failed"}
