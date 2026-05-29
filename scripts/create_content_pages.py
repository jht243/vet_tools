"""Create / upsert hand-written SEO content pages as LandingPage rows.

Each entry in PAGES becomes a LandingPage served at /explainers/<slug>/.
New explainer slugs must also be added to EXPLAINER_SLUGS in server.py so the
route stops 404-gating them. Run:

    .venv/bin/python -m scripts.create_content_pages          # apply
    .venv/bin/python -m scripts.create_content_pages --dry    # preview

Idempotent: re-running overwrites title/subtitle/summary/body_html/faq for an
existing page_key, leaving other rows untouched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from src.models import LandingPage
from server import SessionLocal


def _page(
    slug: str,
    *,
    title: str,
    h1: str,
    summary: str,
    body_html: str,
    faq: list[dict],
    takeaways: list[str],
    keywords: list[str],
    sector: str | None = None,
) -> dict:
    return {
        "page_key": f"explainer:{slug}",
        "page_type": "explainer",
        "sector_slug": sector,
        "canonical_path": f"/explainers/{slug}/",
        "title": title,
        "subtitle": h1,
        "summary": summary,
        "body_html": body_html.strip(),
        "faq_json": faq,
        "sections_json": json.dumps(takeaways),
        "keywords_json": json.dumps(keywords),
    }


PAGES: list[dict] = []

# ---------------------------------------------------------------------------
# Batch 1 — GI Bill BAH / Monthly Housing Allowance (MHA) guide
# ---------------------------------------------------------------------------

_GIB_BAH_BODY = """
<p>The Post-9/11 GI Bill pays more than tuition. While you go to school, it also
pays a tax-free <strong>Monthly Housing Allowance (MHA)</strong> &mdash; often
called your GI Bill BAH. For many veterans, this housing money is the most
valuable part of the benefit. This guide explains how it works in 2026, how the
VA calculates it, and how to estimate your own payment.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Quick Tools</strong><a href="/tools/gi-bill-bah-calculator/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">GI Bill BAH Calculator &rarr;</a><a href="/va-benefits/gi-bill/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Full GI Bill Guide &rarr;</a><a href="https://www.va.gov/education/gi-bill-comparison-tool/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;" target="_blank" rel="noopener noreferrer">VA Comparison Tool &rarr;</a></div>

<h2>What Is the GI Bill BAH (Monthly Housing Allowance)?</h2>
<p>The MHA is a monthly, tax-free payment that helps cover your rent while you
study. The VA pays it on top of your tuition and your books stipend. It is
called "BAH" because the VA bases it on the military's Basic Allowance for
Housing rates.</p>
<p>One key point: the MHA is paid to <strong>you</strong>, not your school. Your
tuition goes straight to the school. Your housing money lands in your bank
account each month, the same way active-duty BAH works.</p>

<h2>How the VA Calculates Your Post-9/11 GI Bill BAH</h2>
<p>The VA uses three factors to set your monthly payment. Miss any one of them
and your check changes.</p>
<ol>
  <li><strong>Your eligibility tier.</strong> This is the share of the full
  benefit you earned. It depends on how long you served after September 10,
  2001. Only 36+ months of service earns the full 100%.</li>
  <li><strong>Your school's location.</strong> The VA uses the BAH rate for an
  <strong>E-5 with dependents</strong> at the ZIP code where you take most of
  your classes. A school in San Diego pays far more than one in a rural town.</li>
  <li><strong>Your rate of pursuit.</strong> This is your course load. Full time
  is 12 credit hours. You must be enrolled at <strong>more than 50%</strong> to
  get any housing money at all.</li>
</ol>
<p>Put together, the formula looks like this:</p>
<p style="background:var(--sr-gray-bg);border-left:4px solid var(--sr-blue);padding:0.85rem 1.1rem;font-weight:600;">Monthly MHA = Local E-5 (with dependents) BAH &times; Tier % &times; Rate of Pursuit %</p>
<p>Want a number without the math? Use our
<a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a> to estimate
your payment in a few clicks.</p>

<h2>2026 Eligibility Tiers: How Much of the Benefit You Earned</h2>
<p>Your tier is set by your total active-duty service after 9/11. Here is the
current breakdown.</p>
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;font-size:0.92rem;margin:1rem 0;">
<thead><tr style="background:var(--sr-blue);color:#fff;"><th style="padding:0.6rem 0.75rem;text-align:left;">Qualifying Active-Duty Service</th><th style="padding:0.6rem 0.75rem;text-align:right;">% of Benefit (MHA, Tuition, Books)</th></tr></thead>
<tbody>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">36+ months (1,095+ days)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">100%</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">30 to 35 months</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">90%</td></tr>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">24 to 29 months</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">80%</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">18 to 23 months</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">70%</td></tr>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">6 to 17 months</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">60%</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">90 days to 5 months</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">50%</td></tr>
</tbody></table>
</div>
<p>A Purple Heart recipient, or anyone discharged for a service-connected
disability after at least 30 days, qualifies for the full 100% tier.</p>

<h2>Online vs. In-Person Housing Rates for 2026&ndash;2027</h2>
<p>Where you take classes changes your rate a lot. The VA uses the BAH rates
that were in effect on January 1, 2025 to set MHA for the school year that runs
August 1, 2025 through July 31, 2026, and updates them again for 2026&ndash;2027.</p>
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;font-size:0.92rem;margin:1rem 0;">
<thead><tr style="background:var(--sr-blue);color:#fff;"><th style="padding:0.6rem 0.75rem;text-align:left;">How You Attend</th><th style="padding:0.6rem 0.75rem;text-align:right;">Max Monthly MHA (100% tier)</th></tr></thead>
<tbody>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">In person at a U.S. school</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">Local E-5 BAH (varies by ZIP)</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">Online only (distance learning)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$1,261</td></tr>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">Foreign school (in person)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$2,522</td></tr>
</tbody></table>
</div>
<p>The online-only rate equals half of the national average BAH. That is why a
fully online program pays far less than a campus in a big city. Here is the
trick most students miss: taking <strong>even one in-person class</strong> can
move you to the higher local rate for your school's ZIP code.</p>

<h2>Tuition and Books: What Else the GI Bill Pays</h2>
<p>The MHA is just one part of the benefit. At the 100% tier, the Post-9/11 GI
Bill also covers:</p>
<ul>
  <li><strong>Public schools:</strong> full in-state tuition and required fees.</li>
  <li><strong>Private or foreign schools:</strong> up to <strong>$30,908.34</strong>
  per year for 2026&ndash;2027 (up from $29,920.95 the year before).</li>
  <li><strong>Books and supplies:</strong> up to <strong>$1,000 per year</strong>,
  paid at $41.67 per credit hour.</li>
</ul>
<p>If your private school costs more than the cap, the
<a href="https://www.va.gov/education/about-gi-bill-benefits/post-9-11/yellow-ribbon-program/" target="_blank" rel="noopener noreferrer">Yellow Ribbon Program</a>
can help cover the gap at participating schools.</p>

<h2>Worked Example: Estimating Your MHA</h2>
<p>Say you are a 100% tier veteran taking 12 credit hours (full time) at a
school where the E-5 with-dependents BAH is $2,400 a month.</p>
<ul>
  <li>Local BAH: $2,400</li>
  <li>Tier: 100% (&times; 1.00)</li>
  <li>Rate of pursuit: full time (&times; 1.00)</li>
  <li><strong>Estimated MHA: $2,400 per month</strong></li>
