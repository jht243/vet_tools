"""Congressional coverage scraper for veterans/military legislation.

Two source tiers (both attempted every run):

  Tier 1 — Congress.gov REST API  (requires free key → CONGRESS_API_KEY env var)
            https://api.congress.gov/sign-up/
            Returns rich committee/status metadata for the 119th Congress.
            Filters to bills assigned to VA or Armed Services committees.

  Tier 2 — GovInfo.gov bills RSS  (no auth required, always runs)
            https://www.govinfo.gov/rss/bills.xml
            Returns the 100 most recently published congressional bills.
            Keyword-filtered to veteran/military topics.

Both sources deduplicate by URL before returning.
"""
from __future__ import annotations

import html as _html_module
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlencode

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

CONGRESS_API_BASE = "https://api.congress.gov/v3"
GOVINFO_BILLS_RSS  = "https://www.govinfo.gov/rss/bills.xml"

# VA / Armed Services committee system codes used by the Congress.gov API
VETERAN_COMMITTEE_CODES = {
    "SSVA",   # Senate Veterans' Affairs
    "HVVA",   # House Veterans' Affairs
    "SSAS",   # Senate Armed Services
    "HSAS",   # House Armed Services
}

# Broad keyword list — must match against headline (and body if available)
VETERAN_KEYWORDS: frozenset[str] = frozenset({
    "veteran", "veterans",
    "va ", " va.", "department of veterans",
    "military",
    "armed forces", "armed services",
    "service member", "servicemember",
    "active duty", "active-duty",
    "national guard", "reservist",
    "pact act", "burn pit", "toxic exposure",
    "gi bill", "post-9/11", "post 9/11",
    "tricare",
    "military retirement", "blended retirement",
    "military pay", "basic allowance", "bah ", "bas ",
    "uniformed services",
    "combat", "deployment",
    "survivor benefit", "sbp ",
    "dfas",
    "vba ", "vso ",
    "title 38", "38 usc", "38 u.s.c",
    "disability compensation", "disability rating",
    "concurrent receipt", "crsc", "crdp",
    "commissary", "exchange benefit",
    "military housing",
    "war power",         # War Powers Resolution matters to service members
    "appropriations for military",
})


