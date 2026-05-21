"""
Energy & AI scraper — DOE EERE news RSS and IEA news RSS.

Filters for AI data-center energy and water-use coverage.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

_FEEDS: list[tuple[str, str, str]] = [
    # (url, source_name, credibility)
    ("https://www.energy.gov/eere/articles/feed", "DOE EERE", "official"),
    ("https://www.iea.org/news.xml", "IEA", "official"),
    ("https://www.datacenterknowledge.com/feed", "Data Center Knowledge", "tier1"),
    ("https://www.theregister.com/headlines/ai_and_ml/", "The Register", "tier2"),
]

_ENERGY_KEYWORDS = {
    "data center", "data centre", "ai energy", "ai water",
    "artificial intelligence energy", "gpu power", "hyperscaler",
    "cooling water", "carbon footprint ai", "ai electricity",
    "power consumption ai", "renewable energy ai",
    "microsoft data center", "google data center", "amazon data center",
    "nvidia power", "ai infrastructure",
}


class EnergyAIScraper(BaseScraper):
    """Aggregates AI energy and water-use news."""

    def get_source_id(self) -> str:
        return "energy_ai"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []

        lookback = timedelta(days=settings.scraper_lookback_days)
        cutoff = (target_date or date.today()) - lookback

        for feed_url, source_name, credibility in _FEEDS:
            articles += self._scrape_rss(feed_url, source_name, credibility, cutoff)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("EnergyAIScraper: %d articles found (cutoff=%s)", len(articles), cutoff)
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    def _scrape_rss(
        self,
        url: str,
        source_name: str,
        credibility: str,
        cutoff: date,
    ) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        try:
            resp = self._fetch(url)
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning("%s RSS fetch failed: %s", source_name, exc)
            return out

        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = (item.findtext("pubDate") or "").strip()
            desc = (item.findtext("description") or "").strip()

            pub_date = _parse_rfc2822(pub_raw)
            if pub_date and pub_date < cutoff:
                continue

            combined = (title + " " + desc).lower()
            if not any(kw in combined for kw in _ENERGY_KEYWORDS):
                continue

            out.append(ScrapedArticle(
                headline=title,
                published_date=pub_date or date.today(),
                source_url=link,
                body_text=desc,
                source_name=source_name,
                source_credibility=credibility,
                article_type="news",
                extra_metadata={"topic": "energy_ai"},
            ))

        logger.info("%s: %d AI energy/water items", source_name, len(out))
        return out


def _parse_rfc2822(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(raw[:31], fmt).date()
        except ValueError:
            continue
    return None
