#!/usr/bin/env python3
"""
Daily orchestrator for Ban the Bots.

Chains: scrape -> analyze -> blog generation -> Google Indexing API
-> newsletter -> IndexNow -> SEO audit -> sitemap sync

Usage:
    python run_daily.py                    # Full pipeline
    python run_daily.py --skip-scrape      # Skip scraping, use existing DB data
    python run_daily.py --skip-email       # Generate report but don't send emails
    python run_daily.py --dry-run          # Full pipeline but no actual sends
"""

from __future__ import annotations

import logging
import time

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import settings

console = Console()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_daily")


@click.command()
@click.option("--skip-scrape", is_flag=True, help="Skip the scraping phase")
@click.option("--skip-email", is_flag=True, help="Skip newsletter distribution")
@click.option("--dry-run", is_flag=True, help="Run everything but don't send real emails")
def main(skip_scrape: bool, skip_email: bool, dry_run: bool):
    """Ban the Bots — Daily Pipeline"""

    console.print(Panel("[bold]Ban the Bots — Daily Pipeline[/bold]", style="blue"))

    results = {}
    start = time.time()

    # Phase 1: Scrape
    if not skip_scrape:
        console.print("\n[bold cyan]Phase 1:[/bold cyan] Scraping sources...")
        try:
            from src.pipeline import run_daily_scrape
            scrape_result = run_daily_scrape()
            results["scrape"] = scrape_result
            console.print(f"  [green]✓[/green] Scraping complete: {scrape_result}")
        except Exception as e:
            logger.error("Scraping failed: %s", e, exc_info=True)
            results["scrape"] = {"error": str(e)}
            console.print(f"  [red]✗[/red] Scraping failed: {e}")
    else:
        console.print("\n[dim]Phase 1: Scraping — SKIPPED[/dim]")

    # Phase 2: LLM Analysis
    console.print("\n[bold cyan]Phase 2:[/bold cyan] Running LLM analysis...")
    try:
        from src.analyzer import run_analysis
        analysis_result = run_analysis()
        results["analysis"] = analysis_result
        console.print(f"  [green]✓[/green] Analysis complete: {analysis_result}")
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        results["analysis"] = {"error": str(e)}
        console.print(f"  [red]✗[/red] Analysis failed: {e}")

    # Phase 2b: Long-form briefing generation (capped budget; non-fatal)
    console.print("\n[bold cyan]Phase 2b:[/bold cyan] Writing long-form briefings...")
    try:
        from src.blog_generator import run_blog_generation
        blog_result = run_blog_generation()
        results["blog_generation"] = blog_result
        console.print(f"  [green]✓[/green] Blog generation: {blog_result}")
    except Exception as e:
        logger.error("Blog generation failed: %s", e, exc_info=True)
        results["blog_generation"] = {"error": str(e)}
        console.print(f"  [yellow]![/yellow] Blog generation failed (non-fatal): {e}")

    # Phase 3: Google Indexing API
    console.print("\n[bold cyan]Phase 3:[/bold cyan] Google Indexing API (URL notifications)...")
    try:
        from src.distribution.runner import run_google_indexing
        gidx = run_google_indexing()
        results["google_indexing"] = gidx
        if gidx.get("status") == "ok":
            console.print(
                f"  [green]✓[/green] pinged {gidx.get('pinged', 0)} "
                f"({gidx.get('succeeded', 0)} ok, {gidx.get('failed', 0)} failed)"
            )
        else:
            console.print(f"  [yellow]·[/yellow] {gidx}")
    except Exception as e:
        logger.error("Google Indexing API failed: %s", e, exc_info=True)
        results["google_indexing"] = {"error": str(e)}
        console.print(f"  [yellow]![/yellow] Google Indexing (non-fatal): {e}")

    # Phase 4: Newsletter
    if not skip_email:
        console.print("\n[bold cyan]Phase 4:[/bold cyan] Sending newsletter...")
        try:
            from src.newsletter import send_newsletter
            email_result = send_newsletter(None, dry_run=dry_run)
            results["newsletter"] = email_result
            console.print(f"  [green]✓[/green] Newsletter: {email_result}")
        except Exception as e:
            logger.error("Newsletter failed: %s", e, exc_info=True)
            results["newsletter"] = {"error": str(e)}
            console.print(f"  [red]✗[/red] Newsletter failed: {e}")
    else:
        console.print("\n[dim]Phase 4: Newsletter — SKIPPED[/dim]")

    # Phase 5: IndexNow
    console.print("\n[bold cyan]Phase 5:[/bold cyan] IndexNow submission...")
    try:
        from src.distribution.runner import run_indexnow
        indexnow_result = run_indexnow()
        results["indexnow"] = indexnow_result
        console.print(f"  [green]✓[/green] IndexNow: {indexnow_result}")
    except Exception as e:
        logger.error("IndexNow failed: %s", e, exc_info=True)
        results["indexnow"] = {"error": str(e)}
        console.print(f"  [yellow]![/yellow] IndexNow failed (non-fatal): {e}")

    # Phase 6: SEO audit
    console.print("\n[bold cyan]Phase 6:[/bold cyan] Running SEO audit...")
    try:
        from src.seo.audit import run_audit
        seo_report = run_audit(max_pages=200)
        results["seo_audit"] = {
            "pages_crawled": seo_report.pages_crawled,
            "errors": len(seo_report.errors),
            "warnings": len(seo_report.warnings),
        }
        if seo_report.errors:
            console.print(f"  [yellow]![/yellow] SEO audit: {seo_report.pages_crawled} pages, {len(seo_report.errors)} errors, {len(seo_report.warnings)} warnings")
            for f in seo_report.errors[:10]:
                console.print(f"        [red]error:[/red] {f}")
        else:
            console.print(f"  [green]✓[/green] SEO audit: {seo_report.pages_crawled} pages, 0 errors, {len(seo_report.warnings)} warnings")

        # Phase 6b: Auto-fix SEO content issues
        console.print("\n[bold cyan]Phase 6b:[/bold cyan] Auto-fixing SEO content issues...")
        try:
            from src.seo.content_fixer import fix_content_issues
            fix_result = fix_content_issues(seo_report)
            results["seo_autofix"] = fix_result
            if fix_result.get("fixed", 0) > 0:
                console.print(
                    f"  [green]✓[/green] SEO auto-fix: "
                    f"{fix_result['fixed']} fixed, "
                    f"{fix_result.get('skipped', 0)} skipped, "
                    f"${fix_result.get('total_cost_usd', 0):.4f} LLM cost"
                )
                for d in fix_result.get("details", []):
                    console.print(f"    · {d.get('fix', ''):22s} {d.get('path', '')}")
            else:
                reason = fix_result.get("reason", fix_result.get("status", ""))
                console.print(f"  [dim]·[/dim] SEO auto-fix: nothing to fix ({reason})")
            manual = fix_result.get("manual_fix_required", [])
            if manual:
                console.print(f"  [yellow]⚠[/yellow] {len(manual)} issue(s) need manual/template fixes:")
                for m in manual[:10]:
                    console.print(f"    · {m.get('issue', ''):22s} {m.get('path', '')}")
        except Exception as e:
            logger.error("SEO auto-fix failed: %s", e, exc_info=True)
            results["seo_autofix"] = {"error": str(e)}
            console.print(f"  [yellow]![/yellow] SEO auto-fix failed (non-fatal): {e}")

        # Ahrefs site audit + auto fix. Daily: IndexNow submission.
        # Weekly (Monday): full issue-type scan + auto fix.
        from datetime import datetime as _dt
        _is_weekly = _dt.utcnow().weekday() == 0  # Monday
        _ahrefs_label = "weekly" if _is_weekly else "daily"
        console.print(f"\n[bold cyan]Ahrefs site audit + auto fix[/bold cyan] ({_ahrefs_label})...")
        if settings.ahrefs_api_key:
            try:
                from src.seo.ahrefs_audit import run_ahrefs_audit
                ahrefs_report = run_ahrefs_audit(weekly=_is_weekly)
                results["ahrefs_audit"] = ahrefs_report.summary()
                console.print(
                    f"  [green]✓[/green] Ahrefs audit: "
                    f"{ahrefs_report.total_findings} findings, "
                    f"{ahrefs_report.auto_fixed} auto-fixed, "
                    f"{ahrefs_report.alerts} alerts, "
                    f"{ahrefs_report.units_used} API units"
                )
                if ahrefs_report.health_score is not None:
                    console.print(f"    Health score: {ahrefs_report.health_score}/100")
            except Exception as e:
                logger.warning("Ahrefs audit failed: %s", e, exc_info=True)
                results["ahrefs_audit"] = {"error": str(e)}
                console.print(f"  [yellow]![/yellow] Ahrefs audit failed (non-fatal): {e}")
        else:
            console.print("  [dim]Skipped — AHREFS_API_KEY not configured[/dim]")
            results["ahrefs_audit"] = {"status": "skipped", "reason": "no API key"}

    except Exception as e:
        logger.error("SEO audit failed: %s", e, exc_info=True)
        results["seo_audit"] = {"error": str(e)}
        console.print(f"  [yellow]![/yellow] SEO audit failed (non-fatal): {e}")

    # Phase 7: Sitemap sync
    console.print("\n[bold cyan]Phase 7:[/bold cyan] Sitemap audit & sync...")
    try:
        from scripts.sync_sitemap import run_sync
        sync_result = run_sync(dry_run=dry_run)
        results["sitemap_sync"] = sync_result
        missing = sync_result.get("missing_routes", [])
        dead = sync_result.get("dead_urls", [])
        patched = sync_result.get("patched", 0)
        pushed = sync_result.get("pushed", False)
        parts = [f"{sync_result.get('live_urls', 0)} live URLs"]
        if missing:
            parts.append(f"{len(missing)} missing route(s)")
        if dead:
            parts.append(f"{len(dead)} dead link(s)")
        if patched:
            parts.append(f"{patched} auto-added" + (" & pushed" if pushed else " (push failed)"))
        if dead:
            console.print(f"  [yellow]![/yellow] Sitemap sync: {', '.join(parts)}")
        else:
            console.print(f"  [green]✓[/green] Sitemap sync: {', '.join(parts)}")
    except Exception as e:
        logger.error("Sitemap sync failed: %s", e, exc_info=True)
        results["sitemap_sync"] = {"error": str(e)}
        console.print(f"  [yellow]![/yellow] Sitemap sync failed (non-fatal): {e}")

    _print_summary(results, start)


def _print_summary(results: dict, start: float):
    elapsed = time.time() - start
    table = Table(title="Pipeline Summary")
    table.add_column("Phase", style="bold")
    table.add_column("Result")
    for phase, result in results.items():
        if isinstance(result, dict) and "error" in result:
            table.add_row(phase.title(), f"[red]Error: {result['error'][:80]}[/red]")
        else:
            table.add_row(phase.title(), f"[green]{result}[/green]")
    table.add_row("Duration", f"{elapsed:.1f}s")
    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    main()
