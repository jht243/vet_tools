#!/usr/bin/env python3
"""Send daily SEO digest email — GSC performance + audit issues."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from rich.console import Console

console = Console()


def _build_html(audit_issues: list, post_count: int, pub_date) -> str:
    issue_rows = ""
    for pi in audit_issues[:20]:
        issues_str = "; ".join(pi.issues)
        issue_rows += f"<tr><td>{pi.url}</td><td>{issues_str}</td></tr>"

    if audit_issues:
        audit_section = (
            f'<table border="1" cellpadding="6" style="border-collapse:collapse;font-size:12px;">'
            f"<tr><th>URL</th><th>Issues</th></tr>{issue_rows}</table>"
        )
    else:
        audit_section = "<p>No issues found.</p>"

    return f"""
<h1>VA Claims Workspace — Daily SEO Digest</h1>
<p><strong>Date:</strong> {pub_date}</p>
<p><strong>Posts published today:</strong> {post_count}</p>
<hr>
<h2>SEO Audit Issues ({len(audit_issues)} pages)</h2>
{audit_section}
<hr>
<p style="font-size:11px;color:#888;">VA Claims Workspace internal report — vaclaimsworkspace.com</p>
"""


@click.command()
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--skip-audit", is_flag=True, default=False)
def main(dry_run, skip_audit):
    """Send daily SEO email digest."""
    from src.models import init_db, BlogPost, engine
    from src.config import settings
    from datetime import date
    from sqlalchemy.orm import Session

    init_db()

    pub_date = date.today()

    with Session(engine) as session:
        post_count = (
            session.query(BlogPost)
            .filter(BlogPost.published_date == pub_date)
            .count()
        )

    audit_issues = []
    if not skip_audit:
        console.print("Running SEO audit...")
        try:
            from src.seo.audit import run_audit
            audit_issues = run_audit(max_pages=50)
        except Exception as exc:
            console.print(f"[yellow]Audit error: {exc}[/yellow]")

    html = _build_html(audit_issues, post_count, pub_date)

    to_email = getattr(settings, "seo_email_to", "") or getattr(settings, "resend_to_email", "")
    if not to_email:
        console.print("[yellow]No SEO_EMAIL_TO configured; printing to console[/yellow]")
        console.print(f"Posts today: {post_count}, Audit issues: {len(audit_issues)}")
        return

    if dry_run:
        console.print(f"[dim]DRY RUN: would send SEO digest to {to_email}[/dim]")
        console.print(f"  Posts: {post_count}, Audit issues: {len(audit_issues)}")
        return

    if settings.resend_api_key:
        import httpx
        from_email = getattr(settings, "resend_from_email", "noreply@vaclaimsworkspace.com")
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": from_email,
                "to": [to_email],
                "subject": f"VA Claims Workspace SEO Digest — {pub_date}",
                "html": html,
            },
            timeout=20,
        )
        if resp.status_code < 400:
            console.print(f"[green]✓[/green] SEO digest sent to {to_email}")
        else:
            console.print(f"[red]✗[/red] Resend error {resp.status_code}: {resp.text[:200]}")
            sys.exit(1)
    else:
        console.print("[yellow]No RESEND_API_KEY; digest not sent[/yellow]")


if __name__ == "__main__":
    main()
