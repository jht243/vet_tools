"""Orchestrates distribution channels for a daily run."""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_STATIC_URLS_TO_PING_DAILY = [
    "https://vaclaimsworkspace.com/",
    "https://vaclaimsworkspace.com/briefing/",
    "https://vaclaimsworkspace.com/tools/",
    "https://vaclaimsworkspace.com/va-claims/",
    "https://vaclaimsworkspace.com/va-disability/",
    "https://vaclaimsworkspace.com/military-retirement/",
    "https://vaclaimsworkspace.com/military-pay/",
    "https://vaclaimsworkspace.com/state-benefits/",
    "https://vaclaimsworkspace.com/explainers/",
    "https://vaclaimsworkspace.com/sitemap.xml",
]


def run_indexnow(post_urls: list[str]) -> dict:
    from src.distribution.indexnow import submit_urls

    all_urls = list(dict.fromkeys(_STATIC_URLS_TO_PING_DAILY + post_urls))
    result = submit_urls(all_urls)
    return {
        "success": result.success,
        "submitted": result.submitted,
        "status_code": result.status_code,
        "snippet": result.response_snippet,
    }


def run_all(
    post_urls: Optional[list[str]] = None,
) -> dict:
    post_urls = post_urls or []
    results = {}

    try:
        results["indexnow"] = run_indexnow(post_urls)
    except Exception as exc:
        logger.error("IndexNow failed: %s", exc)
        results["indexnow"] = {"success": False, "error": str(exc)}

    return results
