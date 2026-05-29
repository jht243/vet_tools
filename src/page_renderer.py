"""
Page rendering helpers — builds the seo dict and jsonld for every route.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.config import settings


def _seo_title(text: str, max_len: int = 70) -> str:
    """Truncate to max_len chars, preserving whole words."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated


def _seo_desc(text: str, max_len: int = 160) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated).rstrip(".") + "…"


# ---------------------------------------------------------------------------
# Blog post SEO
# ---------------------------------------------------------------------------

def build_blog_post_seo(post) -> dict:
    """Build the seo context dict for a BlogPost detail page."""
    base = settings.canonical_site_url

    raw_title = f"{post.title} | Rank and Pay"
    title = _seo_title(raw_title, max_len=70)

    description = ""
    if post.summary:
        description = _seo_desc(post.summary, max_len=160)

    canonical = f"{base}/briefing/{post.slug}"
    og_image = f"/og/briefing/{post.slug}.png"

    published_iso = ""
    modified_iso = ""
    if post.published_date:
        if hasattr(post.published_date, "isoformat"):
            published_iso = post.published_date.isoformat()
        else:
            published_iso = str(post.published_date)
    if post.updated_at:
        if hasattr(post.updated_at, "isoformat"):
            modified_iso = post.updated_at.isoformat()
        else:
            modified_iso = str(post.updated_at)

    # Derive section and tags from sectors_json
    sectors = post.sectors_json or []
    section = sectors[0] if sectors else (post.primary_sector or "VA Benefits")
    article_tags = sectors if sectors else []

    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_image": og_image,
        "og_type": "article",
        "published_iso": published_iso,
        "modified_iso": modified_iso,
        "section": section,
        "article_tags": article_tags,
        "site_name": settings.site_name,
        "locale": settings.site_locale,
    }


def build_blog_post_jsonld(post, seo: dict) -> str:
    """Build the JSON-LD @graph string for a BlogPost detail page."""
    base = settings.canonical_site_url
    site_name = settings.site_name
    canonical = seo["canonical"]

    og_image_url = f"{base}{seo['og_image']}"

    publisher = {
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": site_name,
        "url": base,
    }

    author = {
        "@type": "Organization",
        "name": site_name,
        "url": base,
    }

    news_article: dict = {
        "@type": "NewsArticle",
        "@id": f"{canonical}#article",
        "headline": _seo_title(post.title, max_len=110),
        "description": seo.get("description", ""),
        "url": canonical,
        "datePublished": seo.get("published_iso", ""),
        "dateModified": seo.get("modified_iso", "") or seo.get("published_iso", ""),
        "image": {
            "@type": "ImageObject",
            "url": og_image_url,
            "width": 1200,
            "height": 630,
        },
        "publisher": publisher,
        "author": author,
        "inLanguage": "en-US",
        "isPartOf": {
            "@type": "WebSite",
            "@id": f"{base}/#website",
            "name": site_name,
            "url": base,
        },
    }

    if seo.get("article_tags"):
        news_article["keywords"] = ", ".join(seo["article_tags"])

    if seo.get("section"):
        news_article["articleSection"] = seo["section"]

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": base,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Briefings",
                "item": f"{base}/briefing/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": post.title,
                "item": canonical,
            },
        ],
    }

    graph = [news_article, breadcrumb]

    # FAQPage from takeaways_json if present
    takeaways = post.takeaways_json or []
    if takeaways:
        faq_items = []
        for i, takeaway in enumerate(takeaways):
            if isinstance(takeaway, dict):
                q = takeaway.get("question") or takeaway.get("q") or f"Key takeaway {i + 1}"
                a = takeaway.get("answer") or takeaway.get("a") or takeaway.get("text", "")
            else:
                q = f"Key takeaway {i + 1}"
                a = str(takeaway)
            if a:
                faq_items.append({
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": a,
                    },
                })
        if faq_items:
            graph.append({
                "@type": "FAQPage",
                "@id": f"{canonical}#faq",
                "mainEntity": faq_items,
            })

    return json.dumps(
        {"@context": "https://schema.org", "@graph": graph},
        ensure_ascii=False,
        indent=None,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# Landing page SEO
# ---------------------------------------------------------------------------

def build_landing_page_seo(page) -> dict:
    """Build the seo context dict for a LandingPage."""
    base = settings.canonical_site_url

    title = _seo_title(page.title, max_len=70)
    description = _seo_desc(page.summary or "", max_len=160) if page.summary else ""

    canonical_path = page.canonical_path or "/"
    if not canonical_path.startswith("/"):
        canonical_path = "/" + canonical_path
    canonical = f"{base}{canonical_path}"

    # Derive OG image: prefer sector-level default
    og_image = f"/static/og-default.png"

    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_image": og_image,
        "og_type": "article",
        "site_name": settings.site_name,
        "locale": settings.site_locale,
    }


