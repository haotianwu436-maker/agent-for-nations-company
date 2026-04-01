from packages.citation.service import validate_citations


def test_citation_coverage_metrics():
    metrics = validate_citations(
        [
            {"section_key": "focus", "paragraph_index": 0, "source_url": "https://a.com"},
            {"section_key": "focus", "paragraph_index": 1, "source_url": ""},
            {"section_key": "global", "paragraph_index": 0, "source_url": "https://b.com"},
        ]
    )
    assert metrics["total"] == 3
    assert metrics["valid"] == 2
    assert 0 < metrics["overall_coverage"] < 1
    assert "focus" in metrics["section_coverage"]
