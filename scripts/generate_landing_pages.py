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

# Seed explainers: (slug, topic_title, search_intent, research_context)
# research_context is pre-gathered facts/stats baked in at prompt time for richer E-E-A-T output.
# Existing entries have no research_context (empty string) — they rely on live DB signal only.

AGI_RESEARCH_CONTEXT = """
KEY FACTS AND STATISTICS:
- AGI (Artificial General Intelligence) does not yet exist as of 2026. Current AI — including ChatGPT, Gemini, and Claude — is "narrow AI": excellent at specific tasks but unable to transfer knowledge across unrelated domains without retraining.
- Expert timeline predictions vary dramatically: Dario Amodei (Anthropic CEO) has suggested AGI could arrive as early as 2026; Demis Hassabis (Google DeepMind) gives a 50/50 chance by 2030; most AI researchers surveyed put the median probability at 2047.
- A January 2026 White House Council of Economic Advisers report flagged AGI-level automation as a potential driver of extreme wealth concentration, with wages for human workers potentially being pushed toward zero as AGI labour replaces them.
- McKinsey estimates narrow AI already adds $2.6–4.4 trillion annually to the global economy; AGI would automate cognitive labour across all industries simultaneously.
- A February 2025 academic paper (arXiv:2502.07050) warns AGI could end human employment as currently understood, requiring a renegotiated social contract.
- World Economic Forum: 40% of companies plan to trim their workforces as AI automation expands; 66% plan to hire workers with AI skills.
- "Superintelligence" refers to AI that surpasses human intelligence in every domain — a step beyond AGI. Philosopher Nick Bostrom's 2014 book "Superintelligence" popularised concerns about misalignment: a superintelligent system pursuing the wrong goal could be catastrophic and irreversible.
- The UK AI Safety Institute (AISI) and Anthropic both treat the AGI threshold as a critical safety checkpoint.
- OpenAI CEO Sam Altman claimed in early 2025 that OpenAI had "basically achieved" AGI — a claim disputed by most researchers, who note there is no agreed scientific definition or benchmark.
- Key distinction: AGI ≠ superintelligence. AGI = human-level general intelligence. Superintelligence = surpasses human intelligence in every domain.

KEY RISKS FOR ORDINARY PEOPLE:
- Job displacement across white-collar and knowledge work sectors, not just manual labour
- Extreme wealth concentration if AGI is owned by a small number of corporations or governments
- Loss of human agency in decisions (medical, legal, financial) if AGI systems replace human judgment
- Alignment failure: an AGI pursuing a subtly wrong objective could cause catastrophic harm

WHAT PEOPLE CAN DO:
- Follow AI safety news at /briefing
- Understand which jobs are most at risk at /will-ai-replace-my-job/ and /ai-proof-jobs/
- Track AI regulation at /explainers/ai-regulation
""".strip()

FACIAL_RECOGNITION_RESEARCH_CONTEXT = """
KEY FACTS AND STATISTICS:
- The global facial recognition market was worth $8 billion in 2025, projected to reach $13 billion by 2029.
- The EU AI Act, fully applicable from August 2, 2026, prohibits real-time facial recognition in public spaces by law enforcement, with narrow exceptions. It classifies mass facial recognition databases as "unacceptable risk" AI.
- In the United States, there is no federal facial recognition law as of 2026. Nearly two dozen states have passed biometric privacy laws. At least 16 cities have banned police use of facial recognition, including San Francisco, Boston, and Portland.
- Milwaukee became the latest city to ban police facial recognition in February 2026 after public outcry.
- At least 14 people in the US have been wrongfully arrested due to facial recognition false positives — all publicly confirmed cases involve Black people.
- Robert Williams case (Detroit, 2020): wrongfully arrested after facial recognition matched his expired driver's licence to surveillance footage of a shoplifter. He was not near the store. The case settled in June 2024 with landmark policy changes at Detroit PD — the first settlement requiring police facial recognition policy reform in the US.
- Porcha Woodruff case (Detroit, 2023): wrongfully arrested while eight months pregnant after facial recognition matched her to a carjacking suspect. The actual perpetrator was not visibly pregnant.
- A National Academies of Sciences 2024 report found facial recognition accuracy varies significantly across demographic groups — it is least accurate on darker-skinned faces and women, increasing the risk of wrongful targeting for those groups.
- London's Metropolitan Police scanned approximately 1 million faces in 2025 using live facial recognition cameras.
- UK Home Secretary acknowledged in July 2025 that the UK needs "a proper, clear governance framework" for facial recognition — one does not yet exist.

KEY PRIVACY RISKS:
- Mass surveillance chilling effect on free assembly and expression
- Algorithmic bias disproportionately harming Black, Asian, and female individuals
- No consent, no notification: people are scanned without knowing
- Data breaches: biometric data, once stolen, cannot be changed like a password

WHAT PEOPLE CAN DO:
- Know your rights: in cities with bans, demand police comply
- Support facial recognition legislation at /fighting-back/
- If wrongfully arrested, contact the ACLU
- Track AI incidents at /ai-incidents/
""".strip()

