from app.core.db import get_conn


def get_branding(organization_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, COALESCE(logo_url, '') FROM organizations WHERE id = %s", (organization_id,))
            row = cur.fetchone()
            if not row:
                return {"name": "媒体行业 AI 报告智能体", "logo_url": ""}
            return {"name": row[0], "logo_url": row[1]}


def update_branding(organization_id: str, name: str, logo_url: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE organizations SET name = %s, logo_url = %s WHERE id = %s",
                (name, logo_url, organization_id),
            )
    return {"name": name, "logo_url": logo_url}