def build_landing_page_jsonld(page, seo: dict, faq_block=None) -> str:
    """Build the JSON-LD @graph string for a LandingPage."""
    base = settings.canonical_site_url
    site_name = settings.site_name
    canonical = seo["canonical"]

    publisher = {
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": site_name,
        "url": base,
    }

    # Pillar pages use Article; collection/index pages use CollectionPage
    page_type = getattr(page, "page_type", "") or ""
    if page_type in ("pillar", "spoke", "explainer", "condition", "state", "page", "hub", "form"):
        content_node: dict = {
            "@type": "Article",
            "@id": f"{canonical}#article",
            "headline": page.title,
            "description": seo.get("description", ""),
            "url": canonical,
            "publisher": publisher,
            "author": publisher,
            "inLanguage": "en-US",
        }
        if page.last_generated_at:
            content_node["datePublished"] = page.last_generated_at.isoformat()
            content_node["dateModified"] = page.last_generated_at.isoformat()
        if page.updated_at:
            content_node["dateModified"] = page.updated_at.isoformat()
    else:
        content_node = {
            "@type": "CollectionPage",
            "@id": f"{canonical}#collection",
            "name": page.title,
            "description": seo.get("description", ""),
            "url": canonical,
            "publisher": publisher,
            "inLanguage": "en-US",
        }

    # Build BreadcrumbList from canonical path segments
    breadcrumb_items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": base,
        }
    ]
    canonical_path = getattr(page, "canonical_path", "") or "/"
    parts = [p for p in canonical_path.strip("/").split("/") if p]
    accumulated = base
    for i, part in enumerate(parts):
        accumulated = f"{accumulated}/{part}"
        label = part.replace("-", " ").title()
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": i + 2,
            "name": label,
            "item": accumulated + "/",
        })

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": breadcrumb_items,
    }

    graph = [content_node, breadcrumb]

    # FAQPage from faq_block argument or page.faq_json
    faq_source = faq_block or getattr(page, "faq_json", None)
    if faq_source:
        faq_items = []
        if isinstance(faq_source, list):
            for entry in faq_source:
                if isinstance(entry, dict):
                    q = entry.get("question") or entry.get("q", "")
                    a = entry.get("answer") or entry.get("a", "")
                    if q and a:
                        faq_items.append({
                            "@type": "Question",
                            "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a},
                        })
        if faq_items:
            graph.append({
                "@type": "FAQPage",
                "@id": f"{canonical}#faq",
                "mainEntity": faq_items,
            })

    return json.dumps(
        {"@context": "https://schema.org", "@graph": graph},
        ensure_ascii=False,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# Generic SEO builder
# ---------------------------------------------------------------------------

def build_seo_base(title: str, description: str, path: str, og_type: str = "website") -> dict:
    """Generic seo dict builder for non-blog, non-landing pages."""
    base = settings.canonical_site_url
    if not path.startswith("/"):
        path = "/" + path
    canonical = f"{base}{path}"
    return {
        "title": _seo_title(title, max_len=70),
        "description": _seo_desc(description, max_len=160) if description else "",
        "canonical": canonical,
        "og_image": "/static/og-default.png",
        "og_type": og_type,
        "site_name": settings.site_name,
        "locale": settings.site_locale,
    }


# ---------------------------------------------------------------------------
# Atom feed
# ---------------------------------------------------------------------------

def render_blog_feed_xml(posts: list) -> str:
    """Return Atom 1.0 XML for the /briefing/feed.xml route."""
    base = settings.canonical_site_url
    site_name = settings.site_name
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    entries: list[str] = []
    for post in posts[:50]:
        canonical = f"{base}/briefing/{post.slug}"
        published_iso = ""
        updated_iso = ""
        if post.published_date:
            published_iso = (
                post.published_date.isoformat() + "T00:00:00Z"
                if hasattr(post.published_date, "isoformat")
                else str(post.published_date) + "T00:00:00Z"
            )
        if post.updated_at:
            updated_iso = (
                post.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if hasattr(post.updated_at, "strftime")
                else str(post.updated_at)
            )
        else:
            updated_iso = published_iso

        summary_escaped = _xml_escape(post.summary or "")
        title_escaped = _xml_escape(post.title or "")

        entries.append(f"""  <entry>
    <id>{canonical}</id>
    <title type="text">{title_escaped}</title>
    <link rel="alternate" type="text/html" href="{canonical}"/>
    <published>{published_iso}</published>
    <updated>{updated_iso}</updated>
    <summary type="text">{summary_escaped}</summary>
    <author><name>{_xml_escape(site_name)}</name></author>
  </entry>""")

    entries_str = "\n".join(entries)
    feed_canonical = f"{base}/briefing/feed.xml"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>{base}/briefing/</id>
  <title type="text">{_xml_escape(site_name)} — Briefings</title>
  <link rel="self" type="application/atom+xml" href="{feed_canonical}"/>
  <link rel="alternate" type="text/html" href="{base}/briefing/"/>
  <updated>{now_iso}</updated>
  <author><name>{_xml_escape(site_name)}</name></author>
{entries_str}
</feed>"""


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Jinja2 filter registration
# ---------------------------------------------------------------------------

def register_jinja_filters(app) -> None:
    app.jinja_env.filters["seo_title"] = _seo_title
    app.jinja_env.filters["seo_desc"] = _seo_desc
