"""
Long-form blog post (briefing) generator.

For each high-relevance ExternalArticleEntry (relevance_score >= threshold)
that doesn't yet have a corresponding BlogPost row, runs a single LLM call
that produces a 700-900 word AI-risk briefing ready to render at
/briefing/{slug}.

Costs:
    ~2.5k input tokens + ~1.8k output tokens per post
    -> ~$0.025 input + $0.018 output = ~$0.04/post
    -> default budget 6/run = ~$0.25/run
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

from openai import OpenAI

from src.analyzer import _LLM_USAGE
from src.config import settings
from src.models import (
    BlogPost,
    ExternalArticleEntry,
    ArticleStatus,
    SessionLocal,
    init_db,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots." Voice: plain-English, journalistic, no buzzwords. Cite specific regulation names, companies, dollar figures, job counts. Stance: skeptical but fair — human-first, not anti-technology. Audience: everyday people — workers worried about job security, parents navigating AI and their kids, students, teachers, and anyone trying to understand how AI is changing their daily lives. Do NOT write for business owners, investors, or IT professionals.

You MUST return a single JSON object with these exact fields:
- title (string, STRICT 45-58 chars, front-load the human impact — Google SERPs cut around 60 chars)
- subtitle (string, 80-130 chars, expands the title with the human angle)
- summary (string, STRICT 120-150 chars, plain text meta description — lead with the concrete human impact)
- body_html (string, 1000-1200 words minimum — ONLY <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <a href> tags. MUST include 2-3 internal links from the INTERNAL LINK TARGETS provided.)
- keywords (array of 8-12 lowercase phrases, mix of head terms and long-tail — include year and everyday-person search terms like "will ai take my job", "ai and kids", "how does ai affect me")
- primary_angle (string, one of: jobs_labor, regulation_policy, environment_energy, content_quality, ai_incidents, parenting_education, civil_rights, backlash_protest)
- key_takeaways (array of 4-5 plain-text bullet sentences, each a concrete insight an everyday person can act on)

BODY STRUCTURE (use these <h2> sections in order):
1. Lead paragraph — the news, the number, who it affects. No throat-clearing.
2. <h2>What Happened</h2> — 2-3 paragraphs of context and background
3. <h2>How This Affects Everyday People</h2> — specific implications for workers, families, students, or communities; use relatable examples, not corporate scenarios
4. <h2>The Bigger Picture</h2> — connect to wider trend; cite 1-2 related developments
5. <h2>What You Can Do</h2> — 3-5 concrete, accessible steps for regular people as <ul><li> list
6. <h2>The Bottom Line</h2> — 1 paragraph forward-looking close

INTERNAL LINKS: Use 2-3 <a href="/path/"> links within body text. Use natural anchor text (not "click here"). Only link to paths provided in INTERNAL LINK TARGETS.

Do NOT use markdown. Do NOT wrap output in code fences. Output only the JSON object."""


# Angle → internal pages to link from body text.
_ANGLE_INTERNAL_LINKS: dict[str, list[tuple[str, str]]] = {
    "jobs_labor": [
        ("/explainers/ai-jobs", "how AI is displacing jobs"),
        ("/ai-layoffs/", "AI layoffs tracker"),
        ("/will-ai-replace-my-job/", "will AI replace your job"),
        ("/ai-proof-jobs/", "jobs AI can't replace"),
    ],
    "regulation_policy": [
        ("/explainers/eu-ai-act", "what the EU AI Act means for you"),
        ("/explainers/ai-regulation", "AI regulation explained"),
        ("/ai-backlash/", "the growing AI backlash"),
        ("/fighting-back/", "how people are fighting back against AI"),
    ],
    "environment_energy": [
        ("/explainers/data-center-impact", "AI's water and energy footprint"),
        ("/data-center-map/", "AI data centers near you"),
        ("/ai-backlash/", "why people are pushing back on AI"),
        ("/explainers/ai-water-use", "how much water AI uses"),
    ],
    "content_quality": [
        ("/explainers/ai-slop", "what is AI slop"),
        ("/no-ai-policy-template/", "how to create a no-AI policy"),
        ("/fighting-back/", "how to fight back against AI"),
        ("/ai-backlash/", "the AI backlash explained"),
    ],
    "ai_incidents": [
        ("/ai-backlash/", "documented AI harms"),
        ("/explainers/deepfakes", "what are deepfakes"),
        ("/explainers/facial-recognition", "facial recognition and wrongful arrests"),
        ("/fighting-back/", "how people are pushing back"),
    ],
    "parenting_education": [
        ("/parents/", "parenting in the age of AI"),
        ("/parents/ai-safety/", "keeping kids safe from AI"),
        ("/parents/what-to-study/", "what skills kids need for the future"),
        ("/parents/screen-time/", "AI and screen time for kids"),
    ],
    "civil_rights": [
        ("/explainers/facial-recognition", "facial recognition and your rights"),
        ("/explainers/autonomous-weapons", "autonomous weapons explained"),
        ("/ai-backlash/", "why people are pushing back on AI"),
        ("/fighting-back/", "how to resist AI surveillance"),
    ],
    "backlash_protest": [
        ("/fighting-back/", "how people are fighting back against AI"),
        ("/ai-backlash/", "the AI backlash movement"),
        ("/no-ai-policy-template/", "no-AI policy template"),
        ("/ai-lawsuits/", "AI lawsuits and legal challenges"),
    ],
}
_DEFAULT_INTERNAL_LINKS = [
    ("/ai-backlash/", "the growing AI backlash"),
    ("/fighting-back/", "how people are pushing back"),
    ("/will-ai-replace-my-job/", "will AI replace your job"),
]


