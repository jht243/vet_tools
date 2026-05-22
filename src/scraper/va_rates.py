"""VA disability compensation rates monitoring scraper.

Fetches the VA.gov compensation rates index page and parses the current year's
effective date and COLA percentage.  Because rates only change once per year
(typically December/January), this scraper is primarily a monitoring tool that
fires an article whenever new rate data is detected.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

VA_RATES_URL = "https://www.benefits.va.gov/compensation/rates-index.asp"


def _extract_year(text: str) -> Optional[int]:
    """Find the most recent 4-digit year mentioned in the page text."""
    years = re.findall(r"\b(20\d{2})\b", text)
    if not years:
        return None
    return max(int(y) for y in years)


def _extract_effective_date(text: str) -> Optional[str]:
    """Extract text like 'effective December 1, 2024' or 'effective 12/1/2024'."""
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


def _extract_cola_percent(text: str) -> Optional[str]:
    """Extract COLA percentage like '3.2%' near 'COLA' or 'cost-of-living'."""
    m = re.search(
        r"(?:COLA|cost.of.living)\D{0,40}?(\d+\.\d+)\s*%",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1) + "%"
    # Broader: any percentage near rate/adjustment language
    m = re.search(
        r"(\d+\.\d+)\s*%\s*(?:COLA|increase|adjustment)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1) + "%"
    return None


class VARatesScraper(BaseScraper):
    """Monitors VA.gov for disability compensation rate updates."""

    def get_source_id(self) -> str:
        return "va_rates"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()

        try:
            resp = self._fetch(VA_RATES_URL)
            page_text = resp.text
        except Exception as exc:
            logger.warning("va_rates: failed to fetch rates page: %s", exc)
            return ScrapeResult(
                source=self.get_source_id(),
                success=True,
                articles=[],
                error=str(exc),
                duration_seconds=int(time.monotonic() - start),
            )

        articles = self._parse_rates_page(page_text)

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    def _parse_rates_page(self, page_text: str) -> list[ScrapedArticle]:
        # Strip HTML for text analysis
        clean_text = re.sub(r"<[^>]+>", " ", page_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        year = _extract_year(clean_text)
        effective_date_str = _extract_effective_date(clean_text)
        cola_pct = _extract_cola_percent(clean_text)

        current_year = date.today().year
        rate_year = year or current_year

        headline_parts = [f"{rate_year} VA Disability Compensation Rates"]
        if cola_pct:
            headline_parts.append(f"({cola_pct} COLA Adjustment)")
        headline = " ".join(headline_parts)

        body_parts = [
            f"VA disability compensation rates for {rate_year} are available on VA.gov.",
        ]
        if effective_date_str:
            body_parts.append(f"Rates are effective {effective_date_str}.")
        if cola_pct:
            body_parts.append(
                f"The cost-of-living adjustment (COLA) for {rate_year} is {cola_pct}."
            )
        body_parts.append(
            "Veterans should review the updated rates to understand how their "
            "monthly compensation may have changed."
        )
        body_text = " ".join(body_parts)

        extra: dict = {
            "rate_year": rate_year,
        }
        if effective_date_str:
            extra["effective_date_text"] = effective_date_str
        if cola_pct:
            extra["cola_percent"] = cola_pct

        # Use January 1 of the rate year as the canonical published date
        try:
            pub_date = date(rate_year, 1, 1)
        except (ValueError, TypeError):
            pub_date = date.today()

        return [
            ScrapedArticle(
                headline=headline,
                published_date=pub_date,
                source_url=VA_RATES_URL,
                body_text=body_text,
                source_name="VA.gov Rates",
                source_credibility="official",
                article_type="rate_table",
                extra_metadata=extra,
            )
        ]
