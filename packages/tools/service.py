from __future__ import annotations

from urllib.parse import quote, urlparse

import requests


def verify_source_with_archive(url: str, timeout_seconds: int = 8) -> dict:
    api = f"https://web.archive.org/cdx/search/cdx?url={quote(url)}&output=json&limit=1"
    try:
        resp = requests.get(api, timeout=timeout_seconds)
        ok = resp.status_code == 200 and len(resp.text) > 2
        return {"tool": "archive_verify", "url": url, "success": ok, "http_status": resp.status_code}
    except Exception as exc:
        return {"tool": "archive_verify", "url": url, "success": False, "error": str(exc)}


def detect_aigc_mock(text: str) -> dict:
    tokens = max(len((text or "").split()), 1)
    ratio = min(0.95, round(0.2 + (tokens % 53) / 100, 2))
    return {"tool": "aigc_mock", "success": True, "aigc_probability": ratio}


def run_tools_on_items(items: list[dict], limit: int = 5) -> dict:
    results: list[dict] = []
    for item in items[:limit]:
        url = item.get("source_url") or item.get("url") or ""
        if not urlparse(url).scheme:
            continue
        results.append(verify_source_with_archive(url))
        results.append(detect_aigc_mock(item.get("cleaned_text") or item.get("title") or ""))
    return {
        "tool_results": results,
        "tool_stats": {
            "tools_called": len(results),
            "archive_verify_count": len([x for x in results if x.get("tool") == "archive_verify"]),
            "aigc_mock_count": len([x for x in results if x.get("tool") == "aigc_mock"]),
            "archive_success_count": len([x for x in results if x.get("tool") == "archive_verify" and x.get("success")]),
        },
    }
