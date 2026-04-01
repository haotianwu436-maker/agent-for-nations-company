REQUIRED_SECTIONS = [
    "本期聚焦",
    "全球瞭望",
    "案例工场",
    "趋势雷达",
    "实战锦囊",
    "数据可视化",
    "附录",
]


SECTION_KEYS = {
    "focus": "本期聚焦",
    "global": "全球瞭望",
    "case": "案例工场",
    "trend": "趋势雷达",
    "practice": "实战锦囊",
    "visualization": "数据可视化",
    "appendix": "附录",
}


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen = set()
    unique: list[str] = []
    for line in lines:
        norm = line.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique.append(line)
    return unique


def render_markdown(sections: dict[str, str], section_citations: dict[str, list[dict]] | None = None) -> str:
    section_citations = section_citations or {}
    lines = []
    for title in REQUIRED_SECTIONS:
        content = sections.get(title, "暂无内容")
        content_lines = _dedupe_lines([x for x in content.split("\n") if x.strip()])
        if not content_lines:
            content_lines = ["暂无内容"]
        lines.append(f"## {title}\n")
        lines.extend(content_lines)
        lines.append("\n> 来源脚注区：")
        citems = section_citations.get(title, [])
        if not citems:
            lines.append("- [warning] 本章暂无有效引用")
        else:
            for item in citems:
                source_url = item.get("source_url", "")
                quote = item.get("quote_text", "无摘录")[:120]
                lines.append(f"- [{source_url}] {quote}")
        lines.append("")
    return "\n".join(lines)
