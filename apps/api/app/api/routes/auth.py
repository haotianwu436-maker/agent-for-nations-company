from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.schemas.auth import CreateChildRequest, LoginRequest, LoginResponse
from app.services.auth_service import create_child_user, create_token, login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login_api(payload: LoginRequest):
    user = login(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_token(user["id"], user["organization_id"], user["role"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/create-child")
def create_child_api(payload: CreateChildRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="only owner can create child account")
    return create_child_user(current_user["id"], payload.email, payload.display_name)
