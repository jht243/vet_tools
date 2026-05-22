"""Press radar — identifies today's most significant VA/military news for editorial use."""
from __future__ import annotations
import json
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models import ExternalArticleEntry, SourceType, engine

logger = logging.getLogger(__name__)

PRIMARY_SOURCES = {
    SourceType.VA_NEWS,
    SourceType.DOD_NEWS,
    SourceType.FEDERAL_REGISTER,
    SourceType.CONGRESS_VA,
}

SYSTEM_PROMPT = """\
You are an editorial assistant for VA Claims Workspace, a site covering VA benefits, \
military compensation, and veteran policy.

Your job is to identify the 3-5 most significant news items from today's sources. \
Prioritize: official VA/DoD announcements, new legislation affecting veterans, \
significant disability-rate or pay-table changes, and PACT Act/burn-pit updates. \
Deprioritize: general military news without direct benefits impact.

Return a JSON array (no markdown fences) of objects with:
  { "rank": 1-5, "title": "...", "why_matters": "1-2 sentence plain-English explanation", \
"source": "...", "url": "..." }

Rank 1 = most significant to a veteran trying to understand their benefits today.
"""


def _fetch_today_articles(session: Session, lookback_days: int = 1) -> list[ExternalArticleEntry]:
    cutoff = date.today() - timedelta(days=lookback_days)
    return (
        session.query(ExternalArticleEntry)
        .filter(ExternalArticleEntry.published_date >= cutoff)
        .order_by(ExternalArticleEntry.published_date.desc())
        .limit(60)
        .all()
    )


def _prioritize(articles: list[ExternalArticleEntry]) -> list[ExternalArticleEntry]:
    primary = [a for a in articles if a.source_type in PRIMARY_SOURCES]
    secondary = [a for a in articles if a.source_type not in PRIMARY_SOURCES]
    return (primary + secondary)[:30]


def run_press_radar(dry_run: bool = False) -> Optional[list[dict]]:
    from src.config import settings

    if not settings.openai_api_key:
        logger.info("press_radar: skipping — no OPENAI_API_KEY")
        return None

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    with Session(engine) as session:
        articles = _fetch_today_articles(session)

    if not articles:
        logger.info("press_radar: no articles found for today")
        return []

    articles = _prioritize(articles)
    lines = []
    for a in articles:
        lines.append(
            f"- [{a.source_type}] {a.title} | {a.url} | pub={a.published_date}"
        )
    user_content = "Today's VA/military headlines:\n" + "\n".join(lines)

    if dry_run:
        logger.info("press_radar: dry_run — would send %d articles to LLM", len(articles))
        return None

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        items = json.loads(raw)
        logger.info("press_radar: identified %d top items", len(items))
        return items
    except Exception as exc:
        logger.warning("press_radar: LLM call failed: %s", exc)
        return None
