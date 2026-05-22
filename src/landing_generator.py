"""Landing page generator — creates pillar, spoke, condition, state, and explainer pages."""
from __future__ import annotations
import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.models import LandingPage, VACondition, engine

logger = logging.getLogger(__name__)

PAGE_TTLS = {
    "pillar": 7,
    "spoke": 14,
    "condition": 21,
    "state": 30,
    "explainer": 21,
    "tool": 30,
}

PILLARS = [
    "va-claims",
    "va-disability",
    "military-retirement",
    "military-pay",
    "state-benefits",
    "explainers",
]

VA_CLAIMS_SPOKES = [
    "how-to-file-a-va-claim",
    "service-connection-requirements",
    "nexus-letter-guide",
    "c-and-p-exam-tips",
    "va-claim-timeline",
    "buddy-statement-guide",
    "va-claim-checklist",
    "secondary-conditions",
    "va-rating-increase",
    "claim-for-increase",
]

CONDITIONS = [
    "tinnitus", "ptsd", "lumbar-spine-strain", "sleep-apnea", "knee-pain",
    "migraines", "depression", "anxiety", "tbi", "hearing-loss",
    "shoulder-impingement", "hypertension", "diabetes-mellitus-type-2",
    "burn-pit-exposure", "agent-orange-exposure", "mst-military-sexual-trauma",
    "chronic-fatigue-syndrome", "fibromyalgia", "cervical-spine-strain",
    "plantar-fasciitis", "pes-planus-flat-feet", "bilateral-knee",
    "bilateral-hearing-loss", "Gulf-war-illness", "radiculopathy-lower",
    "radiculopathy-upper", "degenerative-disc-disease", "hemorrhoids",
    "irritable-bowel-syndrome", "gerd", "rhinitis", "sinusitis",
    "skin-conditions-dermatitis",
]

RETIREMENT_SPOKES = [
    "final-pay-retirement",
    "high-36-retirement",
    "blended-retirement-system",
    "disability-retirement-vs-chapter61",
    "reserve-retirement-points",
    "survivor-benefit-plan",
    "concurrent-receipt-crsc-crdp",
]

EXPLAINER_SLUGS = [
    "what-is-a-nexus-letter",
    "va-disability-rating-explained",
    "pact-act-explained",
    "cdr-explained",
    "tdiu-explained",
    "va-appeals-process",
    "blended-retirement-system",
    "bah-explained",
    "tricare-options-explained",
    "government-shutdown-veterans",
    "military-retirement-pay-calculator-guide",
    "va-ebenefits-vs-va-gov",
    "va-buddy-statement-guide",
    "va-disability-back-pay",
]

CONDITION_RESEARCH = {
    "tinnitus": {
        "display_name": "Tinnitus",
        "cfr_citation": "38 CFR Part 4, DC 6260",
        "typical_rating_pct": 10,
        "short_description": "Ringing or buzzing in the ears — the most commonly claimed VA disability.",
    },
    "ptsd": {
        "display_name": "PTSD",
        "cfr_citation": "38 CFR Part 4, DC 9411",
        "typical_rating_pct": 50,
        "short_description": "Post-Traumatic Stress Disorder from in-service trauma, combat, or MST.",
    },
    "sleep-apnea": {
        "display_name": "Sleep Apnea",
        "cfr_citation": "38 CFR Part 4, DC 6847",
        "typical_rating_pct": 50,
        "short_description": "Obstructive sleep apnea requiring CPAP often rated 50%.",
    },
    "lumbar-spine-strain": {
        "display_name": "Lumbar Spine Strain",
        "cfr_citation": "38 CFR Part 4, DC 5237",
        "typical_rating_pct": 20,
        "short_description": "Lower-back pain from in-service injury, one of the most common claims.",
    },
    "knee-pain": {
        "display_name": "Knee Conditions",
        "cfr_citation": "38 CFR Part 4, DC 5257–5260",
        "typical_rating_pct": 10,
        "short_description": "Knee instability, limitation of flexion/extension, and residuals of surgery.",
    },
}

