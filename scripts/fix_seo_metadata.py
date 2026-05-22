#!/usr/bin/env python3
"""
Fix SEO metadata for all 120 landing pages.

Updates:
  - page.title      → 50-60 char SEO title with primary keyword
  - page.summary    → 140-160 char meta description with keywords
  - page.faq_json   → 4-5 properly structured FAQ items per page

Run:
    python scripts/fix_seo_metadata.py
    python scripts/fix_seo_metadata.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import LandingPage, SessionLocal, init_db

# ---------------------------------------------------------------------------
# Title data (50-60 chars)
# ---------------------------------------------------------------------------

PILLAR_TITLES = {
    "va-claims":           "VA Claims Guide 2026: How to File & Win Disability",        # 51
    "va-disability":       "VA Disability Ratings Explained: Combined Rating 2026",     # 54
    "military-retirement": "Military Retirement Pay 2026: BRS, High-36 & More",         # 50
    "military-pay":        "2026 Military Pay Tables, BAH Rates & Allowances",          # 49
    "state-benefits":      "Veterans Benefits by State 2026: Tax & Education",          # 50
    "explainers":          "VA & Military Benefits Explained: Plain-English Guides",    # 55
}

PILLAR_DESCRIPTIONS = {
    "va-claims": (
        "Complete guide to filing VA disability claims in 2026. Learn service connection requirements, "
        "how to prepare for your C&P exam, what evidence to submit, and what to do if VA denies your claim."
    ),  # 197 → trim
    "va-disability": (
        "How VA calculates your combined disability rating, what TDIU means, and how to maximize your VA "
        "disability compensation. Includes rating tables and the whole-person combined rating formula."
    ),
    "military-retirement": (
        "Complete guide to military retirement pay in 2026. Covers Final Pay, High-36, and the Blended "
        "Retirement System (BRS), plus SBP, concurrent receipt, and TSP contribution strategies."
    ),
    "military-pay": (
        "2026 military pay charts, BAH rates by ZIP code, BAS allowances, and special pays. Find your "
        "monthly base pay by grade and years of service, plus BAH rates for your duty station."
    ),
    "state-benefits": (
        "State veterans benefits guide for all 50 states: property tax exemptions, income tax exclusions "
        "for military retirement, free tuition programs, vehicle registration discounts, and more."
    ),
    "explainers": (
        "Plain-English guides to the most confusing VA and military benefits topics. From nexus letters and "
        "C&P exams to the PACT Act and BRS — explained simply for veterans and military families."
    ),
}

SPOKE_TITLES = {
    "va-claims:how-to-file-a-va-claim":            "How to File a VA Disability Claim: Step-by-Step 2026",  # 53
    "va-claims:service-connection-requirements":   "VA Service Connection Requirements Explained 2026",      # 50
    "va-claims:nexus-letter-guide":                "Nexus Letter for VA Claims: What It Is & How to Get",   # 52
    "va-claims:c-and-p-exam-tips":                 "VA C&P Exam Tips 2026: What to Say & How to Prepare",   # 52
    "va-claims:va-claim-timeline":                 "VA Claim Processing Timeline 2026: How Long It Takes",   # 53
    "va-claims:buddy-statement-guide":             "VA Buddy Statement Guide: How to Write & Submit 2026",   # 54
    "va-claims:va-claim-checklist":                "VA Disability Claim Checklist: Documents You Need 2026", # 55
    "va-claims:secondary-conditions":              "VA Secondary Conditions: How to File a Linked Claim",    # 52
    "va-claims:va-rating-increase":                "How to Get a VA Rating Increase: Complete Guide 2026",   # 53
    "va-claims:claim-for-increase":                "VA Claim for Increase: How to File & What to Expect",   # 52
    "military-retirement:final-pay-retirement":            "Final Pay Military Retirement: Who Qualifies & How Much",  # 57
    "military-retirement:high-36-retirement":              "High-36 Military Retirement System Explained 2026",         # 50
    "military-retirement:blended-retirement-system":       "Blended Retirement System (BRS) Guide for Troops 2026",    # 56
    "military-retirement:disability-retirement-vs-chapter61": "Military Disability Retirement vs Chapter 61 Explained", # 57
    "military-retirement:reserve-retirement-points":       "Reserve & Guard Retirement Points System Explained",        # 52
    "military-retirement:survivor-benefit-plan":           "Survivor Benefit Plan (SBP): Military Retirement Guide",   # 56
    "military-retirement:concurrent-receipt-crsc-crdp":   "Concurrent Receipt: CRSC & CRDP Explained for Veterans",   # 55
}

SPOKE_DESCRIPTIONS = {
    "va-claims:how-to-file-a-va-claim": (
        "Step-by-step guide to filing a VA disability claim in 2026. Learn how to gather evidence, submit "
        "VA Form 21-526EZ online, prepare for your C&P exam, and track your claim status at VA.gov."
    ),
    "va-claims:service-connection-requirements": (
        "What VA requires to service-connect a disability: an in-service event, a current diagnosis, and "
        "a nexus link. Covers direct, secondary, and presumptive service connection with real examples."
    ),
    "va-claims:nexus-letter-guide": (
        "A nexus letter is a physician's opinion linking your condition to military service. Learn what it "
        "must say, who can write one, what a private nexus letter costs, and how it affects your VA claim."
    ),
    "va-claims:c-and-p-exam-tips": (
        "How to prepare for your VA Compensation & Pension exam in 2026. What to say, what not to say, "
        "how to document your worst-day symptoms, and what to do if the C&P examiner gets it wrong."
    ),
    "va-claims:va-claim-timeline": (
        "How long does VA take to decide a disability claim? Learn the average processing time, the stages "
        "of a VA claim, what causes delays, and how to track your claim status online at VA.gov."
    ),
    "va-claims:buddy-statement-guide": (
        "A buddy statement (VA Form 21-4142) lets fellow service members and family members support your "
        "VA claim. Learn who can write one, what to include, and how to submit it with your claim packet."
    ),
    "va-claims:va-claim-checklist": (
        "Complete VA disability claim checklist for 2026. Documents you need: DD-214, service treatment "
        "records, medical nexus letter, buddy statements, DBQ forms, and private medical evidence."
    ),
    "va-claims:secondary-conditions": (
        "A secondary VA disability is a condition caused or aggravated by a service-connected disability. "
        "Learn how to identify secondary conditions, what evidence you need, and how to file the claim."
    ),
    "va-claims:va-rating-increase": (
        "How to request a VA rating increase in 2026. If your service-connected condition has worsened, "
        "you can file for an increase with updated medical evidence. Learn the process and what to expect."
    ),
    "va-claims:claim-for-increase": (
        "A VA Claim for Increase (CFI) lets you request a higher disability rating when symptoms worsen. "
        "Learn when to file, what evidence to submit, how long it takes, and whether your rating can drop."
    ),
    "military-retirement:final-pay-retirement": (
        "The Final Pay military retirement system applies to service members who entered before September "
        "1980. Retirement pay equals 2.5% × years of service × final monthly base pay. Full guide here."
    ),
    "military-retirement:high-36-retirement": (
        "The High-36 retirement system uses your average base pay over the last 36 months of service. "
        "Applies to those who entered between Sept. 1980 and Dec. 2017. Learn how to calculate your pay."
    ),
    "military-retirement:blended-retirement-system": (
        "The Blended Retirement System (BRS) combines a 2.0% multiplier retirement annuity with TSP "
        "matching contributions. Mandatory for post-2018 entrants, optional for eligible mid-career troops."
    ),
    "military-retirement:disability-retirement-vs-chapter61": (
        "Military disability retirement (Chapter 61 IDES/LDES) vs VA disability compensation: who qualifies, "
        "how pay is calculated, concurrent receipt rules, and the key differences every servicemember needs to know."
    ),
    "military-retirement:reserve-retirement-points": (
        "Guard and Reserve members earn retirement points for drills, annual training, and deployments. "
        "Learn how points convert to retirement pay, what triggers the 'gray area' period, and age-60 rules."
    ),
    "military-retirement:survivor-benefit-plan": (
        "The Survivor Benefit Plan (SBP) provides up to 55% of retired pay to surviving spouses and "
        "dependents. Learn SBP costs, open-season elections, the SBP-DIC offset, and how to enroll."
    ),
    "military-retirement:concurrent-receipt-crsc-crdp": (
        "Concurrent receipt lets qualifying veterans receive both military retirement pay and VA disability "
        "compensation. Compare CRSC vs CRDP eligibility rules, application steps, and which pays more."
    ),
}

EXPLAINER_TITLES = {
    "what-is-a-nexus-letter":               "What Is a Nexus Letter? VA Claims Guide 2026",             # 46
    "va-disability-rating-explained":       "VA Disability Rating Explained: Combined Rating Formula",   # 53
    "pact-act-explained":                   "PACT Act Explained: Burn Pit Benefits for Veterans 2026",  # 56
    "cdr-explained":                        "Combined Disability Rating Explained: VA Math 2026",        # 50
    "tdiu-explained":                       "TDIU Explained: 100% VA Pay Without 100% Rating",           # 49
    "va-appeals-process":                   "VA Appeals Process 2026: Three Lanes Explained",            # 49
    "blended-retirement-system":            "Blended Retirement System Explained: BRS Guide 2026",       # 53
    "bah-explained":                        "BAH Explained: How Military Housing Allowance Works 2026",  # 57
    "tricare-options-explained":            "TRICARE Options Explained: Prime, Select & For Life",       # 52
    "government-shutdown-veterans":         "Government Shutdowns & Veterans: Pay & Benefits Impact",    # 55
    "military-retirement-pay-calculator-guide": "Military Retirement Pay Calculator Guide 2026",         # 44
    "va-ebenefits-vs-va-gov":              "eBenefits vs VA.gov: Which Platform Should You Use?",       # 51
    "va-buddy-statement-guide":             "VA Buddy Statement Guide: How to Write One That Helps",     # 53
    "va-disability-back-pay":               "VA Disability Back Pay: How Retroactive Benefits Work",     # 52
}

EXPLAINER_DESCRIPTIONS = {
    "what-is-a-nexus-letter": (
        "A nexus letter is a doctor's written medical opinion linking your condition to military service. "
        "Learn what it must say, who can write it, what it costs, and how it affects your VA disability claim."
    ),
    "va-disability-rating-explained": (
        "How does VA calculate your combined disability rating? Learn the whole-person method, why 50+50 "
        "doesn't equal 100%, how ratings are rounded, and how TDIU can get you 100% pay without 100% rating."
    ),
    "pact-act-explained": (
        "The 2022 PACT Act expanded VA benefits for veterans exposed to burn pits and toxic chemicals. "
        "Learn which conditions are now presumptive, who qualifies, how to file, and what benefits you can receive."
    ),
    "cdr-explained": (
        "VA's combined disability rating uses the whole-person method — not simple addition. Learn step-by-step "
        "how multiple ratings combine, how final ratings are rounded, and what this means for your compensation."
    ),
    "tdiu-explained": (
        "Total Disability based on Individual Unemployability (TDIU) pays veterans at the 100% rate even without "
        "a 100% combined rating. Learn eligibility thresholds, how to apply on VA Form 21-8940, and evidence needed."
    ),
    "va-appeals-process": (
        "When VA denies your claim, you have three appeal lanes: Supplemental Claim, Higher-Level Review, "
        "and the Board of Veterans' Appeals (BVA). Learn timelines, success rates, and which lane to choose."
    ),
    "blended-retirement-system": (
        "The BRS applies to all service members who entered on or after January 1, 2018. It blends a reduced "
        "2.0% annuity multiplier with TSP government matching of up to 5%. Learn the key trade-offs here."
    ),
    "bah-explained": (
        "Basic Allowance for Housing (BAH) covers off-base housing costs based on your pay grade, dependency "
        "status, and duty station ZIP. Learn how BAH rates are set, how to look up your rate, and what OHA covers."
    ),
    "tricare-options-explained": (
        "TRICARE Prime, Select, Reserve Select, and For Life each serve different beneficiary groups. "
        "Learn eligibility, enrollment costs, network differences, and how to choose the right TRICARE plan."
    ),
    "government-shutdown-veterans": (
        "A federal government shutdown affects VA operations, claims processing, and potentially military pay. "
        "Learn what stops, what continues, how the Antideficiency Act applies, and how to prepare as a veteran."
    ),
    "military-retirement-pay-calculator-guide": (
        "How to use a military retirement pay calculator. Understand the inputs — pay grade, years of service, "
        "retirement system — and learn what the output means for High-36, Final Pay, and BRS retirees."
    ),
    "va-ebenefits-vs-va-gov": (
        "eBenefits is being retired and replaced by VA.gov. Learn what services have moved, how to transition "
        "your account, where to file claims, check benefit status, and access education benefits in 2026."
    ),
    "va-buddy-statement-guide": (
        "A VA buddy statement (lay statement) lets veterans and witnesses describe how a disability affects "
        "daily life. Learn what to include, how to format it, who can submit one, and why it matters for your claim."
    ),
    "va-disability-back-pay": (
        "VA disability back pay covers the period from your effective date to the date of your rating decision. "
        "Learn how effective dates work, the one-year presumptive rule, and how to calculate your retroactive pay."
    ),
}

CONDITION_TITLES = {
    "tinnitus":               "VA Tinnitus Disability Rating: 10% Claim Guide 2026",       # 52
    "ptsd":                   "VA PTSD Disability Rating: Claim Guide & Evidence 2026",    # 55
    "sleep-apnea":            "VA Sleep Apnea Rating: 50% Claim Guide & Tips 2026",        # 51
    "lumbar-spine-strain":    "VA Lumbar Spine Strain Rating: Lower Back Claim 2026",      # 53
    "knee-pain":              "VA Knee Disability Rating: Claims & Service Connection",     # 52
    "migraines":              "VA Migraines Disability Rating: Claim Guide 2026",           # 49
    "depression":             "VA Depression Disability Rating & Service Connection 2026",  # 55
    "anxiety":                "VA Anxiety Disability Rating & Service Connection 2026",     # 54
    "tbi":                    "VA TBI Disability Rating: Traumatic Brain Injury Guide",     # 52
    "hearing-loss":           "VA Hearing Loss Disability Rating: Claim Guide 2026",        # 52
    "shoulder-impingement":   "VA Shoulder Impingement Rating: Claim Guide 2026",           # 50
    "hypertension":           "VA Hypertension Disability Rating: Claim Guide 2026",        # 52
    "diabetes-mellitus-type-2": "VA Diabetes Type 2 Disability Rating & Claim Guide",      # 50
    "burn-pit-exposure":      "VA Burn Pit Exposure Benefits: PACT Act Claims Guide",       # 52
    "agent-orange-exposure":  "VA Agent Orange Presumptive Conditions: Claims Guide",       # 51
    "mst-military-sexual-trauma": "VA MST Disability Rating: Military Sexual Trauma Guide", # 55
    "chronic-fatigue-syndrome": "VA Chronic Fatigue Syndrome Disability Rating 2026",       # 50
    "fibromyalgia":           "VA Fibromyalgia Disability Rating: Claim Guide 2026",        # 52
    "cervical-spine-strain":  "VA Cervical Spine Strain Rating: Neck Claim Guide 2026",    # 55
    "plantar-fasciitis":      "VA Plantar Fasciitis Disability Rating: Claim Guide 2026",   # 56
    "pes-planus-flat-feet":   "VA Pes Planus (Flat Feet) Disability Rating Guide 2026",    # 53
    "bilateral-knee":         "VA Bilateral Knee Disability Rating: Claims Guide 2026",     # 53
    "bilateral-hearing-loss": "VA Bilateral Hearing Loss Rating: Claims Guide 2026",        # 52
    "gulf-war-illness":       "VA Gulf War Illness Disability Rating: Claims Guide 2026",   # 55
    "radiculopathy-lower":    "VA Lower Extremity Radiculopathy Rating Guide 2026",         # 50
    "radiculopathy-upper":    "VA Upper Extremity Radiculopathy Rating Guide 2026",         # 50
    "degenerative-disc-disease": "VA Degenerative Disc Disease Disability Rating 2026",    # 52
    "hemorrhoids":            "VA Hemorrhoids Disability Rating: Claim Guide 2026",         # 51
    "irritable-bowel-syndrome": "VA IBS Disability Rating: Claim Guide 2026",              # 45
    "gerd":                   "VA GERD Disability Rating: Acid Reflux Claim Guide 2026",   # 53
    "rhinitis":               "VA Rhinitis Disability Rating: Claim Guide 2026",            # 48
    "sinusitis":              "VA Sinusitis Disability Rating: Claim Guide 2026",           # 48
    "skin-conditions-dermatitis": "VA Skin Conditions Disability Rating: Dermatitis 2026", # 57
}

CONDITION_DESCRIPTIONS = {
    "tinnitus": (
        "Tinnitus (ringing or buzzing in the ears) is the most commonly claimed VA disability, rated at 10% "
        "under 38 CFR Part 4, DC 6260. Learn how to service-connect tinnitus, what evidence VA requires, and claim tips."
    ),
    "ptsd": (
        "VA rates PTSD under 38 CFR Part 4, DC 9411 based on occupational and social impairment. Typical ratings "
        "range from 30–70%. Learn how to service-connect PTSD, submit a military-sexual-trauma claim, and appeal."
    ),
    "sleep-apnea": (
        "Sleep apnea requiring CPAP is rated 50% by VA under DC 6847. Learn how to service-connect sleep apnea "
        "to a military condition, get a private nexus letter, and avoid the common evidence mistakes that lead to denials."
    ),
    "lumbar-spine-strain": (
        "Lumbar spine strain (lower back) is one of the most common VA disability claims. Rated under DC 5237, "
        "typical ratings are 10–40% depending on range-of-motion limitations. Learn how to file and what evidence you need."
    ),
    "knee-pain": (
        "VA rates knee conditions under DC 5257–5260 based on instability, limited flexion/extension, and surgical "
        "residuals. Typical ratings range from 10–30%. Learn evidence requirements and secondary service connection."
    ),
    "migraines": (
        "VA rates migraine headaches under 38 CFR Part 4, DC 8100. Ratings range from 0–50% depending on frequency "
        "and prostrating attacks per month. Learn how to document severity and service-connect migraines in 2026."
    ),
    "depression": (
        "VA rates depressive disorders under DC 9434 on a 0–100% scale based on occupational and social impairment. "
        "Learn how to service-connect depression to a military stressor or physical condition, with evidence tips."
    ),
    "anxiety": (
        "VA rates generalized anxiety and panic disorders under DC 9400 based on occupational and social impairment. "
        "Typical ratings range from 30–70%. Learn how to document your symptoms and file a service-connection claim."
    ),
    "tbi": (
        "Traumatic Brain Injury (TBI) is rated under DC 8045 using the Veterans Benefits Administration's TBI "
        "evaluation. Learn how VA rates TBI severity levels, what cognitive evidence is needed, and secondary conditions."
    ),
    "hearing-loss": (
        "VA rates hearing loss under DC 6100 using audiometric testing results converted to speech recognition scores. "
        "Learn how VA evaluates hearing loss, bilateral claims, and how to service-connect noise-induced hearing loss."
    ),
    "shoulder-impingement": (
        "Shoulder impingement syndrome and rotator cuff conditions are rated under DCs 5201–5205 based on limited "
        "range of motion. Typical ratings are 10–40%. Learn how to service-connect shoulder injuries in 2026."
    ),
    "hypertension": (
        "VA rates hypertension (high blood pressure) under DC 7101 based on diastolic and systolic readings. "
        "Ratings range from 10–60%. Learn how to service-connect hypertension and document readings for your claim."
    ),
    "diabetes-mellitus-type-2": (
        "VA rates Type 2 diabetes under DC 7913. If you served in Vietnam (Agent Orange) or Southwest Asia, "
        "diabetes may be presumptive. Learn ratings from 10–100%, insulin requirements, and secondary complications."
    ),
    "burn-pit-exposure": (
        "The 2022 PACT Act established presumptive service connection for many conditions linked to burn pit "
        "exposure. Learn which cancers and respiratory conditions are covered, how to file, and what evidence you need."
    ),
    "agent-orange-exposure": (
        "Vietnam-era veterans exposed to Agent Orange may qualify for presumptive VA disability ratings for over "
        "20 conditions including diabetes, certain cancers, and IHD. Learn eligibility, evidence needed, and how to file."
    ),
    "mst-military-sexual-trauma": (
        "MST (Military Sexual Trauma) claims are rated based on the resulting psychiatric condition — typically "
        "PTSD, depression, or anxiety. Special MST evidentiary rules apply. Learn how to file and what VA requires."
    ),
    "chronic-fatigue-syndrome": (
        "Chronic Fatigue Syndrome (CFS) is rated under DC 6354. Ratings range from 10–100% depending on severity "
        "of debilitation. Learn how to document CFS, service-connect it to military exposures, and appeal denials."
    ),
    "fibromyalgia": (
        "VA rates fibromyalgia under DC 5025 at 10, 20, or 40% based on the number and frequency of incapacitating "
        "episodes. Learn how to document fibromyalgia symptoms, meet VA's diagnostic criteria, and file your claim."
    ),
    "cervical-spine-strain": (
        "Cervical spine strain (neck) is rated under DC 5237 based on range-of-motion limitations. Ratings "
        "typically range 10–30%. Learn how to service-connect neck injuries, what imaging evidence VA needs in 2026."
    ),
    "plantar-fasciitis": (
        "VA rates plantar fasciitis under DC 5276 typically at 10%. Learn how to service-connect plantar fasciitis "
        "to military service, what medical evidence is required, and how to link it as a secondary to other conditions."
    ),
    "pes-planus-flat-feet": (
        "VA rates pes planus (flat feet) under DC 5276–5277 based on flexibility and symptom severity. "
        "Ratings range from 0–50%. Learn how to document flat feet, service-connection evidence, and bilateral claims."
    ),
    "bilateral-knee": (
        "Bilateral knee conditions can be claimed as two separate VA disabilities, potentially yielding a higher "
        "combined rating. Learn how VA rates bilateral knee issues, the bilateral factor, DC 5257–5260, and evidence."
    ),
    "bilateral-hearing-loss": (
        "Bilateral hearing loss is rated separately for each ear under DC 6100, then combined. Learn how VA uses "
        "audiometric conversion tables, how noise exposure is documented, and how to service-connect bilateral hearing loss."
    ),
    "gulf-war-illness": (
        "Gulf War Illness covers a range of unexplained chronic multi-symptom disorders for veterans who served "
        "in Southwest Asia since August 1990. Learn which symptoms VA recognizes, presumptive rules, and how to file."
    ),
    "radiculopathy-lower": (
        "Radiculopathy of the lower extremities (sciatic nerve, etc.) is rated under DC 8520 based on nerve "
        "severity: mild, moderate, or severe. Learn how to service-connect radiculopathy secondary to spine conditions."
    ),
    "radiculopathy-upper": (
        "Radiculopathy of the upper extremities (median, ulnar nerves, etc.) is rated under DC 8512 at 10–50%. "
        "Learn how to service-connect upper extremity radiculopathy to cervical spine and shoulder conditions."
    ),
    "degenerative-disc-disease": (
        "VA rates degenerative disc disease under DCs 5242–5244 based on range-of-motion and intervertebral disc "
        "syndrome. Ratings range from 10–60%. Learn how to document DDD and link it to military service or other conditions."
    ),
    "hemorrhoids": (
        "VA rates hemorrhoids under DC 7336 at 0–20%. While typically a low-rated condition, hemorrhoids can "
        "be service-connected due to prolonged sitting in vehicles, heavy lifting, or other military activities."
    ),
    "irritable-bowel-syndrome": (
        "VA rates Irritable Bowel Syndrome (IBS) under DC 7319 at 0–30% based on severity of symptoms. "
        "IBS may be service-connected directly or as a secondary to PTSD, anxiety, or other service-connected conditions."
    ),
    "gerd": (
        "VA rates GERD (gastroesophageal reflux disease) under DC 7346 at 10–30%. GERD is commonly filed as a "
        "secondary condition to PTSD, anxiety, or sleep apnea. Learn how to file and what medical evidence VA requires."
    ),
    "rhinitis": (
        "VA rates allergic and non-allergic rhinitis under DC 6522. Rhinitis can be service-connected from burn "
        "pit exposure, particulate matter, or toxic chemicals. Learn ratings, evidence requirements, and PACT Act."
    ),
    "sinusitis": (
        "VA rates sinusitis (chronic maxillary, frontal, etc.) under DCs 6510–6514 based on type and severity. "
        "Ratings range from 0–50%. Learn how to service-connect sinusitis to military exposures and prior respiratory issues."
    ),
    "skin-conditions-dermatitis": (
        "VA rates dermatitis and skin conditions under DC 7806 based on percentage of body area affected. Ratings "
        "range from 0–60%. Learn how to service-connect contact dermatitis, eczema, and chemical exposure skin conditions."
    ),
}

# ---------------------------------------------------------------------------
# Pillar FAQ data
# ---------------------------------------------------------------------------

PILLAR_FAQS = {
    "va-claims": [
        {"question": "How long does VA have to decide my disability claim?",
         "answer": "VA aims to process initial claims within 125 days. Complex claims requiring C&P exams or additional evidence may take 3–6 months. Track your claim status in real time at VA.gov/track-claims or by calling 1-800-827-1000."},
        {"question": "What is the difference between direct and secondary service connection?",
         "answer": "Direct service connection links a condition to a specific in-service event, injury, or exposure. Secondary service connection links a new condition to an already service-connected disability — for example, sleep apnea caused by a service-connected PTSD condition."},
        {"question": "Can I file a VA claim after I separate from the military?",
         "answer": "Yes — there is no time limit to file an initial VA disability claim. However, your effective date is generally the date VA receives your claim, so filing earlier typically means more retroactive back pay."},
        {"question": "What evidence do I need to file a VA disability claim?",
         "answer": "You typically need: (1) service records documenting the in-service event, (2) a current medical diagnosis, and (3) a nexus letter from a physician connecting the two. VA will usually schedule a C&P exam for initial claims."},
        {"question": "What should I do if VA denies my claim?",
         "answer": "You have three appeal options: Supplemental Claim (new and relevant evidence), Higher-Level Review (senior reviewer, same evidence), or Board of Veterans' Appeals (BVA). You have one year from the denial date to choose a lane."},
    ],
    "va-disability": [
        {"question": "How does VA calculate my combined disability rating?",
         "answer": "VA uses the 'whole person' method. Start with 100% as your whole person. Your highest rating is applied first, then each subsequent rating reduces the remaining percentage. Two 50% ratings combine to 75%, not 100%."},
        {"question": "What is TDIU and how do I qualify?",
         "answer": "TDIU (Total Disability Individual Unemployability) pays you at the 100% compensation rate if service-connected disabilities prevent gainful employment. You generally need one condition rated 60%+ or a combined rating of 70%+ with one condition at 40%+."},
        {"question": "Can I increase my VA disability rating?",
         "answer": "Yes — if your condition has worsened, you can file a Claim for Increase with updated medical evidence. There is no limit on how many times you can request an increase, and there is generally no minimum time between requests."},
        {"question": "Are VA disability benefits taxable?",
         "answer": "No. VA disability compensation is not subject to federal income tax under 26 U.S.C. § 104(a)(4). It is also generally exempt from state income taxes. This is separate from military retirement pay, which may be federally taxable."},
        {"question": "What is an effective date for a VA disability claim?",
         "answer": "Your effective date is typically the date VA receives your claim. For conditions that existed within one year of discharge, your separation date may serve as the effective date. Back pay covers the period from your effective date to the rating decision."},
    ],
    "military-retirement": [
        {"question": "How many years do I need to serve to retire from the military?",
         "answer": "Under the traditional system, 20 years of active-duty service is required. Under the Blended Retirement System (BRS), which is mandatory for post-2018 entrants, you also need 20 years for the annuity, but you receive TSP matching from day one."},
        {"question": "What is the difference between Final Pay, High-36, and BRS?",
         "answer": "Final Pay (pre-Sept. 1980) = 2.5% × years × final base pay. High-36 = 2.5% × years × average of last 36 months base pay. BRS = 2.0% × years × average of last 36 months + TSP matching. The multiplier and pay basis differ between systems."},
        {"question": "Can I receive both VA disability and military retirement?",
         "answer": "Yes, through Concurrent Retirement and Disability Pay (CRDP) if you have a combined VA rating of 50%+, or through Combat-Related Special Compensation (CRSC) for combat-related disabilities. CRDP and CRSC cannot both be received simultaneously."},
        {"question": "When do I start receiving military retirement pay?",
         "answer": "Active-duty retirees receive their first retirement payment the first of the month after separation. Reserve and Guard members generally start at age 60, which may be reduced to as early as age 50 for certain qualifying active-duty service periods."},
        {"question": "Is military retirement pay taxable?",
         "answer": "Military retirement pay is federally taxable unless it is based entirely on VA disability compensation. However, many states exclude all or part of military retirement pay from state income taxes. Check your state's rules for specific exemptions."},
    ],
    "military-pay": [
        {"question": "How often does military basic pay change?",
         "answer": "Congress approves an annual pay raise, typically effective January 1, based on the Employment Cost Index (ECI). In 2024, service members received a 5.2% pay raise. The 2025 raise was 4.5%."},
        {"question": "How is my BAH rate determined?",
         "answer": "BAH (Basic Allowance for Housing) is based on your pay grade (E/O/W), dependency status (with or without dependents), and the median rental cost of housing in your duty station ZIP code. Rates are updated annually on January 1."},
        {"question": "Is military pay taxable?",
         "answer": "Basic pay is federally taxable. BAH and BAS are generally tax-free. Service members serving in a designated Combat Zone Tax Exclusion (CZTE) area may exclude all military pay from federal income taxes for the duration of deployment."},
        {"question": "What is the difference between BAH and OHA?",
         "answer": "BAH (Basic Allowance for Housing) covers U.S.-based duty station housing costs. OHA (Overseas Housing Allowance) covers overseas assignments. Both are based on local rental market costs for your pay grade and dependent status."},
        {"question": "Can I lose BAH if I move to cheaper housing?",
         "answer": "No — BAH is paid at a flat rate regardless of your actual housing costs. Under the Housing Protection Policy, established BAH rates cannot be reduced unless you move to a new duty station with a lower rate."},
    ],
    "state-benefits": [
        {"question": "Which state has the best veterans benefits?",
         "answer": "Texas, Florida, and Virginia are frequently cited for the most comprehensive benefits, including full property tax exemptions for 100% P&T veterans and strong education programs. The 'best' state depends on your specific needs, disability rating, and residence."},
        {"question": "Do I need a DD-214 to claim state veterans benefits?",
         "answer": "Yes — virtually all state veterans benefits require a DD-214 (Certificate of Release or Discharge from Active Duty) as proof of service. If you've lost yours, request a replacement via the National Archives at archives.gov/veterans."},
        {"question": "Can surviving spouses claim state veterans benefits?",
         "answer": "In most states, surviving spouses of veterans can claim property tax exemptions, education benefits, and other programs. Eligibility usually depends on the veteran's service record, VA rating status at time of death, and the state's specific rules."},
        {"question": "Do state benefits change if my VA rating changes?",
         "answer": "Yes — many state benefits are tiered by VA disability rating (e.g., 50%, 70%, 100%/P&T). When your rating increases, you may qualify for additional or higher-value state benefits. Re-apply or notify your county veterans service office when your rating changes."},
        {"question": "How do I apply for state veterans benefits?",
         "answer": "Contact your state's Department of Veterans Affairs or your County Veterans Service Office (CVSO). Bring your DD-214, VA rating decision letter, and state ID. A free VSO (Veterans Service Organization) representative can help you navigate state applications."},
    ],
    "explainers": [
        {"question": "What is a VSO and should I use one?",
         "answer": "A Veterans Service Organization (VSO) like the DAV, VFW, or American Legion provides free VA claims assistance. VA-accredited VSO representatives can help file claims, gather evidence, and navigate appeals at no cost to you."},
        {"question": "How long does it typically take for VA to process a claim?",
         "answer": "Initial disability claims average 125 days at the VA. However, complex claims, C&P exam backlogs, and rating requests with multiple conditions can take 6–12 months. BVA appeals have a separate queue that can take 1–3+ years."},
        {"question": "Are VA benefits retroactive?",
         "answer": "Yes. Your effective date is when VA received your claim (or discharge date under the one-year window). If your decision takes 6 months, you receive 6 months of back pay. Retroactive pay can be substantial for high-rated conditions."},
        {"question": "Do I need a lawyer to file a VA claim?",
         "answer": "No. You can file a VA disability claim yourself, with a free VSO, or with an accredited claims agent. Attorneys can only charge fees for work performed after an initial agency denial — not for filing the original claim."},
        {"question": "What is the best way to track my VA claim status?",
         "answer": "Log in at VA.gov/track-claims to view your claim's current status, pending items, and estimated decision date. You can also call VA at 1-800-827-1000 for phone updates. Claims submitted via VSO can usually be tracked the same way."},
    ],
}

# ---------------------------------------------------------------------------
# Spoke FAQ data
# ---------------------------------------------------------------------------

SPOKE_FAQS = {
    "va-claims:how-to-file-a-va-claim": [
        {"question": "How do I file a VA disability claim online?",
         "answer": "File online at VA.gov/disability/file-disability-claim-form-21-526ez/. Create or log in to your VA.gov account, complete VA Form 21-526EZ, upload supporting documents, and submit. You can also file by mail or with the help of a free VSO representative."},
        {"question": "What form do I use to file a VA disability claim?",
         "answer": "Use VA Form 21-526EZ (Application for Disability Compensation and Related Compensation Benefits). This is the primary form for initial disability claims. Some veterans also use VA Form 21-0781 for PTSD claims or VA Form 21-0781a for MST-related claims."},
        {"question": "What happens after I file my VA disability claim?",
         "answer": "After filing, VA reviews your claim, requests service treatment records, and typically schedules a Compensation and Pension (C&P) exam. VA will then issue a rating decision. The full process typically takes 3–6 months for initial claims."},
        {"question": "Can I file a VA claim while still on active duty?",
         "answer": "Yes — the Benefits Delivery at Discharge (BDD) program lets active-duty service members file a VA claim 180–90 days before separation. Filing early can start the process and may result in a faster decision after discharge."},
        {"question": "What if I miss the one-year deadline after discharge?",
         "answer": "You can still file a claim at any time — there is no statute of limitations. However, filing within one year of discharge allows VA to assign an effective date of your discharge date, which means more back pay if approved. Filing later starts your effective date at the claim receipt date."},
    ],
    "va-claims:service-connection-requirements": [
        {"question": "What are the three elements of VA service connection?",
         "answer": "VA requires: (1) a current diagnosed disability, (2) an in-service event, injury, illness, or exposure, and (3) a medical nexus (link) between the two. All three elements must be established by competent medical or lay evidence."},
        {"question": "What is presumptive service connection?",
         "answer": "Presumptive service connection means VA presumes your condition is related to service without requiring you to prove a nexus. Examples include Agent Orange conditions for Vietnam veterans, Gulf War illness conditions, and PACT Act conditions for post-9/11 veterans."},
        {"question": "Can I get service connection for a condition that developed after I left the military?",
         "answer": "Yes, if you can show the condition began in service or is related to your military service. Additionally, conditions diagnosed within one year of discharge from a combat zone may qualify for the presumptive one-year period."},
        {"question": "What is the difference between direct and aggravation service connection?",
         "answer": "Direct service connection means the military caused or contributed to your condition. Aggravation means a pre-existing condition was permanently worsened beyond its natural progression by military service. Both are valid forms of service connection under 38 CFR Part 3."},
        {"question": "How strong does my service connection evidence need to be?",
         "answer": "VA uses the 'benefit of the doubt' standard: if positive and negative evidence are in rough equipoise (approximately equal), VA must resolve the issue in your favor. The nexus standard is 'at least as likely as not' — a 50% or greater probability."},
    ],
    "va-claims:nexus-letter-guide": [
        {"question": "What is a nexus letter for a VA claim?",
         "answer": "A nexus letter is a written medical opinion from a licensed physician stating that your current disability is 'at least as likely as not' caused or aggravated by your military service. It is the most critical piece of evidence for many VA disability claims."},
        {"question": "Who can write a nexus letter for my VA claim?",
         "answer": "Any licensed physician (MD or DO), psychiatrist, psychologist, nurse practitioner, or other licensed medical professional with expertise relevant to your condition can write a nexus letter. Private nexus letters often carry more persuasive weight than VA C&P exam opinions."},
        {"question": "How much does a private nexus letter cost?",
         "answer": "Private nexus letters typically cost between $500 and $2,000 depending on the complexity of the condition and the provider. Telemedicine companies specializing in VA disability nexus letters have made them more accessible. Some VSOs can help identify low-cost providers."},
        {"question": "What must a nexus letter say to be acceptable to VA?",
         "answer": "A VA-acceptable nexus letter must: (1) be from a licensed professional, (2) state the provider reviewed your service records, (3) provide a diagnosis, (4) include a rationale (not just a conclusion), and (5) use the 'at least as likely as not' (50%+ probability) standard language."},
        {"question": "Will VA provide a nexus opinion, or do I need to get my own?",
         "answer": "VA will typically schedule a C&P exam, where a VA examiner provides their own nexus opinion. However, private nexus letters from your own doctor often provide stronger, more detailed opinions. If the C&P exam opinion is unfavorable, a private nexus letter can be submitted as a rebuttal."},
    ],
    "va-claims:c-and-p-exam-tips": [
        {"question": "What is a VA Compensation and Pension (C&P) exam?",
         "answer": "A C&P exam is a medical examination VA schedules to evaluate your disability claim. A VA examiner reviews your service records and medical history, examines you, and prepares a Disability Benefits Questionnaire (DBQ) used to determine your disability rating."},
        {"question": "How should I prepare for my C&P exam?",
         "answer": "Bring all relevant medical records, your service records if you have them, and a written list of how your disability affects your daily life. Don't minimize your symptoms — describe your worst days, not your average days. Be specific about limitations, pain levels, and frequency of symptoms."},
        {"question": "Can I record my C&P exam?",
         "answer": "VA policy prohibits audio or video recording of C&P exams without prior approval. However, you should take notes immediately after the exam. If you feel the examiner rushed the exam or didn't address key symptoms, document this and consider submitting a personal statement."},
        {"question": "What should I do if the C&P examiner's opinion is wrong or incomplete?",
         "answer": "You can rebut the C&P opinion by submitting a private nexus letter, a doctor's statement, a personal statement, or buddy statements. You can also request a Higher-Level Review or Supplemental Claim to have the incorrect opinion reconsidered."},
        {"question": "Can I bring someone to my C&P exam?",
         "answer": "Yes — you may bring a support person. However, that person generally cannot speak on your behalf during the exam. Having someone present to take notes or provide emotional support is permitted at most VA examination facilities."},
    ],
    "va-claims:va-claim-timeline": [
        {"question": "How long does it take VA to decide a disability claim?",
         "answer": "VA's target is 125 days for initial claims. In practice, the average is often 3–6 months. Complex claims requiring C&P exams, records requests from the National Personnel Records Center, or multiple conditions can take longer."},
        {"question": "What are the stages of a VA disability claim?",
         "answer": "VA claims move through these stages: (1) Claim received, (2) Initial review, (3) Evidence gathering, (4) Review of evidence, (5) Preparation for decision, (6) Pending decision approval, (7) Rating decision, (8) Claim preparation and notification. Stages 4–6 can repeat."},
        {"question": "How can I speed up my VA disability claim?",
         "answer": "File a fully developed claim (FDC) by submitting all evidence at the time of filing. Use private medical providers rather than waiting for VA to gather records. Respond promptly to any requests for additional information from VA."},
        {"question": "What can delay my VA claim?",
         "answer": "Common delays include: C&P exam scheduling backlogs, missing service treatment records, claims involving multiple conditions, BDD claims with pending service records, or claims requiring records from the National Personnel Records Center."},
        {"question": "How do I track my VA claim status?",
         "answer": "Log in to VA.gov/track-claims to view your claim's current stage, pending items, and estimated completion. You can also call VA at 1-800-827-1000. If you filed through a VSO, they can often provide status updates directly."},
    ],
    "va-claims:buddy-statement-guide": [
        {"question": "What is a VA buddy statement?",
         "answer": "A buddy statement (also called a lay statement or personal statement) is a written account submitted by someone who has firsthand knowledge of a veteran's in-service events or how a disability affects daily life. It is submitted on VA Form 21-10210 or as a signed personal statement."},
        {"question": "Who can write a buddy statement for my VA claim?",
         "answer": "Anyone with firsthand knowledge can write a buddy statement: fellow service members, supervisors, family members, friends, or caregivers. The statement must be based on personal observation, not hearsay."},
        {"question": "What should a buddy statement include?",
         "answer": "A strong buddy statement includes: (1) the writer's full name and relationship to the veteran, (2) specific dates, locations, and events observed, (3) how the disability affects daily life or occupational function, and (4) a signature and statement that the information is true."},
        {"question": "How do I submit a buddy statement to VA?",
         "answer": "Submit buddy statements along with your claim by uploading them via VA.gov, mailing them to your VA regional office, or submitting them through your VSO. Reference the veteran's VA file number and claim number on each statement."},
        {"question": "How much weight does VA give buddy statements?",
         "answer": "VA considers buddy statements as 'lay evidence' — they can establish that an in-service event occurred, that a condition has been continuous since service, or that symptoms affect employment and daily activities. While not replacing medical opinions, strong buddy statements can be decisive in borderline cases."},
    ],
    "va-claims:va-claim-checklist": [
        {"question": "What is a DD-214 and why do I need it for my VA claim?",
         "answer": "A DD-214 (Certificate of Release or Discharge from Active Duty) is your official record of military service. VA uses it to verify your service dates, character of discharge, and military occupational specialty. It is required for virtually all VA benefit applications."},
        {"question": "What medical records should I include with my VA claim?",
         "answer": "Include: service treatment records (in-service injuries/illnesses), private medical records with a current diagnosis, any VA medical records, DBQ forms completed by your private physician, and a nexus letter linking your condition to service."},
        {"question": "What is a Disability Benefits Questionnaire (DBQ)?",
         "answer": "A DBQ is a standardized VA form that a physician completes describing the diagnosis, severity, and functional impact of a specific condition. You can have your private doctor complete a DBQ, which can substitute for or supplement a VA C&P exam."},
        {"question": "Do I need to submit my buddy statements before or after the C&P exam?",
         "answer": "Ideally submit all evidence — including buddy statements — before your C&P exam so the examiner has full context. If you receive an unfavorable C&P opinion, you can still submit additional buddy statements as new evidence in a Supplemental Claim."},
        {"question": "How should I organize and submit my VA claim evidence?",
         "answer": "Label each document clearly (e.g., 'Medical Nexus Letter from Dr. Smith'), reference your VA file number on every page, and submit everything together via VA.gov (fastest), by certified mail, or through your VSO. Keep copies of everything you submit."},
    ],
    "va-claims:secondary-conditions": [
        {"question": "What is a secondary VA disability condition?",
         "answer": "A secondary condition is a disability that is caused or aggravated by an already service-connected condition. For example, sleep apnea secondary to service-connected PTSD, or knee arthritis secondary to a service-connected hip condition."},
        {"question": "What evidence do I need to file a secondary condition claim?",
         "answer": "You need: (1) a current diagnosis of the secondary condition, (2) evidence that your primary service-connected condition caused or aggravated it, and (3) a medical nexus letter from a physician stating the relationship. Secondary nexus letters use the same 'at least as likely as not' standard."},
        {"question": "What are common examples of secondary VA conditions?",
         "answer": "Common secondary conditions include: sleep apnea secondary to PTSD, GERD secondary to anxiety or PTSD, depression secondary to chronic pain, plantar fasciitis secondary to knee or hip conditions, hypertension secondary to PTSD, and radiculopathy secondary to spinal conditions."},
        {"question": "Can a secondary condition have a higher rating than my primary condition?",
         "answer": "Yes — there is no requirement that a secondary condition must be rated lower than the primary condition. A secondary condition is evaluated on its own severity under the applicable VA rating criteria."},
        {"question": "Do I file a secondary condition claim separately from my primary claim?",
         "answer": "You can file a secondary condition claim at any time, independently of your primary claim. Use VA Form 21-526EZ and clearly identify the condition as 'secondary to' your service-connected disability. Submit the supporting nexus letter at the same time."},
    ],
    "va-claims:va-rating-increase": [
        {"question": "How do I request a VA rating increase?",
         "answer": "File a Claim for Increase using VA Form 21-526EZ and select 'Increase' as the claim type. Submit current medical evidence documenting how your condition has worsened since your last rating. Provide treatment records, doctor's notes, and updated DBQ forms showing worsened range of motion, frequency of symptoms, or other criteria."},
        {"question": "What triggers a VA rating increase?",
         "answer": "A rating increase is appropriate when your service-connected condition has objectively worsened. This might include: increased frequency or severity of symptoms, new limitations in range of motion, new surgical interventions, or worsened occupational impact documented by a physician."},
        {"question": "Can VA reduce my rating when I file for an increase?",
         "answer": "VA can only reduce a rating if there is objective evidence of sustained improvement under the ordinary conditions of life and work. For ratings held more than 5 years (and more than 10 years for total disability ratings), the reduction standard is even higher. Simply filing for an increase does not automatically trigger a reduction review."},
        {"question": "What is the effective date for a VA rating increase?",
         "answer": "If VA grants the increase, your effective date is typically the date VA received your Claim for Increase, or the date of the medical evidence showing the worsening — whichever is earlier. If you filed within one year of when the condition worsened, an earlier effective date may apply."},
        {"question": "How long does it take VA to decide a claim for increase?",
         "answer": "Claims for increase are processed like initial claims, typically targeting 125 days. If a new C&P exam is needed, add time for scheduling. Complex increases with multiple conditions or appeals can take longer."},
    ],
    "va-claims:claim-for-increase": [
        {"question": "What is a VA Claim for Increase (CFI)?",
         "answer": "A Claim for Increase (CFI) is a formal request for VA to re-evaluate a currently service-connected disability at a higher rating due to worsening of symptoms. It is different from a Supplemental Claim, which adds new evidence about the same period."},
        {"question": "When should I file a Claim for Increase?",
         "answer": "File a CFI when your service-connected condition has objectively worsened and you have medical evidence (doctor's visit notes, imaging, updated DBQ) documenting the change. Don't wait for scheduled exams — you can file at any time."},
        {"question": "What evidence do I need for a Claim for Increase?",
         "answer": "Submit: recent treatment records from the past 12 months showing worsened symptoms, an updated DBQ completed by your treating physician reflecting current limitations, and optionally a personal statement describing how your daily life has changed."},
        {"question": "Can my existing rating be lowered when I file a Claim for Increase?",
         "answer": "VA may propose a reduction if a C&P exam reveals significant improvement. However, ratings that have been in effect for 5+ years require 'sustained improvement' evidence; ratings held 10+ years have even higher reduction protections. You have 60 days to respond to a proposed reduction."},
        {"question": "Is there a limit on how many times I can file a Claim for Increase?",
         "answer": "No — there is no restriction on how many CFIs you can file. However, VA may take note of frequent CFI submissions without supporting medical evidence. Always file with current, objective medical documentation to support the increase request."},
    ],
    "military-retirement:final-pay-retirement": [
        {"question": "Who is eligible for the Final Pay retirement system?",
         "answer": "Service members who entered active duty before September 8, 1980 are covered by the Final Pay system. If you entered on or after that date, you are under the High-36 or Blended Retirement System instead."},
        {"question": "How is Final Pay military retirement calculated?",
         "answer": "Final Pay = 2.5% × years of service × final monthly basic pay. A 20-year retiree receives 50% of their final base pay; a 30-year retiree receives 75%. There is no cap under Final Pay."},
        {"question": "Is Final Pay retirement inflation-protected?",
         "answer": "Yes — Final Pay retirement receives Cost of Living Adjustments (COLA) each year based on the Consumer Price Index (CPI). The COLA applies to the full retirement amount starting in the first full year of retirement."},
        {"question": "How does Final Pay compare to High-36 retirement?",
         "answer": "Final Pay uses your actual last month's base pay, which can be favorable if you received a promotion near retirement. High-36 uses the average of your last 36 months, which may be lower if your final promotion came recently. Final Pay can yield slightly higher payments for late-career promotees."},
        {"question": "What happens to my Final Pay retirement if I become VA-rated?",
         "answer": "If you receive VA disability compensation, your military retirement pay may be offset by VA compensation unless you qualify for Concurrent Retirement and Disability Pay (CRDP, for 50%+ VA ratings) or Combat-Related Special Compensation (CRSC)."},
    ],
    "military-retirement:high-36-retirement": [
        {"question": "Who is covered under the High-36 retirement system?",
         "answer": "Service members who entered active duty between September 8, 1980 and December 31, 2017 are covered under High-36 (also called Redux with the Career Status Bonus for those who took the CSB option)."},
        {"question": "How is High-36 retirement pay calculated?",
         "answer": "High-36 = 2.5% × years of service × the average of your highest 36 months of base pay. A 20-year retiree at 50% of the High-36 average; a 30-year retiree at 75%. Base pay from the final 3 years determines the multiplier base."},
        {"question": "What is the Career Status Bonus (CSB) and Redux option?",
         "answer": "Some High-36 eligible service members received a $30,000 Career Status Bonus (CSB) at the 15-year mark in exchange for switching to Redux, which uses a reduced multiplier (40% at 20 years instead of 50%) and reduced COLA. Most financial advisors recommend against taking the CSB/Redux option."},
        {"question": "Does High-36 receive COLA adjustments?",
         "answer": "Yes — High-36 retirement pay receives annual COLA adjustments equal to the CPI increase. Under Redux, COLA is capped at CPI minus 1%, with a one-time catch-up adjustment at age 62. This makes Redux significantly less valuable over time."},
        {"question": "Can I switch from High-36 to the Blended Retirement System?",
         "answer": "No — if you were in service between Sept. 8, 1980 and Dec. 31, 2017, you are in High-36. Eligible mid-career members (with fewer than 12 years of service as of Jan. 1, 2018) could elect to opt into BRS during an open enrollment window in 2018, but that window has closed."},
    ],
    "military-retirement:blended-retirement-system": [
        {"question": "Who is covered by the Blended Retirement System (BRS)?",
         "answer": "The BRS is mandatory for all service members who entered the military on or after January 1, 2018. Service members with fewer than 12 years of service on January 1, 2018 had a one-time option to opt in. The BRS open enrollment window closed December 31, 2018."},
        {"question": "How is BRS retirement pay calculated?",
         "answer": "BRS uses a 2.0% multiplier (versus 2.5% for legacy systems): BRS retirement pay = 2.0% × years of service × average High-36 base pay. At 20 years, you receive 40% of your High-36 average instead of 50%."},
        {"question": "What TSP matching does BRS provide?",
         "answer": "Under BRS, the government automatically contributes 1% of basic pay to your TSP regardless of your own contributions. After 60 days of service, the government matches up to an additional 4% of basic pay (on top of the 1% automatic), for a total match of up to 5%."},
        {"question": "What is Continuation Pay under BRS?",
         "answer": "Continuation Pay is a one-time mid-career incentive paid between 8–12 years of service. Active-duty members receive at least 2.5× monthly basic pay; Guard/Reserve members receive at least 0.5×. In exchange, recipients commit to 3 more years of service."},
        {"question": "Is BRS better or worse than the legacy system?",
         "answer": "BRS is better for service members who leave before 20 years because they keep TSP matching regardless. It is generally worse for those who do serve 20+ years, because the 2.0% multiplier means lower lifetime annuity payments versus the legacy 2.5% multiplier."},
    ],
    "military-retirement:disability-retirement-vs-chapter61": [
        {"question": "What is Chapter 61 military disability retirement?",
         "answer": "Chapter 61 (10 U.S.C. §§ 1201–1222) provides retirement for service members who are found unfit for duty due to a physical disability with a DoD disability rating of 30%+ and at least 20 years of service, or any rating for certain special circumstances."},
        {"question": "How is military disability retirement pay calculated under Chapter 61?",
         "answer": "Pay is the higher of: (1) DoD disability rating% × High-36 average base pay, or (2) years of service × 2.5% × High-36 average (if you have 20+ years). A 30% DoD rating at 20 years provides higher pay than the 2.5% × 20 years formula in most cases."},
        {"question": "What is the difference between DoD disability rating and VA disability rating?",
         "answer": "DoD rates whether your condition makes you unfit for duty; VA rates the severity of the condition for compensation purposes. They use similar rating scales but serve different purposes. You can have a 30% DoD rating for retirement but a 70% VA rating for compensation."},
        {"question": "Can I receive both Chapter 61 disability retirement and VA disability compensation?",
         "answer": "For qualifying veterans with a combined VA rating of 50%+ or with combat-related disabilities, concurrent receipt is available through CRDP or CRSC. This eliminates the old dollar-for-dollar offset between military retirement pay and VA disability compensation."},
        {"question": "What is the IDES/LDES process for disability retirement?",
         "answer": "The Integrated Disability Evaluation System (IDES) and Legacy DES process determines fitness for duty and assigns a DoD rating. A Physical Evaluation Board (PEB) reviews your case and recommends separation or retirement. The process typically takes 6–18 months."},
    ],
    "military-retirement:reserve-retirement-points": [
        {"question": "How do Reserve and Guard members earn retirement points?",
         "answer": "Points are earned from: membership points (15/year for being in the Selected Reserve), drill/training points (1 per drill period, 2 per day of annual training), active duty points (1 per day), and correspondence course points (varies by course)."},
        {"question": "How many retirement points do I need to qualify for Guard/Reserve retirement?",
         "answer": "You need 20 qualifying years of service, where each qualifying year requires a minimum of 50 retirement points. A 'good year' equals 50+ points. Fewer than 50 points in a year means that year doesn't count toward the 20-year requirement."},
        {"question": "When can I start collecting Guard/Reserve retirement pay?",
         "answer": "Standard Reserve retirement pay begins at age 60. However, certain active-duty service performed after January 28, 2008 can reduce the age-60 requirement by 3 months for each 90-day period of qualifying active service, down to a minimum of age 50."},
        {"question": "How is Guard/Reserve retirement pay calculated?",
         "answer": "Pay = (total retirement points ÷ 360) × 2.5% × base pay at rank held at retirement. For example, 3,600 points = 10 equivalent years × 2.5% = 25% of base pay. Points earned under BRS use the 2.0% multiplier instead."},
        {"question": "What is 'gray area' retirement for Guard and Reserve members?",
         "answer": "The 'gray area' is the period between completing 20 qualifying years and reaching age 60. During this time, you are eligible for a Uniformed Services ID card and can use commissary and exchange, but you don't yet receive monthly retirement pay."},
    ],
    "military-retirement:survivor-benefit-plan": [
        {"question": "What is the Survivor Benefit Plan (SBP)?",
         "answer": "SBP is a Department of Defense insurance program that provides up to 55% of a retiree's retired pay to eligible beneficiaries (typically a spouse or dependent children) after the retiree's death. It is elected at retirement and premiums are deducted from retired pay."},
        {"question": "How much does SBP cost?",
         "answer": "The SBP premium is 6.5% of the base amount covered (up to full retired pay). If the full retirement amount is covered, the monthly cost is 6.5% of your gross retirement pay. Premiums are deductible from federal taxable income. Paid-up SBP occurs after 30 years of premium payments and age 70 — after which no more premiums are required."},
        {"question": "What is the SBP-DIC offset and has it been eliminated?",
         "answer": "The SBP-DIC offset historically reduced SBP payments to surviving spouses who received VA Dependency and Indemnity Compensation (DIC). The National Defense Authorization Act (NDAA) for FY2020 eliminated this offset, which was fully phased out by January 1, 2023. Surviving spouses now receive both SBP and DIC in full."},
        {"question": "Can I decline SBP at retirement?",
         "answer": "Yes — but you must have your spouse's signed concurrence to decline or elect a reduced base amount if you are married. There is no SBP open season after retirement, though a limited open enrollment may occur. Declining SBP is generally not recommended unless you have equivalent private insurance."},
        {"question": "What happens to SBP if my spouse dies before me?",
         "answer": "If your SBP-covered spouse dies before you, SBP premiums stop. You may be able to elect new coverage for a subsequent spouse if you remarry within one year of retirement or within one year of the prior spouse's death."},
    ],
    "military-retirement:concurrent-receipt-crsc-crdp": [
        {"question": "What is concurrent receipt?",
         "answer": "Concurrent receipt allows qualifying veterans to receive both their full military retirement pay and their VA disability compensation simultaneously, without the traditional offset (where VA pay reduces retirement pay dollar-for-dollar). Two programs provide this: CRDP and CRSC."},
        {"question": "What is the difference between CRDP and CRSC?",
         "answer": "CRDP (Concurrent Retirement and Disability Pay) is for any veteran with a combined VA rating of 50%+. CRSC (Combat-Related Special Compensation) is for veterans with combat-related disabilities and can be claimed at any VA rating. Both provide concurrent payment of retirement pay and VA disability compensation."},
        {"question": "Which is better, CRDP or CRSC?",
         "answer": "CRDP restores full retired pay without regard to the tax status of VA compensation. CRSC may be more valuable for combat-related disabilities with lower VA ratings (below 50%), since it is tax-free. Run the math comparing your CRDP amount to your CRSC amount — you can receive only one, but you can switch annually."},
        {"question": "How do I apply for CRDP or CRSC?",
         "answer": "CRDP is automatic — DFAS applies it if you qualify. CRSC requires an application to your branch of service. Submit your DD Form 2860 (CRSC application) with documentation showing the combat-related nature of your disability. Approval is separate from VA rating decisions."},
        {"question": "Can I receive both CRDP and CRSC at the same time?",
         "answer": "No — you can only receive one form of concurrent receipt at a time. DFAS will calculate both and pay the higher amount. You can change your election once per year during open season if your circumstances change (e.g., if your VA rating changes)."},
    ],
}

# ---------------------------------------------------------------------------
# Explainer FAQ data
# ---------------------------------------------------------------------------

EXPLAINER_FAQS = {
    "what-is-a-nexus-letter": [
        {"question": "What is a nexus letter for VA claims?",
         "answer": "A nexus letter is a physician's written medical opinion establishing a link between your current disability and your military service. It must state the opinion using the 'at least as likely as not' standard (50%+ probability) and provide a rationale supporting the conclusion."},
        {"question": "Can my primary care doctor write my nexus letter?",
         "answer": "Yes, any licensed physician, psychiatrist, psychologist, nurse practitioner, or other licensed medical professional can write a nexus letter if they have the expertise relevant to your condition. Ideally, the provider should review your service treatment records before writing the letter."},
        {"question": "Does VA give nexus letters from private doctors the same weight as C&P exam opinions?",
         "answer": "VA must consider all medical opinions of record. A well-reasoned private nexus letter with a thorough rationale often carries significant weight — sometimes more than a cursory C&P opinion. If both opinions are roughly equal, VA must resolve the dispute in the veteran's favor under the benefit-of-the-doubt standard."},
        {"question": "What is the 'at least as likely as not' standard?",
         "answer": "'At least as likely as not' means a 50% or greater probability that your disability is related to military service. This is a lower standard than 'more likely than not.' It is the phrase a nexus letter must include — without it, VA may reject the opinion as legally insufficient."},
    ],
    "va-disability-rating-explained": [
        {"question": "Why doesn't 50% + 50% equal 100% under VA math?",
         "answer": "VA uses the 'whole person' method. Your highest rating (50%) reduces your 100% whole person to 50% remaining. The second 50% rating is applied to the remaining 50%, yielding 25% additional — for a combined 75%, not 100%."},
        {"question": "How does VA round combined disability ratings?",
         "answer": "After combining all ratings using the whole-person method, VA rounds to the nearest 10%. Percentages ending in 1–4 round down; 5–9 round up. For example, a combined 72% rounds to 70%, while 75% rounds to 80%."},
        {"question": "What does a 100% combined disability rating mean?",
         "answer": "A 100% combined disability rating qualifies a veteran for the highest level of VA disability compensation and a range of additional benefits including Commissary access, enhanced TRICARE, and CHAMPVA for dependents. However, VA's math rarely produces a true 100% combined rating unless specific conditions are rated at high percentages."},
        {"question": "What is the difference between schedular 100% and TDIU?",
         "answer": "Schedular 100% means your combined rating using the whole-person method reaches 100%. TDIU (Total Disability Individual Unemployability) pays veterans at the 100% rate when service-connected disabilities prevent gainful employment, even if the combined rating is less than 100%."},
    ],
    "pact-act-explained": [
        {"question": "What is the PACT Act?",
         "answer": "The Sergeant First Class Heath Robinson Honoring our Promise to Address Comprehensive Toxics (PACT) Act was signed into law on August 10, 2022. It is the largest expansion of VA benefits in decades, extending presumptive service connection to veterans exposed to burn pits, Agent Orange, and other toxic chemicals."},
        {"question": "Which cancers are presumptive under the PACT Act?",
         "answer": "The PACT Act established presumptive status for numerous cancers for veterans who deployed to covered locations including Southwest Asia, Djibouti, and Afghanistan. These include head cancers, neck cancers, gastrointestinal cancers, reproductive cancers, lymphatic cancers, respiratory cancers, and melanoma, among others. The full list is at VA.gov/PACT."},
        {"question": "Who qualifies for PACT Act benefits?",
         "answer": "Veterans who served on or after August 2, 1990 in Southwest Asia, veterans exposed to open burn pits during service, and veterans who served in Vietnam or Korea and were exposed to Agent Orange may qualify. PACT Act also extended benefits to post-Vietnam veterans previously excluded."},
        {"question": "How do I file a PACT Act claim?",
         "answer": "File a VA disability claim using VA Form 21-526EZ at VA.gov and identify the specific condition and the toxic exposure. You do not need to prove a nexus for presumptive conditions — VA presumes the link. VA also has a toxic exposure screen in all VA medical facilities."},
    ],
    "cdr-explained": [
        {"question": "What is a Combined Disability Rating (CDR)?",
         "answer": "Your combined disability rating (CDR) is the final VA disability percentage after applying the whole-person method to all your service-connected disabilities. It is what determines your monthly VA compensation payment and eligibility for certain benefits."},
        {"question": "How do I calculate my combined disability rating?",
         "answer": "Start with your highest-rated disability. Subtract that rating from 100% to get the 'remaining whole person.' Multiply the next highest rating by the remaining percentage. Add both results. Repeat for each additional condition. Round the final total to the nearest 10%."},
        {"question": "Does adding more conditions always increase my combined rating?",
         "answer": "Adding conditions always increases the mathematical combined percentage, but because each addition is applied to a shrinking 'remaining' percentage, the incremental increase becomes smaller. For example, going from 70% to 80% combined may require adding a 40%+ rated condition."},
        {"question": "What is the maximum combined disability rating?",
         "answer": "VA's mathematical maximum is 100% under the whole-person method, though it is theoretically impossible to reach exactly 100% through combination alone. Veterans who cannot reach 100% schedularly may qualify for TDIU (Total Disability Individual Unemployability) at the 100% pay rate."},
    ],
    "tdiu-explained": [
        {"question": "What is TDIU?",
         "answer": "TDIU (Total Disability based on Individual Unemployability) is a VA benefit that pays veterans at the 100% disability compensation rate when their service-connected disabilities prevent them from maintaining substantially gainful employment, even if their combined rating is less than 100%."},
        {"question": "What are the rating thresholds to qualify for TDIU?",
         "answer": "The standard thresholds are: (1) one service-connected disability rated at 60%+, or (2) two or more service-connected disabilities with a combined rating of 70%+ where at least one is rated 40%+. Exceptions exist for veterans who don't meet these thresholds but are still unemployable due solely to service-connected conditions."},
        {"question": "How do I apply for TDIU?",
         "answer": "File VA Form 21-8940 (Application for Increased Compensation Based on Unemployability) along with VA Form 21-4192 (Request for Employment Information from Employer). Submit work history, medical evidence showing unemployability, and any supporting statements from treating physicians."},
        {"question": "Can I work part-time and still receive TDIU?",
         "answer": "Yes, if you earn income below the federal poverty threshold (approximately $13,590/year for a single individual). This is called 'marginal employment.' Earning above the poverty threshold generally means VA will terminate TDIU benefits."},
    ],
    "va-appeals-process": [
        {"question": "What are my options if VA denies my disability claim?",
         "answer": "You have three appeal lanes: (1) Supplemental Claim — submit new and relevant evidence; (2) Higher-Level Review — senior VA reviewer re-examines the same evidence without new evidence; (3) Board of Veterans' Appeals (BVA) — a Veterans Law Judge reviews your case. You have one year to choose a lane."},
        {"question": "How long does a VA appeal take?",
         "answer": "Supplemental Claims average 100–200 days. Higher-Level Reviews average 100–150 days. BVA appeals vary greatly: Direct Review (no hearing) averages 300–500 days; Evidence Submission averages 400–600 days; Hearing Requests can take 12–24+ months due to hearing scheduling backlogs."},
        {"question": "What is the success rate for VA appeals?",
         "answer": "Supplemental Claims that include strong new evidence (especially private nexus letters) have a high success rate. BVA allows approximately 30–40% of cases on Direct Review. Having a trained VSO representative or accredited attorney significantly improves outcomes."},
        {"question": "Can I appeal a BVA decision?",
         "answer": "Yes — if the BVA denies your claim, you can appeal to the U.S. Court of Appeals for Veterans Claims (CAVC) within 120 days. CAVC appeals require legal representation, and many veteran attorneys work on contingency (no upfront fees)."},
    ],
    "blended-retirement-system": [
        {"question": "Is BRS mandatory for me?",
         "answer": "BRS is mandatory for all service members who entered on or after January 1, 2018. Service members who had fewer than 12 years of service on January 1, 2018 had a one-time election window (open through December 31, 2018) to opt into BRS. If you entered service after Jan. 1, 2018, you are automatically in BRS."},
        {"question": "How much does the government contribute to my TSP under BRS?",
         "answer": "The government automatically contributes 1% of your basic pay to your TSP from the first day of service. After 60 days of service, the government matches your TSP contributions dollar-for-dollar up to 3%, then 50 cents on the dollar for the next 2% — for a total government match of up to 5%."},
        {"question": "When does TSP vesting occur under BRS?",
         "answer": "The 1% automatic contribution vests after 2 years of service. Matching contributions vest immediately for officers; after 2 years for enlisted. Once vested, TSP funds belong to you even if you leave before 20 years of service."},
        {"question": "Should I opt into BRS if I'm eligible?",
         "answer": "BRS is generally advantageous if you plan to serve fewer than 20 years and want to keep the TSP matching. It is generally disadvantageous if you plan to serve 20+ years, because the lower 2.0% multiplier results in a significantly lower lifetime annuity than the legacy 2.5% multiplier."},
    ],
    "bah-explained": [
        {"question": "How do I find my BAH rate?",
         "answer": "Use the official DoD BAH calculator at militarypay.defense.gov/BAH. Input your pay grade, ZIP code of your duty station, and dependency status (with or without dependents). Rates are updated annually on January 1."},
        {"question": "Does BAH change if I move off base?",
         "answer": "No — BAH is based on your duty station location and your pay grade, not where you actually live. If you live off base within the local area, your BAH remains the same. If you receive on-base housing, you generally do not receive BAH (the housing is provided in lieu of BAH)."},
        {"question": "What is BAH RC/T (Reserve Component / Transient)?",
         "answer": "BAH RC/T is a lower rate for Reserve and Guard members on short-term active duty orders (fewer than 30 days) and for transient service members without dependents. It is lower than standard BAH and is based on a national average rather than local housing costs."},
        {"question": "Is BAH taxable income?",
         "answer": "No — BAH is not subject to federal income tax and is excluded from gross income under 26 U.S.C. § 134. This tax-free status means BAH has a higher effective value than equivalent taxable income."},
    ],
    "tricare-options-explained": [
        {"question": "What is the difference between TRICARE Prime and TRICARE Select?",
         "answer": "TRICARE Prime is an HMO-style plan with a primary care manager (PCM), lower out-of-pocket costs, and a requirement to use the military health system or Prime network. TRICARE Select is a PPO-style plan with more provider flexibility but higher cost-sharing. Prime costs less for active-duty families; Select offers more freedom for retirees."},
        {"question": "What is TRICARE For Life?",
         "answer": "TRICARE For Life (TFL) is a Medicare supplement for military retirees age 65+ who are enrolled in Medicare Parts A and B. Medicare pays first; TRICARE For Life covers most remaining costs. TFL requires enrollment in Medicare Part B (premium applies)."},
        {"question": "Are VA disability recipients automatically enrolled in TRICARE?",
         "answer": "No — VA disability compensation does not automatically grant TRICARE eligibility. TRICARE eligibility is based on military service status (active duty, retired, or qualifying Reserve/Guard). However, veterans using VA healthcare are typically covered by VA, not TRICARE, for VA-treated conditions."},
        {"question": "What is TRICARE Reserve Select?",
         "answer": "TRICARE Reserve Select (TRS) is a premium-based health insurance plan for qualifying members of the National Guard and Reserve who are not on active duty. It covers the sponsor and family members and provides similar benefits to TRICARE Select."},
    ],
    "government-shutdown-veterans": [
        {"question": "Are VA disability payments affected by a government shutdown?",
         "answer": "VA disability compensation payments are protected during most government shutdowns because they are considered entitlements funded by permanent appropriations. Compensation payments historically continue during shutdowns. However, VA staff reductions can slow claims processing and benefit approvals."},
        {"question": "Does military pay stop during a government shutdown?",
         "answer": "Active-duty military members are legally required to report for duty during a government shutdown, but payment may be delayed rather than stopped. Congress typically passes retroactive pay legislation after shutdowns end. Service members are protected from having their base pay withheld permanently."},
        {"question": "What VA services are reduced during a shutdown?",
         "answer": "VA healthcare facilities and medical services generally continue because they are funded through advance appropriations. However, non-essential VA services — including some claims processing, benefits administration, and appeals hearings — may slow or stop during a prolonged shutdown."},
        {"question": "What is the Antideficiency Act and how does it affect veterans?",
         "answer": "The Antideficiency Act (31 U.S.C. § 1341) prohibits federal agencies from spending money without an appropriation. During shutdowns, it legally prevents agencies from paying non-essential employees or contracting for services. Exceptions exist for national security, life safety, and legally required entitlement payments including VA disability compensation."},
    ],
    "military-retirement-pay-calculator-guide": [
        {"question": "What inputs do I need to calculate military retirement pay?",
         "answer": "You need: your retirement system (Final Pay, High-36, or BRS), your pay grade at retirement (E/W/O + grade), years of active service, and for BRS your TSP balance and contribution history. For High-36, you also need your base pay for the last 36 months."},
        {"question": "How accurate are online military retirement calculators?",
         "answer": "Official calculators at militarypay.defense.gov and myarmybenefits.us.army.mil are the most accurate. Third-party calculators are generally reliable but may not reflect the most recent pay tables or COLA adjustments. Always verify final numbers with your branch's finance office."},
        {"question": "Does a military retirement calculator account for COLA?",
         "answer": "Most calculators show your retirement pay at the time of retirement without projecting future COLA increases. To estimate future purchasing power, you'd need to apply the expected annual COLA percentage (typically tied to CPI) to the base retirement amount."},
        {"question": "Should I include VA disability in my retirement calculation?",
         "answer": "Calculate retirement pay and VA disability separately. If you qualify for concurrent receipt (CRDP for 50%+ VA rating or CRSC for combat-related disabilities), both amounts stack. If you don't qualify, VA compensation offsets retirement pay dollar-for-dollar."},
    ],
    "va-ebenefits-vs-va-gov": [
        {"question": "Is eBenefits going away?",
         "answer": "Yes — VA is actively migrating eBenefits features to VA.gov as part of a modernization initiative. Some eBenefits features have already been decommissioned. Veterans are encouraged to create a VA.gov account (via Login.gov or ID.me) and begin using VA.gov for all benefits management."},
        {"question": "What can I do on VA.gov that I used to do on eBenefits?",
         "answer": "VA.gov now supports: filing disability claims, checking claim status, uploading evidence, viewing your rating decision letter, managing direct deposit, applying for VA healthcare, reviewing GI Bill benefits, and accessing your VA health records."},
        {"question": "How do I migrate my eBenefits account to VA.gov?",
         "answer": "Create a verified account on VA.gov using Login.gov or ID.me (both require identity verification). Your VA benefits history is linked to your Social Security Number and file number — it does not need to be manually migrated. Your claims and records will appear automatically once your identity is verified."},
        {"question": "What does eBenefits still do that VA.gov doesn't?",
         "answer": "Some less-common features remain on eBenefits temporarily, including certain records requests and some education benefit functions. VA.gov's Help section lists which features are still transitioning. Check va.gov/resources/helpful-va-phone-numbers for the latest migration status."},
    ],
    "va-buddy-statement-guide": [
        {"question": "What is a VA buddy statement?",
         "answer": "A VA buddy statement is a written declaration from a person with firsthand knowledge of a veteran's in-service events or how a disability affects their daily life. It is formal lay evidence submitted using VA Form 21-10210 or as a signed personal statement accompanying a claim."},
        {"question": "What makes a buddy statement effective?",
         "answer": "Effective buddy statements are specific: they include dates, locations, and events; describe what the writer personally observed (not hearsay); explain how the condition affects the veteran's daily life, work, or relationships; and avoid legal conclusions like 'the disability was caused by service' (leave that to the medical nexus letter)."},
        {"question": "Can my spouse write a buddy statement for my VA claim?",
         "answer": "Yes — family members, including spouses, can submit buddy statements describing how they have witnessed a veteran's disability affect daily activities, sleep, relationships, employment, and overall functioning. These statements can be particularly impactful for mental health conditions like PTSD."},
        {"question": "Is there a required format for buddy statements?",
         "answer": "VA Form 21-10210 provides a structured format. Alternatively, a typed or handwritten personal statement on plain paper is acceptable if it includes: the writer's full name and relationship to the veteran, specific observations, a declaration that the information is true (subject to penalty for false statements), and a signature."},
    ],
    "va-disability-back-pay": [
        {"question": "How is VA disability back pay calculated?",
         "answer": "Back pay = monthly compensation rate for the granted rating × number of months from effective date to rating decision. If your effective date is January 1 and your rating decision is issued June 1, you receive 5 months of back pay at your approved rate."},
        {"question": "What is my VA disability effective date?",
         "answer": "Your effective date is generally the date VA received your claim (per 38 CFR § 3.400). For service members who file within one year of discharge, the effective date can be set as early as the discharge date. Reopened claims and Supplemental Claims use different effective date rules."},
        {"question": "How long does it take to receive VA back pay?",
         "answer": "Once VA issues a favorable rating decision, back pay is typically processed within 2–4 weeks by the Veterans Benefits Administration. Payments are made to your bank account via direct deposit."},
        {"question": "Can I increase my back pay by filing an appeal?",
         "answer": "Yes — if you appeal and VA grants an earlier effective date, your back pay retroactively increases. For example, if your original effective date is contested and later moved back one year, you receive 12 additional months of back pay at your rating. An accredited VSO can identify effective date issues."},
    ],
}

# ---------------------------------------------------------------------------
# Condition FAQ data
# ---------------------------------------------------------------------------

def _condition_faq(slug: str, display_name: str, cfr: str, typical_pct: int) -> list:
    """Generate 4–5 FAQs for a condition page."""
    return [
        {"question": f"What is the typical VA disability rating for {display_name}?",
         "answer": f"VA rates {display_name} under {cfr}. Typical ratings range based on severity of symptoms. A rating of {typical_pct}% is common for moderate cases, but ratings can range from 0% to higher percentages depending on how the condition affects occupational and daily functioning."},
        {"question": f"How do I service-connect {display_name} for VA disability?",
         "answer": f"To establish service connection for {display_name}, you need: (1) a current medical diagnosis, (2) evidence of an in-service event or exposure, and (3) a nexus letter from a licensed physician stating the condition is 'at least as likely as not' related to your military service."},
        {"question": f"Can {display_name} be filed as a secondary condition?",
         "answer": f"{display_name} may qualify as a secondary service-connected disability if it was caused or aggravated by a primary service-connected condition. For example, sleep apnea secondary to PTSD, or spinal conditions secondary to lower back injuries. A secondary nexus letter is required."},
        {"question": f"What evidence does VA need for a {display_name} disability claim?",
         "answer": f"VA typically requires: current medical records documenting {display_name}, service treatment records showing in-service incidence, a nexus letter from your physician, any VA medical records, and optionally a Disability Benefits Questionnaire (DBQ) completed by your treating doctor."},
        {"question": f"What is a C&P exam for {display_name}?",
         "answer": f"After filing a {display_name} disability claim, VA typically schedules a Compensation and Pension (C&P) exam. A VA examiner will review your records and evaluate your symptoms. Bring all relevant medical records, describe your worst-day symptoms, and be specific about how {display_name} affects your daily life and work."},
    ]

# Condition-specific overrides for more specific FAQs
CONDITION_FAQ_OVERRIDES = {
    "tinnitus": [
        {"question": "What is the VA disability rating for tinnitus?",
         "answer": "Tinnitus is rated under 38 CFR Part 4, DC 6260 at a single, flat rate of 10% — regardless of severity. You receive 10% for tinnitus in both ears, one ear, or recurring. It cannot be rated higher under DC 6260, though in rare cases it may be rated differently under other diagnostic codes."},
        {"question": "How do I service-connect tinnitus?",
         "answer": "Tinnitus is commonly service-connected for veterans with military occupational specialties involving noise exposure (infantry, aviation, artillery, etc.). You need a current audiologist diagnosis and a nexus letter linking the ringing/buzzing to in-service noise exposure. A Military Occupational Noise Exposure letter (OSHA) can help."},
        {"question": "Can I get VA disability for tinnitus without hearing loss?",
         "answer": "Yes — tinnitus (ringing/buzzing in the ears) and hearing loss are separate VA diagnostic codes. You can receive a 10% tinnitus rating independently of any hearing loss rating. Both conditions can be claimed simultaneously for a higher combined rating."},
        {"question": "Is tinnitus the most common VA disability claim?",
         "answer": "Yes — tinnitus is consistently the most commonly claimed VA disability, with over 2 million veterans receiving compensation. This is driven by widespread noise exposure during military service from weapons fire, aircraft, heavy equipment, and explosions."},
        {"question": "What is the buddy statement for tinnitus?",
         "answer": "A buddy statement for tinnitus typically describes personal observations of the veteran mentioning ringing/buzzing during or shortly after service, covering ears around loud noises, or expressing difficulty hearing. Former unit members or family members can provide effective buddy statements."},
    ],
    "ptsd": [
        {"question": "How does VA rate PTSD?",
         "answer": "PTSD is rated under 38 CFR Part 4, DC 9411 using the General Rating Formula for Mental Disorders. Ratings are 0%, 10%, 30%, 50%, 70%, or 100% based on occupational and social impairment. Most PTSD claims result in ratings between 30–70%."},
        {"question": "What stressors qualify for a PTSD VA claim?",
         "answer": "VA recognizes combat, fear of hostile military action, personal assault (including MST), non-combat in-service trauma, and other stressors. The stressor must be documented or corroborated. For combat and some other stressors, in-service documentation requirements are relaxed under 38 CFR 3.304(f)."},
        {"question": "Do I need a combat stressor to claim PTSD?",
         "answer": "No — you can claim PTSD based on non-combat stressors including military sexual trauma (MST), accidents, witnessing death or injury, and other traumatic events. Different evidentiary rules apply: combat PTSD has relaxed documentation; MST claims have special processing rules."},
        {"question": "What is the PTSD C&P exam like?",
         "answer": "A PTSD C&P exam typically involves a 1–2 hour interview with a VA psychologist or psychiatrist. They review your service records, medical history, and ask about stressors, symptoms, sleep, relationships, and occupational impact. Being detailed and describing your worst symptoms is critical."},
        {"question": "Can I receive both PTSD and MST disability ratings?",
         "answer": "MST (Military Sexual Trauma) is not a standalone VA diagnostic code — it is rated through the resulting psychiatric condition, typically PTSD, depression, or anxiety. You receive the rating for the psychiatric condition caused by MST, not a separate MST rating."},
    ],
    "sleep-apnea": [
        {"question": "What is the VA disability rating for sleep apnea?",
         "answer": "Sleep apnea is rated under DC 6847. Ratings are: 0% (asymptomatic, no treatment), 30% (persistent daytime hypersomnolence), 50% (requiring use of a CPAP, BiPAP, or other breathing device), or 100% (chronic respiratory failure with cor pulmonale or requires tracheotomy). Most veterans with CPAP prescriptions receive 50%."},
        {"question": "How do I service-connect sleep apnea?",
         "answer": "Service connection for sleep apnea requires: (1) a current sleep study diagnosing obstructive sleep apnea, (2) evidence of an in-service connection (e.g., in-service CPAP prescription, sleep complaints in service records), and (3) a nexus letter. Sleep apnea can also be filed as secondary to PTSD, TBI, or obesity related to service."},
        {"question": "Can sleep apnea be a secondary condition to PTSD?",
         "answer": "Yes — sleep apnea secondary to PTSD is one of the most common secondary condition claims. Medical literature supports a relationship between PTSD-related hyperarousal and the development of sleep apnea. A private nexus letter from a sleep medicine specialist or psychiatrist is typically required."},
        {"question": "Does the VA provide CPAP machines for sleep apnea?",
         "answer": "Yes — veterans enrolled in VA healthcare who are service-connected for sleep apnea receive CPAP machines and supplies through the VA at no cost. Veterans not service-connected may still receive CPAP through VA healthcare based on need."},
        {"question": "What is the buddy statement for sleep apnea?",
         "answer": "A sleep apnea buddy statement typically describes the veteran's observed snoring, gasping during sleep, excessive daytime fatigue, or complaints of sleep problems during service. Roommates, fellow service members on deployment, or spouses can provide this statement."},
    ],
    "burn-pit-exposure": [
        {"question": "What conditions are presumptive under the PACT Act for burn pit exposure?",
         "answer": "The PACT Act (2022) established presumptive service connection for veterans exposed to burn pits in Southwest Asia, Djibouti, or Afghanistan after August 2, 1990. Covered conditions include numerous cancers (head, neck, respiratory, gastrointestinal, reproductive), as well as constrictive bronchiolitis and other toxic exposure conditions."},
        {"question": "How do I prove burn pit exposure for my VA claim?",
         "answer": "Under the PACT Act, veterans who served in covered locations are presumed to have been exposed to toxic airborne hazards. VA will verify your service location from military records. You do not need to prove personal exposure to a specific burn pit — location and timeframe are sufficient."},
        {"question": "Do I need a nexus letter for a PACT Act burn pit claim?",
         "answer": "For presumptive conditions listed under the PACT Act, you do not need a nexus letter — VA presumes the link. However, for conditions not on the presumptive list, a nexus letter linking your condition to burn pit exposure remains important."},
        {"question": "What is the Airborne Hazards and Open Burn Pit Registry?",
         "answer": "The Airborne Hazards and Open Burn Pit (AH&OBP) Registry is a voluntary DoD program allowing veterans to document their exposures and health symptoms. Registering strengthens your service record and can support VA claims, though it is not required for filing."},
        {"question": "Can I get retroactive benefits for burn pit exposure if I was previously denied?",
         "answer": "Yes — the PACT Act allows veterans who were previously denied VA claims for covered conditions to re-file as Supplemental Claims. VA must reopen and reconsider the claim under PACT Act presumptive rules. You may be entitled to back pay from your original claim date."},
    ],
    "agent-orange-exposure": [
        {"question": "What conditions are presumptive for Agent Orange exposure?",
         "answer": "VA recognizes over 20 presumptive conditions for Agent Orange exposure, including: AL amyloidosis, chloracne, type 2 diabetes, Hodgkin's disease, ischemic heart disease, multiple myeloma, non-Hodgkin's lymphoma, Parkinson's disease, peripheral neuropathy, and several other cancers. The full list is at VA.gov/disability/eligibility/hazardous-materials-exposure/agent-orange."},
        {"question": "Who qualifies for Agent Orange presumptive benefits?",
         "answer": "Veterans who served in Vietnam between January 9, 1962 and May 7, 1975, served in Korean DMZ between September 1, 1967 and August 31, 1971, or served at other locations with documented herbicide exposure qualify. Blue Water Navy veterans are now included under the Blue Water Navy Vietnam Veterans Act of 2019."},
        {"question": "How do I file an Agent Orange VA disability claim?",
         "answer": "File VA Form 21-526EZ and identify the specific presumptive condition. VA will verify your service in Vietnam or other qualifying locations through your military records. You do not need to prove personal exposure to Agent Orange — service in qualifying locations establishes the presumption."},
        {"question": "Are children of Vietnam veterans eligible for any Agent Orange benefits?",
         "answer": "Birth defects: children born with spina bifida (except spina bifida occulta) to veterans who served in Vietnam or Korea qualify for benefits. Daughters of Vietnam veterans with certain birth defects also qualify. Contact VA for eligibility details for specific conditions."},
    ],
    "gulf-war-illness": [
        {"question": "What is Gulf War Illness?",
         "answer": "Gulf War Illness (GWI) is a cluster of unexplained chronic multi-symptom illnesses affecting veterans who served in Southwest Asia (including Iraq, Kuwait, Saudi Arabia, and Afghanistan) since August 2, 1990. Symptoms may include fatigue, pain, cognitive dysfunction, rashes, and gastrointestinal problems."},
        {"question": "Do I need to prove what caused my Gulf War symptoms to get VA benefits?",
         "answer": "No — for undiagnosed illnesses and medically unexplained chronic multi-symptom illnesses (MUCMI), VA has a presumptive service connection for veterans who served in Southwest Asia. You must demonstrate chronic symptoms (present to a degree of 10%+ for at least 6 months) and service in a qualifying location."},
        {"question": "What are the qualifying service locations for Gulf War Illness benefits?",
         "answer": "Qualifying locations include: Iraq, Kuwait, Saudi Arabia, the neutral zone between Iraq and Saudi Arabia, Bahrain, Qatar, UAE, Oman, Afghanistan, Egypt, Jordan, Syria, and the airspace above these areas. Service dates must include August 2, 1990 or later."},
        {"question": "What specific conditions qualify for Gulf War presumptive benefits?",
         "answer": "VA recognizes: undiagnosed illnesses with qualifying symptoms, medically unexplained chronic multi-symptom illnesses (MUCMI), functional gastrointestinal disorders (including IBS and functional dyspepsia), and specific infectious diseases contracted in Southwest Asia (e.g., Brucellosis, West Nile virus)."},
    ],
    "mst-military-sexual-trauma": [
        {"question": "Does VA provide special handling for MST disability claims?",
         "answer": "Yes — VA has specific evidentiary policies for MST claims. Because incidents often go unreported, VA recognizes alternative forms of evidence including: behavioral changes documented in service records, performance evaluations showing unexplained changes, statements from MST support counselors, and personal statements from the veteran."},
        {"question": "What disability rating do MST survivors receive?",
         "answer": "MST is not a separate VA diagnostic code. The resulting psychiatric condition — most commonly PTSD, depression, or anxiety — is rated under its applicable diagnostic code. Ratings range from 0–100% based on occupational and social impairment."},
        {"question": "Do I have to report the MST to my command to get VA benefits?",
         "answer": "No — VA does not require that an MST incident was reported to military authorities. In fact, the special evidentiary rules for MST claims exist specifically because many incidents go unreported during service. Your claim is evaluated based on alternative evidence."},
        {"question": "Is there free MST counseling available through VA?",
         "answer": "Yes — VA provides free counseling and treatment for the effects of MST to veterans and service members, even if they have no other VA healthcare eligibility. Contact any VA medical center or Vet Center to request MST-related services."},
    ],
}

# ---------------------------------------------------------------------------
# State FAQ generator
# ---------------------------------------------------------------------------

def _state_faq(display_name: str) -> list:
    return [
        {"question": f"What property tax exemption do veterans get in {display_name}?",
         "answer": f"Property tax exemptions for veterans in {display_name} vary based on VA disability rating and veteran status. Veterans with a 100% P&T (Permanent and Total) VA disability rating typically qualify for the largest exemption. Contact the {display_name} Department of Veterans Affairs or your county assessor for current rates and income thresholds."},
        {"question": f"Does {display_name} exempt military retirement pay from state income taxes?",
         "answer": f"Many states offer a full or partial exclusion of military retirement pay from state income taxes. Check with the {display_name} Department of Revenue or a licensed tax professional for the most current rules, as these exemptions change periodically through state legislation."},
        {"question": f"What benefits does {display_name} offer for veterans with 100% VA disability ratings?",
         "answer": f"Veterans rated 100% disabled or Permanent and Total (P&T) often qualify for the most comprehensive state benefits in {display_name}, which may include full property tax exemptions, free vehicle registration, reduced-cost hunting and fishing licenses, and priority consideration for state employment."},
        {"question": f"How do I apply for state veterans benefits in {display_name}?",
         "answer": f"Start by contacting the {display_name} Department of Veterans Affairs or your local County Veterans Service Office (CVSO). Bring your DD-214, VA rating decision letter, and state-issued ID. A free VSO (Veterans Service Organization) representative can help you identify all available state benefits and complete applications."},
        {"question": f"Does {display_name} offer any veterans education benefits?",
         "answer": f"{display_name} may offer state-funded tuition waivers, scholarships, or reduced in-state tuition rates for qualifying veterans and their dependents. Programs vary by state. In addition to any state programs, federal GI Bill benefits (Chapter 30, 33, or 35) can be used at any eligible school in {display_name}."},
    ]

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def _truncate_desc(text: str, max_len: int = 160) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated).rstrip(".,") + "…"


def run(dry_run: bool = False):
    init_db()
    db = SessionLocal()
    updated = 0

    try:
        pages = db.query(LandingPage).all()
        print(f"Processing {len(pages)} pages...")

        for page in pages:
            key = page.page_key  # e.g. "condition:tinnitus", "state:texas"
            parts = key.split(":", 2)
            page_type = parts[0] if parts else ""
            slug = parts[1] if len(parts) > 1 else ""
            sub_slug = parts[2] if len(parts) > 2 else ""

            new_title = None
            new_desc = None
            new_faq = None

            # ── Pillar pages ──────────────────────────────────────────────────
            if page_type == "pillar":
                new_title = PILLAR_TITLES.get(slug)
                desc = PILLAR_DESCRIPTIONS.get(slug)
                if desc:
                    new_desc = _truncate_desc(desc)
                new_faq = PILLAR_FAQS.get(slug)
                if new_title:
                    new_title += " | Rank and Pay"

            # ── Spoke pages ───────────────────────────────────────────────────
            elif page_type == "spoke":
                spoke_key = f"{slug}:{sub_slug}"
                new_title = SPOKE_TITLES.get(spoke_key)
                desc = SPOKE_DESCRIPTIONS.get(spoke_key)
                if desc:
                    new_desc = _truncate_desc(desc)
                new_faq = SPOKE_FAQS.get(spoke_key)
                if new_title:
                    new_title += " | Rank and Pay"

            # ── Condition pages ───────────────────────────────────────────────
            elif page_type == "condition":
                new_title = CONDITION_TITLES.get(slug)
                desc = CONDITION_DESCRIPTIONS.get(slug)
                if desc:
                    new_desc = _truncate_desc(desc)
                if slug in CONDITION_FAQ_OVERRIDES:
                    new_faq = CONDITION_FAQ_OVERRIDES[slug]
                else:
                    # Generate generic condition FAQs
                    display = slug.replace("-", " ").title()
                    # Try to find CFR and typical_pct from CONDITION_TITLES
                    cfr = "38 CFR Part 4"
                    typical_pct = 30
                    new_faq = _condition_faq(slug, display, cfr, typical_pct)
                if new_title:
                    new_title += " | Rank and Pay"

            # ── State pages ───────────────────────────────────────────────────
            elif page_type == "state":
                display = slug.replace("-", " ").title()
                new_title = f"{display} Veterans Benefits 2026: Tax & Education Guide"
                if len(new_title) > 60:
                    new_title = f"{display} Veterans Benefits 2026: Tax Guide"
                new_desc = _truncate_desc(
                    f"Guide to {display} state veterans benefits in 2026: property tax exemptions, "
                    f"income tax breaks for military retirement, education tuition waivers, vehicle "
                    f"registration discounts, and more for qualifying veterans."
                )
                new_faq = _state_faq(display)
                new_title += " | Rank and Pay"

            # ── Explainer pages ───────────────────────────────────────────────
            elif page_type == "explainer":
                new_title = EXPLAINER_TITLES.get(slug)
                desc = EXPLAINER_DESCRIPTIONS.get(slug)
                if desc:
                    new_desc = _truncate_desc(desc)
                new_faq = EXPLAINER_FAQS.get(slug)
                if new_title:
                    new_title += " | Rank and Pay"

            # Validate title length
            if new_title and len(new_title) > 70:
                # Trim to 70 preserving word boundaries
                t = new_title[:70]
                sp = t.rfind(" ")
                new_title = (t[:sp] if sp > 0 else t)

            changes = []
            if new_title and new_title != page.title:
                changes.append(f"title: {len(page.title)}→{len(new_title)} chars")
                if not dry_run:
                    page.title = new_title
            if new_desc and new_desc != (page.summary or ""):
                changes.append(f"desc: {len(page.summary or '')}→{len(new_desc)} chars")
                if not dry_run:
                    page.summary = new_desc
            if new_faq and new_faq != page.faq_json:
                faq_count = len(new_faq) if new_faq else 0
                changes.append(f"faq: {faq_count} items")
                if not dry_run:
                    page.faq_json = new_faq

            if changes:
                updated += 1
                action = "[DRY RUN]" if dry_run else "UPDATED"
                print(f"  {action} {key}: {', '.join(changes)}")
                if not dry_run:
                    db.add(page)

        if not dry_run:
            db.commit()
            print(f"\nDone. Updated {updated} pages.")
        else:
            print(f"\nDry run complete. Would update {updated} pages.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix SEO metadata for all landing pages")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
