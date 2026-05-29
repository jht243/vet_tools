"""Create / upsert SEO content pages for Priorities 4-12 from the keyword inventory.

This script builds the remaining 31 LandingPage rows identified in
target-keyword-inventory.md. URL routing was added to server.py (top-level routes,
VA_FORMS set, GI_BILL_SPOKES set, MILITARY_PAY_SPOKES additions, EXPLAINER_SLUGS
additions).

Run:
    .venv/bin/python -m scripts.create_content_pages_batch2          # apply
    .venv/bin/python -m scripts.create_content_pages_batch2 --dry    # preview

Idempotent — re-running overwrites title/subtitle/summary/body_html/faq for each
page_key, leaving other rows untouched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from src.models import LandingPage
from server import SessionLocal


def _page(
    *,
    page_key: str,
    canonical_path: str,
    title: str,
    h1: str,
    summary: str,
    body_html: str,
    faq: list[dict],
    takeaways: list[str],
    keywords: list[str],
    page_type: str = "explainer",
    sector: str | None = None,
) -> dict:
    return {
        "page_key": page_key,
        "page_type": page_type,
        "sector_slug": sector,
        "canonical_path": canonical_path,
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
# Priority 6 — VA Forms cluster (5 pages)
# ---------------------------------------------------------------------------

_FORM_526EZ_BODY = """
<p><strong>VA Form 21-526EZ</strong> is the official application veterans use to
file for VA disability compensation. It is the most important form in the VA
claims process — and the one most veterans use to start a disability claim in
2026.</p>

<h2>What is VA Form 21-526EZ?</h2>
<p>VA Form 21-526EZ is the &ldquo;Application for Disability Compensation and
Related Compensation Benefits.&rdquo; You use it to file an original claim, add
a new condition, or file a claim for secondary service connection. The
&ldquo;EZ&rdquo; version replaced the older Form 21-526 and is built to support
the <strong>Fully Developed Claim (FDC)</strong> program for faster decisions.</p>

<h2>How to file VA Form 21-526EZ in 2026</h2>
<p>The VA prefers digital submissions. Most veterans file online because it is
faster and easier to track. Here are the four options, ranked by VA preference.</p>
<ol>
  <li><strong>Online at VA.gov</strong> &mdash; the recommended path. The system
  prefills your info, saves your progress, lets you upload evidence, and supports
  the Fully Developed Claim program.</li>
  <li><strong>By mail</strong> &mdash; send the completed form to: Department of
  Veterans Affairs, Claims Intake Center, PO Box 4444, Janesville, WI 53547-4444.</li>
  <li><strong>In person</strong> at a VA Regional Office.</li>
  <li><strong>With help</strong> from an accredited Veterans Service Officer
  (VSO), VA-accredited attorney, or claims agent.</li>
</ol>

<h2>What documents to include with VA Form 21-526EZ</h2>
<p>Strong evidence speeds up your claim. Submit as much as you can with the
initial filing.</p>
<ul>
  <li><strong>DD-214</strong> (or service treatment records if still on active
  duty).</li>
  <li><strong>Service treatment records</strong> showing in-service injury,
  illness, or event.</li>
  <li><strong>Current medical records</strong> showing your present diagnosis
  (private doctor or VA care).</li>
  <li><strong>Nexus evidence</strong> &mdash; usually a
  <a href="/explainers/what-is-a-nexus-letter/">nexus letter</a> from a doctor
  linking your condition to service.</li>
  <li><strong>Buddy or lay statements</strong> on
  <a href="/va-forms/21-4138/">VA Form 21-4138</a>.</li>
</ul>

<h2>Tips for completing VA Form 21-526EZ</h2>
<ul>
  <li><strong>Use the FDC program.</strong> Upload all evidence upfront and check
  the FDC box to cut weeks off the decision time.</li>
  <li><strong>List every condition you want rated.</strong> Conditions not listed
  will not be decided.</li>
  <li><strong>Mark each claim type clearly</strong> &mdash; original, secondary,
  or claim for increase.</li>
  <li><strong>Add an
  <a href="/va-intent-to-file/">Intent to File</a> first</strong> if you need
  more time to gather evidence. It locks your effective date for 12 months.</li>
  <li><strong>Sign and date the form.</strong> Unsigned forms are returned.</li>
</ul>

<h2>VA Form 21-526EZ processing time</h2>
<p>The average VA disability claim decision took <strong>about 76 days</strong>
in early 2026, according to VA Benefits data. Fully Developed Claims often clear
in 100&ndash;140 days. Claims with missing evidence can take 150 days or more.</p>

<h2>Related VA forms and guides</h2>
<ul>
  <li><a href="/va-forms/21-4138/">VA Form 21-4138 &mdash; Statement in Support of Claim</a></li>
  <li><a href="/va-forms/21-0781/">VA Form 21-0781 &mdash; PTSD Stressor Statement</a></li>
  <li><a href="/va-forms/21-8940/">VA Form 21-8940 &mdash; TDIU Application</a></li>
  <li><a href="/va-intent-to-file/">VA Intent to File &mdash; lock your effective date</a></li>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA disability claim</a></li>
</ul>

<p>You can download the latest VA Form 21-526EZ directly from
<a href="https://www.va.gov/find-forms/about-form-21-526ez/" target="_blank" rel="noopener noreferrer">VA.gov</a>
or file your claim online at the
<a href="https://www.va.gov/disability/file-disability-claim-form-21-526ez/" target="_blank" rel="noopener noreferrer">VA disability application portal</a>.</p>
"""

# /va-forms/ hub — index of common VA disability forms
_VA_FORMS_HUB_BODY = """
<p>The VA uses dozens of forms in the disability claims process. This 2026 hub
covers the most important forms veterans need to know, with detailed guides to
each. Bookmark this page as your starting point.</p>

<h2>Most important VA disability forms</h2>
<ul>
  <li><a href="/va-forms/21-526ez/"><strong>VA Form 21-526EZ</strong></a>
  &mdash; the main application for VA disability compensation.</li>
  <li><a href="/va-forms/21-4138/"><strong>VA Form 21-4138</strong></a>
  &mdash; Statement in Support of Claim. Use for buddy statements, lay
  statements, and clarifications.</li>
  <li><a href="/va-forms/21-0781/"><strong>VA Form 21-0781</strong></a>
  &mdash; PTSD stressor statement. Now also covers MST and personal assault.</li>
  <li><a href="/va-forms/21-8940/"><strong>VA Form 21-8940</strong></a>
  &mdash; TDIU application for unemployability.</li>
  <li><strong>VA Form 21-0966</strong> &mdash; Intent to File. See the
  <a href="/va-intent-to-file/">Intent to File guide</a>.</li>
</ul>

<h2>How VA forms work together</h2>
<p>Most disability claims start with VA Form 21-526EZ. Supporting forms add
evidence: 21-4138 for buddy statements, 21-0781 for PTSD stressors, 21-8940
for unemployability. File online at VA.gov whenever possible &mdash; the
system prefills your information and supports the Fully Developed Claim
program.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA claim</a></li>
  <li><a href="/va-claims/buddy-statement-guide/">Buddy statement guide</a></li>
  <li><a href="/explainers/tdiu-explained/">TDIU eligibility</a></li>
  <li><a href="/va-intent-to-file/">VA Intent to File</a></li>
</ul>

<p>Download the latest VA forms at
<a href="https://www.va.gov/find-forms/" target="_blank" rel="noopener noreferrer">VA.gov forms</a>.</p>
"""

PAGES.append(_page(
    page_key="hub:va-forms",
    canonical_path="/va-forms/",
    title="VA Disability Forms 2026: Complete Guide to Every Form",
    h1="VA Disability Forms: The 2026 Guide to Every Form You Need",
    summary=(
        "Every VA disability form you may need in 2026. Plain-English guides "
        "to VA Form 21-526EZ, 21-4138, 21-0781, 21-8940, and Intent to File."
    ),
    body_html=_VA_FORMS_HUB_BODY,
    faq=[
        {"question": "What is the main VA disability form?",
         "answer": "VA Form 21-526EZ is the primary application for VA disability compensation. Most claims start here. The 'EZ' version replaced the older Form 21-526 and supports the Fully Developed Claim program."},
        {"question": "How many VA disability forms do I need?",
         "answer": "Most claims need 21-526EZ and supporting evidence. Specific situations add 21-4138 (buddy statements), 21-0781 (PTSD), 21-8940 (TDIU), or 21-0966 (Intent to File)."},
        {"question": "Where can I download VA forms?",
         "answer": "All current VA forms are available at va.gov/find-forms. You can also file most disability forms directly online through VA.gov instead of downloading."},
        {"question": "Do I need to mail VA forms?",
         "answer": "Not anymore. The VA prefers online submissions at VA.gov. If you need to mail, send forms to the VA Claims Intake Center, PO Box 4444, Janesville, WI 53547-4444."},
    ],
    takeaways=[
        "VA Form 21-526EZ is the main disability compensation application.",
        "Supporting forms include 21-4138, 21-0781, 21-8940, and 21-0966.",
        "File online at VA.gov for the fastest processing.",
        "Paper mail goes to the VA Claims Intake Center in Janesville, WI.",
    ],
    keywords=[
        "va disability forms", "va forms", "va claim forms",
        "va disability compensation forms", "va forms list",
    ],
    page_type="hub",
    sector="va_benefits",
))


PAGES.append(_page(
    page_key="form:21-526ez",
    canonical_path="/va-forms/21-526ez/",
    title="VA Form 21-526EZ: How to File Your Disability Claim 2026",
    h1="VA Form 21-526EZ: How to File a VA Disability Claim",
    summary=(
        "VA Form 21-526EZ is the application veterans use to file a disability "
        "compensation claim. Learn how to complete it, what evidence to attach, "
        "and how the Fully Developed Claim program speeds your decision."
    ),
    body_html=_FORM_526EZ_BODY,
    faq=[
        {"question": "What is VA Form 21-526EZ used for?",
         "answer": "VA Form 21-526EZ is the application for VA disability compensation. Veterans use it to file original disability claims, add new conditions, or file claims for secondary service connection."},
        {"question": "How do I submit VA Form 21-526EZ?",
         "answer": "The fastest way is online at VA.gov. You can also mail it to the VA Claims Intake Center in Janesville, WI, file it in person at a Regional Office, or submit it through a Veterans Service Officer."},
        {"question": "How long does VA Form 21-526EZ take to process?",
         "answer": "In early 2026, the VA averaged about 76 days to decide a disability claim. Fully Developed Claims (FDC) often clear in 100 to 140 days. Claims missing evidence can take 5 to 6 months."},
        {"question": "What documents should I send with VA Form 21-526EZ?",
         "answer": "Include your DD-214, service treatment records, current medical records, a nexus letter, and any buddy statements on VA Form 21-4138. Uploading all evidence upfront triggers the faster FDC process."},
    ],
    takeaways=[
        "VA Form 21-526EZ is the primary application for VA disability compensation.",
        "File online at VA.gov for the fastest processing — the system supports the FDC program.",
        "Strong evidence (DD-214, medical records, nexus letter) submitted up front cuts decision time.",
        "Average VA claim decision time was about 76 days in early 2026 per VA data.",
    ],
    keywords=[
        "va form 21-526ez", "va form 21 526ez", "21-526ez", "va disability claim form",
        "how to file va form 21-526ez", "fully developed claim form",
    ],
    page_type="form",
    sector="va_benefits",
))


_FORM_4138_BODY = """
<p><strong>VA Form 21-4138</strong> &mdash; the &ldquo;Statement in Support of
Claim&rdquo; &mdash; is one of the most flexible forms in the VA claims process.
It is how veterans, family members, and friends add written evidence to a VA
disability claim. In 2026, it remains the standard form for buddy statements and
lay evidence.</p>

<h2>What is VA Form 21-4138?</h2>
<p>VA Form 21-4138 lets anyone make a written statement supporting a VA claim.
You use it to add new facts, explain symptoms, submit a
<strong>buddy statement</strong>, withdraw a claim, or clarify any other claim
detail.</p>

<h2>When to use VA Form 21-4138</h2>
<ul>
  <li><strong>Buddy statements</strong> from fellow service members who saw an
  injury or event.</li>
  <li><strong>Lay statements</strong> from a spouse or family member describing
  symptoms over time.</li>
  <li><strong>Personal statements</strong> from the veteran explaining how a
  condition affects daily life.</li>
  <li><strong>Withdrawing or amending</strong> a pending VA claim.</li>
  <li><strong>Clarifying conflicting evidence</strong> in the file.</li>
</ul>

<h2>How to write a strong buddy statement</h2>
<p>A strong buddy statement is specific, signed, and credible. Use these rules:</p>
<ol>
  <li><strong>Pick the right writer.</strong> The person should have seen the
  event, injury, or symptoms in person.</li>
  <li><strong>Include names and contact info.</strong> Start with the writer's
  full name, address, and phone number. Add the veteran's full name.</li>
  <li><strong>Be specific.</strong> Use real dates, places, units, and
  observations. Avoid generic language.</li>
  <li><strong>Stick to 3&ndash;4 paragraphs.</strong> Focus on either the
  in-service event or how symptoms progressed.</li>
  <li><strong>Sign and date.</strong> Unsigned statements carry no weight in a
  VA decision.</li>
</ol>

<h2>VA Form 21-4138 example structure</h2>
<p>A useful buddy statement usually follows this structure:</p>
<ul>
  <li><strong>Paragraph 1</strong> &mdash; who you are and your relationship to
  the veteran.</li>
  <li><strong>Paragraph 2</strong> &mdash; what you saw, when, and where.</li>
  <li><strong>Paragraph 3</strong> &mdash; how the veteran's condition changed
  or worsened over time.</li>
  <li><strong>Paragraph 4</strong> &mdash; affirmation that the statement is
  true, signed and dated.</li>
</ul>

<h2>Tips for stronger 21-4138 statements</h2>
<ul>
  <li><strong>Quote specific events.</strong> &ldquo;In April 2010 at FOB
  Sharana, I saw John take a fall from a Humvee&rdquo; beats &ldquo;He hurt
  his back overseas.&rdquo;</li>
  <li><strong>Attach proof when possible.</strong> Photos, deployment orders,
  or unit memos can back up the statement.</li>
  <li><strong>Use the writer's own words.</strong> Templates feel canned and
  hurt credibility.</li>
  <li><strong>Submit multiple statements</strong> if more than one person
  witnessed the event.</li>
</ul>

<h2>Related VA forms and guides</h2>
<ul>
  <li><a href="/va-forms/21-526ez/">VA Form 21-526EZ &mdash; Disability claim application</a></li>
  <li><a href="/va-forms/21-0781/">VA Form 21-0781 &mdash; PTSD stressor statement</a></li>
  <li><a href="/va-claims/buddy-statement-guide/">How to write a strong buddy statement</a></li>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA disability claim</a></li>
</ul>

<p>Download the latest VA Form 21-4138 at
<a href="https://www.va.gov/find-forms/about-form-21-4138/" target="_blank" rel="noopener noreferrer">VA.gov</a>.</p>
"""

PAGES.append(_page(
    page_key="form:21-4138",
    canonical_path="/va-forms/21-4138/",
    title="VA Form 21-4138: Statement in Support of Claim Guide 2026",
    h1="VA Form 21-4138: Statement in Support of Claim and Buddy Statements",
    summary=(
        "VA Form 21-4138 is the Statement in Support of Claim. Learn when to "
        "use it, how to write a strong buddy statement, and how to submit it to "
        "support your VA disability claim."
    ),
    body_html=_FORM_4138_BODY,
    faq=[
        {"question": "What is VA Form 21-4138 used for?",
         "answer": "VA Form 21-4138 is the Statement in Support of Claim. Veterans, family members, and witnesses use it to add lay evidence, submit buddy statements, withdraw claims, or clarify facts in a VA disability claim."},
        {"question": "Who can write a VA Form 21-4138 buddy statement?",
         "answer": "Any fellow service member, family member, friend, or coworker who saw the in-service event or witnessed symptoms first-hand can write a statement. The writer must sign and date the form."},
        {"question": "What makes a strong VA buddy statement?",
         "answer": "Strong statements use specific dates, places, and observations rather than vague language. They are 3 to 4 paragraphs, signed, dated, and written in the witness's own words rather than copied from a template."},
        {"question": "How do I submit VA Form 21-4138?",
         "answer": "Upload it through VA.gov with your claim, mail it to the VA Claims Intake Center in Janesville, WI, or give it to a Veterans Service Officer to file."},
    ],
    takeaways=[
        "VA Form 21-4138 is the standard form for lay evidence and buddy statements.",
        "Strong statements are specific, signed, dated, and written in the writer's own words.",
        "Use it to add facts, submit buddy statements, withdraw claims, or clarify the record.",
        "Upload via VA.gov for the fastest processing — paper mail to Janesville, WI also works.",
    ],
    keywords=[
        "va form 21-4138", "21-4138 form", "statement in support of claim",
        "va buddy statement form", "va lay statement form", "21 4138",
    ],
    page_type="form",
    sector="va_benefits",
))


_FORM_0781_BODY = """
<p><strong>VA Form 21-0781</strong> is the form veterans use to describe the
traumatic event behind a service-connected mental health claim &mdash; including
PTSD. In 2024, the VA updated this form and discontinued the separate 21-0781a
(personal assault/MST) form. In 2026, all mental health stressors now go on
this single revised 21-0781.</p>

<h2>What is VA Form 21-0781?</h2>
<p>VA Form 21-0781 is the &ldquo;Statement in Support of Claim for Service
Connection of a Mental Health Condition.&rdquo; You use it to describe the
in-service event or stressor that caused PTSD or another mental health
condition.</p>

<h2>2024 changes: 21-0781a is gone</h2>
<p>On <strong>June 28, 2024</strong>, the VA discontinued VA Form 21-0781a.
The agency rebuilt the standard 21-0781 to cover every type of stressor &mdash;
combat, training accidents, military sexual trauma (MST), personal assault, and
non-combat incidents. Today, MST claims also use VA Form 21-0781.</p>

<h2>When you need VA Form 21-0781</h2>
<p>You use this form when:</p>
<ul>
  <li>You file a new claim for PTSD or another service-connected mental health
  condition.</li>
  <li>The VA already denied your PTSD claim and you want to provide a clearer
  stressor.</li>
  <li>You're filing for MST or personal assault as a mental health stressor.</li>
</ul>

<h2>What to include on VA Form 21-0781</h2>
<p>Provide as much detail as you can. Approximate information is acceptable
&mdash; the VA will still review partial details.</p>
<ul>
  <li><strong>Date(s) of the event.</strong> A month and year is enough.</li>
  <li><strong>Location and unit.</strong> Base, country, deployment, or unit
  designation.</li>
  <li><strong>Description of the event.</strong> What happened, in your own
  words.</li>
  <li><strong>Impact on your life.</strong> How it affected your work,
  relationships, and health.</li>
</ul>

<h2>What is no longer required</h2>
<p>Under the new 21-0781, witness names are <strong>optional</strong>. You do
not need to remember specific names or dates of death. The VA also accepts
partial information for MST stressors.</p>

<h2>Tips for completing VA Form 21-0781</h2>
<ul>
  <li><strong>Stick to facts.</strong> Describe what you saw and felt without
  guessing about other people.</li>
  <li><strong>Use approximate dates.</strong> &ldquo;Summer 2008&rdquo; is fine
  when the exact date is unclear.</li>
  <li><strong>Add markers of behavioral change.</strong> Performance reviews,
  pregnancy tests, transfer requests, and complaints to friends can support an
  MST claim.</li>
  <li><strong>Pair it with a doctor's diagnosis.</strong> The VA needs a current
  PTSD diagnosis from a qualified clinician.</li>
  <li><strong>Submit lay statements</strong> on
  <a href="/va-forms/21-4138/">VA Form 21-4138</a> from people who saw a change
  in your behavior after the event.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-disability/ptsd/">VA disability rating for PTSD</a></li>
  <li><a href="/va-forms/21-526ez/">VA Form 21-526EZ &mdash; main disability application</a></li>
  <li><a href="/va-forms/21-4138/">VA Form 21-4138 &mdash; buddy statements</a></li>
  <li><a href="/explainers/pact-act-explained/">PACT Act explained</a></li>
</ul>

<p>The current form is available at
<a href="https://www.va.gov/find-forms/about-form-21-0781/" target="_blank" rel="noopener noreferrer">VA.gov</a>.</p>
"""

PAGES.append(_page(
    page_key="form:21-0781",
    canonical_path="/va-forms/21-0781/",
    title="VA Form 21-0781: PTSD Stressor Statement Guide 2026",
    h1="VA Form 21-0781: PTSD and Mental Health Stressor Statement",
    summary=(
        "VA Form 21-0781 is how you describe the in-service stressor behind a "
        "PTSD or mental health claim in 2026. Learn what changed in the 2024 "
        "update and how to complete it."
    ),
    body_html=_FORM_0781_BODY,
    faq=[
        {"question": "What is VA Form 21-0781?",
         "answer": "VA Form 21-0781 is the Statement in Support of Claim for Service Connection of a Mental Health Condition. Veterans use it to describe the in-service event or stressor behind a PTSD or other mental health claim."},
        {"question": "Is VA Form 21-0781a still used?",
         "answer": "No. On June 28, 2024, the VA discontinued Form 21-0781a. All mental health stressors, including military sexual trauma and personal assault, now use the revised VA Form 21-0781."},
        {"question": "Do I need to list witnesses on VA Form 21-0781?",
         "answer": "No. Under the 2024 revision, witness names and contact information are optional. The VA will still review your claim with partial or approximate details."},
        {"question": "What evidence supports VA Form 21-0781?",
         "answer": "Pair the form with a current PTSD or mental health diagnosis from a qualified clinician. Buddy statements on VA Form 21-4138, performance evaluations, transfer requests, and medical records also strengthen the claim."},
    ],
    takeaways=[
        "VA Form 21-0781 is the PTSD and mental health stressor statement.",
        "In 2024, the VA discontinued the separate 21-0781a — all stressors (including MST) now use 21-0781.",
        "Witness names are now optional; approximate dates are accepted.",
        "Pair the form with a current mental health diagnosis and supporting lay statements.",
    ],
    keywords=[
        "va form 21-0781", "21-0781", "ptsd stressor statement", "21 0781",
        "va ptsd form", "va mst form", "21-0781a", "mental health stressor va",
    ],
    page_type="form",
    sector="va_benefits",
))


_FORM_8940_BODY = """
<p><strong>VA Form 21-8940</strong> is the application veterans use to apply for
<strong>Total Disability based on Individual Unemployability (TDIU)</strong>.
TDIU pays VA disability at the 100% rate &mdash; about $3,938 per month for a
single veteran in 2026 &mdash; for veterans whose service-connected conditions
prevent them from working.</p>

