"""
Landing-page generator. Produces evergreen, long-form HTML for:
  - the pillar page   (/ai-backlash/)
  - industry pages    (/responsible-ai/{slug}/)
  - explainers        (/explainers/{slug})

Pages target high-intent SEO queries ("AI backlash", "responsible AI in
healthcare", "what is the EU AI Act") and are regenerated weekly (or on
demand). Each generation uses the premium model so the language reads like
a senior analyst — different cost/quality trade-off from the daily news
churn handled by analyzer.py and blog_generator.py.

Output is persisted to the LandingPage table; Flask routes read from
there so the request path stays cheap.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta

from openai import OpenAI

from src.config import settings
from src.models import (
    BlogPost,
    ExternalArticleEntry,
    ArticleStatus,
    LandingPage,
    SessionLocal,
    init_db,
)


logger = logging.getLogger(__name__)


INDUSTRY_SLUGS = (
    "healthcare",
    "finance",
    "legal",
    "retail",
    "education",
    "manufacturing",
    "real-estate",
    "marketing",
)

_ALLOWED_TAGS_RE = re.compile(
    r"<\s*/?\s*(h2|h3|h4|p|ul|ol|li|strong|em|b|i|blockquote|a|table|thead|tbody|tr|th|td)(\s+[^>]*)?\s*/?\s*>",
    re.IGNORECASE,
)
_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize_body_html(html: str) -> str:
    if not html:
        return ""

    def _replace(match: re.Match) -> str:
        if _ALLOWED_TAGS_RE.fullmatch(match.group(0)):
            return match.group(0)
        return ""

    return _ANY_TAG_RE.sub(_replace, html)


def _count_words(html: str) -> int:
    text = _ANY_TAG_RE.sub(" ", html or "")
    return len([w for w in text.split() if w])


def _premium_call(client: OpenAI, *, system: str, user: str, max_tokens: int = 4500) -> tuple[str, dict]:
    """Single premium-model call. Returns (raw_json_string, usage_dict)."""
    model = settings.openai_premium_model
    is_gpt5 = model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")

    base_kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )

    if is_gpt5:
        base_kwargs["max_completion_tokens"] = max_tokens
    else:
        base_kwargs["max_tokens"] = max_tokens
        base_kwargs["temperature"] = 0.4

    response = client.chat.completions.create(**base_kwargs)
    raw = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    cost = (
        (in_tok or 0) / 1_000_000 * settings.llm_premium_input_price_per_mtok
        + (out_tok or 0) / 1_000_000 * settings.llm_premium_output_price_per_mtok
    )
    return raw, {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 4),
        "model": settings.openai_premium_model,
    }


def _gather_recent_signal(db, *, angles_filter: list[str] | None = None, limit: int = 25) -> dict:
    """
    Pull the freshest high-relevance briefing entries to feed the LLM as
    live context. Optionally filter by angle (jobs_labor, regulation_policy, etc.).
    """
    cutoff = date.today() - timedelta(days=90)

    ext = (
        db.query(ExternalArticleEntry)
        .filter(ExternalArticleEntry.status == ArticleStatus.ANALYZED)
        .filter(ExternalArticleEntry.published_date >= cutoff)
        .order_by(ExternalArticleEntry.published_date.desc())
        .limit(150)
        .all()
    )

    items = []
    for r in ext:
        analysis = r.analysis_json or {}
        if analysis.get("relevance_score", 0) < settings.analysis_min_relevance:
            continue
        angles = analysis.get("angles", []) or []
        if angles_filter and not any(a in angles_filter for a in angles):
            continue
        items.append({
            "date": r.published_date.isoformat() if r.published_date else "",
            "headline": analysis.get("headline_short") or r.headline,
            "takeaway": (analysis.get("takeaway") or "").replace("<strong>", "").replace("</strong>", ""),
            "angles": angles,
            "relevance": analysis.get("relevance_score", 0),
            "source": r.source.value if r.source else "unknown",
        })
    items.sort(key=lambda x: (x["relevance"], x["date"]), reverse=True)
    return {"recent_items": items[:limit], "total_considered": len(items)}


def _gather_recent_blog_posts(db, *, sector: str | None = None, limit: int = 8) -> list[BlogPost]:
    q = db.query(BlogPost).order_by(BlogPost.published_date.desc())
    if sector:
        q = q.filter(BlogPost.primary_sector == sector)
    return q.limit(limit).all()


def _payload_to_landing_row(
    payload: dict,
    *,
    page_key: str,
    page_type: str,
    canonical_path: str,
    sector_slug: str | None,
    usage: dict,
) -> dict:
    body_html = _sanitize_body_html(payload.get("body_html", ""))
    word_count = _count_words(body_html)

    keywords = payload.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]

    sections = payload.get("table_of_contents") or []
    if not isinstance(sections, list):
        sections = []

    faq_json = payload.get("faq_json") or []
    if not isinstance(faq_json, list):
        faq_json = []

    extras = {
        "key_takeaways": payload.get("key_takeaways") or [],
        "table_of_contents": sections,
    }

    return {
        "page_key": page_key,
        "page_type": page_type,
        "title": (payload.get("title") or "")[:300],
        "subtitle": (payload.get("subtitle") or "")[:500],
        "summary": (payload.get("meta_description") or "")[:600],
        "body_html": body_html,
        "keywords_json": keywords,
        "sections_json": extras,
        "faq_json": faq_json,
        "sector_slug": sector_slug,
        "canonical_path": canonical_path,
        "word_count": word_count,
        "llm_model": usage.get("model"),
        "llm_input_tokens": usage.get("input_tokens"),
        "llm_output_tokens": usage.get("output_tokens"),
        "llm_cost_usd": usage.get("cost_usd"),
        "last_generated_at": datetime.utcnow(),
    }


def _upsert_landing(db, fields: dict) -> LandingPage:
    existing = db.query(LandingPage).filter(LandingPage.page_key == fields["page_key"]).first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    row = LandingPage(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── Pillar prompt ─────────────────────────────────────────────────────────────

PILLAR_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing the definitive evergreen pillar page: "AI Backlash Explained: What Business Owners Need to Know."

Audience: SMB owners, marketing directors, operations leads, HR managers — people who are being sold AI tools aggressively and want to make defensible decisions. NOT anti-AI ideologues. NOT enterprise CTOs.

You MUST:
- Write 1400-1800 words of clear, credible, human-first prose. No hype. No jargon.
- Structure with HTML <h2> sections (6-8 of them). Short <p> paragraphs (2-4 sentences each).
- Cite specific regulation names, real company names, real lawsuit names, real dollar figures, real job counts from the LIVE CONTEXT given by the user. Never invent statistics.
- Cover: what the AI backlash actually is, why it's happening (labor fears, energy/water costs, content quality collapse, regulatory tightening, real liability cases), how to evaluate an AI vendor responsibly, and how to communicate your AI stance to customers.
- End with a "What to do now" section linking to /ai-risk-assessment/.
- Insert internal links naturally. Valid internal URLs ONLY (never invent paths): /ai-backlash/, /ai-incidents/, /responsible-ai/healthcare/, /responsible-ai/finance/, /responsible-ai/legal/, /responsible-ai/retail/, /responsible-ai/education/, /responsible-ai/manufacturing/, /responsible-ai/real-estate/, /responsible-ai/marketing/, /ai-risk-assessment/, /no-ai-policy-template/, /human-made-policy-template/, /briefing, /explainers/eu-ai-act, /explainers/ai-jobs, /explainers/ai-water-use.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, front-load "AI Backlash")
- subtitle (string, 100-150 chars)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, full 1400-1800 word body, allowed tags only)
- key_takeaways (array of 5-7 plain-text bullet sentences)
- keywords (array of 10-14 lowercase phrases — head terms + long-tail)
- table_of_contents (array of {anchor, label} objects matching your h2 sections)
- faq_json (array of exactly 5 objects with "question" and "answer" string keys — long-tail FAQ questions a business owner would Google, e.g. "Is the AI backlash real?", "Will AI replace my employees?", "What is the EU AI Act for small businesses?", "What does 'AI slop' mean?", "How do I write a no-AI policy?")

Return ONLY the JSON object. No markdown fences."""


