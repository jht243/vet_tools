#!/usr/bin/env python3
"""
Rank and Pay — Flask web server.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime, date, timedelta
from functools import wraps
from typing import Optional

import httpx
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from src.config import settings
from src.models import (
    BlogPost,
    EmailCapture,
    ExternalArticleEntry,
    LandingPage,
    SessionLocal,
    VACondition,
    init_db,
)
from src.page_renderer import (
    build_blog_post_jsonld,
    build_blog_post_seo,
    build_landing_page_jsonld,
    build_landing_page_seo,
    build_seo_base,
    register_jinja_filters,
    render_blog_feed_xml,
)
from src.storage_remote import fetch_report_html, supabase_storage_read_enabled

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates", static_folder="static")
register_jinja_filters(app)
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new-hampshire", "new-jersey",
    "new-mexico", "new-york", "north-carolina", "north-dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode-island", "south-carolina",
    "south-dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west-virginia", "wisconsin", "wyoming",
}

VA_CLAIMS_SPOKES = {
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
    "benefits-delivery-at-discharge",
    "va-claim-denied",
}

RETIREMENT_SPOKES = {
    "final-pay-retirement",
    "high-36-retirement",
    "blended-retirement-system",
    "disability-retirement-vs-chapter61",
    "reserve-retirement-points",
    "survivor-benefit-plan",
    "concurrent-receipt-crsc-crdp",
}

MILITARY_PAY_SPOKES = {
    "basic-pay", "basic-allowance-housing", "special-pays",
    "pcs-entitlements",
    "army-pay-chart", "army-pay-calculator",
    "navy-pay-chart", "air-force-pay-chart",
}

GI_BILL_SPOKES = {
    "post-9-11", "comparison",
}

VA_FORMS = {
    "21-526ez", "21-4138", "21-0781", "21-8940",
}

VA_BENEFITS_SPOKES = {
    "gi-bill", "dic", "va-home-loan", "sgli", "vgli",
    "va-healthcare", "va-pension", "vocational-rehab",
}

TOOLS_DATA = [
    {
        "slug": "va-disability-rating-calculator",
        "title": "VA Disability Rating Calculator",
        "description": "Calculate your combined VA disability rating using the whole-person method and see your estimated monthly compensation.",
        "icon": "⚖️",
        "live": True,
        "template": "tool_va_rating.html.j2",
        "seo_title": "VA Disability Rating Calculator 2026 | Free VA Calculator | Rank and Pay",
        "seo_description": "Free VA calculator — compute your combined VA disability rating using the official whole-person method. Get your estimated 2026 monthly compensation and check TDIU eligibility. No signup required.",
    },
    {
        "slug": "military-retirement-calculator",
        "title": "Military Retirement Pay Calculator",
        "description": "Estimate your monthly military retirement pay under Final Pay, High-36, or the Blended Retirement System (BRS).",
        "icon": "🎖️",
        "live": True,
        "template": "tool_retirement.html.j2",
        "seo_title": "Military Retirement Pay Calculator 2026 | Rank and Pay",
        "seo_description": "Estimate your military retirement pay under Final Pay, High-36, or Blended Retirement System. Enter your grade and years of service for an instant 2026 calculation — free.",
    },
    {
        "slug": "bah-calculator",
        "title": "BAH Calculator",
        "description": "Estimate your Basic Allowance for Housing by pay grade and dependent status, with links to the official DoD BAH tool.",
        "icon": "🏠",
        "live": True,
        "template": "tool_bah.html.j2",
        "seo_title": "BAH Calculator 2026: Military Housing Allowance | Rank and Pay",
        "seo_description": "Estimate your 2026 Basic Allowance for Housing (BAH) by pay grade and dependent status. See national average ranges and get your exact local rate from DoD — free tool.",
    },
    {
        "slug": "military-pay-calculator",
        "title": "Military Pay Calculator",
        "description": "See your full military pay breakdown: base pay, BAH, BAS, and estimated take-home after taxes.",
        "icon": "💰",
        "live": True,
        "template": "tool_military_pay.html.j2",
        "seo_title": "2026 Military Base Pay Calculator | Rank and Pay",
        "seo_description": "Calculate your full 2026 military pay: base pay, BAH, BAS, and estimated take-home after federal taxes. Select your grade and years of service for an instant breakdown — free.",
    },
    {
        "slug": "crsc-crdp-calculator",
        "title": "CRSC vs CRDP Calculator",
        "description": "Find out whether Combat-Related Special Compensation (CRSC) or Concurrent Retirement and Disability Pay (CRDP) pays you more.",
        "icon": "⚔️",
        "live": True,
        "template": "tool_crsc_crdp.html.j2",
        "seo_title": "CRSC vs CRDP Calculator: Which Pays More? | Rank and Pay",
        "seo_description": "Compare CRSC vs CRDP side-by-side to find which concurrent receipt option pays you more. Enter your retirement pay and VA rating for an instant 2026 estimate — free tool.",
    },
    {
        "slug": "va-claim-checklist",
        "title": "VA Disability Claim Checklist",
        "description": "Interactive checklist of every document and form you need to file a strong VA disability claim.",
        "icon": "✅",
        "live": True,
        "template": "tool_checklist.html.j2",
        "seo_title": "VA Disability Claim Checklist 2026 | Rank and Pay",
        "seo_description": "Complete interactive checklist for filing a VA disability claim in 2026. Track your evidence, forms, and statements with a progress bar. Saves automatically — free, no signup.",
    },
    {
        "slug": "secondary-conditions-lookup",
        "title": "Secondary Conditions Lookup",
        "description": "Look up common secondary service-connected conditions linked to primary diagnoses like PTSD, back pain, and tinnitus.",
        "icon": "🔍",
        "live": True,
        "template": "tool_secondary_conditions.html.j2",
        "seo_title": "VA Secondary Conditions Lookup Tool | Rank and Pay",
        "seo_description": "Look up secondary service-connected VA conditions by primary diagnosis. Understand the medical nexus for PTSD, back pain, tinnitus, TBI, and more — free lookup tool.",
    },
    {
        "slug": "bah-comparison",
        "title": "BAH Comparison Tool",
        "description": "Compare BAH rates side-by-side for 2-3 duty stations to see which location pays more housing allowance.",
        "icon": "📊",
        "live": True,
        "template": "tool_bah_comparison.html.j2",
        "seo_title": "BAH Comparison Tool 2026: Compare Rates by Location",
        "seo_description": "Compare BAH rates side-by-side for multiple duty stations. See which location pays more housing allowance by grade and dependent status.",
    },
    {
        "slug": "va-back-pay-calculator",
        "title": "VA Back Pay Calculator",
        "description": "Estimate your VA disability back pay based on your effective date, decision date, and disability rating.",
        "icon": "💵",
        "live": True,
        "template": "tool_back_pay.html.j2",
        "seo_title": "VA Back Pay Calculator 2026 | Estimate Retroactive Pay",
        "seo_description": "Calculate your estimated VA disability back pay. Enter your effective date, rating, and dependents to see your retroactive lump sum — free tool.",
    },
    {
        "slug": "military-retirement-checklist",
        "title": "Military Retirement Checklist",
        "description": "Interactive checklist covering every step of military retirement — from 12 months out through your first 90 days as a retiree.",
        "icon": "📋",
        "live": True,
        "template": "tool_retirement_checklist.html.j2",
        "seo_title": "Military Retirement Checklist 2026 | Rank and Pay",
        "seo_description": "Interactive military retirement checklist — track every step from 12 months out through your first 90 days. SBP, VA claims, DFAS, TRICARE. Free.",
    },
    {
        "slug": "va-claim-eligibility",
        "title": "Can I Still File a VA Claim?",
        "description": "Answer a few questions to find out if you're eligible to file a VA disability claim and which filing path is right for you.",
        "icon": "🔀",
        "live": True,
        "template": "tool_claim_decision_tree.html.j2",
        "seo_title": "Can I Still File a VA Claim? | Eligibility Check",
        "seo_description": "Find out if you can still file a VA disability claim. Answer a few questions about your service and get a personalized filing recommendation — free.",
    },
    {
        "slug": "total-retirement-income-estimator",
        "title": "Total Retirement Income Estimator",
        "description": "Combine military retirement pay, VA disability compensation, and TSP withdrawals into one total monthly income estimate.",
        "icon": "📈",
        "live": True,
        "template": "tool_retirement_estimator.html.j2",
        "seo_title": "Total Military Retirement Income Estimator 2026",
        "seo_description": "Estimate your total military retirement income — combine retirement pay, VA disability compensation, and TSP withdrawals in one monthly picture. Free.",
    },
    {
        "slug": "gi-bill-bah-calculator",
        "title": "GI Bill BAH Calculator",
        "description": "Estimate your Post-9/11 GI Bill Monthly Housing Allowance (MHA) by eligibility tier, course load, and whether you study online or in person.",
        "icon": "🎓",
        "live": True,
        "template": "tool_gi_bill_bah.html.j2",
        "seo_title": "GI Bill BAH Calculator 2026: Housing Allowance (MHA)",
        "seo_description": "Free GI Bill BAH calculator — estimate your 2026 Post-9/11 Monthly Housing Allowance (MHA) by eligibility tier, credit hours, and online vs. in-person study. No signup.",
    },
    {
        "slug": "va-rating-estimator",
        "title": "VA Rating Estimator",
        "description": "Select your conditions to see typical VA disability ratings and estimate your combined rating with monthly compensation.",
        "icon": "🎯",
        "live": True,
        "template": "tool_rating_estimator.html.j2",
        "seo_title": "VA Rating Estimator 2026: What Rating Will I Get?",
        "seo_description": "Estimate your VA disability rating by condition. See typical ratings, calculate your combined rating, and view 2026 monthly compensation — free.",
    },
]

TOOL_SLUGS = {t["slug"] for t in TOOLS_DATA}

# ---------------------------------------------------------------------------
# Eligibility quizzes
# ---------------------------------------------------------------------------

ELIGIBILITY_QUIZZES = {
    "va-disability-claim": {
        "title": "VA Disability Claim Eligibility Quiz",
        "icon": "🎖️",
        "description": "Find out in 60 seconds if you may qualify for VA disability compensation.",
        "cta_url": "/va-claims/how-to-file-a-va-claim/",
        "cta_label": "Read the Full VA Claims Guide",
        "eligible_message": "Based on your answers, you appear to meet the basic eligibility requirements for VA disability compensation. The next step is to gather your evidence and file your claim.",
        "ineligible_message": "Based on your answers, you may not currently qualify for VA disability compensation.",
        "questions": [
            {
                "id": "discharge",
                "question": "What was your discharge status?",
                "help": "Most VA benefits require an honorable or general discharge.",
                "options": [
                    {"label": "Honorable", "qualifies": True},
                    {"label": "General (under honorable conditions)", "qualifies": True},
                    {"label": "Other Than Honorable, Bad Conduct, or Dishonorable", "qualifies": False, "reason": "Most VA disability benefits require an honorable or general discharge. You may be able to apply for a discharge upgrade through your branch's Discharge Review Board."},
                    {"label": "I'm not sure", "qualifies": True},
                ],
            },
            {
                "id": "diagnosis",
                "question": "Do you have a current medical diagnosis of a physical or mental condition?",
                "help": "A current diagnosis from any qualified medical provider counts.",
                "options": [
                    {"label": "Yes, I have a current diagnosis", "qualifies": True},
                    {"label": "I have symptoms but no formal diagnosis yet", "qualifies": True},
                    {"label": "No, I'm in good health currently", "qualifies": False, "reason": "VA disability compensation requires a current medical condition. If you develop a condition later, you can file at that time."},
                ],
            },
            {
                "id": "in-service-event",
                "question": "Did the condition begin during, or was it caused by, your military service?",
                "help": "This includes injuries, illnesses, or events that happened in service — even if symptoms appeared later.",
                "options": [
                    {"label": "Yes, it began or was caused during service", "qualifies": True},
                    {"label": "It was caused by another service-connected condition", "qualifies": True},
                    {"label": "I'm not sure if it's connected to service", "qualifies": True},
                    {"label": "No, it's unrelated to my service", "qualifies": False, "reason": "VA disability compensation requires a service connection. If you have evidence suggesting a link to service, you may still qualify — consult a VSO."},
                ],
            },
            {
                "id": "served",
                "question": "Did you serve on active duty, in the Reserves, or in the National Guard?",
                "options": [
                    {"label": "Active duty", "qualifies": True},
                    {"label": "Reserves with active-duty deployment", "qualifies": True},
                    {"label": "National Guard with federal activation", "qualifies": True},
                    {"label": "Reserves/Guard with no active-duty time", "qualifies": False, "reason": "Reserve and Guard members typically need active-duty service or federal activation to qualify for most VA disability benefits."},
                ],
            },
        ],
    },

    "gi-bill": {
        "title": "GI Bill Eligibility Quiz",
        "icon": "🎓",
        "description": "See if you qualify for Post-9/11 or Montgomery GI Bill education benefits.",
        "cta_url": "/va-benefits/gi-bill/",
        "cta_label": "Read the GI Bill Guide",
        "eligible_message": "Based on your answers, you likely qualify for GI Bill education benefits. Here's everything you need to know to apply and use your benefits.",
        "ineligible_message": "Based on your answers, you may not qualify for the GI Bill at this time.",
        "questions": [
            {
                "id": "service-dates",
                "question": "When did you serve on active duty?",
                "options": [
                    {"label": "After September 10, 2001 (Post-9/11)", "qualifies": True},
                    {"label": "Between 1985 and 2001 (Montgomery GI Bill era)", "qualifies": True},
                    {"label": "Before 1985", "qualifies": False, "reason": "The GI Bill programs primarily cover service after 1985. Older veterans may have different education benefits available — contact your state VA office."},
                ],
            },
            {
                "id": "discharge",
                "question": "What was your discharge status?",
                "options": [
                    {"label": "Honorable", "qualifies": True},
                    {"label": "General (under honorable conditions)", "qualifies": True},
                    {"label": "Other Than Honorable, Bad Conduct, or Dishonorable", "qualifies": False, "reason": "The GI Bill requires an honorable discharge. A discharge upgrade may restore eligibility."},
                    {"label": "Still on active duty", "qualifies": True},
                ],
            },
            {
                "id": "length-of-service",
                "question": "How long did you serve on active duty (or are currently serving)?",
                "help": "Counts cumulative active-duty time after 9/11/2001 for Post-9/11 GI Bill.",
                "options": [
                    {"label": "36+ months", "qualifies": True},
                    {"label": "At least 90 days", "qualifies": True},
                    {"label": "Less than 90 days", "qualifies": False, "reason": "The Post-9/11 GI Bill generally requires at least 90 days of aggregate active-duty service, unless discharged for a service-connected disability."},
                    {"label": "I was discharged early due to a service-connected disability", "qualifies": True},
                ],
            },
        ],
    },

    "va-home-loan": {
        "title": "VA Home Loan Eligibility Quiz",
        "icon": "🏠",
        "description": "Check if you qualify for a VA home loan with zero down payment and no PMI.",
        "cta_url": "/va-benefits/va-home-loan/",
        "cta_label": "Read the VA Home Loan Guide",
        "eligible_message": "Based on your answers, you likely qualify for a VA home loan. The next step is to obtain your Certificate of Eligibility (COE) and find a VA-approved lender.",
        "ineligible_message": "Based on your answers, you may not currently qualify for a VA home loan.",
        "questions": [
            {
                "id": "service-type",
                "question": "What was your service status?",
                "options": [
                    {"label": "Active-duty veteran", "qualifies": True},
                    {"label": "Active duty (currently serving)", "qualifies": True},
                    {"label": "National Guard or Reserves", "qualifies": True},
                    {"label": "Surviving spouse of a veteran", "qualifies": True},
                    {"label": "I never served in the military", "qualifies": False, "reason": "VA home loans are restricted to qualifying veterans, active-duty members, and certain surviving spouses."},
                ],
            },
            {
                "id": "service-length",
                "question": "How long did you serve (or have you been serving)?",
                "help": "Minimum service times vary by service era and discharge reason.",
                "options": [
                    {"label": "24+ months of active duty (or full tour)", "qualifies": True},
                    {"label": "90+ days active duty during wartime", "qualifies": True},
                    {"label": "181+ days active duty during peacetime", "qualifies": True},
                    {"label": "6+ years in the Guard or Reserves", "qualifies": True},
                    {"label": "Discharged early for a service-connected disability", "qualifies": True},
                    {"label": "Less than minimum service time above", "qualifies": False, "reason": "VA home loan minimum service requirements vary by era. You may still qualify under exceptions — request a Certificate of Eligibility (COE) from VA to confirm."},
                ],
            },
            {
                "id": "discharge",
                "question": "Was your discharge under conditions other than dishonorable?",
                "options": [
                    {"label": "Yes (honorable, general, or under honorable conditions)", "qualifies": True},
                    {"label": "I'm currently still serving", "qualifies": True},
                    {"label": "No (dishonorable, bad conduct, or other than honorable)", "qualifies": False, "reason": "VA home loans require a discharge under conditions other than dishonorable. A discharge upgrade may restore eligibility."},
                ],
            },
        ],
    },

    "va-healthcare": {
        "title": "VA Healthcare Eligibility Quiz",
        "icon": "🏥",
        "description": "Find out if you qualify for VA healthcare benefits and which priority group you fit into.",
        "cta_url": "/va-benefits/va-healthcare/",
        "cta_label": "Read the VA Healthcare Guide",
        "eligible_message": "Based on your answers, you likely qualify for VA healthcare. Your specific priority group will determine your copays and access to certain services.",
        "ineligible_message": "Based on your answers, you may not currently qualify for VA healthcare enrollment.",
        "questions": [
            {
                "id": "served",
                "question": "Did you serve in active military, naval, or air service?",
                "options": [
                    {"label": "Yes, active duty", "qualifies": True},
                    {"label": "Reserves/Guard with federal activation", "qualifies": True},
                    {"label": "Reserves/Guard with no active-duty time", "qualifies": False, "reason": "VA healthcare generally requires active-duty service or federal activation."},
                    {"label": "No", "qualifies": False, "reason": "VA healthcare is restricted to veterans who served in active military, naval, or air service."},
                ],
            },
            {
                "id": "service-length",
                "question": "How long did you serve on active duty?",
                "help": "Most veterans need at least 24 months of active duty, with exceptions for early service members and those discharged for disability.",
                "options": [
                    {"label": "24+ months or the full period for which I was called to active duty", "qualifies": True},
                    {"label": "Enlisted before September 7, 1980 (any length)", "qualifies": True},
                    {"label": "Discharged for a service-connected disability", "qualifies": True},
                    {"label": "Less than 24 months and none of the above", "qualifies": False, "reason": "Generally you need 24 months of active duty to qualify, but exceptions exist for hardship discharges, early-out programs, and combat veterans."},
                ],
            },
            {
                "id": "discharge",
                "question": "What was your discharge status?",
                "options": [
                    {"label": "Honorable", "qualifies": True},
                    {"label": "General (under honorable conditions)", "qualifies": True},
                    {"label": "Other than honorable / Bad conduct / Dishonorable", "qualifies": False, "reason": "VA healthcare requires a discharge under conditions other than dishonorable. A discharge upgrade may restore eligibility."},
                ],
            },
        ],
    },

    "military-retirement": {
        "title": "Military Retirement Eligibility Quiz",
        "icon": "🏅",
        "description": "Find out if you qualify for military retirement pay and which system applies to you.",
        "cta_url": "/military-retirement/",
        "cta_label": "Explore Military Retirement Guides",
        "eligible_message": "Based on your answers, you likely qualify for military retirement pay. The retirement system that applies depends on your entry date.",
        "ineligible_message": "Based on your answers, you may not yet qualify for a regular military retirement.",
        "questions": [
            {
                "id": "component",
                "question": "Are/were you active duty or Reserve/Guard?",
                "options": [
                    {"label": "Active duty", "qualifies": True},
                    {"label": "Reserves or National Guard", "qualifies": True},
                ],
            },
            {
                "id": "years-of-service",
                "question": "How many years have you served (or will you serve)?",
                "help": "For active duty: years of service. For Reserves/Guard: qualifying years with at least 50 points.",
                "options": [
                    {"label": "20+ years", "qualifies": True},
                    {"label": "Medically retired with 30%+ disability (any years)", "qualifies": True},
                    {"label": "15-19 years (TERA/early retirement may apply)", "qualifies": True},
                    {"label": "Less than 15 years and not medically retired", "qualifies": False, "reason": "Standard military retirement requires 20 years of service. You may still receive separation pay or VA disability compensation depending on your circumstances."},
                ],
            },
            {
                "id": "discharge",
                "question": "Did/will you discharge under honorable conditions?",
                "options": [
                    {"label": "Yes (honorable or general)", "qualifies": True},
                    {"label": "Still serving", "qualifies": True},
                    {"label": "No (other than honorable, bad conduct, dishonorable)", "qualifies": False, "reason": "Military retirement requires an honorable discharge. Less-than-honorable discharges can result in loss of retirement benefits."},
                ],
            },
        ],
    },

    "va-pension": {
        "title": "VA Pension Eligibility Quiz",
        "icon": "💵",
        "description": "See if you qualify for the VA's income-based pension for wartime veterans.",
        "cta_url": "/va-benefits/va-pension/",
        "cta_label": "Read the VA Pension Guide",
        "eligible_message": "Based on your answers, you may qualify for VA Pension. Aid & Attendance and Housebound benefits can add additional monthly amounts on top of the base pension.",
        "ineligible_message": "Based on your answers, you may not currently qualify for the VA pension program.",
        "questions": [
            {
                "id": "wartime-service",
                "question": "Did you serve at least 90 days of active duty with at least one day during a wartime period?",
                "help": "Wartime periods include WWII, Korea, Vietnam, Gulf War (1990-present), and others.",
                "options": [
                    {"label": "Yes, I served during wartime", "qualifies": True},
                    {"label": "I served, but only during peacetime", "qualifies": False, "reason": "The VA pension specifically requires wartime service. You may still qualify for other VA benefits like disability compensation or healthcare."},
                    {"label": "I didn't serve in the military", "qualifies": False, "reason": "VA pension is restricted to qualifying wartime veterans and their surviving spouses."},
                ],
            },
            {
                "id": "discharge",
                "question": "Was your discharge under conditions other than dishonorable?",
                "options": [
                    {"label": "Yes", "qualifies": True},
                    {"label": "No", "qualifies": False, "reason": "VA pension requires a discharge under conditions other than dishonorable. A discharge upgrade may restore eligibility."},
                ],
            },
            {
                "id": "age-or-disability",
                "question": "Are you age 65+ or have a permanent and total disability?",
                "options": [
                    {"label": "Yes, I'm 65 or older", "qualifies": True},
                    {"label": "Yes, I have a permanent and total disability", "qualifies": True},
                    {"label": "I'm receiving SSI or SSDI", "qualifies": True},
                    {"label": "I'm in a nursing home receiving long-term care", "qualifies": True},
                    {"label": "None of the above", "qualifies": False, "reason": "VA pension requires you to be 65+, permanently and totally disabled, or receiving certain disability benefits."},
                ],
            },
            {
                "id": "income",
                "question": "Is your countable family income below the VA's annual pension limit?",
                "help": "The 2026 Maximum Annual Pension Rate for a single veteran with no dependents is approximately $16,965.",
                "options": [
                    {"label": "Yes, my income is below the limit", "qualifies": True},
                    {"label": "I'm not sure", "qualifies": True},
                    {"label": "No, my income is above the limit", "qualifies": False, "reason": "VA pension is needs-based. If your income exceeds the limit, you won't qualify — but certain medical expenses can reduce your countable income."},
                ],
            },
        ],
    },

    "vocational-rehab": {
        "title": "Vocational Rehab (VR&E) Eligibility Quiz",
        "icon": "🛠️",
        "description": "See if you qualify for Chapter 31 Vocational Rehabilitation and Employment benefits.",
        "cta_url": "/va-benefits/vocational-rehab/",
        "cta_label": "Read the VR&E Guide",
        "eligible_message": "Based on your answers, you likely qualify for VR&E (Chapter 31) benefits. VR&E can pay for training, education, and equipment to help you get and keep employment.",
        "ineligible_message": "Based on your answers, you may not currently qualify for VR&E.",
        "questions": [
            {
                "id": "discharge",
                "question": "Was your discharge under conditions other than dishonorable?",
                "options": [
                    {"label": "Yes", "qualifies": True},
                    {"label": "I'm currently on active duty", "qualifies": True},
                    {"label": "No", "qualifies": False, "reason": "VR&E requires a discharge under conditions other than dishonorable."},
                ],
            },
            {
                "id": "disability-rating",
                "question": "Do you have a VA service-connected disability rating?",
                "help": "VR&E generally requires a rating of at least 10% (or 20% for some programs).",
                "options": [
                    {"label": "Yes, 20% or higher", "qualifies": True},
                    {"label": "Yes, 10%", "qualifies": True},
                    {"label": "Memorandum rating of 20%+ from active duty", "qualifies": True},
                    {"label": "Not rated, or 0% only", "qualifies": False, "reason": "VR&E generally requires a service-connected rating of at least 10%. File a VA disability claim first if you have qualifying conditions."},
                ],
            },
            {
                "id": "employment-handicap",
                "question": "Does your service-connected disability create a barrier to getting or keeping a job?",
                "options": [
                    {"label": "Yes, it limits the types of work I can do", "qualifies": True},
                    {"label": "Yes, it's prevented me from finding suitable work", "qualifies": True},
                    {"label": "I'm not sure", "qualifies": True},
                    {"label": "No, my disability doesn't affect my ability to work", "qualifies": False, "reason": "VR&E specifically helps veterans whose service-connected disability creates an employment barrier. If yours doesn't, the GI Bill may be a better fit."},
                ],
            },
        ],
    },

    "dic": {
        "title": "DIC (Survivor Benefits) Eligibility Quiz",
        "icon": "❤️",
        "description": "Find out if you qualify for Dependency and Indemnity Compensation as a survivor.",
        "cta_url": "/va-benefits/dic/",
        "cta_label": "Read the DIC Guide",
        "eligible_message": "Based on your answers, you may qualify for DIC. DIC is a tax-free monthly benefit paid to eligible survivors of service members and veterans whose death was service-connected.",
        "ineligible_message": "Based on your answers, you may not currently qualify for DIC benefits.",
        "questions": [
            {
                "id": "relationship",
                "question": "What is your relationship to the deceased veteran or service member?",
                "options": [
                    {"label": "Surviving spouse", "qualifies": True},
                    {"label": "Surviving child (under 18, or 18-23 if in school)", "qualifies": True},
                    {"label": "Dependent parent", "qualifies": True},
                    {"label": "Other relationship", "qualifies": False, "reason": "DIC is paid to surviving spouses, qualifying children, and dependent parents only."},
                ],
            },
            {
                "id": "cause-of-death",
                "question": "Was the veteran's death related to military service?",
                "help": "This includes deaths from service-connected conditions, even years after discharge.",
                "options": [
                    {"label": "Yes, died from a service-connected condition", "qualifies": True},
                    {"label": "Yes, died on active duty or active for training", "qualifies": True},
                    {"label": "Veteran was rated 100% (or TDIU) for 10+ years before death", "qualifies": True},
                    {"label": "Veteran was rated 100% (or TDIU) for 5+ years right after discharge", "qualifies": True},
                    {"label": "No, death was unrelated to service", "qualifies": False, "reason": "DIC generally requires a service-connected cause of death OR that the veteran was rated 100% or TDIU for the required period before death."},
                ],
            },
            {
                "id": "spouse-criteria",
                "question": "If you're a surviving spouse, which applies to you?",
                "help": "Skip if you selected child or parent above.",
                "options": [
                    {"label": "I was married to the veteran for 1+ years", "qualifies": True},
                    {"label": "We had a child together", "qualifies": True},
                    {"label": "We married within 15 years of the veteran's discharge", "qualifies": True},
                    {"label": "I'm a dependent child or parent (not spouse)", "qualifies": True},
                    {"label": "None of the above", "qualifies": False, "reason": "Surviving spouses generally need at least 1 year of marriage, a shared child, or marriage within 15 years of the veteran's discharge to qualify for DIC."},
                ],
            },
        ],
    },
}

QUIZ_SLUGS = set(ELIGIBILITY_QUIZZES.keys())

EXPLAINER_SLUGS = {
    "what-is-a-nexus-letter",
    "va-disability-rating-explained",
    "pact-act-explained",
    "cdr-explained",
    "tdiu-explained",
    "va-intent-to-file",
    "va-claim-status-guide",
    "va-appeals-process",
    "blended-retirement-system",
    "bah-explained",
    "tricare-options-explained",
    "government-shutdown-veterans",
    "military-retirement-pay-calculator-guide",
    "va-ebenefits-vs-va-gov",
    "va-buddy-statement-guide",
    "va-disability-back-pay",
    "tsp-withdrawal-strategies",
    "post-9-11-gi-bill-bah",
    "100-percent-disabled-veteran-benefits-by-state",
    "100-percent-va-disability-benefits",
    "100-percent-va-disability-pay",
    "how-to-get-100-va-disability",
    "va-disability-rates-2026",
    "va-disability-pay-dates-2026",
    "va-cola-2026",
    "pact-act-presumptive-conditions",
    "presumptive-conditions",
    "38-cfr-rating-schedule",
    "sgli-explained",
    "vgli-explained",
    "military-life-insurance",
    "tdiu-benefits",
    "tdiu-approval-rate",
    "va-unemployability-vs-100-percent",
    "veterans-evaluation-services",
    "optum-serve-cp-exam",
}

BLOG_POSTS_PER_PAGE = 20

# ---------------------------------------------------------------------------
# In-memory page cache
# ---------------------------------------------------------------------------

_PAGE_CACHE: dict[str, tuple[float, str]] = {}
_PAGE_CACHE_TTL = 90  # seconds


def _cached_page(cache_key: str, render_fn) -> str:
    now = time.time()
    if cache_key in _PAGE_CACHE:
        ts, html = _PAGE_CACHE[cache_key]
        if now - ts < _PAGE_CACHE_TTL:
            return html
    html = render_fn()
    _PAGE_CACHE[cache_key] = (now, html)
    return html


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _gzip_response(html: str, status: int = 200) -> Response:
    if len(html) < 500 or "gzip" not in request.headers.get("Accept-Encoding", ""):
        return Response(html, status=status, mimetype="text/html; charset=utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(html.encode("utf-8"))
    return Response(
        buf.getvalue(),
        status=status,
        mimetype="text/html; charset=utf-8",
        headers={"Content-Encoding": "gzip"},
    )


# ---------------------------------------------------------------------------
# Admin decorator
# ---------------------------------------------------------------------------

def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not settings.admin_token:
            abort(404)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.admin_token}":
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Landing page helpers
# ---------------------------------------------------------------------------

def _build_cluster_ctx(page: LandingPage) -> dict:
    """Build navigation cluster context based on the page's type and sector."""
    page_type = page.page_type or ""
    sector = page.sector_slug or ""
    return {
        "page_type": page_type,
        "sector": sector,
        "canonical_path": page.canonical_path or "/",
    }


