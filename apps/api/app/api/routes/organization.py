import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors as pg_errors

from app.api.deps import get_current_user
from app.schemas.branding import BrandingUpdateRequest
from app.services.branding_service import get_branding, update_branding

router = APIRouter(prefix="/organization", tags=["organization"])


def _raise_db(e: psycopg.Error) -> None:
    if isinstance(e, pg_errors.StringDataRightTruncation):
        raise HTTPException(
            status_code=400,
            detail="Logo 或名称超出数据库字段长度。请重启 API（启动时会自动把 logo_url 扩为 TEXT），或在 PostgreSQL 执行：ALTER TABLE organizations ALTER COLUMN logo_url TYPE TEXT;",
        ) from e
    if isinstance(e, pg_errors.InvalidTextRepresentation):
        raise HTTPException(status_code=401, detail="令牌中的组织信息无效，请重新登录。") from e
    raise HTTPException(status_code=503, detail=f"数据库异常：{e!s}") from e


@router.get("/branding")
def get_branding_api(current_user: dict = Depends(get_current_user)):
    try:
        return get_branding(current_user["organization_id"])
    except psycopg.Error as e:
        _raise_db(e)


@router.put("/branding")
def update_branding_api(payload: BrandingUpdateRequest, current_user: dict = Depends(get_current_user)):
    try:
        return update_branding(current_user["organization_id"], payload.name, payload.logo_url)
    except psycopg.Error as e:
        _raise_db(e)
