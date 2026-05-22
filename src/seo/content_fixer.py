"""LLM-powered content fixer — improves meta descriptions and titles for low-traffic pages."""
from __future__ import annotations
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.models import BlogPost, LandingPage, engine

logger = logging.getLogger(__name__)

MAX_FIXES_PER_RUN = 5

SYSTEM_PROMPT = """\
You are an SEO copywriter for VA Claims Workspace, a site about VA disability claims and \
military benefits. Given a page title and body excerpt, rewrite the meta description to be \
compelling, accurate, and under 155 characters. Return only the meta description text — \
no quotes, no labels, no extra commentary.
"""


def _fix_description(title: str, excerpt: str, client) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Title: {title}\n\nExcerpt (first 400 chars): {excerpt[:400]}",
            },
        ],
        temperature=0.4,
        max_tokens=80,
    )
    return (resp.choices[0].message.content or "").strip()[:160]


def run_content_fixer(dry_run: bool = False) -> dict:
    from src.config import settings

    if not settings.openai_api_key:
        logger.info("content_fixer: skipping — no OPENAI_API_KEY")
        return {"status": "skipped", "fixes": 0}

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    fixes = 0

    with Session(engine) as session:
        cutoff = date.today() - timedelta(days=30)
        posts = (
            session.query(BlogPost)
            .filter(
                BlogPost.published_date >= cutoff,
                (BlogPost.seo_description == None) | (BlogPost.seo_description == ""),
            )
            .order_by(BlogPost.published_date.desc())
            .limit(MAX_FIXES_PER_RUN)
            .all()
        )

        for post in posts:
            if fixes >= MAX_FIXES_PER_RUN:
                break
            excerpt = (post.content or post.summary or "")
            if not excerpt:
                continue
            try:
                if dry_run:
                    logger.info("content_fixer: dry_run — would fix: %s", post.title)
                    fixes += 1
                    continue
                new_desc = _fix_description(post.title, excerpt, client)
                post.seo_description = new_desc
                session.add(post)
                fixes += 1
                logger.info("content_fixer: fixed description for %s", post.slug)
            except Exception as exc:
                logger.warning("content_fixer: error for %s: %s", post.slug, exc)

        if not dry_run:
            session.commit()

    return {"status": "ok", "fixes": fixes}
