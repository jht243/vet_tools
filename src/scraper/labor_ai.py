"""
Labor & AI scraper — layoffs.fyi table + BLS employment news.

Sources:
  - layoffs.fyi: parse the public Google Sheets CSV export
  - BLS: news-release RSS for monthly employment situation reports
    (filter for AI/automation-related keywords in description)
"""
from __future__ import annotations

import csv
import io
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# Layoffs.fyi Google Sheets CSV export (public, no auth required).
_LAYOFFS_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1LErCaz4G0QF4xU9TMfzF5OBBdM9ssSuXAzHXWWV-1fA"
    "/export?format=csv&gid=0"
)

# BLS news-release RSS
_BLS_RSS = "https://www.bls.gov/feed/bls_latest.rss"

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

        articles += self._scrape_layoffs_fyi(cutoff)
        articles += self._scrape_bls(cutoff)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("LaborAIScraper: %d articles found (cutoff=%s)", len(articles), cutoff)
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    # ── layoffs.fyi ───────────────────────────────────────────────────

    def _scrape_layoffs_fyi(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        try:
            resp = self._fetch(_LAYOFFS_CSV_URL)
            reader = csv.DictReader(io.StringIO(resp.text))
        except Exception as exc:
            logger.warning("layoffs.fyi fetch failed: %s", exc)
            return out

        for row in reader:
            company = (row.get("Company") or "").strip()
            layoffs_raw = (row.get("Laid_Off_Count") or row.get("# Laid Off") or "").strip()
            date_raw = (row.get("Date") or "").strip()
            industry = (row.get("Industry") or "").strip()
            source_url = (row.get("Source") or "").strip()
            stage = (row.get("Stage") or "").strip()

            pub_date = _parse_flexible_date(date_raw)
            if not pub_date or pub_date < cutoff:
                continue

            combined = (company + " " + industry + " " + stage).lower()
            if not any(kw in combined for kw in _AI_LABOR_KEYWORDS):
                continue

            count_str = f", {layoffs_raw} jobs" if layoffs_raw and layoffs_raw.isdigit() else ""
            headline = f"{company} layoffs{count_str} ({industry})"

            out.append(ScrapedArticle(
                headline=headline,
                published_date=pub_date,
                source_url=source_url or "https://layoffs.fyi",
                body_text=(
                    f"{company} laid off {layoffs_raw or 'an undisclosed number of'} workers"
                    f" in the {industry} sector{(' (' + stage + ')') if stage else ''}."
                ),
                source_name="layoffs.fyi",
                source_credibility="tier2",
                article_type="news",
                extra_metadata={
                    "company": company,
                    "layoff_count": layoffs_raw,
                    "industry": industry,
                },
            ))

        logger.info("layoffs.fyi: %d AI-related layoff events", len(out))
        return out

    # ── BLS ───────────────────────────────────────────────────────────

    def _scrape_bls(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        try:
            resp = self._fetch(_BLS_RSS)
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning("BLS RSS fetch failed: %s", exc)
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
            if not any(kw in combined for kw in _AI_LABOR_KEYWORDS):
                continue

            out.append(ScrapedArticle(
                headline=f"BLS: {title}",
                published_date=pub_date or date.today(),
                source_url=link,
                body_text=desc,
                source_name="BLS",
                source_credibility="official",
                article_type="report",
                extra_metadata={"agency": "BLS"},
            ))

        logger.info("BLS: %d AI/labor items", len(out))
        return out


# ── Date parsing helpers ──────────────────────────────────────────────

def _parse_flexible_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_rfc2822(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(raw[:31], fmt).date()
        except ValueError:
            continue
    return None