def _get_recent_briefings(limit: int = 3, sector_filter: Optional[str] = None) -> list:
    db = SessionLocal()
    try:
        q = db.query(BlogPost).order_by(BlogPost.published_date.desc())
        if sector_filter:
            q = q.filter(BlogPost.primary_sector == sector_filter)
        return q.limit(limit).all()
    finally:
        db.close()


def _build_breadcrumbs(page: LandingPage) -> list[dict]:
    """Build breadcrumb list from canonical_path."""
    base = settings.canonical_site_url
    crumbs = [{"label": "Home", "url": "/"}]
    path = (page.canonical_path or "/").strip("/")
    parts = [p for p in path.split("/") if p]
    accumulated = ""
    label_map = {
        "va-claims": "VA Claims",
        "va-disability": "VA Disability",
        "va-benefits": "VA Benefits",
        "military-retirement": "Military Retirement",
        "military-pay": "Military Pay",
        "state-benefits": "State Benefits",
        "explainers": "Explainers",
        "briefing": "Briefings",
    }
    for i, part in enumerate(parts):
        accumulated += f"/{part}"
        label = label_map.get(part, part.replace("-", " ").title())
        crumbs.append({"label": label, "url": accumulated + "/"})
    return crumbs


_FAQ_SECTION_RE = re.compile(
    r'<h2[^>]*id=["\']?faq["\']?[^>]*>.*?(?=<h2[ >]|\Z)',
    re.DOTALL | re.IGNORECASE,
)