USER_PROMPT_TEMPLATE = """Write a long-form briefing post about the following development, from the perspective of how it affects everyday people.

SOURCE: {source_name} ({credibility})
PUBLISHED: {published_date}
URL: {source_url}
HEADLINE: {headline}
ANALYST SUMMARY: {headline_short}

ANALYST TAKEAWAY:
{takeaway}

ANGLES: {angles}
SENTIMENT: {sentiment}
RELEVANCE SCORE: {relevance}/10

SOURCE BODY (truncated):
{body_text}

INTERNAL LINK TARGETS (use 2-3 of these as <a href="/path/"> in body text with natural anchor text):
{internal_links}

Follow the 6-section body structure from your instructions. Minimum 1000 words. Be specific: name the regulation, company, dollar figure, or job count — never be vague. Write for workers, parents, students, and regular people — not business owners or investors. The "What You Can Do" section must have at least 3 actionable steps an everyday person could take."""


_ALLOWED_TAGS_RE = re.compile(
    r"<\s*/?\s*(h2|h3|h4|p|ul|ol|li|strong|em|b|i|blockquote|a|dl|dt|dd)(\s+[^>]*)?\s*/?\s*>",
    re.IGNORECASE,
)
_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _slugify(text: str, *, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len] or "briefing"


def _count_words(html: str) -> int:
    text = _ANY_TAG_RE.sub(" ", html or "")
    return len([w for w in text.split() if w])


def _sanitize_body_html(html: str) -> str:
    """Drop any tags that aren't on the allow-list."""
    if not html:
        return ""

    def _replace(match: re.Match) -> str:
        if _ALLOWED_TAGS_RE.fullmatch(match.group(0)):
            return match.group(0)
        return ""

    return _ANY_TAG_RE.sub(_replace, html)


def _candidate_external(db) -> list[ExternalArticleEntry]:
    cutoff = date.today() - timedelta(days=settings.blog_gen_lookback_days)
    rows = (
        db.query(ExternalArticleEntry)
        .filter(ExternalArticleEntry.status == ArticleStatus.ANALYZED)
        .filter(ExternalArticleEntry.published_date >= cutoff)
        .order_by(ExternalArticleEntry.published_date.desc())
        .all()
    )
    out = []
    for r in rows:
        analysis = r.analysis_json or {}
        if analysis.get("relevance_score", 0) < settings.blog_gen_min_relevance:
            continue
        out.append(r)
    return out


def _existing_blog_keys(db) -> set[tuple[str, int]]:
    return {
        (row.source_table, row.source_id)
        for row in db.query(BlogPost.source_table, BlogPost.source_id).all()
    }


# ---------------------------------------------------------------------------
# Topic-level deduplication — prevents near-duplicate posts from different
# outlets covering the same event.
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that"
    " the this to was were will with ai artificial intelligence".split()
)


def _rough_stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in ("ing", "tion", "sion", "ment", "ness", "ous", "ive", "ful"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)]
    if word.endswith("es") and len(word) > 3:
        return word[:-2]
    if word.endswith("ed") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _headline_tokens(text: str) -> set[str]:
    words = re.sub(r"[^a-z0-9\s]", "", (text or "").lower()).split()
    return {_rough_stem(w) for w in words if w and w not in _STOP_WORDS and len(w) > 1}


