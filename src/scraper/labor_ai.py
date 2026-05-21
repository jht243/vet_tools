"""
Labor & AI scraper — layoffs.fyi table + BLS employment news.

Sources:
  - layoffs.fyi: parse the public Google Sheets CSV export
  - BLS: news-release RSS for monthly employment situation reports
    (filter for AI/automation-related keywords in description)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# RSS feeds covering AI layoffs and workforce displacement.
# layoffs.fyi Google Sheets export is no longer public; BLS blocks scrapers.
_LABOR_FEEDS: list[tuple[str, str, str]] = [
    # TechCrunch layoffs tag — direct layoff news with company + count
    ("https://techcrunch.com/tag/layoffs/feed/", "TechCrunch Layoffs", "tier1"),
    # MIT Technology Review — authoritative AI/labor economics coverage
    ("https://www.technologyreview.com/feed/", "MIT Technology Review", "tier1"),
    # Ars Technica — strong AI jobs and automation coverage
    ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica", "tier2"),
]

_AI_LABOR_KEYWORDS = {
    "artificial intelligence", "ai", "automation", "machine learning",
    "robot", "autonomous", "tech layoffs", "workforce reduction",
    "job displacement", "algorithm",
}


class LaborAIScraper(BaseScraper):
    """Aggregates labor/AI displacement signals."""

    def get_source_id(self) -> str:
        return "labor_ai"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []

        lookback = timedelta(days=settings.scraper_lookback_days)
        cutoff = (target_date or date.today()) - lookback

        articles += self._scrape_labor_feeds(cutoff)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("LaborAIScraper: %d articles found (cutoff=%s)", len(articles), cutoff)
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    # ── Labor RSS feeds ────────────────────────────────────────────────

    def _scrape_labor_feeds(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        for feed_url, source_name, credibility in _LABOR_FEEDS:
            try:
                resp = self._fetch(feed_url)
                root = ET.fromstring(resp.text)
            except Exception as exc:
                logger.warning("%s fetch failed: %s", source_name, exc)
                continue

            feed_count = 0
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_raw = (item.findtext("pubDate") or "").strip()
                desc = (item.findtext("description") or "").strip()

                pub_date = _parse_rfc2822(pub_raw)
                if pub_date and pub_date < cutoff:
                    continue

                combined = (title + " " + desc).lower()
                if not any(kw in combined for kw in _AI_LABOR_KEYWORDS):
                    continue

                out.append(ScrapedArticle(
                    headline=title,
                    published_date=pub_date or date.today(),
                    source_url=link,
                    body_text=desc[:600],
                    source_name=source_name,
                    source_credibility=credibility,
                    article_type="news",
                    extra_metadata={"topic": "jobs_labor"},
                ))
                feed_count += 1

            logger.info("%s: %d AI-labor items", source_name, feed_count)
        return out


# ── Date parsing helpers ──────────────────────────────────────────────

def _parse_rfc2822(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(raw[:31], fmt).date()
        except ValueError:
            continue
    return None
