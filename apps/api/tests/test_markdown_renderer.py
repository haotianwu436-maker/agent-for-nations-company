from packages.reporting.renderer import render_markdown


def test_markdown_renderer_keeps_seven_sections():
    md = render_markdown(
        {"本期聚焦": "- A\n- A", "全球瞭望": "- B"},
        {"本期聚焦": [{"source_url": "https://a.com", "quote_text": "q"}]},
    )
    assert "## 本期聚焦" in md
    assert "## 全球瞭望" in md
    assert "## 案例工场" in md
    assert "## 趋势雷达" in md
    assert "## 实战锦囊" in md
    assert "## 数据可视化" in md
    assert "## 附录" in md
