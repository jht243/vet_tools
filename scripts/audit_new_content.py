"""One-off audit of newly created SEO content pages.

Checks four things per page:
  1. Metadata lengths  - SEO <title> and meta description from rendered HTML.
  2. FAQ JSON schema    - faq_json is a list of {question, answer} dicts.
  3. Internal linking   - every href="/..." in body resolves 200 on the server.
  4. schema.org JSON-LD - rendered JSON-LD parses and has expected @types.

Run: .venv/bin/python -m scripts.audit_new_content
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error

from src.models import SessionLocal, LandingPage

BASE = "http://127.0.0.1:8080"

EXPLAINER_SLUGS = [
    # Batch 1 (already audited - kept for completeness)
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
    # Batch 2 — new explainer slugs
    "38-cfr-rating-schedule",
    "sgli-explained",
    "vgli-explained",
    "military-life-insurance",
    "tdiu-benefits",
    "tdiu-approval-rate",
    "va-unemployability-vs-100-percent",
    "veterans-evaluation-services",
    "optum-serve-cp-exam",
]

# Other paths created in batch 2
OTHER_PATHS = [
    "/va-disability-conditions-list/",
    "/va-disability-percentages/",
    "/va-disability-cheat-sheet/",
    "/dic-benefits/",
    "/va-survivor-benefits/",
    "/va-survivor-benefits/dic-vs-sbp/",
    "/va-life-insurance/",
    "/va-intent-to-file/",
    "/va-claim-status/",
    "/va-education-benefits/",
    "/va-forms/21-526ez/",
    "/va-forms/21-4138/",
    "/va-forms/21-0781/",
    "/va-forms/21-8940/",
    "/gi-bill/",
    "/gi-bill/post-9-11/",
    "/gi-bill/comparison/",
    "/military-pay/army-pay-chart/",
    "/military-pay/army-pay-calculator/",
    "/military-pay/navy-pay-chart/",
    "/military-pay/air-force-pay-chart/",
    "/va-claims/benefits-delivery-at-discharge/",
]

TOOL_PATHS = ["/tools/gi-bill-bah-calculator/"]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content="(.*?)"', re.S | re.I)
JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
HREF_RE = re.compile(r'href=["\'](/[^"\'#?]*)["\']')

_link_cache: dict[str, int] = {}


def fetch(path: str) -> tuple[int, str]:
    url = path if path.startswith("http") else BASE + path
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def status_of(path: str) -> int:
    if path not in _link_cache:
        try:
            req = urllib.request.Request(BASE + path, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                _link_cache[path] = r.status
        except urllib.error.HTTPError as e:
            _link_cache[path] = e.code
        except Exception:
            # some routes reject HEAD; fall back to GET
            _link_cache[path] = fetch(path)[0]
    return _link_cache[path]


def audit_page(path: str, html: str, faq_json, is_tool: bool) -> list[str]:
    issues: list[str] = []

    # --- 1. metadata lengths ---
    tm = TITLE_RE.search(html)
    title = tm.group(1).strip() if tm else ""
    dm = DESC_RE.search(html)
    desc = dm.group(1).strip() if dm else ""
    tlen, dlen = len(title), len(desc)
    flag_t = "" if 50 <= tlen <= 60 else "  <-- outside 50-60"
    flag_d = "" if 120 <= dlen <= 160 else "  <-- outside 120-160"
    print(f"    title[{tlen}]: {title}{flag_t}")
    print(f"    desc [{dlen}]: {desc}{flag_d}")
    if title.endswith("…") or title.endswith("..."):
        issues.append(f"title appears truncated: {title!r}")
    if tlen > 60:
        issues.append(f"title {tlen} chars (>60)")
    if tlen < 50:
        issues.append(f"title {tlen} chars (<50)")
    if dlen > 160:
        issues.append(f"meta description {dlen} chars (>160)")
    if dlen and dlen < 120:
        issues.append(f"meta description {dlen} chars (<120)")
    if not desc:
        issues.append("missing meta description")

    # --- 2. FAQ JSON schema (DB side) ---
    if not is_tool:
        if not isinstance(faq_json, list) or not faq_json:
            issues.append("faq_json missing or not a non-empty list")
        else:
            for i, e in enumerate(faq_json):
                if not isinstance(e, dict):
                    issues.append(f"faq[{i}] not a dict")
                    continue
                q = e.get("question") or e.get("q")
                a = e.get("answer") or e.get("a")
                if not q:
                    issues.append(f"faq[{i}] empty question")
                if not a:
                    issues.append(f"faq[{i}] empty answer")

    # --- 4. schema.org JSON-LD ---
    blocks = JSONLD_RE.findall(html)
    types_found: set[str] = set()
    if not blocks:
        issues.append("no JSON-LD block found")
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError as e:
            issues.append(f"JSON-LD invalid: {e}")
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else []
        for n in nodes:
            t = n.get("@type")
            if isinstance(t, list):
                types_found.update(t)
            elif t:
                types_found.add(t)
            # validate FAQPage shape if present
            if n.get("@type") == "FAQPage":
                for me in n.get("mainEntity", []):
                    if me.get("@type") != "Question" or not me.get("name"):
                        issues.append("FAQPage Question malformed")
                    aa = me.get("acceptedAnswer", {})
                    if aa.get("@type") != "Answer" or not aa.get("text"):
                        issues.append("FAQPage Answer malformed")
    print(f"    json-ld @types: {sorted(types_found)}")
    expected = {"WebApplication", "BreadcrumbList"} if is_tool else {"Article", "BreadcrumbList", "FAQPage"}
    missing = expected - types_found
    if missing:
        issues.append(f"JSON-LD missing @types: {sorted(missing)}")

    # --- 3. internal linking ---
    hrefs = sorted(set(HREF_RE.findall(html)))
    broken = []
    for h in hrefs:
        if h.startswith("/static/"):
            continue
        code = status_of(h)
        if code not in (200, 301, 308):
            broken.append(f"{h} -> {code}")
    if broken:
        issues.append("broken internal links: " + ", ".join(broken))
    print(f"    internal links: {len(hrefs)} checked, {len(broken)} broken")

    return issues


def main() -> None:
    sess = SessionLocal()
    try:
        faq_by_path: dict[str, list] = {}
        for slug in EXPLAINER_SLUGS:
            p = f"/explainers/{slug}/"
            row = sess.query(LandingPage).filter_by(canonical_path=p).first()
            faq_by_path[p] = row.faq_json if row else None
        for p in OTHER_PATHS:
            row = sess.query(LandingPage).filter_by(canonical_path=p).first()
            faq_by_path[p] = row.faq_json if row else None
    finally:
        sess.close()

    all_issues: dict[str, list[str]] = {}

    for slug in EXPLAINER_SLUGS:
        path = f"/explainers/{slug}/"
        print(f"\n=== {path} ===")
        status, html = fetch(path)
        if status != 200:
            all_issues[path] = [f"page returned {status}"]
            print(f"    !! status {status}")
            continue
        all_issues[path] = audit_page(path, html, faq_by_path[path], is_tool=False)

    for path in OTHER_PATHS:
        print(f"\n=== {path} ===")
        status, html = fetch(path)
        if status != 200:
            all_issues[path] = [f"page returned {status}"]
            print(f"    !! status {status}")
            continue
        all_issues[path] = audit_page(path, html, faq_by_path[path], is_tool=False)

    for path in TOOL_PATHS:
        print(f"\n=== {path} ===")
        status, html = fetch(path)
        if status != 200:
            all_issues[path] = [f"page returned {status}"]
            print(f"    !! status {status}")
            continue
        all_issues[path] = audit_page(path, html, None, is_tool=True)

    print("\n\n========== SUMMARY ==========")
    total = 0
    for path, issues in all_issues.items():
        if issues:
            total += len(issues)
            print(f"\n{path}:")
            for i in issues:
                print(f"  - {i}")
    if total == 0:
        print("All clean. No issues found.")
    else:
        print(f"\nTotal issues: {total}")


if __name__ == "__main__":
    main()
