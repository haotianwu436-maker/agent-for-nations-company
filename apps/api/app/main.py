from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.organization import router as organization_router
from app.api.routes.report_jobs import router as report_jobs_router
from app.api.routes.reports import router as reports_router

app = FastAPI(title="媒体 AI 报告智能体 API", version="0.1.0")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(report_jobs_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")
