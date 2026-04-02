"""
内部知识检索（当前：关键词重叠）。Phase 3：PDF/Word → 解析分块 → PGVector，供 retriever_node 与 Crawl4AI 混合召回。
"""
import re


def chunk_text(content: str, chunk_size: int = 600) -> list[str]:
    text = re.sub(r"\s+", " ", content or "").strip()
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def retrieve_evidence(query: str, kb_chunks: list[dict], top_k: int = 5) -> list[dict]:
    q_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (query or "").lower()))
    scored = []
    for row in kb_chunks:
        chunk = row.get("chunk_text", "")
        c_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", chunk.lower()))
        if not c_tokens:
            continue
        inter = len(q_tokens.intersection(c_tokens))
        if inter <= 0:
            continue
        score = inter / max(len(q_tokens), 1)
        scored.append(
            {
                "chunk_text": chunk[:280],
                "score": round(score, 4),
                "source_name": row.get("source_name", "knowledge-base"),
                "title": row.get("title", "知识库文档"),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
