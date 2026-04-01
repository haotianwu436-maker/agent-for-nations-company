import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.core.db import get_conn

import sys

CURRENT = Path(__file__).resolve()
candidate_paths = [Path("/"), Path("/packages")]
candidate_paths.extend(CURRENT.parents)
for candidate in candidate_paths:
    if (candidate / "packages").exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))
if "/packages" not in sys.path:
    sys.path.append("/packages")

from packages.orchestrator.workflow import WorkflowState, execute_workflow  # noqa: E402


def create_report_job(data: dict, organization_id: str, user_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO report_jobs(
                    organization_id, created_by, report_type, keywords,
                    time_range_start, time_range_end, source_whitelist, template_name, language, status
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, 'pending')
                RETURNING id::text, status, report_type, created_at
                """,
                (
                    organization_id,
                    user_id,
                    data["report_type"],
                    json.dumps(data["keywords"]),
                    data["time_range_start"],
                    data["time_range_end"],
                    json.dumps(data["source_whitelist"]),
                    data["template_name"],
                    data["language"],
                ),
            )
            row = cur.fetchone()
            return {"id": row[0], "status": row[1], "report_type": row[2], "created_at": row[3]}


def list_report_jobs(organization_id: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, status, report_type, created_at
                FROM report_jobs
                WHERE organization_id = %s
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (organization_id,),
            )
            rows = cur.fetchall()
            return [{"id": r[0], "status": r[1], "report_type": r[2], "created_at": r[3]} for r in rows]


def get_report_job(job_id: str, organization_id: str) -> dict | None:
    UUID(job_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, status, report_type, created_at, error_message, status_message, started_at, finished_at
                FROM report_jobs
                WHERE id = %s AND organization_id = %s
                """,
                (job_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "status": row[1],
                "report_type": row[2],
                "created_at": row[3],
                "error_message": row[4],
                "status_message": row[5],
                "started_at": row[6],
                "finished_at": row[7],
            }


def _persist_workflow_state(state: WorkflowState) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM source_items WHERE job_id = %s", (state.job_id,))
            cur.execute("DELETE FROM report_sections WHERE job_id = %s", (state.job_id,))
            cur.execute("DELETE FROM citations WHERE job_id = %s", (state.job_id,))
            cur.execute("DELETE FROM report_charts WHERE job_id = %s", (state.job_id,))

            source_url_to_id: dict[str, str] = {}
            for item in state.cleaned_documents:
                cur.execute(
                    """
                    INSERT INTO source_items(
                        job_id, source_url, title, source_name, body_raw, body_cleaned,
                        raw_text, cleaned_text, published_at, media_name, fetch_status,
                        hash, content_hash, dedupe_group, dedup_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id::text, source_url
                    """,
                    (
                        state.job_id,
                        item.get("source_url") or "",
                        item.get("title") or "未命名标题",
                        item.get("source_name") or "",
                        item.get("raw_text") or "",
                        item.get("cleaned_text") or "",
                        item.get("raw_text") or "",
                        item.get("cleaned_text") or "",
                        item.get("published_at"),
                        item.get("source_name") or item.get("media_name") or "",
                        item.get("fetch_status") or "success",
                        item.get("hash"),
                        item.get("hash"),
                        item.get("dedupe_group"),
                        "kept" if any(d.get("id") == item.get("id") for d in state.deduplicated_documents) else "merged",
                    ),
                )
                inserted_id, inserted_url = cur.fetchone()
                source_url_to_id[inserted_url] = inserted_id

            for section_title, markdown in state.section_markdown.items():
                section_key = next((k for k, v in {
                    "focus": "本期聚焦",
                    "global": "全球瞭望",
                    "case": "案例工场",
                    "trend": "趋势雷达",
                    "practice": "实战锦囊",
                    "visualization": "数据可视化",
                    "appendix": "附录",
                }.items() if v == section_title), "appendix")
                cur.execute(
                    """
                    INSERT INTO report_sections(job_id, section_type, section_key, section_title, content_markdown, markdown_content)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (state.job_id, section_key, section_key, section_title, markdown, markdown),
                )

            for c in state.citations:
                cur.execute(
                    """
                    INSERT INTO citations(
                        job_id, section_key, paragraph_index, claim_text, source_item_id, source_url,
                        quote_text, evidence_snippet, validation_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        state.job_id,
                        c.get("section_key") or "appendix",
                        c.get("paragraph_index", 0),
                        c.get("claim_text") or "",
                        source_url_to_id.get(c.get("source_url") or ""),
                        c.get("source_url") or "",
                        c.get("quote_text") or "",
                        c.get("evidence_snippet") or "",
                        c.get("validation_status") or "pending",
                    ),
                )

            for chart in state.charts:
                cur.execute(
                    """
                    INSERT INTO report_charts(job_id, chart_type, title, labels, values, notes)
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    """,
                    (
                        state.job_id,
                        chart.get("chart_type") or chart.get("type") or "bar",
                        chart.get("title") or "未命名图表",
                        json.dumps(chart.get("labels", [])),
                        json.dumps(chart.get("values", [])),
                        chart.get("notes") or "",
                    ),
                )

            cur.execute(
                """
                UPDATE report_jobs
                SET markdown_content = %s, stats = %s::jsonb, status_message = %s, updated_at = %s
                WHERE id = %s
                """,
                (
                    state.markdown,
                    json.dumps(
                        {
                            **state.stats,
                            "dedupe": state.dedupe_meta,
                            "citation_metrics": state.citation_metrics,
                        }
                    ),
                    state.status_message,
                    datetime.now(timezone.utc),
                    state.job_id,
                ),
            )


def run_report_job(job_id: str, organization_id: str) -> dict | None:
    now = datetime.now(timezone.utc)
    job_payload = None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE report_jobs
                SET status = 'running', status_message = 'workflow started', started_at = %s, updated_at = %s
                WHERE id = %s AND organization_id = %s
                RETURNING id::text, report_type, keywords, time_range_start, time_range_end, source_whitelist, language
                """,
                (now, now, job_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            job_payload = row

    try:
        _, report_type, keywords, start_at, end_at, source_whitelist, language = job_payload
        writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
        use_llm_writing = writing_mode != "rule"
        state = WorkflowState(
            job_id=job_id,
            organization_id=organization_id,
            report_type=report_type,
            keywords=keywords or [],
            time_range_start=start_at.isoformat(),
            time_range_end=end_at.isoformat(),
            source_whitelist=source_whitelist or [],
            language=language or "zh-CN",
            use_llm_writing=use_llm_writing,
        )
        final_state = execute_workflow(state, persist_fn=_persist_workflow_state)
        with get_conn() as conn:
            with conn.cursor() as cur:
                if final_state.status == "success":
                    cur.execute(
                        """
                        UPDATE report_jobs
                        SET status = 'success', status_message = %s, finished_at = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (final_state.status_message, datetime.now(timezone.utc), datetime.now(timezone.utc), job_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE report_jobs
                        SET status = 'failed', status_message = %s, error_message = %s, finished_at = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            final_state.status_message,
                            "; ".join(final_state.errors[:3]),
                            datetime.now(timezone.utc),
                            datetime.now(timezone.utc),
                            job_id,
                        ),
                    )
        return {"id": job_id, "status": final_state.status}
    except Exception as exc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE report_jobs
                    SET status = 'failed', status_message = 'workflow crashed', error_message = %s, finished_at = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (str(exc), datetime.now(timezone.utc), datetime.now(timezone.utc), job_id),
                )
        return {"id": job_id, "status": "failed"}


