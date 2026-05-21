"""
LLM-powered analysis for scraped AI news articles.

Reads entries with status=SCRAPED from the database, sends each to GPT-4o
with an AI-backlash-focused prompt, and stores structured analysis in
analysis_json. Only entries scoring above the relevance threshold make it
into the briefing pipeline.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta

from openai import OpenAI

from src.config import settings
from src.models import (
    SessionLocal,
    ExternalArticleEntry,
    ArticleStatus,
    SourceType,
)

logger = logging.getLogger(__name__)

LLM_CALL_BUDGET_PER_RUN = settings.llm_call_budget_per_run


# Module-level usage accumulator so callers can read token totals after a
# batch and log estimated cost. Reset with reset_usage().
_LLM_USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


def reset_usage() -> None:
    _LLM_USAGE.update({"calls": 0, "input_tokens": 0, "output_tokens": 0})


def get_usage() -> dict:
    """Current accumulated LLM usage with estimated USD cost."""
    in_cost = _LLM_USAGE["input_tokens"] / 1_000_000 * settings.llm_input_price_per_mtok
    out_cost = _LLM_USAGE["output_tokens"] / 1_000_000 * settings.llm_output_price_per_mtok
    return {
        **_LLM_USAGE,
        "estimated_cost_usd": round(in_cost + out_cost, 4),
    }


RELEVANCE_KEYWORDS = (
    "ai act", "eu ai act", "regulation", "law", "rights",
    "lawsuit", "class action", "workers", "union",
    "layoffs", "laid off", "job loss", "job displacement", "replacing workers",
    "automation", "workforce", "unemployment", "gig workers",
    "education", "schools", "students", "teachers", "cheating",
    "kids", "children", "parents", "teens", "mental health",
    "deepfake", "misinformation", "disinformation", "ai slop",
    "data center water", "ai water", "ai energy", "electricity",
    "ai ethics", "ai safety", "ai risk", "ai backlash", "anti-ai",
    "surveillance", "facial recognition", "privacy", "data collection",
    "housing", "healthcare", "benefits", "social services",
    "wages", "income", "cost of living", "consumer",
)

SYSTEM_PROMPT = """You are a senior analyst for "Ban the Bots," a citizen-first site covering how AI affects everyday people — not businesses or investors. Stance: skeptical but fair — human-first, not anti-technology. Audience: workers worried about job security, parents navigating AI and their kids, students, teachers, and regular people trying to understand how AI is changing their lives.

Return JSON:
{
  "relevance_score": <int 1-10>,
  "angles": [<list from: jobs_labor, regulation_policy, environment_energy, content_quality, ai_incidents, parenting_education, civil_rights, backlash_protest>],
  "sentiment": "<concern|neutral|reassurance|mixed>",
  "category_label": "<e.g. 'Jobs & Labor', 'AI Regulation', 'Kids & Education', 'Environment & Energy', 'Civil Rights', 'AI Harms'>",
  "headline_short": "<max 80 chars>",
  "takeaway": "<2-4 sentences for an everyday person; wrap the key sentence in <strong>. No markdown.>",
  "risk_type": "<job_loss|privacy|education|health|environment|civil_rights|content_quality|regulatory|none>",
  "is_breaking": <bool>,
  "source_trust": "<official|tier1|tier2>"
}

Score 8-10 for stories that directly affect workers, families, students, or communities — job losses, layoffs, school AI policies, regulation that protects or harms people, AI surveillance, deepfakes affecting real people.
Score 6-7 for meaningful policy changes, significant labor actions, or AI incidents with real human impact.
Score 4-5 for background trends and context that helps people understand the bigger picture.
Score 1-3 for AI cybersecurity, enterprise IT, investor news, or technical research with no direct human impact.
DEPRIORITIZE: AI security vulnerabilities, enterprise compliance, AI model benchmarks, startup funding rounds, chip shortages, B2B software news.
Return ONLY the JSON object."""

USER_PROMPT_TEMPLATE = """Analyze this article for AI business risk relevance:

SOURCE: {source_name} ({credibility})
DATE: {published_date}
HEADLINE: {headline}
URL: {source_url}