def _strip_body_faq(html: str) -> str:
    """Remove an FAQ section from body_html so the template's faq_json version is the only one."""
    return _FAQ_SECTION_RE.sub('', html)


def _serve_landing_page(
    page_key: str, template: str = "landing.html.j2", **extra_ctx
) -> Response:
    # Use in-memory cache for landing pages to avoid repeated DB round-trips on
    # every request. Cache key includes the template name so different templates
    # for the same page_key don't collide. extra_ctx is intentionally not part
    # of the key — it's only used for tool pages where content is client-side.
    cache_key = f"lp:{page_key}:{template}"

    def _render() -> str:
        db = SessionLocal()
        try:
            page = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if not page:
                return ""
            seo = build_landing_page_seo(page)
            faq = page.faq_json or []
            if faq and page.body_html:
                page.body_html = _strip_body_faq(page.body_html)
            jsonld = build_landing_page_jsonld(page, seo, faq_block=faq)
            cluster_ctx = _build_cluster_ctx(page)
            recent = _get_recent_briefings(limit=3, sector_filter=page.sector_slug)
            breadcrumbs = _build_breadcrumbs(page)
            return render_template(
                template,
                page=page,
                seo=seo,
                jsonld=jsonld,
                faq=faq,
                breadcrumbs=breadcrumbs,
                cluster_ctx=cluster_ctx,
                recent_briefings=recent,
                **extra_ctx,
            )
        finally:
            db.close()

    html = _cached_page(cache_key, _render)
    if not html:
        abort(404)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Homepage
