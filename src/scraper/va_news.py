"""VA.gov News RSS scraper.

Fetches the VA News RSS feed and returns press releases published within the
configured lookback window.
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

VA_NEWS_RSS = "https://news.va.gov/feed/"


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


class VANewsScraper(BaseScraper):
    """Fetches VA.gov News RSS feed press releases."""

    def get_source_id(self) -> str:
        return "va_news"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []

        cutoff = date.today() - timedelta(days=settings.scraper_lookback_days)

        try:
            resp = self._fetch(VA_NEWS_RSS)
            articles = self._parse_feed(resp.text, cutoff, target_date)
        except Exception as exc:
            logger.warning("va_news: failed to fetch or parse feed: %s", exc)
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
            logger.warning("va_news: XML parse error: %s", exc)
            return articles

        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
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

        if title_el is None or link_el is None:
            return None

        headline = _strip_html(title_el.text or "").strip()
        # <link> in RSS 2.0 is sometimes a text node, sometimes the next sibling
        source_url = (link_el.text or "").strip()
        if not source_url:
            # Try the <guid> element as a fallback URL
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

        return ScrapedArticle(
            headline=headline,
            published_date=pub_date,
            source_url=source_url,
            body_text=body_text,
            source_name="VA.gov News",
            source_credibility="official",
            article_type="press_release",
            extra_metadata={},
        )
