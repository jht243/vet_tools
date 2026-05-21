"""
Digg AI scraper — https://digg.com/ai

Digg curates AI news "before it trends," surfacing stories ranked by
engagement across technical Twitter/X. No public RSS or API exists;
this scraper fetches the HTML and extracts story cards using
BeautifulSoup. Covers all five BTB angles.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup

from src.config import settings
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

_DIGG_AI_URL = "https://digg.com/ai"
_DIGG_BASE = "https://digg.com"

# Minimum relevance: article must contain at least one of these.
_RELEVANCE_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "llm",
    "chatgpt", "openai", "anthropic", "gemini", "nvidia",
    "data center", "automation", "robot", "layoff", "regulation",
    "eu ai act", "ftc", "safety", "bias", "hallucination",
    "generative", "deepfake", "gpt", "model", "agent",
}


class DiggAIScraper(BaseScraper):
    """Scrapes trending AI stories from digg.com/ai."""

    def get_source_id(self) -> str:
        return "digg_ai"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        start = datetime.utcnow()
        articles: list[ScrapedArticle] = []

        try:
            resp = self._fetch(_DIGG_AI_URL)
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = self._parse_stories(soup)
        except Exception as exc:
            logger.warning("Digg AI fetch/parse failed: %s", exc)

        elapsed = int((datetime.utcnow() - start).total_seconds())
        logger.info("DiggAIScraper: %d stories found", len(articles))
        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            duration_seconds=elapsed,
        )

    def _parse_stories(self, soup: BeautifulSoup) -> list[ScrapedArticle]:
        out: list[ScrapedArticle] = []
        seen: set[str] = set()

        # Digg renders story cards as <a> tags whose href matches
        # the pattern /ai/<story-id> or /story/<story-id>.
        # Each card wraps an <h2> or <h3> with the headline text.
        story_pattern = re.compile(r"^/(ai|story)/[a-z0-9\-]+", re.IGNORECASE)

        for a_tag in soup.find_all("a", href=story_pattern):
            href = a_tag.get("href", "")
            if not href:
                continue

            # Build absolute URL
            url = href if href.startswith("http") else _DIGG_BASE + href
            if url in seen:
                continue
            seen.add(url)

            # Title: prefer heading text inside the link, fall back to
            # aria-label or the link's own text.
            heading = a_tag.find(re.compile(r"^h[1-6]$"))
            if heading:
                title = heading.get_text(" ", strip=True)
            else:
                title = (
                    a_tag.get("aria-label")
                    or a_tag.get_text(" ", strip=True)
                )
            title = _clean_text(title)
            if not title or len(title) < 15:
                continue

            # Relevance filter
            if not any(kw in title.lower() for kw in _RELEVANCE_KEYWORDS):
                # Check surrounding card text as well
                card = a_tag.parent or a_tag
                card_text = card.get_text(" ", strip=True).lower()
                if not any(kw in card_text for kw in _RELEVANCE_KEYWORDS):
                    continue

            # Description: grab sibling paragraph text in the card
            card_el = a_tag.parent or a_tag
            paras = card_el.find_all("p")
            desc = " ".join(p.get_text(" ", strip=True) for p in paras)[:500]
            if not desc:
                desc = title

            out.append(ScrapedArticle(
                headline=title,
                published_date=date.today(),
                source_url=url,
                body_text=desc,
                source_name="Digg AI",
                source_credibility="tier2",
                article_type="news",
                extra_metadata={"topic": "digg_trending"},
            ))

        logger.info("Digg AI: %d relevant stories parsed", len(out))
        return out


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text or "").strip()
