#!/usr/bin/env python3
"""
One-shot migration: convert dash-based landing_page.page_key values to the
colon-based format the server expects.

  condition-tinnitus          → condition:tinnitus
  state-california            → state:california
  pillar va-claims            → pillar:va-claims
  explainer-va-rating         → explainer:va-rating
  spoke va-claims-how-to-file → spoke:va-claims:how-to-file

Run once after the first LLM generation pass:
  python3 scripts/fix_landing_page_keys.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models import engine, LandingPage
from sqlalchemy.orm import Session

PILLAR_SLUGS = [
    "va-claims",
    "va-disability",
    "military-retirement",
    "military-pay",
    "state-benefits",
    "explainers",
]


def new_key(page_type: str, old_key: str) -> str:
    if page_type == "pillar":
        # old: "va-claims"  new: "pillar:va-claims"
        if old_key.startswith("pillar:"):
            return old_key  # already correct
        return f"pillar:{old_key}"

    if page_type == "condition":
        # old: "condition-tinnitus"  new: "condition:tinnitus"
        if old_key.startswith("condition:"):
            return old_key
        return f"condition:{old_key.removeprefix('condition-')}"

    if page_type == "state":
        # old: "state-california"  new: "state:california"
        if old_key.startswith("state:"):
            return old_key
        return f"state:{old_key.removeprefix('state-')}"

    if page_type == "explainer":
        # old: "explainer-va-rating"  new: "explainer:va-rating"
        if old_key.startswith("explainer:"):
            return old_key
        return f"explainer:{old_key.removeprefix('explainer-')}"

    if page_type == "spoke":
        # old: "va-claims-how-to-file-a-va-claim"
        # new: "spoke:va-claims:how-to-file-a-va-claim"
        if old_key.startswith("spoke:"):
            return old_key
        for pillar in PILLAR_SLUGS:
            prefix = f"{pillar}-"
            if old_key.startswith(prefix):
                spoke = old_key[len(prefix):]
                return f"spoke:{pillar}:{spoke}"
        # Fallback — shouldn't happen
        return f"spoke:{old_key}"

    return old_key


def main():
    fixed = 0
    skipped = 0

    with Session(engine) as session:
        rows = session.query(LandingPage).all()
        for row in rows:
            target = new_key(row.page_type, row.page_key)
            if target == row.page_key:
                skipped += 1
                continue
            # Check for collision before renaming
            collision = session.query(LandingPage).filter_by(page_key=target).first()
            if collision and collision.id != row.id:
                print(f"  SKIP (collision) {row.page_key!r} → {target!r}")
                skipped += 1
                continue
            print(f"  {row.page_key!r}  →  {target!r}")
            row.page_key = target
            session.add(row)
            fixed += 1
        session.commit()

    print(f"\nDone: {fixed} keys updated, {skipped} already correct / skipped.")


if __name__ == "__main__":
    main()