def _clean_title(raw: str) -> str:
    """Normalize GovInfo bill titles (strip HTML entities, collapse whitespace)."""
    text = _html_module.unescape(raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_rss_date(date_str: str) -> Optional[date]:
    for parser in (
        lambda s: parsedate_to_datetime(s).date(),
        lambda s: date.fromisoformat(s[:10]),
    ):
        try:
            return parser(date_str)
        except Exception:
            continue
    return None


def _is_veteran_related(headline: str, body: str = "") -> bool:
    combined = f"{headline} {body}".lower()
    return any(kw in combined for kw in VETERAN_KEYWORDS)


class CongressVAScraper(BaseScraper):
    """Scrapes Congress.gov API + GovInfo bills RSS for veteran/military legislation."""

    def get_source_id(self) -> str:
        return "congress_va"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = time.monotonic()
        articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()
        cutoff = date.today() - timedelta(days=settings.scraper_lookback_days)

        # ── Tier 1: Congress.gov API ──────────────────────────────────────────
        if settings.congress_api_key:
            try:
                api_arts = self._fetch_congress_api(cutoff, seen_urls)
                articles.extend(api_arts)
                logger.info("congress_va: API → %d veteran-related bills", len(api_arts))
            except Exception as exc:
                logger.warning("congress_va: Congress.gov API failed: %s", exc)
        else:
            logger.debug(
                "congress_va: CONGRESS_API_KEY not set — skipping API tier. "
                "Get a free key at https://api.congress.gov/sign-up/"
            )

        # ── Tier 2: GovInfo.gov bills RSS ─────────────────────────────────────
        try:
            resp = self._fetch(GOVINFO_BILLS_RSS)
            rss_arts = self._parse_govinfo_rss(resp.text, cutoff, seen_urls, target_date)
            articles.extend(rss_arts)
            if rss_arts:
                logger.info("congress_va: GovInfo RSS → %d bills", len(rss_arts))
        except Exception as exc:
            logger.warning("congress_va: GovInfo RSS failed: %s", exc)

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=int(time.monotonic() - start),
        )

    # ── Congress.gov API ──────────────────────────────────────────────────────

    def _fetch_congress_api(
        self, cutoff: date, seen_urls: set[str]
    ) -> list[ScrapedArticle]:
        """Pull recent 119th Congress bills via the API, filter by committee."""
        articles: list[ScrapedArticle] = []
        url = (
            f"{CONGRESS_API_BASE}/bill/119?"
            + urlencode([
                ("format", "json"),
                ("limit", "250"),
                ("sort", "updateDate+desc"),
                ("api_key", settings.congress_api_key),
            ])
        )
        data = self._fetch(url).json()
        for bill in data.get("bills", []):
            art = self._bill_to_article(bill, cutoff, seen_urls)
            if art:
                articles.append(art)
        return articles

    def _bill_to_article(
        self, bill: dict, cutoff: date, seen_urls: set[str]
    ) -> Optional[ScrapedArticle]:
        title = (bill.get("title") or "").strip()
        if not title:
            return None

        # Build canonical congress.gov URL
        number    = bill.get("number", "")
        bill_type = (bill.get("type") or "").lower()
        congress  = bill.get("congress", 119)
        if number and bill_type:
            url = f"https://www.congress.gov/bill/{congress}th-congress/{bill_type}/{number}"
        else:
            url = bill.get("url", "")
        if not url or url in seen_urls:
            return None

        # Publication date
        pub_date: Optional[date] = None
        for field in ("latestAction", "updateDate", "introducedDate"):
            raw = bill.get(field)
            if isinstance(raw, dict):
                raw = raw.get("actionDate") or raw.get("date") or ""
            if raw:
                try:
                    pub_date = date.fromisoformat(str(raw)[:10]); break
                except ValueError:
                    continue
        if pub_date is None:
            pub_date = date.today()
        if pub_date < cutoff:
            return None

        # Relevance check: committee OR keyword
        committees = bill.get("committees") or {}
        codes: set[str] = set()
        items = committees.get("item", []) if isinstance(committees, dict) else (committees if isinstance(committees, list) else [])
        for c in items:
            codes.add((c.get("systemCode") or "")[:4].upper())

        if not (codes & VETERAN_COMMITTEE_CODES or _is_veteran_related(title)):
            return None

        seen_urls.add(url)

        latest = bill.get("latestAction") or {}
        action = latest.get("text", "") if isinstance(latest, dict) else ""
        origin = bill.get("originChamber", "")
        label  = f"{bill_type.upper()}{number}" if bill_type and number else ""
        body   = f"{label} ({origin}). Latest action: {action}".strip(" .")

        return ScrapedArticle(
            headline=title,
            published_date=pub_date,
            source_url=url,
            body_text=body or None,
            source_name="Congress.gov",
            source_credibility="official",
            article_type="legislation",
            extra_metadata={
                "bill_number": label,
                "congress": congress,
                "committee_codes": sorted(codes),
            },
        )

    # ── GovInfo RSS ───────────────────────────────────────────────────────────

    def _parse_govinfo_rss(
        self,
        xml_text: str,
        cutoff: date,
        seen_urls: set[str],
        target_date: Optional[date],
    ) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("congress_va: GovInfo XML parse error: %s", exc)
            return articles

        for item in root.findall(".//item"):
            title_raw = item.findtext("title") or ""
            link      = (item.findtext("link") or "").strip()
            pub_raw   = item.findtext("pubDate") or ""
            desc_raw  = item.findtext("description") or ""

            if not title_raw or not link or link in seen_urls:
                continue

            title = _clean_title(title_raw)

            pub_date = _parse_rss_date(pub_raw) if pub_raw else date.today()
            if pub_date < cutoff:
                continue
            if target_date is not None and pub_date != target_date:
                continue

            # Extract the plain bill number from GovInfo GUID / link
            # e.g. "BILLS-119hr3482eh" → "H.R. 3482"
            guid = item.findtext("guid") or ""
            bill_label = _parse_govinfo_bill_label(guid or link)

            if not _is_veteran_related(title):
                continue

            seen_urls.add(link)
            articles.append(ScrapedArticle(
                headline=title,
                published_date=pub_date,
                source_url=link,
                body_text=None,
                source_name="GovInfo / Congress.gov",
                source_credibility="official",
                article_type="legislation",
                extra_metadata={"bill_label": bill_label, "feed": "govinfo_bills"},
            ))

        return articles


def _parse_govinfo_bill_label(identifier: str) -> str:
    """Extract a human-readable bill label from a GovInfo GUID or URL.

    Examples:
      "BILLS-119hr3482eh"  → "H.R. 3482"
      "BILLS-119s1890rs"   → "S. 1890"
      "BILLS-119hjres45ih" → "H.J.Res. 45"
    """
    m = re.search(
        r"BILLS-\d+([a-z]+?)(\d+)[a-z]*$",
        identifier,
        re.IGNORECASE,
    )
    if not m:
        return ""
    bill_type_raw = m.group(1).lower()
    number = m.group(2)
    type_map = {
        "hr":     "H.R.",
        "s":      "S.",
        "hjres":  "H.J.Res.",
        "sjres":  "S.J.Res.",
        "hconres":"H.Con.Res.",
        "sconres":"S.Con.Res.",
        "hres":   "H.Res.",
        "sres":   "S.Res.",
    }
    label = type_map.get(bill_type_raw, bill_type_raw.upper())
    return f"{label} {number}"