BODY:
{body_text}"""


def run_analysis() -> dict:
    """
    Analyze all unprocessed entries in the database.
    Returns a summary dict with counts.
    """
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY not set — skipping analysis")
        return {"analyzed": 0, "skipped": 0, "errors": 0}

    client = OpenAI(api_key=settings.openai_api_key)
    db = SessionLocal()

    reset_usage()
    summary = {"analyzed": 0, "skipped": 0, "errors": 0}

    try:
        ext_articles = (
            db.query(ExternalArticleEntry)
            .filter(ExternalArticleEntry.status == ArticleStatus.SCRAPED)
            .filter(
                ExternalArticleEntry.published_date
                >= date.today() - timedelta(days=settings.report_lookback_days)
            )
            .all()
        )

        logger.info("Analysis queue: %d external articles", len(ext_articles))

        rule_based, llm_candidates = _partition_articles(ext_articles)

        logger.info(
            "Partitioned: %d rule-based, %d LLM candidates | budget=%d",
            len(rule_based),
            len(llm_candidates),
            LLM_CALL_BUDGET_PER_RUN,
        )

        for article in rule_based:
            try:
                article.analysis_json = _rule_based_analysis(article)
                article.status = ArticleStatus.ANALYZED
                summary["analyzed"] += 1
            except Exception as e:
                logger.error("Rule-based analysis failed for article %d: %s", article.id, e)
                summary["errors"] += 1
        db.commit()
        logger.info(
            "Rule-based pass: %d entries marked analyzed (no LLM cost)",
            len(rule_based),
        )

        llm_budget = LLM_CALL_BUDGET_PER_RUN

        for article in llm_candidates:
            if llm_budget <= 0:
                logger.info("LLM budget exhausted; skipping rest")
                summary["skipped"] += 1
                continue
            try:
                analysis = _analyze_article(
                    client,
                    headline=article.headline,
                    body_text=article.body_text or "",
                    source_name=article.source_name or "Unknown",
                    credibility=article.credibility.value if article.credibility else "tier2",
                    published_date=str(article.published_date),
                    source_url=article.source_url,
                )
                article.analysis_json = analysis
                article.status = ArticleStatus.ANALYZED
                db.commit()
                summary["analyzed"] += 1
                llm_budget -= 1
                logger.info(
                    "LLM analyzed [budget %d left]: %s (score=%s)",
                    llm_budget,
                    article.headline[:60],
                    analysis.get("relevance_score", "?"),
                )
            except Exception as e:
                logger.error("Analysis failed for article %d: %s", article.id, e)
                summary["errors"] += 1
                db.rollback()

            time.sleep(0.5)

        db.commit()

    finally:
        db.close()

    usage = get_usage()
    summary["llm_usage"] = usage
    logger.info(
        "Analysis complete: analyzed=%d skipped=%d errors=%d | "
        "LLM calls=%d input_tok=%d output_tok=%d est_cost=$%.4f",
        summary["analyzed"],
        summary["skipped"],
        summary["errors"],
        usage["calls"],
        usage["input_tokens"],
        usage["output_tokens"],
        usage["estimated_cost_usd"],
    )
    return summary


def _partition_articles(articles: list) -> tuple[list, list]:
    """Split articles into (rule_based, llm_candidates).

    Rule-based: AI_INCIDENT_DB gets a fixed score (already structured data).
    LLM candidates: must clear a keyword pre-screen, sorted by priority.
    """
    rule_based = []
    llm_candidates = []

    for a in articles:
        if a.source == SourceType.AI_INCIDENT_DB:
            rule_based.append(a)
            continue

        if not _passes_prefilter(a):
            rule_based.append(a)
            continue

        llm_candidates.append(a)

    llm_candidates.sort(key=_llm_priority, reverse=True)
    return rule_based, llm_candidates


def _passes_prefilter(article) -> bool:
    """Cheap heuristic: must look AI-relevant before we pay for an LLM call."""
    text = f"{article.headline or ''} {article.body_text or ''}".lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def _llm_priority(article) -> tuple:
    """Higher tuple = analyzed first when budget is tight."""
    source_rank = {
        SourceType.EU_AI_ACT: 4,
        SourceType.FTC_AI: 4,
        SourceType.CONGRESS_AI: 3,
        SourceType.NIST_RMF: 3,
        SourceType.BLS_LABOR: 3,
        SourceType.GOOGLE_NEWS: 2,
        SourceType.ARXIV_AI: 2,
        SourceType.SEJ_ALGO: 2,
    }.get(article.source, 1)
    tone_magnitude = abs(article.tone_score) if article.tone_score is not None else 0
    return (source_rank, tone_magnitude)


def _rule_based_analysis(article) -> dict:
    """Templated analysis for high-volume, low-variance sources."""
    if article.source == SourceType.AI_INCIDENT_DB:
        meta = article.extra_metadata or {}
        title = (meta.get("title") or article.headline or "Unknown incident")[:80]
        harm = meta.get("harm_type") or "unspecified harm"
        return {
            "relevance_score": 6,
            "angles": ["ai_incidents"],
            "sentiment": "concern",
            "category_label": "AI Incident",
            "headline_short": title,
            "takeaway": (
                f"<strong>An AI incident has been logged involving {harm}.</strong> "
                "This entry is auto-tagged from the AI Incident Database. "
                "Full analysis available in the briefing."
            ),
            "risk_type": "reputational",
            "is_breaking": False,
            "source_trust": "tier1",
            "_rule_based": True,
        }

    return {
        "relevance_score": 2,
        "angles": [],
        "sentiment": "neutral",
        "category_label": "Background",
        "headline_short": (article.headline or "")[:80],
        "takeaway": "Routine entry — flagged below relevance threshold by pre-screen.",
        "risk_type": "none",
        "is_breaking": False,
        "source_trust": "tier2",
        "_rule_based": True,
    }


def _analyze_article(
    client: OpenAI,
    headline: str,
    body_text: str,
    source_name: str,
    credibility: str,
    published_date: str,
    source_url: str,
) -> dict:
    body_truncated = body_text[:3000] if body_text else "(no body text available)"

    user_msg = USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        credibility=credibility,
        published_date=published_date,
        headline=headline,
        source_url=source_url,
        body_text=body_truncated,
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=600,
        response_format={"type": "json_object"},
    )

    usage = getattr(response, "usage", None)
    if usage is not None:
        _LLM_USAGE["calls"] += 1
        _LLM_USAGE["input_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        _LLM_USAGE["output_tokens"] += getattr(usage, "completion_tokens", 0) or 0

    raw = response.choices[0].message.content
    return json.loads(raw)
