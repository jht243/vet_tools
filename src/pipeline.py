"""
Daily scraping pipeline orchestrator.

Runs all scrapers, persists results to the database, and logs results.

Usage:
    from src.pipeline import run_daily_scrape
    run_daily_scrape()                    # today
    run_daily_scrape(date(2026, 3, 27))   # specific date
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.models import (
    SessionLocal, init_db,
    ExternalArticleEntry, ScrapeLog,
    SourceType, CredibilityTier, ArticleStatus,
)
from src.scraper.base import ScrapedArticle, ScrapeResult
from src.scraper.google_news import GoogleNewsScraper
from src.scraper.ai_incident_db import AIIncidentDBScraper
from src.scraper.regulatory_ai import RegulatoryAIScraper
from src.scraper.labor_ai import LaborAIScraper
from src.scraper.energy_ai import EnergyAIScraper
from src.scraper.arxiv_ai import ArxivAIScraper
from src.scraper.sej_algo import SEJAlgoScraper
from src.scraper.digg_ai import DiggAIScraper

logger = logging.getLogger(__name__)


def run_daily_scrape(target_date: Optional[date] = None) -> dict:
    """
    Run the full daily scraping pipeline:
      1. Scrape all sources
      2. Persist new entries to DB
      3. Log results

    Returns a summary dict with counts.
    """
    target_date = target_date or date.today()
    init_db()

    logger.info("=" * 60)
    logger.info("Starting daily scrape for %s", target_date)
    logger.info("=" * 60)

    summary = {
        "date": str(target_date),
        "articles_found": 0,
        "articles_new": 0,
        "errors": [],
    }

    # --- Phase 1: Scrape all sources ---
    scrape_results: list[ScrapeResult] = []

    scrapers = [
        GoogleNewsScraper(),
        AIIncidentDBScraper(),
        RegulatoryAIScraper(),
        LaborAIScraper(),
        EnergyAIScraper(),
        ArxivAIScraper(),
        SEJAlgoScraper(),
        DiggAIScraper(),
    ]

    for scraper in scrapers:
        try:
            logger.info("Running scraper: %s", scraper.get_source_id())
            result = scraper.scrape(target_date)
            scrape_results.append(result)
            _log_scrape(result, target_date)

            if not result.success:
                summary["errors"].append(f"{scraper.get_source_id()}: {result.error}")
        except Exception as e:
            logger.error("Scraper %s crashed: %s", scraper.get_source_id(), e, exc_info=True)
            summary["errors"].append(f"{scraper.get_source_id()}: {e}")
        finally:
            scraper.close()

    # --- Phase 2: Persist external articles ---
    all_articles: list[ScrapedArticle] = []
    for r in scrape_results:
        all_articles.extend(r.articles)
    summary["articles_found"] = len(all_articles)

    # Cap-and-rank pass for Google News BEFORE persistence. Keeps the
    # blog-gen pipeline focused on the highest-signal articles each day.
    all_articles = _apply_google_news_daily_cap(all_articles)

    new_articles = _persist_articles(all_articles)
    summary["articles_new"] = len(new_articles)

    logger.info("=" * 60)
    logger.info("Scrape complete: %s", summary)
    logger.info("=" * 60)

    return summary


def _persist_articles(articles: list[ScrapedArticle]) -> list[int]:
    """Insert external articles into the DB.

    Two layers of dedup:
      1. (source, source_url) UNIQUE constraint at the DB level.
      2. Cross-source headline match (Google News only) — catches the
         same wire story landing via different URLs.
    """
    new_ids = []
    db = SessionLocal()

    credibility_map = {
        "official": CredibilityTier.OFFICIAL,
        "tier1": CredibilityTier.TIER1,
        "tier2": CredibilityTier.TIER2,
        "state": CredibilityTier.STATE,
    }

    recent_headlines = _load_recent_headline_index(db)

    try:
        for a in articles:
            source_type = _resolve_source_type(a.source_name)
            cred = credibility_map.get(a.source_credibility, CredibilityTier.TIER2)
            tone = a.extra_metadata.get("tone") if a.extra_metadata else None

            if source_type == SourceType.GOOGLE_NEWS:
                match = _match_existing_headline(a.headline, recent_headlines)
                if match is not None:
                    logger.info(
                        "Google News dedupe: skipping %r (matches existing %r)",
                        (a.headline or "")[:80], match[:80],
                    )
                    continue

            entry = ExternalArticleEntry(
                source=source_type,
                source_url=a.source_url,
                source_name=a.source_name,
                credibility=cred,
                headline=a.headline,
                published_date=a.published_date,
                body_text=a.body_text,
                article_type=a.article_type,
                tone_score=float(tone) if tone is not None else None,
                extra_metadata=a.extra_metadata,
                status=ArticleStatus.SCRAPED,
            )
            nested = db.begin_nested()
            try:
                db.add(entry)
                db.flush()
                nested.commit()
                new_ids.append(entry.id)
                logger.info("Persisted article: %s [%s]", a.headline[:80], a.source_name)
                _index_headline(a.headline, recent_headlines)
            except IntegrityError:
                nested.rollback()
                logger.debug("Duplicate article skipped: %s", a.source_url)

        db.commit()
    finally:
        db.close()

    return new_ids


# ── headline dedup ─────────────────────────────────────────────────────
# Cross-source dedup against existing rows. Used by _persist_articles to
# keep Google News from re-importing the same story from different queries.

_HEADLINE_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "by", "with", "as", "from",
    "that", "this", "it", "its", "but", "not", "have", "has", "had",
    "will", "would", "should", "could", "may", "might", "can", "do",
    "does", "did", "say", "says", "said", "new", "more", "than",
    "ai", "artificial", "intelligence",  # too common in BTB to be dedup signal
})

_HEADLINE_DEDUP_LOOKBACK_DAYS = 14
_HEADLINE_JACCARD_THRESHOLD = 0.85


def _normalize_headline(headline: str) -> str:
    if not headline:
        return ""
    text = headline
    if " - " in text:
        text = text.rsplit(" - ", 1)[0]
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _headline_token_set(normalized: str) -> frozenset[str]:
    return frozenset(
        t for t in normalized.split()
        if len(t) > 2 and t not in _HEADLINE_STOPWORDS
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _load_recent_headline_index(db) -> list[tuple[str, frozenset[str]]]:
    cutoff = date.today() - timedelta(days=_HEADLINE_DEDUP_LOOKBACK_DAYS)
    rows = (
        db.query(ExternalArticleEntry.headline)
        .filter(ExternalArticleEntry.published_date >= cutoff)
        .all()
    )
    index: list[tuple[str, frozenset[str]]] = []
    for (headline,) in rows:
        normalized = _normalize_headline(headline)
        if not normalized:
            continue
        index.append((normalized, _headline_token_set(normalized)))
    return index


def _index_headline(headline: str, index: list[tuple[str, frozenset[str]]]) -> None:
    normalized = _normalize_headline(headline)
    if not normalized:
        return
    index.append((normalized, _headline_token_set(normalized)))


def _match_existing_headline(
    headline: str,
    index: list[tuple[str, frozenset[str]]],
) -> Optional[str]:
    normalized = _normalize_headline(headline)
    if not normalized:
        return None
    tokens = _headline_token_set(normalized)
    if not tokens:
        return None
    for existing_norm, existing_tokens in index:
        if existing_norm == normalized:
            return existing_norm
        if _jaccard(tokens, existing_tokens) >= _HEADLINE_JACCARD_THRESHOLD:
            return existing_norm
    return None


# ── Google News daily cap + AI-relevance ranking ──────────────────────
# Google News can return 100+ items/day. We persist at most
# settings.google_news_daily_cap of them, picking the highest-signal ones.

_AI_RELEVANCE_KEYWORDS: dict[str, float] = {
    # Jobs / labor — highest signal for our audience
    "layoffs": 3.5, "laid off": 3.5, "job loss": 3.5, "job cut": 3.0,
    "job displacement": 3.5, "replacing workers": 3.5, "replace human": 3.0,
    "automation": 2.5, "workforce": 2.5, "unemployment": 3.0,
    "gig worker": 3.0, "union": 2.5, "strike": 2.5, "wages": 2.5,
    # Education / kids / parenting
    "students": 3.0, "schools": 3.0, "teachers": 3.0, "cheating": 3.0,
    "kids": 3.0, "children": 3.0, "parents": 2.5, "teens": 3.0,
    "mental health": 3.0, "classroom": 3.0, "homework": 3.0,
    # Regulation protecting people
    "ai act": 3.0, "eu ai act": 3.5, "regulation": 2.0,
    "lawsuit": 2.5, "class action": 3.0, "rights": 2.5, "ban": 2.5,
    # Surveillance / civil rights
    "facial recognition": 3.5, "surveillance": 3.0, "privacy": 2.5,
    "wrongful arrest": 3.5, "discrimination": 3.0, "bias": 2.5,
    "data collection": 2.5, "tracking": 2.0,
    # Deepfakes / content harm
    "deepfake": 3.0, "misinformation": 2.5, "disinformation": 2.5,
    "ai slop": 3.0, "ai-generated": 2.0, "ai content": 2.0,
    # Environment / community impact
    "data center water": 3.0, "ai water": 3.0,
    "ai energy": 2.5, "electricity": 2.0, "data center": 1.5,
    # General AI backlash / human impact
    "ai backlash": 3.0, "no ai": 3.0, "anti-ai": 3.0,
    "ai ethics": 2.0, "ai safety": 2.0, "ai harm": 3.0,
    "ai risk": 2.0, "human-first": 2.5,
}

_CREDIBILITY_WEIGHTS: dict[str, float] = {
    "official": 2.5,
    "tier1": 2.0,
    "tier2": 1.0,
    "state": 0.5,
}

_GOOGLE_NEWS_MAX_AGE_DAYS = 7
_GOOGLE_NEWS_MAX_PER_PUBLISHER = 2
_GOOGLE_NEWS_IN_BATCH_DIVERSITY_THRESHOLD = 0.40


def _ai_relevance_score(article: ScrapedArticle) -> float:
    """Heuristic 0-15ish score predicting AI-backlash relevance."""
    headline = (article.headline or "").lower()
    snippet = ""
    if article.extra_metadata:
        snippet = (article.extra_metadata.get("snippet") or "").lower()
    text = f"{headline} {snippet}"

    keyword_score = sum(
        weight for kw, weight in _AI_RELEVANCE_KEYWORDS.items() if kw in text
    )

    cred_score = _CREDIBILITY_WEIGHTS.get(article.source_credibility, 0.5)

    days_old = max(0, (date.today() - article.published_date).days)
    recency_bonus = max(0.0, 1.5 - 0.5 * days_old)

    length_penalty = -2.0 if len(headline.split()) < 4 else 0.0

    return keyword_score + cred_score + recency_bonus + length_penalty


def _count_google_news_persisted_today(db) -> int:
    today = date.today()
    return (
        db.query(ExternalArticleEntry)
        .filter(ExternalArticleEntry.source == SourceType.GOOGLE_NEWS)
        .filter(ExternalArticleEntry.created_at >= today)
        .count()
    )


_CLUSTERING_SYSTEM_PROMPT = """You are an expert news editor for a citizen-first site covering how AI affects everyday people — workers, parents, students, and communities.