# ---------------------------------------------------------------------------

@app.route("/")
def homepage():
    def _render():
        db = SessionLocal()
        try:
            total = db.query(BlogPost).count()
            recent_posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .limit(6)
                .all()
            )
            seo = build_seo_base(
                title="Free VA Disability & Military Benefits Tools | Rank and Pay",
                description=settings.site_description,
                path="/",
                og_type="website",
            )
            return render_template(
                "homepage.html.j2",
                seo=seo,
                total_briefings=total,
                recent_posts=recent_posts,
                recent_briefings=recent_posts,
            )
        finally:
            db.close()

    html = _cached_page("homepage", _render)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Blog
# ---------------------------------------------------------------------------

@app.route("/briefing/")
def blog_index():
    page_num = request.args.get("page", 1, type=int)
    if page_num < 1:
        page_num = 1

    db = SessionLocal()
    try:
        total = db.query(BlogPost).count()
        posts = (
            db.query(BlogPost)
            .order_by(BlogPost.published_date.desc())
            .offset((page_num - 1) * BLOG_POSTS_PER_PAGE)
            .limit(BLOG_POSTS_PER_PAGE)
            .all()
        )
        total_pages = max(1, (total + BLOG_POSTS_PER_PAGE - 1) // BLOG_POSTS_PER_PAGE)

        seo = build_seo_base(
            title="VA & Military Benefits Briefings | Rank and Pay",
            description=(
                "Daily briefings covering VA disability claims, military retirement, "
                "pay tables, legislation, and veteran benefits news."
            ),
            path="/briefing/",
        )
        html = render_template(
            "blog_index.html.j2",
            seo=seo,
            posts=posts,
            page=page_num,
            total_pages=total_pages,
            total=total,
        )
        return _gzip_response(html)
    finally:
        db.close()


@app.route("/briefing/feed.xml")
def blog_feed():
    db = SessionLocal()
    try:
        posts = (
            db.query(BlogPost)
            .order_by(BlogPost.published_date.desc())
            .limit(50)
            .all()
        )
        xml = render_blog_feed_xml(posts)
        return Response(xml, status=200, mimetype="application/atom+xml; charset=utf-8")
    finally:
        db.close()


@app.route("/briefing/<slug>/")
def blog_post(slug: str):
    db = SessionLocal()
    try:
        post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
        if not post:
            abort(404)
        seo = build_blog_post_seo(post)
        jsonld = build_blog_post_jsonld(post, seo)
        related: list = []
        if post.related_slugs_json:
            related = (
                db.query(BlogPost)
                .filter(BlogPost.slug.in_(post.related_slugs_json))
                .limit(4)
                .all()
            )
        html = render_template(
            "blog_post.html.j2",
            post=post,
            seo=seo,
            jsonld=jsonld,
            related_posts=related,
        )
        return _gzip_response(html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — Sources
# ---------------------------------------------------------------------------

@app.route("/sources/")
def sources():
    seo = build_seo_base(
        title="Our Sources | Rank and Pay",
        description=(
            "Rank and Pay draws from official VA, DoD, and federal government "
            "sources to deliver accurate veteran benefits information."
        ),
        path="/sources/",
    )
    html = render_template("sources.html.j2", seo=seo)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Tools
# ---------------------------------------------------------------------------

@app.route("/tools/")
def tools_index():
    seo = build_seo_base(
        title="Free VA & Military Benefits Tools | Rank and Pay",
        description=(
            "Free calculators and tools for VA disability ratings, BAH, military pay, "
            "CRSC/CRDP, and more — no signup required."
        ),
        path="/tools/",
    )
    quizzes = [
        {"slug": slug, "title": q["title"], "description": q["description"], "icon": q.get("icon", "❓")}
        for slug, q in ELIGIBILITY_QUIZZES.items()
    ]
    html = render_template("tools_index.html.j2", seo=seo, tools=TOOLS_DATA, quizzes=quizzes)
    return _gzip_response(html)


@app.route("/tools/<tool_slug>/")
def tool_page(tool_slug: str):
    if tool_slug not in TOOL_SLUGS:
        abort(404)
    tool = next((t for t in TOOLS_DATA if t["slug"] == tool_slug), None)
    if tool is None:
        abort(404)
    seo = build_seo_base(
        title=tool["seo_title"],
        description=tool["seo_description"],
        path=f"/tools/{tool_slug}/",
    )
    base_url = "https://rankandpay.org"
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebApplication",
                "name": tool["title"],
                "description": tool["description"],
                "url": f"{base_url}/tools/{tool_slug}/",
                "applicationCategory": "FinanceApplication",
                "operatingSystem": "Any",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                "browserRequirements": "Requires JavaScript",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"},
                    {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{base_url}/tools/"},
                    {"@type": "ListItem", "position": 3, "name": tool["title"], "item": f"{base_url}/tools/{tool_slug}/"},
                ],
            },
        ],
    })
    html = render_template(
        tool["template"],
        seo=seo,
        tool=tool,
        jsonld=jsonld,
    )
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Eligibility quizzes
# ---------------------------------------------------------------------------

