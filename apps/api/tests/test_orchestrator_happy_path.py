from packages.orchestrator import workflow


def test_orchestrator_happy_path(monkeypatch):
    monkeypatch.setattr(
        workflow,
        "crawl_by_whitelist",
        lambda **kwargs: [
            {
                "title": "测试新闻",
                "url": "https://example.com/a",
                "source_url": "https://example.com/a",
                "source_name": "example.com",
                "published_at": "2026-03-28T00:00:00+00:00",
                "raw_text": "AI 媒体新闻",
                "cleaned_text": "AI 媒体新闻",
                "fetch_status": "success",
            }
        ],
    )
    state = workflow.WorkflowState(
        job_id="job-1",
        organization_id="org-1",
        report_type="weekly",
        keywords=[],
        time_range_start="2026-03-25T00:00:00+00:00",
        time_range_end="2026-04-01T00:00:00+00:00",
        source_whitelist=["https://example.com"],
    )
    output = workflow.execute_workflow(state, persist_fn=lambda _: None)
    assert output.status == "success"
    assert output.dedupe_meta["after_count"] >= 1
