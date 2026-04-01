import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.orchestrator.workflow import WorkflowState, execute_workflow


def main() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    state = WorkflowState(
        job_id="demo-job-local",
        organization_id="demo-org",
        report_type="weekly",
        keywords=[],
        time_range_start=start.isoformat(),
        time_range_end=now.isoformat(),
        source_whitelist=[
            "https://www.iana.org/domains/reserved",
            "https://httpbin.org/html",
            "https://httpbin.org/xml",
            "https://httpbin.org/robots.txt",
            "https://httpbin.org/encoding/utf8",
            "https://httpbin.org/json",
        ],
    )
    out = execute_workflow(state, persist_fn=None)
    payload = {
        "job_input": {
            "job_id": state.job_id,
            "report_type": state.report_type,
            "keywords": state.keywords,
            "time_range_start": state.time_range_start,
            "time_range_end": state.time_range_end,
            "source_whitelist": state.source_whitelist,
        },
        "status": out.status,
        "status_message": out.status_message,
        "stats": out.stats,
        "source_items_sample": out.cleaned_documents[:3],
        "dedupe": out.dedupe_meta,
        "classification": {k: [x.get("title") for x in v] for k, v in out.section_map.items()},
        "citations_sample": out.citations[:5],
        "charts": out.charts,
        "markdown": out.markdown,
    }
    output_path = ROOT / "scripts" / "demo_output.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
