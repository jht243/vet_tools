#!/usr/bin/env python3
"""
Ban the Bots — historical backfill runner.

Scrapes articles and AI incidents from the configured start date to today,
then runs the analyzer and blog generator to produce briefings from any
newly eligible articles.

Usage:
    python run_backfill.py
    python run_backfill.py --start-date 2026-01-01
    python run_backfill.py --skip-analyze --skip-blog
    python run_backfill.py --skip-incidents
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import date, datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.config import settings
from src.models import init_db
from src.pipeline import _log_scrape, _persist_articles

console = Console()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_backfill")


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _backfill_google_news(start: date, end: date) -> dict:
    """Scrape Google News for the lookback window."""
    console.print("[cyan]→ Google News[/cyan]")
    summary: dict = {"articles_new": 0, "errors": []}
    try:
        from src.scraper.google_news import GoogleNewsScraper
        scraper = GoogleNewsScraper()
        result = scraper.scrape(end)
        if result.success and result.articles:
            new_ids = _persist_articles(result.articles)
            summary["articles_new"] = len(new_ids)
            console.print(
                f"  [green]✓[/green] {len(result.articles)} fetched, "
                f"{len(new_ids)} new"
            )
            _log_scrape(result, end)
        else:
            msg = result.error or "no articles"
            console.print(f"  [yellow]~[/yellow] {msg}")
        scraper.close()
    except Exception as exc:
        logger.error("Google News backfill failed: %s", exc, exc_info=True)
        summary["errors"].append(str(exc))
        console.print(f"  [red]✗[/red] {exc}")
    return summary


def _backfill_ai_incidents() -> dict:
    """Fetch AI incidents from AIID GraphQL + AIAAIC CSV."""
    console.print("[cyan]→ AI Incident Database + AIAAIC[/cyan]")
    summary: dict = {"incidents_new": 0, "articles_new": 0, "errors": []}
    try:
        from src.scraper.ai_incident_db import AIIncidentDBScraper
        scraper = AIIncidentDBScraper()
        result = scraper.scrape(date.today())
        if result.success:
            if result.articles:
                new_ids = _persist_articles(result.articles)
                summary["articles_new"] = len(new_ids)
            _log_scrape(result, date.today())
            console.print(
                f"  [green]✓[/green] "
                f"incidents written={summary.get('incidents_new', 0)}, "
                f"articles_new={summary['articles_new']}"
            )
        else:
            summary["errors"].append(result.error or "scrape failed")
            console.print(f"  [red]✗[/red] {result.error}")
        scraper.close()
    except Exception as exc:
        logger.error("AI Incident backfill failed: %s", exc, exc_info=True)
        summary["errors"].append(str(exc))
        console.print(f"  [red]✗[/red] {exc}")
    return summary


def _run_analyzer() -> None:
    console.print("\n[bold cyan]Analyzer[/bold cyan]")
    try:
        from src.analyzer import run_analysis
        result = run_analysis()
        console.print(f"  [green]✓[/green] {result}")
    except Exception as exc:
        logger.error("Analyzer failed: %s", exc, exc_info=True)
        console.print(f"  [red]✗[/red] {exc}")


def _run_blog_generator() -> None:
    console.print("\n[bold cyan]Blog generator[/bold cyan]")
    try:
        from src.blog_generator import run_blog_generator
        result = run_blog_generator()
        console.print(f"  [green]✓[/green] {result}")
    except Exception as exc:
        logger.error("Blog generator failed: %s", exc, exc_info=True)
        console.print(f"  [red]✗[/red] {exc}")


def _backfill_og_images() -> None:
    console.print("\n[bold cyan]OG image backfill[/bold cyan]")
    try:
        from scripts.backfill_og_images import main as og_main
        og_main([])
    except Exception as exc:
        logger.error("OG image backfill failed: %s", exc, exc_info=True)
        console.print(f"  [red]✗[/red] {exc}")


@click.command()
@click.option(
    "--start-date",
    default="2026-01-01",
    help="ISO date (YYYY-MM-DD). Default: 2026-01-01.",
)
@click.option(
    "--end-date",
    default=None,
    help="ISO date (YYYY-MM-DD). Default: today.",
)
@click.option("--skip-news", is_flag=True, help="Skip Google News scraper.")
@click.option("--skip-incidents", is_flag=True, help="Skip AI incident scraper.")
@click.option("--skip-analyze", is_flag=True, help="Skip the LLM analyzer pass.")
@click.option("--skip-blog", is_flag=True, help="Skip blog-post generation.")
@click.option("--skip-og", is_flag=True, help="Skip OG image backfill.")
def main(
    start_date: str,
    end_date: str | None,
    skip_news: bool,
    skip_incidents: bool,
    skip_analyze: bool,
    skip_blog: bool,
    skip_og: bool,
) -> None:
    """Ban the Bots — historical backfill"""

    start = _parse_date(start_date)
    end = _parse_date(end_date) if end_date else date.today()

    if start > end:
        console.print(f"[red]start_date {start} is after end_date {end}[/red]")
        sys.exit(1)

    console.print(
        Panel(
            f"[bold]Backfill[/bold] {start} → {end}",
            style="blue",
        )
    )
    init_db()

    started = time.time()
    grand: dict[str, int] = {"articles_new": 0, "incidents_new": 0}

    if not skip_news:
        s = _backfill_google_news(start, end)
        grand["articles_new"] += s.get("articles_new", 0)

    if not skip_incidents:
        s = _backfill_ai_incidents()
        grand["articles_new"] += s.get("articles_new", 0)
        grand["incidents_new"] += s.get("incidents_new", 0)

    console.print(
        f"\n[bold green]Scrape complete[/bold green] — "
        f"articles_new={grand['articles_new']}, "
        f"incidents_new={grand['incidents_new']} "
        f"({time.time() - started:.1f}s)"
    )

    if not skip_analyze:
        _run_analyzer()

    if not skip_blog:
        _run_blog_generator()

    if not skip_og:
        _backfill_og_images()

    console.print(f"\n[dim]Total elapsed: {time.time() - started:.1f}s[/dim]")


if __name__ == "__main__":
    main()
