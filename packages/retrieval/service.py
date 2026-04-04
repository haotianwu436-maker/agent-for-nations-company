"""
内部知识检索（token-overlap）+ Phase 3：chromadb 混合 RAG

核心要求：
- 保持 `chunk_text` 与 `retrieve_evidence` 兼容旧 Phase 2
- Phase 3 新增 chromadb ingest 与向量检索函数
- chromadb 未初始化/不可用时，上层回退到 token-overlap retrieve_evidence
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
import torch
from transformers import AutoModel, AutoTokenizer


def chunk_text(content: str, chunk_size: int = 600) -> list[str]:
    text = re.sub(r"\s+", " ", content or "").strip()
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def retrieve_evidence(query: str, kb_chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Phase 2 fallback：关键词重叠检索。
    返回结构保持兼容：chunk_text/score/source_name/title(+可选 source_url)。
    """
    q_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (query or "").lower()))
    scored: list[dict[str, Any]] = []
    for row in kb_chunks:
        chunk = row.get("chunk_text", "")
        c_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (chunk or "").lower()))
        if not c_tokens:
            continue
        inter = len(q_tokens.intersection(c_tokens))
        if inter <= 0:
            continue
        score = inter / max(len(q_tokens), 1)
        scored.append(
            {
                "chunk_text": chunk[:280],
                "score": round(float(score), 4),
                "source_name": row.get("source_name", "knowledge-base"),
                "title": row.get("title", "知识库文档"),
                "source_url": row.get("source_url") or "knowledge-base",
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _persist_dir() -> str:
    return os.getenv("CHROMA_PERSIST_DIR", "/data/chroma").strip() or "/data/chroma"


def _collection_name() -> str:
    return os.getenv("CHROMA_INTERNAL_COLLECTION_NAME", "agent_internal_kb").strip() or "agent_internal_kb"


def _bge_model_name() -> str:
    return os.getenv("BGE_EMBED_MODEL", "BAAI/bge-large-zh-v1.5").strip() or "BAAI/bge-large-zh-v1.5"


@lru_cache(maxsize=1)
def _embedder():
    """
    用 transformers 加载 BGE embedding（本地 CPU）。
    注意：加载模型很重，上层应尽量在 chroma ingest/检索时触发；chromadb readiness 检查不要触发 embedding。
    """
    model_name = _bge_model_name()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    return tokenizer, model


@torch.no_grad()
def _embed_texts(texts: list[str], batch_size: int = 8) -> list[list[float]]:
    tokenizer, model = _embedder()
    vecs: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        encoded = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        # bge 常用均值池化 + L2 normalize（cosine 相似度通常更稳）
        outputs = model(**encoded)
        token_embeddings = outputs.last_hidden_state  # [B, S, H]
        attention_mask = encoded["attention_mask"].unsqueeze(-1)  # [B, S, 1]
        masked = token_embeddings * attention_mask
        summed = masked.sum(dim=1)  # [B, H]
        denom = attention_mask.sum(dim=1).clamp(min=1e-9)  # [B, 1]
        embeddings = summed / denom
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        vecs.extend(embeddings.cpu().tolist())
    return vecs


def chroma_is_ready() -> bool:
    """
    判断 chromadb 是否已初始化（有内容）：
    - 不做 embedding warmup，避免触发下载/加载大模型
    - 通过目录与集合计数判断
    """
    persist_dir = _persist_dir()
    cn = _collection_name()
    try:
        if not os.path.isdir(persist_dir):
            return False

        client = chromadb.PersistentClient(path=persist_dir)
        col = client.get_collection(name=cn)
        # 不依赖 embedding 是否可用
        try:
            cnt = col.count()
        except Exception:
            got = col.get(limit=1, include=[])
            cnt = len(got.get("ids") or [])
        return cnt > 0
    except Exception:
        return False


def ingest_texts_to_chroma(
    texts: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str] | None = None,
    collection_name: str | None = None,
) -> int:
    """
    写入 chromadb：
    - 使用 bge-large-zh-v1.5 本地 embedding
    - 自动跳过已有 ids（避免重复 ingest 失败）
    """
    if len(texts) == 0:
        return 0
    if len(metadatas) != len(texts):
        raise ValueError("texts 与 metadatas 长度必须一致")

    cn = collection_name or _collection_name()
    persist_dir = _persist_dir()

    client = chromadb.PersistentClient(path=persist_dir)
    col = client.get_or_create_collection(name=cn)

    if ids is None:
        ids = []
        for i, t in enumerate(texts):
            payload = f"{cn}-{i}-{t[:200]}"
            ids.append(hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest())

    if len(ids) != len(texts):
        raise ValueError("ids 长度必须与 texts 一致")

    # 过滤已有 ids
    try:
        got = col.get(ids=ids, include=[])
        exist_ids = set(got.get("ids") or [])
    except Exception:
        exist_ids = set()

    add_indices = [i for i, did in enumerate(ids) if did not in exist_ids]
    if not add_indices:
        return 0

    texts_to_add = [texts[i] for i in add_indices]
    metas_to_add = [metadatas[i] for i in add_indices]
    ids_to_add = [ids[i] for i in add_indices]

    embeddings = _embed_texts(texts_to_add)

    col.add(
        ids=ids_to_add,
        documents=texts_to_add,
        embeddings=embeddings,
        metadatas=metas_to_add,
    )
    return len(texts_to_add)


def retrieve_chroma_evidence(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    内部 KB（chromadb 向量检索）：
    返回结构用于 nodes.py 映射为 internal docs。
    """
    cn = _collection_name()
    client = chromadb.PersistentClient(path=_persist_dir())
    col = client.get_collection(name=cn)

    q_vec = _embed_texts([query], batch_size=1)[0]

    res = col.query(
        query_embeddings=[q_vec],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    hits: list[dict[str, Any]] = []
    for i in range(len(docs)):
        dist = float(dists[i]) if i < len(dists) else 999.0
        # dist 越小越相似；换算成 score 越大越相似
        score = 1.0 / (1.0 + dist) if dist >= 0 else 0.0
        meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        hits.append(
            {
                "chunk_text": str(docs[i] or ""),
                "score": round(score, 6),
                "source_name": meta.get("source_name") or "internal-kb",
                "title": meta.get("title") or "内部知识库文档",
                "source_url": meta.get("source_url") or "chroma://internal",
            }
        )

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:top_k]


def _kb_examples_dir() -> Path:
    return Path(os.getenv("KB_EXAMPLES_DIR", "demo/kb_examples")).resolve()


def _kb_meta_path() -> Path:
    return Path(_persist_dir()).resolve() / "kb_sync_meta.json"


def _read_kb_meta() -> dict[str, Any]:
    p = _kb_meta_path()
    if not p.exists():
        return {"indexed_files": {}, "last_updated_at": ""}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"indexed_files": {}, "last_updated_at": ""}


def _write_kb_meta(meta: dict[str, Any]) -> None:
    p = _kb_meta_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_kb_file_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    # simple fallback for docs/pdf in demo mode
    try:
        return path.read_bytes().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def auto_update_kb() -> dict[str, Any]:
    """
    扫描 demo/kb_examples，自动 ingest 新增/修改文件（简单版本）。
    """
    base_dir = _kb_examples_dir()
    if not base_dir.exists():
        return {"updated_files": 0, "inserted_chunks": 0, "status": "no_kb_dir"}

    meta = _read_kb_meta()
    indexed_files = dict(meta.get("indexed_files") or {})
    exts = {".txt", ".md", ".pdf", ".docx"}
    files = [p for p in base_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]

    changed: list[Path] = []
    for f in files:
        key = str(f.resolve())
        mtime = f.stat().st_mtime
        if float(indexed_files.get(key, 0.0)) < float(mtime):
            changed.append(f)

    if not changed:
        return {"updated_files": 0, "inserted_chunks": 0, "status": "up_to_date"}

    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []
    chunk_size = int(os.getenv("DEMO_INGEST_CHUNK_SIZE", "600"))
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default-org").strip() or "default-org"

    for f in changed:
        content = re.sub(r"\s+", " ", _parse_kb_file_text(f)).strip()
        if not content:
            continue
        chunks = chunk_text(content, chunk_size=chunk_size)
        for idx, chunk in enumerate(chunks):
            texts.append(chunk)
            metadatas.append(
                {
                    "title": f.stem,
                    "source_name": "internal-kb",
                    "source_url": str(f.resolve()),
                    "organization_id": org_id,
                    "chunk_index": idx,
                }
            )
            payload = f"{f.resolve()}-{f.stat().st_mtime}-{idx}-{chunk[:120]}"
            ids.append(hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest())

    inserted = 0
    if texts:
        inserted = ingest_texts_to_chroma(texts=texts, metadatas=metadatas, ids=ids)

    for f in changed:
        indexed_files[str(f.resolve())] = f.stat().st_mtime
    meta = {"indexed_files": indexed_files, "last_updated_at": datetime.now(timezone.utc).isoformat()}
    _write_kb_meta(meta)

    return {"updated_files": len(changed), "inserted_chunks": inserted, "status": "ok"}


def get_kb_status() -> dict[str, Any]:
    """
    返回知识库状态：文档数量与最后更新时间。
    """
    meta = _read_kb_meta()
    indexed_files = dict(meta.get("indexed_files") or {})
    doc_count = len(indexed_files)
    last_updated_at = str(meta.get("last_updated_at") or "")
    chunk_count = 0
    try:
        client = chromadb.PersistentClient(path=_persist_dir())
        col = client.get_collection(name=_collection_name())
        chunk_count = int(col.count())
    except Exception:
        chunk_count = 0
    return {
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "last_updated_at": last_updated_at,
    }