@app.route("/tools/<quiz_slug>-eligibility-quiz/")
def eligibility_quiz_page(quiz_slug: str):
    if quiz_slug not in QUIZ_SLUGS:
        abort(404)
    quiz = ELIGIBILITY_QUIZZES[quiz_slug]
    path = f"/tools/{quiz_slug}-eligibility-quiz/"
    seo = build_seo_base(
        title=f"{quiz['title']} | Rank and Pay",
        description=quiz["description"],
        path=path,
    )
    breadcrumbs = [
        {"label": "Home", "url": "/"},
        {"label": "Tools", "url": "/tools/"},
        {"label": quiz["title"], "url": path},
    ]
    html = render_template(
        "tool_eligibility_quiz.html.j2",
        seo=seo,
        quiz=quiz,
        breadcrumbs=breadcrumbs,
    )
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — VA Claims pillar + spokes
# ---------------------------------------------------------------------------

@app.route("/va-claims/")
def va_claims_pillar():
    spoke_links = [
        {"url": "/va-claims/how-to-file-a-va-claim/", "label": "How to File a VA Claim", "description": "Step-by-step walkthrough of the VA claims process from start to finish."},
        {"url": "/va-claims/service-connection-requirements/", "label": "Service Connection", "description": "What the VA requires to link your condition to military service."},
        {"url": "/va-claims/nexus-letter-guide/", "label": "Nexus Letters", "description": "How to get a medical nexus letter that supports your claim."},
        {"url": "/va-claims/c-and-p-exam-tips/", "label": "C&P Exam Tips", "description": "What to expect and how to prepare for your Compensation & Pension exam."},
        {"url": "/va-claims/va-claim-timeline/", "label": "Claim Timeline", "description": "How long VA claims take and what each stage means."},
        {"url": "/va-claims/buddy-statement-guide/", "label": "Buddy Statements", "description": "How lay statements from fellow service members strengthen your claim."},
        {"url": "/va-claims/va-claim-checklist/", "label": "Claim Checklist", "description": "Everything you need to gather before filing your VA claim."},
        {"url": "/va-claims/secondary-conditions/", "label": "Secondary Conditions", "description": "How to claim conditions caused or aggravated by a service-connected disability."},
        {"url": "/va-claims/va-rating-increase/", "label": "Rating Increase", "description": "How to request a higher VA disability rating when your condition worsens."},
        {"url": "/va-claims/claim-for-increase/", "label": "Claim for Increase", "description": "File a claim for increase when your disability has gotten worse."},
        {"url": "/va-claims/benefits-delivery-at-discharge/", "label": "BDD Program", "description": "File your claim 180–90 days before separation for faster benefits."},
        {"url": "/va-claims/va-claim-denied/", "label": "Claim Denied?", "description": "Your options after a VA claim denial — supplemental claims, HLR, and appeals."},
        {"url": "/va-intent-to-file/", "label": "VA Intent to File", "description": "Lock your effective date for back pay for 12 months while you gather evidence."},
        {"url": "/va-claim-status/", "label": "Check Claim Status", "description": "Track your VA disability claim through every stage on VA.gov."},
        {"url": "/va-forms/", "label": "VA Disability Forms", "description": "Every form you may need: 21-526EZ, 21-4138, 21-0781, 21-8940, and more."},
    ]
    return _serve_landing_page(
        "pillar:va-claims", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="Navigate the VA Claims Process",
        intro_text="Filing a VA disability claim can be overwhelming. Use the guides below to understand each step — from gathering evidence to appealing a denial.",
        quiz_url="/tools/va-disability-claim-eligibility-quiz/",
        quiz_cta_title="Not sure if you qualify for VA disability?",
        quiz_cta_text="Take our free 60-second eligibility quiz.",
    )


@app.route("/va-claims/<spoke>/")
def va_claims_spoke(spoke: str):
    if spoke not in VA_CLAIMS_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:va-claims:{spoke}")


# ---------------------------------------------------------------------------
# Routes — VA Disability pillar + condition pages
# ---------------------------------------------------------------------------

@app.route("/va-disability/")
def va_disability_pillar():
    db = SessionLocal()
    try:
        conditions = db.query(VACondition).order_by(VACondition.name).all()
        spoke_links = [
            {"url": "/va-disability-conditions-list/", "label": "VA Conditions List", "description": "Every VA-rated condition with diagnostic codes and rating ranges."},
            {"url": "/va-disability-percentages/", "label": "VA Disability Percentages", "description": "What each rating from 0% to 100% means and pays in 2026."},
            {"url": "/va-disability-cheat-sheet/", "label": "VA Disability Cheat Sheet", "description": "Quick-reference pay rates, combined rating math, and key deadlines."},
            {"url": "/explainers/38-cfr-rating-schedule/", "label": "38 CFR Rating Schedule", "description": "How the VA rating rulebook is organized and how to read it."},
            {"url": "/explainers/va-disability-rates-2026/", "label": "2026 VA Pay Chart", "description": "Full 2026 VA disability pay chart by rating and dependents."},
        ] + [
            {
                "url": f"/va-disability/{c.slug}/",
                "label": c.display_name,
                "description": c.short_description or "",
            }
            for c in conditions
        ]
    finally:
        db.close()
    return _serve_landing_page(
        "pillar:va-disability", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="VA Disability Ratings by Condition",
        intro_text="Select a condition below to see how the VA rates it, what evidence you need, and which secondary conditions may apply.",
        quiz_url="/tools/va-disability-claim-eligibility-quiz/",
        quiz_cta_title="Not sure if you qualify for VA disability?",
        quiz_cta_text="Take our free 60-second eligibility quiz.",
    )


