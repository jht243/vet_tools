"""
LLM-powered blog post generator for vet_tools.

Queries ExternalArticleEntry rows that have been analyzed (status=ANALYZED)
with a relevance score >= blog_gen_min_relevance and no existing BlogPost,
deduplicates near-duplicate topics, then calls the LLM to write long-form
700-900 word guides for veterans and military families.

Run via:
    python -m src.blog_generator          # generate and persist posts
    python -m src.blog_generator --dry    # print without writing
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
import unicodedata
from datetime import date, timedelta
from typing import Any, Optional

import openai
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.models import (
    BlogPost,
    ExternalArticleEntry,
    GazetteStatus,
    SessionLocal,
    init_db,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior policy writer creating long-form guides for veterans and military families navigating US benefits. Your audience is veterans filing VA disability claims, service members planning retirement, and military families managing benefits.

Your writing is:
- Plain English, journalistic, no bureaucratic jargon
- Concrete: cite specific CFR citations, VA form numbers, claim types, dollar amounts, deadlines
- Actionable: tell the reader what to DO, not just what happened
- 700-900 words total in the body
- Structured with HTML <h2> subheadings (3-5) and short <p> paragraphs (2-4 sentences each)

When relevant, link to these internal pages using <a href> tags:
- /va-claims/ (VA claims hub)
- /va-disability/ (disability ratings hub)
- /tools/va-disability-rating-calculator/ (combined rating calculator)
- /military-retirement/ (military retirement hub)
- /tools/bah-calculator/ (BAH calculator)
- /explainers/ (topic explainers index)

You MUST return a single JSON object with these fields:
- title (string, STRICT 45-58 chars, English, optimized for "VA claims / veterans benefits / disability rating" search intent. Front-load specific nouns: VA form numbers, condition names, benefit names.)
- subtitle (string, 80-130 chars, English, expands title with second-most-important angle)
- summary (string, STRICT 120-150 chars, plain text, meta description. Lead with concrete fact.)
- body_html (string, full post body — ONLY <h2>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <a href> tags)
- keywords (array of 6-10 lowercase phrases, mix of head terms and long-tail)
- primary_sector (string, one of: va_claims, disability_ratings, retirement, military_pay, legislation, appeals, pact_act, healthcare, other)
- key_takeaways (array of 3-5 short bullet sentences, plain text)
- investor_implications (string, 80-160 chars, "what this means for veterans and service members")
- social_hook (string, 180-250 chars — opening line of a social post. Voice: one VSO counselor to another. What changed, why it matters. No hashtags, no emoji, no exclamation marks.)

Do NOT use markdown. Output only the JSON object.\
"""

USER_PROMPT_TEMPLATE = """\
Write a long-form guide based on this US veterans benefits / VA policy / military compensation development.

Source: {source}
Published: {published_date}
Headline: {headline}
Relevance score: {relevance_score}/10
Angles: {angles}

Article body (may be truncated):
{body_text}

Analysis notes:
{takeaway}

Return ONLY the JSON object described in your instructions.\
"""

# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the and or but in on at to for of with by from as is are was were be been"
    " being have has had do does did will would could should may might shall can".split()
)