DEEPFAKES_RESEARCH_CONTEXT = """
KEY FACTS AND STATISTICS:
- A deepfake is a synthetic image, video, or audio created by AI that depicts someone doing or saying something they never did — often indistinguishable from real footage.
- 46 US states have enacted laws targeting AI-generated synthetic media as of spring 2026.
- The TAKE IT DOWN Act was signed into law by President Trump on May 19, 2025. It criminalises the non-consensual publication of intimate images (real or AI-generated) with penalties of up to 3 years in prison. It also requires platforms to remove flagged content within 48 hours of notice. The first conviction under this law was issued in April 2026.
- The DEFIANCE Act (Disrupt Explicit Forged Images and Non-Consensual Edits Act) passed the US Senate unanimously in January 2026. It creates a federal right of action allowing victims to sue creators and distributors, with statutory damages up to $150,000 (or $250,000 if linked to sexual assault or stalking).
- Taylor Swift case (January 2024): AI-generated sexually explicit images of Swift spread across social media; one post was viewed over 47 million times before removal. In November 2025, McAfee ranked Taylor Swift as the #1 celebrity most targeted by deepfake scammers.
- In August 2025, Elon Musk's Grok AI image tool generated sexually explicit deepfakes of Taylor Swift from innocuous prompts, reigniting debate about platform responsibility.
- Women and girls are the overwhelming majority of deepfake victims. Celebrities are disproportionately targeted but ordinary people — including teenagers — are increasingly victimised.
- How to spot a deepfake: look for unnatural blinking, inconsistent lighting, blurry edges around hair, audio that doesn't sync with mouth movements, and use detection tools like Microsoft's Video Authenticator or Sensity AI.

LEGAL LANDSCAPE:
- TAKE IT DOWN Act (federal, 2025): criminalises NCII and deepfakes intended to harm
- DEFIANCE Act (federal, 2026): civil right of action for victims
- 46 states have their own deepfake laws covering political ads, sexual content, or both
- EU: the AI Act requires deepfakes to be labelled; the Digital Services Act requires platform takedowns
- California AB 2655 (2024): partially struck down by federal judge citing Section 230

WHAT PEOPLE CAN DO:
- If you are a victim: report to the NCMEC (minors) or the Cyber Civil Rights Initiative
- US federal law (TAKE IT DOWN Act) gives you a right to request takedown within 48 hours
- Document evidence before reporting (screenshots, URLs)
- Check /ai-lawsuits/ for ongoing legal cases involving deepfake platforms
""".strip()

AUTONOMOUS_WEAPONS_RESEARCH_CONTEXT = """
KEY FACTS AND STATISTICS:
- Lethal Autonomous Weapons Systems (LAWS) — often called "killer robots" — are weapons that can select and engage targets without meaningful human control. They exist and are being deployed today, not just in science fiction.
- Lavender (Israel/Gaza, 2024): The Israeli military deployed an AI system called "Lavender" that analysed surveillance data on 2.3 million Gazans and assigned each person a 1–100 probability score for militant affiliation. At its peak, Lavender listed 37,000 Palestinian men as potential targets. The system could identify and approve a strike target in 20 seconds, often without meaningful human review. A companion system, "Where's Daddy?", tracked targets to their family homes. Intelligence officers told +972 Magazine the system accepted up to 15–20 civilian deaths per low-ranking militant.
- Human Rights Watch, the ICRC, and UN human rights experts have stated the use of Lavender raises serious violations of international humanitarian law, particularly the principles of distinction and proportionality.
- The Pentagon requested a record $14.2 billion for AI and autonomous research for fiscal year 2026. Its "Replicator" programme received $1 billion in 2025 to fast-track thousands of expendable autonomous drones.
- Russia deployed the "Iron Beam" laser system in late 2025, using autonomous targeting to neutralise threats faster than any human operator.
- UN General Assembly First Committee vote, November 6, 2025: 156 states voted in favour of a resolution on autonomous weapons. Only 5 nations voted against — notably the United States and Russia.
- UN Secretary-General António Guterres called in May 2025 for a legally binding treaty to regulate and ban certain autonomous weapons by 2026. More than 120 countries support negotiations.
- The Campaign to Stop Killer Robots (coalition of 270+ NGOs) argues that removing human judgement from lethal decisions violates human dignity and makes accountability for war crimes impossible.
- Key legal gap: international humanitarian law (the Geneva Conventions) was written before autonomous weapons existed. No treaty currently prohibits LAWS, though the ICRC argues existing rules require meaningful human control.

KEY CONCERNS FOR ORDINARY PEOPLE:
- Accountability vacuum: if an AI weapon kills civilians, who is responsible?
- Proliferation: autonomous weapons could be built cheaply and deployed by non-state actors and terrorist groups
- Lowered threshold for war: cheap drones with autonomous targeting make military action easier to initiate
- Export: military AI developed in conflict zones is often later sold or licensed to authoritarian governments

WHAT PEOPLE CAN DO:
- Support the Campaign to Stop Killer Robots (stopkillerrobots.org)
- Contact elected representatives to support a UN LAWS treaty
- Follow developments at /briefing and /fighting-back/
""".strip()