@app.route("/va-disability/<condition>/")
def va_disability_condition(condition: str):
    cache_key = f"va-disability-condition:{condition}"
    if cache_key in _PAGE_CACHE:
        ts, cached_html = _PAGE_CACHE[cache_key]
        if time.time() - ts < _PAGE_CACHE_TTL:
            if cached_html == "__404__":
                abort(404)
            return _gzip_response(cached_html)

    db = SessionLocal()
    try:
        va_condition = (
            db.query(VACondition).filter(VACondition.slug == condition).first()
        )
        if va_condition:
            # Try a matching LandingPage for richer content; fall back to condition row
            landing = (
                db.query(LandingPage)
                .filter(LandingPage.page_key == f"condition:{condition}")
                .first()
            )
            if landing:
                faq = landing.faq_json or []
                body_html = landing.body_html or ""
                if faq and body_html:
                    body_html = _strip_body_faq(body_html)
                seo = build_landing_page_seo(landing)
                jsonld = build_landing_page_jsonld(landing, seo, faq_block=faq)
                cluster_ctx = _build_cluster_ctx(landing)
                recent = _get_recent_briefings(limit=3, sector_filter=landing.sector_slug)
                breadcrumbs = [
                    {"label": "Home", "url": "/"},
                    {"label": "VA Disability", "url": "/va-disability/"},
                    {"label": va_condition.name, "url": f"/va-disability/{condition}/"},
                ]
                html = render_template(
                    "condition_detail.html.j2",
                    page=landing,
                    condition=va_condition,
                    seo=seo,
                    jsonld=jsonld,
                    faq=faq,
                    body_html=body_html,
                    key_takeaways=landing.key_takeaways,
                    breadcrumbs=breadcrumbs,
                    cluster_ctx=cluster_ctx,
                    recent_briefings=recent,
                )
            else:
                seo = build_seo_base(
                    title=f"{va_condition.name} VA Disability | Rank and Pay",
                    description=(
                        f"VA disability ratings, evidence requirements, and secondary "
                        f"conditions for {va_condition.name}."
                    ),
                    path=f"/va-disability/{condition}/",
                )
                breadcrumbs = [
                    {"label": "Home", "url": "/"},
                    {"label": "VA Disability", "url": "/va-disability/"},
                    {"label": va_condition.name, "url": f"/va-disability/{condition}/"},
                ]
                html = render_template(
                    "condition_detail.html.j2",
                    page=None,
                    condition=va_condition,
                    seo=seo,
                    jsonld="{}",
                    faq=[],
                    body_html="",
                    key_takeaways=[],
                    breadcrumbs=breadcrumbs,
                    cluster_ctx={},
                    recent_briefings=[],
                )
            _PAGE_CACHE[cache_key] = (time.time(), html)
            return _gzip_response(html)

        # No VACondition row — check for a LandingPage
        landing = (
            db.query(LandingPage)
            .filter(LandingPage.page_key == f"condition:{condition}")
            .first()
        )
        if not landing:
            _PAGE_CACHE[cache_key] = (time.time(), "__404__")
            abort(404)
        faq = landing.faq_json or []
        seo = build_landing_page_seo(landing)
        jsonld = build_landing_page_jsonld(landing, seo, faq_block=faq)
        cluster_ctx = _build_cluster_ctx(landing)
        recent = _get_recent_briefings(limit=3, sector_filter=landing.sector_slug)
        breadcrumbs = _build_breadcrumbs(landing)
        html = render_template(
            "landing.html.j2",
            page=landing,
            seo=seo,
            jsonld=jsonld,
            faq=faq,
            breadcrumbs=breadcrumbs,
            cluster_ctx=cluster_ctx,
            recent_briefings=recent,
        )
        _PAGE_CACHE[cache_key] = (time.time(), html)
        return _gzip_response(html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — Military Retirement
# ---------------------------------------------------------------------------

@app.route("/military-retirement/")
def military_retirement_pillar():
    spoke_links = [
        {"url": "/military-retirement/final-pay-retirement/", "label": "Final Pay Retirement", "description": "Legacy retirement system based on your final base pay at retirement."},
        {"url": "/military-retirement/high-36-retirement/", "label": "High-36 Retirement", "description": "Retirement pay calculated from your highest 36 months of base pay."},
        {"url": "/military-retirement/blended-retirement-system/", "label": "Blended Retirement (BRS)", "description": "The new system combining reduced pension with TSP matching."},
        {"url": "/military-retirement/disability-retirement-vs-chapter61/", "label": "Disability Retirement", "description": "Medical retirement vs. Chapter 61 separation — key differences."},
        {"url": "/military-retirement/reserve-retirement-points/", "label": "Reserve Retirement Points", "description": "How Guard and Reserve members earn and calculate retirement points."},
        {"url": "/military-retirement/survivor-benefit-plan/", "label": "Survivor Benefit Plan (SBP)", "description": "Protecting your spouse's income after you pass — costs and coverage."},
        {"url": "/military-retirement/concurrent-receipt-crsc-crdp/", "label": "CRSC & CRDP", "description": "Concurrent receipt rules for collecting both retirement and VA disability pay."},
        {"url": "/tools/military-retirement-calculator/", "label": "Retirement Calculator", "description": "Estimate your monthly retirement pay under any system."},
    ]
    return _serve_landing_page(
        "pillar:military-retirement", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="Plan Your Military Retirement",
        intro_text="Whether you're under the legacy system or BRS, the guides below cover every aspect of military retirement pay, survivor benefits, and concurrent receipt.",
        quiz_url="/tools/military-retirement-eligibility-quiz/",
        quiz_cta_title="Will you qualify for military retirement?",
        quiz_cta_text="Take our free quiz to see which retirement system applies and whether you're on track.",
    )


@app.route("/military-retirement/<spoke>/")
def military_retirement_spoke(spoke: str):
    if spoke not in RETIREMENT_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:military-retirement:{spoke}")


# ---------------------------------------------------------------------------
# Routes — Military Pay
# ---------------------------------------------------------------------------

@app.route("/military-pay/")
def military_pay_pillar():
    spoke_links = [
        {"url": "/military-pay/basic-pay/", "label": "Base Pay Tables", "description": "Monthly base pay by rank and years of service for all branches."},
        {"url": "/military-pay/basic-allowance-housing/", "label": "BAH Rates", "description": "Basic Allowance for Housing rates by location, rank, and dependents."},
        {"url": "/military-pay/special-pays/", "label": "Special & Incentive Pay", "description": "Hazardous duty, flight pay, dive pay, and other special pays."},
        {"url": "/military-pay/pcs-entitlements/", "label": "PCS Entitlements", "description": "Moving allowances, DITY moves, TLE, and per diem for PCS orders."},
        {"url": "/military-pay/army-pay-chart/", "label": "Army Pay Chart 2026", "description": "Army monthly basic pay by rank and years of service."},
        {"url": "/military-pay/navy-pay-chart/", "label": "Navy Pay Chart 2026", "description": "Navy monthly basic pay by rank and years of service."},
        {"url": "/military-pay/air-force-pay-chart/", "label": "Air Force Pay Chart 2026", "description": "Air Force monthly basic pay by rank and years of service."},
        {"url": "/military-pay/army-pay-calculator/", "label": "Army Pay Calculator", "description": "Estimate Army monthly pay including BAH, BAS, and special pays."},
        {"url": "/tools/bah-calculator/", "label": "BAH Calculator", "description": "Look up your BAH rate by zip code, rank, and dependency status."},
        {"url": "/tools/military-pay-calculator/", "label": "Military Pay Calculator", "description": "Estimate your total military compensation including allowances."},
    ]
    return _serve_landing_page(
        "pillar:military-pay", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="Understand Your Military Pay",
        intro_text="Base pay, BAH, BAS, and special pays — use the guides and calculators below to see exactly what you're entitled to.",
    )


@app.route("/military-pay/<spoke>/")
def military_pay_spoke(spoke: str):
    if spoke not in MILITARY_PAY_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:military-pay:{spoke}")


# ---------------------------------------------------------------------------
# Routes — VA Benefits pillar + spoke pages
# ---------------------------------------------------------------------------

@app.route("/va-benefits/")
def va_benefits_pillar():
    spoke_links = [
        {"url": "/gi-bill/", "label": "GI Bill Benefits", "description": "Post-9/11, Montgomery GI Bill, housing stipend, and eligibility."},
        {"url": "/va-education-benefits/", "label": "VA Education Benefits", "description": "Every education program: GI Bill, VR&E, DEA, Fry Scholarship, Yellow Ribbon."},
        {"url": "/va-benefits/va-home-loan/", "label": "VA Home Loan", "description": "Zero down payment, no PMI, and how to get your COE."},
        {"url": "/va-benefits/va-healthcare/", "label": "VA Healthcare", "description": "Eligibility, priority groups, enrollment, and copays."},
        {"url": "/dic-benefits/", "label": "DIC Survivor Benefits", "description": "$1,699/mo tax-free DIC for surviving spouses and dependents."},
        {"url": "/va-survivor-benefits/", "label": "VA Survivor Benefits", "description": "DIC, Survivors Pension, CHAMPVA, Chapter 35, and burial benefits."},
        {"url": "/va-life-insurance/", "label": "VA Life Insurance", "description": "Compare SGLI, VGLI, VALife, and VMLI in one guide."},
        {"url": "/explainers/sgli-explained/", "label": "SGLI Explained", "description": "Active-duty $500K life insurance for $26/month in 2026."},
        {"url": "/explainers/vgli-explained/", "label": "VGLI Explained", "description": "Convert your SGLI after separation — rates and enrollment."},
        {"url": "/va-benefits/va-pension/", "label": "VA Pension", "description": "Income-based benefits for wartime veterans and Aid & Attendance."},
        {"url": "/va-benefits/vocational-rehab/", "label": "Vocational Rehab (VR&E)", "description": "Chapter 31 career training for disabled veterans."},
        {"url": "/va-disability/", "label": "VA Disability Ratings", "description": "How VA rates service-connected disabilities."},
        {"url": "/va-claims/", "label": "VA Claims Guide", "description": "Step-by-step guide to filing your VA disability claim."},
        {"url": "/va-forms/", "label": "VA Disability Forms", "description": "Every disability form: 21-526EZ, 21-4138, 21-0781, 21-8940."},
    ]
    return _serve_landing_page(
        "pillar:va-benefits", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="Explore Your VA Benefits",
        intro_text="From the GI Bill to VA home loans, the guides below break down every major benefit available to veterans and their families.",
    )


@app.route("/va-benefits/<spoke>/")
def va_benefits_spoke(spoke: str):
    if spoke not in VA_BENEFITS_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:va-benefits:{spoke}")


# ---------------------------------------------------------------------------
# Routes — State Benefits
# ---------------------------------------------------------------------------

@app.route("/state-benefits/")
def state_benefits_hub():
    spoke_links = [
        {"url": f"/state-benefits/{s}/", "label": s.replace("-", " ").title()}
        for s in sorted(US_STATES)
    ]
    return _serve_landing_page(
        "pillar:state-benefits", template="pillar.html.j2", spokes=spoke_links,
        intro_heading="Find Your State's Veterans Benefits",
        intro_text="Every state offers its own veterans benefits — property tax exemptions, tuition waivers, and more. Select your state below to see what's available.",
    )


@app.route("/state-benefits/<state>/")
def state_benefits_page(state: str):
    if state not in US_STATES:
        abort(404)
    return _serve_landing_page(f"state:{state}")


# ---------------------------------------------------------------------------
# Routes — Explainers
# ---------------------------------------------------------------------------

@app.route("/explainers/")
def explainers_index():
    db = SessionLocal()
    try:
        pages = (
            db.query(LandingPage)
            .filter(LandingPage.page_type == "explainer")
            .order_by(LandingPage.title)
            .all()
        )
        seo = build_seo_base(
            title="VA & Military Benefits Explainers | Rank and Pay",
            description=(
                "Plain-language explainers for VA disability ratings, military retirement, "
                "BAH, appeals, and more — written for veterans, not lawyers."
            ),
            path="/explainers/",
        )
        html = render_template("explainers_index.html.j2", seo=seo, pages=pages)
        return _gzip_response(html)
    finally:
        db.close()


@app.route("/explainers/<slug>/")
def explainer_detail(slug: str):
    if slug not in EXPLAINER_SLUGS:
        abort(404)
    return _serve_landing_page(f"explainer:{slug}")


# ---------------------------------------------------------------------------
# Routes — Top-level SEO content pages (Priority 4-11 from keyword inventory)
# ---------------------------------------------------------------------------

@app.route("/va-disability-conditions-list/")
def va_disability_conditions_list():
    return _serve_landing_page("page:va-disability-conditions-list")


@app.route("/va-disability-percentages/")
def va_disability_percentages():
    return _serve_landing_page("page:va-disability-percentages")


@app.route("/va-disability-cheat-sheet/")
def va_disability_cheat_sheet():
    return _serve_landing_page("page:va-disability-cheat-sheet")


@app.route("/dic-benefits/")
def dic_benefits():
    return _serve_landing_page("page:dic-benefits")


@app.route("/va-survivor-benefits/")
def va_survivor_benefits():
    return _serve_landing_page("page:va-survivor-benefits")


@app.route("/va-survivor-benefits/dic-vs-sbp/")
def va_survivor_dic_vs_sbp():
    return _serve_landing_page("page:va-survivor-benefits-dic-vs-sbp")


@app.route("/va-life-insurance/")
def va_life_insurance():
    return _serve_landing_page("page:va-life-insurance")


@app.route("/va-intent-to-file/")
def va_intent_to_file():
    return _serve_landing_page("page:va-intent-to-file")


@app.route("/va-claim-status/")
def va_claim_status():
    return _serve_landing_page("page:va-claim-status")


@app.route("/va-education-benefits/")
def va_education_benefits():
    return _serve_landing_page("page:va-education-benefits")


# VA Forms cluster
@app.route("/va-forms/")
def va_forms_hub():
    return _serve_landing_page("hub:va-forms")


@app.route("/va-forms/<form_id>/")
def va_forms_detail(form_id: str):
    if form_id not in VA_FORMS:
        abort(404)
    return _serve_landing_page(f"form:{form_id}")


# GI Bill cluster
@app.route("/gi-bill/")
def gi_bill_hub():
    return _serve_landing_page("hub:gi-bill")


@app.route("/gi-bill/<spoke>/")
def gi_bill_spoke(spoke: str):
    if spoke not in GI_BILL_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:gi-bill:{spoke}")


# ---------------------------------------------------------------------------
# Routes — XML / Technical
# ---------------------------------------------------------------------------

@app.route("/sitemap.xml")
def sitemap():
    base = settings.canonical_site_url
    now = datetime.utcnow().strftime("%Y-%m-%d")

    urls: list[tuple[str, str, str]] = [
        # (loc, lastmod, changefreq)
        (f"{base}/", now, "daily"),
        (f"{base}/briefing/", now, "daily"),
        (f"{base}/tools/", now, "weekly"),
        (f"{base}/sources/", now, "monthly"),
        (f"{base}/explainers/", now, "weekly"),
        (f"{base}/va-claims/", now, "weekly"),
        (f"{base}/va-disability/", now, "weekly"),
        (f"{base}/military-retirement/", now, "weekly"),
        (f"{base}/military-pay/", now, "weekly"),
        (f"{base}/va-benefits/", now, "weekly"),
        (f"{base}/state-benefits/", now, "weekly"),
        (f"{base}/about/", now, "monthly"),
        (f"{base}/privacy/", now, "monthly"),
        (f"{base}/terms/", now, "monthly"),
        (f"{base}/contact/", now, "monthly"),
    ]

    for spoke in sorted(VA_CLAIMS_SPOKES):
        urls.append((f"{base}/va-claims/{spoke}/", now, "monthly"))
    for spoke in sorted(RETIREMENT_SPOKES):
        urls.append((f"{base}/military-retirement/{spoke}/", now, "monthly"))
    for spoke in sorted(MILITARY_PAY_SPOKES):
        urls.append((f"{base}/military-pay/{spoke}/", now, "monthly"))
    for spoke in sorted(VA_BENEFITS_SPOKES):
        urls.append((f"{base}/va-benefits/{spoke}/", now, "monthly"))
    for tool in sorted(TOOL_SLUGS):
        urls.append((f"{base}/tools/{tool}/", now, "monthly"))
    for state in sorted(US_STATES):
        urls.append((f"{base}/state-benefits/{state}/", now, "monthly"))
    # Note: explainer pages are included via the DB landing-page query below,
    # which uses canonical_path (already includes trailing slash). The hardcoded
    # EXPLAINER_SLUGS loop is intentionally omitted here to avoid duplicate sitemap
    # entries. The EXPLAINER_SLUGS set is still used for 404-gating the route.

    db = SessionLocal()
    try:
        posts = db.query(BlogPost.slug, BlogPost.updated_at, BlogPost.published_date).all()
        for row in posts:
            if row.updated_at:
                lastmod = row.updated_at.strftime("%Y-%m-%d")
            elif row.published_date:
                lastmod = (
                    row.published_date.isoformat()
                    if hasattr(row.published_date, "isoformat")
                    else str(row.published_date)
                )
            else:
                lastmod = now
            urls.append((f"{base}/briefing/{row.slug}/", lastmod, "weekly"))

        lp_rows = db.query(LandingPage.canonical_path, LandingPage.updated_at).all()
        for row in lp_rows:
            path = row.canonical_path or ""
            if not path:
                continue
            if not path.startswith("/"):
                path = "/" + path
            lastmod = row.updated_at.strftime("%Y-%m-%d") if row.updated_at else now
            urls.append((f"{base}{path}", lastmod, "monthly"))

        conditions = db.query(VACondition.slug, VACondition.updated_at).all()
        for row in conditions:
            lastmod = row.updated_at.strftime("%Y-%m-%d") if row.updated_at else now
            urls.append((f"{base}/va-disability/{row.slug}/", lastmod, "monthly"))
    finally:
        db.close()

    url_tags = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lm}</lastmod>\n    "
        f"<changefreq>{cf}</changefreq>\n  </url>"
        for loc, lm, cf in urls
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{url_tags}\n"
        "</urlset>"
    )
    return Response(xml, status=200, mimetype="application/xml; charset=utf-8")


