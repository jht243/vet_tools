"""One-shot repair: clean up broken internal links in stored LandingPage
bodies that LLM-generated content baked in (stale Venezuela paths,
literal /responsible-ai/* wildcards, mistyped slugs).

Run once. Safe to re-run — it's idempotent (string replace).

    python scripts/fix_broken_landing_links.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

os.environ.setdefault("SITE_URL", "https://banthebots.org")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.models import LandingPage, SessionLocal, init_db  # noqa: E402

# Each entry: (regex, replacement, description). Order matters — fix the
# specific cases first, then the general placeholders.
FIXES: list[tuple[str, str, str]] = [
    # Mistyped industry slug — real-estate needs the hyphen.
    (r'href="/responsible-ai/realestate"',
     'href="/responsible-ai/real-estate/"',
     "/responsible-ai/realestate -> /responsible-ai/real-estate/"),
    # Bare /responsible-ai/ wildcards the LLM baked in.
    (r'href="/responsible-ai/\*"',
     'href="/responsible-ai/"',
     "/responsible-ai/* -> /responsible-ai/"),
    # Stale /sectors/* paths (ported from Venezuela).
    (r'href="/sectors/[^"]*"',
     'href="/responsible-ai/"',
     "/sectors/* -> /responsible-ai/"),
    # Stale /invest-in-venezuela link.
    (r'href="/invest-in-venezuela[^"]*"',
     'href="/ai-backlash/"',
     "/invest-in-venezuela -> /ai-backlash/"),
    # Stale /sanctions-tracker links.
    (r'href="/sanctions[^"]*"',
     'href="/ai-incidents/"',
     "/sanctions/* -> /ai-incidents/"),
    # Stale /tools/* generic placeholders.
    (r'href="/tools/\*"',
     'href="/ai-risk-assessment/"',
     "/tools/* -> /ai-risk-assessment/"),
    # Belt-and-suspenders: bare path variants.
    (r"/sectors/realestate\b", "/responsible-ai/real-estate/", "bare /sectors/realestate"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        pages = db.query(LandingPage).all()
        print(f"Scanning {len(pages)} landing pages...")
        total_changes = 0
        changed_pages = 0
        for page in pages:
            html = page.body_html or ""
            new_html = html
            page_changes = 0
            for pattern, repl, desc in FIXES:
                fixed, n = re.subn(pattern, repl, new_html, flags=re.IGNORECASE)
                if n > 0:
                    page_changes += n
                    print(f"  [{page.page_key}] {desc}: {n} fix(es)")
                    new_html = fixed
            if page_changes:
                changed_pages += 1
                total_changes += page_changes
                if not args.dry_run:
                    page.body_html = new_html
        if not args.dry_run and total_changes:
            db.commit()
            print(f"\nCommitted {total_changes} fix(es) across {changed_pages} page(s).")
        elif args.dry_run:
            print(f"\nDRY RUN: would fix {total_changes} link(s) across {changed_pages} page(s).")
        else:
            print("\nNo fixes needed.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