SEED_EXPLAINERS = [
    # (slug, topic_title, search_intent, research_context)
    (
        "eu-ai-act",
        "What Is the EU AI Act? Plain-English Guide for Everyone",
        "what is eu ai act and what does it mean for me",
        "",
    ),
    (
        "ai-jobs",
        "Is AI Really Taking Jobs? What the Data Actually Says",
        "is ai taking jobs statistics workers",
        "",
    ),
    (
        "ai-water-use",
        "How Much Water Does AI Use — And What About Energy?",
        "how much water does ai use data centers ai energy consumption ai power why does ai use so much water how much water is used for ai ai water consumption does ai use a lot of water",
        "",
    ),
    (
        "no-ai-policy",
        "How to Write a No-AI Policy (For Anyone, Not Just Businesses)",
        "no ai policy template freelancer artist creator",
        "",
    ),
    (
        "ai-slop",
        "What Is AI Slop? Why the Internet Feels Worse Than It Used To",
        "what is ai slop meaning internet getting worse is this image ai generated how to detect ai content ai image detection",
        "",
    ),
    (
        "ai-art-theft",
        "Is AI Stealing Art? What Artists Are Fighting For and Why It Matters",
        "is ai art theft stealing from artists copyright opt out of ai training have i been trained spawning chatgpt lawsuit ai copyright lawsuit news copyright ai news",
        "",
    ),
    (
        "ai-proof-jobs",
        "The Most AI-Proof Jobs: What Work Humans Will Always Do Better",
        "what jobs can ai not replace most ai proof careers",
        "",
    ),
    (
        "data-center-impact",
        "AI Data Centers Near You: Water, Power, and Property Values",
        "ai data center near me water usage environmental impact community",
        "",
    ),
    (
        "what-to-study",
        "What Should Your Kids Study to Be AI-Proof? A Parent's Guide",
        "what should kids study for future with ai jobs",
        "",
    ),
    (
        "ai-regulation",
        "AI Laws Being Passed Right Now: What They Mean for You",
        "ai regulation news us eu uk what it means for regular people eu ai act news colorado ai act trump executive order ai ai governance trends ai laws",
        "",
    ),
    # ── NEW pages ────────────────────────────────────────────────────────────────
    (
        "agi",
        "What Is AGI? Artificial General Intelligence Explained",
        "agi meaning artificial general intelligence definition risks timeline superintelligence what does agi mean agi vs ai",
        AGI_RESEARCH_CONTEXT,
    ),
    (
        "facial-recognition",
        "Facial Recognition: How It Works, Who's Watching, Your Rights",
        "facial recognition technology how it works wrongful arrests ban facial recognition laws biometric data privacy facial recognition software",
        FACIAL_RECOGNITION_RESEARCH_CONTEXT,
    ),
    (
        "deepfakes",
        "What Are Deepfakes? Laws, Harms, and How to Spot Them",
        "what are deepfakes definition how to spot a deepfake deepfake laws is deepfake porn illegal taylor swift deepfake deepfakes definition",
        DEEPFAKES_RESEARCH_CONTEXT,
    ),
    (
        "autonomous-weapons",
        "Killer Robots: The AI Weapons Nobody Voted For",
        "killer robots autonomous weapons lethal autonomous weapons lavender ai ban campaign what are killer robots autonomous weapons ban",
        AUTONOMOUS_WEAPONS_RESEARCH_CONTEXT,
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
        for entry in SEED_EXPLAINERS:
            slug, topic_title, search_intent = entry[0], entry[1], entry[2]
            research_context = entry[3] if len(entry) > 3 else ""
            try:
                row = generate_explainer(
                    slug,
                    topic_title=topic_title,
                    search_intent=search_intent,
                    research_context=research_context,
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
