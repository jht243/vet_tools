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

PILLAR_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing the definitive evergreen pillar page: "AI Backlash Explained."

Audience: regular people — workers worried about their jobs, parents wondering what their kids should study, renters and homeowners near new AI data centers, artists whose work was scraped without permission, anyone who noticed the internet feeling worse and wants to understand why. NOT business compliance officers. NOT enterprise CTOs. Write as if explaining this to a smart friend who hasn't followed AI news closely but is starting to feel its effects.

You MUST:
- Write 1400-1800 words of clear, credible, human-first prose. No hype. No jargon.
- Structure with HTML <h2> sections (6-8 of them). Short <p> paragraphs (2-4 sentences each).
- Cite specific regulation names, real company names, real lawsuit names, real dollar figures, real job counts from the LIVE CONTEXT given by the user. Never invent statistics.
- Cover: what the AI backlash actually is and who is driving it (workers, artists, parents, communities near data centers), why it's happening (job displacement, energy and water costs, content quality collapse, regulatory tightening, real harm cases), what ordinary people can do about it.
- End with a "What you can do" section linking to our tools.
- Insert internal links naturally. Valid internal URLs ONLY (never invent paths): /ai-backlash/, /ai-incidents/, /ai-layoffs/, /ai-lawsuits/, /fighting-back/, /data-center-map/, /ai-proof-jobs/, /will-ai-replace-my-job/, /parents/, /responsible-ai/healthcare/, /responsible-ai/finance/, /responsible-ai/legal/, /responsible-ai/retail/, /responsible-ai/education/, /responsible-ai/manufacturing/, /responsible-ai/real-estate/, /responsible-ai/marketing/, /no-ai-policy-template/, /human-made-policy-template/, /briefing, /explainers/eu-ai-act, /explainers/ai-jobs, /explainers/ai-water-use, /explainers/ai-slop, /explainers/ai-art-theft, /explainers/ai-proof-jobs, /explainers/data-center-impact, /explainers/ai-regulation.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, front-load "AI Backlash")
- subtitle (string, 100-150 chars)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, full 1400-1800 word body, allowed tags only)
- key_takeaways (array of 5-7 plain-text bullet sentences)
- keywords (array of 10-14 lowercase phrases — head terms + long-tail)
- table_of_contents (array of {anchor, label} objects matching your h2 sections)
- faq_json (array of exactly 5 objects with "question" and "answer" string keys — long-tail FAQ questions a real person would Google, e.g. "Is the AI backlash real?", "Will AI replace my job?", "What is AI slop?", "How do I find out if there's a data center near me?", "What companies have a no-AI policy?")

Return ONLY the JSON object. No markdown fences."""


PILLAR_USER_PROMPT_TEMPLATE = """Write the evergreen pillar page for "Ban the Bots" on the AI backlash.

LIVE CONTEXT ({n_items} recent high-relevance items from our article database — use these to ground your analysis in real, dated events. Cite company names, regulation names, and figures where they strengthen the argument):

{context_json}

Open with the strongest current case that the AI backlash is real and felt by ordinary people — workers, parents, artists, and communities. Follow with why it's happening: job displacement, energy and water costs from data centers, content quality collapse (AI slop), regulatory tightening, and real harm cases. Walk through each category with real examples from the live context. Acknowledge the nuance: the backlash isn't about AI being inherently evil — it's about who bears the costs and who captures the benefits. Close with a concrete "What you can do" section pointing readers to our tools and trackers."""


# ── Industry prompt ───────────────────────────────────────────────────────────

INDUSTRY_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing an evergreen guide about AI's impact on a specific industry — written for the people who work in it and depend on it, not the executives running it.

Audience: workers, patients, students, and consumers affected by AI in this sector — a nurse, a loan applicant, a student, a retail worker, a teacher. NOT HR departments or compliance officers. Write about how AI decisions in this industry affect ordinary people's lives, jobs, safety, and rights.

