"""
Search Engine Journal / Search Engine Land scraper.

Covers AI content quality, AI-generated SEO spam, Google algorithm
updates penalizing AI slop, and related search-industry coverage.
These feed the content_quality and backlash_protest angles.
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
    # (rss_url, source_name, credibility)
    ("https://searchengineland.com/feed", "Search Engine Land", "tier1"),
    ("https://www.searchenginejournal.com/feed/", "Search Engine Journal", "tier1"),
    ("https://www.seroundtable.com/feed", "SE Roundtable", "tier2"),
]

_SEJ_KEYWORDS = {
    "ai content", "ai-generated", "ai slop", "ai spam",
    "google algorithm", "helpful content", "content quality",
    "ai detection", "synthetic content", "llm content",
    "ai writing", "chatgpt seo", "generative ai seo",
    "core update", "spam update", "anti-ai",
    "human-made", "human-written", "no ai",
    "ai backlash", "ai disclosure",
}


class SEJAlgoScraper(BaseScraper):
    """Fetches AI content-quality / algorithm news from SEL and SEJ."""

    def get_source_id(self) -> str:
        return "sej_algo"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []
        seen: set[str] = set()

        lookback = timedelta(days=settings.scraper_lookback_days)
        cutoff = (target_date or date.today()) - lookback

        for feed_url, source_name, credibility in _FEEDS:
            for article in self._scrape_rss(feed_url, source_name, credibility, cutoff):
                if article.source_url not in seen:
                    seen.add(article.source_url)
                    articles.append(article)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("SEJAlgoScraper: %d articles found (cutoff=%s)", len(articles), cutoff)
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

            # Some feeds wrap description in CDATA — ET handles that,
            # but strip residual HTML tags for scoring.
            desc_clean = _strip_tags(desc)

            pub_date = _parse_rfc2822(pub_raw)
            if pub_date and pub_date < cutoff:
                continue

            combined = (title + " " + desc_clean).lower()
            if not any(kw in combined for kw in _SEJ_KEYWORDS):
                continue

            out.append(ScrapedArticle(
                headline=title,
                published_date=pub_date or date.today(),
                source_url=link,
                body_text=desc_clean[:600],
                source_name=source_name,
                source_credibility=credibility,
                article_type="news",
                extra_metadata={"topic": "content_quality"},
            ))

        logger.info("%s: %d AI/algo items", source_name, len(out))
        return out


import re as _re
_TAG_RE = _re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html).strip()


def _parse_rfc2822(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(raw[:31], fmt).date()
        except ValueError:
            continue
    return None
