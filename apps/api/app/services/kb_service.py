from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

from app.core.db import get_conn

CURRENT = Path(__file__).resolve()
candidate_paths = [Path("/"), Path("/packages")]
candidate_paths.extend(CURRENT.parents)
for candidate in candidate_paths:
    if (candidate / "packages").exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))
if "/packages" not in sys.path:
    sys.path.append("/packages")

from packages.retrieval.service import chunk_text, retrieve_evidence  # noqa: E402
from docx import Document

logger = logging.getLogger(__name__)


def _parse_with_docling(file_path: Path) -> tuple[str, bool]:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        text = ""
        if hasattr(result, "document"):
            doc_obj = getattr(result, "document")
            if hasattr(doc_obj, "export_to_markdown"):
                text = doc_obj.export_to_markdown() or ""
            elif hasattr(doc_obj, "export_to_text"):
                text = doc_obj.export_to_text() or ""
        if not text and hasattr(result, "text"):
            text = getattr(result, "text") or ""
        if text.strip():
            return text.strip(), True
    except Exception as exc:
        logger.warning("docling_parse_failed path=%s error=%s", file_path, exc)
    return "", False


def _parse_file_fallback(file_path: Path, file_type: str) -> str:
    if file_type in {"txt", "md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if file_type == "docx":
        doc = Document(str(file_path))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return file_path.read_bytes().decode("utf-8", errors="ignore")


def upload_document(organization_id: str, user_id: str, title: str, content: str, source_name: str = "") -> dict:
    chunks = chunk_text(content)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_documents(organization_id, uploaded_by, title, source_name, content, parsed_file_type, docling_used, docling_fallback_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (organization_id, user_id, title, source_name, content, "text", False, 0),
            )
            doc_id = cur.fetchone()[0]
            for idx, c in enumerate(chunks):
                cur.execute(
                    """
                    INSERT INTO kb_chunks(organization_id, document_id, chunk_index, chunk_text, token_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (organization_id, doc_id, idx, c, len(c)),
                )
    return {"document_id": doc_id, "chunk_count": len(chunks)}


def upload_document_file(
    organization_id: str,
    user_id: str,
    filename: str,
    content_bytes: bytes,
    source_name: str = "",
) -> dict:
    suffix = (Path(filename).suffix.lower() or "").replace(".", "")
    if suffix not in {"txt", "md", "docx"}:
        raise ValueError("only txt/md/docx are supported currently")
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
        tmp.write(content_bytes)
        tmp_path = Path(tmp.name)
    parsed, used_docling = _parse_with_docling(tmp_path)
    fallback_count = 0
    if not parsed.strip():
        parsed = _parse_file_fallback(tmp_path, suffix)
        fallback_count = 1
    tmp_path.unlink(missing_ok=True)
    chunks = chunk_text(parsed)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_documents(organization_id, uploaded_by, title, source_name, content, parsed_file_type, docling_used, docling_fallback_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (organization_id, user_id, filename, source_name, parsed, suffix, used_docling, fallback_count),
            )
            doc_id = cur.fetchone()[0]
            for idx, c in enumerate(chunks):
                cur.execute(
                    """
                    INSERT INTO kb_chunks(organization_id, document_id, chunk_index, chunk_text, token_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (organization_id, doc_id, idx, c, len(c)),
                )
    logger.info(
        "kb_file_uploaded doc=%s type=%s docling_used=%s docling_fallback_count=%s",
        filename,
        suffix,
        used_docling,
        fallback_count,
    )
    return {
        "document_id": doc_id,
        "chunk_count": len(chunks),
        "docling_used": used_docling,
        "docling_fallback_count": fallback_count,
        "parsed_file_type": suffix,
    }


def load_kb_chunks(organization_id: str, limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT kc.chunk_text, kd.source_name, kd.title
                FROM kb_chunks kc
                JOIN kb_documents kd ON kd.id = kc.document_id
                WHERE kc.organization_id = %s
                ORDER BY kc.created_at DESC
                LIMIT %s
                """,
                (organization_id, limit),
            )
            rows = cur.fetchall()
    return [{"chunk_text": r[0], "source_name": r[1] or "knowledge-base", "title": r[2] or "知识库文档"} for r in rows]


def search_kb(organization_id: str, query: str, top_k: int = 5) -> list[dict]:
    chunks = load_kb_chunks(organization_id, limit=400)
    return retrieve_evidence(query=query, kb_chunks=chunks, top_k=top_k)
