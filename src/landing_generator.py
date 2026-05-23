"""Landing page generator — creates pillar, spoke, condition, state, and explainer pages."""
from __future__ import annotations
import json
import logging
from datetime import date, datetime
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
    "va-benefits",
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
    "bilateral-hearing-loss", "gulf-war-illness", "radiculopathy-lower",
    "radiculopathy-upper", "degenerative-disc-disease", "hemorrhoids",
    "irritable-bowel-syndrome", "gerd", "rhinitis", "sinusitis",
    "skin-conditions-dermatitis",
]

VA_BENEFITS_SPOKES = [
    "gi-bill",
    "dic",
    "va-home-loan",
    "sgli",
    "vgli",
    "va-healthcare",
    "va-pension",
    "vocational-rehab",
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

VA_BENEFITS_SPOKE_RESEARCH = {
    "gi-bill": {
        "title": "GI Bill Benefits Guide",
        "seo_title": "GI Bill Benefits 2026: Post-9/11, Montgomery & Comparison",
        "h1": "GI Bill Benefits: Everything Veterans Need to Know in 2026",
        "seo_description": "Complete GI Bill guide — compare Post-9/11 vs. Montgomery GI Bill, learn eligibility, housing stipend (BAH rates), tuition coverage, and how to apply.",
        "primary_keyword": "gi bill",
        "secondary_keywords": ["post 9/11 gi bill", "gi bill comparison", "va education benefits", "gi bill housing stipend", "montgomery gi bill"],
        "key_points": [
            "The Post-9/11 GI Bill covers 100% of in-state tuition at public schools, plus a monthly housing allowance based on BAH rates.",
            "You have 36 months of total GI Bill benefits — plan your semesters carefully.",
            "The GI Bill housing stipend equals the E-5 with dependents BAH rate for your school's zip code.",
            "You can transfer unused GI Bill benefits to a spouse or child if you commit to additional service.",
        ],
        "internal_links": {
            "BAH Calculator": "/tools/bah-calculator/",
            "Military Pay": "/military-pay/",
            "VA Benefits Hub": "/va-benefits/",
        },
    },
    "dic": {
        "title": "DIC Benefits for Surviving Spouses",
        "seo_title": "DIC Benefits 2026: Dependency & Indemnity Compensation Guide",
        "h1": "DIC Benefits: Dependency and Indemnity Compensation for Survivors",
        "seo_description": "DIC benefits guide for surviving spouses and dependents — 2026 rates, eligibility, how to apply, and how DIC compares to the Survivor Benefit Plan (SBP).",
        "primary_keyword": "dic benefits",
        "secondary_keywords": ["dependency and indemnity compensation", "va survivor benefits", "dic vs sbp", "dic rates 2026", "va death benefits"],
        "key_points": [
            "DIC pays surviving spouses a tax-free monthly benefit — $1,612.75/month in 2025 (2026 rates pending COLA).",
            "DIC is available when a veteran's death is service-connected or when a 100% P&T-rated veteran dies.",
            "DIC and SBP are separate programs — you may qualify for both, but an SBP offset applies.",
            "You must file VA Form 21-534EZ to apply for DIC benefits.",
        ],
        "internal_links": {
            "Survivor Benefit Plan": "/military-retirement/survivor-benefit-plan/",
            "VA Disability Ratings": "/va-disability/",
            "VA Benefits Hub": "/va-benefits/",
        },
    },
    "va-home-loan": {
        "title": "VA Home Loan Guide",
        "seo_title": "VA Home Loan 2026: Eligibility, Rates & How to Apply",
        "h1": "VA Home Loan: The Complete Guide for Veterans and Servicemembers",
        "seo_description": "VA home loan guide — no down payment, no PMI, competitive rates. Learn eligibility, funding fees, loan limits, and how to get your Certificate of Eligibility (COE).",
        "primary_keyword": "va home loan",
        "secondary_keywords": ["va loan requirements", "va loan rates", "va certificate of eligibility", "va loan no down payment", "va funding fee"],
        "key_points": [
            "VA home loans require zero down payment and no private mortgage insurance (PMI).",
            "You need a Certificate of Eligibility (COE) from the VA — apply online through eBenefits or VA.gov.",
            "The VA funding fee ranges from 1.25% to 3.3% depending on service type, down payment, and whether it's your first use.",
            "Veterans with a 10%+ VA disability rating are exempt from the VA funding fee — saving thousands.",
        ],
        "internal_links": {
            "VA Disability Ratings": "/va-disability/",
            "VA Benefits Hub": "/va-benefits/",
            "BAH Rates": "/military-pay/basic-allowance-housing/",
        },
    },
    "sgli": {
        "title": "SGLI: Servicemembers' Group Life Insurance",
        "seo_title": "SGLI Explained 2026: Coverage, Rates, Cost & Beneficiaries",
        "h1": "SGLI: Servicemembers' Group Life Insurance Guide",
        "seo_description": "SGLI guide — $500,000 max coverage, low-cost premiums, how to update beneficiaries, and what happens to your SGLI when you separate. Rates and enrollment explained.",
        "primary_keyword": "sgli",
        "secondary_keywords": ["sgli coverage amount", "sgli rates", "sgli beneficiary", "servicemembers group life insurance", "sgli cost"],
        "key_points": [
            "SGLI provides up to $500,000 in low-cost life insurance for active-duty servicemembers.",
            "Monthly premiums are just $25/month for the full $500,000 coverage (as of 2025).",
            "SGLI coverage ends 120 days after separation — you must convert to VGLI or a private policy.",
            "Update your SGLI beneficiaries through SOES (Servicemembers Online Enrollment System) — don't rely on outdated DD Form 93.",
        ],
        "internal_links": {
            "VGLI": "/va-benefits/vgli/",
            "Survivor Benefit Plan": "/military-retirement/survivor-benefit-plan/",
            "VA Benefits Hub": "/va-benefits/",
        },
    },
    "vgli": {
        "title": "VGLI: Veterans' Group Life Insurance",
        "seo_title": "VGLI 2026: Rates, Eligibility & How to Convert from SGLI",
        "h1": "VGLI: Veterans' Group Life Insurance After Separation",
        "seo_description": "VGLI guide for veterans — convert your SGLI within 240 days of separation. Compare VGLI rates, coverage amounts, and whether VGLI or private insurance is the better deal.",
        "primary_keyword": "vgli",
        "secondary_keywords": ["vgli rates", "vgli vs sgli", "vgli enrollment", "veterans group life insurance", "vgli cost by age"],
        "key_points": [
            "You have 240 days after separation to convert SGLI to VGLI with no health screening required.",
            "VGLI premiums increase every 5 years as you age — it gets expensive after 50.",
            "VGLI coverage maxes at $500,000 (matching your SGLI amount at separation).",
            "For younger, healthy veterans, a private term life policy is almost always cheaper than VGLI.",
        ],
        "internal_links": {
            "SGLI": "/va-benefits/sgli/",
            "Survivor Benefit Plan": "/military-retirement/survivor-benefit-plan/",
            "VA Benefits Hub": "/va-benefits/",
        },
    },
    "va-healthcare": {
        "title": "VA Healthcare Benefits",
        "seo_title": "VA Healthcare 2026: Eligibility, Priority Groups & Enrollment",
        "h1": "VA Healthcare: Eligibility, Enrollment, and What's Covered",
        "seo_description": "VA healthcare guide — eligibility requirements, 8 priority groups, how to enroll, copays, and what VA medical centers cover. Separate from TRICARE.",
        "primary_keyword": "va healthcare",
        "secondary_keywords": ["va health benefits", "va healthcare eligibility", "va priority groups", "va medical center", "va healthcare enrollment"],
        "key_points": [
            "VA healthcare is separate from TRICARE — it's a VA-run system of 1,300+ medical facilities.",
            "Eligibility is based on 8 priority groups — veterans with service-connected disabilities get the highest priority.",
            "Veterans with a 50%+ disability rating get free VA healthcare with no copays.",
            "Enroll through VA.gov, by phone (1-877-222-8387), or in person at any VA medical center.",
        ],
        "internal_links": {
            "TRICARE Options": "/explainers/tricare-options-explained/",
            "VA Disability Ratings": "/va-disability/",
            "VA Benefits Hub": "/va-benefits/",
        },
    },
    "va-pension": {
        "title": "VA Pension for Wartime Veterans",
        "seo_title": "VA Pension 2026: Eligibility, Rates & Aid and Attendance",
        "h1": "VA Pension: Income-Based Benefits for Wartime Veterans",
        "seo_description": "VA pension guide — not the same as VA disability compensation. Learn eligibility (wartime service + income limits), 2026 rates, Aid and Attendance, and Housebound benefits.",
        "primary_keyword": "va pension",
        "secondary_keywords": ["va pension rates", "aid and attendance", "housebound benefit", "va pension vs disability", "wartime veteran pension"],
        "key_points": [
            "VA pension is NOT the same as VA disability compensation — it's income-based, not tied to a service-connected condition.",
            "You must have 90+ days of active service with at least 1 day during a wartime period.",
            "The Aid and Attendance add-on increases monthly pension for veterans who need daily living assistance.",
            "VA pension is reduced dollar-for-dollar by other income sources — countable income must fall below the Maximum Annual Pension Rate (MAPR).",
        ],
        "internal_links": {
            "VA Disability Ratings": "/va-disability/",
            "VA Benefits Hub": "/va-benefits/",
            "Military Retirement Pay": "/military-retirement/",
        },
    },
    "vocational-rehab": {
        "title": "VA Vocational Rehabilitation (VR&E / Chapter 31)",
        "seo_title": "VA Vocational Rehab 2026: Chapter 31 VR&E Eligibility & Benefits",
        "h1": "VA Vocational Rehab: Chapter 31 VR&E Program Guide",
        "seo_description": "VA Vocational Rehabilitation (VR&E / Chapter 31) guide — eligibility, 5 career tracks, how it compares to the GI Bill, and how to apply. For veterans with service-connected disabilities.",
        "primary_keyword": "va vocational rehab",
        "secondary_keywords": ["chapter 31 vre", "va voc rehab eligibility", "vre benefits", "vocational rehabilitation veterans", "vre vs gi bill"],
        "key_points": [
            "VR&E (Chapter 31) provides career counseling, training, education, and job placement for veterans with service-connected disabilities.",
            "You need at least a 10% VA disability rating and an employment handicap to qualify.",
            "VR&E can cover tuition, books, supplies, and a monthly subsistence allowance — similar to GI Bill but with more support services.",
            "Using VR&E does NOT consume your GI Bill entitlement — they're separate benefits (though you can't use both simultaneously).",
        ],
        "internal_links": {
            "GI Bill": "/va-benefits/gi-bill/",
            "VA Disability Ratings": "/va-disability/",
            "VA Benefits Hub": "/va-benefits/",
        },
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
        "title": "VA Disability Rates & Rating Explained",
        "subtitle": "VA disability rates, the combined rating formula, and why it's not simple addition",
        "key_points": [
            "VA uses a 'whole person' method: each rating reduces the remaining able-bodied percentage.",
            "50% + 50% does NOT equal 100% under VA math.",
            "The final rating is rounded to the nearest 10%.",
        ],
    },
    "pact-act-explained": {
        "title": "PACT Act & Presumptive Conditions Explained",
        "subtitle": "The PACT Act's presumptive conditions list and what it means for burn-pit veterans",
        "key_points": [
            "Signed into law August 2022, the PACT Act is the largest expansion of VA presumptive benefits in decades.",
            "It establishes presumptive service connection for 23 burn-pit/toxic-exposure cancers.",
            "Veterans who deployed to Southwest Asia on or after August 2, 1990 may qualify under presumptive coverage.",
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
            model=settings.openai_narrative_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an SEO content writer for Rank and Pay. "
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
    """Insert or update a LandingPage row.

    Maps the generator's logical fields to the actual model columns:
      slug            → page_key
      h1 / subtitle   → subtitle (stored as "h1 | subtitle")
      seo_description → summary
      key_takeaways   → sections_json
    """
    import json as _json

    # Store h1 in subtitle (the primary display heading for the page).
    # seo_description goes to summary. Both are rendered by the template.
    stored_subtitle = h1  # templates use page.subtitle as the page H1
    stored_sections = _json.dumps(key_takeaways or [])

    existing = session.query(LandingPage).filter_by(page_key=slug).first()
    if existing:
        existing.title = title
        existing.subtitle = stored_subtitle
        existing.summary = seo_description
        existing.body_html = body_html
        if faq_json is not None:
            existing.faq_json = faq_json  # model stores as JSON natively
        existing.sections_json = stored_sections
        existing.last_generated_at = datetime.utcnow()
        session.add(existing)
        return existing

    page = LandingPage(
        page_key=slug,
        canonical_path=canonical_path,
        page_type=page_type,
        title=title,
        subtitle=stored_subtitle,
        summary=seo_description,
        body_html=body_html,
        faq_json=faq_json or [],
        sections_json=stored_sections,
    )
    session.add(page)
    return page


def generate_pillar_page(slug: str, dry_run: bool = False) -> Optional[LandingPage]:
    from src.config import settings

    titles = {
        "va-claims": ("VA Claims Guide", "How to File a VA Claim", "A complete guide to filing and winning your VA disability claim"),
        "va-disability": ("VA Disability Ratings", "VA Disability Ratings & Benefits for Disabled Veterans", "How VA rates disabilities, calculates your combined rating, and what disability benefits you qualify for"),
        "va-benefits": ("VA Benefits", "VA Benefits: The Complete Guide for Veterans", "All VA benefits in one place — disability compensation, GI Bill, VA home loans, healthcare, life insurance, survivor benefits, and more"),
        "military-retirement": ("Military Retirement Pay", "Military Retirement Pay Guide", "Everything you need to know about military retirement and the BRS"),
        "military-pay": ("Military Pay Charts", "Military Pay Tables & BAH Rates", "Current military pay tables, BAH rates, and BAS allowances"),
        "state-benefits": ("State Veterans Benefits", "State Veterans Benefits by State", "Property tax exemptions, tuition waivers, and more — by state"),
        "explainers": ("VA & Military Benefits Explainers", "VA & Military Benefits Explained", "Plain-English guides to the most confusing benefits topics"),
    }
    if slug not in titles:
        logger.warning("generate_pillar_page: unknown pillar %r", slug)
        return None

    title, h1, subtitle = titles[slug]

    if slug == "va-benefits":
        prompt = (
            "You are an expert SEO content writer. Write a 1,500-word hub page for 'VA Benefits: The Complete Guide for Veterans'. "
            "\n\nPrimary keywords: 'va benefits' and 'veterans benefits' — use them in the first paragraph, 2-3 H2s, and conclusion."
            "\n\nThis page is a comprehensive overview hub that links to deeper spoke pages. "
            "Cover each major VA benefit category with a 2-3 paragraph summary and link to its dedicated page:"
            "\n- Disability Compensation → <a href='/va-disability/'>VA Disability Ratings</a>"
            "\n- Filing a VA Claim → <a href='/va-claims/'>VA Claims Guide</a>"
            "\n- GI Bill & Education → <a href='/va-benefits/gi-bill/'>GI Bill Benefits</a>"
            "\n- VA Home Loans → <a href='/va-benefits/va-home-loan/'>VA Home Loan Guide</a>"
            "\n- VA Healthcare → <a href='/va-benefits/va-healthcare/'>VA Healthcare</a>"
            "\n- DIC & Survivor Benefits → <a href='/va-benefits/dic/'>DIC Benefits</a>"
            "\n- Life Insurance (SGLI/VGLI) → <a href='/va-benefits/sgli/'>SGLI</a> and <a href='/va-benefits/vgli/'>VGLI</a>"
            "\n- VA Pension → <a href='/va-benefits/va-pension/'>VA Pension</a>"
            "\n- Vocational Rehab (VR&E) → <a href='/va-benefits/vocational-rehab/'>Vocational Rehab</a>"
            "\n- Military Retirement → <a href='/military-retirement/'>Retirement Pay Guide</a>"
            "\n\nAlso link to tools: <a href='/tools/va-disability-rating-calculator/'>VA Rating Calculator</a>, "
            "<a href='/tools/bah-calculator/'>BAH Calculator</a>."
            "\n\nStructure: Use h2 for each benefit category, h3 for sub-topics, p and ul/li for content. "
            "Include a table of contents at the top. Add a comparison table summarizing all benefits "
            "(columns: Benefit, Who Qualifies, Monthly Value, How to Apply). "
            "End with a strong CTA. Include 2026 references. Use plain HTML only, no markdown."
        )
    else:
        prompt = (
            f"Write a 400-word pillar page introduction for '{h1}'. "
            "Explain the topic, why it matters to veterans, and what the reader will learn. "
            "Use h2, p, and ul/li HTML only. Link internally where relevant."
        )
    max_tok = 4000 if slug == "va-benefits" else 1200
    body = "" if dry_run else (_llm_generate(prompt, settings, max_tokens=max_tok) or "")

    page_key = f"pillar:{slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=page_key,
            canonical_path=f"/{slug}/",
            page_type="pillar",
            title=f"{title} | Rank and Pay",
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

    # Check for structured research data (VA Benefits spokes have detailed SEO metadata)
    research = VA_BENEFITS_SPOKE_RESEARCH.get(spoke_slug, {})

    if research:
        display = research["title"]
        seo_title = research.get("seo_title", f"{display} | Rank and Pay")
        h1 = research.get("h1", display)
        seo_desc = research.get("seo_description", f"Complete guide to {display.lower()} for veterans.")
        key_points = research.get("key_points", [])
        primary_kw = research.get("primary_keyword", "")
        secondary_kws = research.get("secondary_keywords", [])
        internal_links = research.get("internal_links", {})

        # Build a detailed SEO-optimized prompt using the research data
        links_str = ", ".join([f"{label} ({url})" for label, url in internal_links.items()])
        secondary_str = ", ".join(secondary_kws)
        prompt = (
            f"You are an expert SEO content writer creating a high-ranking, helpful article. "
            f"Write a 2,000-word guide about '{h1}'. "
            f"\n\nPrimary keyword: '{primary_kw}' — use it in the first paragraph, conclusion, and 2-3 H2/H3 headings. "
            f"Secondary keywords to weave in naturally: {secondary_str}. "
            f"\n\nKey facts to cover:\n" + "\n".join(f"- {pt}" for pt in key_points) +
            f"\n\nStructure requirements:"
            f"\n- Use h2, h3, p, ul/li, and table HTML only. No markdown."
            f"\n- Include a table of contents at the top with anchor links."
            f"\n- Add an FAQ section with 4-5 common questions at the bottom."
            f"\n- Include comparison tables where relevant."
            f"\n- Add internal links using <a> tags to these pages: {links_str}"
            f"\n- Include 2026 data, current rates, and recent policy changes where applicable."
            f"\n- End with a clear conclusion and call-to-action directing readers to related tools or guides."
            f"\n- Demonstrate E-E-A-T: cite VA.gov, CFR references, and official program details."
            f"\n- Optimize for featured snippets: use concise definitions, numbered lists, and direct answers."
            f"\n\nWrite factual, practical content. No fluff, no filler. Every paragraph should teach something."
        )
    else:
        display = spoke_slug.replace("-", " ").title()
        seo_title = f"{display} | Rank and Pay"
        h1 = display
        seo_desc = f"Learn everything about {display.lower()} for your VA claim."
        key_points = []
        prompt = (
            f"Write a 600-word guide about '{display}' for veterans. "
            "Include: why it matters, step-by-step guidance, common mistakes, and tips. "
            "Use h2, h3, p, ul/li HTML only."
        )

    body = "" if dry_run else (_llm_generate(prompt, settings, max_tokens=4000) or "")

    page_key = f"spoke:{pillar}:{spoke_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=page_key,
            canonical_path=f"/{pillar}/{spoke_slug}/",
            page_type="spoke",
            title=seo_title,
            h1=h1,
            subtitle=seo_desc,
            seo_description=seo_desc,
            body_html=body,
            key_takeaways=key_points,
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

    page_key = f"condition:{condition_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=page_key,
            canonical_path=f"/va-disability/{condition_slug}/",
            page_type="condition",
            title=f"VA Disability for {display_name} | Rank and Pay",
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

    page_key = f"state:{state_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=page_key,
            canonical_path=f"/state-benefits/{state_slug}/",
            page_type="state",
            title=f"{display_name} Veterans Benefits | Rank and Pay",
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

    page_key = f"explainer:{explainer_slug}"
    with Session(engine) as session:
        page = _upsert_page(
            session,
            slug=page_key,
            canonical_path=f"/explainers/{explainer_slug}/",
            page_type="explainer",
            title=f"{title} | Rank and Pay",
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
        for slug in VA_BENEFITS_SPOKES:
            try:
                generate_spoke_page("va-benefits", slug, dry_run=dry_run)
                counts["spokes"] += 1
            except Exception as exc:
                logger.error("spoke va-benefits/%s: %s", slug, exc)
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
