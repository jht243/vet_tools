#!/usr/bin/env python3
"""Seed MilitaryPayTable with 2024 base pay samples."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from rich.console import Console
from rich.table import Table

console = Console()

# 2024 monthly base pay (selected grades/YOS) — fill out full table from DFAS scraper
SAMPLE_PAY_2024 = [
    # (pay_grade, yos_min, yos_max, monthly_pay)
    ("E-1", 0, 2, 1917),
    ("E-2", 0, 2, 2149),
    ("E-3", 0, 2, 2259),
    ("E-3", 2, 3, 2341),
    ("E-4", 0, 2, 2503),
    ("E-4", 2, 3, 2626),
    ("E-4", 3, 4, 2751),
    ("E-5", 0, 2, 2730),
    ("E-5", 2, 4, 2912),
    ("E-5", 4, 6, 3095),
    ("E-6", 0, 2, 2980),
    ("E-6", 4, 6, 3263),
    ("E-6", 6, 8, 3446),
    ("E-7", 6, 8, 3862),
    ("E-7", 8, 10, 4007),
    ("E-8", 8, 10, 4480),
    ("E-9", 10, 12, 5473),
    ("O-1", 0, 2, 3637),
    ("O-2", 0, 2, 4188),
    ("O-3", 0, 2, 4862),
    ("O-3", 4, 6, 5473),
    ("O-3", 6, 8, 5855),
    ("O-4", 6, 8, 6633),
    ("O-5", 10, 12, 8205),
    ("O-6", 18, 20, 11917),
]


@click.command()
@click.option("--year", default=2024, type=int)
@click.option("--dry-run", is_flag=True, default=False)
def main(year, dry_run):
    """Seed MilitaryPayTable with sample 2024 base pay data."""
    from src.models import init_db, MilitaryPayTable, engine
    from sqlalchemy.orm import Session

    init_db()

    inserted = updated = 0

    with Session(engine) as session:
        for pay_grade, yos_min, yos_max, monthly_pay in SAMPLE_PAY_2024:
            existing = (
                session.query(MilitaryPayTable)
                .filter_by(year=year, pay_grade=pay_grade, yos_min=yos_min)
                .first()
            )
            if existing:
                existing.monthly_basic_pay = monthly_pay
                existing.yos_max = yos_max
                if not dry_run:
                    session.add(existing)
                updated += 1
            else:
                if not dry_run:
                    row = MilitaryPayTable(
                        year=year,
                        pay_grade=pay_grade,
                        yos_min=yos_min,
                        yos_max=yos_max,
                        monthly_basic_pay=monthly_pay,
                    )
                    session.add(row)
                inserted += 1

        if not dry_run:
            session.commit()

    prefix = "[DRY RUN] " if dry_run else ""
    table = Table(title=f"{prefix}MilitaryPayTable Import — Year {year}")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Inserted", str(inserted))
    table.add_row("Updated", str(updated))
    console.print(table)


if __name__ == "__main__":
    main()
