from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.schemas.report_job import CreateReportJobRequest
from app.services.report_job_service import create_report_job, get_report_job, list_report_jobs, run_report_job

router = APIRouter(prefix="/report-jobs", tags=["report-jobs"])


@router.post("")
def create_report_job_api(payload: CreateReportJobRequest, current_user: dict = Depends(get_current_user)):
    if payload.time_range_start >= payload.time_range_end:
        raise HTTPException(status_code=400, detail="invalid time range")
    return create_report_job(payload.model_dump(), current_user["organization_id"], current_user["id"])


@router.get("")
def list_report_jobs_api(current_user: dict = Depends(get_current_user)):
    items = list_report_jobs(current_user["organization_id"])
    return {"items": items, "total": len(items)}


@router.get("/{job_id}")
def get_report_job_api(job_id: str, current_user: dict = Depends(get_current_user)):
    job = get_report_job(job_id, current_user["organization_id"])
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/{job_id}/run")
def run_report_job_api(job_id: str, current_user: dict = Depends(get_current_user)):
    result = run_report_job(job_id, current_user["organization_id"])
    if not result:
        raise HTTPException(status_code=404, detail="job not found")
    return result
