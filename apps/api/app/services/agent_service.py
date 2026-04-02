"""
自然语言 → LangGraph Agent → legacy execute_workflow（Phase 1 编排）。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.kb_service import load_kb_chunks
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

from packages.orchestrator.graph import get_report_agent_graph  # noqa: E402
from packages.orchestrator.nodes import build_workflow_state_for_persist  # noqa: E402
from packages.orchestrator.workflow import persist_report  # noqa: E402

logger = logging.getLogger(__name__)


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
    # Phase 2：节点不落库，持久化统一放到这里
    persist_failed = False
    if st != "failed" and md:
        try:
            ws = build_workflow_state_for_persist(final)
            ws.status_message = final.get("status_message") or "agent completed"
            persist_report(ws, persist_fn=_persist_workflow_state)
        except Exception as exc:
            logger.exception("persist_failed job_id=%s: %s", job_id, exc)
            # persist 失败不阻断返回，但把错误暴露出来，便于你定位
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
