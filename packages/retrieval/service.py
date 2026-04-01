def index_documents(documents: list[dict]) -> None:
    return None


def retrieve_evidence(query: str, top_k: int = 5) -> list[dict]:
    return [{"source_url": "https://example.com", "snippet": "MVP 证据"}][:top_k]