def get_report_markdown(job_id: str, organization_id: str) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rj.id
                FROM report_jobs rj
                WHERE rj.id = %s AND rj.organization_id = %s
                """,
                (job_id, organization_id),
            )
            if not cur.fetchone():
                return None

            cur.execute(
                """
                SELECT markdown_content
                FROM report_jobs
                WHERE id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return "# 报告未生成\n"
            return row[0]


def get_report_charts(job_id: str, organization_id: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rc.chart_type, rc.title, rc.labels, rc.values, rc.notes
                FROM report_charts rc
                JOIN report_jobs rj ON rj.id = rc.job_id
                WHERE rc.job_id = %s AND rj.organization_id = %s
                ORDER BY rc.created_at ASC
                """,
                (job_id, organization_id),
            )
            rows = cur.fetchall()
            return [{"chart_type": r[0], "title": r[1], "labels": r[2], "values": r[3], "notes": r[4]} for r in rows]


def get_report_citations(job_id: str, organization_id: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.section_key, c.paragraph_index, c.claim_text, c.source_url, c.quote_text, c.evidence_snippet, c.validation_status
                FROM citations c
                JOIN report_jobs rj ON rj.id = c.job_id
                WHERE c.job_id = %s AND rj.organization_id = %s
                ORDER BY c.created_at ASC
                """,
                (job_id, organization_id),
            )
            rows = cur.fetchall()
            return [
                {
                    "section_key": r[0],
                    "paragraph_index": r[1],
                    "claim_text": r[2],
                    "source_url": r[3],
                    "quote_text": r[4],
                    "evidence_snippet": r[5],
                    "validation_status": r[6],
                }
                for r in rows
            ]
