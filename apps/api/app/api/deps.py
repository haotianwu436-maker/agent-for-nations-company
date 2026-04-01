from fastapi import Header, HTTPException
from jose import JWTError, jwt

from app.core.config import settings


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.replace("Bearer ", "", 1)
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return {"id": payload["sub"], "organization_id": payload["org"], "role": payload["role"]}
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
