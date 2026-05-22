"""
LLM-powered relevance analyzer for vet_tools.

For each ExternalArticleEntry with status=SCRAPED, this module decides:
  1. Is the article relevant to VA/military benefits? (prefilter)
  2. Is it a rule-based source (rate tables)? → apply template
  3. Otherwise → call the LLM and store analysis_json

Run via:
    python -m src.analyzer          # process all pending articles
    python -m src.analyzer --dry    # print without writing
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Optional

import openai

from src.config import settings
from src.models import (
    ExternalArticleEntry,
    GazetteStatus,
    SessionLocal,
    SourceType,
    init_db,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relevance vocabulary
# ---------------------------------------------------------------------------

RELEVANCE_KEYWORDS = (
    # Broad catch-alls — catches most headlines even without body text
    "veteran",
    "military",
    "service member",
    "armed forces",
    "department of defense",
    "department of veterans",
    # VA & disability specifics
    "va disability",
    "veterans affairs",
    "va claim",
    "disability rating",
    "compensation",
    "pact act",
    "burn pit",
    "toxic exposure",
    "va appeals",
    "board of veterans",
    "higher level review",
    "supplemental claim",
    "nexus letter",
    "dbq",
    "c&p exam",
    "cp exam",
    "service connection",
    "disability compensation",
    "rating schedule",
    "cfr 38",
    "38 cfr",
    "38 usc",
    # Pay & retirement
    "military retirement",
    "blended retirement",
    "brs",
    "basic allowance",
    "bah",
    "military pay",
    "bas",
    "crsc",
    "crdp",
    "concurrent receipt",
    "survivor benefit",
    "sbp",
    # Healthcare
    "tricare",
    "va healthcare",
    "community care",
    # Legislative / policy
    "government shutdown",
    "antideficiency act",
    "veterans legislation",
    "veterans benefits",
    "veterans bill",
    "veterans act",
    "armed services committee",
    "defense authorization",
    "ndaa",
)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior policy analyst specializing in US veterans benefits and military compensation.
You work for an information service helping veterans, military families, and service members understand their benefits.

Your audience: veterans filing disability claims, active-duty service members planning retirement, military families managing benefits, VSO counselors, and benefits attorneys.

For each article, produce a JSON object with these fields:
{
  "relevance_score": <int 1-10, where 10 = directly changes veteran/military benefits>,
  "angles": [<list of applicable angles from: "va_claims_process", "disability_ratings", "retirement_benefits", "military_pay", "government_shutdown", "legislation_policy", "appeals", "pact_act_burn_pits", "healthcare_tricare">],
  "sentiment": "<one of: positive, negative, mixed>",
  "status": "<one of: passed, in_progress, announced, in_effect, monitoring>",
  "category_label": "<display label, e.g. 'VA Claims', 'Disability Ratings', 'Military Retirement'>",
  "headline_short": "<concise headline, max 80 chars>",
  "takeaway": "<2-4 sentence analysis of what this means for veterans and military families. Wrap the single most important sentence in literal HTML <strong>...</strong> tags. Do NOT use markdown asterisks.>",
  "is_breaking": <true if this materially changes veteran/military benefits>,
  "source_trust": "<one of: official, tier1, state, tier2>"
}

Score guidelines:
- 1-3: routine administrative, no benefit impact
- 4-5: background context, policy monitoring
- 6-7: meaningful policy change, watch closely
- 8-10: directly affects veteran claims, pay, or rights
- PACT Act expansions always 7+
- VA rating schedule changes always 7+
- Government shutdown affecting military pay always 8+
- Major VA policy or legislation always 6+

Return ONLY the JSON object, no markdown fences or explanation.\
"""

USER_PROMPT_TEMPLATE = """\
Analyze this article for veteran/military benefits relevance.

Source: {source}
Published: {published_date}
Headline: {headline}

Body (may be truncated):
{body_text}

Return ONLY the JSON object described in your instructions.\
"""

# ---------------------------------------------------------------------------
# LLM usage tracking
# ---------------------------------------------------------------------------

_LLM_USAGE: dict[str, int] = {
    "calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
}


def reset_usage() -> None:
    _LLM_USAGE["calls"] = 0
    _LLM_USAGE["input_tokens"] = 0
    _LLM_USAGE["output_tokens"] = 0


