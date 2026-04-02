from app.core.db import get_conn


def get_branding(organization_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, COALESCE(logo_url, '') FROM organizations WHERE id = %s", (organization_id,))
            row = cur.fetchone()
            if not row:
                return {
                    "name": "中央广播电视总台研究院新媒体研究部",
                    "logo_url": "/cmg-new-media-brand.png",
                }
            return {"name": row[0], "logo_url": row[1]}


def update_branding(organization_id: str, name: str, logo_url: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE organizations SET name = %s, logo_url = %s WHERE id = %s",
                (name, logo_url, organization_id),
            )
    return {"name": name, "logo_url": logo_url}
