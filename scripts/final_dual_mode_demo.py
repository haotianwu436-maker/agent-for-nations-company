import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.orchestrator.workflow import WorkflowState, execute_workflow


WHITELIST = [
    "https://arstechnica.com/ai/2026/03/entire-claude-code-cli-source-code-leaks-thanks-to-exposed-map-file/",
    "https://arstechnica.com/ai/2026/03/how-did-anthropic-measure-ais-theoretical-capabilities-in-the-job-market/",
    "https://arstechnica.com/ai/2026/03/openai-brings-plugins-to-codex-closing-some-of-the-gap-with-claude-code/",
    "https://arstechnica.com/ai/2026/03/the-debut-of-gemini-3-1-flash-live-could-make-it-harder-to-know-if-youre-talking-to-a-robot/",
    "https://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy",
]


def run_mode(mode: str) -> dict:
    now = datetime.now(timezone.utc)
    state = WorkflowState(
        job_id=f"final-{mode}",
        organization_id="final-org",
        report_type="weekly",
        keywords=["AI", "媒体", "新闻"],
        time_range_start=(now - timedelta(days=7)).isoformat(),
        time_range_end=now.isoformat(),
        source_whitelist=WHITELIST,
        use_llm_writing=(mode == "llm"),
    )
    final_state = execute_workflow(state, persist_fn=None)
    out_md = ROOT / "scripts" / f"final_{mode}_report.md"
    out_md.write_text(final_state.markdown, encoding="utf-8")
    return {
        "mode": mode,
        "status": final_state.status,
        "markdown_file": str(out_md),
        "stats": final_state.stats,
        "citation_warning_count": len(final_state.citation_metrics.get("warnings", [])),
    }


def main() -> None:
    llm_res = run_mode("llm")
    rule_res = run_mode("rule")
    result = {"llm": llm_res, "rule": rule_res}
    out = ROOT / "scripts" / "final_dual_mode_output.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