def get_usage() -> dict[str, int]:
    return dict(_LLM_USAGE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RULE_BASED_SOURCES = {SourceType.VA_RATES, SourceType.BAH_RATES, SourceType.MILITARY_PAY}

# Priority for LLM call ordering (higher = sooner)
_SOURCE_PRIORITY: dict[SourceType, int] = {
    SourceType.FEDERAL_REGISTER: 4,
    SourceType.VA_NEWS: 4,
    SourceType.DOD_NEWS: 3,
    SourceType.CONGRESS_VA: 3,
    SourceType.GOOGLE_NEWS: 2,
}


def _passes_prefilter(article: ExternalArticleEntry) -> bool:
    """Return True if the article headline/body contains at least one relevance keyword."""
    haystack = " ".join(
        [
            (article.headline or ""),
            (article.body_text or ""),
        ]
    ).lower()
    return any(kw in haystack for kw in RELEVANCE_KEYWORDS)


def _llm_priority(article: ExternalArticleEntry) -> int:
    try:
        src = SourceType(article.source) if not isinstance(article.source, SourceType) else article.source
    except ValueError:
        return 1
    return _SOURCE_PRIORITY.get(src, 1)


def _rule_based_analysis(article: ExternalArticleEntry) -> dict[str, Any]:
    """Return a pre-canned analysis dict for rate-table sources."""
    try:
        src = SourceType(article.source) if not isinstance(article.source, SourceType) else article.source
    except ValueError:
        src = None

    if src == SourceType.VA_RATES:
        angles = ["disability_ratings"]
    elif src == SourceType.BAH_RATES:
        angles = ["military_pay"]
    else:
        angles = ["military_pay"]

    return {
        "relevance_score": 3,
        "angles": angles,
        "sentiment": "mixed",
        "status": "monitoring",
        "category_label": "Rate Tables",
        "headline_short": (article.headline or "")[:80],
        "takeaway": "Rate table reference data updated — check VA.gov or DFAS for current rates.",
        "is_breaking": False,
        "source_trust": "official",
        "_rule_based": True,
    }


def _call_llm(article: ExternalArticleEntry) -> Optional[dict[str, Any]]:
    """Call the OpenAI API and return the parsed analysis dict, or None on error."""
    client = openai.OpenAI(api_key=settings.openai_api_key)

    body_snippet = (article.body_text or "")[:3000]
    user_msg = USER_PROMPT_TEMPLATE.format(
        source=str(article.source),
        published_date=str(article.published_date),
        headline=(article.headline or ""),
        body_text=body_snippet,
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=512,
        )
    except openai.OpenAIError as exc:
        logger.error("OpenAI error analyzing article id=%s: %s", article.id, exc)
        return None

    _LLM_USAGE["calls"] += 1
    usage = response.usage
    if usage:
        _LLM_USAGE["input_tokens"] += usage.prompt_tokens or 0
        _LLM_USAGE["output_tokens"] += usage.completion_tokens or 0

    raw = (response.choices[0].message.content or "").strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error for article id=%s: %s | raw=%r", article.id, exc, raw[:200])
        return None


def _partition_articles(
    articles: list[ExternalArticleEntry],
) -> tuple[list[ExternalArticleEntry], list[ExternalArticleEntry]]:
    """Split articles into (rule_based, llm_candidates).

    rule_based:    rate table sources — handled without LLM
    llm_candidates: everything else that passes the keyword prefilter, sorted by priority desc
    """
    rule_based: list[ExternalArticleEntry] = []
    llm_candidates: list[ExternalArticleEntry] = []

    for art in articles:
        try:
            src = SourceType(art.source) if not isinstance(art.source, SourceType) else art.source
        except ValueError:
            src = None

        if src in _RULE_BASED_SOURCES:
            rule_based.append(art)
        elif _passes_prefilter(art):
            llm_candidates.append(art)
        else:
            logger.debug("Prefilter dropped article id=%s headline=%r", art.id, art.headline)

    llm_candidates.sort(key=_llm_priority, reverse=True)
    return rule_based, llm_candidates


def _persist_analysis(
    db,
    article: ExternalArticleEntry,
    analysis: dict[str, Any],
) -> None:
    article.analysis_json = analysis
    article.status = GazetteStatus.ANALYZED
    db.add(article)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_analysis(
    lookback_days: Optional[int] = None,
    dry_run: bool = False,
    budget: Optional[int] = None,
) -> dict[str, Any]:
    """Analyze all pending ExternalArticleEntry rows.

    Args:
        lookback_days: Only consider articles published within this many days.
                       Defaults to settings.report_lookback_days.
        dry_run:       If True, print results but do not write to the database.
        budget:        Maximum number of LLM calls this run.
                       Defaults to settings.llm_call_budget_per_run.

    Returns:
        A summary dict with counts and token usage.
    """
    init_db()

    if lookback_days is None:
        lookback_days = settings.report_lookback_days
    if budget is None:
        budget = settings.llm_call_budget_per_run

    cutoff_date = date.today() - timedelta(days=lookback_days)

    summary: dict[str, Any] = {
        "articles_fetched": 0,
        "rule_based": 0,
        "llm_analyzed": 0,
        "llm_skipped_budget": 0,
        "prefilter_dropped": 0,
        "errors": 0,
    }

    db = SessionLocal()
    try:
        pending = (
            db.query(ExternalArticleEntry)
            .filter(
                ExternalArticleEntry.status == GazetteStatus.SCRAPED,
                ExternalArticleEntry.published_date >= cutoff_date,
            )
            .order_by(ExternalArticleEntry.published_date.desc())
            .all()
        )

        summary["articles_fetched"] = len(pending)
        logger.info("Analyzer: %d pending articles (lookback=%d days)", len(pending), lookback_days)

        rule_based, llm_candidates = _partition_articles(pending)
        summary["prefilter_dropped"] = len(pending) - len(rule_based) - len(llm_candidates)

        # --- Rule-based (rate tables) ---
        for art in rule_based:
            analysis = _rule_based_analysis(art)
            logger.debug("Rule-based article id=%s → score=%s", art.id, analysis.get("relevance_score"))
            if not dry_run:
                _persist_analysis(db, art, analysis)
            summary["rule_based"] += 1

        # --- LLM candidates ---
        llm_calls_used = 0
        for art in llm_candidates:
            if llm_calls_used >= budget:
                logger.warning(
                    "LLM budget exhausted (%d calls). %d articles skipped.",
                    budget,
                    len(llm_candidates) - llm_calls_used,
                )
                summary["llm_skipped_budget"] += len(llm_candidates) - llm_calls_used
                break

            analysis = _call_llm(art)
            llm_calls_used += 1

            if analysis is None:
                summary["errors"] += 1
                continue

            score = analysis.get("relevance_score", 0)
            logger.info(
                "Analyzed id=%s score=%s headline=%r",
                art.id,
                score,
                (art.headline or "")[:60],
            )

            if not dry_run:
                _persist_analysis(db, art, analysis)
            summary["llm_analyzed"] += 1

        if not dry_run:
            db.commit()

        # Cost estimate
        usage = get_usage()
        cost_usd = (
            usage["input_tokens"] / 1_000_000 * settings.llm_input_price_per_mtok
            + usage["output_tokens"] / 1_000_000 * settings.llm_output_price_per_mtok
        )
        summary["llm_calls"] = usage["calls"]
        summary["input_tokens"] = usage["input_tokens"]
        summary["output_tokens"] = usage["output_tokens"]
        summary["estimated_cost_usd"] = round(cost_usd, 4)

        logger.info(
            "Analyzer done — rule_based=%d llm_analyzed=%d errors=%d "
            "tokens_in=%d tokens_out=%d est_cost=$%.4f",
            summary["rule_based"],
            summary["llm_analyzed"],
            summary["errors"],
            usage["input_tokens"],
            usage["output_tokens"],
            cost_usd,
        )

    finally:
        db.close()

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Run VA/military benefits article analyzer")
    parser.add_argument("--dry", action="store_true", help="Dry run — do not write to DB")
    parser.add_argument("--lookback", type=int, default=None, help="Override lookback_days")
    parser.add_argument("--budget", type=int, default=None, help="Override LLM call budget")
    args = parser.parse_args()

    result = run_analysis(
        lookback_days=args.lookback,
        dry_run=args.dry,
        budget=args.budget,
    )
    print(json.dumps(result, indent=2))
