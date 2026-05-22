"""DoD Basic Allowance for Housing (BAH) rates monitoring scraper.

Fetches the DoD travel/BAH lookup page to detect when updated rates are
published for the current year.  BAH rates are updated annually (usually
January 1) so this scraper functions as a monitoring tool rather than a
high-frequency data source.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Optional

from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

BAH_RATE_URL = "https://www.travel.dod.mil/Allowances/Basic-Allowance-for-Housing/BAH-Rate-Lookup/"

# Fallback: DFAS BAH information page
BAH_RATE_FALLBACK_URL = (
    "https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/BAH/"
)

# Informational URL for published rate tables (browseable directory)
BAH_DOCS_BASE = "https://www.defensetravel.dod.mil/Docs/perdiem/browse/Allowances/BAH/"


def _extract_year(text: str) -> Optional[int]:
    years = re.findall(r"\b(20\d{2})\b", text)
    return max(int(y) for y in years) if years else None


def _extract_effective_date(text: str) -> Optional[str]:
    patterns = [
        r"effective\s+((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+20\d{2})",
        r"effective\s+(\d{1,2}/\d{1,2}/20\d{2})",
        r"(\d{1,2}/\d{1,2}/20\d{2})\s+effective",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


class BAHRatesScraper(BaseScraper):
    """Monitors DoD travel portal for BAH rate updates."""

    def get_source_id(self) -> str:
        return "bah_rates"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()

        page_text: Optional[str] = None
        page_url_used = BAH_RATE_URL

        for url in (BAH_RATE_URL, BAH_RATE_FALLBACK_URL):
            try:
                resp = self._fetch(url)
                page_text = resp.text
                page_url_used = url
                break
            except Exception as exc:
                logger.debug("bah_rates: failed to fetch %r: %s", url, exc)

        if page_text is None:
            logger.warning("bah_rates: all URLs failed, returning empty result")
            return ScrapeResult(
                source=self.get_source_id(),
                success=True,
                articles=[],
                error="BAH rate pages unavailable",
                duration_seconds=int(time.monotonic() - start),
            )

        articles = self._parse_page(page_text, page_url_used)

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    def _parse_page(self, page_text: str, source_url: str) -> list[ScrapedArticle]:
        clean_text = re.sub(r"<[^>]+>", " ", page_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        year = _extract_year(clean_text)
        effective_date_str = _extract_effective_date(clean_text)

        current_year = date.today().year
        rate_year = year or current_year

        headline = f"{rate_year} Basic Allowance for Housing (BAH) Rates Published"

        body_parts = [
            f"The Department of Defense has published BAH rates for {rate_year}.",
            "BAH is a monthly housing allowance paid to service members who live "
            "off-post, based on their pay grade, dependency status, and duty location.",
        ]
        if effective_date_str:
            body_parts.append(f"Rates are effective {effective_date_str}.")
        body_parts.append(
            "Service members can look up their specific BAH rate by duty station "
            "and pay grade using the DoD BAH Rate Lookup tool."
        )
        body_text = " ".join(body_parts)

        extra: dict = {
            "rate_year": rate_year,
            "bah_lookup_url": BAH_RATE_URL,
        }
        if effective_date_str:
            extra["effective_date_text"] = effective_date_str

        try:
            pub_date = date(rate_year, 1, 1)
        except (ValueError, TypeError):
            pub_date = date.today()

        return [
            ScrapedArticle(
                headline=headline,
                published_date=pub_date,
                source_url=source_url,
                body_text=body_text,
                source_name="DoD BAH Rates",
                source_credibility="official",
                article_type="rate_table",
                extra_metadata=extra,
            )
        ]
