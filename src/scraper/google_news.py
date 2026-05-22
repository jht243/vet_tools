"""Google News RSS scraper for VA/military benefits topics.

Queries the Google News RSS endpoint for each configured search term,
de-duplicates by URL, and returns ScrapedArticle objects ranked by
source credibility.
"""
from __future__ import annotations

import html
import logging
import re
import ssl
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus

import httpx

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

QUERIES: tuple[str, ...] = (
    '"veterans benefits" OR "VA disability" OR "VA claims"',
    '"VA backlog" OR "veterans affairs" policy changes',
    '"PACT Act" OR "burn pit" OR "toxic exposure" veterans',
    '"military pay" OR "BAH" OR "military retirement" 2024 OR 2025',
    '"government shutdown" military pay OR veterans benefits',
    '"veterans legislation" OR "armed services committee" veterans',
    '"VA disability rating" OR "disability compensation" veterans',
    '"military benefits" changes OR updates 2025',
)

HIGH_CREDIBILITY: frozenset[str] = frozenset(
    {
        "reuters.com",
        "apnews.com",
        "militarytimes.com",
        "stripes.com",
        "military.com",
        "defense.gov",
        "va.gov",
        "congress.gov",
        "govtrack.us",
        "rollcall.com",
        "thehill.com",
        "politico.com",
        "cnn.com",
        "usatoday.com",
        "pbs.org",
    }
)

# Publisher display-name → canonical domain (for credibility lookup)
_PUBLISHER_ALIASES: dict[str, str] = {
    "military times": "militarytimes.com",
    "stars and stripes": "stripes.com",
    "stars & stripes": "stripes.com",
    "defense.gov": "defense.gov",
    "va.gov": "va.gov",
    "the hill": "thehill.com",
    "politico": "politico.com",
    "roll call": "rollcall.com",
    "associated press": "apnews.com",
    "ap": "apnews.com",
    "reuters": "reuters.com",
    "cnn": "cnn.com",
    "pbs newshour": "pbs.org",
    "usa today": "usatoday.com",
}

# Google News RSS base URL
_GN_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

MAX_TOTAL_WALLCLOCK_SECONDS: int = 90
PER_QUERY_MAX_ATTEMPTS: int = 2


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_rfc822(date_str: str) -> Optional[date]:
    """Parse an RFC-822 date string to a date, returning None on failure."""
    try:
        dt = parsedate_to_datetime(date_str)
        # Normalise to UTC then extract the date component
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.date()
    except Exception:
        return None


def _domain_from_url(url: str) -> str:
    """Extract the bare domain (no www.) from a URL."""
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1).lower() if m else ""


def _credibility_for(source_url: str, publisher_name: str) -> str:
    domain = _domain_from_url(source_url)
    if domain in HIGH_CREDIBILITY:
        return "tier1"
    # Try publisher alias lookup
    alias_key = publisher_name.lower().strip()
    aliased = _PUBLISHER_ALIASES.get(alias_key)
    if aliased and aliased in HIGH_CREDIBILITY:
        return "tier1"
    return "tier2"


class GoogleNewsScraper(BaseScraper):
    """Scrapes Google News RSS for military/VA benefits topics."""

    def get_source_id(self) -> str:
        return "google_news"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        cutoff = date.today() - timedelta(days=settings.scraper_lookback_days)

        for query in QUERIES:
            if time.monotonic() - start > MAX_TOTAL_WALLCLOCK_SECONDS:
                logger.warning("google_news: hit wall-clock budget, stopping early")
                break
            try:
                new_articles = self._query_articles(
                    query, cutoff, seen_urls, target_date
                )
                articles.extend(new_articles)
            except Exception as exc:
                logger.warning("google_news: query %r failed: %s", query, exc)
                continue

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    def _query_articles(
        self,
        query: str,
        cutoff: date,
        seen_urls: set[str],
        target_date: Optional[date],
    ) -> list[ScrapedArticle]:
        url = _GN_RSS.format(query=quote_plus(query))

        attempts = 0
        resp = None
        last_exc: Optional[Exception] = None

        while attempts < PER_QUERY_MAX_ATTEMPTS:
            attempts += 1
            try:
                resp = self._fetch_ssl_resilient(url)
                break
            except Exception as exc:
                last_exc = exc
                logger.debug(
                    "google_news: fetch attempt %d/%d failed for query %r: %s",
                    attempts,
                    PER_QUERY_MAX_ATTEMPTS,
                    query,
                    exc,
                )

        if resp is None:
            raise last_exc or RuntimeError("no response")

        return self._parse_feed(resp.text, cutoff, seen_urls, target_date)

    def _fetch_ssl_resilient(self, url: str) -> httpx.Response:
        """Attempt normal fetch; on SSL error, retry with relaxed verification."""
        try:
            return self._fetch(url)
        except httpx.ConnectError as exc:
            if "SSL" in str(exc) or "certificate" in str(exc).lower():
                logger.debug("google_news: SSL error, retrying without verify")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                resp = self.client.get(url, extensions={"ssl_context": ctx})
                resp.raise_for_status()
                return resp
            raise

    def _parse_feed(
        self,
        xml_text: str,
        cutoff: date,
        seen_urls: set[str],
        target_date: Optional[date],
    ) -> list[ScrapedArticle]:
        import xml.etree.ElementTree as ET

        articles: list[ScrapedArticle] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("google_news: XML parse error: %s", exc)
            return articles

        ns = {"media": "http://search.yahoo.com/mrss/"}
        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
            article = self._parse_item(item, ns, cutoff, seen_urls, target_date)
            if article is not None:
                articles.append(article)

        return articles

    def _parse_item(
        self,
        item,
        ns: dict,
        cutoff: date,
        seen_urls: set[str],
        target_date: Optional[date],
    ) -> Optional[ScrapedArticle]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        desc_el = item.find("description")
        source_el = item.find("source")

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
            pub_date = _parse_rfc822(pub_date_el.text)
        if pub_date is None:
            pub_date = date.today()

        if pub_date < cutoff:
            return None

        if target_date is not None and pub_date != target_date:
            return None

        publisher_name = ""
        if source_el is not None:
            publisher_name = (source_el.text or "").strip()

        body_text: Optional[str] = None
        if desc_el is not None and desc_el.text:
            body_text = _strip_html(desc_el.text).strip() or None

        credibility = _credibility_for(source_url, publisher_name)

        seen_urls.add(source_url)

        return ScrapedArticle(
            headline=headline,
            published_date=pub_date,
            source_url=source_url,
            body_text=body_text,
            source_name="Google News",
            source_credibility=credibility,
            article_type="news",
            extra_metadata={"publisher": publisher_name},
        )
