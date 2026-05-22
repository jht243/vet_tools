"""Newsletter dispatch — console (dev), Resend (transactional), Buttondown (broadcast)."""
from __future__ import annotations
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.models import BlogPost, engine

logger = logging.getLogger(__name__)


def _build_digest_html(posts: list[BlogPost], pub_date: date) -> str:
    lines = [
        f"<h1>VA Claims Workspace — {pub_date.strftime('%B %d, %Y')}</h1>",
        "<p>Today's top VA &amp; military benefits briefings:</p>",
        "<hr>",
    ]
    for post in posts[:6]:
        url = f"https://vaclaimsworkspace.com/briefing/{post.slug}/"
        lines.append(f'<h2><a href="{url}">{post.title}</a></h2>')
        if post.summary:
            lines.append(f"<p>{post.summary[:200]}…</p>")
        lines.append(f'<p><a href="{url}">Read more →</a></p>')
        lines.append("<hr>")
    lines.append(
        '<p style="font-size:12px;color:#666;">'
        "VA Claims Workspace — vaclaimsworkspace.com<br>"
        "For informational purposes only; not legal or benefits advice.<br>"
        '<a href="{{ unsubscribe_url }}">Unsubscribe</a>'
        "</p>"
    )
    return "\n".join(lines)


def _build_digest_text(posts: list[BlogPost], pub_date: date) -> str:
    lines = [
        f"VA Claims Workspace — {pub_date.strftime('%B %d, %Y')}",
        "=" * 50,
        "",
    ]
    for post in posts[:6]:
        url = f"https://vaclaimsworkspace.com/briefing/{post.slug}/"
        lines.append(post.title)
        if post.summary:
            lines.append(post.summary[:200] + "…")
        lines.append(url)
        lines.append("")
    lines.append("VA Claims Workspace — vaclaimsworkspace.com")
    lines.append("For informational purposes only; not legal or benefits advice.")
    return "\n".join(lines)


class ConsoleProvider:
    def send(self, subject: str, html: str, text: str) -> dict:
        logger.info("Newsletter (console): %s", subject)
        logger.info("--- TEXT ---\n%s", text[:400])
        return {"status": "ok", "provider": "console"}


class ResendProvider:
    def __init__(self, api_key: str, from_email: str, to_email: str):
        self._key = api_key
        self._from = from_email
        self._to = to_email

    def send(self, subject: str, html: str, text: str) -> dict:
        import httpx

        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={
                "from": self._from,
                "to": [self._to],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=20,
        )
        if resp.status_code >= 400:
            logger.error("Resend error %d: %s", resp.status_code, resp.text[:200])
            return {"status": "error", "code": resp.status_code}
        return {"status": "ok", "provider": "resend", "id": resp.json().get("id")}


class ButtondownProvider:
    def __init__(self, api_key: str):
        self._key = api_key

    def send(self, subject: str, html: str, text: str) -> dict:
        import httpx

        resp = httpx.post(
            "https://api.buttondown.email/v1/emails",
            headers={"Authorization": f"Token {self._key}", "Content-Type": "application/json"},
            json={
                "subject": subject,
                "body": html,
                "status": "about_to_send",
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            logger.error("Buttondown error %d: %s", resp.status_code, resp.text[:200])
            return {"status": "error", "code": resp.status_code}
        return {"status": "ok", "provider": "buttondown", "id": resp.json().get("id")}


def _get_provider(settings):
    if settings.buttondown_api_key:
        return ButtondownProvider(settings.buttondown_api_key)
    if settings.resend_api_key:
        from_email = getattr(settings, "resend_from_email", "briefings@vaclaimsworkspace.com")
        to_email = getattr(settings, "resend_to_email", "")
        return ResendProvider(settings.resend_api_key, from_email, to_email)
    return ConsoleProvider()


def send_newsletter(dry_run: bool = False) -> dict:
    from src.config import settings

    pub_date = date.today()
    with Session(engine) as session:
        posts = (
            session.query(BlogPost)
            .filter(BlogPost.published_date == pub_date)
            .order_by(BlogPost.created_at.desc())
            .limit(6)
            .all()
        )

    if not posts:
        logger.info("newsletter: no posts for today; skipping")
        return {"status": "skipped", "reason": "no posts today"}

    subject = f"VA & Military Benefits Update — {pub_date.strftime('%B %d, %Y')}"
    html = _build_digest_html(posts, pub_date)
    text = _build_digest_text(posts, pub_date)

    if dry_run:
        logger.info("newsletter: dry_run — subject: %s, %d posts", subject, len(posts))
        return {"status": "dry_run", "posts": len(posts), "subject": subject}

    provider = _get_provider(settings)
    result = provider.send(subject, html, text)
    logger.info("newsletter: sent via %s — %s", type(provider).__name__, result)
    return result
