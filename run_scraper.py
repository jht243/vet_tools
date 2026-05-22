#!/usr/bin/env python3
"""
Standalone scraper runner — useful for testing individual scrapers.

Usage:
    python run_scraper.py --source va_news --dry-run
    python run_scraper.py --source google_news
    python run_scraper.py --source all
    python run_scraper.py --source federal_register --lookback 60
"""

import importlib
import logging

import click
from rich.console import Console
from rich.table import Table

from src.config import settings

console = Console()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

SCRAPER_MAP: dict[str, str] = {
    "google_news": "src.scraper.google_news.GoogleNewsScraper",
    "federal_register": "src.scraper.federal_register.FederalRegisterScraper",
    "va_news": "src.scraper.va_news.VANewsScraper",
    "dod_news": "src.scraper.dod_news.DoDNewsScraper",
    "congress_va": "src.scraper.congress_va.CongressVAScraper",
    "va_rates": "src.scraper.va_rates.VARatesScraper",
    "bah_rates": "src.scraper.bah_rates.BAHRatesScraper",
    "military_pay": "src.scraper.military_pay.MilitaryPayScraper",
}

ALL_SOURCES = list(SCRAPER_MAP.keys()) + ["all"]


def _load_scraper(dotted_path: str):
    """Instantiate a scraper class by its fully-qualified dotted path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    # Convert src.scraper.foo → src/scraper/foo (importlib works with dots)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def _run_one(source: str, dry_run: bool, lookback: int) -> tuple[bool, int, str]:
    """
    Run a single scraper and return (success, article_count, error_message).
    """
    dotted = SCRAPER_MAP[source]
    try:
        scraper = _load_scraper(dotted)
        articles = scraper.scrape()
        count = len(articles) if articles is not None else 0

        if dry_run:
            console.print(
                f"\n[dim]  {source} — dry-run: first 3 headlines:[/dim]"
            )
            for article in (articles or [])[:3]:
                # Support both dict-like and ORM objects with a .title attribute
                title = (
                    article.get("title", "(no title)")
                    if isinstance(article, dict)
                    else getattr(article, "title", "(no title)")
                )
                console.print(f"    [cyan]•[/cyan] {title}")
        else:
            from src.pipeline import run_daily_scrape  # noqa: PLC0415

            run_daily_scrape(sources=[source])

        return True, count, ""
    except Exception as exc:  # noqa: BLE001
        log.warning("Scraper %s failed: %s", source, exc)
        return False, 0, str(exc)


@click.command()
@click.option(
    "--source",
    required=True,
    type=click.Choice(ALL_SOURCES, case_sensitive=False),
    help="Scraper to run, or 'all' to run every scraper.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Scrape but do not persist results to the database.",
)
@click.option(
    "--lookback",
    default=None,
    type=int,
    show_default=True,
    help=(
        "How many days back to look for articles. "
        f"Defaults to settings.scraper_lookback_days ({settings.scraper_lookback_days})."
    ),
)
def main(source: str, dry_run: bool, lookback: int | None) -> None:
    effective_lookback = lookback if lookback is not None else settings.scraper_lookback_days

    if dry_run:
        console.print("[yellow]Dry-run mode — results will NOT be persisted.[/yellow]")

    console.print(
        f"[bold]Lookback:[/bold] {effective_lookback} days\n"
    )

    sources_to_run = list(SCRAPER_MAP.keys()) if source == "all" else [source]

    rows: list[tuple[str, str, str, str]] = []

    for src in sources_to_run:
        console.print(f"[cyan]Running scraper:[/cyan] {src} …")
        success, count, error = _run_one(src, dry_run=dry_run, lookback=effective_lookback)
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        rows.append((src, status, str(count) if success else "—", error))

    # ── Results table ─────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold blue]Scraper Results[/bold blue]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Articles", justify="right")
    table.add_column("Error")

    for src, status, count, error in rows:
        table.add_row(src, status, count, error)

    console.print(table)

    failures = [src for src, status, _, _ in rows if "✗" in status]
    if failures:
        console.print(
            f"\n[red]Failed scrapers:[/red] {', '.join(failures)}"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
