"""
One-off backfill: generate blog posts for existing high-relevance briefing
entries that don't yet have one.

Usage:
    python scripts/backfill_blog_posts.py                     # default settings
    python scripts/backfill_blog_posts.py --limit 40          # cap LLM calls
    python scripts/backfill_blog_posts.py --min-relevance 6   # raise bar
    python scripts/backfill_blog_posts.py --lookback 60       # days to look back
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.blog_generator import run_blog_generation
from src.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill blog posts for existing entries")
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Maximum number of posts to generate in this run (cost cap). Default: 40 (~$1.60)",
    )
    parser.add_argument(
        "--min-relevance",
        type=int,
        default=None,
        help=f"Minimum relevance_score (default: {settings.blog_gen_min_relevance})",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        help=f"How many days back to consider (default: {settings.blog_gen_lookback_days})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
    )
    log = logging.getLogger("backfill_blog_posts")

    if args.min_relevance is not None:
        settings.blog_gen_min_relevance = args.min_relevance
    if args.lookback is not None:
        settings.blog_gen_lookback_days = args.lookback

    log.info(
        "starting backfill: limit=%d, min_relevance=%d, lookback=%d days",
        args.limit, settings.blog_gen_min_relevance, settings.blog_gen_lookback_days,
    )

    result = run_blog_generation(budget=args.limit)
    log.info("backfill complete: %s", result)


if __name__ == "__main__":
    main()
