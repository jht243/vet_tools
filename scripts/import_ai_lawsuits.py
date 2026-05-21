#!/usr/bin/env python3
"""
One-time import of seed AI lawsuit records from static/data/ai_lawsuits_seed.json.

Usage:
    python scripts/import_ai_lawsuits.py
    python scripts/import_ai_lawsuits.py --clear   # wipe table first
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console

from src.models import AILawsuit, SessionLocal, init_db

console = Console()
SEED_FILE = Path(__file__).parent.parent / "static" / "data" / "ai_lawsuits_seed.json"


@click.command()
@click.option("--clear", is_flag=True, help="Delete all existing rows before importing")
def main(clear: bool) -> None:
    init_db()
    db = SessionLocal()
    try:
        if clear:
            deleted = db.query(AILawsuit).delete()
            db.commit()
            console.print(f"[yellow]Cleared {deleted} existing rows[/yellow]")

        records = json.loads(SEED_FILE.read_text())
        console.print(f"Importing {len(records)} lawsuit records...")

        inserted = 0
        skipped = 0
        for r in records:
            existing = db.query(AILawsuit).filter(AILawsuit.case_name == r["case_name"]).first()
            if existing:
                skipped += 1
                continue

            filed = None
            if r.get("filed_date"):
                filed = date.fromisoformat(r["filed_date"])

            row = AILawsuit(
                case_name=r["case_name"],
                plaintiff=r["plaintiff"],
                defendant=r["defendant"],
                filed_date=filed,
                court=r.get("court"),
                claim_type=r.get("claim_type"),
                status=r.get("status", "ongoing"),
                amount_sought_usd=r.get("amount_sought_usd"),
                description=r.get("description"),
                source_url=r.get("source_url"),
            )
            db.add(row)
            inserted += 1

        db.commit()
        console.print(f"[green]Done:[/green] {inserted} inserted, {skipped} skipped (already exist)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
