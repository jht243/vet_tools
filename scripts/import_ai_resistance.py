#!/usr/bin/env python3
"""
One-time import of seed AI resistance action records from static/data/ai_resistance_seed.json.

Usage:
    python scripts/import_ai_resistance.py
    python scripts/import_ai_resistance.py --clear   # wipe table first
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console

from src.models import AIResistanceAction, SessionLocal, init_db

console = Console()
SEED_FILE = Path(__file__).parent.parent / "static" / "data" / "ai_resistance_seed.json"


@click.command()
@click.option("--clear", is_flag=True, help="Delete all existing rows before importing")
def main(clear: bool) -> None:
    init_db()
    db = SessionLocal()
    try:
        if clear:
            deleted = db.query(AIResistanceAction).delete()
            db.commit()
            console.print(f"[yellow]Cleared {deleted} existing rows[/yellow]")

        records = json.loads(SEED_FILE.read_text())
        console.print(f"Importing {len(records)} resistance action records...")

        inserted = 0
        skipped = 0
        for r in records:
            existing = (
                db.query(AIResistanceAction)
                .filter(AIResistanceAction.actor == r["actor"])
                .filter(AIResistanceAction.action_type == r["action_type"])
                .first()
            )
            if existing:
                skipped += 1
                continue

            announced = None
            if r.get("announced_date"):
                announced = date.fromisoformat(r["announced_date"])

            row = AIResistanceAction(
                actor=r["actor"],
                actor_type=r["actor_type"],
                action_type=r["action_type"],
                country=r.get("country", "US"),
                state=r.get("state"),
                industry=r.get("industry"),
                announced_date=announced,
                description=r.get("description"),
                source_url=r.get("source_url"),
                still_active=r.get("still_active", True),
            )
            db.add(row)
            inserted += 1

        db.commit()
        console.print(f"[green]Done:[/green] {inserted} inserted, {skipped} skipped (already exist)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
