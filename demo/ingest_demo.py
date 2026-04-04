import argparse
import hashlib
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _ensure_sys_path():
    current = Path(__file__).resolve()
    candidates = [Path("."), Path("/"), Path("/packages")]
    candidates.extend(current.parents)
    for c in candidates:
        if (c / "packages").exists() and str(c) not in sys.path:
            sys.path.append(str(c))
    if "/packages" not in sys.path:
        sys.path.append("/packages")


_ensure_sys_path()

from packages.retrieval.service import chunk_text, ingest_texts_to_chroma  # noqa: E402


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_file_text(path: Path) -> str:
    suffix = (path.suffix or "").lower().lstrip(".")

    if suffix in {"txt", "md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    # PDF/Word：优先 docling
    if suffix in {"pdf", "docx"}:
        try:
            from docling.document_converter import DocumentConverter  # type: ignore

            converter = DocumentConverter()
            result = converter.convert(str(path))
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
                return text
        except Exception as exc:
            logger.warning("docling_parse_failed path=%s err=%s", path, exc)

    # docx fallback
    if suffix == "docx":
        try:
            from docx import Document  # type: ignore

            doc = Document(str(path))
            return "\n".join([p.text for p in doc.paragraphs if p.text and p.text.strip()])
        except Exception as exc:
            logger.warning("docx_parse_failed path=%s err=%s", path, exc)

    # last resort
    try:
        return path.read_bytes().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Ingest demo PDFs/Word/TXT into chromadb")
    parser.add_argument("--demo_dir", default="demo", help="demo folder path")
    parser.add_argument("--collection_name", default=None, help="override CHROMA_INTERNAL_COLLECTION_NAME")
    args = parser.parse_args()

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    demo_dir = Path(args.demo_dir).resolve()
    if not demo_dir.exists():
        raise SystemExit(f"demo_dir not found: {demo_dir}")

    exts = {".pdf", ".docx", ".txt", ".md"}
    files = [p for p in demo_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    if not files:
        logger.warning("No supported files found under %s (need pdf/docx/txt/md)", demo_dir)

    all_chunks: list[str] = []
    all_metas: list[dict] = []
    chunk_ids: list[str] = []

    chunk_size = int(os.getenv("DEMO_INGEST_CHUNK_SIZE", "600"))

    for f in files:
        raw = _parse_file_text(f)
        raw = _normalize(raw)
        if not raw or len(raw) < 50:
            continue

        title = f.stem
        source_name = "demo"
        source_url = str(f)

        chunks = chunk_text(raw, chunk_size=chunk_size)
        for i, c in enumerate(chunks):
            all_chunks.append(c)
            all_metas.append(
                {
                    "title": title,
                    "source_name": source_name,
                    "source_url": source_url,
                    "org_tag": "demo",
                    "chunk_index": i,
                }
            )
            payload = f"{source_url}-{i}-{c[:200]}"
            chunk_ids.append(hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest())

    if not all_chunks:
        logger.warning("No content chunks generated, nothing to ingest.")
        return

    inserted = ingest_texts_to_chroma(
        texts=all_chunks,
        metadatas=all_metas,
        ids=chunk_ids,
        collection_name=args.collection_name,
    )
    logger.info("Ingest done. inserted_chunks=%s", inserted)


if __name__ == "__main__":
    main()