</ul>
<p>Now drop to 8 credit hours. The VA counts that as about 67% time and rounds
to 70%. Your payment falls to roughly $1,680 a month. Drop to 6 credits (50%)
and the housing allowance stops entirely.</p>

<h2>Common Mistakes That Lower Your Housing Money</h2>
<ul>
  <li><strong>Going fully online to save time.</strong> It can cut your housing
  payment by more than half.</li>
  <li><strong>Dropping below half time.</strong> One dropped class can end your
  MHA for the term.</li>
  <li><strong>Forgetting that active-duty students get no MHA.</strong> Neither
  do spouses using transferred benefits while the service member is on active
  duty.</li>
  <li><strong>Not verifying enrollment.</strong> The VA pays only after your
  school certifies your classes each term.</li>
</ul>

<p>Ready to run your own numbers? Try the
<a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a>, then read
the full <a href="/va-benefits/gi-bill/">GI Bill guide</a> to learn how to apply
and transfer your benefit to family. Always confirm your estimate with the
<a href="https://www.va.gov/education/gi-bill-comparison-tool/" target="_blank" rel="noopener noreferrer">official VA GI Bill Comparison Tool</a>.</p>
"""

PAGES.append(_page(
    "post-9-11-gi-bill-bah",
    title="Post-9/11 GI Bill BAH 2026: Housing Allowance (MHA) Guide",
    h1="Post-9/11 GI Bill BAH: Your 2026 Monthly Housing Allowance (MHA) Guide",
    summary=(
        "How the Post-9/11 GI Bill BAH works in 2026. Learn how the Monthly "
        "Housing Allowance (MHA) is calculated, online vs. in-person rates, and "
        "how to estimate yours."
    ),
    body_html=_GIB_BAH_BODY,
    faq=[
        {
            "question": "How much is the Post-9/11 GI Bill BAH in 2026?",
            "answer": (
                "It depends on your school's ZIP code. The VA uses the E-5 "
                "with-dependents BAH rate for that location. Online-only "
                "students receive $1,261 per month for the 2026–2027 year, "
                "while in-person rates in high-cost cities can be much higher."
            ),
        },
        {
            "question": "How is GI Bill MHA calculated?",
            "answer": (
                "Your Monthly Housing Allowance equals the local E-5 "
                "with-dependents BAH multiplied by your eligibility tier "
                "(50%–100%) and your rate of pursuit (course load). You must "
                "be enrolled at more than 50% to receive any housing payment."
            ),
        },
        {
            "question": "Do online students get the GI Bill housing allowance?",
            "answer": (
                "Yes, but at a reduced rate. Fully online students get half the "
                "national average BAH — $1,261 per month for 2026–2027. "
                "Taking at least one in-person class can qualify you for the "
                "higher local rate."
            ),
        },
        {
            "question": "Does the GI Bill pay housing during summer break?",
            "answer": (
                "You receive MHA only while enrolled above half time. If you "
                "take summer classes, payments continue. During breaks between "
                "terms, the housing allowance generally stops."
            ),
        },
    ],
    takeaways=[
        "The GI Bill BAH (Monthly Housing Allowance) is a tax-free payment sent to you, not your school.",
        "Your MHA = local E-5 with-dependents BAH × eligibility tier × rate of pursuit.",
        "Online-only students get $1,261/month for 2026–2027; in-person rates vary by ZIP code.",
        "You must be enrolled above 50% (more than half time) to receive any housing money.",
    ],
    keywords=[
        "post 9/11 gi bill bah",
        "gi bill housing allowance",
        "gi bill mha 2026",
        "mha gi bill calculator",
        "bah from gi bill",
        "post 911 gi bill bah",
    ],
    sector="va_benefits",
))

# ---------------------------------------------------------------------------
# Batch 2 — 100% disabled veteran cluster
# ---------------------------------------------------------------------------

_FULL_PTAX_STATES = [
    "alabama", "arizona", "arkansas", "connecticut", "florida", "hawaii",
    "illinois", "iowa", "louisiana", "maryland", "michigan", "mississippi",
    "nebraska", "new-hampshire", "new-jersey", "new-mexico", "oklahoma",
    "pennsylvania", "south-carolina", "texas", "virginia", "wisconsin",
]


def _state_links_grid(slugs: list[str]) -> str:
    names = {s: s.replace("-", " ").title() for s in slugs}
    items = "".join(
        f'<li><a href="/state-benefits/{s}/">{names[s]}</a></li>' for s in slugs
    )
    return (
        '<ul style="columns:3;-webkit-columns:3;column-gap:1.5rem;margin:1rem 0;'
        'padding-left:1.1rem;font-size:0.92rem;">' + items + "</ul>"
    )


_BY_STATE_BODY = f"""
<p>A 100% VA disability rating opens the door to two layers of benefits: federal
benefits from the VA, and a second set of perks from your state. State benefits
are where the biggest surprises hide &mdash; full property tax exemptions, free
vehicle registration, free college for your kids, and more. This guide breaks
down 100% disabled veteran benefits by state for 2026.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Start Here</strong><a href="/state-benefits/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Browse Benefits by State &rarr;</a><a href="/explainers/100-percent-va-disability-benefits/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Federal 100% Benefits &rarr;</a></div>

<h2>Federal vs. State Benefits: What's the Difference?</h2>
<p>Your federal benefits are the same no matter where you live. A 100% rating
pays <strong>$3,938.58 a month</strong> in 2026 for a single veteran, plus free
VA health care and more. See our guide to
<a href="/explainers/100-percent-va-disability-benefits/">federal 100% disabled veteran benefits</a>
for the full list.</p>
<p>State benefits are different. Each state sets its own rules. Where you live
can be worth thousands of dollars a year. The three biggest state benefits are
property tax exemptions, income tax breaks, and education benefits for your
family.</p>

<h2>States With a Full Property Tax Exemption (2026)</h2>
<p>This is the single most valuable state benefit. In <strong>22 states</strong>,
a veteran rated 100% disabled (or paid at the 100% rate for individual
unemployability) pays <strong>no property tax</strong> on their primary home.
On a $350,000 home, that can save $4,000 to $9,000 every year.</p>
{_state_links_grid(_FULL_PTAX_STATES)}
<p style="font-size:0.85rem;color:var(--sr-gray-text);">Rules vary by county. Some states cap the acreage or home value, and some
require permanent and total (P&amp;T) status. Always confirm with your local tax
assessor. Click any state above for its full benefit details.</p>

<h2>Other Common State Benefits at 100%</h2>
<ul>
  <li><strong>Income tax:</strong> Many states fully exempt VA disability pay
  (it is already federally tax-free). Nine states have no income tax at all,
  including Texas, Florida, and Tennessee.</li>
  <li><strong>Vehicle registration:</strong> States like Texas, South Carolina,
  and Virginia waive registration fees or property tax on one or two vehicles.</li>
  <li><strong>Education:</strong> States such as Texas (Hazlewood Act), Illinois,
  and Florida offer free or reduced college tuition for disabled veterans or
  their children.</li>
  <li><strong>Hunting and fishing licenses:</strong> Most states offer free or
  discounted licenses to disabled veterans.</li>
  <li><strong>Recreation:</strong> Free state park access and special license
  plates are common.</li>
