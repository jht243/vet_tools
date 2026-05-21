"""
Regulatory AI scraper — FTC press releases, EU AI Act news feed, and
US Congress AI-related bill tracker.

Sources:
  - FTC: RSS feed for news/press-releases (filter for AI keywords)
  - Congress API: api.congress.gov/v3/bill filtered for AI subject matter
  - EU AI Act: EUR-Lex RSS for regulation 2024/1689
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# FTC AI-related keywords — article must contain at least one.
_FTC_KEYWORDS = {
    "artificial intelligence", "ai", "algorithm", "automated",
    "machine learning", "chatbot", "deepfake", "generative",
}

# Congress search query — returns bills with AI-related policy area.
_CONGRESS_SEARCH_QUERY = "artificial intelligence"

_FTC_RSS = "https://www.ftc.gov/feeds/press-release-list.xml"
_EU_AIACT_RSS = "https://eur-lex.europa.eu/legal-content/EN/rss.xml?type=OJ&ojYear=2024"
_CONGRESS_API = "https://api.congress.gov/v3/bill"


class RegulatoryAIScraper(BaseScraper):
    """Aggregates regulatory AI signals from FTC, Congress, and EUR-Lex."""

    def get_source_id(self) -> str:
        return "regulatory_ai"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []

        lookback = timedelta(days=settings.scraper_lookback_days)
        cutoff = (target_date or date.today()) - lookback

        articles += self._scrape_ftc(cutoff)
        articles += self._scrape_congress(cutoff)
        articles += self._scrape_eu_aiact(cutoff)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info(
            "RegulatoryAIScraper: %d articles found (cutoff=%s)",
            len(articles),
            cutoff,
        )
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    # ── FTC ───────────────────────────────────────────────────────────

    def _scrape_ftc(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        try:
            resp = self._fetch(_FTC_RSS)
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning("FTC RSS fetch failed: %s", exc)
            return out

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_raw = (item.findtext("pubDate") or "").strip()
            desc = (item.findtext("description") or "").strip()

            pub_date = _parse_rfc2822(pub_date_raw)
            if pub_date and pub_date < cutoff:
                continue

            combined = (title + " " + desc).lower()
            if not any(kw in combined for kw in _FTC_KEYWORDS):
                continue

            out.append(ScrapedArticle(
                headline=title,
                published_date=pub_date or date.today(),
                source_url=link,
                body_text=desc,
                source_name="FTC",
                source_credibility="official",
                article_type="regulatory",
                extra_metadata={"regulator": "FTC"},
            ))

        logger.info("FTC: %d AI-related items", len(out))
        return out

    # ── Congress.gov API ──────────────────────────────────────────────

    def _scrape_congress(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        api_key = getattr(settings, "congress_api_key", None) or ""
        if not api_key:
            logger.debug("CONGRESS_API_KEY not set — skipping Congress scraper")
            return out

        params: dict = {
            "query": _CONGRESS_SEARCH_QUERY,
            "sort": "updateDate+desc",
            "limit": "20",
            "api_key": api_key,
        }
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{_CONGRESS_API}?{param_str}"

        try:
            resp = self._fetch(url)
            data = resp.json()
        except Exception as exc:
            logger.warning("Congress API fetch failed: %s", exc)
            return out

        for bill in (data.get("bills") or []):
            title = (bill.get("title") or bill.get("shortTitle") or "").strip()
            if not title:
                continue
            updated_raw = bill.get("updateDate") or ""
            updated = _parse_iso_date(updated_raw)
            if updated and updated < cutoff:
                continue

            congress = bill.get("congress", "")
            bill_type = bill.get("type", "").lower()
            number = bill.get("number", "")
            url_path = f"https://www.congress.gov/{congress}/bills/{bill_type}{number}"

            out.append(ScrapedArticle(
                headline=f"US Congress: {title}",
                published_date=updated or date.today(),
                source_url=url_path,
                body_text=title,
                source_name="Congress.gov",
                source_credibility="official",
                article_type="regulatory",
                extra_metadata={"bill_type": bill_type, "congress": congress},
            ))

        logger.info("Congress API: %d AI-related bills", len(out))
        return out

    # ── EUR-Lex EU AI Act ─────────────────────────────────────────────

    def _scrape_eu_aiact(self, cutoff: date) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        _EU_AIACT_KEYWORDS = {
            "artificial intelligence", "ai act", "regulation 2024/1689",
            "high-risk ai", "prohibited ai",
        }
        try:
            resp = self._fetch(_EU_AIACT_RSS)
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning("EUR-Lex RSS fetch failed: %s", exc)
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
            if not any(kw in combined for kw in _EU_AIACT_KEYWORDS):
                continue

            out.append(ScrapedArticle(
                headline=f"EU AI Act: {title}",
                published_date=pub_date or date.today(),
                source_url=link,
                body_text=desc,
                source_name="EUR-Lex",
                source_credibility="official",
                article_type="regulatory",
                extra_metadata={"regulator": "EU"},
            ))

        logger.info("EUR-Lex: %d AI Act items", len(out))
        return out


# ── Date parsing helpers ──────────────────────────────────────────────

def _parse_rfc2822(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
    ):
        try:
            return datetime.strptime(raw[:31], fmt).date()
        except ValueError:
            continue
    return None


def _parse_iso_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None
