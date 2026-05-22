"""DFAS Military Basic Pay tables monitoring scraper.

Fetches the DFAS pay tables index page to detect when updated pay tables are
published for the current year.  Pay tables are updated annually (usually
January 1, tied to the National Defense Authorization Act) so this scraper is
a monitoring tool rather than a high-frequency data source.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Optional

from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

DFAS_PAY_TABLES_URL = (
    "https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/"
)

# Fallback: DFAS main military pay entitlements page
DFAS_PAY_FALLBACK_URL = (
    "https://www.dfas.mil/MilitaryMembers/payentitlements/"
)

# Informational reference for DoD FMR pay policy
DOD_PAY_POLICY_URL = (
    "https://comptroller.defense.gov/FMR/"
)


def _extract_year(text: str) -> Optional[int]:
    years = re.findall(r"\b(20\d{2})\b", text)
    return max(int(y) for y in years) if years else None


def _extract_effective_date(text: str) -> Optional[str]:
    patterns = [
        r"effective\s+((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+20\d{2})",
        r"effective\s+(\d{1,2}/\d{1,2}/20\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_pay_raise_percent(text: str) -> Optional[str]:
    """Extract annual pay raise percentage from page text."""
    patterns = [
        r"(\d+\.\d+)\s*%\s*(?:pay\s+raise|pay\s+increase|increase\s+in\s+pay)",
        r"(?:pay\s+raise|pay\s+increase)\s+of\s+(\d+\.\d+)\s*%",
        r"(\d+\.\d+)\s*percent\s+(?:pay\s+raise|pay\s+increase|increase)",
        r"ECI\D{0,20}?(\d+\.\d+)\s*%",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1) + "%"
    return None


class MilitaryPayScraper(BaseScraper):
    """Monitors DFAS for military basic pay table updates."""

    def get_source_id(self) -> str:
        return "military_pay"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()

        page_text: Optional[str] = None
        page_url_used = DFAS_PAY_TABLES_URL

        for url in (DFAS_PAY_TABLES_URL, DFAS_PAY_FALLBACK_URL):
            try:
                resp = self._fetch(url)
                page_text = resp.text
                page_url_used = url
                break
            except Exception as exc:
                logger.debug("military_pay: failed to fetch %r: %s", url, exc)

        if page_text is None:
            logger.warning("military_pay: all URLs failed, returning empty result")
            return ScrapeResult(
                source=self.get_source_id(),
                success=True,
                articles=[],
                error="DFAS pay table pages unavailable",
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
        pay_raise_pct = _extract_pay_raise_percent(clean_text)

        current_year = date.today().year
        rate_year = year or current_year

        headline_parts = [f"{rate_year} Military Basic Pay Tables"]
        if pay_raise_pct:
            headline_parts.append(f"({pay_raise_pct} Pay Raise)")
        headline = " ".join(headline_parts)

        body_parts = [
            f"DFAS has published the {rate_year} military basic pay tables.",
            "Basic pay is determined by an active duty service member's pay grade "
            "(rank) and years of service.",
        ]
        if effective_date_str:
            body_parts.append(f"The new pay rates are effective {effective_date_str}.")
        if pay_raise_pct:
            body_parts.append(
                f"Service members will see a {pay_raise_pct} increase in their "
                f"basic pay for {rate_year}."
            )
        body_parts.append(
            "Both officer and enlisted pay tables are available on the DFAS website. "
            "Service members should review their Leave and Earnings Statement (LES) "
            "to confirm the new rates are reflected in their pay."
        )
        body_text = " ".join(body_parts)

        extra: dict = {
            "rate_year": rate_year,
            "dfas_pay_tables_url": DFAS_PAY_TABLES_URL,
        }
        if effective_date_str:
            extra["effective_date_text"] = effective_date_str
        if pay_raise_pct:
            extra["pay_raise_percent"] = pay_raise_pct

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
                source_name="DFAS Military Pay",
                source_credibility="official",
                article_type="rate_table",
                extra_metadata=extra,
            )
        ]