<h2>What is VA Form 21-8940?</h2>
<p>VA Form 21-8940 is the &ldquo;Application for Increased Compensation Based on
Unemployability.&rdquo; You use it to ask the VA to pay disability compensation
at the 100% rate even if your combined rating is below 100%.</p>

<h2>When to file VA Form 21-8940</h2>
<p>File this form when your service-connected disabilities keep you from holding
a full-time job. The VA also looks at the form during regular disability claims
if your evidence suggests you can't work.</p>

<h2>TDIU eligibility before filing</h2>
<p>To meet the <a href="/explainers/tdiu-explained/">schedular TDIU</a> criteria
under 38 CFR 4.16(a), you generally need:</p>
<ul>
  <li><strong>One condition at 60% or higher</strong>, OR</li>
  <li><strong>A combined rating of 70% or more</strong>, with at least one
  condition rated 40% or higher.</li>
</ul>
<p>Veterans who don't meet those thresholds can still apply under
<strong>extraschedular TDIU</strong> (38 CFR 4.16(b)).</p>

<h2>What VA Form 21-8940 asks</h2>
<p>The form gathers information the VA needs to decide if you can hold
substantially gainful work.</p>
<ul>
  <li>Your service-connected conditions that prevent work.</li>
  <li>The <strong>last date you worked full-time</strong>.</li>
  <li>Your <strong>last 5 years of employers</strong> &mdash; name, address,
  dates, hours per week, and gross earnings.</li>
  <li>Highest gross earnings per month before you stopped working.</li>
  <li>Education and training history.</li>
  <li>Any attempts to find work since becoming unable to work.</li>
</ul>

<h2>VA Form 21-8940 pairs with VA Form 21-4192</h2>
<p>When you list past employers, the VA mails each one
<strong>VA Form 21-4192</strong> &mdash; Request for Employment Information.
Employers report your last day, reason for leaving, and any accommodations.</p>
<p>If an employer doesn't return the form, the VA cannot deny TDIU on that
basis alone. Document your follow-up attempts.</p>

<h2>Tips for completing VA Form 21-8940</h2>
<ul>
  <li><strong>Be honest about your last day worked.</strong> The effective date
  often anchors here.</li>
  <li><strong>Don't pad income.</strong> Earnings must reflect what you actually
  reported on taxes.</li>
  <li><strong>Mark protected/sheltered work clearly.</strong> Earnings inside a
  protected work environment don't count against you.</li>
  <li><strong>Add a personal statement.</strong> Use
  <a href="/va-forms/21-4138/">VA Form 21-4138</a> to describe how your
  conditions limit work, in your own words.</li>
  <li><strong>Submit supporting medical evidence.</strong> A vocational expert
  or treating provider opinion strengthens the claim.</li>
</ul>

<h2>What happens after you file</h2>
<p>The VA reviews the 21-8940 alongside your medical and employment evidence.
About <strong>87,000+ veterans currently receive TDIU</strong>, but TDIU is
under-claimed &mdash; many eligible veterans never apply.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/tdiu-explained/">TDIU explained &mdash; eligibility and how it works</a></li>
  <li><a href="/explainers/tdiu-benefits/">TDIU benefits beyond monthly pay</a></li>
  <li><a href="/explainers/tdiu-approval-rate/">VA TDIU approval rate &mdash; the data</a></li>
  <li><a href="/va-forms/21-526ez/">VA Form 21-526EZ &mdash; main disability claim</a></li>
</ul>

<p>The current form is available at
<a href="https://www.va.gov/find-forms/about-form-21-8940/" target="_blank" rel="noopener noreferrer">VA.gov</a>.</p>
"""

PAGES.append(_page(
    page_key="form:21-8940",
    canonical_path="/va-forms/21-8940/",
    title="VA Form 21-8940: TDIU Unemployability Application Guide",
    h1="VA Form 21-8940: TDIU Application for Individual Unemployability",
    summary=(
        "VA Form 21-8940 is the application for Total Disability based on "
        "Individual Unemployability (TDIU). Learn the eligibility rules, what "
        "the form asks, and how to file in 2026."
    ),
    body_html=_FORM_8940_BODY,
    faq=[
        {"question": "What is VA Form 21-8940 used for?",
         "answer": "VA Form 21-8940 is the application for Total Disability based on Individual Unemployability (TDIU). It lets the VA pay disability compensation at the 100% rate when service-connected conditions prevent substantially gainful employment."},
        {"question": "Who qualifies to file VA Form 21-8940?",
         "answer": "Veterans with one service-connected condition rated 60% or higher, or a combined rating of 70% or more with at least one condition at 40%, meet the schedular TDIU criteria. Veterans below those thresholds may still apply for extraschedular TDIU."},
        {"question": "What is VA Form 21-4192?",
         "answer": "VA Form 21-4192 is the Request for Employment Information. The VA mails it to each former employer listed on your 21-8940 to verify dates worked, reason for leaving, and any accommodations."},
        {"question": "How much does TDIU pay in 2026?",
         "answer": "TDIU pays VA disability at the 100% rate — about $3,938 per month tax-free for a single veteran in 2026. Veterans with dependents receive higher amounts."},
    ],
    takeaways=[
        "VA Form 21-8940 applies for TDIU — VA disability paid at the 100% rate.",
        "Schedular TDIU needs one rating at 60% or combined 70% with one at 40%.",
        "TDIU pays about $3,938/month for a single veteran in 2026.",
        "The form pairs with VA Form 21-4192 sent to former employers.",
    ],
    keywords=[
        "va form 21-8940", "21-8940", "tdiu application", "va unemployability form",
        "individual unemployability application", "21 8940",
    ],
    page_type="form",
    sector="va_benefits",
))


_INTENT_TO_FILE_BODY = """
<p>A <strong>VA Intent to File (ITF)</strong> locks in your effective date for
back pay. By filing an ITF in 2026, you have a full 12 months to gather evidence
and submit a complete disability claim &mdash; without losing a single day of
retroactive compensation.</p>

<h2>What is a VA Intent to File?</h2>
<p>An Intent to File tells the VA you plan to file a disability or pension
claim. It does not start the claim review. Instead, it preserves your
<strong>effective date</strong> &mdash; the date your back pay clock starts
ticking &mdash; for up to 365 days.</p>

<h2>Why VA Intent to File matters</h2>
<p>VA back pay flows from your effective date. The longer the gap between when
you should have applied and when your claim is granted, the more retroactive
compensation you receive.</p>
<p>For example: a veteran with a 70% rating earns about $1,808 per month in 2026.
Filing an ITF and submitting the formal claim 11 months later preserves about
<strong>$19,893 in back pay</strong> that would otherwise be lost.</p>

<h2>How to file a VA Intent to File</h2>
<p>You have three ways to submit a VA ITF.</p>
<ol>
  <li><strong>Online at VA.gov.</strong> Start (but don't finish) a disability
  application. The system automatically creates an ITF in your file.</li>
  <li><strong>By phone.</strong> Call <strong>1-800-827-1000</strong> and ask
  the representative to file an Intent to File on your behalf.</li>
  <li><strong>By mail.</strong> Send completed
  <strong>VA Form 21-0966</strong> &mdash; Intent to File a Claim for
  Compensation and/or Pension &mdash; to the VA Claims Intake Center.</li>
</ol>

<h2>What claims an ITF covers</h2>
<p>One ITF can preserve the effective date for any combination of these claim
types:</p>
<ul>
  <li><strong>VA disability compensation</strong> (the most common use).</li>
  <li><strong>VA pension</strong> for wartime veterans with limited income.</li>
  <li><strong>Survivors' DIC or pension</strong> for spouses, children, or
  dependent parents.</li>
</ul>

<h2>How long an Intent to File lasts</h2>
<p>An ITF protects your effective date for <strong>12 months (365 days)</strong>
from the date you file it. You must submit a complete claim within that window
or the ITF expires and the effective date resets to the date the claim is
finally filed.</p>

<h2>When to file an ITF instead of a claim</h2>
<ul>
  <li>You haven't gathered all your medical evidence yet.</li>
  <li>You're waiting on a <a href="/explainers/what-is-a-nexus-letter/">nexus
  letter</a> from a doctor.</li>
  <li>You're still pulling service treatment records.</li>
  <li>You're working with a VSO and need time to prepare the strongest claim.</li>
  <li>You're approaching separation and want to file under the
  <a href="/va-claims/benefits-delivery-at-discharge/">BDD program</a> later.</li>
</ul>

<h2>Common Intent to File mistakes</h2>
<ul>
  <li><strong>Letting the ITF expire.</strong> Mark the 365-day deadline on your
  calendar.</li>
  <li><strong>Filing too late.</strong> An ITF doesn't help if you wait years to
  file the claim.</li>
  <li><strong>Submitting a partial claim and assuming it counts as an ITF.</strong>
  You must specifically request an ITF or use VA Form 21-0966.</li>
  <li><strong>Forgetting survivors' coverage.</strong> A surviving spouse needs
  to file an ITF too if they plan to file DIC.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-forms/21-526ez/">VA Form 21-526EZ &mdash; disability claim application</a></li>
  <li><a href="/explainers/va-disability-back-pay/">How VA back pay is calculated</a></li>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA disability claim</a></li>
  <li><a href="/va-claims/benefits-delivery-at-discharge/">Benefits Delivery at Discharge program</a></li>
</ul>

<p>You can start an Intent to File or complete VA Form 21-0966 at
<a href="https://www.va.gov/resources/your-intent-to-file-a-va-claim/" target="_blank" rel="noopener noreferrer">VA.gov</a>.</p>
"""

PAGES.append(_page(
    page_key="page:va-intent-to-file",
    canonical_path="/va-intent-to-file/",
    title="VA Intent to File 2026: Protect Your Back Pay Date",
    h1="VA Intent to File: How to Protect Your Effective Date in 2026",
    summary=(
        "A VA Intent to File preserves your effective date for back pay for 12 "
        "months. Learn how to file an ITF online, by phone, or with VA Form "
        "21-0966 to maximize your retroactive compensation."
    ),
    body_html=_INTENT_TO_FILE_BODY,
    faq=[
        {"question": "What is a VA Intent to File?",
         "answer": "A VA Intent to File (ITF) tells the VA you plan to file a disability or pension claim. It preserves your effective date for back pay for up to 12 months so retroactive compensation isn't lost while you gather evidence."},
        {"question": "How long does a VA Intent to File last?",
         "answer": "An ITF protects your effective date for 12 months (365 days). You must submit a complete claim within that window or the effective date resets to the actual filing date."},
        {"question": "How do I file a VA Intent to File?",
         "answer": "You can file three ways: start a disability application at VA.gov (auto-creates an ITF), call the VA at 1-800-827-1000, or mail VA Form 21-0966 to the VA Claims Intake Center."},
        {"question": "How much back pay does an ITF protect?",
         "answer": "It depends on your final rating. A 70% rating pays about $1,808 per month in 2026. Filing an ITF and the formal claim 11 months later preserves roughly $19,893 in back pay that would otherwise be lost."},
    ],
    takeaways=[
        "A VA Intent to File locks your effective date for back pay for 12 months.",
        "File online at VA.gov, by phone at 1-800-827-1000, or via VA Form 21-0966.",
        "One ITF covers disability compensation, pension, and survivors' benefits.",
        "Set a calendar reminder — if you miss the 365-day window, your effective date resets.",
    ],
    keywords=[
        "va intent to file", "intent to file va claim", "va itf",
        "va form 21-0966", "va effective date", "intent to file deadline",
    ],
    page_type="page",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 4 — VA Conditions Reference cluster (4 pages)
# ---------------------------------------------------------------------------

_CONDITIONS_LIST_BODY = """
<p>The <strong>VA disability conditions list</strong> covers thousands of
medical conditions recognized for service connection. Each one is rated under
38 CFR Part 4 &mdash; the VA Schedule for Rating Disabilities. This 2026 guide
shows the most common conditions, how the VA rates each, and which related
secondary conditions you might also claim.</p>

<h2>How VA disability conditions are rated</h2>
<p>The VA assigns a percentage (0%, 10%, 20%, up to 100%) for each
service-connected condition. Ratings reflect the average loss in working ability
caused by the disability. Multiple ratings combine using the VA's
<a href="/tools/va-disability-rating-calculator/">combined rating formula</a>
&mdash; not simple addition.</p>

<h2>Most common VA disability conditions</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Condition</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">DC code</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Rating range</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/tinnitus/">Tinnitus</a></td><td style="padding:0.5rem;border:1px solid #ddd;">6260</td><td style="padding:0.5rem;border:1px solid #ddd;">10%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/ptsd/">PTSD</a></td><td style="padding:0.5rem;border:1px solid #ddd;">9411</td><td style="padding:0.5rem;border:1px solid #ddd;">0–100%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/hearing-loss/">Hearing loss</a></td><td style="padding:0.5rem;border:1px solid #ddd;">6100</td><td style="padding:0.5rem;border:1px solid #ddd;">0–100%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/sleep-apnea/">Sleep apnea</a></td><td style="padding:0.5rem;border:1px solid #ddd;">6847</td><td style="padding:0.5rem;border:1px solid #ddd;">0/30/50/100%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Lumbar strain</td><td style="padding:0.5rem;border:1px solid #ddd;">5237</td><td style="padding:0.5rem;border:1px solid #ddd;">10/20/40/50%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Knee limitation of motion</td><td style="padding:0.5rem;border:1px solid #ddd;">5260</td><td style="padding:0.5rem;border:1px solid #ddd;">0/10/20/30%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/hypertension/">Hypertension</a></td><td style="padding:0.5rem;border:1px solid #ddd;">7101</td><td style="padding:0.5rem;border:1px solid #ddd;">10/20/40/60%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/va-disability/migraines/">Migraines</a></td><td style="padding:0.5rem;border:1px solid #ddd;">8100</td><td style="padding:0.5rem;border:1px solid #ddd;">0/10/30/50%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Scars (unstable/painful)</td><td style="padding:0.5rem;border:1px solid #ddd;">7804</td><td style="padding:0.5rem;border:1px solid #ddd;">10/20/30%</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Diabetes type 2</td><td style="padding:0.5rem;border:1px solid #ddd;">7913</td><td style="padding:0.5rem;border:1px solid #ddd;">10/20/40/60/100%</td></tr>
</tbody>
</table>

<h2>Mental health conditions</h2>
<p>All service-connected mental health conditions use a single rating formula
(38 CFR 4.130): 0%, 10%, 30%, 50%, 70%, or 100%. Common diagnostic codes
include:</p>
<ul>
  <li><strong>PTSD</strong> &mdash; DC 9411</li>
  <li><strong>Major depressive disorder</strong> &mdash; DC 9434</li>
  <li><strong>Generalized anxiety disorder</strong> &mdash; DC 9400</li>
  <li><strong>Adjustment disorder</strong> &mdash; DC 9440</li>
  <li><strong>Bipolar disorder</strong> &mdash; DC 9432</li>
</ul>

<h2>Musculoskeletal conditions</h2>
<p>Back, knee, shoulder, and hip conditions are the most-claimed
musculoskeletal disabilities. Range of motion drives the rating.</p>
<ul>
  <li>Cervical spine &mdash; DC 5237</li>
  <li>Lumbar spine &mdash; DC 5237 or DC 5242</li>
  <li>Knee (limitation of flexion) &mdash; DC 5260</li>
  <li>Knee (instability) &mdash; DC 5257</li>
  <li>Shoulder &mdash; DC 5201</li>
</ul>

<h2>Hearing and tinnitus</h2>
<p>Tinnitus is the single most-claimed VA disability. It pays a flat 10%
regardless of severity. Hearing loss uses a separate formula based on speech
discrimination and puretone audiometry.</p>

<h2>Respiratory conditions</h2>
<ul>
  <li>Sleep apnea &mdash; DC 6847</li>
  <li>Asthma &mdash; DC 6602</li>
  <li>COPD &mdash; DC 6604</li>
  <li>Sinusitis &mdash; DC 6510-6514</li>
</ul>

<h2>Presumptive conditions</h2>
<p>Some conditions are presumed service-connected based on exposure or service
era. The <a href="/explainers/pact-act-presumptive-conditions/">PACT Act</a>
adds dozens of burn pit cancers and respiratory illnesses. Agent Orange,
Camp Lejeune, and Gulf War service all carry their own presumptive lists.</p>

<h2>Secondary conditions</h2>
<p>A condition caused or worsened by a service-connected disability can be
claimed as <a href="/va-claims/secondary-conditions/">secondary</a>. Common
examples include sleep apnea secondary to PTSD, depression secondary to chronic
pain, and radiculopathy secondary to a back condition.</p>

<h2>How to claim a condition on the list</h2>
<ol>
  <li>File <a href="/va-forms/21-526ez/">VA Form 21-526EZ</a>.</li>
  <li>List every condition you want rated.</li>
  <li>Include a current medical diagnosis and service treatment records.</li>
  <li>Add a <a href="/explainers/what-is-a-nexus-letter/">nexus letter</a>
  linking the condition to service.</li>
  <li>Submit lay statements on <a href="/va-forms/21-4138/">VA Form 21-4138</a>.</li>
</ol>

<p>Want to estimate your payment? Use the
<a href="/tools/va-disability-rating-calculator/">VA disability rating
calculator</a> or check the full
<a href="/explainers/va-disability-rates-2026/">2026 VA disability rate chart</a>.</p>
"""

PAGES.append(_page(
    page_key="page:va-disability-conditions-list",
    canonical_path="/va-disability-conditions-list/",
    title="VA Disability Conditions List & Ratings (2026 Guide)",
    h1="VA Disability Conditions List and Ratings",
    summary=(
        "The full VA disability conditions list for 2026. See the top "
        "service-connected conditions, their diagnostic codes, rating ranges, "
        "and how to file a claim."
    ),
    body_html=_CONDITIONS_LIST_BODY,
    faq=[
        {"question": "How many conditions are on the VA disability list?",
         "answer": "Thousands. The VA Schedule for Rating Disabilities (38 CFR Part 4) covers virtually every medical condition, organized by body system. The most common conditions account for the majority of claims."},
        {"question": "What is the most common VA disability?",
         "answer": "Tinnitus is the most-claimed VA disability. It pays a flat 10% rating regardless of severity. PTSD, hearing loss, and lumbar strain follow closely behind."},
        {"question": "How are VA disability ratings combined?",
         "answer": "The VA uses a 'whole person' formula rather than simple addition. Higher ratings count first, and each additional rating reduces remaining 'efficiency.' Use the VA combined rating calculator to see your total."},
        {"question": "Can I claim conditions not on the VA list?",
         "answer": "Yes. The VA can rate a condition 'by analogy' using the most similar listed condition. Talk to a VSO or accredited representative if your diagnosis doesn't have a specific diagnostic code."},
    ],
    takeaways=[
        "Every VA-rated condition has a diagnostic code under 38 CFR Part 4.",
        "Tinnitus, PTSD, and hearing loss are the three most-claimed conditions.",
        "Mental health conditions all share one rating formula (0/10/30/50/70/100%).",
        "Conditions caused by another service-connected condition can be claimed as secondary.",
    ],
    keywords=[
        "va disability conditions list", "va disability list", "va rated conditions",
        "va disability conditions and ratings", "list of va disabilities",
    ],
    page_type="page",
    sector="va_benefits",
))


_PERCENTAGES_BODY = """
<p>The <strong>VA disability percentages</strong> system rates each
service-connected condition from 0% to 100% in 10% increments. This 2026 guide
explains what each percentage means, how the VA assigns ratings, and how
multiple ratings combine using VA math.</p>

<h2>How VA disability percentages work</h2>
<p>VA percentages represent the average loss in earning capacity caused by a
service-connected condition. The 38 CFR Part 4 rating schedule sets specific
criteria for each percentage of every condition.</p>

<h2>What each VA disability percentage pays in 2026</h2>
<p>Monthly VA disability pay rises with your combined rating. Rates increased
2.8% on December 1, 2025 (the 2026 COLA).</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Rating</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Veteran alone</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">With spouse</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">10%</td><td style="padding:0.5rem;border:1px solid #ddd;">$175.51</td><td style="padding:0.5rem;border:1px solid #ddd;">$175.51</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">20%</td><td style="padding:0.5rem;border:1px solid #ddd;">$346.95</td><td style="padding:0.5rem;border:1px solid #ddd;">$346.95</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">30%</td><td style="padding:0.5rem;border:1px solid #ddd;">$537.42</td><td style="padding:0.5rem;border:1px solid #ddd;">$601.42</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">40%</td><td style="padding:0.5rem;border:1px solid #ddd;">$774.16</td><td style="padding:0.5rem;border:1px solid #ddd;">$859.16</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">50%</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,102.04</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,208.04</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">60%</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,395.93</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,523.93</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">70%</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,759.19</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,908.19</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">80%</td><td style="padding:0.5rem;border:1px solid #ddd;">$2,044.89</td><td style="padding:0.5rem;border:1px solid #ddd;">$2,214.89</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">90%</td><td style="padding:0.5rem;border:1px solid #ddd;">$2,297.96</td><td style="padding:0.5rem;border:1px solid #ddd;">$2,489.96</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">100%</td><td style="padding:0.5rem;border:1px solid #ddd;">$3,831.30</td><td style="padding:0.5rem;border:1px solid #ddd;">$4,044.91</td></tr>
</tbody>
</table>
<p>See the full <a href="/explainers/va-disability-rates-2026/">2026 VA disability pay chart</a> for all dependent variations.</p>

<h2>What 0% means</h2>
<p>A 0% rating still establishes service connection, even though it pays
nothing. It locks in the effective date and lets you file for an increase
later. You also gain priority access to VA healthcare for that condition.</p>

<h2>What 100% means</h2>
<p>A 100% rating is the highest VA disability rating. It pays about $3,831 per
month in 2026 for a single veteran. Veterans rated
<a href="/explainers/100-percent-va-disability-benefits/">100% disabled</a>
also qualify for CHAMPVA, dependents education (Chapter 35), commissary access,
and many state benefits.</p>

<h2>Common VA percentages by condition</h2>
<ul>
  <li><strong>Tinnitus</strong> &mdash; flat 10%.</li>
  <li><strong>PTSD</strong> &mdash; usually 30%, 50%, or 70%.</li>
  <li><strong>Sleep apnea with CPAP</strong> &mdash; 50%.</li>
  <li><strong>Migraines (prostrating, monthly)</strong> &mdash; 30%.</li>
  <li><strong>Lumbar strain (flexion ≤30°)</strong> &mdash; 40%.</li>
  <li><strong>Hearing loss (mild bilateral)</strong> &mdash; usually 0%.</li>
</ul>

<h2>How combined ratings work</h2>
<p>The VA doesn't add ratings together. Instead, it uses a &ldquo;whole
person&rdquo; formula. Higher ratings count first, and each additional rating
reduces the remaining &ldquo;efficiency&rdquo; left in your body.</p>
<p>Example: 50% + 30% = 65% rounded to <strong>70%</strong>, not 80%.</p>
<p>Use the <a href="/tools/va-disability-rating-calculator/">VA combined rating
calculator</a> to see exactly how your conditions stack.</p>

<h2>TDIU pays at the 100% rate</h2>
<p><a href="/explainers/tdiu-explained/">Total Disability based on Individual
Unemployability (TDIU)</a> pays at the 100% rate even when your combined rating
is below 100%. Veterans with one 60% condition or combined 70% (with one at
40%+) who can't work may qualify.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/va-disability-rates-2026/">2026 VA disability rate chart</a></li>
  <li><a href="/tools/va-disability-rating-calculator/">VA combined rating calculator</a></li>
  <li><a href="/va-disability-conditions-list/">VA disability conditions list</a></li>
  <li><a href="/explainers/how-to-get-100-va-disability/">How to reach 100% VA disability</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="page:va-disability-percentages",
    canonical_path="/va-disability-percentages/",
    title="VA Disability Percentages 2026: What Each Rating Means",
    h1="VA Disability Percentages: How VA Ratings Work in 2026",
    summary=(
        "VA disability percentages range from 0% to 100% in 10% steps. Learn "
        "what each rating means, what it pays in 2026, and how the VA combines "
        "multiple ratings using VA math."
    ),
    body_html=_PERCENTAGES_BODY,
    faq=[
        {"question": "What do VA disability percentages mean?",
         "answer": "VA disability percentages represent the average loss in earning capacity caused by a service-connected condition. Each rating from 0% to 100% has specific criteria under 38 CFR Part 4."},
        {"question": "How much does each VA disability percentage pay in 2026?",
         "answer": "A 10% rating pays about $175 per month. A 50% rating pays about $1,102. A 100% rating pays about $3,831 for a single veteran. Veterans with dependents earn more starting at the 30% rating."},
        {"question": "How does the VA combine multiple disability ratings?",
         "answer": "The VA uses a 'whole person' formula instead of addition. Higher ratings count first, and each additional rating reduces the remaining efficiency. A 50% plus 30% combines to 70%, not 80%."},
        {"question": "Does a 0% VA rating pay anything?",
         "answer": "No, a 0% rating pays nothing but it establishes service connection. It locks the effective date for future increases and grants priority VA healthcare for that condition."},
    ],
    takeaways=[
        "VA disability percentages range from 0% to 100% in 10% increments.",
        "100% pays about $3,831/month for a single veteran in 2026.",
        "The VA combines ratings using a 'whole person' formula — not simple addition.",
        "TDIU lets veterans below 100% receive the 100% pay rate when they can't work.",
    ],
    keywords=[
        "va disability percentages", "va disability rating percentages",
        "va percentages for conditions", "va disability percent meanings",
        "va rating percentages explained",
    ],
    page_type="page",
    sector="va_benefits",
))


