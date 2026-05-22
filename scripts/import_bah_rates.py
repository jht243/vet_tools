#!/usr/bin/env python3
"""Seed BAHRate table with sample rates. Replace with live DoD data scrape for production."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Sample rates for common MHAs — replace with full table from BAH scraper in production
SAMPLE_RATES_2024 = [
    # (mha_code, mha_name, pay_grade, with_dependents, monthly_rate)
    ("NY", "New York City, NY", "O-3", True, 4512),
    ("NY", "New York City, NY", "O-3", False, 3756),
    ("NY", "New York City, NY", "E-5", True, 3564),
    ("NY", "New York City, NY", "E-5", False, 2988),
    ("DC", "Washington, DC", "O-3", True, 3906),
    ("DC", "Washington, DC", "O-3", False, 3252),
    ("DC", "Washington, DC", "E-5", True, 3024),
    ("DC", "Washington, DC", "E-5", False, 2520),
    ("SAN", "San Diego, CA", "O-3", True, 3996),
    ("SAN", "San Diego, CA", "O-3", False, 3330),
    ("SAN", "San Diego, CA", "E-5", True, 3108),
    ("SAN", "San Diego, CA", "E-5", False, 2592),
]


@click.command()
@click.option("--year", default=2024, type=int)
@click.option("--dry-run", is_flag=True, default=False)
def main(year, dry_run):
    """Seed BAHRate table with sample data."""
    from src.models import init_db, BAHRate, engine
    from sqlalchemy.orm import Session

    init_db()

    inserted = updated = 0

    with Session(engine) as session:
        for mha_code, mha_name, pay_grade, with_deps, rate in SAMPLE_RATES_2024:
            existing = (
                session.query(BAHRate)
                .filter_by(year=year, mha_code=mha_code, pay_grade=pay_grade, with_dependents=with_deps)
                .first()
            )
            if existing:
                existing.monthly_rate = rate
                existing.mha_name = mha_name
                if not dry_run:
                    session.add(existing)
                updated += 1
            else:
                if not dry_run:
                    r = BAHRate(
                        year=year,
                        mha_code=mha_code,
                        mha_name=mha_name,
                        pay_grade=pay_grade,
                        with_dependents=with_deps,
                        monthly_rate=rate,
                    )
                    session.add(r)
                inserted += 1

        if not dry_run:
            session.commit()

    prefix = "[DRY RUN] " if dry_run else ""
    table = Table(title=f"{prefix}BAHRate Import — Year {year}")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Inserted", str(inserted))
    table.add_row("Updated", str(updated))
    console.print(table)


if __name__ == "__main__":
    main()
