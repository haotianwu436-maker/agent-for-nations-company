import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.orchestrator.workflow import WorkflowState, execute_workflow


def run_once(mode: str) -> dict:
    now = datetime.now(timezone.utc)
    state = WorkflowState(
        job_id=f"ab-{mode}",
        organization_id="ab-org",
        report_type="weekly",
        keywords=["AI", "媒体", "新闻"],
        time_range_start=(now - timedelta(days=7)).isoformat(),
        time_range_end=now.isoformat(),
        source_whitelist=[
            "https://arstechnica.com/ai/2026/03/entire-claude-code-cli-source-code-leaks-thanks-to-exposed-map-file/",
            "https://arstechnica.com/ai/2026/03/how-did-anthropic-measure-ais-theoretical-capabilities-in-the-job-market/",
            "https://arstechnica.com/ai/2026/03/openai-brings-plugins-to-codex-closing-some-of-the-gap-with-claude-code/",
            "https://arstechnica.com/ai/2026/03/the-debut-of-gemini-3-1-flash-live-could-make-it-harder-to-know-if-youre-talking-to-a-robot/",
            "https://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy",
        ],
        use_llm_writing=(mode == "llm"),
    )
    out = execute_workflow(state, persist_fn=None)
    return {
        "mode": mode,
        "status": out.status,
        "markdown": out.markdown,
        "stats": out.stats,
        "citations": out.citations,
    }


def evaluate(payload: dict) -> dict:
    md = payload["markdown"]
    lines = [x.strip() for x in md.splitlines() if x.strip()]
    readability = sum(1 for x in lines if x.startswith("事件描述：") or x.startswith("行业影响：") or x.startswith("关键信号：") or x.startswith("风险点/机会点："))
    diff_score = len(set([x for x in lines if x.startswith("行业影响：")]))
    citation_warn = len(payload["stats"].get("citation_metrics", {}).get("warnings", []))
    advice_lines = len([x for x in lines if x.startswith("1)") or x.startswith("2)") or x.startswith("3)")])
    return {
        "readability_score": readability,
        "differentiation_score": diff_score,
        "citation_warning_count": citation_warn,
        "advice_quality_proxy": advice_lines,
        "llm_used_count": payload["stats"].get("section_generation_mode", {}).get("llm_summary_count", 0),
    }


def main() -> None:
    rule = run_once("rule")
    llm = run_once("llm")
    result = {
        "rule": {"metrics": evaluate(rule), "stats": rule["stats"]},
        "llm": {"metrics": evaluate(llm), "stats": llm["stats"]},
        "llm_enabled": bool(os.getenv("LITELLM_MODEL")) and os.getenv("LITELLM_API_KEY") not in (None, "", "replace_me"),
    }
    Path("scripts/ab_compare_output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("scripts/ab_compare_output.json")


if __name__ == "__main__":
    main()
