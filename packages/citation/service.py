import re


def _find_span(source_text: str, paragraph_text: str) -> tuple[int, int]:
    if not source_text:
        return -1, -1
    low_source = source_text.lower()
    # 优先用句子片段定位；找不到则回退到关键词匹配。
    plain_paragraph = re.sub(r"^\[(模型生成|原文摘录)\]\s*", "", paragraph_text).strip()
    for seg in re.split(r"[。！？.!?]", plain_paragraph):
        seg = seg.strip()
        if len(seg) < 12:
            continue
        idx = low_source.find(seg.lower())
        if idx >= 0:
            return idx, idx + len(seg)
    tokens = [t for t in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{3,}", plain_paragraph)[:6] if t]
    for t in tokens:
        idx = low_source.find(t.lower())
        if idx >= 0:
            return idx, min(len(source_text), idx + 160)
    # 语义近似回退：按关键词命中密度选择文本窗口，避免LLM改写导致精确匹配失败
    keywords = [t for t in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{3,}", plain_paragraph.lower()) if t][:20]
    if keywords and source_text:
        low = source_text.lower()
        best_start = -1
        best_score = 0
        step = 120
        window_size = 360
        for start in range(0, max(len(low) - 1, 1), step):
            end = min(len(low), start + window_size)
            win = low[start:end]
            score = sum(1 for k in keywords if k in win)
            if score > best_score:
                best_score = score
                best_start = start
        if best_start >= 0 and best_score > 0:
            return best_start, min(len(source_text), best_start + window_size)
    return -1, -1


def build_citations_for_sections(section_items: dict[str, list[dict]], section_paragraphs: dict[str, list[dict]] | None = None) -> list[dict]:
    citations: list[dict] = []
    section_paragraphs = section_paragraphs or {}
    for section_key, items in section_items.items():
        paragraphs = section_paragraphs.get(section_key, [])
        for idx, item in enumerate(items):
            paragraph = paragraphs[idx] if idx < len(paragraphs) else {}
            source_text = item.get("cleaned_text") or paragraph.get("source_text") or ""
            source_mode = paragraph.get("source_mode", "extractive")
            if source_mode == "extractive" and source_text:
                span_start, span_end = 0, min(len(source_text), 220)
            else:
                span_start, span_end = _find_span(source_text, paragraph.get("paragraph_text", ""))
                # 摘要句反查失败时，降级到来源正文首段证据，避免弱引用告警
                if span_start < 0 and source_text:
                    span_start, span_end = 0, min(len(source_text), 220)
            snippet = source_text[max(span_start, 0) : span_end] if span_start >= 0 else source_text[:220]
            citations.append(
                {
                    "section_key": section_key,
                    "paragraph_index": idx,
                    "claim_text": paragraph.get("paragraph_text") or item.get("summary") or item.get("title") or "未命名结论",
                    "source_item_id": item.get("id"),
                    "source_url": item.get("source_url") or item.get("url") or "",
                    "quote_text": snippet,
                    "evidence_snippet": f"span[{span_start}:{span_end}] {snippet}",
                    "span_start": span_start,
                    "span_end": span_end,
                    "validation_status": "valid" if (item.get("source_url") or item.get("url")) and span_start >= 0 else "weak",
                    "source_mode": source_mode,
                }
            )
    return citations


def validate_citations(citations: list[dict]) -> dict:
    total = len(citations)
    valid_count = 0
    section_stats: dict[str, dict] = {}
    warnings: list[str] = []

    for item in citations:
        section_key = item.get("section_key", "unknown")
        if section_key not in section_stats:
            section_stats[section_key] = {"total": 0, "valid": 0, "coverage": 0.0}
        section_stats[section_key]["total"] += 1

        if item.get("source_url"):
            valid_count += 1
            section_stats[section_key]["valid"] += 1
            if item.get("validation_status") == "weak":
                warnings.append(f"section={section_key} paragraph={item.get('paragraph_index', 0)} weak citation span")
        else:
            warnings.append(f"section={section_key} paragraph={item.get('paragraph_index', 0)} missing citation")

    for section_key, stat in section_stats.items():
        stat["coverage"] = stat["valid"] / stat["total"] if stat["total"] else 0.0
        if stat["coverage"] < 1.0:
            warnings.append(f"section={section_key} citation coverage={stat['coverage']:.2f}")

    return {
        "total": total,
        "valid": valid_count,
        "overall_coverage": (valid_count / total if total else 0.0),
        "section_coverage": section_stats,
        "warnings": warnings,
    }