</ul>

<h2>How to Claim Your State Benefits</h2>
<ol>
  <li>Get your VA rating decision letter showing 100% (and P&amp;T if you have it).</li>
  <li>Find your state's veterans affairs office or county assessor.</li>
  <li>File the state application &mdash; property tax exemptions are not automatic.</li>
  <li>Re-apply or recertify if your state requires it each year.</li>
</ol>
<p>Pick your state from our <a href="/state-benefits/">state benefits directory</a>
to see exactly what you qualify for and how to apply.</p>
"""

PAGES.append(_page(
    "100-percent-disabled-veteran-benefits-by-state",
    title="100% Disabled Veteran Benefits by State (2026 Guide)",
    h1="100% Disabled Veteran Benefits by State: 2026 Guide",
    summary=(
        "100% disabled veteran benefits by state for 2026. See which 22 states "
        "give full property tax exemptions, plus income tax, vehicle, and "
        "education benefits — with links to all 50 states."
    ),
    body_html=_BY_STATE_BODY,
    faq=[
        {
            "question": "Which states have no property tax for 100% disabled veterans?",
            "answer": (
                "About 22 states offer a full property tax exemption on a 100% "
                "disabled veteran's primary home, including Texas, Florida, "
                "Illinois, Virginia, Pennsylvania, and South Carolina. Rules and "
                "caps vary by county, so confirm with your local tax assessor."
            ),
        },
        {
            "question": "Do 100% disabled veterans pay state income tax on VA benefits?",
            "answer": (
                "No. VA disability compensation is not taxed by the federal "
                "government or any state. Several states also exempt military "
                "retirement pay, and nine states have no income tax at all."
            ),
        },
        {
            "question": "What is the best state for 100% disabled veterans?",
            "answer": (
                "It depends on your priorities. Texas and Florida are popular for "
                "no income tax plus full property tax exemptions. The best choice "
                "weighs property tax, education benefits for your kids, and cost "
                "of living together."
            ),
        },
    ],
    takeaways=[
        "100% disabled veterans get federal benefits (same everywhere) plus state benefits (vary widely).",
        "22 states offer a full property tax exemption on a 100% disabled veteran's primary home.",
        "VA disability pay is never taxed by the federal government or any state.",
        "State benefits are not automatic — you must apply through your state or county.",
    ],
    keywords=[
        "100 disabled veteran benefits by state",
        "100 percent disabled veteran benefits by state",
        "disabled veteran property tax exemption by state",
        "best states for disabled veterans",
    ],
    sector="va_disability",
))

_100_BENEFITS_BODY = """
<p>A 100% VA disability rating is the highest schedular rating the VA awards. It
unlocks the largest monthly payment plus a wide range of health, education, and
family benefits. This guide lists the federal benefits for 100% disabled
veterans in 2026 &mdash; especially those rated 100% Permanent and Total (P&amp;T).</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Related</strong><a href="/explainers/100-percent-va-disability-pay/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">2026 Pay Amounts &rarr;</a><a href="/explainers/100-percent-disabled-veteran-benefits-by-state/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Benefits by State &rarr;</a><a href="/explainers/how-to-get-100-va-disability/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">How to Reach 100% &rarr;</a></div>

<h2>Monthly Compensation</h2>
<p>The biggest benefit is the tax-free monthly payment. In 2026, a single
veteran at 100% receives <strong>$3,938.58 a month</strong> &mdash; about
$47,000 a year, tax-free. Veterans with a spouse, children, or dependent parents
receive more. See the full breakdown in our
<a href="/explainers/100-percent-va-disability-pay/">100% VA disability pay guide</a>.</p>

<h2>Health Care Benefits</h2>
<ul>
  <li><strong>Priority Group 1:</strong> You get the highest priority for VA
  health care, with no copays for care or prescriptions.</li>
  <li><strong>Dental care:</strong> 100% disabled veterans qualify for full VA
  dental benefits, which most veterans do not receive.</li>
  <li><strong>CHAMPVA for family:</strong> If your rating is 100% P&amp;T, your
  spouse and children can get health coverage through CHAMPVA.</li>
  <li><strong>Travel pay:</strong> You can be reimbursed for travel to VA
  medical appointments.</li>
</ul>

<h2>Family and Education Benefits</h2>
<ul>
  <li><strong>Chapter 35 (DEA):</strong> If you are rated P&amp;T, your spouse
  and children can receive up to 36 months of education benefits &mdash; up to
  about <strong>$1,574 a month</strong> for full-time study.</li>
  <li><strong>Dependents added to your pay:</strong> A spouse, child, or
  dependent parent each add to your monthly check.</li>
  <li><strong>Survivor benefits (DIC):</strong> If you are rated P&amp;T for 10
  years, your survivors may qualify for Dependency and Indemnity Compensation.</li>
</ul>

<h2>Other Federal Benefits</h2>
<ul>
  <li><strong>Commissary and exchange access:</strong> Shop on base; families
  often save $2,000&ndash;$4,000 a year on groceries.</li>
  <li><strong>VA home loan:</strong> The funding fee is waived for disabled
  veterans. Read our <a href="/va-benefits/va-home-loan/">VA home loan guide</a>.</li>
  <li><strong>Specially Adapted Housing (SAH) grants:</strong> Money to modify a
  home for a service-connected disability.</li>
  <li><strong>Automobile and adaptive equipment grants:</strong> Help buying or
  modifying a vehicle.</li>
  <li><strong>VA life insurance (VALife):</strong> Guaranteed acceptance whole
  life coverage for service-connected veterans.</li>
</ul>

<h2>What "Permanent and Total" (P&amp;T) Adds</h2>
<p>A regular 100% rating and a 100% P&amp;T rating pay the same monthly amount.
But P&amp;T means the VA does not expect your condition to improve, so you avoid
future re-exams. P&amp;T is also the key that unlocks CHAMPVA and Chapter 35
benefits for your family. Learn more in our
<a href="/explainers/tdiu-explained/">TDIU explainer</a> and
<a href="/explainers/cdr-explained/">continuing review (CDR) guide</a>.</p>
"""

PAGES.append(_page(
    "100-percent-va-disability-benefits",
    title="100% VA Disability Benefits: Full 2026 List | Rank and Pay",
    h1="100% VA Disability Benefits: The Complete 2026 List",
    summary=(
        "Every benefit for 100% disabled veterans in 2026: $3,938.58/month, free "
        "VA health and dental care, CHAMPVA, Chapter 35 education, commissary "
        "access, and more."
    ),
    body_html=_100_BENEFITS_BODY,
    faq=[
        {
            "question": "What benefits do 100% disabled veterans get in 2026?",
            "answer": (
                "A 100% rating pays $3,938.58 a month (more with dependents), "
                "plus free VA health and dental care, travel pay, commissary and "
                "exchange access, and a waived VA home loan funding fee. P&T "
                "veterans also unlock CHAMPVA and Chapter 35 education for family."
            ),
        },
        {
            "question": "Is 100% VA disability the same as Permanent and Total?",
            "answer": (
                "Not always. Both pay the same monthly amount. 'Permanent and "
                "Total' (P&T) means the VA does not expect improvement, so you "
                "avoid re-exams and your family can use CHAMPVA and Chapter 35 "
                "education benefits."
            ),
        },
        {
            "question": "Do 100% disabled veterans get free health care for family?",
            "answer": (
                "Only if rated 100% Permanent and Total. In that case, spouses "
                "and children can enroll in CHAMPVA, the VA's cost-sharing health "
                "program. A standard 100% rating without P&T does not include this."
            ),
        },
    ],
    takeaways=[
        "100% pays $3,938.58/month in 2026 for a single veteran, tax-free.",
        "Benefits include free VA health and dental care, travel pay, and commissary access.",
        "Permanent and Total (P&T) status unlocks CHAMPVA and Chapter 35 for your family.",
        "The VA home loan funding fee is waived for disabled veterans.",
    ],
    keywords=[
        "100 percent va disability benefits",
        "benefits for 100 disabled veterans",
        "100 percent permanent and total benefits",
        "p&t va benefits",
    ],
    sector="va_disability",
))

_100_PAY_BODY = """
<p>Veterans rated 100% disabled receive the largest VA compensation payment. In
2026, the base rate rose 2.8% with the annual cost-of-living adjustment (COLA).
This guide shows the 2026 100% VA disability pay amounts by dependent status and
explains when you get paid.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Tools</strong><a href="/tools/va-disability-rating-calculator/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Rating Calculator &rarr;</a><a href="/tools/va-back-pay-calculator/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Back Pay Calculator &rarr;</a></div>

