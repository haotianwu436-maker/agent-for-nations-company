from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.db import get_conn
from app.services.export_service import export_markdown_to_docx, export_markdown_to_pdf
from app.services.report_job_service import get_report_citations, get_report_charts, get_report_markdown

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{job_id}/markdown")
def get_markdown(job_id: str, current_user: dict = Depends(get_current_user)):
    markdown = get_report_markdown(job_id, current_user["organization_id"])
    if markdown is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {"job_id": job_id, "markdown": markdown}


@router.get("/{job_id}/sections")
def get_sections(job_id: str, current_user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rs.section_key, rs.section_title, rs.markdown_content
                FROM report_sections rs
                JOIN report_jobs rj ON rj.id = rs.job_id
                WHERE rs.job_id = %s AND rj.organization_id = %s
                ORDER BY rs.created_at ASC
                """,
                (job_id, current_user["organization_id"]),
            )
            rows = cur.fetchall()
    return {"job_id": job_id, "sections": [{"key": r[0], "title": r[1], "content": r[2]} for r in rows]}


@router.get("/{job_id}/charts")
def get_charts(job_id: str, current_user: dict = Depends(get_current_user)):
    charts = get_report_charts(job_id, current_user["organization_id"])
    return {"job_id": job_id, "charts": charts}


@router.get("/{job_id}/citations")
def get_citations(job_id: str, current_user: dict = Depends(get_current_user)):
    citations = get_report_citations(job_id, current_user["organization_id"])
    return {"job_id": job_id, "citations": citations}


@router.get("/{job_id}/export")
def export_report(job_id: str, format: str = Query("docx"), current_user: dict = Depends(get_current_user)):
    markdown = get_report_markdown(job_id, current_user["organization_id"])
    if markdown is None:
        raise HTTPException(status_code=404, detail="report not found")
    if format == "docx":
        path = export_markdown_to_docx(job_id, markdown)
        return FileResponse(path=str(path), filename=path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if format == "pdf":
        path = export_markdown_to_pdf(job_id, markdown)
        return FileResponse(path=str(path), filename=path.name, media_type="application/pdf")
    raise HTTPException(status_code=400, detail="supported formats: docx, pdf")
