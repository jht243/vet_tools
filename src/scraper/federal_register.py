"""Federal Register scraper for VA, DoD, and OPM regulatory documents.

Queries the Federal Register public JSON API (no key required) for documents
published by the Department of Veterans Affairs, Department of Defense, and
Office of Personnel Management within the configured lookback window.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

FEDERAL_REGISTER_API = "https://www.federalregister.gov/api/v1/documents.json"

# Agency slugs for the Federal Register API
AGENCY_SLUGS: tuple[str, ...] = (
    "veterans-affairs-department",
    "defense-department",
    "personnel-management-office",
)

_FIELDS = [
    "title",
    "publication_date",
    "html_url",
    "abstract",
    "document_number",
    "type",
    "agency_names",
    "agencies",
    "significant",
    "effective_on",
    "docket_ids",
]


class FederalRegisterScraper(BaseScraper):
    """Scrapes the Federal Register API for VA/DoD/OPM documents."""

    def get_source_id(self) -> str:
        return "federal_register"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []
        seen_doc_numbers: set[str] = set()

        if target_date is not None:
            start_date = target_date
            end_date = target_date
        else:
            end_date = date.today()
            start_date = end_date - timedelta(days=settings.scraper_lookback_days)

        for agency_slug in AGENCY_SLUGS:
            try:
                new_articles = self._fetch_agency_docs(
                    agency_slug, start_date, end_date, seen_doc_numbers
                )
                articles.extend(new_articles)
            except Exception as exc:
                logger.warning(
                    "federal_register: failed fetching agency %r: %s", agency_slug, exc
                )
                continue

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    def _fetch_agency_docs(
        self,
        agency_slug: str,
        start_date: date,
        end_date: date,
        seen_doc_numbers: set[str],
    ) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []
        page = 1

        while True:
            # Build list of (key, value) pairs — fields[] must be repeated per field
            param_pairs: list[tuple[str, str]] = [
                ("fields[]", f) for f in _FIELDS
            ]
            param_pairs += [
                ("conditions[agencies][]", agency_slug),
                ("conditions[publication_date][gte]", start_date.isoformat()),
                ("conditions[publication_date][lte]", end_date.isoformat()),
                ("per_page", "40"),
                ("page", str(page)),
                ("order", "newest"),
            ]

            url = self._build_url_from_pairs(param_pairs)
            try:
                data = self._fetch_json(url)
            except Exception as exc:
                logger.warning(
                    "federal_register: page %d for %r failed: %s",
                    page,
                    agency_slug,
                    exc,
                )
                break

            results = data.get("results", [])
            if not results:
                break

            for doc in results:
                article = self._doc_to_article(doc, seen_doc_numbers)
                if article is not None:
                    articles.append(article)

            # Pagination: stop when we've consumed all pages
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        return articles

    def _build_url(self, params: dict[str, str]) -> str:
        """Build the query URL from a simple params dict (no repeated keys)."""
        from urllib.parse import urlencode
        return f"{FEDERAL_REGISTER_API}?{urlencode(list(params.items()))}"

    def _build_url_from_pairs(self, pairs: list[tuple[str, str]]) -> str:
        """Build the query URL from a list of (key, value) pairs (supports repeated keys)."""
        from urllib.parse import urlencode
        return f"{FEDERAL_REGISTER_API}?{urlencode(pairs)}"

    def _fetch_json(self, url: str) -> dict[str, Any]:
        resp = self._fetch(url)
        return resp.json()

    def _doc_to_article(
        self, doc: dict[str, Any], seen_doc_numbers: set[str]
    ) -> Optional[ScrapedArticle]:
        doc_number = doc.get("document_number", "")
        if not doc_number:
            return None
        if doc_number in seen_doc_numbers:
            return None

        title = (doc.get("title") or "").strip()
        html_url = (doc.get("html_url") or "").strip()
        pub_date_str = doc.get("publication_date") or ""

        if not title or not html_url:
            return None

        try:
            pub_date = date.fromisoformat(pub_date_str)
        except (ValueError, TypeError):
            pub_date = date.today()

        abstract = (doc.get("abstract") or "").strip() or None
        doc_type = (doc.get("type") or "Notice").strip()

        agency_names: list[str] = doc.get("agency_names") or []

        extra: dict = {
            "document_number": doc_number,
            "doc_type": doc_type,
            "agency_names": agency_names,
            "significant": doc.get("significant", False),
        }
        if doc.get("effective_on"):
            extra["effective_on"] = doc["effective_on"]
        if doc.get("docket_ids"):
            extra["docket_ids"] = doc["docket_ids"]

        seen_doc_numbers.add(doc_number)

        return ScrapedArticle(
            headline=title,
            published_date=pub_date,
            source_url=html_url,
            body_text=abstract,
            source_name="Federal Register",
            source_credibility="official",
            article_type=doc_type,
            extra_metadata=extra,
        )
