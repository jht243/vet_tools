#!/usr/bin/env python3
"""
One-time import of seed data center records from static/data/data_centers_seed.json.

Usage:
    python scripts/import_data_centers.py
    python scripts/import_data_centers.py --clear   # wipe table first
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console

from src.models import DataCenter, SessionLocal, init_db

console = Console()
SEED_FILE = Path(__file__).parent.parent / "static" / "data" / "data_centers_seed.json"


@click.command()
@click.option("--clear", is_flag=True, help="Delete all existing rows before importing")
def main(clear: bool) -> None:
    init_db()
    db = SessionLocal()
    try:
        if clear:
            deleted = db.query(DataCenter).delete()
            db.commit()
            console.print(f"[yellow]Cleared {deleted} existing rows[/yellow]")

        records = json.loads(SEED_FILE.read_text())
        console.print(f"Importing {len(records)} data center records...")

        inserted = 0
        skipped = 0
        for r in records:
            existing = db.query(DataCenter).filter(DataCenter.name == r["name"]).first()
            if existing:
                skipped += 1
                continue

            announced = None
            if r.get("announced_date"):
                announced = date.fromisoformat(r["announced_date"])

            row = DataCenter(
                name=r["name"],
                operator=r.get("operator"),
                status=r.get("status", "operating"),
                city=r.get("city"),
                state=r.get("state"),
                county=r.get("county"),
                country=r.get("country", "US"),
                lat=r.get("lat"),
                lng=r.get("lng"),
                capacity_mw=r.get("capacity_mw"),
                water_source=r.get("water_source"),
                announced_date=announced,
                source_url=r.get("source_url"),
                notes=r.get("notes"),
            )
            db.add(row)
            inserted += 1

        db.commit()
        console.print(f"[green]Done:[/green] {inserted} inserted, {skipped} skipped (already exist)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
