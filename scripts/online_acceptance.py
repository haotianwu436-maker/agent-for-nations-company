import json
from datetime import datetime, timedelta, timezone

import psycopg
import requests


API_BASE = "http://127.0.0.1:8000/api/v1"
DB_DSN = "postgresql://media_ai:media_ai@127.0.0.1:5432/media_ai"


def call_api() -> dict:
    out: dict = {}
    session = requests.Session()
    session.trust_env = False
    health = session.get("http://127.0.0.1:8000/healthz", timeout=20)
    out["healthz"] = {"status_code": health.status_code, "json": health.json()}

    login_resp = session.post(
        f"{API_BASE}/auth/login",
        json={"email": "owner@demo.com", "password": "demo1234"},
        timeout=20,
    )
    out["login"] = {"status_code": login_resp.status_code, "json": login_resp.json()}
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)
    payload = {
        "report_type": "weekly",
        "keywords": ["AI", "媒体", "新闻"],
        "time_range_start": (now - timedelta(days=7)).isoformat(),
        "time_range_end": now.isoformat(),
        "source_whitelist": [
            "https://arstechnica.com/ai/2026/03/entire-claude-code-cli-source-code-leaks-thanks-to-exposed-map-file/",
            "https://arstechnica.com/ai/2026/03/how-did-anthropic-measure-ais-theoretical-capabilities-in-the-job-market/",
            "https://arstechnica.com/ai/2026/03/openai-brings-plugins-to-codex-closing-some-of-the-gap-with-claude-code/",
            "https://arstechnica.com/ai/2026/03/the-debut-of-gemini-3-1-flash-live-could-make-it-harder-to-know-if-youre-talking-to-a-robot/",
            "https://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy",
        ],
        "template_name": "global-media-weekly-v1",
        "language": "zh-CN",
    }
    create_resp = session.post(f"{API_BASE}/report-jobs", json=payload, headers=headers, timeout=20)
    out["create_job"] = {"status_code": create_resp.status_code, "json": create_resp.json(), "input": payload}
    job_id = create_resp.json()["id"]

    run_resp = session.post(f"{API_BASE}/report-jobs/{job_id}/run", headers=headers, timeout=180)
    out["run_job"] = {"status_code": run_resp.status_code, "json": run_resp.json()}

    status_resp = session.get(f"{API_BASE}/report-jobs/{job_id}", headers=headers, timeout=20)
    out["job_status"] = {"status_code": status_resp.status_code, "json": status_resp.json()}

    md_resp = session.get(f"{API_BASE}/reports/{job_id}/markdown", headers=headers, timeout=20)
    out["markdown"] = {"status_code": md_resp.status_code, "json": md_resp.json()}

    charts_resp = session.get(f"{API_BASE}/reports/{job_id}/charts", headers=headers, timeout=20)
    out["charts"] = {"status_code": charts_resp.status_code, "json": charts_resp.json()}

    citations_resp = session.get(f"{API_BASE}/reports/{job_id}/citations", headers=headers, timeout=20)
    out["citations"] = {"status_code": citations_resp.status_code, "json": citations_resp.json()}

    out["job_id"] = job_id
    return out


def query_db(job_id: str) -> dict:
    results: dict = {}
    with psycopg.connect(DB_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, status, status_message, started_at, finished_at, stats
                FROM report_jobs WHERE id = %s
                """,
                (job_id,),
            )
            results["report_jobs"] = cur.fetchall()

            cur.execute(
                """
                SELECT id::text, title, source_url, source_name, published_at, left(cleaned_text,300)
                FROM source_items WHERE job_id = %s ORDER BY created_at
                """,
                (job_id,),
            )
            results["source_items"] = cur.fetchall()

            cur.execute(
                """
                SELECT section_type, content_markdown
                FROM report_sections WHERE job_id = %s ORDER BY created_at
                """,
                (job_id,),
            )
            results["report_sections"] = cur.fetchall()

            cur.execute(
                """
                SELECT section_key, source_item_id::text, quote_text
                FROM citations WHERE job_id = %s ORDER BY created_at
                """,
                (job_id,),
            )
            results["citations"] = cur.fetchall()
    return results


def main() -> None:
    api_out = call_api()
    db_out = query_db(api_out["job_id"])
    final = {"api": api_out, "db": db_out}
    with open("scripts/online_acceptance_output.json", "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2, default=str)
    print("scripts/online_acceptance_output.json")


if __name__ == "__main__":
    main()