@app.route("/news-sitemap.xml")
def news_sitemap():
    base = settings.canonical_site_url
    cutoff = datetime.utcnow() - timedelta(hours=48)

    db = SessionLocal()
    try:
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.created_at >= cutoff)
            .order_by(BlogPost.published_date.desc())
            .limit(1000)
            .all()
        )
        news_tags = []
        for post in posts:
            canonical = f"{base}/briefing/{post.slug}"
            pub_date = ""
            if post.published_date:
                pub_date = (
                    post.published_date.isoformat() + "T00:00:00Z"
                    if hasattr(post.published_date, "isoformat")
                    else str(post.published_date) + "T00:00:00Z"
                )
            title_esc = _xml_escape(post.title or "")
            news_tags.append(
                f"  <url>\n"
                f"    <loc>{canonical}</loc>\n"
                f"    <news:news>\n"
                f"      <news:publication>\n"
                f"        <news:name>{_xml_escape(settings.site_name)}</news:name>\n"
                f"        <news:language>en</news:language>\n"
                f"      </news:publication>\n"
                f"      <news:publication_date>{pub_date}</news:publication_date>\n"
                f"      <news:title>{title_esc}</news:title>\n"
                f"    </news:news>\n"
                f"  </url>"
            )
    finally:
        db.close()

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
        + "\n".join(news_tags)
        + "\n</urlset>"
    )
    return Response(xml, status=200, mimetype="application/xml; charset=utf-8")