def _topic_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _recent_blog_headlines(db, *, days: int = 7) -> list[tuple[str, set[str]]]:
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(BlogPost.title)
        .filter(BlogPost.published_date >= cutoff)
        .all()
    )
    return [(r.title, _headline_tokens(r.title)) for r in rows]


_DEDUP_HARD_THRESHOLD = 0.75
_DEDUP_SOFT_THRESHOLD = 0.55

_DEDUP_JUDGE_PROMPT = """You are a deduplication judge for an AI business risk news site.

Two headlines are shown below. Decide whether CANDIDATE covers substantially the same event, policy action, or corporate development as EXISTING — meaning a reader who read EXISTING would learn nothing new from CANDIDATE.

If they cover the same underlying event (even with different framing), answer DUPLICATE.
If they cover genuinely different events, incidents, or regulatory actions, answer UNIQUE.

EXISTING: {existing}
CANDIDATE: {candidate}

Reply with a single word: DUPLICATE or UNIQUE."""


def _llm_dedup_judge(
    client: OpenAI,
    candidate: str,
    existing: str,
) -> bool:
    try:
        resp = client.chat.completions.create(
            model=settings.openai_narrative_model,
            messages=[{
                "role": "user",
                "content": _DEDUP_JUDGE_PROMPT.format(
                    existing=existing, candidate=candidate,
                ),
            }],
            temperature=0,
            max_tokens=4,
        )
        answer = (resp.choices[0].message.content or "").strip().upper()
        is_dup = "DUPLICATE" in answer
        usage = getattr(resp, "usage", None)
        if usage is not None:
            _LLM_USAGE["calls"] += 1
            _LLM_USAGE["input_tokens"] += getattr(usage, "prompt_tokens", 0)
            _LLM_USAGE["output_tokens"] += getattr(usage, "completion_tokens", 0)
        logger.info(
            "blog_generator: dedup judge %r vs %r → %s",
            candidate[:60], existing[:60], answer,
        )
        return is_dup
    except Exception as exc:
        logger.warning("blog_generator: dedup judge failed, treating as unique: %s", exc)
        return False


def _is_topic_duplicate(
    headline: str,
    recent: list[tuple[str, set[str]]],
    *,
    client: OpenAI | None = None,
) -> str | None:
    tokens = _headline_tokens(headline)
    for existing_title, existing_tokens in recent:
        score = _topic_similarity(tokens, existing_tokens)
        if score >= _DEDUP_HARD_THRESHOLD:
            return existing_title
        if score >= _DEDUP_SOFT_THRESHOLD and client is not None:
            if _llm_dedup_judge(client, headline, existing_title):
                return existing_title
    return None


def _build_post_payload(
    client: OpenAI,
    *,
    source_name: str,
    credibility: str,
    published_date: str,
    source_url: str,
    headline: str,
    headline_short: str,
    takeaway: str,
    angles: list[str],
    sentiment: str,
    relevance: int,
    body_text: str,
) -> tuple[dict, dict]:
    body_truncated = (body_text or "")[:6000] or "(no body text available)"

    # Pick internal link targets based on primary angle
    primary_angle = angles[0] if angles else ""
    link_targets = _ANGLE_INTERNAL_LINKS.get(primary_angle, _DEFAULT_INTERNAL_LINKS)
    internal_links_text = "\n".join(f"  {path}  ({label})" for path, label in link_targets)

    user_msg = USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        credibility=credibility,
        published_date=published_date,
        source_url=source_url,
        headline=headline,
        headline_short=headline_short or headline,
        takeaway=takeaway or "(none)",
        angles=", ".join(angles) if angles else "(none)",
        sentiment=sentiment or "mixed",
        relevance=relevance,
        body_text=body_truncated,
        internal_links=internal_links_text,
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.4,
        max_tokens=3500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    if usage is not None:
        _LLM_USAGE["calls"] += 1
        _LLM_USAGE["input_tokens"] += in_tok or 0
        _LLM_USAGE["output_tokens"] += out_tok or 0

    cost = (
        (in_tok or 0) / 1_000_000 * settings.llm_input_price_per_mtok
        + (out_tok or 0) / 1_000_000 * settings.llm_output_price_per_mtok
    )
    return parsed, {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 6),
        "model": settings.openai_model,
    }


def _entry_metadata(item: ExternalArticleEntry) -> dict:
    analysis = item.analysis_json or {}
    meta = item.extra_metadata or {}

    source_name = meta.get("publisher") or item.source_name or item.source.value
    credibility = (item.credibility.value if item.credibility else "tier2").upper()

    return {
        "source_name": source_name,
        "credibility": credibility,
        "headline_short": analysis.get("headline_short", ""),
        "takeaway": analysis.get("takeaway", ""),
        "angles": analysis.get("angles", []) or [],
        "sentiment": analysis.get("sentiment", "mixed"),
        "relevance": analysis.get("relevance_score", 0),
    }


