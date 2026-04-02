"""将演示账号所在组织的名称与 Logo 更新为 patches 中的总台配置（需 PostgreSQL 已启动）。"""
from pathlib import Path

from app.core.db import get_conn


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sql = (root / "db/patches/002_branding_cmg_new_media.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            n = cur.rowcount
    print(f"OK: branding patch applied, rows updated: {n}")


if __name__ == "__main__":
    main()