You MUST:
- Write 900-1200 words of industry-specific, plain-English prose. No hype.
- Structure with HTML <h2> sections (5-6 of them).
- Cover: (1) what AI tools are being deployed in this industry and how they affect workers and consumers, (2) applicable laws and protections that exist (name them specifically — HIPAA for healthcare, FERPA for education, CFPB for finance, etc.), (3) real incidents or harms from the LIVE CONTEXT, (4) a "watch out for" checklist (5-7 concrete things workers and consumers should know as a <ul>), (5) what's being done to protect people in this industry, (6) where to learn more.
- Cite specific regulation names, real company names, real cases from the LIVE CONTEXT. Never invent statistics.
- Insert internal links to: /ai-backlash/, /ai-incidents/, /ai-layoffs/, /fighting-back/, /no-ai-policy-template/, /human-made-policy-template/, /briefing.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, front-load the industry name and "AI")
- subtitle (string, 100-150 chars — speak to the worker/consumer, not the executive)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, 900-1200 words, allowed tags only)
- key_takeaways (array of 4-6 plain-text bullet sentences)
- keywords (array of 8-12 lowercase phrases)
- table_of_contents (array of {anchor, label} objects matching your h2 sections)
- faq_json (array of 4-5 objects with "question" and "answer" string keys — questions a real worker or patient would Google, e.g. "Is AI taking nursing jobs?", "Can my bank use AI to deny my loan?", "Are AI teachers replacing human teachers?")

Return ONLY the JSON object. No markdown fences."""


INDUSTRY_USER_PROMPT_TEMPLATE = """Write the evergreen guide for "Ban the Bots" about AI's impact on the {industry_label} industry — for the people who work in it or depend on it.

LIVE CONTEXT ({n_items} recent high-relevance items from our article database relevant to AI in this industry — use these to ground your analysis in real, dated events):

{context_json}

Open with how AI is already changing day-to-day life for workers and consumers in {industry_label} — name specific tools and real consequences. Walk through the laws that are supposed to protect people (name them). Surface real incidents or cases from the live context where AI caused harm or job loss in this sector. Build a practical "watch out for" checklist a worker or patient can actually use. Close by pointing to what's being done — unions, legislation, no-AI policies — and where readers can track developments."""


# ── Explainer prompt ──────────────────────────────────────────────────────────

EXPLAINER_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots" writing an evergreen explainer.

Audience: anyone who Googled this question — a worker, a student, a parent, a concerned citizen. They don't follow tech news but they're feeling AI's effects in their daily life and want a real answer, not a press release. Write as if talking to a smart person who just asked you this question at a dinner party. No jargon, no business-speak.

You MUST:
- Write 800-1100 words of clear, accessible prose. Define every acronym on first use.
- Structure with HTML <h2> sections (4-6 of them). Short <p> paragraphs.
- Be evergreen. Avoid week-of-publication news framing. Reference LIVE CONTEXT only for illustration.
- Insert internal links naturally. Valid internal URLs ONLY (never invent paths): /ai-backlash/, /ai-incidents/, /ai-layoffs/, /ai-lawsuits/, /fighting-back/, /data-center-map/, /ai-proof-jobs/, /will-ai-replace-my-job/, /parents/, /responsible-ai/healthcare/, /responsible-ai/finance/, /responsible-ai/legal/, /responsible-ai/retail/, /responsible-ai/education/, /responsible-ai/manufacturing/, /responsible-ai/real-estate/, /responsible-ai/marketing/, /no-ai-policy-template/, /human-made-policy-template/, /briefing, /explainers/eu-ai-act, /explainers/ai-jobs, /explainers/ai-water-use, /explainers/ai-slop, /explainers/ai-art-theft, /explainers/ai-proof-jobs, /explainers/data-center-impact, /explainers/what-to-study, /explainers/ai-regulation.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, optimized for the explainer's head term)
- subtitle (string, 100-150 chars — speak to the person who just Googled this, not a business audience)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, allowed tags only)
- key_takeaways (array of 4-6 plain-text bullet sentences)
- keywords (array of 8-12 lowercase phrases, including head term + long-tail)
- table_of_contents (array of {anchor, label} objects)
- faq_json (array of 4-5 objects with "question" and "answer" string keys — questions a real person would Google, not a corporate buyer)

Return ONLY the JSON object. No markdown fences."""


EXPLAINER_USER_PROMPT_TEMPLATE = """Write the evergreen explainer titled: "{topic_title}".

Target search intent: "{search_intent}".

