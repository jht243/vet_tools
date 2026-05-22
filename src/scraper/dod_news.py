"""DoD News RSS scraper.

Fetches the defense.gov news RSS feed and returns articles published within the
configured lookback window.  A keyword filter surfaces pay/benefits/personnel
content, but all articles are returned (the LLM analysis step decides final
relevance).
"""
from __future__ import annotations

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

DOD_NEWS_RSS_PRIMARY = (
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx"
    "?max=10&ContentType=1&Site=945&Item=0"
)
DOD_NEWS_RSS_FALLBACK = "https://www.defense.gov/News/RSS/"

# Keywords that make an article especially likely to be veteran/pay relevant.
# Used to tag articles in extra_metadata; not used to filter them out.
BENEFITS_KEYWORDS: frozenset[str] = frozenset(
    {
        "pay",
        "benefit",
        "retirement",
        "bah",
        "allowance",
        "compensation",
        "veteran",
        "service member",
        "servicemember",
        "personnel",
        "policy",
        "budget",
        "appropriat",
        "cola",
        "disability",
        "tricare",
        "healthcare",
        "housing",
        "education",
        "gi bill",
    }
)


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_pub_date(date_str: str) -> Optional[date]:
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date()
    except Exception:
        return None


def _has_benefits_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in BENEFITS_KEYWORDS)


class DoDNewsScraper(BaseScraper):
    """Fetches DoD defense.gov news RSS feed."""

    def get_source_id(self) -> str:
        return "dod_news"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []

        cutoff = date.today() - timedelta(days=settings.scraper_lookback_days)

        feed_xml: Optional[str] = None
        feed_url_used = DOD_NEWS_RSS_PRIMARY

        # Try primary feed, fall back to secondary
        for feed_url in (DOD_NEWS_RSS_PRIMARY, DOD_NEWS_RSS_FALLBACK):
            try:
                resp = self._fetch(feed_url)
                feed_xml = resp.text
                feed_url_used = feed_url
                break
            except Exception as exc:
                logger.debug("dod_news: feed %r failed: %s", feed_url, exc)

        if feed_xml is None:
            logger.warning("dod_news: all feeds failed, returning empty result")
            return ScrapeResult(
                source=self.get_source_id(),
                success=True,
                articles=[],
                error="all RSS feeds unavailable",
                duration_seconds=int(time.monotonic() - start),
            )

        try:
            articles = self._parse_feed(feed_xml, cutoff, target_date)
        except Exception as exc:
            logger.warning("dod_news: parse error from %r: %s", feed_url_used, exc)
            return ScrapeResult(
                source=self.get_source_id(),
                success=True,
                articles=[],
                error=str(exc),
                duration_seconds=int(time.monotonic() - start),
            )

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    def _parse_feed(
        self,
        xml_text: str,
        cutoff: date,
        target_date: Optional[date],
    ) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("dod_news: XML parse error: %s", exc)
            return articles

        channel = root.find("channel")
        if channel is None:
            # Some Atom-style feeds use feed/entry instead
            items = root.findall("item") or root.findall("entry")
        else:
            items = channel.findall("item")

        for item in items:
            article = self._parse_item(item, cutoff, target_date)
            if article is not None:
                articles.append(article)

        return articles

    def _parse_item(
        self,
        item: ET.Element,
        cutoff: date,
        target_date: Optional[date],
    ) -> Optional[ScrapedArticle]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        desc_el = item.find("description")

        if title_el is None:
            return None

        headline = _strip_html(title_el.text or "").strip()
        source_url = (link_el.text or "").strip() if link_el is not None else ""

        # Atom-style <link href="...">
        if not source_url and link_el is not None:
            source_url = link_el.get("href", "").strip()

        if not source_url:
            guid_el = item.find("guid")
            if guid_el is not None:
                source_url = (guid_el.text or "").strip()

        if not headline or not source_url:
            return None

        pub_date: Optional[date] = None
        if pub_date_el is not None and pub_date_el.text:
            pub_date = _parse_pub_date(pub_date_el.text)
        if pub_date is None:
            pub_date = date.today()

        if pub_date < cutoff:
            return None

        if target_date is not None and pub_date != target_date:
            return None

        body_text: Optional[str] = None
        if desc_el is not None and desc_el.text:
            body_text = _strip_html(desc_el.text).strip() or None

        # Tag whether this article contains pay/benefits keywords
        combined_text = f"{headline} {body_text or ''}"
        is_benefits_related = _has_benefits_keyword(combined_text)

        return ScrapedArticle(
            headline=headline,
            published_date=pub_date,
            source_url=source_url,
            body_text=body_text,
            source_name="DoD News",
            source_credibility="official",
            article_type="news",
            extra_metadata={"benefits_related": is_benefits_related},
        )