PILLAR_USER_PROMPT_TEMPLATE = """Write the evergreen pillar page for "Ban the Bots" on the AI backlash.

LIVE CONTEXT ({n_items} recent high-relevance items from our article database — use these to ground your analysis in real, dated events. Cite company names, regulation names, and figures where they strengthen the argument):

{context_json}

Open with the strongest current case that the AI backlash is real and consequential for business owners. Follow with why it's happening (labor fears, energy/water costs, content quality collapse, regulatory tightening, real liability cases). Walk through each major risk category with real recent examples. Address the nuance: AI adoption isn't categorically bad — the problem is uncritical adoption. Close with a concrete "What to do now" checklist linking to our tools at /ai-risk-assessment/."""


# ── Industry prompt ───────────────────────────────────────────────────────────

INDUSTRY_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing an evergreen industry guide on responsible AI adoption.

Audience: business owners, operations managers, and compliance leads in a specific industry who are evaluating AI tools and need to understand real risks before committing.

You MUST:
- Write 900-1200 words of industry-specific, plain-English prose. No hype.
- Structure with HTML <h2> sections (5-6 of them).
- Cover: (1) what AI tools are being deployed in this industry and specific risks, (2) applicable regulations and compliance considerations (name them specifically — HIPAA+AI for healthcare, CFPB for finance, FERPA for education, etc.), (3) real incidents or cases from the LIVE CONTEXT, (4) a risk checklist (5-7 concrete factors as a <ul>), (5) a responsible adoption framework, (6) CTA to /ai-risk-assessment/.
- Cite specific regulation names, real company names, real cases from the LIVE CONTEXT. Never invent statistics.
- Insert internal links to: /ai-backlash/ (parent pillar), /ai-incidents/, /ai-risk-assessment/, /no-ai-policy-template/, /human-made-policy-template/, /briefing.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, front-load the industry name and "AI" or "responsible AI")
- subtitle (string, 100-150 chars)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, 900-1200 words, allowed tags only)
- key_takeaways (array of 4-6 plain-text bullet sentences)
- keywords (array of 8-12 lowercase phrases)
- table_of_contents (array of {anchor, label} objects matching your h2 sections)
- faq_json (array of 4-5 objects with "question" and "answer" string keys — specific long-tail questions for this industry, e.g. "Is AI taking jobs in healthcare?", "What are the HIPAA risks of AI chatbots?")