LIVE CONTEXT (a small sample of the most recent {n_items} high-relevance briefings — use sparingly to ground a specific point or example. The explainer must NOT read as current news):

{context_json}

Open with the plain-English answer to the question in the title — the reader came here to get a straight answer, so give it in the first paragraph. Then walk through the context: why this is happening, who it affects, what the stakes are. Address the most common follow-up questions. Close with what readers can actually do — point them to our trackers (/ai-layoffs/, /fighting-back/, /data-center-map/) or our AI backlash guide at /ai-backlash/. Avoid hyperbole. No marketing language."""


# ── AI-Proof Jobs pillar prompt ───────────────────────────────────────────────

AI_PROOF_JOBS_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing an evergreen pillar page: "AI-Proof Jobs: What Work Humans Will Always Do Better."

Audience: workers, career-changers, and parents who are scared about AI taking jobs. Write for someone who works in an office, a factory, a school, or a hospital and is wondering if they'll still have a job in 10 years. NOT an HR executive or management consultant. Speak plainly, with warmth and honesty.

You MUST:
- Write 1400-1800 words of clear, human-first prose. No hype. No false reassurance.
- Structure with HTML <h2> sections (6-8 of them). Short <p> paragraphs (2-4 sentences each).
- Cover: (1) what "AI-proof" actually means (it's about tasks, not whole jobs), (2) the job categories most resilient to automation and why — physical dexterity in variable environments, human care and emotional connection, creative judgment, local trust and relationships, crisis response, (3) specific job families that score well on these dimensions, (4) what workers in higher-risk jobs can do to shift toward resilient skills, (5) a frank acknowledgment that some displacement is coming and what that means.
- Cite specific research, name real automation studies, and use real statistics from the LIVE CONTEXT. Never invent statistics.
- Insert internal links naturally. Valid internal URLs ONLY: /will-ai-replace-my-job/, /ai-layoffs/, /fighting-back/, /ai-backlash/, /ai-incidents/, /parents/, /explainers/ai-proof-jobs, /explainers/ai-jobs, /explainers/what-to-study, /explainers/ai-regulation, /briefing.
- Use only: h2, h3, p, ul, ol, li, strong, em, blockquote, a. No div, span, table, script, style.

Return ONE JSON object with these fields:
- title (string, 55-75 chars, front-load "AI-Proof Jobs")
- subtitle (string, 100-150 chars — speak to the worker, not the executive)
- meta_description (string, 140-160 chars, plain text, ends with period)
- body_html (string, full 1400-1800 word body, allowed tags only)
- key_takeaways (array of 5-7 plain-text bullet sentences)
- keywords (array of 10-14 lowercase phrases)
- table_of_contents (array of {anchor, label} objects matching your h2 sections)
- faq_json (array of 5 objects with "question" and "answer" string keys — questions real workers Google, e.g. "What jobs are safe from AI?", "Will AI replace nurses?", "What should I study to avoid AI taking my job?", "Are trade jobs safe from AI?", "How long until AI takes most jobs?")

Return ONLY the JSON object. No markdown fences."""

