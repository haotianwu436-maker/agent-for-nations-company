from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import get_current_user
from app.schemas.kb import UploadKnowledgeRequest
from app.services.kb_service import load_kb_chunks, search_kb, upload_document, upload_document_file

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents")
def upload_doc_api(payload: UploadKnowledgeRequest, current_user: dict = Depends(get_current_user)):
    return upload_document(
        organization_id=current_user["organization_id"],
        user_id=current_user["id"],
        title=payload.title,
        content=payload.content,
        source_name=payload.source_name,
    )


@router.get("/search")
def search_doc_api(q: str = Query(..., min_length=2), top_k: int = 5, current_user: dict = Depends(get_current_user)):
    return {"items": search_kb(current_user["organization_id"], q, top_k=top_k)}


@router.get("/chunks")
def list_chunks_api(current_user: dict = Depends(get_current_user)):
    return {"items": load_kb_chunks(current_user["organization_id"])}


@router.post("/files")
async def upload_file_api(
    file: UploadFile = File(...),
    source_name: str = "",
    current_user: dict = Depends(get_current_user),
):
    payload = await file.read()
    return upload_document_file(
        organization_id=current_user["organization_id"],
        user_id=current_user["id"],
        filename=file.filename or "knowledge.txt",
        content_bytes=payload,
        source_name=source_name,
    )
