"""Congress.gov legislation scraper for veterans/military bills.

Uses the Congress.gov public RSS feed for recent legislation and filters by
keywords relevant to veterans, VA benefits, military pay, and related topics.
The RSS feed requires no API key and is updated daily.
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

# Congress.gov RSS — recent legislation (no API key required)
CONGRESS_RSS_URLS: tuple[tuple[str, str], ...] = (
    (
        "https://www.congress.gov/rss/legislation.xml",
        "Congress.gov",
    ),
)

# GovTrack RSS for bills matching veterans/military terms
GOVTRACK_RSS_URLS: tuple[tuple[str, str], ...] = (
    (
        "https://www.govtrack.us/events/govtrack.rss"
        "?feeds=bill:s&terms=veterans,disability,military+pay&count=20",
        "GovTrack",
    ),
    (
        "https://www.govtrack.us/events/govtrack.rss"
        "?feeds=bill:h&terms=veterans,disability,military+pay&count=20",
        "GovTrack",
    ),
)

# Keywords to filter/tag legislation as veterans/military relevant
VETERAN_KEYWORDS: frozenset[str] = frozenset(
    {
        "veteran",
        "va ",
        "department of veterans",
        "disability",
        "military pay",
        "armed forces",
        "service member",
        "servicemember",
        "pact act",
        "burn pit",
        "toxic exposure",
        "gi bill",
        "tricare",
        "military retirement",
        "uniformed services",
        "national guard",
        "reserve",
        "bah",
        "basic allowance",
        "veterans affairs",
        "vba",
        "combat",
        "survivor benefit",
        "commissary",
        "military housing",
        "dfas",
        "active duty",
        "honorable discharge",
    }
)

# Relevant congressional committees (used to tag articles)
RELEVANT_COMMITTEES: frozenset[str] = frozenset(
    {
        "Veterans' Affairs",
        "Veterans Affairs",
        "Armed Services",
        "Defense",
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
        # Try ISO format
        try:
            return date.fromisoformat(date_str[:10])
        except Exception:
            return None


def _is_veteran_related(headline: str, description: str) -> bool:
    combined = f"{headline} {description}".lower()
    return any(kw.lower() in combined for kw in VETERAN_KEYWORDS)


class CongressVAScraper(BaseScraper):
    """Scrapes Congress.gov and GovTrack RSS for veteran/military legislation."""

    def get_source_id(self) -> str:
        return "congress_va"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        cutoff = date.today() - timedelta(days=settings.scraper_lookback_days)

        all_feeds = list(CONGRESS_RSS_URLS) + list(GOVTRACK_RSS_URLS)

        for feed_url, feed_label in all_feeds:
            try:
                resp = self._fetch(feed_url)
                new_articles = self._parse_feed(
                    resp.text, cutoff, seen_urls, target_date, source_label=feed_label
                )
                articles.extend(new_articles)
            except Exception as exc:
                logger.warning(
                    "congress_va: feed %r (%s) failed: %s", feed_url, feed_label, exc
                )
                continue

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
        seen_urls: set[str],
        target_date: Optional[date],
        source_label: str = "Congress.gov",
    ) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("congress_va: XML parse error from %s: %s", source_label, exc)
            return articles

        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
            article = self._parse_item(
                item, cutoff, seen_urls, target_date, source_label
            )
            if article is not None:
                articles.append(article)

        return articles

    def _parse_item(
        self,
        item: ET.Element,
        cutoff: date,
        seen_urls: set[str],
        target_date: Optional[date],
        source_label: str,
    ) -> Optional[ScrapedArticle]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        desc_el = item.find("description")

        if title_el is None or link_el is None:
            return None

        headline = _strip_html(title_el.text or "").strip()
        source_url = (link_el.text or "").strip()

        if not headline or not source_url:
            return None

        if source_url in seen_urls:
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

        description = ""
        if desc_el is not None and desc_el.text:
            description = _strip_html(desc_el.text).strip()

        # Filter: only include if the bill title or description is veteran/military related
        if not _is_veteran_related(headline, description):
            return None

        seen_urls.add(source_url)

        return ScrapedArticle(
            headline=headline,
            published_date=pub_date,
            source_url=source_url,
            body_text=description or None,
            source_name="Congress.gov",
            source_credibility="official",
            article_type="legislation",
            extra_metadata={"feed_source": source_label},
        )
