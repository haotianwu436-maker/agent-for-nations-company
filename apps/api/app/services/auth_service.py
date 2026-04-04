from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings

# Mock 用户数据（无需数据库）
MOCK_USERS = {
    "owner@demo.com": {
        "id": "user-001",
        "organization_id": "org-001",
        "email": "owner@demo.com",
        "role": "owner",
        "password": "demo1234",
    },
    "admin@demo.com": {
        "id": "user-002",
        "organization_id": "org-001",
        "email": "admin@demo.com",
        "role": "admin",
        "password": "demo1234",
    },
    "member@demo.com": {
        "id": "user-003",
        "organization_id": "org-001",
        "email": "member@demo.com",
        "role": "member",
        "password": "demo1234",
    },
}


def create_token(user_id: str, organization_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def login(email: str, password: str) -> dict | None:
    """Mock 登录 - 无需数据库"""
    user = MOCK_USERS.get(email)
    if not user:
        return None
    if password != user["password"]:
        return None
    
    return {
        "id": user["id"],
        "organization_id": user["organization_id"],
        "email": user["email"],
        "role": user["role"],
    }


def create_child_user(owner_user_id: str, email: str, display_name: str) -> dict:
    """Mock 创建子账号"""
    import uuid
    new_id = str(uuid.uuid4())
    
    new_user = {
        "id": new_id,
        "organization_id": "org-001",
        "email": email,
        "role": "member",
    }
    MOCK_USERS[email] = {**new_user, "password": "demo1234"}
    
    return {"id": new_id, "email": email, "role": "member"}