_CHEAT_SHEET_BODY = """
<p>The <strong>VA disability cheat sheet</strong> is a quick-reference guide to
the rules, ratings, and dollar amounts that matter most for veterans in 2026.
Bookmark this page or share it with a buddy starting a claim.</p>

<h2>2026 VA disability pay rates (quick view)</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Rating</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Monthly (alone)</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Monthly (with spouse)</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">10%</td><td style="padding:0.5rem;border:1px solid #ddd;">$175.51</td><td style="padding:0.5rem;border:1px solid #ddd;">$175.51</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">30%</td><td style="padding:0.5rem;border:1px solid #ddd;">$537.42</td><td style="padding:0.5rem;border:1px solid #ddd;">$601.42</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">50%</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,102.04</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,208.04</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">70%</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,759.19</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,908.19</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">100%</td><td style="padding:0.5rem;border:1px solid #ddd;">$3,831.30</td><td style="padding:0.5rem;border:1px solid #ddd;">$4,044.91</td></tr>
</tbody>
</table>

<h2>VA combined rating math (cheat formula)</h2>
<ol>
  <li>Sort your ratings from highest to lowest.</li>
  <li>Start with 100% efficiency.</li>
  <li>Subtract the highest rating from 100. Take that percent of what's left
  for the next rating.</li>
  <li>Round the final number to the nearest 10.</li>
</ol>
<p><strong>Example:</strong> 50 + 30 + 20.</p>
<ul>
  <li>100 &minus; 50 = 50 left.</li>
  <li>30% of 50 = 15. 50 + 15 = 65.</li>
  <li>100 &minus; 65 = 35 left. 20% of 35 = 7. 65 + 7 = 72.</li>
  <li>Round 72 → <strong>70%</strong>.</li>
</ul>

<h2>Top 10 claimed VA conditions</h2>
<ol>
  <li>Tinnitus &mdash; flat 10%</li>
  <li>Hearing loss &mdash; 0–100%</li>
  <li>Lumbar strain &mdash; 10–50%</li>
  <li>PTSD &mdash; 0–100%</li>
  <li>Knee limitation &mdash; 0–30%</li>
  <li>Sleep apnea &mdash; 0/30/50/100%</li>
  <li>Migraines &mdash; 0/10/30/50%</li>
  <li>Painful scars &mdash; 10/20/30%</li>
  <li>Hypertension &mdash; 10/20/40/60%</li>
  <li>Sciatica/radiculopathy &mdash; 10–80%</li>
</ol>

<h2>Important VA forms cheat list</h2>
<ul>
  <li><a href="/va-forms/21-526ez/">21-526EZ</a> &mdash; main disability claim.</li>
  <li><a href="/va-forms/21-4138/">21-4138</a> &mdash; buddy and lay statements.</li>
  <li><a href="/va-forms/21-0781/">21-0781</a> &mdash; PTSD stressor statement.</li>
  <li><a href="/va-forms/21-8940/">21-8940</a> &mdash; TDIU application.</li>
  <li><strong>21-0966</strong> &mdash; Intent to File.</li>
</ul>

<h2>Key deadlines</h2>
<ul>
  <li><strong>Intent to File</strong> &mdash; 12 months to file the formal claim.</li>
  <li><strong>BDD claim</strong> &mdash; file 180 to 90 days before separation.</li>
  <li><strong>Higher-Level Review / Supplemental claim</strong> &mdash; 1 year
  from VA decision letter.</li>
  <li><strong>Board appeal</strong> &mdash; 1 year from decision letter.</li>
</ul>

<h2>Where to get help</h2>
<ul>
  <li><strong>VSO</strong> &mdash; free. Use VFW, DAV, American Legion, or
  state-level service officers.</li>
  <li><strong>Accredited VA attorney</strong> &mdash; usually for appeals.</li>
  <li><strong>VA.gov</strong> &mdash; file online, track status, upload
  evidence.</li>
  <li><strong>VA hotline</strong> &mdash; 1-800-827-1000.</li>
</ul>

<h2>Bookmark these guides</h2>
<ul>
  <li><a href="/explainers/va-disability-rates-2026/">Full 2026 VA pay chart</a></li>
  <li><a href="/explainers/va-disability-pay-dates-2026/">2026 VA disability pay dates</a></li>
  <li><a href="/tools/va-disability-rating-calculator/">VA combined rating calculator</a></li>
  <li><a href="/explainers/how-to-get-100-va-disability/">Path to 100% VA disability</a></li>
  <li><a href="/va-disability-conditions-list/">Full VA conditions list</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="page:va-disability-cheat-sheet",
    canonical_path="/va-disability-cheat-sheet/",
    title="VA Disability Cheat Sheet: 2026 Quick Reference Guide",
    h1="VA Disability Cheat Sheet: 2026 Quick Reference Guide",
    summary=(
        "The 2026 VA disability cheat sheet. Quick-reference pay rates, "
        "combined rating math, top conditions, key forms, and important "
        "deadlines for veterans."
    ),
    body_html=_CHEAT_SHEET_BODY,
    faq=[
        {"question": "What is the VA disability cheat sheet?",
         "answer": "A quick-reference guide covering the most important numbers and rules veterans need to know: 2026 pay rates, combined rating math, top claimed conditions, key forms, and filing deadlines."},
        {"question": "How does VA combined rating math work?",
         "answer": "The VA does not add ratings together. Sort highest to lowest, start with 100% efficiency, and subtract each rating from what's left. Round the final number to the nearest 10."},
        {"question": "What are the most common VA disabilities?",
         "answer": "Tinnitus, hearing loss, lumbar strain, PTSD, and knee conditions are the top five most-claimed VA disabilities. Tinnitus alone accounts for over 2 million ratings."},
        {"question": "What is the deadline to appeal a VA decision?",
         "answer": "You have one year from the date of the VA decision letter to file a Higher-Level Review, Supplemental Claim, or Board appeal. Missing the deadline can require starting the claim over."},
    ],
    takeaways=[
        "2026 100% rate: $3,831/month for a single veteran ($4,044 with spouse).",
        "Combined ratings use VA 'whole person' math — not addition.",
        "Tinnitus, hearing loss, and back conditions are the top three claims.",
        "You have one year from a decision letter to appeal.",
    ],
    keywords=[
        "va disability cheat sheet", "va benefits cheat sheet",
        "va disability quick guide", "va rating cheat sheet",
        "va disability reference guide",
    ],
    page_type="page",
    sector="va_benefits",
))


_38CFR_BODY = """
<p>The <strong>38 CFR rating schedule</strong> is the official rulebook the VA
uses to assign disability ratings. Found in Title 38 of the Code of Federal
Regulations, Part 4, it contains a diagnostic code (DC) and rating criteria
for every condition. This 2026 guide walks through how the schedule is
organized and how to read it.</p>

<h2>What is 38 CFR Part 4?</h2>
<p>38 CFR Part 4 is the VA Schedule for Rating Disabilities. It groups
conditions by body system and assigns specific percentage ratings to each
condition. Every disability rating decision cites a diagnostic code from this
schedule.</p>

<h2>How 38 CFR Part 4 is organized</h2>
<p>The rating schedule is broken into subparts by body system. Each subpart
covers related conditions.</p>
<ul>
  <li><strong>4.71a</strong> &mdash; Musculoskeletal system (spine, knees, hips,
  shoulders).</li>
  <li><strong>4.85&ndash;4.87</strong> &mdash; Hearing impairment and tinnitus.</li>
  <li><strong>4.88a&ndash;4.89</strong> &mdash; Infectious diseases and immune
  disorders.</li>
  <li><strong>4.97</strong> &mdash; Respiratory system (sleep apnea, asthma,
  COPD).</li>
  <li><strong>4.100&ndash;4.104</strong> &mdash; Cardiovascular system
  (hypertension, heart disease).</li>
  <li><strong>4.110&ndash;4.114</strong> &mdash; Digestive system.</li>
  <li><strong>4.115a&ndash;4.115b</strong> &mdash; Genitourinary system.</li>
  <li><strong>4.118</strong> &mdash; Skin (scars, dermatitis).</li>
  <li><strong>4.119</strong> &mdash; Endocrine (diabetes, thyroid).</li>
  <li><strong>4.120&ndash;4.124a</strong> &mdash; Neurological (migraines,
  seizures, peripheral neuropathy).</li>
  <li><strong>4.130</strong> &mdash; Mental disorders (PTSD, depression,
  anxiety).</li>
  <li><strong>4.150</strong> &mdash; Dental and oral conditions.</li>
</ul>

<h2>How to read a diagnostic code</h2>
<p>Each condition lists rating percentages from low to high. The criteria
describe symptoms or measurements required for each level. The VA assigns the
rating that best fits your worst symptom picture.</p>
<p><strong>Example &mdash; Migraines (DC 8100):</strong></p>
<ul>
  <li><strong>0%</strong> &mdash; less frequent attacks.</li>
  <li><strong>10%</strong> &mdash; prostrating attacks averaging 1 every 2
  months.</li>
  <li><strong>30%</strong> &mdash; prostrating attacks averaging once a month.</li>
  <li><strong>50%</strong> &mdash; very frequent prostrating attacks productive
  of severe economic inadaptability.</li>
</ul>

<h2>Key sections to know</h2>
<ul>
  <li><strong>4.16(a)</strong> &mdash; Schedular
  <a href="/explainers/tdiu-explained/">TDIU</a> criteria.</li>
  <li><strong>4.16(b)</strong> &mdash; Extraschedular TDIU.</li>
  <li><strong>4.25</strong> &mdash; Combined rating table (the &ldquo;VA
  math&rdquo;).</li>
  <li><strong>4.26</strong> &mdash; Bilateral factor for paired limbs.</li>
  <li><strong>4.27</strong> &mdash; Use of diagnostic code numbers.</li>
  <li><strong>4.59</strong> &mdash; Painful motion principle.</li>
</ul>

<h2>Why 38 CFR matters in claims</h2>
<p>VA decision letters cite specific 38 CFR sections. Knowing the rating
criteria helps you:</p>
<ul>
  <li>Spot when the rater used the wrong code.</li>
  <li>Identify symptoms that justify a higher rating.</li>
  <li>Build evidence that targets the next level.</li>
  <li>Argue for a separate rating instead of one combined rating.</li>
</ul>

<h2>How to look up 38 CFR Part 4</h2>
<p>The full rating schedule lives at the
<a href="https://www.ecfr.gov/current/title-38/chapter-I/part-4" target="_blank" rel="noopener noreferrer">Electronic Code of Federal Regulations</a>.
It updates as the VA revises the schedule.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-disability-conditions-list/">VA disability conditions list</a></li>
  <li><a href="/va-disability-percentages/">VA disability percentages explained</a></li>
  <li><a href="/explainers/va-disability-rating-explained/">VA disability rating explained</a></li>
  <li><a href="/explainers/tdiu-explained/">TDIU eligibility and rules</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:38-cfr-rating-schedule",
    canonical_path="/explainers/38-cfr-rating-schedule/",
    title="38 CFR Rating Schedule: The VA Disability Rulebook (2026)",
    h1="38 CFR Part 4: The VA Schedule for Rating Disabilities",
    summary=(
        "38 CFR Part 4 is the VA Schedule for Rating Disabilities. Learn how "
        "it's organized, how to read a diagnostic code, and how to use the "
        "rating criteria to support your claim."
    ),
    body_html=_38CFR_BODY,
    faq=[
        {"question": "What is 38 CFR Part 4?",
         "answer": "38 CFR Part 4 is the VA Schedule for Rating Disabilities. It assigns diagnostic codes and rating percentages to every recognized condition and is cited in every VA decision."},
        {"question": "How do I find my condition in 38 CFR?",
         "answer": "Search the Electronic Code of Federal Regulations under Title 38, Chapter I, Part 4. Conditions are grouped by body system (musculoskeletal, mental health, respiratory, etc.) with diagnostic code numbers."},
        {"question": "What is a diagnostic code?",
         "answer": "A diagnostic code (DC) is a four-digit number that identifies a specific condition in the rating schedule. For example, DC 9411 is PTSD, DC 6260 is tinnitus, and DC 5237 is lumbar strain."},
        {"question": "Why does 38 CFR matter for my claim?",
         "answer": "VA raters use 38 CFR criteria to assign your percentage. Knowing the criteria lets you spot mistakes, target evidence that justifies a higher rating, and argue for separate ratings instead of one combined rating."},
    ],
    takeaways=[
        "38 CFR Part 4 is the VA's official rating rulebook.",
        "Conditions are grouped by body system with specific diagnostic codes.",
        "Each diagnostic code lists percentage ratings and the criteria for each level.",
        "Reading the schedule helps you target evidence to the next higher rating.",
    ],
    keywords=[
        "38 cfr part 4", "38 cfr rating schedule", "va rating schedule",
        "38 cfr 4 rating chart", "va schedule for rating disabilities",
    ],
    page_type="explainer",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 5 — Military Life Insurance cluster (4 pages)
# ---------------------------------------------------------------------------

_SGLI_BODY = """
<p><strong>Servicemembers' Group Life Insurance (SGLI)</strong> is the
low-cost group life insurance every active-duty service member gets
automatically. In 2026, the maximum coverage is <strong>$500,000</strong> for
just $26 per month total &mdash; far less than comparable private term
insurance.</p>

<h2>What is SGLI?</h2>
<p>SGLI is term life insurance offered through the VA to active-duty service
members, Ready Reserve, National Guard, ROTC cadets, and commissioned officers
of the Public Health Service and NOAA. Coverage starts the moment you enter
service.</p>

<h2>SGLI 2026 coverage amounts and premiums</h2>
<p>Premiums are flat per $1,000 of coverage. The 2026 rate is
<strong>$0.05 per $1,000</strong>, or $2.50 per month per $50,000 of coverage.
Every member is also charged a flat <strong>$1.00 per month for TSGLI</strong>
&mdash; traumatic injury protection.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Coverage</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">SGLI premium</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">+ TSGLI</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Total/mo</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">$50,000</td><td style="padding:0.5rem;border:1px solid #ddd;">$2.50</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$3.50</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">$100,000</td><td style="padding:0.5rem;border:1px solid #ddd;">$5.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$6.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">$250,000</td><td style="padding:0.5rem;border:1px solid #ddd;">$12.50</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$13.50</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">$400,000</td><td style="padding:0.5rem;border:1px solid #ddd;">$20.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$21.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>$500,000 (max)</strong></td><td style="padding:0.5rem;border:1px solid #ddd;"><strong>$25.00</strong></td><td style="padding:0.5rem;border:1px solid #ddd;"><strong>$1.00</strong></td><td style="padding:0.5rem;border:1px solid #ddd;"><strong>$26.00</strong></td></tr>
</tbody>
</table>

<h2>SGLI is automatic and easy to change</h2>
<p>You're enrolled automatically at the maximum $500,000 unless you decline or
reduce coverage in writing. Use <strong>SGLI Online Enrollment System (SOES)</strong>
through milConnect to:</p>
<ul>
  <li>Reduce coverage in $50,000 increments.</li>
  <li>Decline coverage entirely.</li>
  <li>Update your beneficiary &mdash; spouse must consent if not named primary.</li>
</ul>

<h2>What happens at separation</h2>
<p>SGLI continues for <strong>120 days free</strong> after you separate. After
that, coverage ends unless you convert it to
<a href="/explainers/vgli-explained/">VGLI</a> or a private policy.</p>

<h2>SGLI family coverage</h2>
<p><strong>FSGLI</strong> covers your spouse (up to $100,000) and dependent
children (free, $10,000 each). Spouse premiums vary by age.</p>

<h2>TSGLI: Traumatic Injury Protection</h2>
<p>TSGLI pays $25,000 to $100,000 lump sum for traumatic injuries like
amputation, paralysis, severe burns, or coma. Coverage is automatic for any
member enrolled in SGLI.</p>

<h2>Tips for using SGLI well</h2>
<ul>
  <li><strong>Don't decline.</strong> $26 a month for $500K coverage is the
  cheapest term insurance you'll ever find.</li>
  <li><strong>Name a beneficiary.</strong> Update annually and after any major
  life event.</li>
  <li><strong>Plan ahead for VGLI.</strong> The conversion window opens at
  separation &mdash; mark your calendar.</li>
  <li><strong>Consider supplemental private insurance.</strong> $500K may not
  be enough for families with young kids and a mortgage.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/vgli-explained/">VGLI after separation</a></li>
  <li><a href="/va-life-insurance/">VA life insurance hub</a></li>
  <li><a href="/explainers/military-life-insurance/">Military life insurance overview</a></li>
</ul>

<p>Manage your SGLI at the
<a href="https://www.va.gov/life-insurance/options-eligibility/sgli/" target="_blank" rel="noopener noreferrer">VA SGLI page</a>.</p>
"""