def _persist_post(
    db,
    *,
    source_table: str,
    source_id: int,
    item: ExternalArticleEntry,
    payload: dict,
    usage: dict,
) -> BlogPost:
    body_html = _sanitize_body_html(payload.get("body_html", ""))
    word_count = _count_words(body_html)
    reading_minutes = max(1, round(word_count / 220))

    title = (payload.get("title") or item.headline)[:300]
    slug_base = _slugify(title)
    slug = f"{slug_base}-{item.published_date.strftime('%Y%m%d')}-{source_id}"

    keywords = payload.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    primary_sector = payload.get("primary_angle") or None
    if isinstance(primary_sector, str):
        primary_sector = primary_sector[:80]

    raw_takeaways = payload.get("key_takeaways") or []
    if isinstance(raw_takeaways, str):
        raw_takeaways = [raw_takeaways]
    takeaways: list[str] = []
    for t in raw_takeaways:
        if not isinstance(t, str):
            continue
        cleaned = re.sub(r"<[^>]+>", "", t).strip()
        if not cleaned:
            continue
        if len(cleaned) > 300:
            cleaned = cleaned[:300].rstrip()
        takeaways.append(cleaned)
        if len(takeaways) >= 5:
            break

    post = BlogPost(
        source_table=source_table,
        source_id=source_id,
        slug=slug,
        title=title,
        subtitle=(payload.get("subtitle") or "")[:500],
        summary=(payload.get("summary") or "")[:600],
        body_html=body_html,
        primary_sector=primary_sector,
        sectors_json=payload.get("angles") or [],
        keywords_json=keywords,
        related_slugs_json=[],
        takeaways_json=takeaways or None,
        word_count=word_count,
        reading_minutes=reading_minutes,
        published_date=item.published_date,
        canonical_source_url=item.source_url,
        llm_model=usage.get("model"),
        llm_input_tokens=usage.get("input_tokens"),
        llm_output_tokens=usage.get("output_tokens"),
        llm_cost_usd=usage.get("cost_usd"),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Render per-briefing OG card — best-effort, failure never blocks the post.
    try:
        from src.og_image import render_briefing_card

        png = render_briefing_card(
            title=post.title or "",
            category=post.primary_sector,
            published_date=post.published_date,
        )
        if png:
            post.og_image_bytes = png
            db.commit()
            db.refresh(post)
    except Exception as exc:
        logger.warning("blog_generator: og card render failed for slug=%s: %s", post.slug, exc)

    return post


_CURATOR_SYSTEM = """You are the editorial director of "Ban the Bots," an AI risk news site for SMB owners.

Given a list of analyzed articles (with ID, score, angle, source, and headline), select the best articles to turn into full briefings today.

Rules:
1. Return EXACTLY {n} article IDs (or fewer if fewer candidates exist).
2. Maximise TOPIC DIVERSITY — at most 2 articles per angle category.
3. Prefer higher relevance scores, but a score-6 story on an underrepresented angle beats a score-8 story that duplicates today's coverage.
4. Prefer tier1 and official sources over tier2 when scores are similar.
5. Exclude articles whose headlines are near-identical to each other.

Return ONLY a JSON array of integer IDs, e.g. [12, 45, 7, ...]. No other text."""


def _llm_curate_candidates(
    client: OpenAI,
    candidates: list[ExternalArticleEntry],
    n: int,
) -> list[int]:
    """Single LLM call that acts as editor-in-chief, picking the best n IDs."""
    if len(candidates) <= n:
        return [c.id for c in candidates]

    lines = []
    for c in candidates:
        a = c.analysis_json or {}
        score = a.get("relevance_score", 0)
        angles = ", ".join(a.get("angles") or [a.get("primary_angle", "?")])
        trust = a.get("source_trust") or c.source_credibility or "?"
        headline = (a.get("headline_short") or c.headline or "")[:90]
        lines.append(f"ID={c.id} score={score} angle={angles} src={trust} | {headline}")

    prompt = (
        f"Select the best {n} articles for today's briefings.\n\n"
        + "\n".join(lines)
    )

    try:
        resp = client.chat.completions.create(
            model=settings.openai_narrative_model,
            messages=[
                {"role": "system", "content": _CURATOR_SYSTEM.format(n=n)},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=200,
        )
        raw = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        if usage:
            _LLM_USAGE["calls"] += 1
            _LLM_USAGE["input_tokens"] += getattr(usage, "prompt_tokens", 0)
            _LLM_USAGE["output_tokens"] += getattr(usage, "completion_tokens", 0)

        # Parse JSON array of ints from the response
        match = re.search(r"\[[\d,\s]+\]", raw)
        if match:
            ids = json.loads(match.group())
            valid_ids = {c.id for c in candidates}
            chosen = [i for i in ids if i in valid_ids]
            if chosen:
                logger.info("blog_generator: curator picked %d/%d candidates: %s",
                            len(chosen), len(candidates), chosen)
                return chosen[:n]
    except Exception as exc:
        logger.warning("blog_generator: curation LLM call failed, falling back to score sort: %s", exc)

    # Fallback: top-n by relevance score
    scored = sorted(candidates, key=lambda c: (c.analysis_json or {}).get("relevance_score", 0), reverse=True)
    return [c.id for c in scored[:n]]


def run_blog_generation(*, budget: int | None = None) -> dict:
    """
    Find candidate entries with no blog post yet, write up to `budget`
    posts, persist, return a summary dict.
    """
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set; skipping blog generation")
        return {"generated": 0, "skipped": "no_api_key"}

    init_db()
    db = SessionLocal()
    try:
        budget = budget if budget is not None else settings.blog_gen_budget_per_run
        if budget <= 0:
            return {"generated": 0, "skipped": "budget_zero"}

        existing = _existing_blog_keys(db)
        recent_headlines = _recent_blog_headlines(db, days=7)

        ext_candidates = [
            r for r in _candidate_external(db)
            if ("external_articles", r.id) not in existing
        ]

        client = OpenAI(api_key=settings.openai_api_key)

        # LLM editorial curation: pick the best `budget` from all candidates.
        # Falls back to score-sort if the LLM call fails.
        logger.info(
            "blog_generator: %d unwritten candidates → asking LLM to pick best %d",
            len(ext_candidates), budget,
        )
        chosen_ids = _llm_curate_candidates(client, ext_candidates, budget)
        chosen_set = set(chosen_ids)

        # Build ordered list of chosen items, preserving curator order.
        id_to_item = {c.id: c for c in ext_candidates}
        ordered = [id_to_item[i] for i in chosen_ids if i in id_to_item]

        generated = 0
        failed = 0
        skipped_dupes = 0
        total_cost = 0.0
        slugs: list[str] = []

        for item in ordered:
            if generated >= budget:
                break

            relevance = int((item.analysis_json or {}).get("relevance_score", 0))
            headline = (item.analysis_json or {}).get("headline_short") or item.headline or ""
            dup_of = _is_topic_duplicate(headline, recent_headlines, client=client)
            if dup_of:
                logger.info(
                    "blog_generator: skipping external_articles/%d — topic duplicate of %r",
                    item.id, dup_of,
                )
                skipped_dupes += 1
                continue

            meta = _entry_metadata(item)
            try:
                payload, usage = _build_post_payload(
                    client,
                    source_name=meta["source_name"],
                    credibility=meta["credibility"],
                    published_date=item.published_date.isoformat(),
                    source_url=item.source_url,
                    headline=item.headline,
                    headline_short=meta["headline_short"],
                    takeaway=meta["takeaway"],
                    angles=meta["angles"],
                    sentiment=meta["sentiment"],
                    relevance=meta["relevance"],
                    body_text=item.body_text or "",
                )
                post = _persist_post(
                    db,
                    source_table="external_articles",
                    source_id=item.id,
                    item=item,
                    payload=payload,
                    usage=usage,
                )
                generated += 1
                total_cost += usage.get("cost_usd") or 0.0
                slugs.append(post.slug)
                recent_headlines.append((post.title, _headline_tokens(post.title)))
                logger.info(
                    "blog_generator: wrote %s (relevance=%d, %d words, $%.4f)",
                    post.slug, relevance, post.word_count, usage.get("cost_usd") or 0.0,
                )
            except Exception as exc:
                logger.exception(
                    "blog_generator failed on external_articles/%d: %s", item.id, exc
                )
                failed += 1
                db.rollback()

        return {
            "generated": generated,
            "failed": failed,
            "skipped_topic_dupes": skipped_dupes,
            "candidates": len(ext_candidates),
            "curated": len(chosen_ids),
            "budget": budget,
            "estimated_cost_usd": round(total_cost, 4),
            "slugs": slugs,
        }
    finally:
        db.close()


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    )
    print(run_blog_generation())
