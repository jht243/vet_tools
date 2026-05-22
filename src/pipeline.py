"""
Daily scraping pipeline orchestrator for vet_tools.
Runs all scrapers, persists results to the database, deduplicates.

Run via:
    python -m src.pipeline           # run full daily scrape
    python -m src.pipeline --dry     # scrape only, no DB writes
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import date, timedelta
from typing import Optional

import openai
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.models import (
    CredibilityTier,
    ExternalArticleEntry,
    GazetteStatus,
    ScrapeLog,
    SessionLocal,
    SourceType,
    init_db,
)
from src.scraper.base import ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scraper imports (fail gracefully so missing scrapers don't block others)
# ---------------------------------------------------------------------------

_SCRAPER_CLASSES: list = []

def _try_import(module_path: str, class_name: str) -> None:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _SCRAPER_CLASSES.append(cls)
    except Exception as exc:
        logger.warning("Could not import %s.%s: %s", module_path, class_name, exc)

_try_import("src.scraper.google_news", "GoogleNewsScraper")
_try_import("src.scraper.federal_register", "FederalRegisterScraper")
_try_import("src.scraper.va_news", "VANewsScraper")
_try_import("src.scraper.dod_news", "DoDNewsScraper")
_try_import("src.scraper.congress_va", "CongressVAScraper")
_try_import("src.scraper.va_rates", "VARatesScraper")
_try_import("src.scraper.bah_rates", "BAHRatesScraper")
_try_import("src.scraper.military_pay", "MilitaryPayScraper")

# ---------------------------------------------------------------------------
# Google News daily cap — veteran-interest keyword weights
# ---------------------------------------------------------------------------

_MILITARY_INTEREST_KEYWORDS: dict[str, float] = {
    "va disability": 3.0,
    "disability rating": 3.0,
    "pact act": 3.0,
    "burn pit": 3.0,
    "toxic exposure": 2.5,
    "va claim": 2.5,
    "disability compensation": 2.5,
    "military retirement": 2.5,
    "blended retirement": 2.5,
    "government shutdown": 3.0,
    "antideficiency": 2.5,
    "veterans affairs": 2.0,
    "va benefits": 2.0,
    "military pay": 2.0,
    "basic pay": 1.5,
    "bah": 2.0,
    "allowance": 1.5,
    "tricare": 2.0,
    "va healthcare": 2.0,
    "nexus letter": 2.0,
    "c&p exam": 2.0,
    "dbq": 2.0,
    "higher level review": 2.5,
    "board appeal": 2.5,
    "crsc": 2.0,
    "crdp": 2.0,
    "survivor benefit": 2.0,
    "legislation": 1.5,
    "congress": 1.0,
    "senate": 1.0,
}


def _score_article_interest(article: ScrapedArticle) -> float:
    """Score a Google News article by veteran-interest keyword presence."""
    haystack = " ".join(
        [
            article.headline.lower(),
            (article.body_text or "").lower()[:500],
        ]
    )
    score = 0.0
    for kw, weight in _MILITARY_INTEREST_KEYWORDS.items():
        if kw in haystack:
            score += weight
    return score


def _apply_google_news_daily_cap(
    articles: list[ScrapedArticle],
    cap: int,
    today: date,
    db,
) -> list[ScrapedArticle]:
    """Keep only the top `cap` Google News articles by veteran-interest score,
    after subtracting how many were already persisted today.
    """
    if cap <= 0:
        return articles  # 0 means disabled — pass everything through

    # How many Google News articles already persisted today?
    already_today = (
        db.query(ExternalArticleEntry)
        .filter(
            ExternalArticleEntry.source == SourceType.GOOGLE_NEWS,
            ExternalArticleEntry.published_date == today,
        )
        .count()
    )
    remaining = max(0, cap - already_today)
    if remaining == 0:
        logger.info("Google News daily cap reached (%d). Skipping all candidates.", cap)
        return []

    scored = sorted(articles, key=_score_article_interest, reverse=True)
    kept = scored[:remaining]
    dropped = len(articles) - len(kept)
    if dropped:
        logger.info(
            "Google News cap: keeping %d/%d articles (already_today=%d cap=%d)",
            len(kept),
            len(articles),
            already_today,
            cap,
        )
    return kept


# ---------------------------------------------------------------------------
# Headline normalisation / dedup helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the and or but in on at to for of with by from as is are was were be been"
    " being have has had do does did will would could should may might shall can".split()
)


def _normalize_headline(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def _headline_token_set(headline: str) -> frozenset[str]:
    tokens = _normalize_headline(headline).split()
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 2)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _load_recent_headline_index(db, lookback_days: int = 7) -> list[tuple[int, frozenset]]:
    """Load (id, token_set) pairs for ExternalArticleEntry published in the last N days."""
    cutoff = date.today() - timedelta(days=lookback_days)
    rows = (
        db.query(ExternalArticleEntry.id, ExternalArticleEntry.headline)
        .filter(ExternalArticleEntry.published_date >= cutoff)
        .all()
    )
    return [(r.id, _headline_token_set(r.headline or "")) for r in rows]


def _index_headline(tokens: frozenset, index: list[tuple[int, frozenset]]) -> None:
    """Add a new token set to the in-memory index (mutates the list)."""
    index.append((-1, tokens))  # id=-1 since it's not yet persisted


def _match_existing_headline(
    tokens: frozenset,
    index: list[tuple[int, frozenset]],
    threshold: float = 0.70,
) -> bool:
    """Return True if tokens are near-duplicate of something already in the index."""
    return any(_jaccard(tokens, existing_tokens) >= threshold for _, existing_tokens in index)


# ---------------------------------------------------------------------------
# LLM topic clustering for Google News dedup
# ---------------------------------------------------------------------------


def _llm_cluster_candidates(headlines: list[str]) -> list[int]:
    """Use the LLM to identify redundant headlines within a batch.

    Returns a list of indices (0-based) that are considered duplicates and
    should be dropped. Falls back to an empty list on any error so the caller
    can proceed without LLM-assisted dedup.
    """
    if len(headlines) <= 1:
        return []

    client = openai.OpenAI(api_key=settings.openai_api_key)
    numbered = "\n".join(f"{i}: {h}" for i, h in enumerate(headlines))
    prompt = (
        "You are a news deduplication assistant. Below is a numbered list of "
        "veteran/military news headlines. Identify which headlines cover the same "
        "underlying story (not just a similar topic — same event or same policy update). "
        "For each cluster of duplicates, keep the FIRST (lowest-numbered) headline "
        "and mark the rest as redundant.\n\n"
        f"{numbered}\n\n"
        "Return a JSON array of integers — the indices that should be DROPPED. "
        "If there are no duplicates, return [].\n"
        "Return ONLY the JSON array."
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_narrative_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        if isinstance(result, list):
            return [int(i) for i in result if isinstance(i, int)]
    except Exception as exc:
        logger.warning("LLM cluster dedup failed: %s", exc)

    return []


# ---------------------------------------------------------------------------
# Source type resolution
# ---------------------------------------------------------------------------

_SOURCE_MAP: list[tuple[str, SourceType]] = [
    ("federal register", SourceType.FEDERAL_REGISTER),
    ("va.gov news", SourceType.VA_NEWS),
    ("va news", SourceType.VA_NEWS),
    ("va.gov", SourceType.VA_NEWS),
    ("dod news", SourceType.DOD_NEWS),
    ("defense.gov", SourceType.DOD_NEWS),
    ("congress", SourceType.CONGRESS_VA),
    ("govtrack", SourceType.CONGRESS_VA),
    ("va.gov rates", SourceType.VA_RATES),
    ("dod bah rates", SourceType.BAH_RATES),
    ("bah rates", SourceType.BAH_RATES),
    ("dfas military pay", SourceType.MILITARY_PAY),
    ("military pay", SourceType.MILITARY_PAY),
    ("military news", SourceType.MILITARY_NEWS),
    ("vso news", SourceType.VSO_NEWS),
    ("google news", SourceType.GOOGLE_NEWS),
]


def _resolve_source_type(source_id: str) -> SourceType:
    lower = source_id.lower()
    for fragment, src_type in _SOURCE_MAP:
        if fragment in lower:
            return src_type
    return SourceType.GOOGLE_NEWS


def _resolve_credibility(source_credibility: str) -> CredibilityTier:
    mapping = {
        "official": CredibilityTier.OFFICIAL,
        "tier1": CredibilityTier.TIER1,
        "tier2": CredibilityTier.TIER2,
        "state": CredibilityTier.STATE,
    }
    return mapping.get((source_credibility or "").lower(), CredibilityTier.TIER2)


# ---------------------------------------------------------------------------
# Persist articles
# ---------------------------------------------------------------------------


def _persist_articles(
    db,
    result: ScrapeResult,
    articles: list[ScrapedArticle],
    headline_index: list[tuple[int, frozenset]],
    today: date,
) -> tuple[int, int]:
    """Persist scraped articles. Returns (found, new)."""
    found = len(articles)
    new_count = 0
    source_type = _resolve_source_type(result.source)

    for art in articles:
        tokens = _headline_token_set(art.headline)

        if _match_existing_headline(tokens, headline_index):
            logger.debug("Dedup skip headline=%r", art.headline[:60])
            continue

        entry = ExternalArticleEntry(
            source=source_type,
            source_url=art.source_url,
            source_name=art.source_name or result.source,
            credibility=_resolve_credibility(art.source_credibility),
            headline=art.headline,
            published_date=art.published_date,
            body_text=art.body_text or None,
            article_type=art.article_type or "news",
            extra_metadata=art.extra_metadata or {},
            status=GazetteStatus.SCRAPED,
        )

        try:
            db.add(entry)
            db.flush()
            _index_headline(tokens, headline_index)
            new_count += 1
        except IntegrityError:
            db.rollback()
            logger.debug("Unique constraint skip url=%s", art.source_url[:80])

    return found, new_count


# ---------------------------------------------------------------------------
# Scrape log
# ---------------------------------------------------------------------------


def _log_scrape(
    db,
    source_type: SourceType,
    scrape_date: date,
    success: bool,
    entries_found: int = 0,
    error_message: Optional[str] = None,
    duration_seconds: int = 0,
) -> None:
    log_entry = ScrapeLog(
        source=source_type,
        scrape_date=scrape_date,
        success=success,
        entries_found=entries_found,
        error_message=error_message,
        duration_seconds=duration_seconds,
    )
    try:
        db.add(log_entry)
        db.flush()
    except Exception as exc:
        logger.warning("Failed to write ScrapeLog: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_daily_scrape(
    target_date: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    """Run all scrapers and persist results.

    Args:
        target_date: The date to scrape for (defaults to today).
        dry_run:     If True, scrape but do not write to DB.

    Returns:
        Summary dict with counts per source and aggregate totals.
    """
    init_db()

    today = target_date or date.today()

    summary: dict = {
        "date": str(today),
        "articles_found": 0,
        "articles_new": 0,
        "errors": [],
        "sources": {},
    }

    if not _SCRAPER_CLASSES:
        logger.error("No scrapers available. Check imports above.")
        return summary

    db = SessionLocal()
    try:
        # Build headline dedup index from recently persisted articles
        headline_index = _load_recent_headline_index(db, lookback_days=7)
        logger.info("Loaded %d headlines into dedup index.", len(headline_index))

        for scraper_cls in _SCRAPER_CLASSES:
            scraper_name = scraper_cls.__name__
            logger.info("Running scraper: %s", scraper_name)
            t0 = time.monotonic()

            try:
                scraper = scraper_cls()
                result: ScrapeResult = scraper.scrape(target_date=today)
            except Exception as exc:
                duration = int(time.monotonic() - t0)
                logger.error("Scraper %s crashed: %s", scraper_name, exc, exc_info=True)
                source_type = _resolve_source_type(scraper_name)
                if not dry_run:
                    _log_scrape(
                        db,
                        source_type=source_type,
                        scrape_date=today,
                        success=False,
                        error_message=str(exc)[:500],
                        duration_seconds=duration,
                    )
                    db.commit()
                summary["errors"].append({"scraper": scraper_name, "error": str(exc)})
                continue

            duration = int(time.monotonic() - t0)
            source_type = _resolve_source_type(result.source)
            articles = result.articles or []

            if not result.success:
                logger.warning(
                    "Scraper %s reported failure: %s (%d articles returned)",
                    scraper_name,
                    result.error,
                    len(articles),
                )

            # Apply Google News daily cap
            if source_type == SourceType.GOOGLE_NEWS:
                articles = _apply_google_news_daily_cap(
                    articles, settings.google_news_daily_cap, today, db
                )

            found = len(articles)
            new_count = 0

            if not dry_run and articles:
                new_count_result = _persist_articles(
                    db, result, articles, headline_index, today
                )
                found, new_count = new_count_result

            if not dry_run:
                _log_scrape(
                    db,
                    source_type=source_type,
                    scrape_date=today,
                    success=result.success,
                    entries_found=found,
                    error_message=result.error[:500] if result.error else None,
                    duration_seconds=duration,
                )
                db.commit()

            source_key = result.source
            summary["sources"][source_key] = {
                "found": found,
                "new": new_count,
                "success": result.success,
                "duration_seconds": duration,
            }
            summary["articles_found"] += found
            summary["articles_new"] += new_count

            if result.error:
                summary["errors"].append({"scraper": scraper_name, "error": result.error})

            logger.info(
                "Scraper %s done — found=%d new=%d ok=%s duration=%ds",
                scraper_name,
                found,
                new_count,
                result.success,
                duration,
            )

    finally:
        db.close()

    logger.info(
        "Pipeline done — articles_found=%d articles_new=%d errors=%d",
        summary["articles_found"],
        summary["articles_new"],
        len(summary["errors"]),
    )
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Run vet_tools daily scrape pipeline")
    parser.add_argument("--dry", action="store_true", help="Scrape only — do not write to DB")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target: Optional[date] = None
    if args.date:
        from datetime import datetime
        target = datetime.strptime(args.date, "%Y-%m-%d").date()

    result = run_daily_scrape(target_date=target, dry_run=args.dry)
    print(json.dumps(result, indent=2, default=str))