<h2>2026 100% VA Disability Pay by Dependent Status</h2>
<p>These rates are effective December 1, 2025. Payments are tax-free.</p>
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;font-size:0.92rem;margin:1rem 0;">
<thead><tr style="background:var(--sr-blue);color:#fff;"><th style="padding:0.6rem 0.75rem;text-align:left;">Dependent Status</th><th style="padding:0.6rem 0.75rem;text-align:right;">2026 Monthly Pay</th></tr></thead>
<tbody>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">Veteran alone (no dependents)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$3,938.58</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">With spouse (no children)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$4,158.17</td></tr>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">With spouse and 1 child</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$4,267.28</td></tr>
<tr style="background:var(--sr-gray-bg);"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">With 1 parent (no spouse or children)</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$4,114.82</td></tr>
<tr style="background:#fff;"><td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">With spouse and 2 parents</td><td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">$4,510.65</td></tr>
</tbody></table>
</div>
<p style="font-size:0.85rem;color:var(--sr-gray-text);">Each additional child under 18 adds $109.11 per month. Children in school past
18 and Aid and Attendance for a spouse add more. Special Monthly Compensation
(SMC) can raise the total well above these figures.</p>

<h2>Schedular 100% vs. TDIU: Same Pay</h2>
<p>There are two ways to get paid at the 100% rate. A <strong>schedular 100%</strong>
rating comes from your combined disability percentage. <strong>TDIU</strong>
(Total Disability based on Individual Unemployability) pays the 100% rate when
your conditions stop you from working, even if your combined rating is lower.
Both pay the exact same monthly amount. Read our
<a href="/explainers/tdiu-explained/">TDIU explainer</a> to compare them.</p>

<h2>When Do You Get Paid?</h2>
<p>VA pays monthly, on the first business day of the following month. The 2026
COLA increase first appeared in the payment deposited December 31, 2025. If a
payday lands on a weekend or holiday, the VA pays on the last business day
before it.</p>

<h2>Back Pay at 100%</h2>
<p>When the VA grants or increases your rating, you receive back pay to your
effective date. At the 100% rate, a year of back pay can exceed $47,000. Use our
<a href="/tools/va-back-pay-calculator/">VA back pay calculator</a> to estimate
your lump sum.</p>
"""

PAGES.append(_page(
    "100-percent-va-disability-pay",
    title="100% VA Disability Pay 2026: Monthly Amounts | Rank and Pay",
    h1="100% VA Disability Pay in 2026: Monthly Amounts by Dependent",
    summary=(
        "2026 100% VA disability pay: $3,938.58/month for a single veteran, more "
        "with dependents. See the full pay chart, the 2.8% COLA, payment dates, "
        "and back pay."
    ),
    body_html=_100_PAY_BODY,
    faq=[
        {
            "question": "How much is 100% VA disability pay in 2026?",
            "answer": (
                "A single veteran at 100% receives $3,938.58 per month in 2026, "
                "tax-free. With a spouse it rises to $4,158.17, and each "
                "additional child under 18 adds $109.11. Special Monthly "
                "Compensation can increase the total further."
            ),
        },
        {
            "question": "Does TDIU pay the same as 100%?",
            "answer": (
                "Yes. TDIU (unemployability) pays the same monthly amount as a "
                "schedular 100% rating — $3,938.58 for a single veteran in 2026. "
                "The difference is how you qualify, not how much you receive."
            ),
        },
        {
            "question": "When does the 2026 VA disability increase start?",
            "answer": (
                "The 2.8% COLA took effect December 1, 2025. The first increased "
                "payment was deposited December 31, 2025. VA pays on the first "
                "business day of each month for the prior month."
            ),
        },
    ],
    takeaways=[
        "2026 100% pay is $3,938.58/month for a single veteran (up 2.8% with COLA).",
        "With a spouse it is $4,158.17; each child under 18 adds $109.11.",
        "Schedular 100% and TDIU pay the exact same monthly amount.",
        "VA pays on the first business day of the following month; payments are tax-free.",
    ],
    keywords=[
        "100 percent va disability pay",
        "100 va disability pay 2026",
        "va 100 disability monthly amount",
        "tdiu pay 2026",
    ],
    sector="va_disability",
))

_HOW_TO_100_BODY = """
<p>Reaching a 100% VA disability rating is hard, but thousands of veterans do it
every year. There are three main paths: a schedular 100% rating, combining
ratings with VA math, or TDIU. This guide explains how to get 100% VA disability
in 2026 and the mistakes that hold veterans back.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Tools &amp; Guides</strong><a href="/tools/va-disability-rating-calculator/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Combined Rating Calculator &rarr;</a><a href="/va-claims/how-to-file-a-va-claim/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">How to File a Claim &rarr;</a></div>

<h2>Path 1: A Single 100% Condition</h2>
<p>Some conditions can be rated 100% on their own. Examples include certain
cancers during active treatment, severe heart conditions, and some mental health
conditions that cause total occupational and social impairment. If one condition
is severe enough, you may not need to combine ratings at all.</p>

<h2>Path 2: Combining Ratings With VA Math</h2>
<p>The VA does not add your ratings the simple way. It uses "VA math," which
combines ratings on a sliding scale. Two 50% ratings do not equal 100% &mdash;
they combine to 75%, which rounds to 80%. To reach 100% schedular, you usually
need several high ratings stacked together.</p>
<p>Use our <a href="/tools/va-disability-rating-calculator/">VA combined rating
calculator</a> to see your real number. Learn the rules in our
<a href="/explainers/va-disability-rating-explained/">VA rating explainer</a>.</p>

<h2>Path 3: TDIU (Unemployability)</h2>
<p>If your service-connected conditions stop you from holding a steady job, you
can be paid at the 100% rate through TDIU &mdash; even if your combined rating is
only 60% or 70%. This is one of the most overlooked paths to 100% pay. Read our
<a href="/explainers/tdiu-explained/">complete TDIU guide</a>.</p>

