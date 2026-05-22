#!/usr/bin/env python3
"""
Daily orchestrator for VA Claims Workspace.

Chains: scrape -> analyze -> blog generation -> press radar ->
        Google Indexing API -> newsletter -> IndexNow/archive/Zenodo/OSF ->
        SEO audit -> sitemap sync

Usage:
    python run_daily.py                    # Full pipeline
    python run_daily.py --skip-scrape      # Skip scraping, use existing DB data
    python run_daily.py --skip-email       # Generate report but don't send emails
    python run_daily.py --dry-run          # Full pipeline but no actual sends
    python run_daily.py --report-only      # Only skip scrape and email
"""

import logging
import sys
from datetime import datetime, timezone

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


def _print_header() -> None:
    console.rule("[bold blue]VA Claims Workspace — Daily Pipeline[/bold blue]")
    console.print(
        f"  [dim]{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}[/dim]\n"
    )


def _print_summary(results: dict[str, str]) -> None:
    console.rule("[bold blue]Pipeline Summary[/bold blue]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Phase", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Detail")

    status_style = {
        "ok": "[green]✓ OK[/green]",
        "skip": "[dim]— skip[/dim]",
        "warn": "[yellow]! warn[/yellow]",
        "fail": "[red]✗ FAIL[/red]",
    }

    for phase, (state, detail) in results.items():
        styled = status_style.get(state, state)
        table.add_row(phase, styled, detail or "")

    console.print(table)
    console.print()


@click.command()
@click.option("--skip-scrape", is_flag=True, default=False, help="Skip scraping phase.")
@click.option("--skip-email", is_flag=True, default=False, help="Skip newsletter send.")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Full pipeline but no actual sends/writes.",
)
@click.option(
    "--report-only",
    is_flag=True,
    default=False,
    help="Alias for --skip-scrape --skip-email.",
)
def main(
    skip_scrape: bool,
    skip_email: bool,
    dry_run: bool,
    report_only: bool,
) -> None:
    if report_only:
        skip_scrape = True
        skip_email = True

    _print_header()
    results: dict[str, tuple[str, str]] = {}

    # ── Phase 1: Scrape ───────────────────────────────────────────────────────
    phase = "Phase 1: Scrape"
    if skip_scrape:
        console.print(f"[dim]{phase} — skipped[/dim]")
        results[phase] = ("skip", "")
    else:
        console.rule(f"[cyan]{phase}[/cyan]")
        try:
            from src.pipeline import run_daily_scrape

            run_daily_scrape()
            console.print(f"[green]✓ {phase} complete[/green]")
            results[phase] = ("ok", "")
        except Exception as exc:
            log.exception("Fatal error in %s", phase)
            console.print(f"[bold red]✗ {phase} failed: {exc}[/bold red]")
            results[phase] = ("fail", str(exc))
            _print_summary(results)
            sys.exit(1)

    # ── Phase 2: LLM Analysis ────────────────────────────────────────────────
    phase = "Phase 2: LLM Analysis"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.analyzer import run_analysis

        run_analysis()
        console.print(f"[green]✓ {phase} complete[/green]")
        results[phase] = ("ok", "")
    except Exception as exc:
        log.exception("Fatal error in %s", phase)
        console.print(f"[bold red]✗ {phase} failed: {exc}[/bold red]")
        results[phase] = ("fail", str(exc))
        _print_summary(results)
        sys.exit(1)

    # ── Phase 2b: Blog Generation ────────────────────────────────────────────
    phase = "Phase 2b: Blog Generation"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.blog_generator import run_blog_generation

        result = run_blog_generation()
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 2c: Press Radar ────────────────────────────────────────────────
    phase = "Phase 2c: Press Radar"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.press_radar import run_press_radar

        result = run_press_radar(dry_run=dry_run)
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 3: Google Indexing API ─────────────────────────────────────────
    phase = "Phase 3: Google Indexing API"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.distribution.runner import run_google_indexing

        result = run_google_indexing(dry_run=dry_run)
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 4: Newsletter ──────────────────────────────────────────────────
    phase = "Phase 4: Newsletter"
    if skip_email and not dry_run:
        console.print(f"[dim]{phase} — skipped[/dim]")
        results[phase] = ("skip", "--skip-email")
    else:
        console.rule(f"[cyan]{phase}[/cyan]")
        try:
            from src.newsletter import send_newsletter

            result = send_newsletter(dry_run=dry_run or skip_email)
            console.print(f"[green]✓ {phase} complete[/green]: {result}")
            results[phase] = ("ok", str(result))
        except Exception as exc:
            log.warning("Non-fatal error in %s: %s", phase, exc)
            console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
            results[phase] = ("warn", str(exc))

    # ── Phase 5: Distribution (IndexNow + Archive + Zenodo + OSF) ───────────
    phase = "Phase 5: Distribution"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.distribution.runner import run_all as run_distribution_all

        result = run_distribution_all(dry_run=dry_run)
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 5b: Outreach — not configured ─────────────────────────────────
    console.print("[dim]Phase 5b: Outreach — not configured[/dim]")
    results["Phase 5b: Outreach"] = ("skip", "not configured")

    # ── Phase 6: SEO Audit ───────────────────────────────────────────────────
    phase = "Phase 6: SEO Audit"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.seo.audit import run_audit

        seo_report = run_audit(max_pages=200)
        console.print(f"[green]✓ {phase} complete[/green]: {seo_report}")
        results[phase] = ("ok", str(seo_report))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 6b: SEO Auto-fix ───────────────────────────────────────────────
    phase = "Phase 6b: SEO Auto-fix"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from src.seo.content_fixer import fix_content_issues

        result = fix_content_issues(dry_run=dry_run)
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    # ── Phase 6c: Ahrefs Audit (Mondays only) ───────────────────────────────
    phase = "Phase 6c: Ahrefs Audit"
    if datetime.now(timezone.utc).weekday() == 0:  # Monday == 0
        console.rule(f"[cyan]{phase}[/cyan]")
        try:
            from src.seo.ahrefs_audit import run_ahrefs_audit

            result = run_ahrefs_audit(dry_run=dry_run)
            console.print(f"[green]✓ {phase} complete[/green]: {result}")
            results[phase] = ("ok", str(result))
        except Exception as exc:
            log.warning("Non-fatal error in %s: %s", phase, exc)
            console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
            results[phase] = ("warn", str(exc))
    else:
        console.print(f"[dim]{phase} — runs on Mondays only[/dim]")
        results[phase] = ("skip", "not Monday")

    # ── Phase 7: Sitemap Sync ────────────────────────────────────────────────
    phase = "Phase 7: Sitemap Sync"
    console.rule(f"[cyan]{phase}[/cyan]")
    try:
        from scripts.sync_sitemap import run_sync

        result = run_sync(dry_run=dry_run)
        console.print(f"[green]✓ {phase} complete[/green]: {result}")
        results[phase] = ("ok", str(result))
    except Exception as exc:
        log.warning("Non-fatal error in %s: %s", phase, exc)
        console.print(f"[yellow]! {phase} warning: {exc}[/yellow]")
        results[phase] = ("warn", str(exc))

    _print_summary(results)

    failures = [p for p, (state, _) in results.items() if state == "fail"]
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