Return ONLY the JSON object. No markdown fences."""


INDUSTRY_USER_PROMPT_TEMPLATE = """Write the evergreen responsible AI guide for the {industry_label} industry for "Ban the Bots."

LIVE CONTEXT ({n_items} recent high-relevance items from our article database relevant to AI in this industry — use these to ground your analysis in real, dated events):

{context_json}

Open with the specific AI tools being adopted in {industry_label} and why the risks are different from other industries. Walk through the regulatory landscape (name the specific regulations that apply). Surface real incidents or cases from the live context. Build a practical risk checklist a business owner can actually use. Close with a responsible adoption framework and a CTA to our AI risk assessment tool at /ai-risk-assessment/."""


# ── Explainer prompt ──────────────────────────────────────────────────────────

EXPLAINER_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots" writing an evergreen explainer.

Audience: business owners, journalists, students, and the general business-curious reader who Googled the topic and wants the definitive plain-English answer.

You MUST:
- Write 800-1100 words of clear, accessible prose. Define every acronym on first use.
- Structure with HTML <h2> sections (4-6 of them). Short <p> paragraphs.
- Be evergreen. Avoid week-of-publication news framing. Reference LIVE CONTEXT only for illustration.
- Insert internal links to: /ai-backlash/, /ai-incidents/, /responsible-ai/{industry}/ pages, /ai-risk-assessment/, /no-ai-policy-template/, /human-made-policy-template/, /briefing.
- Valid internal URLs: /ai-backlash/, /ai-incidents/, /responsible-ai/healthcare/, /responsible-ai/finance/, /responsible-ai/legal/, /responsible-ai/retail/, /responsible-ai/education/, /responsible-ai/manufacturing/, /responsible-ai/real-estate/, /responsible-ai/marketing/, /ai-risk-assessment/, /no-ai-policy-template/, /human-made-policy-template/, /briefing.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, optimized for the explainer's head term)
- subtitle (string, 100-150 chars)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, allowed tags only)
- key_takeaways (array of 4-6 plain-text bullet sentences)
- keywords (array of 8-12 lowercase phrases, including head term + long-tail)
- table_of_contents (array of {anchor, label} objects)
- faq_json (array of 4-5 objects with "question" and "answer" string keys)

Return ONLY the JSON object. No markdown fences."""