<h2>Tips to Increase Your Rating</h2>
<ol>
  <li><strong>Claim secondary conditions.</strong> One service-connected
  condition often causes others. For example, knee pain can lead to a back
  condition, and tinnitus often pairs with hearing loss.</li>
  <li><strong>Check PACT Act presumptives.</strong> The PACT Act added many
  presumptive conditions for burn pit and Agent Orange exposure. See our
  <a href="/explainers/pact-act-explained/">PACT Act guide</a>.</li>
  <li><strong>Get strong medical evidence.</strong> A current diagnosis, a nexus
  letter, and detailed exam results matter most.</li>
  <li><strong>File for an increase.</strong> If a rated condition has gotten
  worse, file for a higher rating with new evidence.</li>
  <li><strong>Don't quit too early.</strong> Appeal a low decision rather than
  starting over. See our <a href="/explainers/va-appeals-process/">appeals guide</a>.</li>
</ol>

<h2>Aim for Permanent and Total (P&amp;T)</h2>
<p>Once you reach 100%, ask whether the VA marked you Permanent and Total.
P&amp;T status ends future re-exams and unlocks CHAMPVA and Chapter 35 education
for your family. See the full list of
<a href="/explainers/100-percent-va-disability-benefits/">100% disabled veteran benefits</a>.</p>
"""

PAGES.append(_page(
    "how-to-get-100-va-disability",
    title="How to Get 100% VA Disability in 2026 | Rank and Pay",
    h1="How to Get 100% VA Disability: 3 Proven Paths for 2026",
    summary=(
        "How to get 100% VA disability in 2026. Learn the three paths — a single "
        "100% condition, combining ratings with VA math, and TDIU — plus tips to "
        "raise your rating."
    ),
    body_html=_HOW_TO_100_BODY,
    faq=[
        {
            "question": "What is the easiest way to get 100% VA disability?",
            "answer": (
                "There is no single easy path, but TDIU is often overlooked. If "
                "your service-connected conditions keep you from working, you can "
                "be paid at the 100% rate even with a combined rating of 60–70%. "
                "Claiming secondary conditions also helps many veterans."
            ),
        },
        {
            "question": "How does VA math work for combining ratings?",
            "answer": (
                "The VA combines ratings on a sliding scale, not by simple "
                "addition. Two 50% ratings combine to 75%, which rounds to 80%. "
                "Use a combined rating calculator to find your real number."
            ),
        },
        {
            "question": "Is TDIU the same as 100% disability?",
            "answer": (
                "TDIU pays the same monthly amount as a 100% schedular rating. "
                "The difference is qualification: TDIU is based on being unable "
                "to work, while schedular 100% is based on your combined rating."
            ),
        },
    ],
    takeaways=[
        "Three paths reach 100%: a single 100% condition, combined ratings, or TDIU.",
        "VA math is a sliding scale — two 50% ratings combine to 80%, not 100%.",
        "TDIU pays the 100% rate when conditions keep you from working, even at 60–70% combined.",
        "Claim secondary and PACT Act presumptive conditions to raise your rating.",
    ],
    keywords=[
        "how to get 100 va disability",
        "how to get 100 percent va disability",
        "tdiu",
        "increase va disability rating",
    ],
    sector="va_disability",
))


# ---------------------------------------------------------------------------
# Batch 3 — 2026 VA disability rates, pay chart, pay dates, COLA
# ---------------------------------------------------------------------------

_RATES_2026 = [
    ("10%", "$180.42", "N/A"),
    ("20%", "$356.66", "N/A"),
    ("30%", "$552.47", "$617.47"),
    ("40%", "$795.84", "$882.84"),
    ("50%", "$1,132.90", "$1,241.90"),
    ("60%", "$1,435.02", "$1,566.02"),
    ("70%", "$1,808.45", "$1,961.45"),
    ("80%", "$2,102.15", "$2,277.15"),
    ("90%", "$2,362.30", "$2,559.30"),
    ("100%", "$3,938.58", "$4,158.17"),
]


def _rate_chart() -> str:
    rows = ""
    for i, (rating, alone, spouse) in enumerate(_RATES_2026):
        bg = "#fff" if i % 2 == 0 else "var(--sr-gray-bg)"
        rows += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);font-weight:600;">{rating}</td>'
            f'<td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">{alone}</td>'
            f'<td style="padding:0.5rem 0.75rem;text-align:right;border-bottom:1px solid var(--sr-gray-light);">{spouse}</td>'
            "</tr>"
        )
    return (
        '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.92rem;margin:1rem 0;">'
        '<thead><tr style="background:var(--sr-blue);color:#fff;">'
        '<th style="padding:0.6rem 0.75rem;text-align:left;">Rating</th>'
        '<th style="padding:0.6rem 0.75rem;text-align:right;">Veteran Alone</th>'
        '<th style="padding:0.6rem 0.75rem;text-align:right;">With Spouse (no children)</th>'
        "</tr></thead><tbody>" + rows + "</tbody></table></div>"
    )


_PAY_DATES_2026 = [
    ("December 2025", "Wednesday, December 31, 2025"),
    ("January 2026", "Friday, January 30, 2026"),
    ("February 2026", "Friday, February 27, 2026"),
    ("March 2026", "Wednesday, April 1, 2026"),
    ("April 2026", "Friday, May 1, 2026"),
    ("May 2026", "Monday, June 1, 2026"),
    ("June 2026", "Wednesday, July 1, 2026"),
    ("July 2026", "Friday, July 31, 2026"),
    ("August 2026", "Tuesday, September 1, 2026"),
    ("September 2026", "Thursday, October 1, 2026"),
    ("October 2026", "Friday, October 30, 2026"),
    ("November 2026", "Tuesday, December 1, 2026"),
    ("December 2026", "Thursday, December 31, 2026"),
]


def _pay_date_table() -> str:
    rows = ""
    for i, (month, date) in enumerate(_PAY_DATES_2026):
        bg = "#fff" if i % 2 == 0 else "var(--sr-gray-bg)"
        rows += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">{month}</td>'
            f'<td style="padding:0.5rem 0.75rem;border-bottom:1px solid var(--sr-gray-light);">{date}</td>'
            "</tr>"
        )
    return (
        '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.92rem;margin:1rem 0;">'
        '<thead><tr style="background:var(--sr-blue);color:#fff;">'
        '<th style="padding:0.6rem 0.75rem;text-align:left;">Benefit Month</th>'
        '<th style="padding:0.6rem 0.75rem;text-align:left;">Payment Date</th>'
        "</tr></thead><tbody>" + rows + "</tbody></table></div>"
    )


_RATES_BODY = f"""
<p>The 2026 VA disability rates rose 2.8% on December 1, 2025, thanks to the
annual cost-of-living adjustment (COLA). This page shows the full 2026 VA
disability pay chart by rating and dependent status. All payments are tax-free.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Tools</strong><a href="/tools/va-disability-rating-calculator/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Combined Rating Calculator &rarr;</a><a href="/explainers/va-disability-pay-dates-2026/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">2026 Pay Dates &rarr;</a><a href="/explainers/va-cola-2026/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">2026 COLA &rarr;</a></div>

