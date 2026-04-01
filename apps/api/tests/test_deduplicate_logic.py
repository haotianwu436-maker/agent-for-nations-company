from packages.orchestrator.workflow import WorkflowState, deduplicate_documents


def test_deduplicate_by_url_and_title():
    state = WorkflowState(
        job_id="job-2",
        organization_id="org-1",
        report_type="weekly",
        keywords=[],
        time_range_start="2026-03-25T00:00:00+00:00",
        time_range_end="2026-04-01T00:00:00+00:00",
        source_whitelist=[],
    )
    state.cleaned_documents = [
        {"id": "a", "source_url": "https://a.com/x?u=1", "title": "同一新闻", "cleaned_text": "abc def"},
        {"id": "b", "source_url": "https://a.com/x?u=2", "title": "同一新闻", "cleaned_text": "abc def ghi"},
        {"id": "c", "source_url": "https://b.com/y", "title": "另一新闻", "cleaned_text": "zzz yyy"},
    ]
    output = deduplicate_documents(state)
    assert output.dedupe_meta["before_count"] == 3
    assert output.dedupe_meta["after_count"] == 2
    assert len(output.dedupe_meta["merged_map"]) >= 1