EXPLAINER_USER_PROMPT_TEMPLATE = """Write the evergreen explainer titled: "{topic_title}".

Target search intent: "{search_intent}".

LIVE CONTEXT (a small sample of the most recent {n_items} high-relevance briefings — use sparingly to ground a specific point or example. The explainer must NOT read as current news):

{context_json}

Open with the plain-English answer to the question in the title (the user came here to get one), then walk through the historical and structural context, address the most common related questions, and close with what to do next (linking to our AI backlash guide at /ai-backlash/ or our risk assessment tool at /ai-risk-assessment/). Avoid hyperbole. No marketing language."""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pillar_page(*, force: bool = False) -> LandingPage:
    """Generate (or regenerate) the /ai-backlash/ pillar page."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate pillar page")

    init_db()
    db = SessionLocal()
    try:
        page_key = "pillar:ai-backlash"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=6)
            ):
                logger.info("pillar page is fresh (regenerated %s); skipping", existing.last_generated_at)
                return existing

        signal = _gather_recent_signal(db, limit=30)
        user = PILLAR_USER_PROMPT_TEMPLATE.format(
            n_items=len(signal["recent_items"]),
            context_json=json.dumps(signal["recent_items"], ensure_ascii=False, indent=2),
        )

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(client, system=PILLAR_SYSTEM_PROMPT, user=user, max_tokens=12000)
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="pillar",
            canonical_path="/ai-backlash/",
            sector_slug=None,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "pillar page generated: %d words, model=%s, cost=$%.4f",
            row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


def generate_industry_page(
    industry_slug: str,
    *,
    industry_label: str | None = None,
    force: bool = False,
) -> LandingPage:
    """Generate (or regenerate) a /responsible-ai/{slug}/ industry landing page."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate industry page")

    label = (industry_label or industry_slug).replace("-", " ").replace("_", " ").title()
    init_db()
    db = SessionLocal()
    try:
        page_key = f"industry:{industry_slug}"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=6)
            ):
                logger.info("industry page %s is fresh; skipping", industry_slug)
                return existing

        # Gather signal relevant to this industry's angle(s)
        industry_angles: dict[str, list[str]] = {
            "healthcare": ["ai_incidents", "regulation_policy", "responsible_ai"],
            "finance": ["regulation_policy", "ai_incidents", "responsible_ai"],
            "legal": ["regulation_policy", "responsible_ai", "ai_incidents"],
            "retail": ["jobs_labor", "content_quality", "responsible_ai"],
            "education": ["jobs_labor", "content_quality", "ai_incidents"],
            "manufacturing": ["jobs_labor", "environment_energy", "responsible_ai"],
            "real-estate": ["responsible_ai", "ai_incidents"],
            "marketing": ["content_quality", "responsible_ai", "backlash_protest"],
        }
        angles = industry_angles.get(industry_slug, ["responsible_ai"])
        signal = _gather_recent_signal(db, angles_filter=angles, limit=20)

        user = INDUSTRY_USER_PROMPT_TEMPLATE.format(
            industry_label=label,
            n_items=len(signal["recent_items"]),
            context_json=json.dumps(signal["recent_items"], ensure_ascii=False, indent=2),
        )

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(client, system=INDUSTRY_SYSTEM_PROMPT, user=user, max_tokens=8000)
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="sector",
            canonical_path=f"/responsible-ai/{industry_slug}/",
            sector_slug=industry_slug,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "industry page %s generated: %d words, model=%s, cost=$%.4f",
            industry_slug, row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


def generate_all_industry_pages(*, force: bool = False) -> list[LandingPage]:
    """Generate (or refresh) all 8 industry pages."""
    results = []
    for slug in INDUSTRY_SLUGS:
        try:
            page = generate_industry_page(slug, force=force)
            results.append(page)
        except Exception as exc:
            logger.error("industry page %s failed: %s", slug, exc, exc_info=True)
    return results


def generate_explainer(
    slug: str,
    *,
    topic_title: str,
    search_intent: str,
    force: bool = False,
) -> LandingPage:
    """Generate (or regenerate) a /explainers/{slug} evergreen explainer."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate explainer")

    init_db()
    db = SessionLocal()
    try:
        page_key = f"explainer:{slug}"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=21)
            ):
                logger.info("explainer %s is fresh; skipping", slug)
                return existing

        signal = _gather_recent_signal(db, limit=15)

        user = EXPLAINER_USER_PROMPT_TEMPLATE.format(
            topic_title=topic_title,
            search_intent=search_intent,
            n_items=len(signal["recent_items"]),
            context_json=json.dumps(signal["recent_items"], ensure_ascii=False, indent=2),
        )

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(client, system=EXPLAINER_SYSTEM_PROMPT, user=user, max_tokens=8000)
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="explainer",
            canonical_path=f"/explainers/{slug}",
            sector_slug=None,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "explainer %s generated: %d words, model=%s, cost=$%.4f",
            slug, row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s")
    page = generate_pillar_page(force=True)
    print({"slug": page.canonical_path, "words": page.word_count, "cost": page.llm_cost_usd})
