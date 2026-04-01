from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.core.db import get_conn


def create_token(user_id: str, organization_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def login(email: str, password: str) -> dict | None:
    # MVP: 使用 schema.sql 中种子账号演示，后续替换为安全哈希校验。
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id::text, u.organization_id::text, u.email, r.code
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id
                WHERE u.email = %s AND u.is_active = TRUE
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row:
                return None
            if password != "demo1234":
                return None

            user_id, org_id, user_email, role = row
            return {
                "id": user_id,
                "organization_id": org_id,
                "email": user_email,
                "role": role,
            }


def create_child_user(owner_user_id: str, email: str, display_name: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT organization_id::text FROM users WHERE id = %s", (owner_user_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("owner not found")
            org_id = row[0]

            cur.execute(
                """
                INSERT INTO users(organization_id, email, password_hash, display_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id::text, email
                """,
                (org_id, email, "demo_hashed_password", display_name),
            )
            user_id, user_email = cur.fetchone()

            cur.execute("SELECT id FROM roles WHERE code = 'member' LIMIT 1")
            role_id = cur.fetchone()[0]
            cur.execute("INSERT INTO user_roles(user_id, role_id) VALUES (%s, %s)", (user_id, role_id))

            return {"id": user_id, "email": user_email, "role": "member"}
