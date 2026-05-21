#!/usr/bin/env python3
"""
Generate (or refresh) all Ban the Bots landing pages:
  - /ai-backlash/         (pillar)
  - /responsible-ai/*/    (8 industry pages)
  - /explainers/*/        (seed explainers)

Usage:
    python scripts/generate_landing_pages.py
    python scripts/generate_landing_pages.py --force
    python scripts/generate_landing_pages.py --skip-explainers
    python scripts/generate_landing_pages.py --skip-pillar --skip-industry
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Make sure the repo root is on sys.path when running as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

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
logger = logging.getLogger("generate_landing_pages")

# Seed explainers: (slug, topic_title, search_intent)
SEED_EXPLAINERS = [
    (
        "eu-ai-act",
        "What Is the EU AI Act? Plain-English Guide for Everyone",
        "what is eu ai act and what does it mean for me",
    ),
    (
        "ai-jobs",
        "Is AI Really Taking Jobs? What the Data Actually Says",
        "is ai taking jobs statistics workers",
    ),
    (
        "ai-water-use",
        "How Much Water Do AI Data Centers Use?",
        "how much water does ai use data centers",
    ),
    (
        "no-ai-policy",
        "How to Write a No-AI Policy (For Anyone, Not Just Businesses)",
        "no ai policy template freelancer artist creator",
    ),
    # New — culture/slop cluster (KD 19.2, zero current coverage)
    (
        "ai-slop",
        "What Is AI Slop? Why the Internet Feels Worse Than It Used To",
        "what is ai slop meaning internet getting worse",
    ),
    # New — creator/copyright cluster (KD 8.8, easiest to rank)
    (
        "ai-art-theft",
        "Is AI Stealing Art? What Artists Are Fighting For and Why It Matters",
        "is ai art theft stealing from artists copyright opt out of ai training have i been trained spawning",
    ),
    # New — labor/jobs cluster (compete with willrobotstakemyjob.com)
    (
        "ai-proof-jobs",
        "The Most AI-Proof Jobs: What Work Humans Will Always Do Better",
        "what jobs can ai not replace most ai proof careers",
    ),
    # New — data center/local cluster, community angle
    (
        "data-center-impact",
        "AI Data Centers Near You: Water, Power, and Property Values",
        "ai data center near me water usage environmental impact community",
    ),
    # New — parent/student angle on labor cluster
    (
        "what-to-study",
        "What Should Your Kids Study to Be AI-Proof? A Parent's Guide",
        "what should kids study for future with ai jobs",
    ),
    # New — risk/safety cluster, citizen angle
    (
        "ai-regulation",
        "AI Laws Being Passed Right Now: What They Mean for You",
        "ai regulation news us eu uk what it means for regular people",
    ),
]


@click.command()
@click.option("--force", is_flag=True, help="Regenerate all pages even if fresh")
@click.option("--skip-pillar", is_flag=True, help="Skip the /ai-backlash/ pillar page")
@click.option("--skip-industry", is_flag=True, help="Skip the 8 industry pages")
@click.option("--skip-explainers", is_flag=True, help="Skip the seed explainer pages")
@click.option("--skip-ai-proof-jobs", is_flag=True, help="Skip the /ai-proof-jobs/ pillar page")
@click.option("--skip-parents", is_flag=True, help="Skip the /parents/ hub and spoke pages")
def main(force: bool, skip_pillar: bool, skip_industry: bool, skip_explainers: bool, skip_ai_proof_jobs: bool, skip_parents: bool):
    """Ban the Bots — Generate / refresh all landing pages."""

    console.print(Panel("[bold]Ban the Bots — Landing Page Generator[/bold]", style="blue"))

    from src.landing_generator import (
        INDUSTRY_SLUGS,
        PARENT_SPOKE_SLUGS,
        generate_pillar_page,
        generate_ai_proof_jobs_pillar,
        generate_industry_page,
        generate_all_industry_pages,
        generate_explainer,
        generate_parent_hub,
        generate_parent_spoke,
    )

    results: list[tuple[str, str, float | None]] = []  # (path, status, cost)
    start = time.time()
    total_cost = 0.0

    # ── Pillar ────────────────────────────────────────────────────────────────
    if not skip_pillar:
        console.print("\n[bold cyan]Phase 1:[/bold cyan] Pillar page (/ai-backlash/) ...")
        try:
            row = generate_pillar_page(force=force)
            cost = row.llm_cost_usd or 0.0
            total_cost += cost
            results.append((row.canonical_path, "ok", cost))
            console.print(
                f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}"
            )
        except Exception as e:
            logger.error("Pillar page failed: %s", e, exc_info=True)
            results.append(("/ai-backlash/", f"error: {e}", None))
            console.print(f"  [red]✗[/red] Pillar failed: {e}")
    else:
        console.print("\n[dim]Phase 1: Pillar — SKIPPED[/dim]")

    # ── Industry pages ────────────────────────────────────────────────────────
    if not skip_industry:
        console.print(f"\n[bold cyan]Phase 2:[/bold cyan] Industry pages ({len(INDUSTRY_SLUGS)} pages) ...")
        for slug in INDUSTRY_SLUGS:
            try:
                row = generate_industry_page(slug, force=force)
                cost = row.llm_cost_usd or 0.0
                total_cost += cost
                results.append((row.canonical_path, "ok", cost))
                console.print(
                    f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}"
                )
            except Exception as e:
                logger.error("Industry page %s failed: %s", slug, e, exc_info=True)
                results.append((f"/responsible-ai/{slug}/", f"error: {e}", None))
                console.print(f"  [red]✗[/red] {slug}: {e}")
    else:
        console.print("\n[dim]Phase 2: Industry pages — SKIPPED[/dim]")

    # ── AI-Proof Jobs pillar ──────────────────────────────────────────────────
    if not skip_ai_proof_jobs:
        console.print("\n[bold cyan]Phase 3a:[/bold cyan] AI-Proof Jobs pillar (/ai-proof-jobs/) ...")
        try:
            row = generate_ai_proof_jobs_pillar(force=force)
            cost = row.llm_cost_usd or 0.0
            total_cost += cost
            results.append((row.canonical_path, "ok", cost))
            console.print(
                f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}"
            )
        except Exception as e:
            logger.error("AI-proof jobs pillar failed: %s", e, exc_info=True)
            results.append(("/ai-proof-jobs/", f"error: {e}", None))
            console.print(f"  [red]✗[/red] AI-proof jobs failed: {e}")
    else:
        console.print("\n[dim]Phase 3a: AI-Proof Jobs — SKIPPED[/dim]")

    # ── Explainers ────────────────────────────────────────────────────────────
    if not skip_explainers:
        console.print(f"\n[bold cyan]Phase 3:[/bold cyan] Seed explainers ({len(SEED_EXPLAINERS)} pages) ...")
        for slug, topic_title, search_intent in SEED_EXPLAINERS:
            try:
                row = generate_explainer(
                    slug,
                    topic_title=topic_title,
                    search_intent=search_intent,
                    force=force,
                )
                cost = row.llm_cost_usd or 0.0
                total_cost += cost
                results.append((row.canonical_path, "ok", cost))
                console.print(
                    f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}"
                )
            except Exception as e:
                logger.error("Explainer %s failed: %s", slug, e, exc_info=True)
                results.append((f"/explainers/{slug}", f"error: {e}", None))
                console.print(f"  [red]✗[/red] {slug}: {e}")
    else:
        console.print("\n[dim]Phase 3: Explainers — SKIPPED[/dim]")

    # ── Parenting hub + spokes ────────────────────────────────────────────────
    if not skip_parents:
        console.print(f"\n[bold cyan]Phase 4:[/bold cyan] Parenting hub + {len(PARENT_SPOKE_SLUGS)} spoke pages ...")
        # Hub first
        try:
            row = generate_parent_hub(force=force)
            cost = row.llm_cost_usd or 0.0
            total_cost += cost
            results.append((row.canonical_path, "ok", cost))
            console.print(f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}")
        except Exception as e:
            logger.error("Parent hub failed: %s", e, exc_info=True)
            results.append(("/parents/", f"error: {e}", None))
            console.print(f"  [red]✗[/red] /parents/: {e}")
        # Spoke pages
        for slug in PARENT_SPOKE_SLUGS:
            try:
                row = generate_parent_spoke(slug, force=force)
                cost = row.llm_cost_usd or 0.0
                total_cost += cost
                results.append((row.canonical_path, "ok", cost))
                console.print(f"  [green]✓[/green] {row.canonical_path} — {row.word_count} words, ${cost:.4f}")
            except Exception as e:
                logger.error("Parent spoke %s failed: %s", slug, e, exc_info=True)
                results.append((f"/parents/{slug}/", f"error: {e}", None))
                console.print(f"  [red]✗[/red] /parents/{slug}/: {e}")
    else:
        console.print("\n[dim]Phase 4: Parenting hub — SKIPPED[/dim]")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start
    table = Table(title="Landing Page Generation Summary")
    table.add_column("Page", style="bold")
    table.add_column("Status")
    table.add_column("LLM cost")
    ok_count = 0
    for path, status, cost in results:
        if status == "ok":
            ok_count += 1
            table.add_row(path, "[green]ok[/green]", f"${cost:.4f}" if cost else "—")
        else:
            table.add_row(path, f"[red]{status[:60]}[/red]", "—")
    table.add_row("TOTAL", f"{ok_count}/{len(results)} succeeded", f"${total_cost:.4f}")
    table.add_row("Duration", f"{elapsed:.1f}s", "")
    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    main()