STATE_RESEARCH = {
    "texas": {
        "display_name": "Texas",
        "headline_benefit": "100% P&T veterans pay no property taxes in Texas.",
    },
    "florida": {
        "display_name": "Florida",
        "headline_benefit": "Florida exempts 100% P&T veterans from property taxes and sales tax on adaptive equipment.",
    },
    "california": {
        "display_name": "California",
        "headline_benefit": "California offers property tax exemptions up to $150,000 for 100% disabled veterans.",
    },
    "virginia": {
        "display_name": "Virginia",
        "headline_benefit": "Virginia exempts 100% P&T veterans from real property taxes.",
    },
}

EXPLAINER_RESEARCH = {
    "what-is-a-nexus-letter": {
        "title": "What Is a Nexus Letter?",
        "subtitle": "The medical opinion that connects your condition to military service",
        "key_points": [
            "A nexus letter is a written medical opinion linking your current condition to an in-service event.",
            "It must state the link is 'at least as likely as not' (50%+ probability).",
            "Private nexus letters often carry more weight than VA C&P exams.",
        ],
    },
    "va-disability-rating-explained": {
        "title": "VA Disability Rating Explained",
        "subtitle": "How the combined rating formula works — and why it's not simple addition",
        "key_points": [
            "VA uses a 'whole person' method: each rating reduces the remaining able-bodied percentage.",
            "50% + 50% does NOT equal 100% under VA math.",
            "The final rating is rounded to the nearest 10%.",
        ],
    },
    "pact-act-explained": {
        "title": "PACT Act Explained",
        "subtitle": "What the Sergeant First Class Heath Robinson PACT Act means for burn-pit veterans",
        "key_points": [
            "Signed into law August 2022, the PACT Act is the largest expansion of VA benefits in decades.",
            "It establishes presumptive service connection for 23 burn-pit/toxic-exposure cancers.",
            "Veterans who deployed to Southwest Asia on or after August 2, 1990 may qualify.",
        ],
    },
}


def _llm_generate(prompt: str, settings, max_tokens: int = 1200) -> Optional[str]:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.fast_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an SEO content writer for VA Claims Workspace. "
                        "Write factual, helpful content for veterans. "
                        "Use plain HTML (h2, h3, p, ul/li only). No markdown. No disclaimers."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("landing_generator: LLM call failed: %s", exc)
        return None


def _upsert_page(
    session: Session,
    *,
    slug: str,
    canonical_path: str,
    page_type: str,
    title: str,
    h1: str,
    subtitle: str = "",
    seo_description: str = "",
    body_html: str = "",
    faq_json: Optional[list] = None,
    key_takeaways: Optional[list] = None,
    cache_ttl_hours: Optional[int] = None,
) -> LandingPage:
    existing = session.query(LandingPage).filter_by(slug=slug).first()
    if existing:
        existing.title = title
        existing.h1 = h1
        existing.subtitle = subtitle
        existing.seo_description = seo_description
        existing.body_html = body_html
        if faq_json is not None:
            existing.faq_json = json.dumps(faq_json)
        if key_takeaways is not None:
            existing.key_takeaways_json = json.dumps(key_takeaways)
        if cache_ttl_hours is not None:
            existing.cache_ttl_hours = cache_ttl_hours
        session.add(existing)
        return existing

    page = LandingPage(
        slug=slug,
        canonical_path=canonical_path,
        page_type=page_type,
        title=title,
        h1=h1,
        subtitle=subtitle,
        seo_description=seo_description,
        body_html=body_html,
        faq_json=json.dumps(faq_json or []),
        key_takeaways_json=json.dumps(key_takeaways or []),
        cache_ttl_hours=cache_ttl_hours or PAGE_TTLS.get(page_type, 24) * 24,
    )
    session.add(page)
    return page


