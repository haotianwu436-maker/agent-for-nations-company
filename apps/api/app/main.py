import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.organization import router as organization_router
from app.api.routes.report_jobs import router as report_jobs_router
from app.api.routes.reports import router as reports_router

logger = logging.getLogger(__name__)


def _ensure_logo_url_text_column() -> None:
    """旧库若 logo_url 为 VARCHAR，存 Base64 会 500；启动时尽量改为 TEXT（失败则忽略）。"""
    try:
        from app.core.db import get_conn

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "ALTER TABLE organizations ALTER COLUMN logo_url TYPE TEXT USING logo_url::text"
                )
    except Exception as e:
        logger.debug("organizations.logo_url -> TEXT 跳过: %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_logo_url_text_column()
    yield


app = FastAPI(title="媒体 AI 报告智能体 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    # Next 换端口（如 3001）或本机 IP 访问时仍放行开发环境
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(report_jobs_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")
