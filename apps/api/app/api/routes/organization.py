from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.branding import BrandingUpdateRequest
from app.services.branding_service import get_branding, update_branding

router = APIRouter(prefix="/organization", tags=["organization"])


@router.get("/branding")
def get_branding_api(current_user: dict = Depends(get_current_user)):
    return get_branding(current_user["organization_id"])


@router.put("/branding")
def update_branding_api(payload: BrandingUpdateRequest, current_user: dict = Depends(get_current_user)):
    return update_branding(current_user["organization_id"], payload.name, payload.logo_url)
