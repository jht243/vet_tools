"""
inject_links.py — Inject actionable hyperlinks into body_html of all LandingPage rows.

Runs substitutions (most-specific first) to avoid double-linking.
"""

import sys
import re

sys.path.insert(0, '.')
from src.models import SessionLocal, LandingPage  # noqa: E402

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def link_phrase(html: str, phrase: str, url: str, attrs: str = "", max_subs: int = 1) -> tuple[str, int]:
    """Replace up to max_subs occurrences of phrase (case-insensitive) that are
    NOT already inside an <a> tag.  Returns (new_html, substitution_count)."""
    if not html or phrase.lower() not in html.lower():
        return html, 0

    # Split into <a>…</a> blocks vs plain text; only replace in plain-text chunks.
    parts = re.split(r'(<a\b[^>]*>.*?</a>)', html, flags=re.DOTALL | re.IGNORECASE)
    count = 0
    result = []
    for part in parts:
        if count >= max_subs:
            result.append(part)
            continue
        if re.match(r'<a\b', part, flags=re.IGNORECASE):
            result.append(part)
            continue
        # Replace in this non-anchor chunk
        def replacer(m, _count_ref=[count]):
            nonlocal count
            if count >= max_subs:
                return m.group(0)
            count += 1
            extra = f' {attrs}' if attrs else ''
            return f'<a href="{url}"{extra}>{m.group(0)}</a>'
        part = re.sub(re.escape(phrase), replacer, part, flags=re.IGNORECASE)
        result.append(part)
    return ''.join(result), count


def link_pattern(html: str, pattern: str, url: str, attrs: str = "", max_subs: int = 1) -> tuple[str, int]:
    """Like link_phrase but takes a raw regex pattern (for word-boundary cases)."""
    if not html:
        return html, 0

    parts = re.split(r'(<a\b[^>]*>.*?</a>)', html, flags=re.DOTALL | re.IGNORECASE)
    count = 0
    result = []
    for part in parts:
        if count >= max_subs:
            result.append(part)
            continue
        if re.match(r'<a\b', part, flags=re.IGNORECASE):
            result.append(part)
            continue

        def replacer(m):
            nonlocal count
            if count >= max_subs:
                return m.group(0)
            count += 1
            extra = f' {attrs}' if attrs else ''
            return f'<a href="{url}"{extra}>{m.group(0)}</a>'
        part = re.sub(pattern, replacer, part, flags=re.IGNORECASE)
        result.append(part)
    return ''.join(result), count


# ---------------------------------------------------------------------------
# Substitution table  (applied in order — most specific first)
# ---------------------------------------------------------------------------
EXT = 'target="_blank" rel="noopener noreferrer"'