<h2>2026 VA Disability Pay Chart</h2>
<p>These monthly rates are effective December 1, 2025. The "veteran alone" column
is for a veteran with no dependents. Veterans rated 30% or higher get extra pay
for a spouse, children, and dependent parents.</p>
{_rate_chart()}
<p style="font-size:0.85rem;color:var(--sr-gray-text);">Ratings of 10% and 20% do not include extra pay for dependents. At 100%, each
additional child under 18 adds $109.11 per month. Use our
<a href="/tools/va-disability-rating-calculator/">VA rating calculator</a> to
find your combined rating and estimated pay.</p>

<h2>How VA Disability Pay Is Calculated</h2>
<p>Your monthly payment depends on two things: your combined disability rating
and your dependents. The VA combines multiple ratings with "VA math," a sliding
scale &mdash; not simple addition. Learn the rules in our
<a href="/explainers/va-disability-rating-explained/">VA rating explainer</a>.</p>

<h2>Extra Pay for Dependents</h2>
<p>If your rating is 30% or higher, you can add dependents to your claim for more
money each month. This includes a spouse, children under 18 (or under 23 if in
school), and dependent parents. Aid and Attendance for a spouse who needs care
adds even more.</p>

<h2>2025 vs. 2026 Rates</h2>
<p>The 2.8% COLA raised every rate. For example, a single veteran at 100% went
from $3,831.30 in 2025 to <strong>$3,938.58</strong> in 2026 &mdash; about $107
more per month. See the details in our
<a href="/explainers/va-cola-2026/">2026 VA COLA guide</a>.</p>
"""

PAGES.append(_page(
    "va-disability-rates-2026",
    title="2026 VA Disability Rates: Full Pay Chart | Rank and Pay",
    h1="2026 VA Disability Rates & Pay Chart (2.8% COLA)",
    summary=(
        "2026 VA disability pay chart with all ratings and dependent amounts. "
        "Rates rose 2.8% on December 1, 2025 — 100% now pays $3,938.58/month for "
        "a single veteran, tax-free."
    ),
    body_html=_RATES_BODY,
    faq=[
        {
            "question": "How much did VA disability go up in 2026?",
            "answer": (
                "VA disability rates rose 2.8% in 2026 from the cost-of-living "
                "adjustment, effective December 1, 2025. A single veteran at 100% "
                "went from $3,831.30 to $3,938.58 per month."
            ),
        },
        {
            "question": "What is the 2026 VA disability rate for 100%?",
            "answer": (
                "In 2026, a single veteran at 100% receives $3,938.58 per month. "
                "With a spouse it is $4,158.17, and each additional child under "
                "18 adds $109.11. All VA disability pay is tax-free."
            ),
        },
        {
            "question": "Do you get extra VA pay for dependents?",
            "answer": (
                "Yes, if your rating is 30% or higher. You can add a spouse, "
                "children, and dependent parents for more monthly pay. Ratings of "
                "10% and 20% do not include dependent pay."
            ),
        },
    ],
    takeaways=[
        "2026 VA disability rates rose 2.8% (COLA), effective December 1, 2025.",
        "100% pays $3,938.58/month for a single veteran; $4,158.17 with a spouse.",
        "Dependent pay is added only at ratings of 30% or higher.",
        "All VA disability compensation is tax-free.",
    ],
    keywords=[
        "2026 va disability rates",
        "va disability pay chart 2026",
        "va disability rates 2026",
        "va compensation rates 2026",
    ],
    sector="va_disability",
))

_PAY_DATES_BODY = f"""
<p>The VA pays disability compensation once a month for the previous month's
benefits. Knowing your 2026 VA disability pay dates helps you plan your budget.
This page lists every payment date for 2026.</p>

<h2>2026 VA Disability Payment Dates</h2>
<p>The VA pays on the first business day of the month. When the first falls on a
weekend or federal holiday, the payment moves to the last business day before
it. That is why some payments arrive at the end of the prior month.</p>
{_pay_date_table()}
<p style="font-size:0.85rem;color:var(--sr-gray-text);">Direct deposit usually posts on the payment date. Some banks make funds
available a day or two early.</p>

<h2>Why the December Payment Comes Early</h2>
<p>Your December 2025 benefits were paid <strong>December 31, 2025</strong>,
because January 1 is a federal holiday. The same happens in December 2026. This
is the payment that includes the new 2.8% COLA increase. Read our
<a href="/explainers/va-cola-2026/">2026 VA COLA guide</a> for details.</p>

<h2>What If My Payment Is Late?</h2>
<ol>
  <li>Wait 3 business days &mdash; banks post on different schedules.</li>
  <li>Check your direct deposit details on VA.gov.</li>
  <li>Call the VA at 800-827-1000 if the payment still has not arrived.</li>
</ol>
<p>To see how much you should receive, view the full
<a href="/explainers/va-disability-rates-2026/">2026 VA disability pay chart</a>.</p>
"""

PAGES.append(_page(
    "va-disability-pay-dates-2026",
    title="2026 VA Disability Pay Dates: Full Schedule | Rank and Pay",
    h1="2026 VA Disability Pay Dates: The Complete Schedule",
    summary=(
        "Every 2026 VA disability payment date. The VA pays on the first business "
        "day of the month — see the full schedule and why the December payment "
        "arrives early."
    ),
    body_html=_PAY_DATES_BODY,
    faq=[
        {
            "question": "What day does VA disability pay in 2026?",
            "answer": (
                "The VA pays on the first business day of each month for the "
                "prior month's benefits. If the first is a weekend or holiday, "
                "payment moves to the last business day before it. For example, "
                "January 2026 benefits were paid January 30, 2026."
            ),
        },
        {
            "question": "Why did I get paid on December 31?",
            "answer": (
                "Because January 1 is a federal holiday, the December benefit "
                "payment moves up to December 31. This payment also included the "
                "new 2.8% COLA increase for 2026."
            ),
        },
        {
            "question": "Does VA disability pay come early?",
            "answer": (
                "It can. When the first of the month is a weekend or holiday, the "
                "VA pays on the last business day before it. Some banks also post "
                "direct deposits a day or two early."
            ),
        },
    ],
    takeaways=[
        "The VA pays disability on the first business day of each month.",
        "If the 1st is a weekend or holiday, payment moves earlier, not later.",
        "December 2025 benefits paid December 31, 2025 — including the 2.8% COLA.",
        "Allow 3 business days before reporting a missing payment.",
    ],
    keywords=[
        "va disability pay dates 2026",
        "va payment dates 2026",
        "va disability deposit dates 2026",
        "when does va disability pay",
    ],
    sector="va_disability",
))

_COLA_BODY = """
<p>Every year, VA benefits rise with the cost-of-living adjustment (COLA). The
2026 VA COLA is <strong>2.8%</strong>, effective December 1, 2025. This guide
explains what the 2026 COLA means for your VA disability pay and when you saw the
increase.</p>

<h2>What Is the 2026 VA COLA?</h2>
<p>The COLA is a yearly raise that keeps benefits in line with inflation. It is
based on the Consumer Price Index (CPI-W). VA disability compensation, VA
pension, and DIC all rise by the same percentage as Social Security. For 2026,
that increase is 2.8%.</p>

