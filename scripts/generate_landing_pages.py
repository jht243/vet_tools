#!/usr/bin/env python3
"""CLI to generate landing pages in batch."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command()
@click.option("--pillars/--no-pillars", default=True)
@click.option("--spokes/--no-spokes", default=True)
@click.option("--conditions/--no-conditions", default=True)
@click.option("--states/--no-states", default=True)
@click.option("--explainers/--no-explainers", default=True)
@click.option("--dry-run", is_flag=True, default=False)
def main(pillars, spokes, conditions, states, explainers, dry_run):
    """Generate all landing pages (pillar, spoke, condition, state, explainer)."""
    from src.models import init_db
    init_db()

    from src.landing_generator import generate_all_landing_pages

    if dry_run:
        console.print("[yellow]DRY RUN — no DB writes[/yellow]")

    counts = generate_all_landing_pages(
        dry_run=dry_run,
        pillars=pillars,
        spokes=spokes,
        conditions=conditions,
        states=states,
        explainers=explainers,
    )

    table = Table(title="Landing Page Generation Results")
    table.add_column("Type")
    table.add_column("Count", justify="right")
    for k, v in counts.items():
        style = "red" if k == "errors" and v > 0 else "green"
        table.add_row(k, str(v), style=style if v > 0 else "dim")

    console.print(table)
    if counts.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