SUBSTITUTIONS = [
    # ── VA Forms (max_subs=3 so users can easily find form numbers) ─────────
    ("phrase", "VA Form 21-8940",   "https://www.va.gov/find-forms/about-form-21-8940/",  EXT, 3),
    ("phrase", "Form 21-8940",      "https://www.va.gov/find-forms/about-form-21-8940/",  EXT, 3),
    ("phrase", "VA Form 21-526EZ",  "https://www.va.gov/find-forms/about-form-21-526ez/", EXT, 3),
    ("phrase", "Form 21-526EZ",     "https://www.va.gov/find-forms/about-form-21-526ez/", EXT, 3),
    ("phrase", "VA Form 21-0781",   "https://www.va.gov/find-forms/about-form-21-0781/",  EXT, 3),
    ("phrase", "VA Form 21-4142",   "https://www.va.gov/find-forms/about-form-21-4142/",  EXT, 3),
    ("phrase", "VA Form 21-10210",  "https://www.va.gov/find-forms/about-form-21-10210/", EXT, 3),
    ("phrase", "VA Form 21-0966",   "https://www.va.gov/find-forms/about-form-21-0966/",  EXT, 3),
    ("phrase", "VA Form 10-10EZ",   "https://www.va.gov/find-forms/about-form-10-10ez/",  EXT, 3),

    # ── Decision review lanes ───────────────────────────────────────────────
    ("phrase", "Supplemental Claim",                 "https://www.va.gov/decision-reviews/supplemental-claim/",  EXT, 1),
    ("phrase", "Higher-Level Review",                "https://www.va.gov/decision-reviews/higher-level-review/", EXT, 1),
    ("phrase", "Higher Level Review",                "https://www.va.gov/decision-reviews/higher-level-review/", EXT, 1),
    ("phrase", "Board Appeal",                       "https://www.va.gov/decision-reviews/board-appeal/",        EXT, 1),
    ("phrase", "Board of Veterans' Appeals",         "https://www.bva.va.gov/",                                  EXT, 1),
    ("phrase", "Board of Veterans Appeals",          "https://www.bva.va.gov/",                                  EXT, 1),
    ("phrase", "Court of Appeals for Veterans Claims", "https://www.uscourts.cavc.gov/",                         EXT, 1),
    ("phrase", "CAVC",                               "https://www.uscourts.cavc.gov/",                           EXT, 1),

    # ── VA resources ────────────────────────────────────────────────────────
    ("phrase", "VA regional office",        "https://www.va.gov/find-locations/",                        EXT, 1),
    ("phrase", "VA Regional Office",        "https://www.va.gov/find-locations/",                        EXT, 1),
    ("phrase", "Compensation and Pension exam", "https://www.va.gov/disability/va-claim-exam/",          EXT, 1),
    ("phrase", "C&amp;P exam",              "https://www.va.gov/disability/va-claim-exam/",               EXT, 1),
    ("phrase", "C&P exam",                  "https://www.va.gov/disability/va-claim-exam/",               EXT, 1),
    ("phrase", "Intent to File",            "https://www.va.gov/resources/your-intent-to-file-a-va-claim/",       EXT, 1),
    ("phrase", "intent to file",            "https://www.va.gov/resources/your-intent-to-file-a-va-claim/",       EXT, 1),
    ("phrase", "find a VSO",                "https://www.va.gov/vso/",                                    EXT, 1),
    ("phrase", "find an accredited VSO",    "https://www.va.gov/ogc/apps/accreditation/index.asp",       EXT, 1),
    ("phrase", "accredited claims agent",   "https://www.va.gov/ogc/apps/accreditation/index.asp",       EXT, 1),
    ("phrase", "VR&amp;E",                  "https://www.va.gov/careers-employment/vocational-rehabilitation/", EXT, 1),
    ("phrase", "Vocational Rehabilitation", "https://www.va.gov/careers-employment/vocational-rehabilitation/", EXT, 1),
    ("phrase", "Post-9/11 GI Bill",         "https://www.va.gov/education/about-gi-bill-benefits/post-9-11/", EXT, 1),
    ("phrase", "GI Bill",                   "https://www.va.gov/education/about-gi-bill-benefits/",      EXT, 1),
    ("phrase", "VA health care",            "https://www.va.gov/health-care/",                            EXT, 1),
    ("phrase", "VA healthcare",             "https://www.va.gov/health-care/",                            EXT, 1),
    ("phrase", "TRICARE",                   "https://www.tricare.mil/",                                   EXT, 1),
    ("phrase", "eBenefits",                 "https://www.va.gov/resources/ebenefits-to-vagov-migration-frequently-asked-questions/", EXT, 1),
    ("phrase", "MyPay",                     "https://mypay.dfas.mil/",                                    EXT, 1),
    ("phrase", "DFAS",                      "https://www.dfas.mil/",                                      EXT, 1),

    # ── Internal links ──────────────────────────────────────────────────────
    ("phrase", "nexus letter",              "/explainers/what-is-a-nexus-letter/",      "", 1),
    ("phrase", "Nexus Letter",              "/explainers/what-is-a-nexus-letter/",      "", 1),
    ("phrase", "TDIU",                      "/explainers/tdiu-explained/",              "", 2),
    ("phrase", "Individual Unemployability","/explainers/tdiu-explained/",              "", 1),
    ("phrase", "buddy statement",           "/explainers/va-buddy-statement-guide/",    "", 1),
    ("phrase", "Buddy Statement",           "/explainers/va-buddy-statement-guide/",    "", 1),
    ("phrase", "VA back pay",               "/explainers/va-disability-back-pay/",      "", 1),
    ("phrase", "effective date",            "/explainers/va-disability-back-pay/",      "", 1),
    ("phrase", "PACT Act",                  "/explainers/pact-act-explained/",          "", 1),
    ("phrase", "Blended Retirement System", "/explainers/blended-retirement-system/",   "", 1),
    # BRS: word-boundary pattern only
    ("pattern", r"\bBRS\b",                "/explainers/blended-retirement-system/",   "", 1),
    ("phrase", "CRSC",                     "/tools/crsc-crdp-calculator/",             "", 1),
    ("phrase", "CRDP",                     "/tools/crsc-crdp-calculator/",             "", 1),
    ("phrase", "VA combined rating calculator", "/tools/va-disability-rating-calculator/", "", 1),
    ("phrase", "combined rating calculator",    "/tools/va-disability-rating-calculator/", "", 1),
    ("phrase", "secondary conditions",     "/tools/secondary-conditions-lookup/",      "", 1),
    ("phrase", "secondary service-connected", "/tools/secondary-conditions-lookup/",   "", 1),
    ("phrase", "BAH calculator",           "/tools/bah-calculator/",                   "", 1),
    ("phrase", "retirement pay calculator","/tools/military-retirement-calculator/",   "", 1),
    ("phrase", "military pay calculator",  "/tools/military-pay-calculator/",          "", 1),
]

# Internal-link phrases that should be skipped for state pages
INTERNAL_PHRASES = {
    "nexus letter", "Nexus Letter", "TDIU", "Individual Unemployability",
    "buddy statement", "Buddy Statement", "VA back pay", "effective date",
    "PACT Act", "Blended Retirement System", r"\bBRS\b", "CRSC", "CRDP",
    "VA combined rating calculator", "combined rating calculator",
    "secondary conditions", "secondary service-connected", "BAH calculator",
    "retirement pay calculator", "military pay calculator",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    db = SessionLocal()
    try:
        pages = db.query(LandingPage).filter(
            LandingPage.body_html.isnot(None),
            LandingPage.body_html != ""
        ).all()

        print(f"Found {len(pages)} pages with body_html.\n")

        total_pages_updated = 0
        total_injections = 0

        for page in pages:
            is_state = getattr(page, 'page_type', None) == 'state'
            page_injections = 0
            html = page.body_html

            for sub in SUBSTITUTIONS:
                kind, phrase, url, attrs, max_subs = sub

                # Skip internal links for state pages
                if is_state and phrase in INTERNAL_PHRASES:
                    continue

                if kind == "pattern":
                    new_html, cnt = link_pattern(html, phrase, url, attrs, max_subs)
                else:
                    new_html, cnt = link_phrase(html, phrase, url, attrs, max_subs)

                if cnt:
                    html = new_html
                    page_injections += cnt

            if page_injections > 0:
                page.body_html = html
                total_pages_updated += 1
                total_injections += page_injections
                page_key = getattr(page, 'page_key', getattr(page, 'slug', str(page.id)))
                print(f"  {page_key}: {page_injections} injection(s)")

        db.commit()
        print(f"\n--- Summary ---")
        print(f"Total pages updated:   {total_pages_updated}")
        print(f"Total link injections: {total_injections}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
