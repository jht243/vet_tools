"""Basic SEO audit — crawls the live site and checks for common issues."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import settings

logger = logging.getLogger(__name__)

SEED_URLS = [
    "/",
    "/briefing/",
    "/tools/",
    "/va-claims/",
    "/va-disability/",
    "/military-retirement/",
    "/military-pay/",
    "/state-benefits/",
    "/explainers/",
    "/sources/",
]

MAX_PAGES = 200
_TITLE_MAX = 70
_DESC_MAX = 160
_TITLE_MIN = 20
_DESC_MIN = 50


@dataclass
class PageIssues:
    url: str
    status_code: int = 0
    issues: list[str] = field(default_factory=list)


def _abs(base: str, href: str) -> Optional[str]:
    try:
        full = urljoin(base, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            return None
        return full.split("#")[0]
    except Exception:
        return None


def _check_page(url: str, html: str, status: int) -> PageIssues:
    pi = PageIssues(url=url, status_code=status)
    if status >= 400:
        pi.issues.append(f"HTTP {status}")
        return pi

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if not title_text:
        pi.issues.append("missing <title>")
    elif len(title_text) > _TITLE_MAX:
        pi.issues.append(f"title too long ({len(title_text)} chars)")
    elif len(title_text) < _TITLE_MIN:
        pi.issues.append(f"title too short ({len(title_text)} chars)")

    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc_text = desc_tag.get("content", "").strip() if desc_tag else ""
    if not desc_text:
        pi.issues.append("missing meta description")
    elif len(desc_text) > _DESC_MAX:
        pi.issues.append(f"meta description too long ({len(desc_text)} chars)")
    elif len(desc_text) < _DESC_MIN:
        pi.issues.append(f"meta description too short ({len(desc_text)} chars)")

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if not canonical or not canonical.get("href"):
        pi.issues.append("missing canonical link")

    h1_tags = soup.find_all("h1")
    if not h1_tags:
        pi.issues.append("missing h1")
    elif len(h1_tags) > 1:
        pi.issues.append(f"multiple h1 tags ({len(h1_tags)})")

    og_title = soup.find("meta", property="og:title")
    if not og_title:
        pi.issues.append("missing og:title")

    return pi


def run_audit(
    base_url: Optional[str] = None,
    max_pages: int = MAX_PAGES,
    timeout: int = 10,
) -> list[PageIssues]:
    base = (base_url or settings.site_url).rstrip("/")
    visited: set[str] = set()
    queue: list[str] = [base + p for p in SEED_URLS]
    results: list[PageIssues] = []

    client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "VATbot/1.0"})

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = client.get(url)
            html = resp.text
            status = resp.status_code
        except Exception as exc:
            results.append(PageIssues(url=url, status_code=0, issues=[f"fetch error: {exc}"]))
            continue

        pi = _check_page(url, html, status)
        if pi.issues:
            results.append(pi)
            logger.debug("audit: %s — %s", url, pi.issues)

        if status < 400:
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                link = _abs(url, a["href"])
                if link and link.startswith(base) and link not in visited:
                    queue.append(link)

    client.close()
    logger.info("audit: crawled %d pages, %d with issues", len(visited), len(results))
    return results