PAGES.append(_page(
    page_key="explainer:sgli-explained",
    canonical_path="/explainers/sgli-explained/",
    title="SGLI Explained 2026: Coverage, Cost, and How to Use It",
    h1="SGLI: Servicemembers' Group Life Insurance Explained",
    summary=(
        "SGLI is automatic $500,000 term life insurance for active-duty "
        "service members at just $26 per month in 2026. Learn coverage, "
        "premiums, family options, and what happens at separation."
    ),
    body_html=_SGLI_BODY,
    faq=[
        {"question": "How much does SGLI cost in 2026?",
         "answer": "Maximum $500,000 coverage costs $26 per month — $25 for SGLI plus $1 for TSGLI traumatic injury protection. Premiums are $0.05 per $1,000 of coverage."},
        {"question": "Is SGLI automatic?",
         "answer": "Yes. Every active-duty member is enrolled at the $500,000 maximum unless they decline or reduce coverage in writing through the SGLI Online Enrollment System (SOES)."},
        {"question": "What happens to SGLI when I separate?",
         "answer": "SGLI continues for 120 days free after separation. After that it ends unless you convert it to VGLI within the application window."},
        {"question": "Does SGLI cover my family?",
         "answer": "FSGLI covers your spouse for up to $100,000 (paid premium) and each dependent child for $10,000 (free). Spouse premiums vary by age."},
    ],
    takeaways=[
        "SGLI is automatic $500,000 coverage for $26/month total in 2026.",
        "Premiums are $0.05 per $1,000 of coverage plus $1 flat for TSGLI.",
        "Coverage continues 120 days after separation, then ends.",
        "FSGLI covers spouses (paid) and children (free) too.",
    ],
    keywords=[
        "sgli", "sgli explained", "servicemembers group life insurance",
        "sgli 2026", "sgli coverage", "tsgli",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_VGLI_BODY = """
<p><strong>Veterans' Group Life Insurance (VGLI)</strong> lets you keep your
SGLI coverage after separation &mdash; up to $500,000 in 2026. It's the only
post-service VA life insurance available to all veterans, no medical exam
required if you apply within 240 days.</p>

<h2>What is VGLI?</h2>
<p>VGLI is renewable term life insurance offered through the VA to separating
service members. It's a continuation of SGLI but with age-based premiums and
coverage you choose in $10,000 increments up to $500,000.</p>

<h2>VGLI application windows</h2>
<p>You have <strong>1 year and 120 days (485 days total)</strong> after
separation to apply for VGLI. Two windows decide whether you need a medical
exam.</p>
<ul>
  <li><strong>First 240 days</strong> &mdash; guaranteed acceptance, no medical
  exam, no health questions.</li>
  <li><strong>Day 241 through day 485</strong> &mdash; medical underwriting
  required. You can be denied based on health.</li>
</ul>
<p><strong>Tip:</strong> If you have any health issues, apply during the first
240 days while acceptance is guaranteed.</p>

<h2>VGLI 2026 monthly premiums (at $400,000 coverage)</h2>
<p>Premiums rise with age in 5-year brackets. The chart below shows monthly
costs for $400,000 of coverage. Premiums are per $10,000 of coverage.</p>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Age</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Per $10,000</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">$400,000/mo</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Under 30</td><td style="padding:0.5rem;border:1px solid #ddd;">$0.60</td><td style="padding:0.5rem;border:1px solid #ddd;">$24.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">30–34</td><td style="padding:0.5rem;border:1px solid #ddd;">$0.80</td><td style="padding:0.5rem;border:1px solid #ddd;">$32.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">35–39</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$40.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">40–44</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.40</td><td style="padding:0.5rem;border:1px solid #ddd;">$56.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">45–49</td><td style="padding:0.5rem;border:1px solid #ddd;">$1.90</td><td style="padding:0.5rem;border:1px solid #ddd;">$76.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">50–54</td><td style="padding:0.5rem;border:1px solid #ddd;">$2.90</td><td style="padding:0.5rem;border:1px solid #ddd;">$116.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">55–59</td><td style="padding:0.5rem;border:1px solid #ddd;">$5.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$200.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">60–64</td><td style="padding:0.5rem;border:1px solid #ddd;">$8.50</td><td style="padding:0.5rem;border:1px solid #ddd;">$340.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">65–69</td><td style="padding:0.5rem;border:1px solid #ddd;">$13.80</td><td style="padding:0.5rem;border:1px solid #ddd;">$552.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">70–74</td><td style="padding:0.5rem;border:1px solid #ddd;">$21.50</td><td style="padding:0.5rem;border:1px solid #ddd;">$860.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">75–79</td><td style="padding:0.5rem;border:1px solid #ddd;">$38.50</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,540.00</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">80+</td><td style="padding:0.5rem;border:1px solid #ddd;">$44.00</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,760.00</td></tr>
</tbody>
</table>

<h2>VGLI vs. private term life</h2>
<p>For young veterans in good health, private term policies often cost less than
VGLI. For older veterans or those with health issues, VGLI's guaranteed
acceptance during the first 240 days makes it the most affordable option.</p>

<h2>Tips for VGLI</h2>
<ul>
  <li><strong>Apply in the no-exam window.</strong> Even if you don't need it
  long term, lock in coverage during the first 240 days.</li>
  <li><strong>Compare with private quotes.</strong> Healthy younger veterans
  often save money with a private 20-year level term policy.</li>
  <li><strong>You can reduce coverage</strong> in $10,000 steps to lower your
  premium as you age.</li>
  <li><strong>Beneficiary updates</strong> matter &mdash; review annually.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/sgli-explained/">SGLI explained &mdash; active-duty coverage</a></li>
  <li><a href="/va-life-insurance/">VA life insurance options hub</a></li>
  <li><a href="/explainers/military-life-insurance/">Military life insurance overview</a></li>
</ul>

<p>Apply for VGLI at the
<a href="https://www.va.gov/life-insurance/options-eligibility/vgli/" target="_blank" rel="noopener noreferrer">VA VGLI page</a>.</p>
"""

PAGES.append(_page(
    page_key="explainer:vgli-explained",
    canonical_path="/explainers/vgli-explained/",
    title="VGLI Explained 2026: Coverage, Cost, and How to Convert",
    h1="VGLI: Veterans' Group Life Insurance Explained",
    summary=(
        "VGLI lets veterans keep SGLI-style coverage after separation — up to "
        "$500,000. Apply within 240 days for guaranteed acceptance. See 2026 "
        "age-based premiums and tips."
    ),
    body_html=_VGLI_BODY,
    faq=[
        {"question": "How long do I have to apply for VGLI?",
         "answer": "You have 1 year and 120 days (485 days total) after separation. The first 240 days allow guaranteed acceptance with no medical exam. After that, you must pass medical underwriting."},
        {"question": "How much does VGLI cost in 2026?",
         "answer": "Premiums depend on age and coverage amount. Under age 30, $400,000 coverage costs $24/month. Ages 40-44 pay $56/month. Ages 60-64 pay $340/month for the same coverage."},
        {"question": "Is VGLI a good deal?",
         "answer": "It depends. Young healthy veterans often save money with private term insurance. Older veterans or those with health issues benefit from VGLI's guaranteed acceptance during the first 240 days after separation."},
        {"question": "Can I reduce my VGLI coverage later?",
         "answer": "Yes. You can reduce coverage in $10,000 increments to lower premiums as you age. You cannot increase coverage after the initial application without medical underwriting."},
    ],
    takeaways=[
        "VGLI continues SGLI coverage post-separation up to $500,000.",
        "Apply within 240 days for guaranteed acceptance — no medical exam.",
        "Premiums rise with age: $24/mo under 30, $340/mo at age 60 for $400K.",
        "Compare with private term life — healthy young veterans often save with private.",
    ],
    keywords=[
        "vgli", "vgli explained", "veterans group life insurance",
        "vgli 2026", "vgli premiums", "sgli to vgli", "vgli rates",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_VA_LIFE_INSURANCE_BODY = """
<p>The VA offers several life insurance programs for service members, veterans,
and their families. This 2026 guide compares your options &mdash; from
automatic <a href="/explainers/sgli-explained/">SGLI</a> coverage on active duty
to <a href="/explainers/vgli-explained/">VGLI</a> after separation, plus VALife
for disabled veterans.</p>

<h2>VA life insurance programs at a glance</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Program</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Who qualifies</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Max coverage</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/explainers/sgli-explained/">SGLI</a></td><td style="padding:0.5rem;border:1px solid #ddd;">Active duty, Reserve, Guard</td><td style="padding:0.5rem;border:1px solid #ddd;">$500,000</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">FSGLI</td><td style="padding:0.5rem;border:1px solid #ddd;">Spouse/children of SGLI members</td><td style="padding:0.5rem;border:1px solid #ddd;">$100K spouse / $10K child</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">TSGLI</td><td style="padding:0.5rem;border:1px solid #ddd;">SGLI-insured w/ traumatic injury</td><td style="padding:0.5rem;border:1px solid #ddd;">$25K–$100K lump sum</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/explainers/vgli-explained/">VGLI</a></td><td style="padding:0.5rem;border:1px solid #ddd;">Separating service members</td><td style="padding:0.5rem;border:1px solid #ddd;">$500,000</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">VALife</td><td style="padding:0.5rem;border:1px solid #ddd;">Veterans 0–80, any rated disability</td><td style="padding:0.5rem;border:1px solid #ddd;">$40,000 (whole life)</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">S-DVI (closed to new)</td><td style="padding:0.5rem;border:1px solid #ddd;">Pre-2023 disabled vets</td><td style="padding:0.5rem;border:1px solid #ddd;">$10,000</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">VMLI</td><td style="padding:0.5rem;border:1px solid #ddd;">Vets w/ SAH grant</td><td style="padding:0.5rem;border:1px solid #ddd;">$200,000</td></tr>
</tbody>
</table>

<h2>SGLI: Active-duty coverage</h2>
<p><a href="/explainers/sgli-explained/">SGLI</a> covers active service members
automatically at $500,000 for just $26 per month. Coverage extends 120 days
after separation. Read the full
<a href="/explainers/sgli-explained/">SGLI guide</a> for premium tables.</p>

<h2>VGLI: Post-separation term coverage</h2>
<p><a href="/explainers/vgli-explained/">VGLI</a> continues SGLI-style term
coverage after separation. Apply within 240 days for guaranteed acceptance.
Premiums rise with age &mdash; younger veterans often save with private term.</p>

<h2>VALife: For service-connected veterans</h2>
<p><strong>VALife</strong> launched in 2023 as the new whole-life policy for
veterans with any VA disability rating from 0% to 100%. Key features:</p>
<ul>
  <li>Up to <strong>$40,000</strong> in whole-life coverage.</li>
  <li>Guaranteed acceptance regardless of health.</li>
  <li>Available to any veteran <strong>under age 81</strong> with a
  service-connected rating.</li>
  <li><strong>2-year waiting period</strong> before full death benefit pays out.
  Premiums during that time are returned plus interest if you pass away.</li>
</ul>

<h2>VMLI: Mortgage protection for SAH grant recipients</h2>
<p><strong>Veterans' Mortgage Life Insurance (VMLI)</strong> pays off your
mortgage if you die. You qualify if you received a Specially Adapted Housing
(SAH) grant. Coverage maxes at $200,000.</p>

<h2>Service-Disabled Veterans Insurance (S-DVI)</h2>
<p>S-DVI is <strong>closed to new applications</strong> as of January 1, 2023.
VALife replaced it. Existing S-DVI policies remain in force.</p>

<h2>Which VA life insurance is right for you?</h2>
<ul>
  <li><strong>On active duty?</strong> Keep your full $500K SGLI.</li>
  <li><strong>Separating soon?</strong> Apply for VGLI within 240 days
  &mdash; or compare with private term life.</li>
  <li><strong>Service-connected disability?</strong> Add VALife for guaranteed
  $40K of whole-life coverage.</li>
  <li><strong>Received an SAH grant?</strong> Apply for VMLI to protect your
  mortgage.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/sgli-explained/">SGLI explained</a></li>
  <li><a href="/explainers/vgli-explained/">VGLI explained</a></li>
  <li><a href="/explainers/military-life-insurance/">Military life insurance overview</a></li>
  <li><a href="/explainers/100-percent-va-disability-benefits/">100% VA disability benefits</a></li>
</ul>

<p>Compare programs at the
<a href="https://www.va.gov/life-insurance/" target="_blank" rel="noopener noreferrer">VA life insurance hub</a>.</p>
"""

PAGES.append(_page(
    page_key="page:va-life-insurance",
    canonical_path="/va-life-insurance/",
    title="VA Life Insurance 2026: SGLI, VGLI, VALife Compared",
    h1="VA Life Insurance: Compare SGLI, VGLI, VALife, and VMLI",
    summary=(
        "Compare every VA life insurance program in 2026: SGLI on active duty, "
        "VGLI after separation, VALife for disabled veterans, and VMLI for "
        "mortgage protection."
    ),
    body_html=_VA_LIFE_INSURANCE_BODY,
    faq=[
        {"question": "What VA life insurance programs exist?",
         "answer": "The VA offers SGLI (active duty), FSGLI (family), TSGLI (traumatic injury), VGLI (after separation), VALife (service-connected disabled), VMLI (SAH grant recipients), and legacy S-DVI policies."},
        {"question": "What is VALife?",
         "answer": "VALife is the new VA whole-life insurance program that launched in 2023. It offers up to $40,000 of coverage with guaranteed acceptance for any veteran with a service-connected rating, under age 81. There is a 2-year waiting period for the full death benefit."},
        {"question": "Is S-DVI still available?",
         "answer": "No. S-DVI closed to new applications on January 1, 2023. VALife replaced it. Existing S-DVI policies remain in force for current holders."},
        {"question": "Which VA life insurance is best?",
         "answer": "It depends on your status. Keep SGLI on active duty. Convert to VGLI at separation if you can't qualify for private term. Add VALife if you have a service-connected disability. Use VMLI to protect a SAH-funded mortgage."},
    ],
    takeaways=[
        "SGLI covers active-duty members automatically at $500,000.",
        "VGLI continues coverage post-separation — apply in 240 days for no exam.",
        "VALife offers $40K whole-life coverage to any service-connected veteran.",
        "VMLI pays off your mortgage if you received an SAH grant.",
    ],
    keywords=[
        "va life insurance", "veterans life insurance", "sgli vs vgli",
        "valife insurance", "vmli", "va life insurance options",
    ],
    page_type="page",
    sector="va_benefits",
))


_MIL_LIFE_BODY = """
<p><strong>Military life insurance</strong> covers active-duty service members,
veterans, and their families. The VA-administered programs &mdash; SGLI, VGLI,
VALife, and others &mdash; offer guaranteed-acceptance options that private
insurers can't always match. This 2026 guide explains your options and how
they compare with private term insurance.</p>

<h2>What military life insurance covers</h2>
<p>Military life insurance pays a death benefit to your beneficiaries if you
die. Coverage starts on active duty (SGLI), continues into separation (VGLI),
and includes specialized options for disabled veterans (VALife, VMLI).</p>

<h2>The four main programs</h2>
<ol>
  <li><strong><a href="/explainers/sgli-explained/">SGLI</a></strong>
  &mdash; automatic for active-duty members at $500,000 for $26/month.</li>
  <li><strong><a href="/explainers/vgli-explained/">VGLI</a></strong>
  &mdash; post-separation term, up to $500,000, age-based premiums.</li>
  <li><strong>VALife</strong> &mdash; whole-life coverage up to $40,000 for
  service-connected veterans.</li>
  <li><strong>VMLI</strong> &mdash; mortgage protection for SAH grant
  recipients, up to $200,000.</li>
</ol>

<h2>How military life insurance differs from private</h2>
<p>VA programs have three key advantages over most private policies:</p>
<ul>
  <li><strong>Guaranteed acceptance windows.</strong> SGLI starts automatically.
  VGLI requires no medical exam in the first 240 days.</li>
  <li><strong>Coverage during combat or hazardous duty.</strong> Private
  policies often exclude active war zones or skydiving.</li>
  <li><strong>No medical underwriting for VALife.</strong> Even severely
  disabled veterans get coverage.</li>
</ul>
<p>Private policies often win on cost for young, healthy veterans buying $1
million-plus of coverage.</p>

<h2>How much coverage do you need?</h2>
<p>A common rule of thumb is <strong>10–12x your annual income</strong>, plus
any debts (mortgage, car, student loans), plus estimated college costs for
children. A young service member with $80K income, a $300K mortgage, and two
kids might need <strong>$1 million</strong> total. The $500K SGLI cap doesn't
always cover it &mdash; private supplemental term insurance fills the gap.</p>

<h2>Choosing beneficiaries</h2>
<p>Update your beneficiary after every major life event &mdash; marriage,
divorce, new child, death of a loved one. SGLI and VGLI default to a
&ldquo;by law&rdquo; order of survivors if no beneficiary is named, but you
should always name your beneficiary in writing.</p>

<h2>Common military life insurance mistakes</h2>
<ul>
  <li><strong>Declining SGLI to save $26/month.</strong> The cost is trivial
  compared to the coverage.</li>
  <li><strong>Missing the VGLI no-exam window.</strong> Apply within 240 days
  of separation.</li>
  <li><strong>Forgetting to add private supplemental coverage.</strong> $500K
  may not be enough for families.</li>
  <li><strong>Failing to update beneficiaries.</strong> Old beneficiaries
  (ex-spouses, deceased parents) cause delays at the worst time.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-life-insurance/">VA life insurance hub</a></li>
  <li><a href="/explainers/sgli-explained/">SGLI explained</a></li>
  <li><a href="/explainers/vgli-explained/">VGLI explained</a></li>
</ul>

<p>Learn more at the
<a href="https://www.va.gov/life-insurance/" target="_blank" rel="noopener noreferrer">VA life insurance hub</a>.</p>
"""

PAGES.append(_page(
    page_key="explainer:military-life-insurance",
    canonical_path="/explainers/military-life-insurance/",
    title="Military Life Insurance 2026: Programs and Coverage Guide",
    h1="Military Life Insurance: Your Complete 2026 Guide",
    summary=(
        "Military life insurance covers service members, veterans, and "
        "families. Compare SGLI, VGLI, VALife, and VMLI and learn how much "
        "coverage you really need."
    ),
    body_html=_MIL_LIFE_BODY,
    faq=[
        {"question": "What is military life insurance?",
         "answer": "Military life insurance is government-backed coverage administered by the VA. It includes SGLI on active duty, VGLI after separation, VALife for disabled veterans, and VMLI for SAH grant recipients."},
        {"question": "How much military life insurance do I need?",
         "answer": "A common rule is 10 to 12 times annual income, plus debts and estimated college costs. A typical young family might need $1 million — more than the $500,000 SGLI cap, so private supplemental term often fills the gap."},
        {"question": "Is military life insurance better than private?",
         "answer": "It depends. Military programs offer guaranteed acceptance and no combat exclusions. Private term is often cheaper for young, healthy members buying large amounts of coverage. Many families use both."},
        {"question": "Does SGLI cover combat deaths?",
         "answer": "Yes. SGLI pays the full death benefit regardless of cause, including combat. Private policies sometimes exclude active war zones — read the policy carefully before relying on it."},
    ],
    takeaways=[
        "The VA runs SGLI, VGLI, VALife, and VMLI for service members and veterans.",
        "Military coverage has no combat exclusion — private policies sometimes do.",
        "A common rule is 10–12x annual income; SGLI's $500K cap may not be enough.",
        "Update beneficiaries after marriage, divorce, or new children.",
    ],
    keywords=[
        "military life insurance", "military life insurance options",
        "military life insurance 2026", "service member life insurance",
        "veteran life insurance",
    ],
    page_type="explainer",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 7 — DIC & Survivor Benefits cluster (3 pages)
# ---------------------------------------------------------------------------

_DIC_BENEFITS_BODY = """
<p><strong>Dependency and Indemnity Compensation (DIC)</strong> is a tax-free
monthly benefit paid to surviving spouses, children, and parents of veterans
who died from a service-connected condition or a service-related cause. In
2026, the base DIC rate for a surviving spouse is
<strong>$1,699.36 per month</strong> &mdash; up 2.8% from 2025 thanks to the
December 2025 COLA.</p>

<h2>What is DIC?</h2>
<p>DIC is the VA's survivor compensation program. It replaces some of the
income lost when a veteran dies in service or from a service-connected
condition. DIC is separate from Social Security survivor benefits and the
Survivor Benefit Plan (SBP).</p>

<h2>2026 DIC rates for surviving spouses</h2>
<ul>
  <li><strong>Base monthly rate:</strong> $1,699.36</li>
  <li><strong>8-year add-on</strong> (veteran rated totally disabled for 8+
  years before death, married 8+ years): +$360.85</li>
  <li><strong>Each dependent child under 18:</strong> +$421.00</li>
  <li><strong>Aid &amp; Attendance allowance:</strong> +$421.00</li>
  <li><strong>Housebound allowance:</strong> +$197.22</li>
  <li><strong>Each helpless child over 18:</strong> +$421.00</li>
</ul>

<h2>DIC eligibility for surviving spouses</h2>
<p>You qualify for DIC if your spouse:</p>
<ul>
  <li>Died on active duty, active duty for training, or inactive duty
  training.</li>
  <li>Died from a service-connected disability or injury.</li>
  <li>Was rated <strong>totally disabled</strong> (100% schedular or
  <a href="/explainers/tdiu-explained/">TDIU</a>) for at least 10 years before
  death.</li>
  <li>Was rated totally disabled for at least 5 years immediately after
  separation.</li>
  <li>Was a former POW who died after September 30, 1999, with a 1-year
  total-rating period.</li>
</ul>

<h2>DIC for surviving children</h2>
<p>Children under 18 (or 23 if in school) may receive DIC if the surviving
parent doesn't qualify or has remarried. Helpless adult children (disabled
before age 18) receive lifetime DIC.</p>

<h2>DIC for surviving parents</h2>
<p>Parents' DIC is income-based and varies by relationship status. The 2026
maximum parents' DIC ranges from about $704 to $1,400 per month with
income-based reductions of $0.08 per $1 of income above thresholds.</p>

<h2>How to apply for DIC</h2>
<ol>
  <li>File <strong>VA Form 21P-534EZ</strong> &mdash; the survivor benefits
  application.</li>
  <li>Attach the veteran's death certificate.</li>
  <li>Include a copy of your marriage certificate and the veteran's DD-214.</li>
  <li>Submit medical evidence linking the cause of death to a service-connected
  condition, if applicable.</li>
  <li>Submit through VA.gov, by mail, or with a Veterans Service Officer.</li>
</ol>

<h2>DIC and other survivor benefits</h2>
<p>DIC can be combined with other benefits, with some offsets:</p>
<ul>
  <li><strong>Social Security survivor benefits</strong> &mdash; paid in full
  alongside DIC.</li>
  <li><strong>SBP (Survivor Benefit Plan)</strong> &mdash; the 2023
  &ldquo;widow's tax&rdquo; repeal eliminated the SBP-DIC offset. Surviving
  spouses now receive both in full.</li>
  <li><strong>Survivors Pension</strong> &mdash; cannot be paid concurrently
  with DIC. The VA pays whichever is higher.</li>
</ul>

<h2>Special monthly DIC</h2>
<p>Surviving spouses with serious disabilities may qualify for Aid &amp;
Attendance (+$421) or Housebound (+$197) allowances on top of the base rate.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-survivor-benefits/">VA survivor benefits hub</a></li>
  <li><a href="/va-survivor-benefits/dic-vs-sbp/">DIC vs. SBP comparison</a></li>
  <li><a href="/explainers/100-percent-va-disability-benefits/">100% VA disability benefits</a></li>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA claim</a></li>
</ul>

<p>Apply at the
<a href="https://www.va.gov/burials-memorials/dependency-indemnity-compensation/" target="_blank" rel="noopener noreferrer">VA DIC page</a>.</p>
"""

PAGES.append(_page(
    page_key="page:dic-benefits",
    canonical_path="/dic-benefits/",
    title="DIC Benefits 2026: $1,699/mo for VA Surviving Spouses",
    h1="DIC Benefits: Dependency and Indemnity Compensation for Surviving Families",
    summary=(
        "DIC pays surviving spouses $1,699.36 per month tax-free in 2026 plus "
        "child and aid allowances. See eligibility rules, current rates, and "
        "how to apply for VA survivor compensation."
    ),
    body_html=_DIC_BENEFITS_BODY,
    faq=[
        {"question": "How much is DIC in 2026?",
         "answer": "The 2026 base DIC rate for a surviving spouse is $1,699.36 per month, tax-free. Add-ons include $421 per dependent child, $421 for Aid and Attendance, and $197 for Housebound allowance."},
        {"question": "Who qualifies for DIC?",
         "answer": "Surviving spouses, children, and dependent parents of veterans who died on active duty, from a service-connected condition, or who were rated totally disabled for 10+ years before death."},
        {"question": "Can I receive both DIC and SBP?",
         "answer": "Yes. The 2023 'widow's tax' repeal eliminated the SBP-DIC offset. Surviving spouses now receive both benefits in full without reduction."},
        {"question": "How do I apply for DIC?",
         "answer": "File VA Form 21P-534EZ with the veteran's death certificate, marriage certificate, DD-214, and any evidence linking cause of death to service. Submit at VA.gov, by mail, or through a VSO."},
    ],
    takeaways=[
        "2026 DIC base rate: $1,699.36/month tax-free for a surviving spouse.",
        "Add-ons available: $421/child, $421 Aid & Attendance, $197 Housebound.",
        "The 2023 'widow's tax' repeal lets spouses collect DIC and SBP in full.",
        "Apply with VA Form 21P-534EZ and the veteran's death certificate.",
    ],
    keywords=[
        "dic benefits", "dic benefits veterans", "dependency and indemnity compensation",
        "dic rates 2026", "va survivor benefits", "va widow benefits",
    ],
    page_type="page",
    sector="va_benefits",
))


_SURVIVOR_BENEFITS_BODY = """
<p><strong>VA survivor benefits</strong> include cash compensation, healthcare,
education, and home loan benefits for the families of deceased veterans. This
2026 hub explains every program available to surviving spouses, children, and
parents.</p>

<h2>Cash benefits for survivors</h2>
<ul>
  <li><strong><a href="/dic-benefits/">DIC (Dependency and Indemnity
  Compensation)</a></strong> &mdash; $1,699.36/month base rate in 2026 for
  service-connected deaths.</li>
  <li><strong>Survivors Pension</strong> &mdash; income-based monthly benefit
  for low-income surviving spouses and children of wartime veterans.</li>
  <li><strong>Accrued benefits</strong> &mdash; unpaid VA benefits the veteran
  was entitled to before death.</li>
  <li><strong>Burial allowance</strong> &mdash; up to $2,000 for service-
  connected death, $796 for non-service-connected.</li>
</ul>

<h2>Survivor Benefit Plan (SBP)</h2>
<p>SBP is a military retirement annuity option, not a VA benefit. Retirees pay
into SBP from their retirement pay so that 55% continues to a surviving spouse.
Since 2023, SBP and DIC can both be paid in full &mdash; the
&ldquo;widow's tax&rdquo; offset is gone.</p>

<h2>Healthcare for survivors</h2>
<ul>
  <li><strong>CHAMPVA</strong> &mdash; covers spouses and children of veterans
  who died from a service-connected condition, or were rated permanently 100%
  before death. Free healthcare for eligible survivors.</li>
  <li><strong>Tricare Survivor</strong> &mdash; available to spouses and
  children of service members who died on active duty.</li>
</ul>

<h2>Education benefits for survivors</h2>
<ul>
  <li><strong>Chapter 35 / DEA</strong> &mdash; up to 36 months of education
  benefits for spouses and children of permanently disabled or deceased
  veterans. Pays about $1,574/month full-time in 2026.</li>
  <li><strong>Fry Scholarship</strong> &mdash; Post-9/11 GI Bill-style benefits
  for survivors of service members who died in the line of duty after
  9/11/2001. Pays tuition plus MHA.</li>
</ul>

<h2>Home loan benefits</h2>
<p>Surviving spouses of veterans who died from a service-connected condition
may qualify for the <a href="/va-benefits/va-home-loan/">VA home loan</a>
guaranty &mdash; same terms as the veteran would receive.</p>

<h2>Burial and memorial benefits</h2>
<ul>
  <li>Free burial in a VA national cemetery.</li>
  <li>Headstone or marker.</li>
  <li>Burial flag.</li>
  <li>Presidential Memorial Certificate.</li>
  <li>Up to $948 in plot/interment allowance.</li>
</ul>

<h2>How to apply for VA survivor benefits</h2>
<ol>
  <li><strong>Notify the VA</strong> of the veteran's death.</li>
  <li>File <strong>VA Form 21P-534EZ</strong> for DIC, Pension, or accrued
  benefits.</li>
  <li>Apply for <strong>CHAMPVA</strong> via VA Form 10-10d.</li>
  <li>Apply for Chapter 35 education benefits via VA Form 22-5490.</li>
  <li>Apply for VA home loan COE via VA Form 26-1817.</li>
</ol>

<h2>Compare survivor benefits</h2>
<ul>
  <li><a href="/dic-benefits/">DIC in detail &mdash; rates and eligibility</a></li>
  <li><a href="/va-survivor-benefits/dic-vs-sbp/">DIC vs. SBP comparison</a></li>
  <li><a href="/explainers/100-percent-disabled-veteran-benefits-by-state/">State benefits for survivors</a></li>
</ul>

<p>Start at the
<a href="https://www.va.gov/family-and-caregiver-benefits/survivor-compensation/" target="_blank" rel="noopener noreferrer">VA survivor benefits hub</a>.</p>
"""

PAGES.append(_page(
    page_key="page:va-survivor-benefits",
    canonical_path="/va-survivor-benefits/",
    title="VA Survivor Benefits 2026: Complete Guide for Families",
    h1="VA Survivor Benefits: Compensation, Healthcare, and Education",
    summary=(
        "Every VA survivor benefit in 2026: DIC compensation, Survivors "
        "Pension, CHAMPVA healthcare, Chapter 35 education, VA home loans, "
        "and burial benefits."
    ),
    body_html=_SURVIVOR_BENEFITS_BODY,
    faq=[
        {"question": "What are VA survivor benefits?",
         "answer": "VA survivor benefits include DIC monthly compensation, Survivors Pension, CHAMPVA healthcare, Chapter 35/Fry Scholarship education benefits, VA home loan eligibility, and burial benefits for families of deceased veterans."},
        {"question": "Who qualifies for VA survivor benefits?",
         "answer": "Surviving spouses, dependent children, and dependent parents of veterans who died on active duty, from service-connected conditions, or were rated totally disabled for required periods before death."},
        {"question": "Can a surviving spouse use the VA home loan?",
         "answer": "Yes. Surviving spouses of veterans who died from a service-connected condition qualify for the VA home loan guaranty on the same terms as the veteran would receive. Apply with VA Form 26-1817."},
        {"question": "What healthcare do VA survivors get?",
         "answer": "CHAMPVA provides free healthcare to surviving spouses and children of veterans who died from a service-connected condition or were permanently 100% disabled. Active-duty survivors qualify for Tricare instead."},
    ],
    takeaways=[
        "DIC pays $1,699.36/month in 2026 — the main VA survivor cash benefit.",
        "CHAMPVA covers healthcare for spouses and children of service-connected deaths.",
        "Chapter 35 (DEA) and the Fry Scholarship cover survivor education.",
        "Surviving spouses of service-connected deaths qualify for the VA home loan.",
    ],
    keywords=[
        "va survivor benefits", "veterans survivor benefits", "va widow benefits",
        "champva", "chapter 35 dea", "fry scholarship", "survivor benefits 2026",
    ],
    page_type="page",
    sector="va_benefits",
))


_DIC_VS_SBP_BODY = """
<p><strong>DIC vs. SBP</strong> is one of the most-asked questions for
surviving military spouses. They're separate programs with different rules,
funding sources, and tax treatment. Since the 2023 &ldquo;widow's tax&rdquo;
repeal, eligible spouses can receive both in full.</p>

<h2>DIC vs. SBP at a glance</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Feature</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">DIC</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">SBP</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Run by</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">VA</td><td style="padding:0.5rem;border:1px solid #ddd;">DoD/DFAS</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Funded by</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Tax-free VA benefit</td><td style="padding:0.5rem;border:1px solid #ddd;">Retiree's contributions from pay</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>2026 amount</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">$1,699.36/mo base + add-ons</td><td style="padding:0.5rem;border:1px solid #ddd;">Up to 55% of retired pay</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Taxes</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Tax-free</td><td style="padding:0.5rem;border:1px solid #ddd;">Taxable income</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Who qualifies</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Survivors of service-connected death</td><td style="padding:0.5rem;border:1px solid #ddd;">Survivors of SBP enrollees</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Concurrent receipt</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (since 2023)</td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (since 2023)</td></tr>
</tbody>
</table>

<h2>What is DIC?</h2>
<p><a href="/dic-benefits/">DIC</a> is a tax-free VA benefit paid to surviving
spouses, children, and parents of veterans who died from a service-connected
cause. The 2026 base rate is $1,699.36 per month.</p>

<h2>What is SBP?</h2>
<p>SBP is a military retirement annuity option. Retirees pay a premium
(6.5% of covered base) so that 55% of their retired pay continues to a
surviving spouse. SBP is taxable as income.</p>

<h2>The 2023 &ldquo;widow's tax&rdquo; repeal</h2>
<p>Before 2023, SBP was offset dollar-for-dollar by DIC. Many surviving spouses
received only SBP &mdash; the DIC offset wiped out the rest. Congress phased
out the offset between 2021 and 2023.</p>
<p>Starting <strong>January 1, 2023</strong>, surviving spouses receive both
SBP and DIC in full. This change increased typical survivor income by
$1,500&ndash;$2,500 per month.</p>

<h2>When you might qualify for one but not the other</h2>
<ul>
  <li><strong>DIC only:</strong> Veteran died in service or from a
  service-connected condition before retirement; never enrolled in SBP.</li>
  <li><strong>SBP only:</strong> Retiree died from a non-service-connected
  cause and wasn't rated totally disabled long enough.</li>
  <li><strong>Both:</strong> Retiree enrolled in SBP and died from a
  service-connected cause &mdash; spouse receives DIC plus 55% SBP.</li>
</ul>

<h2>How DIC and SBP affect each other now</h2>
<p>They don't &mdash; since the 2023 repeal. The SBP premium refund (Special
Survivor Indemnity Allowance) ended in 2023 because spouses now receive both
benefits in full.</p>

<h2>How to apply</h2>
<ol>
  <li><strong>For DIC:</strong> File VA Form 21P-534EZ with the VA.</li>
  <li><strong>For SBP:</strong> Notify DFAS using DD Form 2656-7.</li>
  <li>Apply for both as soon as possible &mdash; benefits aren't retroactive
  beyond one year from filing.</li>
</ol>

<h2>Related guides</h2>
<ul>
  <li><a href="/dic-benefits/">DIC benefits in full detail</a></li>
  <li><a href="/va-survivor-benefits/">VA survivor benefits hub</a></li>
  <li><a href="/military-retirement/survivor-benefit-plan/">Military SBP overview</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="page:va-survivor-benefits-dic-vs-sbp",
    canonical_path="/va-survivor-benefits/dic-vs-sbp/",
    title="DIC vs. SBP 2026: Compare Both VA Survivor Benefits",
    h1="DIC vs. SBP: How to Maximize Survivor Benefits",
    summary=(
        "DIC vs. SBP for surviving military spouses. Compare both programs, "
        "see how the 2023 widow's tax repeal lets you collect both in full, "
        "and learn how to apply."
    ),
    body_html=_DIC_VS_SBP_BODY,
    faq=[
        {"question": "What's the difference between DIC and SBP?",
         "answer": "DIC is a tax-free VA benefit for survivors of service-connected deaths. SBP is a taxable military annuity funded by retiree contributions. They're administered by different agencies (VA vs. DoD/DFAS)."},
        {"question": "Can I receive both DIC and SBP?",
         "answer": "Yes. The 2023 widow's tax repeal eliminated the DIC-SBP offset. Eligible surviving spouses now receive both benefits in full without reduction."},
        {"question": "Which pays more, DIC or SBP?",
         "answer": "It depends. DIC's 2026 base rate is $1,699.36 tax-free. SBP pays up to 55% of the retiree's covered base — often higher for senior officers. Many survivors qualify for both."},
        {"question": "Do DIC and SBP affect each other?",
         "answer": "Not anymore. Before 2023, SBP was reduced dollar-for-dollar by DIC. Since January 1, 2023, both benefits are paid in full to eligible surviving spouses."},
    ],
    takeaways=[
        "DIC is tax-free; SBP is taxable income.",
        "Since 2023, surviving spouses can receive both DIC and SBP in full.",
        "DIC pays $1,699.36/mo base; SBP pays up to 55% of retiree's covered base.",
        "Apply for DIC via VA Form 21P-534EZ; SBP via DFAS Form 2656-7.",
    ],
    keywords=[
        "dic vs sbp", "dic and sbp", "widow tax repeal",
        "survivor benefit plan vs dic", "va dic sbp",
    ],
    page_type="page",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 8 — TDIU Expansion cluster (3 pages)
# ---------------------------------------------------------------------------

_TDIU_BENEFITS_BODY = """
<p><strong>TDIU benefits</strong> go beyond the monthly check. Veterans approved
for Total Disability based on Individual Unemployability receive VA disability
at the 100% rate &mdash; about $3,938 a month tax-free in 2026 &mdash; plus
access to many of the same benefits available to schedular 100% veterans.</p>

<h2>What you get with TDIU</h2>

<h3>Cash benefits</h3>
<ul>
  <li><strong>Monthly compensation at the 100% rate.</strong> $3,831.30 for a
  single veteran (Dec 2025 COLA-adjusted), more with dependents.</li>
  <li><strong>Tax-free income.</strong> Like all VA disability, TDIU pay isn't
  taxed federally or by most states.</li>
  <li><strong>Concurrent receipt</strong> for military retirees rated 50%+
  combined &mdash; you keep both VA pay and military retirement.</li>
</ul>

<h3>Healthcare</h3>
<ul>
  <li><strong>VA Priority Group 1</strong> &mdash; free care for all
  conditions.</li>
  <li><strong>CHAMPVA for dependents</strong> &mdash; if rated permanent &amp;
  total (P&amp;T).</li>
  <li><strong>Free VA dental care</strong> for service-connected dental
  conditions.</li>
</ul>

<h3>Education benefits for family</h3>
<ul>
  <li><strong>Chapter 35 / DEA</strong> &mdash; up to 36 months of education
  benefits for spouse and dependent children, but only if rated
  permanent &amp; total.</li>
</ul>

<h3>Housing</h3>
<ul>
  <li><strong>Property tax exemptions</strong> in many states &mdash; varies
  by state.</li>
  <li><strong>Specially Adapted Housing (SAH) grant</strong> &mdash; up to
  $117,014 in 2026 for severely disabled veterans.</li>
  <li><strong>VA home loan</strong> with no funding fee.</li>
</ul>

<h3>State and local benefits</h3>
<p>22 states give full property tax exemptions to 100% disabled veterans &mdash;
TDIU recipients qualify in most of them. See the
<a href="/explainers/100-percent-disabled-veteran-benefits-by-state/">full state benefits guide</a>.</p>

<h3>Commissary, exchange, and MWR access</h3>
<p>All VA-rated permanent &amp; total veterans (including TDIU P&amp;T)
qualify for unlimited commissary, exchange, and MWR base access.</p>

<h2>TDIU vs. schedular 100% benefits</h2>
<p>Most benefits are the same. Two key differences:</p>
<ul>
  <li><strong>Chapter 35 education</strong> for family requires P&amp;T status.
  Some TDIU ratings aren't marked P&amp;T.</li>
  <li><strong>Earned income limits.</strong> TDIU recipients must stay below
  substantially gainful employment (~$15,960 in 2026). Schedular 100% veterans
  can earn any amount.</li>
</ul>

<h2>Income rules for TDIU recipients</h2>
<p>You can still earn money on TDIU &mdash; but only up to the federal poverty
threshold for a single person (~$15,960 in 2026). Exceptions:</p>
<ul>
  <li><strong>Marginal employment</strong> &mdash; earning below the poverty
  line.</li>
  <li><strong>Protected work environment</strong> &mdash; sheltered, family
  business, or significantly accommodated work doesn't count.</li>
</ul>

<h2>How to apply for TDIU benefits</h2>
<ol>
  <li>File <a href="/va-forms/21-8940/">VA Form 21-8940</a>.</li>
  <li>Include treatment records and a vocational expert opinion if possible.</li>
  <li>Submit lay statements about how conditions limit work.</li>
  <li>Wait for the VA to mail VA Form 21-4192 to your last employers.</li>
</ol>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/tdiu-explained/">TDIU eligibility and rules</a></li>
  <li><a href="/explainers/tdiu-approval-rate/">TDIU approval rate</a></li>
  <li><a href="/explainers/va-unemployability-vs-100-percent/">TDIU vs. 100% schedular</a></li>
  <li><a href="/va-forms/21-8940/">VA Form 21-8940</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:tdiu-benefits",
    canonical_path="/explainers/tdiu-benefits/",
    title="TDIU Benefits 2026: Healthcare, Education, & More Perks",
    h1="TDIU Benefits: The Full List of Perks Beyond the Monthly Check",
    summary=(
        "TDIU benefits go far beyond monthly pay. See the full list — "
        "healthcare, education, housing, commissary access, and tax exemptions "
        "available to TDIU recipients in 2026."
    ),
    body_html=_TDIU_BENEFITS_BODY,
    faq=[
        {"question": "What benefits come with TDIU?",
         "answer": "TDIU pays VA disability at the 100% rate ($3,831/month in 2026), plus VA Priority Group 1 healthcare, CHAMPVA for dependents (if P&T), Chapter 35 education for family, state property tax exemptions, and commissary access."},
        {"question": "Is TDIU the same as 100% schedular?",
         "answer": "Most benefits are identical. Two differences: TDIU recipients must stay below substantially gainful employment (~$15,960/year in 2026), and Chapter 35 education for family requires permanent and total status."},
        {"question": "Can TDIU veterans work?",
         "answer": "Yes, but earnings must stay below the federal poverty threshold (~$15,960 in 2026). Marginal employment and work in a protected environment don't count against you."},
        {"question": "Does TDIU qualify for CHAMPVA?",
         "answer": "Only if the rating is marked permanent and total (P&T). Many TDIU ratings are P&T, but not all. Check the rating decision letter for confirmation."},
    ],
    takeaways=[
        "TDIU pays VA disability at the 100% rate ($3,831/mo single veteran).",
        "Full VA healthcare, CHAMPVA for family (if P&T), and Chapter 35 education.",
        "Property tax exemptions in 22 states match 100% schedular benefits.",
        "Income limit: roughly $15,960/year for substantially gainful employment.",
    ],
    keywords=[
        "tdiu benefits", "tdiu perks", "tdiu 100 percent benefits",
        "what comes with tdiu", "tdiu va benefits",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_TDIU_APPROVAL_BODY = """
<p>The <strong>VA TDIU approval rate</strong> is among the highest in the VA
disability system &mdash; but accurate numbers are hard to find. In 2026,
approximately <strong>87,000+ veterans receive TDIU</strong>, and TDIU is
significantly under-claimed. Many veterans who would qualify never apply.</p>

<h2>TDIU approval rate at a glance</h2>
<p>Public VA data shows TDIU approval rates between <strong>30% and 50%</strong>
of first-time claims, depending on the year and region. Approval rates rise
sharply on appeal &mdash; some attorney-represented appeals reach 70%+.</p>

<h2>Why TDIU is under-claimed</h2>
<ul>
  <li><strong>Veterans don't know it exists.</strong> The VA doesn't volunteer
  TDIU information when rating decisions arrive.</li>
  <li><strong>Confusion about the income limits.</strong> Many veterans assume
  any work disqualifies them.</li>
  <li><strong>Fear of CDR reviews.</strong> Some worry that improving will
  trigger a rating reduction.</li>
  <li><strong>Missing the schedular thresholds.</strong> Veterans below 60% on
  one condition or 70% combined often don't know about extraschedular TDIU.</li>
</ul>

<h2>What raises your TDIU approval odds</h2>
<ol>
  <li><strong>Strong medical evidence.</strong> Treatment records showing
  consistent symptoms and severe functional limits.</li>
  <li><strong>Vocational expert opinion.</strong> A vocational rehabilitation
  expert's report can carry decisive weight.</li>
  <li><strong>Clear last-day-worked date.</strong> The
  <a href="/va-forms/21-8940/">VA Form 21-8940</a> needs accurate employment
  details.</li>
  <li><strong>Employer cooperation</strong> on VA Form 21-4192. Follow up if
  former employers don't respond.</li>
  <li><strong>Lay statements</strong> from family showing daily limitations.</li>
</ol>

<h2>What lowers TDIU approval odds</h2>
<ul>
  <li>Ongoing full-time work above the poverty threshold.</li>
  <li>Inconsistent medical records.</li>
  <li>Missing the schedular criteria with no compelling extraschedular case.</li>
  <li>Incomplete VA Form 21-8940 employment history.</li>
</ul>

<h2>Schedular TDIU criteria (38 CFR 4.16(a))</h2>
<ul>
  <li><strong>One condition rated 60% or higher</strong>, OR</li>
  <li><strong>Combined rating of 70% or more</strong>, with at least one
  condition at 40%.</li>
</ul>

<h2>Extraschedular TDIU (38 CFR 4.16(b))</h2>
<p>If you don't meet schedular thresholds, you can still qualify under
extraschedular TDIU. Only the VA Director of Compensation Service can grant
initial extraschedular TDIU, so these claims take longer.</p>

<h2>How to track TDIU claim status</h2>
<p>Use <a href="/va-claim-status/">VA.gov claim tracker</a> or call
1-800-827-1000. Initial TDIU decisions in 2026 average about 5 to 7 months.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/tdiu-explained/">TDIU eligibility and how it works</a></li>
  <li><a href="/explainers/tdiu-benefits/">Full TDIU benefits list</a></li>
  <li><a href="/explainers/va-unemployability-vs-100-percent/">TDIU vs. 100% schedular</a></li>
  <li><a href="/va-forms/21-8940/">VA Form 21-8940</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:tdiu-approval-rate",
    canonical_path="/explainers/tdiu-approval-rate/",
    title="VA TDIU Approval Rate 2026: Statistics and Tips to Win",
    h1="VA TDIU Approval Rate: Statistics and What Boosts Your Odds",
    summary=(
        "The VA TDIU approval rate runs 30-50% on initial claims and higher on "
        "appeal. See 2026 statistics, common reasons claims fail, and tips to "
        "strengthen your TDIU application."
    ),
    body_html=_TDIU_APPROVAL_BODY,
    faq=[
        {"question": "What is the VA TDIU approval rate?",
         "answer": "Public VA data shows TDIU approval rates of 30-50% on first-time claims, depending on year and region. Appeals push approval rates higher, with attorney-represented appeals sometimes reaching 70%+."},
        {"question": "How many veterans receive TDIU?",
         "answer": "Roughly 87,000 veterans receive TDIU benefits in 2026. The benefit is widely under-claimed — many veterans who qualify never apply because they don't know about it or fear losing benefits."},
        {"question": "What boosts TDIU approval odds?",
         "answer": "Strong medical records showing consistent severe symptoms, a vocational expert opinion, accurate VA Form 21-8940 employment history, employer cooperation on 21-4192, and lay statements describing daily limits."},
        {"question": "How long does a TDIU decision take?",
         "answer": "Initial TDIU decisions in 2026 average 5 to 7 months. Extraschedular claims under 38 CFR 4.16(b) take longer because they require Director of Compensation Service review."},
    ],
    takeaways=[
        "TDIU approval runs 30-50% on initial claims and higher on appeal.",
        "Roughly 87,000 veterans receive TDIU — far fewer than the eligible pool.",
        "Strong medical evidence and a vocational expert opinion are decisive.",
        "Extraschedular TDIU (38 CFR 4.16(b)) requires Director-level review.",
    ],
    keywords=[
        "tdiu approval rate", "va tdiu approval rate", "tdiu statistics",
        "tdiu approval percentage", "tdiu approval data",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_TDIU_VS_100_BODY = """
<p>Many veterans wonder: <strong>VA unemployability vs. 100% disability</strong>
&mdash; which is better? In dollar terms they pay the same in 2026. But the
two ratings have important differences in earning rules, family education
benefits, and rating stability. This guide explains both.</p>

<h2>The basics</h2>
<ul>
  <li><strong>VA unemployability (TDIU)</strong> pays at the 100% rate when
  service-connected conditions prevent substantially gainful work.</li>
  <li><strong>100% schedular rating</strong> means your combined VA disability
  rating reaches 100% based on the rating schedule.</li>
</ul>

<h2>What's the same</h2>
<ul>
  <li>Monthly pay rate ($3,831.30/mo single veteran in 2026).</li>
  <li>VA Priority Group 1 healthcare.</li>
  <li>VA home loan with no funding fee.</li>
  <li>Disabled veteran license plate access.</li>
  <li>Many state property tax exemptions.</li>
</ul>

<h2>What's different</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Feature</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">100% Schedular</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">TDIU</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Earnings allowed</td><td style="padding:0.5rem;border:1px solid #ddd;">Unlimited</td><td style="padding:0.5rem;border:1px solid #ddd;">≤ $15,960 (2026 poverty)</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Chapter 35 education</td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (if P&amp;T)</td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (if P&amp;T)</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">CHAMPVA</td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (if P&amp;T)</td><td style="padding:0.5rem;border:1px solid #ddd;">Yes (if P&amp;T)</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">CDR review risk</td><td style="padding:0.5rem;border:1px solid #ddd;">Lower</td><td style="padding:0.5rem;border:1px solid #ddd;">Higher</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Rating stability</td><td style="padding:0.5rem;border:1px solid #ddd;">Strong (5+ yrs protected)</td><td style="padding:0.5rem;border:1px solid #ddd;">More vulnerable</td></tr>
</tbody>
</table>

<h2>Why some veterans prefer 100% schedular</h2>
<ul>
  <li>You can work without earnings limits.</li>
  <li>Ratings protected after 5 years (38 CFR 3.951).</li>
  <li>Less risk during continuous disability reviews.</li>
</ul>

<h2>Why TDIU might be your path</h2>
<ul>
  <li>You don't meet schedular 100% criteria.</li>
  <li>Your conditions still keep you from working.</li>
  <li>You'd rather get to the 100% rate now than wait for ratings to climb.</li>
</ul>

<h2>The earnings test for TDIU</h2>
<p>Substantially gainful employment in 2026 means earning above the federal
poverty threshold (~$15,960 for a single person). Veterans can earn:</p>
<ul>
  <li><strong>Below the threshold (marginal employment)</strong> &mdash; no
  effect.</li>
  <li><strong>In a protected work environment</strong> &mdash; no effect.</li>
  <li><strong>Above the threshold for 12+ months</strong> &mdash; may trigger a
  reduction proposal.</li>
</ul>

<h2>Can you go from TDIU to 100% schedular?</h2>
<p>Yes &mdash; many veterans do. As you file claims for new or worsened
conditions, your combined rating may reach 100% schedular. At that point you
keep the same pay rate, but lose the earnings limit.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/tdiu-explained/">TDIU eligibility and how it works</a></li>
  <li><a href="/explainers/tdiu-benefits/">Full TDIU benefits list</a></li>
  <li><a href="/explainers/100-percent-va-disability-benefits/">100% VA disability benefits</a></li>
  <li><a href="/explainers/how-to-get-100-va-disability/">How to reach 100% VA disability</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:va-unemployability-vs-100-percent",
    canonical_path="/explainers/va-unemployability-vs-100-percent/",
    title="VA Unemployability vs. 100% Disability: 2026 Comparison",
    h1="VA Unemployability vs. 100% Disability: Which Is Better?",
    summary=(
        "TDIU vs. 100% schedular disability — both pay the same in 2026, but "
        "have key differences in earnings limits, education benefits, and "
        "rating stability."
    ),
    body_html=_TDIU_VS_100_BODY,
    faq=[
        {"question": "What's the difference between TDIU and 100% schedular?",
         "answer": "Both pay $3,831/month for a single veteran in 2026. TDIU has an earnings limit (~$15,960) and is more vulnerable to CDR reviews. 100% schedular allows unlimited earnings and is more stable."},
        {"question": "Does TDIU pay less than 100% schedular?",
         "answer": "No. TDIU pays at the 100% rate. The monthly check is identical for both, though earnings rules and rating stability differ."},
        {"question": "Can I work on 100% schedular?",
         "answer": "Yes, with no earnings limit. The 100% schedular rating doesn't restrict income. TDIU recipients must stay below substantially gainful employment (~$15,960/year in 2026)."},
        {"question": "Can TDIU become 100% schedular?",
         "answer": "Yes. Many veterans build up to 100% schedular over time by adding ratings or filing for increases. The pay rate stays the same, but earnings limits go away."},
    ],
    takeaways=[
        "TDIU and 100% schedular pay the same monthly amount in 2026.",
        "TDIU has an earnings limit (~$15,960/yr); schedular 100% has no income cap.",
        "Both qualify for CHAMPVA and Chapter 35 only if marked Permanent & Total.",
        "100% schedular ratings protect from reduction after 5 years.",
    ],
    keywords=[
        "tdiu vs 100 percent", "va unemployability vs 100",
        "tdiu vs schedular 100", "individual unemployability vs 100",
    ],
    page_type="explainer",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 9 — C&P vendor + claim status (3 pages)
# ---------------------------------------------------------------------------

_VES_BODY = """
<p><strong>Veterans Evaluation Services (VES)</strong> is one of the VA's main
contractors for Compensation &amp; Pension (C&amp;P) exams. Owned by Maximus,
VES handles VA exams across most of the continental United States. In 2026,
millions of veterans go to VES exams as part of their disability claims.</p>

<h2>Who is VES?</h2>
<p>VES is a Maximus company that holds the VA's domestic C&amp;P exam contracts
for Regions 1 through 4. Maximus was re-awarded these contracts effective
January 1, 2025. The contract covers most US states.</p>

<h2>What to expect at a VES exam</h2>
<ul>
  <li><strong>Medical history review.</strong> The examiner reads your records
  and asks about your condition.</li>
  <li><strong>Symptom interview.</strong> Expect detailed questions about how
  the condition affects daily life.</li>
  <li><strong>Focused physical or mental health exam.</strong> The format
  depends on the condition.</li>
  <li><strong>Examiner credentials.</strong> Most exams are run by MDs, DOs,
  NPs, or PAs. Specialty exams (mental health, audiology) use credentialed
  specialists.</li>
  <li><strong>No treatment.</strong> VES exams gather information for the VA
  &mdash; the examiner doesn't treat you.</li>
</ul>

<h2>How to prepare for a VES exam</h2>
<ol>
  <li><strong>Bring photo ID</strong> and the appointment letter.</li>
  <li><strong>Bring a current medication list.</strong></li>
  <li><strong>Keep a symptom journal.</strong> Note flare-ups, bad days, and
  how symptoms limit work.</li>
  <li><strong>Be honest about your worst days.</strong> Many veterans
  unintentionally minimize symptoms.</li>
  <li><strong>Bring a buddy.</strong> They can take notes or wait nearby.</li>
</ol>

<h2>Common VES exam mistakes</h2>
<ul>
  <li><strong>Downplaying symptoms.</strong> Examiners only see one snapshot.
  Be candid about your worst symptoms.</li>
  <li><strong>Missing the appointment.</strong> Missed exams can lead to claim
  denial. Call ASAP if you can't make it.</li>
  <li><strong>Forgetting medical records.</strong> Bring copies of any private
  medical care for the condition.</li>
  <li><strong>Going alone for mental health exams</strong> if you can bring
  someone supportive.</li>
</ul>

<h2>VES contact information</h2>
<ul>
  <li><strong>Phone:</strong> 877-637-8387 (caller ID shows &ldquo;VA
  EXAM-VES&rdquo;).</li>
  <li><strong>Website:</strong> ves.com</li>
  <li><strong>Reschedule</strong> through the phone number above or VES
  online portal.</li>
</ul>

<h2>VES vs. Optum Serve</h2>
<p>The other major VA exam contractor is <a href="/explainers/optum-serve-cp-exam/">Optum Serve</a>
(UnitedHealth, formerly LHI). Exam content is identical &mdash; only the
contractor and scheduling system differ. Quality varies more by individual
examiner than by company.</p>

<h2>What happens after the VES exam</h2>
<p>The examiner submits a Disability Benefits Questionnaire (DBQ) to the VA
&mdash; usually within <strong>30 business days</strong>. The VA rater uses the
DBQ alongside your medical records to assign a rating.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/optum-serve-cp-exam/">Optum Serve C&amp;P exams</a></li>
  <li><a href="/va-claims/c-and-p-exam-tips/">C&amp;P exam preparation tips</a></li>
  <li><a href="/va-claim-status/">How to check your VA claim status</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:veterans-evaluation-services",
    canonical_path="/explainers/veterans-evaluation-services/",
    title="Veterans Evaluation Services (VES): What to Expect 2026",
    h1="Veterans Evaluation Services (VES) C&P Exam Guide",
    summary=(
        "Veterans Evaluation Services (VES) handles VA C&P exams across most "
        "US regions. Learn what to expect, how to prepare, and how VES "
        "differs from Optum Serve."
    ),
    body_html=_VES_BODY,
    faq=[
        {"question": "What is Veterans Evaluation Services (VES)?",
         "answer": "VES is a Maximus company that holds the VA's C&P exam contracts for domestic Regions 1-4. The contract was re-awarded effective January 1, 2025."},
        {"question": "What happens at a VES exam?",
         "answer": "Expect a medical history review, symptom interview, and focused physical or mental health exam by an MD, DO, NP, or PA. The examiner doesn't provide treatment — they document findings for the VA rater."},
        {"question": "How do I prepare for a VES C&P exam?",
         "answer": "Bring photo ID, medication list, and a symptom journal. Be honest about your worst days. Bring private medical records and consider having a supportive person nearby, especially for mental health exams."},
        {"question": "How long until VES results reach the VA?",
         "answer": "VES typically submits the Disability Benefits Questionnaire (DBQ) to the VA within 30 business days of the exam. The VA rater then assigns a rating based on the DBQ and other evidence."},
    ],
    takeaways=[
        "VES is a Maximus contractor for VA C&P exams in most of the US.",
        "Bring ID, medication list, and a symptom journal to your exam.",
        "Be honest about your worst days — examiners see one snapshot.",
        "Results typically reach the VA within 30 business days.",
    ],
    keywords=[
        "veterans evaluation services", "ves c&p exam", "ves va exam",
        "veterans evaluation services c&p exam", "ves cp exam tips",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_OPTUM_SERVE_BODY = """
<p><strong>Optum Serve</strong> &mdash; formerly Logistics Health Inc. (LHI)
&mdash; is UnitedHealth's VA Compensation &amp; Pension (C&amp;P) exam
contractor. In 2026, Optum Serve runs VA disability exams in several regions
alongside <a href="/explainers/veterans-evaluation-services/">Veterans
Evaluation Services (VES)</a>.</p>

<h2>Who is Optum Serve?</h2>
<p>Optum Serve is the federal health services arm of UnitedHealth Group. It
holds VA contracts for the Medical Disability Examination (MDE) program.
Veterans often still see the old &ldquo;LHI&rdquo; name on appointment
letters.</p>

<h2>What to expect at an Optum Serve exam</h2>
<ul>
  <li><strong>Records review</strong> &mdash; the examiner reads your VA file
  before the appointment.</li>
  <li><strong>Symptom and history interview</strong> &mdash; expect specific
  questions about onset, frequency, and impact on daily life.</li>
  <li><strong>Focused physical or mental health exam</strong> &mdash; format
  depends on the condition.</li>
  <li><strong>Provider type</strong> &mdash; usually MD, DO, NP, or PA. May be
  in-network community clinic or dedicated exam center.</li>
  <li><strong>Length</strong> &mdash; 30 minutes for simple exams, several
  hours for complex multi-condition cases.</li>
</ul>

<h2>How Optum Serve differs from VES</h2>
<ul>
  <li><strong>Different scheduling portal</strong> and customer service
  number.</li>
  <li><strong>Often uses in-network community clinics</strong> rather than
  dedicated exam centers.</li>
  <li><strong>Same exam content</strong> &mdash; both contractors complete the
  same VA Disability Benefits Questionnaires (DBQs).</li>
</ul>

<h2>How to prepare for an Optum Serve exam</h2>
<ol>
  <li><strong>Bring ID</strong> and the appointment letter.</li>
  <li><strong>Bring a medication list</strong> with current doses.</li>
  <li><strong>Bring private medical records</strong> the VA may not have.</li>
  <li><strong>Use a symptom journal</strong> showing frequency and severity
  of flare-ups.</li>
  <li><strong>Be specific about how symptoms limit work and daily life.</strong></li>
</ol>

<h2>Common Optum Serve exam pitfalls</h2>
<ul>
  <li><strong>Examiner variability.</strong> Quality varies more by individual
  provider than by contractor.</li>
  <li><strong>Short visits for complex cases.</strong> Push for the full time
  needed to describe your condition.</li>
  <li><strong>Missing the appointment.</strong> Call to reschedule
  immediately &mdash; missed exams can lead to denials.</li>
  <li><strong>Bringing unrealistic expectations.</strong> The examiner doesn't
  decide your rating &mdash; the VA rater does.</li>
</ul>

<h2>Optum Serve contact info</h2>
<ul>
  <li><strong>Phone:</strong> 866-637-8387 (legacy LHI line) or via VA exam
  notification letter.</li>
  <li><strong>Website:</strong> optumserve.com</li>
  <li><strong>Reschedule</strong> through the phone number on your
  appointment letter.</li>
</ul>

<h2>What happens after your Optum Serve exam</h2>
<p>The examiner submits a DBQ to the VA. The VA rater uses it along with your
medical records and other evidence to decide your rating. Most DBQs reach the
VA within 30 business days.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/veterans-evaluation-services/">Veterans Evaluation Services (VES)</a></li>
  <li><a href="/va-claims/c-and-p-exam-tips/">C&amp;P exam preparation tips</a></li>
  <li><a href="/va-claim-status/">How to check your VA claim status</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="explainer:optum-serve-cp-exam",
    canonical_path="/explainers/optum-serve-cp-exam/",
    title="Optum Serve VA Exam: What to Expect at Your C&P (2026)",
    h1="Optum Serve C&P Exam Guide: What to Expect and How to Prepare",
    summary=(
        "Optum Serve (formerly LHI) handles VA C&P exams in many regions. "
        "Learn what to expect, how to prepare, and how Optum Serve differs "
        "from VES."
    ),
    body_html=_OPTUM_SERVE_BODY,
    faq=[
        {"question": "What is Optum Serve?",
         "answer": "Optum Serve is UnitedHealth's federal health services arm, formerly Logistics Health Inc. (LHI). It contracts with the VA to perform Compensation & Pension (C&P) exams as part of the Medical Disability Examination program."},
        {"question": "Is Optum Serve the same as LHI?",
         "answer": "Yes. Optum Serve is the new name for Logistics Health Inc. (LHI). Some VA appointment letters still use the old LHI name."},
        {"question": "How is Optum Serve different from VES?",
         "answer": "The exam content is identical — both contractors complete the same VA Disability Benefits Questionnaires (DBQs). Optum Serve uses a different scheduling portal and often relies on in-network community clinics, while VES often uses dedicated exam centers."},
        {"question": "How do I prepare for an Optum Serve exam?",
         "answer": "Bring photo ID, a current medication list, private medical records the VA may not have, and a symptom journal showing the frequency and severity of flare-ups. Be specific about how symptoms limit work and daily life."},
    ],
    takeaways=[
        "Optum Serve (formerly LHI) is UnitedHealth's VA C&P exam contractor.",
        "Exam content matches VES — only the contractor and scheduling differ.",
        "Bring ID, meds, private records, and a symptom journal.",
        "DBQs typically reach the VA within 30 business days.",
    ],
    keywords=[
        "optum serve", "optum serve va exam", "lhi va exam", "optum serve cp exam",
        "optum serve c&p exam", "optum serve veterans",
    ],
    page_type="explainer",
    sector="va_benefits",
))


_CLAIM_STATUS_BODY = """
<p>Checking your <strong>VA claim status</strong> is one of the most common
veteran questions in 2026. The VA average decision time was about
<strong>76 days in early 2026</strong>, but each claim follows a unique path
through the system. This guide explains how to check claim status and what
each stage means.</p>

<h2>How to check VA claim status</h2>
<ol>
  <li><strong>VA.gov claim tracker.</strong> The fastest way. Log in at
  <a href="https://www.va.gov/claim-or-appeal-status/" target="_blank" rel="noopener noreferrer">va.gov/claim-or-appeal-status</a>
  to see your active claim's stage.</li>
  <li><strong>VA hotline.</strong> Call <strong>1-800-827-1000</strong>
  Monday-Friday 8 AM-9 PM ET.</li>
  <li><strong>VSO check.</strong> If you filed through a VSO, they can
  check status for you.</li>
  <li><strong>Ask Va (AVA) chatbot</strong> on VA.gov for quick answers.</li>
</ol>

<h2>VA claim stages explained</h2>
<p>The VA.gov tracker shows your claim moving through 5-8 stages depending on
type. Here's what each one means.</p>
<ol>
  <li><strong>Claim received</strong> &mdash; VA confirmed the claim is in
  the system. No action yet.</li>
  <li><strong>Initial review</strong> &mdash; a VSR sorts the file and
  identifies what evidence is needed.</li>
  <li><strong>Evidence gathering, review, and decision</strong> &mdash; the VA
  requests records, schedules exams, and reviews the file. This is the longest
  stage.</li>
  <li><strong>Preparation for decision</strong> (optional intermediate stage)
  &mdash; the rater is finalizing the decision.</li>
  <li><strong>Pending decision approval</strong> &mdash; a senior reviewer
  signs off.</li>
  <li><strong>Preparation for notification</strong> &mdash; the decision letter
  is being prepared.</li>
  <li><strong>Complete</strong> &mdash; the decision has been mailed.</li>
</ol>

<h2>2026 average VA claim processing times</h2>
<ul>
  <li><strong>Initial disability claim</strong> &mdash; about 76 days average
  in early 2026 (down from 100+ days in 2023).</li>
  <li><strong>Fully Developed Claim</strong> &mdash; typically 100-140 days
  when veterans upload all evidence upfront.</li>
  <li><strong>Supplemental claims</strong> &mdash; about 48 days on average,
  but up to 5-6 months when extensive evidence is involved.</li>
  <li><strong>Higher-Level Review</strong> &mdash; usually 90-120 days.</li>
  <li><strong>Board appeal</strong> &mdash; 12-18 months on average.</li>
</ul>

<h2>What stage takes the longest?</h2>
<p>&ldquo;Evidence gathering, review, and decision&rdquo; is typically the
longest stage. The VA waits on:</p>
<ul>
  <li>Service treatment records.</li>
  <li>Private medical records.</li>
  <li>C&amp;P exam results from
  <a href="/explainers/veterans-evaluation-services/">VES</a> or
  <a href="/explainers/optum-serve-cp-exam/">Optum Serve</a>.</li>
  <li>Buddy or lay statements.</li>
</ul>

<h2>How to speed up your VA claim</h2>
<ul>
  <li><strong>Use the Fully Developed Claim (FDC) program.</strong> Upload
  every piece of evidence upfront.</li>
  <li><strong>Show up for C&amp;P exams.</strong> Missing exams adds months.</li>
  <li><strong>Respond fast to evidence requests.</strong> The VA gives you 30
  days, but earlier is better.</li>
  <li><strong>File an
  <a href="/va-intent-to-file/">Intent to File</a></strong> first to lock the
  effective date for back pay.</li>
  <li><strong>Work with a VSO</strong> to avoid common mistakes.</li>
</ul>

<h2>Common claim status questions</h2>
<ul>
  <li><strong>&ldquo;My status hasn't moved in weeks.&rdquo;</strong> &mdash;
  normal during evidence gathering. Stages can stall as the VA waits on
  records.</li>
  <li><strong>&ldquo;Why does my status show 'Closed' but I never got a
  decision?&rdquo;</strong> &mdash; some statuses display before the letter
  mails. Wait 7-10 days.</li>
  <li><strong>&ldquo;What does 'Notice of Disagreement' status mean?&rdquo;</strong>
  &mdash; you (or your VSO) filed an appeal of the prior decision.</li>
</ul>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/va-disability-back-pay/">VA disability back pay explained</a></li>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA disability claim</a></li>
  <li><a href="/va-claims/va-claim-timeline/">Full VA claim timeline</a></li>
  <li><a href="/va-claims/c-and-p-exam-tips/">C&amp;P exam preparation</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="page:va-claim-status",
    canonical_path="/va-claim-status/",
    title="VA Claim Status 2026: How to Check Your Disability Claim",
    h1="VA Claim Status: How to Check Your Disability Claim in 2026",
    summary=(
        "Check your VA claim status at VA.gov or by phone. Learn what each "
        "claim stage means, 2026 average processing times, and how to speed "
        "up your claim."
    ),
    body_html=_CLAIM_STATUS_BODY,
    faq=[
        {"question": "How do I check my VA claim status?",
         "answer": "Log in to VA.gov claim tracker at va.gov/claim-or-appeal-status. You can also call the VA at 1-800-827-1000 or ask your VSO to check on your behalf."},
        {"question": "What does each VA claim stage mean?",
         "answer": "The stages are: Claim received, Initial review, Evidence gathering and decision, Preparation for decision, Pending approval, Preparation for notification, and Complete. Evidence gathering is usually the longest stage."},
        {"question": "How long does a VA claim take in 2026?",
         "answer": "Initial disability claims averaged about 76 days in early 2026. Fully Developed Claims (FDC) typically take 100-140 days. Supplemental claims average 48 days, and Board appeals run 12-18 months."},
        {"question": "How can I speed up my VA claim?",
         "answer": "Use the Fully Developed Claim program by uploading all evidence upfront, show up for every C&P exam, respond fast to VA requests, and file an Intent to File first to lock your effective date."},
    ],
    takeaways=[
        "Check VA claim status at va.gov/claim-or-appeal-status or call 1-800-827-1000.",
        "Average 2026 initial claim decision: about 76 days.",
        "Evidence gathering is usually the longest stage.",
        "Use the Fully Developed Claim program and respond fast to speed your claim.",
    ],
    keywords=[
        "va claim status", "va disability claim status", "check va claim",
        "va claim tracker", "va claim status 2026",
    ],
    page_type="page",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 10 — Branch-specific pay charts (4 pages)
# ---------------------------------------------------------------------------

def _pay_table_2026() -> str:
    """Standard 2026 enlisted+officer pay table HTML used across branch pages."""
    return """
<h3>2026 enlisted monthly basic pay</h3>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;font-size:0.92rem;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.35rem;text-align:left;border:1px solid #ddd;">Grade</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">&lt;2 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">4 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">8 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">12 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">16 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">20+ yrs</th></tr></thead>
<tbody>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-1</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,407</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-2</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,698</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-3</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$2,837</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,198</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,198</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,198</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,198</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,198</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-4</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,142</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,659</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,815</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,815</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,815</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,815</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-5</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,343</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,947</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,281</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,422</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,422</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,422</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-6</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,401</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,069</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,613</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,043</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,194</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,268</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-7</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$3,932</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,673</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,136</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,592</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,001</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,246</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-8</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">—</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">—</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,657</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,062</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,448</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,995</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">E-9</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">—</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">—</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">—</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$7,067</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$7,496</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,105</td></tr>
</tbody>
</table>
<h3>2026 officer monthly basic pay</h3>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;font-size:0.92rem;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.35rem;text-align:left;border:1px solid #ddd;">Grade</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">&lt;2 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">4 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">8 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">12 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">16 yrs</th><th style="padding:0.35rem;text-align:right;border:1px solid #ddd;">20+ yrs</th></tr></thead>
<tbody>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-1</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,150</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,222</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,222</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,222</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,222</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,222</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-2</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$4,782</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,485</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,618</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,618</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,618</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,618</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-3</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$5,534</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$7,383</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,125</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,788</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$9,004</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$9,004</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-4</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$6,295</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$7,881</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,816</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$9,888</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,402</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,510</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-5</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$7,295</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,894</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$9,461</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,272</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$11,391</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$12,033</td></tr>
<tr><td style="padding:0.35rem;border:1px solid #ddd;">O-6</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$8,751</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,245</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,725</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$10,783</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$12,480</td><td style="padding:0.35rem;border:1px solid #ddd;text-align:right;">$13,751</td></tr>
</tbody>
</table>
"""


def _branch_pay_page(*, slug, branch, rank_blurb, branch_ranks):
    """Helper to build a branch-specific pay chart page."""
    title_branch = branch
    page_key = f"spoke:military-pay:{slug}"
    canonical_path = f"/military-pay/{slug}/"
    body = f"""
<p>The <strong>{title_branch} pay chart</strong> for 2026 reflects the
<strong>3.8% basic pay increase</strong> that took effect on January 1, 2026.
{rank_blurb} All US military branches share the same DoD-wide pay tables,
so {title_branch} pay rates match the Army, Navy, Marine Corps, Space Force,
and Coast Guard at the same grade and years of service.</p>

<h2>How {title_branch} pay works</h2>
<p>{title_branch} basic pay is set by grade (rank) and years of service.
Promotions and longevity raise your monthly base pay. On top of base pay,
service members earn:</p>
<ul>
  <li><strong>Basic Allowance for Housing (BAH)</strong> &mdash; tax-free,
  based on ZIP code, rank, and dependency status.</li>
  <li><strong>Basic Allowance for Subsistence (BAS)</strong> &mdash; flat
  tax-free food allowance ($316.98/mo enlisted, $499.55/mo officer in 2025
  rates).</li>
  <li><strong>Special and incentive pays</strong> &mdash; hazardous duty,
  flight, sea, dive, and bonuses.</li>
</ul>

{_pay_table_2026()}

<h2>{title_branch} rank structure</h2>
{branch_ranks}

<h2>{title_branch} pay components</h2>
<ul>
  <li><strong>Base pay</strong> &mdash; taxable.</li>
  <li><strong>BAH</strong> &mdash; tax-free, varies by ZIP.
  Use the <a href="/tools/bah-calculator/">BAH calculator</a>.</li>
  <li><strong>BAS</strong> &mdash; tax-free flat rate.</li>
  <li><strong>Special pays</strong> &mdash; varies by duty.</li>
</ul>

<h2>{title_branch} pay calculator</h2>
<p>Estimate your total monthly pay with the
<a href="/tools/military-pay-calculator/">military pay calculator</a>. It
combines base pay, BAH, BAS, and applicable special pays.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/military-pay/">Military pay hub</a></li>
  <li><a href="/military-pay/basic-pay/">All-branches basic pay tables</a></li>
  <li><a href="/military-pay/basic-allowance-housing/">BAH rates and rules</a></li>
  <li><a href="/military-retirement/">Military retirement guide</a></li>
</ul>

<p>The official 2026 pay tables are published by
<a href="https://www.dfas.mil/MilitaryMembers/payentitlements/Pay-Tables/" target="_blank" rel="noopener noreferrer">DFAS</a>.</p>
"""
    return _page(
        page_key=page_key,
        canonical_path=canonical_path,
        title=f"{title_branch} Pay Chart 2026: Monthly Pay by Rank | Rank and Pay",
        h1=f"{title_branch} Pay Chart 2026: Monthly Basic Pay by Rank",
        summary=(
            f"The 2026 {title_branch} pay chart with monthly basic pay for "
            f"every rank and years of service. Includes BAH, BAS, and special "
            f"pays. Updated for the 3.8% January 1, 2026 raise."
        ),
        body_html=body,
        faq=[
            {"question": f"How much does the {title_branch} pay in 2026?",
             "answer": f"{title_branch} basic pay starts at $2,407/month for E-1 and climbs to $8,105/month for E-9 with 20+ years. Officer pay starts at $4,150/month for O-1 and climbs to $13,751/month for O-6 with 20+ years. Base pay is the same across all US military branches."},
            {"question": f"Did {title_branch} pay go up in 2026?",
             "answer": f"Yes. {title_branch} basic pay rose 3.8% on January 1, 2026, as set by the FY2026 National Defense Authorization Act."},
            {"question": f"Does {title_branch} pay include housing and food?",
             "answer": f"Base pay is separate. Service members also receive tax-free BAH (Basic Allowance for Housing) and BAS (Basic Allowance for Subsistence). Many also earn special and incentive pays."},
            {"question": f"How do I see {title_branch} pay for my rank?",
             "answer": "Use the table on this page to find your grade and years of service. For total monthly compensation including BAH and BAS, use the military pay calculator."},
        ],
        takeaways=[
            f"{title_branch} 2026 basic pay rose 3.8% effective January 1.",
            "Base pay tables are identical across all US military branches.",
            "Total compensation also includes tax-free BAH and BAS.",
            "Use the BAH calculator to add housing allowance to base pay.",
        ],
        keywords=[
            f"{title_branch.lower()} pay chart", f"{title_branch.lower()} pay 2026",
            f"{title_branch.lower()} pay scale", f"{title_branch.lower()} basic pay",
            f"{title_branch.lower()} salary 2026",
        ],
        page_type="spoke",
        sector="military_pay",
    )


PAGES.append(_branch_pay_page(
    slug="army-pay-chart",
    branch="Army",
    rank_blurb="Army Soldiers progress through enlisted grades E-1 through E-9 (Sergeant Major) and commissioned officer grades O-1 (Second Lieutenant) through O-10 (General).",
    branch_ranks="""<ul>
  <li><strong>Enlisted (E):</strong> E-1 Private (PV1) → E-2 Private (PV2) →
  E-3 Private First Class (PFC) → E-4 Specialist/Corporal (SPC/CPL) →
  E-5 Sergeant (SGT) → E-6 Staff Sergeant (SSG) → E-7 Sergeant First Class (SFC)
  → E-8 Master Sergeant/First Sergeant (MSG/1SG) → E-9 Sergeant Major (SGM/CSM/SMA).</li>
  <li><strong>Warrant Officer (W):</strong> WO1 → CW2 → CW3 → CW4 → CW5.</li>
  <li><strong>Commissioned Officer (O):</strong> O-1 Second Lieutenant (2LT) →
  O-2 First Lieutenant (1LT) → O-3 Captain (CPT) → O-4 Major (MAJ) →
  O-5 Lieutenant Colonel (LTC) → O-6 Colonel (COL) → O-7 Brigadier General (BG)
  → O-8 Major General (MG) → O-9 Lieutenant General (LTG) → O-10 General (GEN).</li>
</ul>""",
))


_calc_page = _branch_pay_page(
    slug="army-pay-calculator",
    branch="Army",
    rank_blurb="Use the Army pay calculator to estimate your full monthly compensation by rank, time in service, and duty station.",
    branch_ranks="""<p>To estimate total monthly Army pay, combine:</p>
<ol>
  <li><strong>Base pay</strong> from the 2026 chart above.</li>
  <li><strong>BAH</strong> from the
  <a href="/tools/bah-calculator/">BAH calculator</a>.</li>
  <li><strong>BAS</strong> (flat amount).</li>
  <li><strong>Special pays</strong> &mdash; hazardous duty, flight, jump,
  sea, dive, or bonus pay you receive.</li>
</ol>
<p>Use the <a href="/tools/military-pay-calculator/">military pay calculator</a>
for a complete monthly estimate.</p>""",
)
# Override title/summary so it doesn't duplicate the chart page SEO
_calc_page["title"] = "Army Pay Calculator 2026: Estimate Your Monthly Pay"
_calc_page["subtitle"] = "Army Pay Calculator 2026: Estimate Your Total Monthly Pay"
_calc_page["summary"] = (
    "Free Army pay calculator for 2026 — estimate your monthly base pay, BAH, "
    "BAS, and special pays by rank, years of service, and duty station."
)
_calc_page["keywords_json"] = json.dumps([
    "army pay calculator", "army pay calculator 2026", "army salary calculator",
    "us army pay calculator", "army base pay calculator",
])
PAGES.append(_calc_page)


PAGES.append(_branch_pay_page(
    slug="navy-pay-chart",
    branch="Navy",
    rank_blurb="US Navy Sailors progress through enlisted grades E-1 through E-9 (Master Chief Petty Officer of the Navy) and commissioned officer grades O-1 (Ensign) through O-10 (Admiral).",
    branch_ranks="""<ul>
  <li><strong>Enlisted (E):</strong> E-1 Seaman Recruit (SR) → E-2 Seaman
  Apprentice (SA) → E-3 Seaman (SN) → E-4 Petty Officer 3rd Class (PO3) →
  E-5 Petty Officer 2nd Class (PO2) → E-6 Petty Officer 1st Class (PO1) →
  E-7 Chief Petty Officer (CPO) → E-8 Senior Chief Petty Officer (SCPO) →
  E-9 Master Chief Petty Officer (MCPO).</li>
  <li><strong>Warrant Officer (W):</strong> CW2 → CW3 → CW4 → CW5
  (Navy reactivated warrant officer program for cyber and other specialties).</li>
  <li><strong>Commissioned Officer (O):</strong> O-1 Ensign (ENS) → O-2
  Lieutenant Junior Grade (LTJG) → O-3 Lieutenant (LT) → O-4 Lieutenant
  Commander (LCDR) → O-5 Commander (CDR) → O-6 Captain (CAPT) → O-7 Rear
  Admiral (Lower Half) → O-8 Rear Admiral → O-9 Vice Admiral → O-10 Admiral.</li>
</ul>
<p>Navy sea pay is paid on top of basic pay for sea-duty assignments.</p>""",
))


PAGES.append(_branch_pay_page(
    slug="air-force-pay-chart",
    branch="Air Force",
    rank_blurb="US Air Force Airmen progress through enlisted grades E-1 through E-9 (Chief Master Sergeant of the Air Force) and commissioned officer grades O-1 (Second Lieutenant) through O-10 (General).",
    branch_ranks="""<ul>
  <li><strong>Enlisted (E):</strong> E-1 Airman Basic (AB) → E-2 Airman (Amn) →
  E-3 Airman First Class (A1C) → E-4 Senior Airman (SrA) → E-5 Staff Sergeant
  (SSgt) → E-6 Technical Sergeant (TSgt) → E-7 Master Sergeant (MSgt) →
  E-8 Senior Master Sergeant (SMSgt) → E-9 Chief Master Sergeant (CMSgt).</li>
  <li><strong>Commissioned Officer (O):</strong> O-1 Second Lieutenant (2d Lt) →
  O-2 First Lieutenant (1st Lt) → O-3 Captain (Capt) → O-4 Major (Maj) →
  O-5 Lieutenant Colonel (Lt Col) → O-6 Colonel (Col) → O-7 Brigadier General
  (Brig Gen) → O-8 Major General (Maj Gen) → O-9 Lieutenant General
  (Lt Gen) → O-10 General (Gen).</li>
</ul>
<p>Aviators receive flight pay on top of basic pay; some specialty career
fields receive retention bonuses.</p>""",
))


# ---------------------------------------------------------------------------
# Priority 11 — GI Bill cluster (4 pages)
# ---------------------------------------------------------------------------

_GI_BILL_HUB_BODY = """
<p>The <strong>GI Bill</strong> is the most valuable education benefit veterans
earn. In 2026, four different GI Bill programs cover tuition, housing, books,
and more. This hub explains every chapter and helps you pick the right one.</p>

<h2>What is the GI Bill?</h2>
<p>The GI Bill is a family of federal education benefit programs administered
by the VA. Each program (called a &ldquo;chapter&rdquo;) covers a different
group of service members or veterans.</p>

<h2>The four main GI Bill programs in 2026</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Program</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Who it's for</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Chapter 33<br/><a href="/gi-bill/post-9-11/">Post-9/11 GI Bill</a></strong></td><td style="padding:0.5rem;border:1px solid #ddd;">90+ days of active duty after 9/11/2001</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Chapter 30<br/>Montgomery GI Bill - Active Duty</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Active-duty members who paid the $1,200 buy-in</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Chapter 1606<br/>Montgomery GI Bill - Selected Reserve</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Selected Reserve members with 6-year commitment</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Chapter 35<br/>DEA (Survivors and Dependents)</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Spouses and children of 100% P&amp;T or deceased veterans</td></tr>
</tbody>
</table>

<h2>Which GI Bill should you use?</h2>
<p>For most post-9/11 veterans, the <a href="/gi-bill/post-9-11/">Post-9/11 GI
Bill (Chapter 33)</a> is the most valuable. It pays:</p>
<ul>
  <li>Full in-state tuition at public schools.</li>
  <li>Up to $29,920.95 at private/foreign schools (AY 2025-26).</li>
  <li>A monthly housing allowance based on school ZIP code.</li>
  <li>Up to $1,000/year for books and supplies.</li>
  <li>Optional Yellow Ribbon match for private school overflow tuition.</li>
</ul>

<h2>Transferring GI Bill benefits to family</h2>
<p>Active-duty members with 6+ years of service who commit to 4 more years can
transfer Post-9/11 GI Bill benefits to a spouse or children. Transfers must
happen <strong>before separation</strong> &mdash; you can't transfer after.</p>

<h2>GI Bill housing allowance</h2>
<p>Post-9/11 housing pays the E-5 with-dependents BAH at the school's ZIP code.
Online-only students get half the national average ($1,169/mo for AY 2025-26).
Read the full <a href="/explainers/post-9-11-gi-bill-bah/">GI Bill BAH guide</a>.</p>

<h2>GI Bill time limits</h2>
<ul>
  <li><strong>Post-9/11 (Forever GI Bill):</strong> no time limit if you
  separated on or after January 1, 2013.</li>
  <li><strong>Post-9/11 (legacy):</strong> 15 years to use benefits if you
  separated before January 1, 2013.</li>
  <li><strong>Chapter 30:</strong> 10 years from separation.</li>
  <li><strong>Chapter 35:</strong> 36 months, generally before age 26 for
  children.</li>
  <li><strong>Chapter 1606:</strong> ends when you leave the Selected Reserve.</li>
</ul>

<h2>Compare GI Bill programs in detail</h2>
<p>See the full
<a href="/gi-bill/comparison/">GI Bill comparison guide</a> for side-by-side
benefit tables.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/gi-bill/post-9-11/">Post-9/11 GI Bill (Chapter 33)</a></li>
  <li><a href="/gi-bill/comparison/">GI Bill chapter comparison</a></li>
  <li><a href="/explainers/post-9-11-gi-bill-bah/">GI Bill BAH explained</a></li>
  <li><a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a></li>
  <li><a href="/va-education-benefits/">VA education benefits hub</a></li>
</ul>

<p>Apply at the <a href="https://www.va.gov/education/" target="_blank" rel="noopener noreferrer">VA education benefits portal</a>.</p>
"""

PAGES.append(_page(
    page_key="hub:gi-bill",
    canonical_path="/gi-bill/",
    title="GI Bill 2026: Complete Guide to Every Chapter & Benefit",
    h1="The GI Bill: 2026 Complete Veterans Education Benefits Guide",
    summary=(
        "The GI Bill is the VA's flagship education benefit. Learn every "
        "chapter — Post-9/11, Montgomery, DEA, Reserve — and how to use, "
        "transfer, or compare benefits in 2026."
    ),
    body_html=_GI_BILL_HUB_BODY,
    faq=[
        {"question": "What is the GI Bill?",
         "answer": "The GI Bill is a family of federal education benefit programs administered by the VA. Each chapter covers a different group of service members, veterans, or family members."},
        {"question": "Which GI Bill is best?",
         "answer": "For most post-9/11 veterans, the Post-9/11 GI Bill (Chapter 33) is the most valuable. It pays full in-state tuition, monthly housing, and books up to $1,000/year — and has no time limit for service after January 1, 2013."},
        {"question": "Can I transfer GI Bill to my spouse or kids?",
         "answer": "Yes. Active-duty members with 6+ years of service who commit to 4 additional years can transfer Post-9/11 GI Bill benefits to a spouse or children. The transfer must happen before separation."},
        {"question": "How long do I have to use the GI Bill?",
         "answer": "Post-9/11 benefits never expire if you separated on or after January 1, 2013 (the Forever GI Bill). Service before that date carries a 15-year limit. Chapter 30 lasts 10 years from separation."},
    ],
    takeaways=[
        "Four main GI Bill chapters cover veterans, families, and reservists.",
        "Post-9/11 (Chapter 33) is the most valuable for most post-9/11 veterans.",
        "Post-9/11 benefits never expire for service after Jan 1, 2013.",
        "Active-duty members can transfer Post-9/11 benefits to family.",
    ],
    keywords=[
        "gi bill", "gi bill 2026", "veterans gi bill", "post 911 gi bill",
        "gi bill chapters", "gi bill explained",
    ],
    page_type="hub",
    sector="va_benefits",
))


_POST_911_BODY = """
<p>The <strong>Post-9/11 GI Bill (Chapter 33)</strong> is the VA's most-used
education benefit. Veterans who served at least 90 days on active duty after
September 10, 2001 qualify for full tuition coverage at public schools, a
monthly housing allowance, and a books stipend. In 2026, the benefit is
better than ever.</p>

<h2>Post-9/11 GI Bill eligibility</h2>
<p>You qualify for the Post-9/11 GI Bill if you served:</p>
<ul>
  <li>At least <strong>90 days of active duty</strong> after September 10,
  2001 (any honorable service period), OR</li>
  <li>At least <strong>30 days of continuous active duty</strong> and were
  discharged for a service-connected disability.</li>
</ul>

<h2>Post-9/11 GI Bill benefit percentage</h2>
<p>The amount you receive depends on your length of post-9/11 service.</p>
<ul>
  <li><strong>100%</strong> &mdash; 36+ months of active duty service, or
  Purple Heart, or 30+ days continuous discharged for service-connected
  disability.</li>
  <li><strong>90%</strong> &mdash; 30+ months but less than 36.</li>
  <li><strong>80%</strong> &mdash; 24+ months but less than 30.</li>
  <li><strong>70%</strong> &mdash; 18+ months but less than 24.</li>
  <li><strong>60%</strong> &mdash; 6+ months but less than 18.</li>
  <li><strong>50%</strong> &mdash; 90+ days but less than 6 months.</li>
</ul>

<h2>2026 Post-9/11 GI Bill benefit amounts</h2>
<ul>
  <li><strong>Public school tuition</strong> &mdash; 100% of in-state tuition
  and fees.</li>
  <li><strong>Private/foreign school tuition cap</strong> &mdash;
  $29,920.95/year for AY 2025-26 (rises to $30,908.34 for AY 2026-27).</li>
  <li><strong>Monthly Housing Allowance (MHA)</strong> &mdash; equal to E-5
  with-dependents BAH at school's ZIP code.</li>
  <li><strong>Online-only MHA</strong> &mdash; $1,169/month (AY 2025-26).</li>
  <li><strong>Books and supplies stipend</strong> &mdash; up to $1,000/year
  ($41.67 per credit hour).</li>
  <li><strong>One-time relocation allowance</strong> &mdash; $500 for veterans
  moving from rural areas.</li>
</ul>

<h2>Yellow Ribbon Program</h2>
<p>If your private school costs more than the $29,920.95 cap, the
<strong>Yellow Ribbon Program</strong> can help. The school voluntarily covers
some of the overflow, and the VA matches each Yellow Ribbon dollar dollar-for-
dollar. Many top private universities participate.</p>

<h2>Months of benefit</h2>
<p>You get <strong>36 months</strong> of Post-9/11 benefits &mdash; equivalent
to four academic years. The 48-month rule limits combined GI Bill use across
chapters.</p>

<h2>Transferring Post-9/11 to family</h2>
<p>Active-duty members with at least 6 years of service can transfer benefits
to a spouse or children. You must commit to 4 more years of service and
complete the transfer before separation.</p>

<h2>Forever GI Bill (no time limit)</h2>
<p>The 2017 Forever GI Bill removed the 15-year use-by deadline for veterans
who separated on or after January 1, 2013. Service before that date keeps the
original 15-year limit.</p>

<h2>How to apply for the Post-9/11 GI Bill</h2>
<ol>
  <li>Visit <a href="https://www.va.gov/education/" target="_blank" rel="noopener noreferrer">va.gov/education</a>.</li>
  <li>File <strong>VA Form 22-1990</strong> online.</li>
  <li>Wait 30 days for a Certificate of Eligibility (COE).</li>
  <li>Give the COE to your school certifying official.</li>
  <li>Begin classes &mdash; the VA pays tuition direct to the school and MHA
  to you.</li>
</ol>

<h2>Related guides</h2>
<ul>
  <li><a href="/explainers/post-9-11-gi-bill-bah/">Post-9/11 GI Bill BAH explained</a></li>
  <li><a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a></li>
  <li><a href="/gi-bill/comparison/">GI Bill chapter comparison</a></li>
  <li><a href="/gi-bill/">GI Bill hub</a></li>
  <li><a href="/va-education-benefits/">VA education benefits</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="spoke:gi-bill:post-9-11",
    canonical_path="/gi-bill/post-9-11/",
    title="Post-9/11 GI Bill (Chapter 33): 2026 Complete Guide",
    h1="The Post-9/11 GI Bill: Your Complete 2026 Guide",
    summary=(
        "The Post-9/11 GI Bill (Chapter 33) pays tuition, monthly housing, "
        "and books for veterans. See 2026 amounts, eligibility, transfer "
        "rules, and Yellow Ribbon Program."
    ),
    body_html=_POST_911_BODY,
    faq=[
        {"question": "Who qualifies for the Post-9/11 GI Bill?",
         "answer": "Veterans with at least 90 days of active duty after September 10, 2001, or 30+ days continuous active duty discharged for a service-connected disability."},
        {"question": "How much does the Post-9/11 GI Bill pay in 2026?",
         "answer": "It covers full in-state tuition at public schools, up to $29,920.95/year at private schools (AY 2025-26), a monthly housing allowance equal to E-5 with-dependents BAH at the school's ZIP, and up to $1,000/year for books."},
        {"question": "What is the Forever GI Bill?",
         "answer": "The Forever GI Bill removed the 15-year time limit for veterans who separated on or after January 1, 2013. Their Post-9/11 benefits never expire. Service before that date keeps the 15-year limit."},
        {"question": "Can I transfer Post-9/11 benefits to my spouse?",
         "answer": "Yes, if you're active duty with at least 6 years of service and commit to 4 more years. Transfers must happen before separation — you can't transfer after leaving service."},
    ],
    takeaways=[
        "Post-9/11 GI Bill covers full in-state tuition and monthly housing.",
        "Private school tuition cap: $29,920.95 for AY 2025-26.",
        "Benefits never expire for service after Jan 1, 2013.",
        "Transfer to family requires 6+ years of service and 4-year extension.",
    ],
    keywords=[
        "post 9/11 gi bill", "chapter 33 gi bill", "post-9-11 gi bill",
        "post 911 gi bill 2026", "forever gi bill", "post 9 11 gi bill benefits",
    ],
    page_type="spoke",
    sector="va_benefits",
))


_GI_BILL_COMPARISON_BODY = """
<p>Veterans often qualify for more than one GI Bill chapter. This 2026
<strong>GI Bill comparison</strong> guide shows side-by-side benefit
amounts, eligibility, and trade-offs so you can choose the best program.</p>

<h2>The four chapters compared</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;font-size:0.92rem;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Feature</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Ch. 33 Post-9/11</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Ch. 30 MGIB-AD</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Ch. 35 DEA</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Ch. 1606 MGIB-SR</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Eligible</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">90+ days post-9/11 active duty</td><td style="padding:0.5rem;border:1px solid #ddd;">Active duty + $1,200 buy-in</td><td style="padding:0.5rem;border:1px solid #ddd;">Spouse/children of 100% P&amp;T or KIA vets</td><td style="padding:0.5rem;border:1px solid #ddd;">Selected Reserve, 6-yr commit</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Payment</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Tuition to school + MHA + books</td><td style="padding:0.5rem;border:1px solid #ddd;">$2,185/mo flat (full-time)</td><td style="padding:0.5rem;border:1px solid #ddd;">$1,574/mo full-time</td><td style="padding:0.5rem;border:1px solid #ddd;">$493/mo full-time</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Transferable</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">Yes</td><td style="padding:0.5rem;border:1px solid #ddd;">No</td><td style="padding:0.5rem;border:1px solid #ddd;">N/A</td><td style="padding:0.5rem;border:1px solid #ddd;">No</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Time limit</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">None (Forever GI Bill, post-2013 service)</td><td style="padding:0.5rem;border:1px solid #ddd;">10 yrs from separation</td><td style="padding:0.5rem;border:1px solid #ddd;">36 months; under 26 for children</td><td style="padding:0.5rem;border:1px solid #ddd;">Ends at Selected Reserve exit</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><strong>Months</strong></td><td style="padding:0.5rem;border:1px solid #ddd;">36</td><td style="padding:0.5rem;border:1px solid #ddd;">36</td><td style="padding:0.5rem;border:1px solid #ddd;">36</td><td style="padding:0.5rem;border:1px solid #ddd;">36</td></tr>
</tbody>
</table>

<h2>Post-9/11 (Chapter 33) at a glance</h2>
<p>The <a href="/gi-bill/post-9-11/">Post-9/11 GI Bill</a> is the most valuable
chapter for most post-9/11 veterans. It pays full in-state tuition at public
schools, a monthly housing allowance, and a books stipend. Benefits can
transfer to a spouse or children.</p>

<h2>Montgomery GI Bill - Active Duty (Chapter 30)</h2>
<p>Chapter 30 pays a <strong>flat monthly stipend</strong> ($2,185 full-time
in 2026) to the veteran. Best for older veterans who paid the $1,200 buy-in,
veterans attending low-cost schools, or veterans who only need a single
program of training.</p>

<h2>DEA (Chapter 35)</h2>
<p>Chapter 35 pays <strong>$1,574/month full-time</strong> to spouses or
children of veterans who are 100% permanently &amp; totally disabled, died
from a service-connected condition, or are MIA/POW.</p>

<h2>Selected Reserve (Chapter 1606)</h2>
<p>Chapter 1606 pays <strong>$493/month full-time</strong> to Reserve and
Guard members with a 6-year commitment. Benefits end when you leave the
Selected Reserve.</p>

<h2>Which GI Bill is best for you?</h2>
<ul>
  <li><strong>Active-duty post-9/11 veteran?</strong> Choose Chapter 33 unless
  you have a specific reason for Chapter 30.</li>
  <li><strong>Surviving spouse or child of a 100% P&amp;T veteran?</strong> Use
  Chapter 35 (or Fry Scholarship if the veteran died in service).</li>
  <li><strong>In the Selected Reserve?</strong> Chapter 1606 covers training
  while you serve.</li>
  <li><strong>Pre-9/11 veteran with Chapter 30 paid in?</strong> Compare the
  flat payment to private school costs &mdash; sometimes Chapter 30 is the
  better choice.</li>
</ul>

<h2>Can you use more than one chapter?</h2>
<p>You can use up to <strong>48 months total</strong> across all programs, but
not both at the same time. Most veterans pick one chapter and stick with it.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/gi-bill/">GI Bill hub</a></li>
  <li><a href="/gi-bill/post-9-11/">Post-9/11 GI Bill (Chapter 33)</a></li>
  <li><a href="/explainers/post-9-11-gi-bill-bah/">GI Bill BAH explained</a></li>
  <li><a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="spoke:gi-bill:comparison",
    canonical_path="/gi-bill/comparison/",
    title="GI Bill Comparison 2026: Chapter 33 vs 30 vs 35 vs 1606",
    h1="GI Bill Comparison: Compare All Four Chapters Side by Side",
    summary=(
        "Compare every GI Bill chapter in 2026 — Post-9/11 (33), Montgomery "
        "Active Duty (30), DEA (35), and Selected Reserve (1606). See "
        "eligibility, payments, and time limits."
    ),
    body_html=_GI_BILL_COMPARISON_BODY,
    faq=[
        {"question": "Which GI Bill chapter pays the most?",
         "answer": "For most post-9/11 veterans, Chapter 33 (Post-9/11) pays the most because it covers full tuition plus monthly housing and books. Chapter 30 pays a flat $2,185/month, which can beat Chapter 33 only at very low-cost schools."},
        {"question": "Can I use two GI Bill chapters?",
         "answer": "Not at the same time. You can use up to 48 months total across all programs, but you must pick one chapter for each program of training. Most veterans pick one and stay with it."},
        {"question": "Should I use the Montgomery or Post-9/11 GI Bill?",
         "answer": "For most veterans, Post-9/11 wins because it pays tuition plus a housing allowance. Montgomery pays a flat amount, which only beats Post-9/11 if your tuition is very low or you don't need housing money."},
        {"question": "What is Chapter 35 DEA?",
         "answer": "Chapter 35 (Dependents Educational Assistance) pays $1,574/month full-time to spouses or children of veterans who are 100% permanently and totally disabled, deceased from service-connected causes, or MIA/POW."},
    ],
    takeaways=[
        "Chapter 33 (Post-9/11) is the best choice for most post-9/11 veterans.",
        "Chapter 30 pays $2,185/mo flat; Chapter 35 pays $1,574/mo; Chapter 1606 pays $493/mo.",
        "You can use up to 48 months total across all chapters — not at the same time.",
        "Post-9/11 transfers to family; Chapter 30 does not.",
    ],
    keywords=[
        "gi bill comparison", "gi bill chapters compared", "chapter 33 vs 30",
        "gi bill comparison tool", "post 911 vs montgomery", "gi bill compare",
    ],
    page_type="spoke",
    sector="va_benefits",
))


_VA_EDU_BENEFITS_BODY = """
<p>The VA offers several <strong>education benefits</strong> for veterans,
service members, and their families. Beyond the GI Bill, you can qualify for
vocational rehabilitation, dependent education, tuition assistance, and
scholarships. This 2026 hub explains every program.</p>

<h2>VA education benefits at a glance</h2>
<table style="width:100%;border-collapse:collapse;margin:1rem 0;">
<thead><tr style="background:#f5f5f5;"><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Program</th><th style="padding:0.5rem;text-align:left;border:1px solid #ddd;">Who it's for</th></tr></thead>
<tbody>
<tr><td style="padding:0.5rem;border:1px solid #ddd;"><a href="/gi-bill/post-9-11/">Post-9/11 GI Bill</a></td><td style="padding:0.5rem;border:1px solid #ddd;">Post-9/11 active-duty veterans</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Montgomery GI Bill (Ch. 30/1606)</td><td style="padding:0.5rem;border:1px solid #ddd;">Active-duty (buy-in) and Reserve</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Chapter 35 (DEA)</td><td style="padding:0.5rem;border:1px solid #ddd;">Spouse/children of 100% P&amp;T or deceased vets</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Fry Scholarship</td><td style="padding:0.5rem;border:1px solid #ddd;">Children/spouse of post-9/11 KIA service members</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">VR&amp;E (Chapter 31)</td><td style="padding:0.5rem;border:1px solid #ddd;">Service-connected veterans needing employment</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Yellow Ribbon Program</td><td style="padding:0.5rem;border:1px solid #ddd;">Post-9/11 students at private schools</td></tr>
<tr><td style="padding:0.5rem;border:1px solid #ddd;">Tuition Assistance (TA)</td><td style="padding:0.5rem;border:1px solid #ddd;">Active-duty members</td></tr>
</tbody>
</table>

<h2>The GI Bill: Your primary education benefit</h2>
<p>The <a href="/gi-bill/">GI Bill</a> is the most-used VA education benefit.
Most post-9/11 veterans use the <a href="/gi-bill/post-9-11/">Post-9/11 GI
Bill (Chapter 33)</a>. See the
<a href="/gi-bill/comparison/">GI Bill comparison guide</a> to pick the right
chapter.</p>

<h2>Vocational Rehabilitation and Employment (VR&amp;E)</h2>
<p><strong>VR&amp;E (Chapter 31)</strong> is for service-connected veterans
who need help finding or keeping work because of a disability. VR&amp;E can
pay for:</p>
<ul>
  <li>College, vocational training, or apprenticeships.</li>
  <li>Books, supplies, and equipment.</li>
  <li>Monthly subsistence allowance.</li>
  <li>Job placement and employer outreach.</li>
  <li>Independent living services.</li>
</ul>
<p>VR&amp;E often pays more than the GI Bill because it doesn't have a 36-month
cap when needed. Apply via VA Form 28-1900.</p>

<h2>Education benefits for family members</h2>
<ul>
  <li><strong>Chapter 35 (DEA)</strong> &mdash; pays $1,574/month full-time
  for 36 months. Covers spouses and children of permanently disabled or
  deceased veterans.</li>
  <li><strong>Fry Scholarship</strong> &mdash; Post-9/11-style benefits
  (tuition + MHA + books) for surviving children and spouses of post-9/11
  service members who died in the line of duty.</li>
  <li><strong>Transferred Post-9/11</strong> &mdash; active-duty members with
  6+ years of service can transfer GI Bill benefits to family.</li>
</ul>

<h2>Yellow Ribbon Program</h2>
<p>Yellow Ribbon helps Post-9/11 students attend private schools that cost
more than the tuition cap ($29,920.95 for AY 2025-26). The school
voluntarily covers some of the overflow, and the VA matches each dollar.</p>

<h2>Tuition Assistance (TA) for active duty</h2>
<p>Each branch offers TA covering up to $4,500/year and $250 per credit hour
for active-duty members taking college courses while serving.</p>

<h2>Scholarships beyond the VA</h2>
<ul>
  <li>Veterans of Foreign Wars (VFW) scholarships.</li>
  <li>American Legion scholarships.</li>
  <li>Pat Tillman Foundation Scholars.</li>
  <li>Service Academy Career Conference scholarships.</li>
  <li>State-level veteran tuition waivers (varies).</li>
</ul>

<h2>How to start using VA education benefits</h2>
<ol>
  <li>Check eligibility at
  <a href="https://www.va.gov/education/" target="_blank" rel="noopener noreferrer">va.gov/education</a>.</li>
  <li>File VA Form 22-1990 (or appropriate form for your program).</li>
  <li>Wait for your Certificate of Eligibility (COE).</li>
  <li>Give the COE to the school's certifying official.</li>
  <li>Begin classes and track your monthly benefit at VA.gov.</li>
</ol>

<h2>Related guides</h2>
<ul>
  <li><a href="/gi-bill/">GI Bill hub</a></li>
  <li><a href="/gi-bill/post-9-11/">Post-9/11 GI Bill</a></li>
  <li><a href="/gi-bill/comparison/">GI Bill comparison</a></li>
  <li><a href="/tools/gi-bill-bah-calculator/">GI Bill BAH calculator</a></li>
  <li><a href="/explainers/post-9-11-gi-bill-bah/">GI Bill BAH explained</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="page:va-education-benefits",
    canonical_path="/va-education-benefits/",
    title="VA Education Benefits 2026: All Programs Explained",
    h1="VA Education Benefits: GI Bill, VR&E, DEA, and More in 2026",
    summary=(
        "Every VA education benefit in 2026: Post-9/11 GI Bill, Montgomery, "
        "Chapter 35 DEA, Fry Scholarship, VR&E, Yellow Ribbon, and active-duty "
        "Tuition Assistance."
    ),
    body_html=_VA_EDU_BENEFITS_BODY,
    faq=[
        {"question": "What VA education benefits exist?",
         "answer": "The main programs are the GI Bill (Post-9/11, Montgomery Active Duty, DEA, Selected Reserve), VR&E vocational rehabilitation, the Fry Scholarship for survivors, the Yellow Ribbon Program, and active-duty Tuition Assistance."},
        {"question": "What is VR&E?",
         "answer": "VR&E (Chapter 31) is the Vocational Rehabilitation and Employment program for service-connected veterans who need help finding work. It pays for school, books, subsistence, and job placement — often more generously than the GI Bill."},
        {"question": "Can my spouse use VA education benefits?",
         "answer": "Yes. Spouses qualify for Chapter 35 (DEA) if you're rated 100% permanently and totally disabled or died from a service-connected cause. Active-duty members can also transfer Post-9/11 benefits to a spouse."},
        {"question": "What is the Yellow Ribbon Program?",
         "answer": "Yellow Ribbon helps Post-9/11 GI Bill students at private schools that cost more than the $29,920.95 cap (AY 2025-26). The school covers some of the overflow, and the VA matches dollar-for-dollar."},
    ],
    takeaways=[
        "Post-9/11 GI Bill is the most-used VA education benefit.",
        "VR&E (Chapter 31) can pay more than the GI Bill for disabled veterans.",
        "Family members qualify for Chapter 35 DEA or the Fry Scholarship.",
        "Yellow Ribbon covers private-school tuition above the $29,920 cap.",
    ],
    keywords=[
        "va education benefits", "veterans education benefits",
        "gi bill education benefits", "va school benefits",
        "veteran tuition benefits", "va education programs",
    ],
    page_type="page",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Priority 12 — Benefits Delivery at Discharge (BDD) — VA Claims spoke
# ---------------------------------------------------------------------------

_BDD_BODY = """
<p>The <strong>Benefits Delivery at Discharge (BDD)</strong> program lets
separating service members file their VA disability claim
<strong>180 to 90 days before separation</strong>. The result: a faster
decision &mdash; often within 30 days of separation &mdash; instead of waiting
6+ months as a civilian.</p>

<h2>What is the BDD program?</h2>
<p>BDD is a pre-discharge VA disability claim program. Active-duty, Guard, and
Reserve members file their claim before separation so the VA can review service
treatment records, schedule exams, and prepare a decision in advance.</p>

<h2>BDD eligibility</h2>
<p>You qualify for BDD if you:</p>
<ul>
  <li>Have <strong>180 to 90 days remaining</strong> on active duty.</li>
  <li>Have a known separation date.</li>
  <li>Can attend <strong>all VA exams within 45 days</strong> of filing.</li>
  <li>Are separating with an honorable or general (under honorable conditions)
  discharge.</li>
</ul>
<p>Coast Guard and Reserve/Guard members called to active duty also qualify.</p>

<h2>BDD timeline</h2>
<ol>
  <li><strong>180 days before separation</strong> &mdash; window opens for
  filing.</li>
  <li><strong>90 days before separation</strong> &mdash; window closes for
  BDD. Later claims go through the Quick Start program or standard process.</li>
  <li><strong>45 days from filing</strong> &mdash; you must complete all
  required C&amp;P exams.</li>
  <li><strong>Separation day</strong> &mdash; the VA finalizes review using
  your separation health assessment.</li>
  <li><strong>~30 days after separation</strong> &mdash; decision typically
  arrives.</li>
</ol>

<h2>BDD advantages over standard claims</h2>
<ul>
  <li><strong>Faster decision</strong> &mdash; often 30 days after separation
  versus 76+ days for standard claims.</li>
  <li><strong>Compensation starts immediately</strong> &mdash; first payment
  follows soon after separation.</li>
  <li><strong>Service treatment records ready</strong> &mdash; no need to
  request them later.</li>
  <li><strong>Active-duty exams convenient</strong> &mdash; you're still in
  uniform and on base when the exams happen.</li>
</ul>

<h2>Required documents for BDD</h2>
<ul>
  <li><strong>Separation Health Assessment (SHA)</strong> or equivalent
  separation physical.</li>
  <li>Complete service treatment records.</li>
  <li>Private medical evidence (specialist reports, MRI/X-ray imaging, etc.).</li>
  <li>Buddy statements on <a href="/va-forms/21-4138/">VA Form 21-4138</a>.</li>
</ul>

<h2>How to apply for BDD</h2>
<ol>
  <li>Visit <a href="https://www.va.gov/disability/how-to-file-claim/when-to-file/pre-discharge-claim/" target="_blank" rel="noopener noreferrer">va.gov/disability pre-discharge claim</a>.</li>
  <li>File <a href="/va-forms/21-526ez/">VA Form 21-526EZ</a> through the
  pre-discharge path.</li>
  <li>Upload your service treatment records, SHA, and private medical
  evidence.</li>
  <li>Attend all VA C&amp;P exams within 45 days of filing.</li>
  <li>Wait for the decision letter &mdash; usually within 30 days after
  separation.</li>
</ol>

<h2>BDD vs. Quick Start program</h2>
<p>If you have <strong>less than 90 days</strong> remaining when you file, the
VA uses the Quick Start program instead. Quick Start is slower than BDD but
still faster than waiting until after separation.</p>

<h2>What if I miss the BDD window?</h2>
<p>You can still file a standard claim after separation. File an
<a href="/va-intent-to-file/">Intent to File</a> immediately to lock your
effective date, then submit the formal claim once you've gathered evidence.</p>

<h2>Related guides</h2>
<ul>
  <li><a href="/va-claims/how-to-file-a-va-claim/">How to file a VA disability claim</a></li>
  <li><a href="/va-forms/21-526ez/">VA Form 21-526EZ</a></li>
  <li><a href="/va-intent-to-file/">VA Intent to File</a></li>
  <li><a href="/va-claims/c-and-p-exam-tips/">C&amp;P exam preparation</a></li>
  <li><a href="/explainers/va-disability-back-pay/">VA disability back pay</a></li>
</ul>
"""

PAGES.append(_page(
    page_key="spoke:va-claims:benefits-delivery-at-discharge",
    canonical_path="/va-claims/benefits-delivery-at-discharge/",
    title="VA BDD Claim 2026: File 180 Days Before Separation",
    h1="Benefits Delivery at Discharge (BDD): File Your VA Claim Before Separation",
    summary=(
        "The Benefits Delivery at Discharge (BDD) program lets you file a VA "
        "disability claim 180–90 days before separation. Get a decision "
        "within 30 days after you separate."
    ),
    body_html=_BDD_BODY,
    faq=[
        {"question": "What is the BDD program?",
         "answer": "The Benefits Delivery at Discharge program lets separating service members file VA disability claims 180 to 90 days before separation. The VA reviews records, conducts exams while you're still on active duty, and typically issues a decision within 30 days of separation."},
        {"question": "When can I apply for BDD?",
         "answer": "You can apply when you have 180 to 90 days remaining on active duty and a known separation date. You must also be available for VA exams within 45 days of filing."},
        {"question": "What's the advantage of BDD over a standard claim?",
         "answer": "BDD claims typically result in a decision within 30 days of separation versus 76+ days for standard claims. Your compensation begins almost immediately, and you don't need to chase down service records later."},
        {"question": "What if I miss the 90-day BDD window?",
         "answer": "You can use the Quick Start program if you have less than 90 days left, or file a standard claim after separation. Either way, file an Intent to File first to lock your effective date for back pay."},
    ],
    takeaways=[
        "File BDD 180–90 days before separation for the fastest decision.",
        "Decision typically comes within 30 days after separation.",
        "Must complete all C&P exams within 45 days of filing.",
        "Missed the window? Use Quick Start or file an Intent to File now.",
    ],
    keywords=[
        "bdd va claim", "benefits delivery at discharge", "bdd program va",
        "pre discharge claim", "va bdd 2026", "file va claim before separation",
    ],
    page_type="spoke",
    sector="va_benefits",
))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(dry: bool = False) -> None:
    db = SessionLocal()
    inserted = 0
    updated = 0
    try:
        for data in PAGES:
            row = db.query(LandingPage).filter(LandingPage.page_key == data["page_key"]).first()
            if row is None:
                row = LandingPage(page_key=data["page_key"])
                db.add(row)
                inserted += 1
            else:
                updated += 1
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
        if dry:
            db.rollback()
            print(f"DRY RUN: would insert {inserted}, update {updated}")
        else:
            db.commit()
            print(f"Inserted {inserted}, updated {updated} pages.")
    finally:
        db.close()


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    run(dry=dry)





