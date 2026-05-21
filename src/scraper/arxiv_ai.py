"""
ArXiv scraper — cs.AI and cs.CY (Computers and Society) Atom feed.

Targets papers on AI safety, AI ethics, AI labor impact, and AI
governance that are accessible to a non-specialist business audience
(i.e. we score on practical implication, not mathematical novelty).
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Optional

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# ArXiv Atom API — max_results capped at 50 to stay polite.
_ARXIV_API = "https://export.arxiv.org/api/query"
_SEARCHES: list[tuple[str, str]] = [
    # (search_query, topic_label)
    ("cat:cs.AI+AND+(safety+OR+ethics+OR+governance+OR+risk)", "AI Safety & Ethics"),
    ("cat:cs.CY+AND+(artificial+intelligence+OR+machine+learning)", "AI & Society"),
]

# Relevance filter — paper abstract must contain at least one.
_RELEVANCE_KEYWORDS = {
    "safety", "ethics", "bias", "fairness", "accountability",
    "transparency", "governance", "risk", "harm", "regulation",
    "labor", "employment", "jobs", "workforce", "discrimination",
    "misinformation", "hallucination", "trust", "policy",
}

_ARXIV_NS = "http://www.w3.org/2005/Atom"


class ArxivAIScraper(BaseScraper):
    """Fetches recent AI safety / society papers from ArXiv."""

    def get_source_id(self) -> str:
        return "arxiv_ai"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []
        seen: set[str] = set()

        lookback = timedelta(days=settings.scraper_lookback_days)
        cutoff = (target_date or date.today()) - lookback

        for query, topic in _SEARCHES:
            for article in self._fetch_arxiv(query, topic, cutoff):
                if article.source_url not in seen:
                    seen.add(article.source_url)
                    articles.append(article)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("ArxivAIScraper: %d papers found (cutoff=%s)", len(articles), cutoff)
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    def _fetch_arxiv(
        self, query: str, topic: str, cutoff: date
    ) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        url = (
            f"{_ARXIV_API}?search_query={query}"
            f"&sortBy=submittedDate&sortOrder=descending&max_results=30"
        )
        try:
            resp = self._fetch(url)
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning("ArXiv fetch failed for query '%s': %s", query, exc)
            return out

        ns = _ARXIV_NS
        for entry in root.findall(f"{{{ns}}}entry"):
            arxiv_id = (entry.findtext(f"{{{ns}}}id") or "").strip()
            title = (entry.findtext(f"{{{ns}}}title") or "").strip().replace("\n", " ")
            abstract = (entry.findtext(f"{{{ns}}}summary") or "").strip().replace("\n", " ")
            pub_raw = (entry.findtext(f"{{{ns}}}published") or "").strip()

            pub_date = _parse_iso_datetime(pub_raw)
            if pub_date and pub_date < cutoff:
                continue

            combined = (title + " " + abstract).lower()
            if not any(kw in combined for kw in _RELEVANCE_KEYWORDS):
                continue

            # Build a short non-technical abstract excerpt (≤ 400 chars).
            body = abstract[:400] + ("…" if len(abstract) > 400 else "")

            out.append(ScrapedArticle(
                headline=f"[ArXiv] {title}",
                published_date=pub_date or date.today(),
                source_url=arxiv_id,
                body_text=body,
                source_name="ArXiv",
                source_credibility="tier2",
                article_type="research",
                extra_metadata={"topic": topic, "arxiv_id": arxiv_id},
            ))

        logger.info("ArXiv query '%s': %d relevant papers", topic, len(out))
        return out


def _parse_iso_datetime(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.rstrip("Z")).date()
    except ValueError:
        return None
