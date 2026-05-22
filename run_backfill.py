#!/usr/bin/env python3
"""
Backfill runner for historical data and content regeneration.

Usage:
    python run_backfill.py --blog-posts --days 30
    python run_backfill.py --landing-pages --page-type pillar
    python run_backfill.py --og-images --days 14
    python run_backfill.py --takeaways --days 30
"""

import logging
import sys

import click
from rich.console import Console

from src.config import settings

console = Console()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

PAGE_TYPES = ("all", "pillar", "spoke", "condition", "state", "explainer")


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("--blog-posts", "run_blog_posts", is_flag=True, default=False,
              help="Re-generate blog posts for articles that haven't been written yet.")
@click.option("--landing-pages", "run_landing_pages", is_flag=True, default=False,
              help="Regenerate landing pages by type.")
@click.option("--og-images", "run_og_images", is_flag=True, default=False,
              help="Regenerate missing OG images for blog posts.")
@click.option("--takeaways", "run_takeaways", is_flag=True, default=False,
              help="Backfill missing takeaways_json for blog posts.")
@click.option("--days", default=30, show_default=True, type=int,
              help="Look-back window in days (used by --blog-posts, --og-images, --takeaways).")
@click.option(
    "--page-type",
    default="all",
    show_default=True,
    type=click.Choice(PAGE_TYPES, case_sensitive=False),
    help="Landing-page type to regenerate (used with --landing-pages).",
)
@click.option("--dry-run", is_flag=True, default=False,
              help="Print what would be done without making any changes.")
def main(
    run_blog_posts: bool,
    run_landing_pages: bool,
    run_og_images: bool,
    run_takeaways: bool,
    days: int,
    page_type: str,
    dry_run: bool,
) -> None:
    any_selected = any([run_blog_posts, run_landing_pages, run_og_images, run_takeaways])
    if not any_selected:
        console.print(
            "[yellow]No backfill target selected. "
            "Use --blog-posts, --landing-pages, --og-images, or --takeaways.[/yellow]\n"
            "Run [cyan]python run_backfill.py --help[/cyan] for usage."
        )
        sys.exit(0)

    if dry_run:
        console.print("[yellow]Dry-run mode — no changes will be written.[/yellow]")

    console.rule("[bold blue]VA Claims Workspace — Backfill Runner[/bold blue]")
    results: dict[str, tuple[str, str]] = {}

    # ── Blog Posts ────────────────────────────────────────────────────────────
    if run_blog_posts:
        task = "Blog Posts"
        console.rule(f"[cyan]{task}[/cyan]")
        console.print(f"  Look-back: [bold]{days}[/bold] days")
        if dry_run:
            console.print(
                f"  [dim]Would call run_blog_generation(budget_override=50) "
                f"over the last {days} days[/dim]"
            )
            results[task] = ("skip", "dry-run")
        else:
            try:
                from src.blog_generator import run_blog_generation  # noqa: PLC0415

                result = run_blog_generation(budget_override=50)
                console.print(f"[green]✓ {task} complete[/green]")
                console.print(f"  Blog generation: {result}")
                results[task] = ("ok", str(result))
            except Exception as exc:  # noqa: BLE001
                log.exception("Error in %s backfill", task)
                console.print(f"[red]✗ {task} failed: {exc}[/red]")
                results[task] = ("fail", str(exc))

    # ── Landing Pages ─────────────────────────────────────────────────────────
    if run_landing_pages:
        task = "Landing Pages"
        console.rule(f"[cyan]{task}[/cyan]")
        console.print(f"  Page type: [bold]{page_type}[/bold]")
        try:
            from src.landing_generator import generate_all_landing_pages  # noqa: PLC0415

            result = generate_all_landing_pages(page_type=page_type, dry_run=dry_run)
            console.print(f"[green]✓ {task} complete[/green]")
            console.print(f"  Landing pages: {result}")
            results[task] = ("ok", str(result))
        except Exception as exc:  # noqa: BLE001
            log.exception("Error in %s backfill", task)
            console.print(f"[red]✗ {task} failed: {exc}[/red]")
            results[task] = ("fail", str(exc))

    # ── OG Images ─────────────────────────────────────────────────────────────
    if run_og_images:
        task = "OG Images"
        console.rule(f"[cyan]{task}[/cyan]")
        console.print(f"  Look-back: [bold]{days}[/bold] days")
        try:
            from src.og_image import backfill_og_images  # noqa: PLC0415

            result = backfill_og_images(days=days, dry_run=dry_run)
            console.print(f"[green]✓ {task} complete[/green]")
            console.print(f"  OG images: {result}")
            results[task] = ("ok", str(result))
        except Exception as exc:  # noqa: BLE001
            log.exception("Error in %s backfill", task)
            console.print(f"[red]✗ {task} failed: {exc}[/red]")
            results[task] = ("fail", str(exc))

    # ── Takeaways ─────────────────────────────────────────────────────────────
    if run_takeaways:
        task = "Takeaways"
        console.rule(f"[cyan]{task}[/cyan]")
        console.print(f"  Look-back: [bold]{days}[/bold] days")
        try:
            from src.blog_generator import backfill_takeaways  # noqa: PLC0415

            result = backfill_takeaways(days=days, dry_run=dry_run)
            console.print(f"[green]✓ {task} complete[/green]")
            console.print(f"  Takeaways: {result}")
            results[task] = ("ok", str(result))
        except Exception as exc:  # noqa: BLE001
            log.exception("Error in %s backfill", task)
            console.print(f"[red]✗ {task} failed: {exc}[/red]")
            results[task] = ("fail", str(exc))

    # ── Summary ───────────────────────────────────────────────────────────────
    console.rule("[bold blue]Backfill Summary[/bold blue]")
    for task, (state, detail) in results.items():
        icon = {"ok": "[green]✓[/green]", "skip": "[dim]—[/dim]", "fail": "[red]✗[/red]"}.get(
            state, state
        )
        suffix = f": {detail}" if detail else ""
        console.print(f"  {icon} {task}{suffix}")

    console.print()

    failures = [t for t, (state, _) in results.items() if state == "fail"]
    if failures:
        console.print(f"[red]Failed:[/red] {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