<h2>How the COLA Affects Your Pay</h2>
<p>The 2.8% raise applies to your base rate and your dependent pay. Here are a
few examples of the 2026 increase:</p>
<ul>
  <li><strong>100% single veteran:</strong> $3,831.30 &rarr; <strong>$3,938.58</strong> (about $107 more per month).</li>
  <li><strong>70% single veteran:</strong> $1,759.19 &rarr; <strong>$1,808.45</strong>.</li>
  <li><strong>50% single veteran:</strong> $1,102.04 &rarr; <strong>$1,132.90</strong>.</li>
</ul>
<p>See the full numbers in our
<a href="/explainers/va-disability-rates-2026/">2026 VA disability pay chart</a>.</p>

<h2>When Did the 2026 COLA Start?</h2>
<p>The increase took effect December 1, 2025. Because VA pays a month behind, the
first payment with the higher amount arrived <strong>December 31, 2025</strong>.
See all <a href="/explainers/va-disability-pay-dates-2026/">2026 VA pay dates</a>.</p>

<h2>Who Gets the COLA?</h2>
<p>The COLA is automatic. You do not need to apply. It covers veterans receiving
disability compensation, survivors receiving DIC, and veterans receiving VA
pension. Social Security recipients get the same 2.8% raise.</p>
"""

PAGES.append(_page(
    "va-cola-2026",
    title="2026 VA COLA: 2.8% Increase Explained | Rank and Pay",
    h1="2026 VA COLA: The 2.8% Increase Explained",
    summary=(
        "The 2026 VA COLA is 2.8%, effective December 1, 2025. See how the "
        "cost-of-living increase raises your VA disability pay and when the first "
        "higher payment arrived."
    ),
    body_html=_COLA_BODY,
    faq=[
        {
            "question": "What is the 2026 VA COLA increase?",
            "answer": (
                "The 2026 COLA is 2.8%, effective December 1, 2025. It raises VA "
                "disability compensation, DIC, and VA pension by 2.8%, the same "
                "increase Social Security recipients receive."
            ),
        },
        {
            "question": "When did the 2026 VA COLA take effect?",
            "answer": (
                "The increase took effect December 1, 2025. Because the VA pays a "
                "month behind, the first higher payment was deposited December 31, "
                "2025."
            ),
        },
        {
            "question": "Do I need to apply for the COLA?",
            "answer": (
                "No. The COLA is automatic for everyone receiving VA disability "
                "compensation, DIC, or pension. There is nothing to file."
            ),
        },
    ],
    takeaways=[
        "The 2026 VA COLA is 2.8%, effective December 1, 2025.",
        "It raises disability compensation, DIC, and pension automatically.",
        "A 100% single veteran's pay rose about $107/month to $3,938.58.",
        "The first higher payment arrived December 31, 2025.",
    ],
    keywords=[
        "va cola 2026",
        "2026 va cola increase",
        "va disability cola 2026",
        "cost of living adjustment va",
    ],
    sector="va_disability",
))


# ---------------------------------------------------------------------------
# Batch 4 — PACT Act presumptive conditions
# ---------------------------------------------------------------------------

_PACT_BODY = """
<p>The PACT Act is the largest expansion of veteran benefits in decades. It adds
dozens of presumptive conditions tied to burn pits, Agent Orange, and other toxic
exposures. If you have a presumptive condition, you do not have to prove it was
caused by your service. This guide lists the PACT Act presumptive conditions for
2026 and how to file.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Related</strong><a href="/explainers/pact-act-explained/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">PACT Act Explained &rarr;</a><a href="/explainers/presumptive-conditions/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">What Are Presumptive Conditions? &rarr;</a><a href="/va-claims/how-to-file-a-va-claim/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">How to File &rarr;</a></div>

<h2>What Is a Presumptive Condition?</h2>
<p>Normally, you must prove your condition is linked to your service. With a
presumptive condition, the VA already accepts the link. You just need a current
diagnosis and proof you served in a qualifying time and place. This makes claims
faster and easier to win.</p>

<h2>Burn Pit Presumptive Cancers</h2>
<p>The PACT Act made these cancers presumptive for veterans exposed to burn pits
and airborne hazards (Gulf War and post-9/11 service):</p>
<ul>
  <li>Brain cancer</li>
  <li>Glioblastoma</li>
  <li>Gastrointestinal cancer of any type</li>
  <li>Head cancer of any type</li>
  <li>Kidney cancer</li>
  <li>Lymphatic cancer of any type</li>
  <li>Lymphoma of any type</li>
  <li>Melanoma</li>
  <li>Neck cancer of any type</li>
  <li>Pancreatic cancer</li>
  <li>Reproductive cancer of any type</li>
  <li>Respiratory (breathing-related) cancer of any type</li>
</ul>

<h2>Burn Pit Presumptive Illnesses (Non-Cancer)</h2>
<ul>
  <li>Asthma (diagnosed after service)</li>
  <li>Chronic bronchitis</li>
  <li>Chronic obstructive pulmonary disease (COPD)</li>
  <li>Chronic rhinitis</li>
  <li>Chronic sinusitis</li>
  <li>Constrictive or obliterative bronchiolitis</li>
  <li>Emphysema</li>
  <li>Granulomatous disease</li>
  <li>Interstitial lung disease (ILD)</li>
  <li>Pleuritis</li>
  <li>Pulmonary fibrosis</li>
  <li>Sarcoidosis</li>
</ul>

<h2>New Agent Orange Presumptive Conditions</h2>
<p>The PACT Act added two conditions for veterans exposed to Agent Orange:</p>
<ul>
  <li><strong>High blood pressure (hypertension)</strong> &mdash; see our
  <a href="/va-disability/hypertension/">hypertension VA rating guide</a>.</li>
  <li>Monoclonal gammopathy of undetermined significance (MGUS)</li>
</ul>
<p>It also expanded the list of locations presumed exposed to Agent Orange,
including Thailand, Laos, Cambodia, Guam, American Samoa, and Johnston Atoll.</p>

<h2>How to File a PACT Act Claim</h2>
<ol>
  <li>Confirm your condition is on the presumptive list above.</li>
  <li>Gather your diagnosis and service records showing where you served.</li>
  <li>File a disability claim on VA.gov or with a VSO.</li>
  <li>Attend any VA exam (C&amp;P exam) the VA schedules.</li>