AI_PROOF_JOBS_USER_PROMPT_TEMPLATE = """Write the evergreen pillar page for "Ban the Bots" on AI-proof jobs.

LIVE CONTEXT ({n_items} recent high-relevance items from our article database — use these to ground your analysis in real, dated events and studies):

{context_json}

Open with honest framing: some jobs are genuinely safer than others, and the research tells us why. Walk through the categories of work that are hardest to automate — physical dexterity in unpredictable environments, human care and emotional intelligence, creative judgment that requires cultural context, local trust relationships, crisis and emergency response. Give specific job examples in each category. Address the workers most at risk and what skills they can develop. Close with a section on what's being done — unions, legislation, no-AI policies — pointing to /fighting-back/ and /ai-layoffs/ for the real-world picture."""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_ai_proof_jobs_pillar(*, force: bool = False) -> LandingPage:
    """Generate (or regenerate) the /ai-proof-jobs/ pillar page."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate AI-proof jobs pillar")

    init_db()
    db = SessionLocal()
    try:
        page_key = "pillar:ai-proof-jobs"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=6)
            ):
                logger.info("ai-proof-jobs pillar is fresh (regenerated %s); skipping", existing.last_generated_at)
                return existing

        signal = _gather_recent_signal(db, limit=30, angles_filter=["jobs_labor"])
        user = AI_PROOF_JOBS_USER_PROMPT_TEMPLATE.format(
            n_items=len(signal["recent_items"]),
            context_json=json.dumps(signal["recent_items"], ensure_ascii=False, indent=2),
        )

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(client, system=AI_PROOF_JOBS_SYSTEM_PROMPT, user=user, max_tokens=12000)
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="pillar",
            canonical_path="/ai-proof-jobs/",
            sector_slug=None,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "ai-proof-jobs pillar generated: %d words, model=%s, cost=$%.4f",
            row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


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


PARENT_SPOKE_SLUGS: tuple[str, ...] = (
    "screen-time",
    "what-to-study",
    "ai-safety",
    "how-to-use-ai-for-good",
    "social-media",
)

PARENT_SPOKE_LABELS: dict[str, str] = {
    "screen-time": "AI & Screen Time",
    "what-to-study": "What Should My Kids Study?",
    "ai-safety": "AI Safety for Kids",
    "how-to-use-ai-for-good": "Using AI for Good",
    "social-media": "AI & Social Media",
}

PARENT_SYSTEM_PROMPT = """You are a senior writer for "Ban the Bots," writing content for parents of school-age children (ages 6–18).

Audience: parents who are worried about AI's effect on their kids — not from a tech perspective, but from a parenting one. They want to know: Is my kid safe? Are they falling behind or getting ahead? What do I actually say to them about AI? They use Google, not Hacker News. Write warmly but credibly. Use plain English. Avoid jargon.

Tone: like a knowledgeable friend who happens to have read the research — not a tech blogger, not a consultant. Concerned, honest, practical.

Cover real research. Name real platforms and products (TikTok, ChatGPT, Instagram, YouTube, Khan Academy, etc.). Give practical actions parents can take this week, not abstract advice.

Valid internal URLs (use these naturally to connect content — do NOT use external links except for sources):
/parents/ — parenting hub homepage
/parents/screen-time/ — AI and kids' screen time
/parents/what-to-study/ — what to encourage kids to study
/parents/ai-safety/ — deepfakes, inappropriate content, AI safety
/parents/how-to-use-ai-for-good/ — AI as homework helper vs crutch
/parents/social-media/ — AI recommendation engines and children
/ai-proof-jobs/ — AI-proof jobs guide
/will-ai-replace-my-job/ — job risk checker
/explainers/what-to-study — explainer on future-proof studies
/explainers/ai-regulation — AI laws and regulations
/briefing — daily AI briefings
/ai-backlash/ — AI backlash explainer

Return a JSON object with these exact keys:
{
  "title": "...",
  "subtitle": "...",
  "meta_description": "...",
  "body_html": "...",
  "key_takeaways": ["...", "...", "..."],
  "keywords": ["...", "..."],
  "table_of_contents": [{"id": "...", "text": "..."}, ...],
  "faq_json": [{"question": "...", "answer": "..."}, ...]
}"""

PARENT_HUB_USER_PROMPT = """Write the hub/overview page for the "Parenting in the Age of AI" section of Ban the Bots.

This hub page should:
- Open with an honest, warm framing: AI is reshaping childhood fast, parents are right to have questions, and this section is here to help
- Briefly introduce each of the 5 sub-topics: screen time, what to study, AI safety, using AI for good, social media
- Give a 2–3 sentence preview of what each spoke covers and why it matters for parents
- Link naturally to each spoke page: /parents/screen-time/, /parents/what-to-study/, /parents/ai-safety/, /parents/how-to-use-ai-for-good/, /parents/social-media/
- Close with practical encouragement: the goal isn't to fear AI but to navigate it as a family

Keep it relatively concise — this is a navigation hub, not a deep-dive article. ~600–900 words body."""

PARENT_SPOKE_USER_PROMPT_TEMPLATE = """Write a deep-dive article for the "Parenting in the Age of AI" section of Ban the Bots.

Topic: {spoke_label}
URL: /parents/{spoke_slug}/

LIVE CONTEXT ({n_items} recent high-relevance items from our article database — use these to ground your analysis in real, dated events):

{context_json}

