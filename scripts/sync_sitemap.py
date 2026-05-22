#!/usr/bin/env python3
"""Sync sitemap to Supabase Storage and ping search engines."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console

console = Console()


def main():
    from src.models import init_db
    init_db()

    from src.config import settings
    from src.distribution.indexnow import submit_urls

    console.print("[bold]Syncing sitemap...[/bold]")

    # Ping IndexNow with sitemap URL
    sitemap_url = f"{settings.canonical_site_url.rstrip('/')}/sitemap.xml"
    news_sitemap_url = f"{settings.canonical_site_url.rstrip('/')}/news-sitemap.xml"

    result = submit_urls([sitemap_url, news_sitemap_url])
    if result.success:
        console.print(f"[green]✓[/green] IndexNow: pinged {result.submitted} URL(s)")
    else:
        console.print(f"[yellow]![/yellow] IndexNow: {result.response_snippet}")

    # Upload sitemap to Supabase Storage if configured
    from src.storage_remote import supabase_storage_enabled, upload_object
    if supabase_storage_enabled():
        import httpx
        try:
            resp = httpx.get(
                f"{settings.canonical_site_url.rstrip('/')}/sitemap.xml",
                timeout=15,
            )
            if resp.status_code == 200:
                upload_object("sitemap.xml", resp.content, content_type="application/xml")
                console.print("[green]✓[/green] Uploaded sitemap.xml to Supabase Storage")
        except Exception as exc:
            console.print(f"[yellow]![/yellow] Supabase sitemap upload skipped: {exc}")
    else:
        console.print("[dim]Supabase Storage not configured; skipping sitemap upload[/dim]")

    console.print("[green]Done.[/green]")


if __name__ == "__main__":
    main()