def generate_pillar_page(slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    titles = {
        "va-claims": ("VA Claims Guide", "How to File a VA Claim", "A complete guide to filing and winning your VA disability claim"),
        "va-disability": ("VA Disability Ratings", "VA Disability Ratings Explained", "How VA rates disabilities and calculates your combined rating"),
        "military-retirement": ("Military Retirement Pay", "Military Retirement Pay Guide", "Everything you need to know about military retirement and the BRS"),
        "military-pay": ("Military Pay Charts", "Military Pay Tables & BAH Rates", "Current military pay tables, BAH rates, and BAS allowances"),
        "state-benefits": ("State Veterans Benefits", "State Veterans Benefits by State", "Property tax exemptions, tuition waivers, and more — by state"),
        "explainers": ("VA & Military Benefits Explainers", "VA & Military Benefits Explained", "Plain-English guides to the most confusing benefits topics"),
    }
    if slug not in titles:
        logger.warning("generate_pillar_page: unknown pillar %r", slug)
        return None

    title, h1, subtitle = titles[slug]
    prompt = (
        f"Write a 400-word pillar page introduction for '{h1}'. "
        "Explain the topic, why it matters to veterans, and what the reader will learn. "
        "Use h2, p, and ul/li HTML only. Link internally where relevant."
    )
    body = "" if dry_run else (_llm_generate(prompt, settings) or "")

    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=slug,
            canonical_path=f"/{slug}/",
            page_type="pillar",
            title=f"{title} | VA Claims Workspace",
            h1=h1,
            subtitle=subtitle,
            seo_description=subtitle,
            body_html=body,
            cache_ttl_hours=PAGE_TTLS["pillar"] * 24,
        )
        session.commit()
        session.refresh(page)
    return page


def generate_spoke_page(pillar: str, spoke_slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    display = spoke_slug.replace("-", " ").title()
    prompt = (
        f"Write a 600-word guide about '{display}' for veterans. "
        "Include: why it matters, step-by-step guidance, common mistakes, and tips. "
        "Use h2, h3, p, ul/li HTML only."
    )
    body = "" if dry_run else (_llm_generate(prompt, settings) or "")

    slug = f"{pillar}-{spoke_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=slug,
            canonical_path=f"/{pillar}/{spoke_slug}/",
            page_type="spoke",
            title=f"{display} | VA Claims Workspace",
            h1=display,
            subtitle=f"A complete guide to {display.lower()} for veterans.",
            seo_description=f"Learn everything about {display.lower()} for your VA claim.",
            body_html=body,
            cache_ttl_hours=PAGE_TTLS["spoke"] * 24,
        )
        session.commit()
        session.refresh(page)
    return page


def generate_condition_page(condition_slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    research = CONDITION_RESEARCH.get(condition_slug, {})
    display_name = research.get("display_name") or condition_slug.replace("-", " ").title()

    prompt = (
        f"Write a 700-word VA disability guide for veterans with '{display_name}'. "
        "Cover: how VA rates this condition, what evidence is needed, common secondary conditions, "
        "and tips to get the right rating. Use h2, h3, p, ul/li HTML only."
    )
    body = "" if dry_run else (_llm_generate(prompt, settings) or "")

    faq = [
        {"question": f"What is the VA rating for {display_name}?", "answer": f"VA rates {display_name} based on the severity of symptoms. Ratings typically range from 0% to {research.get('typical_rating_pct', 100)}%."},
        {"question": f"How do I service-connect {display_name}?", "answer": f"You need medical evidence and a nexus letter linking {display_name} to an in-service event or condition."},
    ]

    slug = f"condition-{condition_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=slug,
            canonical_path=f"/va-disability/{condition_slug}/",
            page_type="condition",
            title=f"VA Disability for {display_name} | VA Claims Workspace",
            h1=f"VA Disability: {display_name}",
            subtitle=research.get("short_description", ""),
            seo_description=f"How VA rates {display_name}, what evidence you need, and tips to maximize your rating.",
            body_html=body,
            faq_json=faq,
            cache_ttl_hours=PAGE_TTLS["condition"] * 24,
        )
        session.commit()
        session.refresh(page)
    return page