@app.route("/robots.txt")
def robots_txt():
    base = settings.canonical_site_url
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin/\n"
        "Disallow: /health\n"
        f"\nSitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/news-sitemap.xml\n"
    )
    return Response(body, status=200, mimetype="text/plain; charset=utf-8")


@app.route("/<path:key_file>.txt")
def indexnow_key_file(key_file: str):
    """Serve the IndexNow key verification file at /<key>.txt."""
    key = settings.indexnow_key or ""
    if not key or key_file != key:
        abort(404)
    return Response(key, status=200, mimetype="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Routes — Static / Legal pages
# ---------------------------------------------------------------------------

@app.route("/about/")
def about_page():
    seo = build_seo_base(
        title="About Rank and Pay | Veterans Benefits Resource",
        description=(
            "Rank and Pay provides free tools, calculators, and daily briefings for "
            "U.S. veterans and military families — covering VA disability, military pay, "
            "BAH, retirement, and state benefits."
        ),
        path="/about/",
    )
    html = render_template("about.html.j2", seo=seo)
    return _gzip_response(html)


@app.route("/privacy/")
def privacy_page():
    seo = build_seo_base(
        title="Privacy Policy | Rank and Pay",
        description="Rank and Pay Privacy Policy — learn how we collect, use, and protect your personal information when you use our free military pay and VA benefits tools.",
        path="/privacy/",
    )
    html = render_template("privacy.html.j2", seo=seo)
    return _gzip_response(html)


@app.route("/terms/")
def terms_page():
    seo = build_seo_base(
        title="Terms of Use | Rank and Pay",
        description="Terms of use for Rank and Pay. Rank and Pay provides general information only — not legal or benefits advice.",
        path="/terms/",
    )
    html = render_template("terms.html.j2", seo=seo)
    return _gzip_response(html)


@app.route("/contact/")
def contact_page():
    seo = build_seo_base(
        title="Contact Rank and Pay | Veterans Benefits Questions",
        description=(
            "Contact Rank and Pay with questions, feedback, or corrections. "
            "We're a small team dedicated to helping veterans navigate benefits."
        ),
        path="/contact/",
    )
    html = render_template("contact.html.j2", seo=seo)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — OG images
# ---------------------------------------------------------------------------

@app.route("/og/briefing/<slug>.png")
def og_image_briefing(slug: str):
    db = SessionLocal()
    try:
        post = (
            db.query(BlogPost.og_image_bytes, BlogPost.title)
            .filter(BlogPost.slug == slug)
            .first()
        )
        if not post:
            abort(404)
        if post.og_image_bytes:
            return Response(
                post.og_image_bytes,
                status=200,
                mimetype="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        # Fallback: redirect to a static default OG image
        return redirect("/static/og-default.png", code=302)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email address"}), 400

    api_key = settings.buttondown_api_key
    if not api_key:
        logger.warning("/api/subscribe called but BUTTONDOWN_API_KEY not set")
        return jsonify({"ok": False, "error": "Newsletter not configured"}), 503

    try:
        resp = httpx.post(
            "https://api.buttondown.email/v1/subscribers",
            headers={"Authorization": f"Token {api_key}"},
            json={"email_address": email},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return jsonify({"ok": True}), 200
        if resp.status_code == 409:
            # Already subscribed — treat as success
            return jsonify({"ok": True, "already_subscribed": True}), 200
        logger.warning("Buttondown subscribe failed %d: %s", resp.status_code, resp.text[:200])
        return jsonify({"ok": False, "error": "Subscription failed"}), 502
    except Exception as exc:
        logger.error("Buttondown subscribe error: %s", exc)
        return jsonify({"ok": False, "error": "Upstream error"}), 502


@app.route("/api/email-capture", methods=["POST"])
def api_email_capture():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    source_tool = (data.get("source_tool") or "").strip()[:120]

    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email address"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else None

    db = SessionLocal()
    try:
        capture = EmailCapture(
            email=email,
            source_tool=source_tool or None,
            capture_date=date.today(),
            ip_hash=ip_hash,
        )
        db.add(capture)
        db.commit()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        db.rollback()
        logger.error("EmailCapture insert error: %s", exc)
        return jsonify({"ok": False, "error": "Could not save email"}), 500
    finally:
        db.close()


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(silent=True) or {}
    honeypot = data.get("honeypot") or data.get("website") or ""
    if honeypot:
        # Silently swallow bot submissions
        return jsonify({"ok": True}), 200

    message = (data.get("message") or "").strip()
    page_url = (data.get("page_url") or "").strip()[:500]

    if not message:
        return jsonify({"ok": False, "error": "Message is required"}), 400

    resend_key = settings.resend_api_key
    if not resend_key:
        logger.info("Feedback received (Resend not configured): %s", message[:100])
        return jsonify({"ok": True}), 200

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.newsletter_from_email,
                "to": [settings.seo_email_recipient],
                "subject": f"[{settings.site_name}] User Feedback",
                "text": f"Page: {page_url}\n\nMessage:\n{message}",
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.warning("Resend feedback email failed %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.error("Resend feedback error: %s", exc)

    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------------
# Routes — Admin
# ---------------------------------------------------------------------------

@app.route("/admin/regen-report", methods=["POST"])
@_require_admin
def admin_regen_report():
    """Trigger an in-process regeneration of key landing pages.

    At launch this clears the in-memory page cache so the next request
    re-renders from the DB. A heavier async job can be wired in here later.
    """
    cleared = list(_PAGE_CACHE.keys())
    _PAGE_CACHE.clear()
    logger.info("Cache cleared by /admin/regen-report: %d keys", len(cleared))
    return jsonify({"ok": True, "cleared_keys": cleared}), 200


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    db = SessionLocal()
    db_ok = False
    briefing_count = 0
    last_briefing_age_hours: Optional[float] = None
    try:
        briefing_count = db.query(BlogPost).count()
        db_ok = True
        latest = (
            db.query(BlogPost.published_date)
            .order_by(BlogPost.published_date.desc())
            .first()
        )
        if latest and latest.published_date:
            pub = latest.published_date
            if hasattr(pub, "year"):
                pub_dt = datetime(pub.year, pub.month, pub.day)
            else:
                pub_dt = datetime.utcnow()
            last_briefing_age_hours = round(
                (datetime.utcnow() - pub_dt).total_seconds() / 3600, 1
            )
    except Exception as exc:
        logger.error("Health check DB error: %s", exc)
    finally:
        db.close()

    warnings = []
    if last_briefing_age_hours is not None and last_briefing_age_hours > 25:
        warnings.append(f"Last briefing is {last_briefing_age_hours}h old (threshold: 25h)")

    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "last_briefing_age_hours": last_briefing_age_hours,
        "briefing_count": briefing_count,
    }
    if warnings:
        payload["warnings"] = warnings

    return jsonify(payload), 200 if db_ok else 503


# ---------------------------------------------------------------------------
# Utility — XML escape (duplicated from page_renderer for local use)
# ---------------------------------------------------------------------------

def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.server_port, debug=True)