</ol>
<p>There is no deadline to file under the PACT Act, but filing sooner can set an
earlier effective date for back pay. Learn the basics in our
<a href="/explainers/pact-act-explained/">PACT Act explainer</a>.</p>
"""

PAGES.append(_page(
    "pact-act-presumptive-conditions",
    title="PACT Act Presumptive Conditions List (2026) | Rank and Pay",
    h1="PACT Act Presumptive Conditions: The Full 2026 List",
    summary=(
        "The full PACT Act presumptive conditions list for 2026 — burn pit "
        "cancers and lung illnesses, plus new Agent Orange conditions. See if you "
        "qualify and how to file."
    ),
    body_html=_PACT_BODY,
    faq=[
        {
            "question": "What conditions are presumptive under the PACT Act?",
            "answer": (
                "The PACT Act makes many burn pit cancers and lung illnesses "
                "presumptive, including brain, kidney, and pancreatic cancers, "
                "asthma, COPD, and pulmonary fibrosis. It also added high blood "
                "pressure and MGUS for Agent Orange exposure."
            ),
        },
        {
            "question": "Do I have to prove my PACT Act condition is service-related?",
            "answer": (
                "No. For a presumptive condition, the VA already accepts the link "
                "to your service. You only need a current diagnosis and proof you "
                "served in a qualifying time and location."
            ),
        },
        {
            "question": "Is there a deadline to file a PACT Act claim?",
            "answer": (
                "There is no hard deadline, but filing sooner can give you an "
                "earlier effective date and more back pay. You can file anytime "
                "on VA.gov or with an accredited VSO."
            ),
        },
    ],
    takeaways=[
        "The PACT Act made many burn pit cancers and lung illnesses presumptive.",
        "Presumptive means you don't have to prove the link to your service.",
        "High blood pressure and MGUS are new Agent Orange presumptive conditions.",
        "There's no deadline, but filing sooner can mean more back pay.",
    ],
    keywords=[
        "pact act presumptive conditions",
        "pact act conditions list",
        "burn pit presumptive conditions",
        "pact act presumptive conditions list 2026",
    ],
    sector="va_disability",
))

_PRESUMPTIVE_BODY = """
<p>A presumptive condition is one the VA automatically connects to your military
service. You do not have to prove how your service caused it. This single rule
makes thousands of VA claims easier to win every year. This guide explains how
presumptive conditions work and the main exposure groups for 2026.</p>

<div style="background:var(--sr-gray-bg);border:1px solid var(--sr-gray-light);border-left:4px solid var(--sr-blue);border-radius:var(--radius);padding:1.25rem 1.5rem;margin:1.75rem 0;"><strong style="display:block;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--sr-blue);margin-bottom:0.75rem;">Related</strong><a href="/explainers/pact-act-presumptive-conditions/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">PACT Act Conditions List &rarr;</a><a href="/explainers/what-is-a-nexus-letter/" style="display:inline-block;margin:0.3rem 0.5rem 0.3rem 0;padding:0.35rem 0.85rem;background:var(--sr-blue);color:#fff;border-radius:var(--radius);font-size:0.85rem;font-weight:600;text-decoration:none;">Nexus Letters &rarr;</a></div>

<h2>How Presumptive Conditions Work</h2>
<p>A normal VA claim needs three things: a current diagnosis, an in-service event,
and a medical "nexus" linking the two. A presumptive condition skips the hardest
part &mdash; the nexus. The VA presumes the link based on where and when you
served. You still need a current diagnosis and proof of qualifying service.</p>

<h2>The Main Presumptive Exposure Groups</h2>
<ul>
  <li><strong>Burn pits and airborne hazards (PACT Act):</strong> Covers Gulf War
  and post-9/11 veterans. See the full
  <a href="/explainers/pact-act-presumptive-conditions/">PACT Act conditions list</a>.</li>
  <li><strong>Agent Orange:</strong> For Vietnam-era and other veterans exposed to
  herbicides. Conditions include type 2 diabetes, ischemic heart disease,
  Parkinson's disease, several cancers, and now high blood pressure.</li>
  <li><strong>Gulf War illness:</strong> Unexplained chronic symptoms like
  fatigue, joint pain, and digestive problems in Gulf War veterans.</li>
  <li><strong>Radiation exposure:</strong> Certain cancers in "atomic veterans"
  and others exposed to ionizing radiation.</li>
  <li><strong>Camp Lejeune water:</strong> Veterans and families exposed to
  contaminated water at Camp Lejeune from 1953 to 1987.</li>
</ul>

<h2>Why Presumptive Status Matters</h2>
<p>Presumptive claims are faster and have higher approval rates. They remove the
need for a costly nexus letter and reduce the medical evidence you must gather.
If your condition is not presumptive, you can still win with a strong
<a href="/explainers/what-is-a-nexus-letter/">nexus letter</a> and medical
evidence.</p>

<h2>How to File a Presumptive Claim</h2>
<ol>
  <li>Check whether your condition is on a presumptive list.</li>
  <li>Get a current diagnosis from a doctor.</li>
  <li>Show proof of qualifying service (dates and locations).</li>
  <li>File on VA.gov or with an accredited VSO, then attend any VA exam.</li>
</ol>
<p>Want to estimate your rating once service-connected? Try our
<a href="/tools/va-disability-rating-calculator/">VA rating calculator</a>.</p>
"""

PAGES.append(_page(
    "presumptive-conditions",
    title="VA Presumptive Conditions: 2026 Guide | Rank and Pay",
    h1="VA Presumptive Conditions: How They Work in 2026",
    summary=(
        "What VA presumptive conditions are and how they make claims easier in "
        "2026. Learn the main exposure groups — burn pits, Agent Orange, Gulf "
        "War, radiation, and Camp Lejeune."
    ),
    body_html=_PRESUMPTIVE_BODY,
    faq=[
        {
            "question": "What does presumptive condition mean for VA claims?",
            "answer": (
                "It means the VA automatically accepts that your condition is "
                "linked to your service. You skip the hardest part of a claim — "
                "the medical nexus — and only need a current diagnosis and proof "
                "of qualifying service."
            ),
        },
        {
            "question": "What are the main VA presumptive exposure groups?",
            "answer": (
                "The major groups are burn pits and airborne hazards (PACT Act), "
                "Agent Orange, Gulf War illness, radiation exposure, and "
                "contaminated water at Camp Lejeune."
            ),
        },
        {
            "question": "What if my condition is not presumptive?",
            "answer": (
                "You can still win your claim. You'll need to prove the link to "
                "service with medical evidence and usually a nexus letter from a "
                "doctor connecting your condition to an in-service event."
            ),
        },
    ],
    takeaways=[
        "A presumptive condition is one the VA automatically links to your service.",
        "It removes the need for a nexus letter, making claims faster to win.",
        "Major groups: burn pits (PACT Act), Agent Orange, Gulf War, radiation, Camp Lejeune.",
        "You still need a current diagnosis and proof of qualifying service.",
    ],
    keywords=[
        "presumptive conditions",
        "va presumptive conditions",
        "presumptive conditions va disability",
        "what is a presumptive condition",
    ],
    sector="va_disability",
))


def run(dry: bool = False) -> None:
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for data in PAGES:
            row = (
                db.query(LandingPage)
                .filter(LandingPage.page_key == data["page_key"])
                .first()
            )
            if row is None:
                row = LandingPage(page_key=data["page_key"])
                db.add(row)
                created += 1
                action = "CREATE"
            else:
                updated += 1
                action = "UPDATE"
            row.page_type = data["page_type"]
            row.sector_slug = data["sector_slug"]
            row.canonical_path = data["canonical_path"]
            row.title = data["title"]
            row.subtitle = data["subtitle"]
            row.summary = data["summary"]
            row.body_html = data["body_html"]
            row.faq_json = data["faq_json"]
            row.sections_json = data["sections_json"]
            row.keywords_json = data["keywords_json"]
            row.last_generated_at = datetime.utcnow()
            print(f"  {action}  {data['canonical_path']}  ({len(data['body_html'])} chars body)")
        if dry:
            db.rollback()
            print(f"\nDRY RUN — rolled back. Would create {created}, update {updated}.")
        else:
            db.commit()
            print(f"\nDone. Created {created}, updated {updated}.")
    finally:
        db.close()


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)