def generate_state_page(state_slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    research = STATE_RESEARCH.get(state_slug, {})
    display_name = research.get("display_name") or state_slug.replace("-", " ").title()

    prompt = (
        f"Write a 600-word guide to veteran benefits in {display_name}. "
        "Cover: property tax exemptions, income tax exemptions for military retirement, "
        "education benefits, vehicle registration discounts, and hunting/fishing licenses. "
        "Use h2, p, ul/li HTML only. Be specific to {display_name} state law."
    )
    body = "" if dry_run else (_llm_generate(prompt, settings) or "")

    headline = research.get("headline_benefit", f"{display_name} offers several property tax and income tax exemptions for qualifying veterans.")
    key_takeaways = [headline]

    slug = f"state-{state_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=slug,
            canonical_path=f"/state-benefits/{state_slug}/",
            page_type="state",
            title=f"{display_name} Veterans Benefits | VA Claims Workspace",
            h1=f"Veterans Benefits in {display_name}",
            subtitle=f"Property tax exemptions, education benefits, and more for {display_name} veterans.",
            seo_description=f"Complete guide to {display_name} state veterans benefits: property taxes, education, vehicle registration, and more.",
            body_html=body,
            key_takeaways=key_takeaways,
            cache_ttl_hours=PAGE_TTLS["state"] * 24,
        )
        session.commit()
        session.refresh(page)
    return page


def generate_explainer_page(explainer_slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    research = EXPLAINER_RESEARCH.get(explainer_slug, {})
    title = research.get("title") or explainer_slug.replace("-", " ").title()
    key_points = research.get("key_points", [])

    prompt = (
        f"Write a 700-word explainer about '{title}' for veterans. "
        "Be clear, factual, and practical. Include key facts, a step-by-step section if applicable, "
        "and common misconceptions. Use h2, h3, p, ul/li HTML only."
    )
    body = "" if dry_run else (_llm_generate(prompt, settings) or "")

    slug = f"explainer-{explainer_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=slug,
            canonical_path=f"/explainers/{explainer_slug}/",
            page_type="explainer",
            title=f"{title} | VA Claims Workspace",
            h1=title,
            subtitle=research.get("subtitle", ""),
            seo_description=f"{title} — plain-English guide for veterans and military families.",
            body_html=body,
            key_takeaways=key_points,
            cache_ttl_hours=PAGE_TTLS["explainer"] * 24,
        )
        session.commit()
        session.refresh(page)
    return page


US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new-hampshire", "new-jersey", "new-mexico", "new-york",
    "north-carolina", "north-dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode-island", "south-carolina", "south-dakota",
    "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west-virginia", "wisconsin", "wyoming",
]


def generate_all_landing_pages(
    dry_run: bool = False,
    pillars: bool = True,
    spokes: bool = True,
    conditions: bool = True,
    states: bool = True,
    explainers: bool = True,
) -> dict:
    counts = {"pillars": 0, "spokes": 0, "conditions": 0, "states": 0, "explainers": 0, "errors": 0}

    if pillars:
        for slug in PILLARS:
            try:
                generate_pillar_page(slug, dry_run=dry_run)
                counts["pillars"] += 1
            except Exception as exc:
                logger.error("pillar %s: %s", slug, exc)
                counts["errors"] += 1

    if spokes:
        for slug in VA_CLAIMS_SPOKES:
            try:
                generate_spoke_page("va-claims", slug, dry_run=dry_run)
                counts["spokes"] += 1
            except Exception as exc:
                logger.error("spoke va-claims/%s: %s", slug, exc)
                counts["errors"] += 1
        for slug in RETIREMENT_SPOKES:
            try:
                generate_spoke_page("military-retirement", slug, dry_run=dry_run)
                counts["spokes"] += 1
            except Exception as exc:
                logger.error("spoke military-retirement/%s: %s", slug, exc)
                counts["errors"] += 1

    if conditions:
        for slug in CONDITIONS:
            try:
                generate_condition_page(slug, dry_run=dry_run)
                counts["conditions"] += 1
            except Exception as exc:
                logger.error("condition %s: %s", slug, exc)
                counts["errors"] += 1

    if states:
        for slug in US_STATES:
            try:
                generate_state_page(slug, dry_run=dry_run)
                counts["states"] += 1
            except Exception as exc:
                logger.error("state %s: %s", slug, exc)
                counts["errors"] += 1

    if explainers:
        for slug in EXPLAINER_SLUGS:
            try:
                generate_explainer_page(slug, dry_run=dry_run)
                counts["explainers"] += 1
            except Exception as exc:
                logger.error("explainer %s: %s", slug, exc)
                counts["errors"] += 1

    logger.info("generate_all_landing_pages: %s", counts)
    return counts