You will receive a numbered list of news headlines with dates and publishers. Your job is to group headlines that report the SAME real-world event into clusters.

DEFINITION OF "SAME EVENT" (group together):
- Same regulation, law, or enforcement action covered by multiple outlets
- Same AI incident or harm report from different sources
- Same research finding or study cited across outlets
- Same layoff announcement or corporate AI news
- Same wire story republished by syndicators

NOT THE SAME EVENT (keep separate):
- Two different stories about the same company on the same day
- A sector analysis vs a specific incident
- An explainer published days after the underlying event
- Opinion pieces vs the news they reference

OUTPUT FORMAT (strict JSON, no prose, no markdown):
{
  "clusters": [
    [1, 4, 7],
    [2],
    [3, 5]
  ]
}

Every input ID must appear in exactly one cluster. Single-item clusters are expected and fine.
"""


def _llm_cluster_candidates(
    candidates: list[ScrapedArticle],
) -> list[list[int]]:
    """Group candidates that report the same real-world news event.

    Returns clusters as 0-indexed lists. On any failure returns the
    identity clustering (one cluster per item).
    """
    fallback = [[i] for i in range(len(candidates))]

    if not candidates:
        return []
    if len(candidates) <= 1:
        return fallback
    if not settings.openai_api_key:
        logger.info("LLM clustering: no OPENAI_API_KEY; using identity clusters")
        return fallback

    lines = []
    for i, c in enumerate(candidates, start=1):
        pub = (c.extra_metadata or {}).get("publisher") or ""
        snippet = (c.extra_metadata or {}).get("snippet") or ""
        tail = f' ({snippet[:120]})' if snippet else ""
        lines.append(
            f'{i}. [{c.published_date}] "{c.headline}" — {pub}{tail}'
        )
    user_msg = "Cluster these AI news headlines:\n\n" + "\n".join(lines)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_narrative_model,
            messages=[
                {"role": "system", "content": _CLUSTERING_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=600,
            response_format={"type": "json_object"},
            timeout=20.0,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        raw_clusters = parsed.get("clusters", [])

        if not isinstance(raw_clusters, list):
            raise ValueError(f"clusters not a list: {type(raw_clusters).__name__}")

        clusters: list[list[int]] = []
        seen: set[int] = set()
        for cluster in raw_clusters:
            if not isinstance(cluster, list):
                continue
            valid = []
            for n in cluster:
                try:
                    idx = int(n) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(candidates) and idx not in seen:
                    valid.append(idx)
                    seen.add(idx)
            if valid:
                clusters.append(valid)

        for i in range(len(candidates)):
            if i not in seen:
                clusters.append([i])

        merged_count = sum(1 for c in clusters if len(c) > 1)
        merged_total = sum(len(c) - 1 for c in clusters if len(c) > 1)
        logger.info(
            "LLM clustering: %d candidates -> %d clusters "
            "(%d multi-item clusters merged %d duplicates)",
            len(candidates), len(clusters), merged_count, merged_total,
        )
        return clusters

    except Exception as exc:
        logger.warning(
            "LLM clustering failed (%s: %s) — falling back to identity clusters",
            type(exc).__name__, exc,
        )
        return fallback


def _apply_google_news_daily_cap(
    articles: list[ScrapedArticle],
) -> list[ScrapedArticle]:
    """Prune the article list to enforce settings.google_news_daily_cap."""
    cap = settings.google_news_daily_cap
    if cap <= 0:
        non_gn = [a for a in articles if _resolve_source_type(a.source_name) != SourceType.GOOGLE_NEWS]
        gn_dropped = len(articles) - len(non_gn)
        if gn_dropped:
            logger.info("Google News intake disabled (cap=0); dropped %d articles", gn_dropped)
        return non_gn

    gn_candidates = [
        a for a in articles
        if _resolve_source_type(a.source_name) == SourceType.GOOGLE_NEWS
    ]
    non_gn = [
        a for a in articles
        if _resolve_source_type(a.source_name) != SourceType.GOOGLE_NEWS
    ]

    if not gn_candidates:
        return non_gn

    today = date.today()
    fresh_candidates = [
        a for a in gn_candidates
        if a.published_date and (today - a.published_date).days <= _GOOGLE_NEWS_MAX_AGE_DAYS
    ]
    stale_dropped = len(gn_candidates) - len(fresh_candidates)

    if not fresh_candidates:
        logger.info(
            "Google News cap pass: 0 candidates within %d-day window (dropped %d stale)",
            _GOOGLE_NEWS_MAX_AGE_DAYS, stale_dropped,
        )
        return non_gn

    db = SessionLocal()
    try:
        already_today = _count_google_news_persisted_today(db)
        remaining = max(0, cap - already_today)

        if remaining == 0:
            logger.info(
                "Google News daily cap (%d) already reached today (%d persisted) "
                "— dropping %d new candidates",
                cap, already_today, len(fresh_candidates),
            )
            return non_gn

        index = _load_recent_headline_index(db)
        new_candidates: list[ScrapedArticle] = []
        rejected_dup = 0
        for cand in fresh_candidates:
            match = _match_existing_headline(cand.headline, index)
            if match is not None:
                rejected_dup += 1
                logger.debug(
                    "Google News cap-pass cross-DB dedup: skipping %r ~ %r",
                    (cand.headline or "")[:70], match[:70],
                )
                continue
            new_candidates.append(cand)

        if not new_candidates:
            logger.info(
                "Google News cap pass: 0 candidates survived cross-DB dedup "
                "(%d in 7d, %d already in DB, %d stale)",
                len(fresh_candidates), rejected_dup, stale_dropped,
            )
            return non_gn

        clusters = _llm_cluster_candidates(new_candidates)

        cluster_reps: list[tuple[float, ScrapedArticle, int]] = []
        for cluster in clusters:
            cluster_scored = [
                (_ai_relevance_score(new_candidates[i]), new_candidates[i])
                for i in cluster
            ]
            cluster_scored.sort(key=lambda t: t[0], reverse=True)
            best_score, best_item = cluster_scored[0]
            cluster_reps.append((best_score, best_item, len(cluster)))

        cluster_reps.sort(key=lambda t: t[0], reverse=True)

        clusters_collapsed = sum(1 for _, _, sz in cluster_reps if sz > 1)
        rejected_clustering = len(new_candidates) - len(cluster_reps)

        accepted: list[ScrapedArticle] = []
        accepted_token_sets: list[frozenset[str]] = []
        rejected_publisher = 0
        rejected_diversity = 0
        per_publisher_count: dict[str, int] = {}

        for score, cand, _cluster_size in cluster_reps:
            if len(accepted) >= remaining:
                break

            meta = cand.extra_metadata or {}
            publisher_key = (
                meta.get("publisher")
                or meta.get("publisher_domain")
                or ""
            ).strip().lower() or "(unknown)"
            if per_publisher_count.get(publisher_key, 0) >= _GOOGLE_NEWS_MAX_PER_PUBLISHER:
                rejected_publisher += 1
                continue

            cand_tokens = _headline_token_set(_normalize_headline(cand.headline))
            most_similar = max(
                (_jaccard(cand_tokens, pt) for pt in accepted_token_sets),
                default=0.0,
            )
            if most_similar >= _GOOGLE_NEWS_IN_BATCH_DIVERSITY_THRESHOLD:
                rejected_diversity += 1
                continue

            accepted.append(cand)
            accepted_token_sets.append(cand_tokens)
            per_publisher_count[publisher_key] = per_publisher_count.get(publisher_key, 0) + 1
            _index_headline(cand.headline, index)

        over_cap = max(
            0,
            len(cluster_reps) - len(accepted) - rejected_publisher - rejected_diversity,
        )
        logger.info(
            "Google News cap pass: %d in 7d / %d total -> %d accepted "
            "(cap=%d, already_today=%d, dropped_stale=%d, dropped_db_dup=%d, "
            "merged_by_llm=%d (%d clusters collapsed), dropped_pub_limit=%d, "
            "dropped_token_diversity=%d, dropped_over_cap=%d)",
            len(fresh_candidates), len(gn_candidates), len(accepted), cap,
            already_today, stale_dropped, rejected_dup,
            rejected_clustering, clusters_collapsed,
            rejected_publisher, rejected_diversity, over_cap,
        )
        return non_gn + accepted
    finally:
        db.close()


def _resolve_source_type(source_name: str) -> SourceType:
    """Map a source name string to a SourceType enum value."""
    name_lower = (source_name or "").lower()
    mapping = {
        "google news": SourceType.GOOGLE_NEWS,
        "ai incident db": SourceType.AI_INCIDENT_DB,
        "aiid": SourceType.AI_INCIDENT_DB,
        "aiaaic": SourceType.AIAAIC,
        "eu ai act": SourceType.EU_AI_ACT,
        "ftc": SourceType.FTC_AI,
        "nist": SourceType.NIST_RMF,
        "congress": SourceType.CONGRESS_AI,
        "doe": SourceType.DOE_ENERGY,
        "bls": SourceType.BLS_LABOR,
        "layoffs.fyi": SourceType.LAYOFF_FYI,
        "arxiv": SourceType.ARXIV_AI,
        "search engine land": SourceType.SEJ_ALGO,
        "search engine journal": SourceType.SEJ_ALGO,
    }
    for key, val in mapping.items():
        if key in name_lower:
            return val
    return SourceType.GOOGLE_NEWS


def _log_scrape(result: ScrapeResult, target_date: date) -> None:
    """Write a scrape log entry for diagnostics."""
    db = SessionLocal()
    try:
        try:
            source = SourceType(result.source)
        except ValueError:
            logger.warning("Unknown source type '%s', skipping log", result.source)
            return

        log = ScrapeLog(
            source=source,
            scrape_date=target_date,
            success=result.success,
            entries_found=len(result.articles),
            error_message=result.error,
            duration_seconds=result.duration_seconds,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
