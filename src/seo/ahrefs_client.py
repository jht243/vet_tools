"""
Ahrefs API v3 client — low-level HTTP wrapper with rate limiting,
unit tracking, and retry logic.

Usage:
    from src.seo.ahrefs_client import AhrefsClient
    client = AhrefsClient()
    issues = client.site_audit_issues(project_id="9842538")
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from src.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.ahrefs.com/v3"
_MIN_UNITS_PER_REQUEST = 50
_MAX_REQUESTS_PER_MINUTE = 60


class AhrefsAPIError(Exception):
    """Raised on non-2xx Ahrefs responses."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Ahrefs API {status_code}: {message}")


class AhrefsClient:
    """Thin wrapper around the Ahrefs REST API v3."""

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
    ):
        self._key = api_key or getattr(settings, "ahrefs_api_key", "")
        self.project_id = project_id or getattr(settings, "ahrefs_project_id", "9842538")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self._key}"
        self._session.headers["Accept"] = "application/json"

        self._request_times: list[float] = []
        self._units_used = 0

    # ── internal helpers ──────────────────────────────────────────────

    def _throttle(self) -> None:
        """Enforce 60 requests/minute rate limit."""
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= _MAX_REQUESTS_PER_MINUTE:
            sleep_for = 60 - (now - self._request_times[0]) + 0.1
            logger.debug("Ahrefs rate limit: sleeping %.1fs", sleep_for)
            time.sleep(sleep_for)
        self._request_times.append(time.time())

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        retries: int = 2,
    ) -> dict[str, Any]:
        """Issue GET, handle rate limits and retries, track units."""
        self._throttle()

        url = f"{_BASE}/{path}"
        for attempt in range(retries + 1):
            resp = self._session.get(url, params=params, timeout=30)

            if resp.status_code == 429:
                wait = min(2 ** attempt * 5, 60)
                logger.warning("Ahrefs 429 — backing off %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue

            if resp.status_code >= 400:
                body = resp.text[:500]
                raise AhrefsAPIError(resp.status_code, body)

            self._units_used += _MIN_UNITS_PER_REQUEST
            return resp.json()

        raise AhrefsAPIError(429, "Rate limit exceeded after retries")

    @property
    def units_used(self) -> int:
        return self._units_used

    # ── Site Audit endpoints ──────────────────────────────────────────

    def site_audit_issues(self, project_id: str | None = None) -> list[dict]:
        """Get all issue types with counts.  Returns list of issue dicts."""
        pid = project_id or self.project_id
        data = self._get("site-audit/issues", {"project_id": pid})
        return data.get("issues", [])

    def site_audit_issues_with_hits(self, project_id: str | None = None) -> list[dict]:
        """Only issues where crawled > 0 (i.e. actually found problems)."""
        return [
            i for i in self.site_audit_issues(project_id)
            if (i.get("crawled") or 0) > 0
        ]

    def site_audit_pages_for_issue(
        self,
        issue_id: str,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get pages affected by a specific issue UUID."""
        pid = project_id or self.project_id
        data = self._get(
            "site-audit/page-explorer",
            {"project_id": pid, "issue_id": issue_id, "limit": limit, "offset": offset},
        )
        return data.get("pages", [])

    def site_audit_all_pages(
        self,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get all crawled pages (no issue filter)."""
        pid = project_id or self.project_id
        data = self._get(
            "site-audit/page-explorer",
            {"project_id": pid, "limit": limit, "offset": offset},
        )
        return data.get("pages", [])

    def site_audit_page_content(
        self,
        target_url: str,
        select: str = "page_text_md,raw_html",
        project_id: str | None = None,
    ) -> dict:
        """Get raw/rendered content of a specific crawled page."""
        pid = project_id or self.project_id
        data = self._get(
            "site-audit/page-content",
            {"project_id": pid, "target_url": target_url, "select": select},
        )
        return data.get("page-content", {})

    def site_audit_health(self, project_id: str | None = None) -> dict:
        """Get project health score."""
        pid = project_id or self.project_id
        data = self._get("site-audit/projects", {"project_id": pid})
        projects = data.get("projects", [])
        return projects[0] if projects else {}

    # ── Site Explorer endpoints ───────────────────────────────────────

    def organic_keywords(
        self,
        target: str = "banthebots.org",
        country: str = "us",
        select: str = "keyword,volume,best_position,best_position_url,is_informational,is_commercial,is_transactional,is_local,is_navigational,is_branded",
        order_by: str = "volume:desc",
        limit: int = 100,
        date: str | None = None,
    ) -> list[dict]:
        """Get organic keywords we rank for."""
        from datetime import date as _date
        d = date or _date.today().isoformat()
        data = self._get(
            "site-explorer/organic-keywords",
            {
                "target": target,
                "country": country,
                "date": d,
                "mode": "subdomains",
                "select": select,
                "order_by": order_by,
                "limit": limit,
            },
        )
        return data.get("keywords", [])

    def top_pages(
        self,
        target: str = "banthebots.org",
        country: str = "us",
        select: str = "url,traffic,keywords,top_keyword,top_keyword_volume,position",
        limit: int = 50,
        date: str | None = None,
    ) -> list[dict]:
        from datetime import date as _date
        d = date or _date.today().isoformat()
        data = self._get(
            "site-explorer/top-pages",
            {
                "target": target,
                "country": country,
                "date": d,
                "mode": "subdomains",
                "select": select,
                "limit": limit,
            },
        )
        return data.get("pages", [])

    def pages_by_internal_links(
        self,
        target: str = "banthebots.org",
        select: str = "url,links_internal",
        order_by: str = "links_internal:asc",
        limit: int = 50,
        date: str | None = None,
    ) -> list[dict]:
        from datetime import date as _date
        d = date or _date.today().isoformat()
        data = self._get(
            "site-explorer/pages-by-internal-links",
            {
                "target": target,
                "date": d,
                "mode": "subdomains",
                "select": select,
                "order_by": order_by,
                "limit": limit,
            },
        )
        return data.get("pages", [])

    # ── Keywords Explorer endpoints ───────────────────────────────────

    def keyword_overview(
        self,
        keywords: list[str],
        country: str = "us",
        select: str = "keyword,volume,difficulty,cpc,clicks,traffic_potential,parent_topic,parent_volume,intents",
    ) -> list[dict]:
        """Get metrics + intent for a batch of keywords."""
        kw_str = ",".join(keywords)
        data = self._get(
            "keywords-explorer/overview",
            {"keywords": kw_str, "country": country, "select": select},
        )
        return data.get("keywords", [])

    def matching_terms(
        self,
        keyword: str,
        country: str = "us",
        select: str = "keyword,volume,difficulty,traffic_potential,intents",
        limit: int = 50,
    ) -> list[dict]:
        """Get keywords matching a seed term."""
        data = self._get(
            "keywords-explorer/matching-terms",
            {"keyword": keyword, "country": country, "select": select, "limit": limit},
        )
        return data.get("keywords", [])

    def related_terms(
        self,
        keyword: str,
        country: str = "us",
        select: str = "keyword,volume,difficulty,traffic_potential,intents",
        limit: int = 50,
    ) -> list[dict]:
        """Get semantically related keywords."""
        data = self._get(
            "keywords-explorer/related-terms",
            {"keyword": keyword, "country": country, "select": select, "limit": limit},
        )
        return data.get("keywords", [])

    def search_suggestions(
        self,
        keyword: str,
        country: str = "us",
        select: str = "keyword,volume,difficulty",
        limit: int = 30,
    ) -> list[dict]:
        data = self._get(
            "keywords-explorer/search-suggestions",
            {"keyword": keyword, "country": country, "select": select, "limit": limit},
        )
        return data.get("keywords", [])

    # ── SERP Overview ─────────────────────────────────────────────────

    def serp_overview(
        self,
        keyword: str,
        country: str = "us",
        select: str = "url,title,domain_rating,url_rating,backlinks,refdomains,traffic,position,type,page_type",
        limit: int = 10,
    ) -> list[dict]:
        """Get top SERP results for a keyword."""
        data = self._get(
            "serp-overview/serp-overview",
            {"keyword": keyword, "country": country, "select": select, "limit": limit},
        )
        return data.get("positions", [])

    # ── Subscription Info ─────────────────────────────────────────────

    def usage(self) -> dict:
        """Current plan, usage, and limits."""
        data = self._get("subscription-info/limits-and-usage")
        return data.get("limits_and_usage", {})
