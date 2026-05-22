#!/usr/bin/env python3
"""Submit URLs to IndexNow on demand."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("urls", nargs=-1)
@click.option("--all-posts", is_flag=True, default=False, help="Submit all blog post URLs")
@click.option("--days", default=7, help="Submit posts published in last N days (with --all-posts)")
def main(urls, all_posts, days):
    """Submit one or more URLs to IndexNow.

    Usage:
      python scripts/indexnow_submit.py https://rankandpay.org/briefing/my-post/
      python scripts/indexnow_submit.py --all-posts --days 3
    """
    from src.models import init_db, BlogPost, engine
    init_db()

    url_list = list(urls)

    if all_posts:
        from datetime import date, timedelta
        from sqlalchemy.orm import Session

        cutoff = date.today() - timedelta(days=days)
        with Session(engine) as session:
            posts = (
                session.query(BlogPost)
                .filter(BlogPost.published_date >= cutoff)
                .all()
            )
        from src.config import settings
        base = settings.canonical_site_url.rstrip("/")
        for p in posts:
            url_list.append(f"{base}/briefing/{p.slug}/")

    if not url_list:
        console.print("[yellow]No URLs to submit.[/yellow]")
        sys.exit(0)

    console.print(f"Submitting {len(url_list)} URL(s) to IndexNow...")

    from src.distribution.indexnow import submit_urls
    result = submit_urls(url_list)

    if result.success:
        console.print(f"[green]✓[/green] Submitted {result.submitted} URL(s) — HTTP {result.status_code}")
    else:
        console.print(f"[red]✗[/red] Failed: {result.response_snippet}")
        sys.exit(1)


if __name__ == "__main__":
    main()
