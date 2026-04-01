def can_create_child(role: str) -> bool:
    return role == "owner"


def can_create_job(role: str) -> bool:
    return role in {"owner", "member"}