def _rough_stem(word: str) -> str:
    """Very lightweight suffix stripping — good enough for headline dedup."""
    for suffix in ("ing", "tion", "ions", "ion", "ment", "ments", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _headline_token_set(headline: str) -> frozenset[str]:
    tokens = re.sub(r"[^a-z0-9\s]", " ", headline.lower()).split()
    return frozenset(_rough_stem(t) for t in tokens if t not in _STOP_WORDS and len(t) > 2)


def _jaccard_headline(a: str, b: str) -> float:
    sa, sb = _headline_token_set(a), _headline_token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _batch_topic_dedup(
    candidates: list[ExternalArticleEntry],
    threshold: float = 0.55,
) -> list[ExternalArticleEntry]:
    """Greedy dedup: keep the first article in each near-duplicate cluster."""
    kept: list[ExternalArticleEntry] = []
    for cand in candidates:
        headline = cand.headline or ""
        is_dup = any(
            _jaccard_headline(headline, k.headline or "") >= threshold for k in kept
        )
        if not is_dup:
            kept.append(cand)
        else:
            logger.debug(
                "Dedup dropped id=%s headline=%r", cand.id, headline[:60]
            )
    return kept


# ---------------------------------------------------------------------------
# Slug / word count / HTML sanitizer
# ---------------------------------------------------------------------------

_ALLOWED_TAGS = re.compile(
    r"<(/?)(?:h2|p|ul|ol|li|strong|em|blockquote|a)(\s[^>]*)?>",
    re.IGNORECASE,
)


def _slugify(text: str) -> str:
    """Convert title to a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:120]


def _count_words(html: str) -> int:
    """Count words in body HTML (strip tags first)."""
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def _sanitize_body_html(raw: str) -> str:
    """Strip any tags not in the allowed list — leave allowed tags intact."""
    # Remove script/style blocks entirely
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.IGNORECASE)

    result: list[str] = []
    pos = 0
    for m in re.finditer(r"<[^>]+>", raw):
        # Text before this tag
        result.append(raw[pos : m.start()])
        tag = m.group()
        if _ALLOWED_TAGS.match(tag):
            result.append(tag)
        # else: drop the tag, but keep the text that follows
        pos = m.end()
    result.append(raw[pos:])
    return "".join(result)


def _existing_blog_keys(db) -> set[tuple[str, int]]:
    """Return set of (source_table, source_id) for already-written posts."""
    rows = db.query(BlogPost.source_table, BlogPost.source_id).all()
    return {(r.source_table, r.source_id) for r in rows}


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def _candidate_external(
    db,
    min_relevance: int,
    lookback_days: int,
    existing_keys: set[tuple[str, int]],
) -> list[ExternalArticleEntry]:
    """Query ExternalArticleEntry rows eligible for blog generation."""
    cutoff = date.today() - timedelta(days=lookback_days)
    rows = (
        db.query(ExternalArticleEntry)
        .filter(
            ExternalArticleEntry.status == GazetteStatus.ANALYZED,
            ExternalArticleEntry.published_date >= cutoff,
        )
        .order_by(ExternalArticleEntry.published_date.desc())
        .all()
    )

    eligible: list[ExternalArticleEntry] = []
    for row in rows:
        if ("external_articles", row.id) in existing_keys:
            continue
        analysis = row.analysis_json or {}
        score = analysis.get("relevance_score", 0)
        if score >= min_relevance:
            eligible.append(row)

    return eligible


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _call_llm(article: ExternalArticleEntry) -> Optional[dict[str, Any]]:
    client = openai.OpenAI(api_key=settings.openai_api_key)

    analysis = article.analysis_json or {}
    body_snippet = (article.body_text or "")[:4000]

    user_msg = USER_PROMPT_TEMPLATE.format(
        source=str(article.source),
        published_date=str(article.published_date),
        headline=(article.headline or ""),
        relevance_score=analysis.get("relevance_score", "?"),
        angles=", ".join(analysis.get("angles", [])),
        body_text=body_snippet,
        takeaway=analysis.get("takeaway", ""),
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            max_tokens=2048,
        )
    except openai.OpenAIError as exc:
        logger.error("OpenAI error for article id=%s: %s", article.id, exc)
        return None

    usage = response.usage
    input_tokens = (usage.prompt_tokens or 0) if usage else 0
    output_tokens = (usage.completion_tokens or 0) if usage else 0
    cost = (
        input_tokens / 1_000_000 * settings.llm_input_price_per_mtok
        + output_tokens / 1_000_000 * settings.llm_output_price_per_mtok
    )

    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse error for article id=%s: %s | raw=%r", article.id, exc, raw[:200]
        )
        return None

    data["_meta"] = {
        "llm_model": settings.openai_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
    }
    return data


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------


def _make_slug(title: str, db) -> str:
    """Generate a unique slug, appending a suffix if needed."""
    base = _slugify(title)
    slug = base
    suffix = 1
    while db.query(BlogPost.id).filter(BlogPost.slug == slug).first():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


def _persist_post(
    db,
    article: ExternalArticleEntry,
    data: dict[str, Any],
) -> Optional[BlogPost]:
    meta = data.pop("_meta", {})

    title = (data.get("title") or "")[:200]
    slug = _make_slug(title, db)
    body_html = _sanitize_body_html(data.get("body_html") or "")
    word_count = _count_words(body_html)
    reading_minutes = max(1, math.ceil(word_count / 200))

    post = BlogPost(
        source_table="external_articles",
        source_id=article.id,
        slug=slug,
        title=title,
        subtitle=(data.get("subtitle") or "")[:500] or None,
        summary=(data.get("summary") or "")[:500] or None,
        body_html=body_html,
        social_hook=(data.get("social_hook") or "")[:500] or None,
        primary_sector=data.get("primary_sector") or None,
        keywords_json=data.get("keywords") or [],
        takeaways_json=data.get("key_takeaways") or [],
        word_count=word_count,
        reading_minutes=reading_minutes,
        published_date=article.published_date,
        canonical_source_url=article.source_url,
        llm_model=meta.get("llm_model"),
        llm_input_tokens=meta.get("input_tokens"),
        llm_output_tokens=meta.get("output_tokens"),
        llm_cost_usd=meta.get("cost_usd"),
    )

    try:
        db.add(post)
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate blog post for article id=%s — skipping", article.id)
        return None

    return post


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_blog_generation(
    min_relevance: Optional[int] = None,
    lookback_days: Optional[int] = None,
    budget: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate blog posts for high-relevance external articles.

    Args:
        min_relevance: Minimum relevance_score to consider. Defaults to settings.blog_gen_min_relevance.
        lookback_days: How many days back to look. Defaults to settings.blog_gen_lookback_days.
        budget:        Maximum posts to generate this run. Defaults to settings.blog_gen_budget_per_run.
        dry_run:       If True, generate but do not write to the database.

    Returns:
        Summary dict with counts and cost estimates.
    """
    init_db()

    if min_relevance is None:
        min_relevance = settings.blog_gen_min_relevance
    if lookback_days is None:
        lookback_days = settings.blog_gen_lookback_days
    if budget is None:
        budget = settings.blog_gen_budget_per_run

    summary: dict[str, Any] = {
        "candidates_found": 0,
        "after_dedup": 0,
        "posts_generated": 0,
        "errors": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
    }

    db = SessionLocal()
    try:
        existing_keys = _existing_blog_keys(db)
        candidates = _candidate_external(db, min_relevance, lookback_days, existing_keys)
        summary["candidates_found"] = len(candidates)

        # Sort by relevance_score desc so highest-value articles go first
        candidates.sort(
            key=lambda a: (a.analysis_json or {}).get("relevance_score", 0),
            reverse=True,
        )

        deduped = _batch_topic_dedup(candidates)
        summary["after_dedup"] = len(deduped)

        logger.info(
            "Blog generator: %d candidates → %d after dedup (budget=%d)",
            len(candidates),
            len(deduped),
            budget,
        )

        posts_written = 0
        for article in deduped:
            if posts_written >= budget:
                logger.info("Blog budget reached (%d posts).", budget)
                break

            logger.info(
                "Generating post for article id=%s score=%s headline=%r",
                article.id,
                (article.analysis_json or {}).get("relevance_score", "?"),
                (article.headline or "")[:60],
            )

            data = _call_llm(article)
            if data is None:
                summary["errors"] += 1
                continue

            meta = data.get("_meta", {})
            summary["total_input_tokens"] += meta.get("input_tokens", 0)
            summary["total_output_tokens"] += meta.get("output_tokens", 0)
            summary["total_cost_usd"] += meta.get("cost_usd", 0.0)

            if not dry_run:
                post = _persist_post(db, article, data)
                if post:
                    logger.info("Persisted blog post slug=%r for article id=%s", post.slug, article.id)
                    posts_written += 1
                    summary["posts_generated"] += 1
            else:
                logger.info(
                    "[DRY RUN] Would write post title=%r for article id=%s",
                    (data.get("title") or "")[:60],
                    article.id,
                )
                posts_written += 1
                summary["posts_generated"] += 1

        if not dry_run:
            db.commit()

        summary["total_cost_usd"] = round(summary["total_cost_usd"], 4)
        logger.info(
            "Blog generator done — generated=%d errors=%d cost=$%.4f",
            summary["posts_generated"],
            summary["errors"],
            summary["total_cost_usd"],
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

    parser = argparse.ArgumentParser(description="Generate VA/military blog posts")
    parser.add_argument("--dry", action="store_true", help="Dry run — do not write to DB")
    parser.add_argument("--min-relevance", type=int, default=None)
    parser.add_argument("--lookback", type=int, default=None)
    parser.add_argument("--budget", type=int, default=None)
    args = parser.parse_args()

    result = run_blog_generation(
        min_relevance=args.min_relevance,
        lookback_days=args.lookback,
        budget=args.budget,
        dry_run=args.dry,
    )
    print(json.dumps(result, indent=2))
