from __future__ import annotations

import logging
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_datetime

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    title: str
    url: str
    source_name: str
    published_at: str | None
    raw_text: str
    cleaned_text: str
    fetch_status: str
    error: str | None = None


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:15000]


def _extract_meta_published_at(soup: BeautifulSoup) -> str | None:
    candidates = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("time", {}),
    ]
    for tag_name, attrs in candidates:
        tags = soup.find_all(tag_name, attrs=attrs) if attrs else soup.find_all(tag_name)
        for tag in tags:
            if tag_name == "meta":
                value = tag.get("content")
            else:
                value = tag.get("datetime") or tag.get_text(" ", strip=True)
            if value and len(value) >= 8:
                return value
    return None


def _extract_jsonld_article_text(soup: BeautifulSoup) -> str:
    chunks: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        data_list = payload if isinstance(payload, list) else [payload]
        for item in data_list:
            if not isinstance(item, dict):
                continue
            article_body = item.get("articleBody") or item.get("description")
            if isinstance(article_body, str) and len(article_body.strip()) > 20:
                chunks.append(article_body)
    return _normalize_text(" ".join(chunks))


def _extract_by_bs4(html: str, url: str) -> tuple[str, str, str | None, int]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.text if soup.title else "").strip() or url
    published_at = _extract_meta_published_at(soup)
    baseline_text = _normalize_text(soup.get_text("\n", strip=True))

    # 优先抽取 article/main，兼容新闻站常见结构。
    article_candidates = []
    for selector in ["article", "main", "[role='main']", ".article-body", ".post-content", ".entry-content"]:
        article_candidates.extend(soup.select(selector))
    candidate_texts: list[str] = []
    for node in article_candidates[:6]:
        candidate_texts.append(_normalize_text(node.get_text(" ", strip=True)))

    jsonld_text = _extract_jsonld_article_text(soup)
    if jsonld_text:
        candidate_texts.append(jsonld_text)

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta_tag:
        meta_desc = _normalize_text(meta_tag.get("content", ""))
        if meta_desc:
            candidate_texts.append(meta_desc)

    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.extract()
    raw_text = _normalize_text(soup.get_text("\n", strip=True))
    candidate_texts.append(raw_text)

    cleaned = max(candidate_texts, key=lambda x: len(x or ""), default="")
    if len(cleaned) < 160 and len(baseline_text) > len(cleaned):
        cleaned = baseline_text

    return title, cleaned, published_at, len(baseline_text)


def _time_in_range(published_at: str | None, start_at: datetime, end_at: datetime) -> bool:
    if not published_at:
        return True
    try:
        parsed = parse_datetime(published_at)
        return start_at <= parsed <= end_at
    except Exception:
        return True


def _domain_allowed(url: str, whitelist: list[str]) -> bool:
    if not whitelist:
        return True
    host = urlparse(url).netloc
    allow_hosts = {urlparse(item).netloc for item in whitelist}
    return host in allow_hosts


def _crawl_one_with_requests(url: str, timeout_seconds: int, retries: int) -> CrawlResult:
    attempt = 0
    while attempt <= retries:
        try:
            resp = requests.get(url, timeout=timeout_seconds, headers={"User-Agent": "media-ai-agent/0.1"})
            resp.raise_for_status()
            title, cleaned_text, published_at, baseline_len = _extract_by_bs4(resp.text, url)
            source_name = urlparse(url).netloc
            return CrawlResult(
                title=title,
                url=url,
                source_name=source_name,
                published_at=published_at,
                raw_text=resp.text[:20000],
                cleaned_text=cleaned_text,
                fetch_status="success",
                error=f"baseline_len={baseline_len};extracted_len={len(cleaned_text)}",
            )
        except Exception as exc:
            attempt += 1
            if attempt > retries:
                return CrawlResult(
                    title=url,
                    url=url,
                    source_name=urlparse(url).netloc,
                    published_at=None,
                    raw_text="",
                    cleaned_text="",
                    fetch_status="failed",
                    error=str(exc),
                )
            time.sleep(0.5 * attempt)
    return CrawlResult(title=url, url=url, source_name=urlparse(url).netloc, published_at=None, raw_text="", cleaned_text="", fetch_status="failed", error="unknown")


def _crawl_with_crawl4ai(url: str, timeout_seconds: int) -> CrawlResult:
    # 使用延迟导入，避免环境没有安装时直接失败。
    from crawl4ai import AsyncWebCrawler  # type: ignore
    import asyncio

    async def _run() -> CrawlResult:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, bypass_cache=True, timeout=timeout_seconds)
            text = getattr(result, "markdown", "") or getattr(result, "cleaned_html", "") or ""
            cleaned = _normalize_text(text)
            return CrawlResult(
                title=getattr(result, "title", "") or url,
                url=url,
                source_name=urlparse(url).netloc,
                published_at=None,
                raw_text=cleaned,
                cleaned_text=cleaned,
                fetch_status="success",
            )

    return asyncio.run(_run())


def crawl_by_whitelist(whitelist: list[str], keywords: list[str], start_at: str, end_at: str, timeout_seconds: int = 10, retries: int = 2) -> list[dict]:
    results: list[dict] = []
    start_dt = parse_datetime(start_at)
    end_dt = parse_datetime(end_at)
    for target in whitelist:
        if not _domain_allowed(target, whitelist):
            logger.warning("domain blocked by whitelist: %s", target)
            continue
        try:
            item = _crawl_with_crawl4ai(target, timeout_seconds)
        except Exception:
            item = _crawl_one_with_requests(target, timeout_seconds, retries)

        as_dict = item.__dict__
        if as_dict["fetch_status"] != "success":
            logger.warning("crawl failed url=%s error=%s", target, as_dict.get("error"))
            results.append(as_dict)
            continue

        if keywords:
            key_hit = any(k.lower() in as_dict["cleaned_text"].lower() or k.lower() in as_dict["title"].lower() for k in keywords)
            if not key_hit:
                logger.info("skip by keyword filter: %s", target)
                continue

        if not _time_in_range(as_dict.get("published_at"), start_dt, end_dt):
            logger.info("skip by time range: %s", target)
            continue

        results.append(as_dict)

    return results