This article should:
- Open with a specific, relatable scenario a parent would recognize
- Cite real research, studies, or expert recommendations (name the source)
- Name real products and platforms parents and kids actually use
- Give 5–7 concrete actions a parent can take (not vague advice)
- Connect to other spoke pages where relevant
- Avoid condescension — parents reading this are smart; they just need the information

SPOKE-SPECIFIC REQUIREMENTS:
- If spoke is "ai-safety": explicitly address "is Character AI safe for kids?" — it is one of the
  top-searched parenting+AI questions. Discuss the lawsuit (Garcia v. Character.AI), the lack of
  age verification, and the grooming/self-harm incident reports. Also cover ChatGPT, Snapchat My AI,
  and Replika's child safety policies.
- If spoke is "what-to-study": explicitly address "what should my kids study" and "what majors are
  ai proof" — name specific subjects (trades, healthcare, social work, creative arts, law) and explain
  why they are resilient. Reference BLS or McKinsey data.
- If spoke is "social-media": address TikTok's algorithm (ForYou Page), YouTube autoplay, and
  Instagram Reels — explain how AI recommendation systems work and what parents can do about them.
- If spoke is "screen-time": address how AI apps differ from regular apps (they adapt to the child,
  making them more engaging) and what current research says about recommended limits.
- If spoke is "how-to-use-ai-for-good": address the "is my kid cheating?" question directly. Explain
  the difference between using AI to avoid thinking vs. using AI as a Socratic tutor.

Target length: 1,200–1,800 words body."""


def generate_parent_hub(*, force: bool = False) -> LandingPage:
    """Generate (or regenerate) the /parents/ hub page."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate parent hub")

    init_db()
    db = SessionLocal()
    try:
        page_key = "parent:hub"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=14)
            ):
                logger.info("parent hub is fresh (regenerated %s); skipping", existing.last_generated_at)
                return existing

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(
            client, system=PARENT_SYSTEM_PROMPT, user=PARENT_HUB_USER_PROMPT, max_tokens=6000
        )
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="pillar",
            canonical_path="/parents/",
            sector_slug=None,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "parent hub generated: %d words, model=%s, cost=$%.4f",
            row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


def generate_parent_spoke(spoke_slug: str, *, force: bool = False) -> LandingPage:
    """Generate (or regenerate) a /parents/{spoke_slug}/ article."""
    if spoke_slug not in PARENT_SPOKE_SLUGS:
        raise ValueError(f"Unknown parent spoke: {spoke_slug!r}. Valid slugs: {PARENT_SPOKE_SLUGS}")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set; cannot generate parent spoke")

    init_db()
    db = SessionLocal()
    try:
        page_key = f"parent:{spoke_slug}"
        if not force:
            existing = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if existing and existing.last_generated_at and (
                datetime.utcnow() - existing.last_generated_at < timedelta(days=14)
            ):
                logger.info("parent spoke %s is fresh; skipping", spoke_slug)
                return existing

        signal = _gather_recent_signal(db, limit=15, angles_filter=["jobs_labor", "ai_incidents", "regulation_policy"])
        label = PARENT_SPOKE_LABELS[spoke_slug]
        user = PARENT_SPOKE_USER_PROMPT_TEMPLATE.format(
            spoke_label=label,
            spoke_slug=spoke_slug,
            n_items=len(signal["recent_items"]),
            context_json=json.dumps(signal["recent_items"], ensure_ascii=False, indent=2),
        )

        client = OpenAI(api_key=settings.openai_api_key)
        raw, usage = _premium_call(client, system=PARENT_SYSTEM_PROMPT, user=user, max_tokens=10000)
        payload = json.loads(raw)

        fields = _payload_to_landing_row(
            payload,
            page_key=page_key,
            page_type="pillar",
            canonical_path=f"/parents/{spoke_slug}/",
            sector_slug=None,
            usage=usage,
        )
        row = _upsert_landing(db, fields)
        logger.info(
            "parent spoke %s generated: %d words, model=%s, cost=$%.4f",
            spoke_slug, row.word_count, row.llm_model, row.llm_cost_usd or 0.0,
        )
        return row
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s")
    page = generate_pillar_page(force=True)
    print({"slug": page.canonical_path, "words": page.word_count, "cost": page.llm_cost_usd})
