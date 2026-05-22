#!/usr/bin/env python3
"""
VA Claims Workspace — Flask web server.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import time
from datetime import datetime, date, timedelta
from functools import wraps
from typing import Optional

import httpx
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from src.config import settings
from src.models import (
    BlogPost,
    EmailCapture,
    ExternalArticleEntry,
    LandingPage,
    SessionLocal,
    VACondition,
    init_db,
)
from src.page_renderer import (
    build_blog_post_jsonld,
    build_blog_post_seo,
    build_landing_page_jsonld,
    build_landing_page_seo,
    build_seo_base,
    register_jinja_filters,
    render_blog_feed_xml,
)
from src.storage_remote import fetch_report_html, supabase_storage_read_enabled

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, template_folder="templates", static_folder="static")
register_jinja_filters(app)
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new-hampshire", "new-jersey",
    "new-mexico", "new-york", "north-carolina", "north-dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode-island", "south-carolina",
    "south-dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west-virginia", "wisconsin", "wyoming",
}

VA_CLAIMS_SPOKES = {
    "initial-claim", "increase-claim", "supplemental-claim",
    "higher-level-review", "board-appeal", "nexus-letter",
    "dbq-guide", "cp-exam-prep", "evidence-gathering", "secondary-conditions",
}

RETIREMENT_SPOKES = {
    "blended-retirement-system", "legacy-retirement", "crsc",
    "crdp", "medical-retirement", "reserve-retirement", "survivor-benefit-plan",
}

MILITARY_PAY_SPOKES = {
    "basic-pay", "basic-allowance-housing", "special-pays",
}

TOOL_SLUGS = {
    "va-disability-rating-calculator", "military-retirement-calculator",
    "bah-calculator", "military-pay-calculator", "crsc-crdp-calculator",
    "va-claim-checklist", "secondary-conditions-lookup",
}

EXPLAINER_SLUGS = {
    "va-combined-rating-formula", "nexus-letter", "dbq-explained",
    "cp-exam-tips", "secondary-conditions", "brs-vs-legacy", "tsp-military",
    "crsc-vs-crdp", "medical-retirement-process", "va-appeal-options",
    "bah-explained", "burn-pit-exposure-pact-act", "military-state-tax",
    "va-disability-increase",
}

BLOG_POSTS_PER_PAGE = 20

# ---------------------------------------------------------------------------
# In-memory page cache
# ---------------------------------------------------------------------------

_PAGE_CACHE: dict[str, tuple[float, str]] = {}
_PAGE_CACHE_TTL = 90  # seconds


def _cached_page(cache_key: str, render_fn) -> str:
    now = time.time()
    if cache_key in _PAGE_CACHE:
        ts, html = _PAGE_CACHE[cache_key]
        if now - ts < _PAGE_CACHE_TTL:
            return html
    html = render_fn()
    _PAGE_CACHE[cache_key] = (now, html)
    return html


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _gzip_response(html: str, status: int = 200) -> Response:
    if len(html) < 500 or "gzip" not in request.headers.get("Accept-Encoding", ""):
        return Response(html, status=status, mimetype="text/html; charset=utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(html.encode("utf-8"))
    return Response(
        buf.getvalue(),
        status=status,
        mimetype="text/html; charset=utf-8",
        headers={"Content-Encoding": "gzip"},
    )


# ---------------------------------------------------------------------------
# Admin decorator
# ---------------------------------------------------------------------------

def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not settings.admin_token:
            abort(404)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.admin_token}":
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Landing page helpers
# ---------------------------------------------------------------------------

def _build_cluster_ctx(page: LandingPage) -> dict:
    """Build navigation cluster context based on the page's type and sector."""
    page_type = page.page_type or ""
    sector = page.sector_slug or ""
    return {
        "page_type": page_type,
        "sector": sector,
        "canonical_path": page.canonical_path or "/",
    }


def _get_recent_briefings(limit: int = 3, sector_filter: Optional[str] = None) -> list:
    db = SessionLocal()
    try:
        q = db.query(BlogPost).order_by(BlogPost.published_date.desc())
        if sector_filter:
            q = q.filter(BlogPost.primary_sector == sector_filter)
        return q.limit(limit).all()
    finally:
        db.close()


def _serve_landing_page(
    page_key: str, template: str = "landing.html.j2", **extra_ctx
) -> Response:
    db = SessionLocal()
    try:
        page = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
        if not page:
            abort(404)
        seo = build_landing_page_seo(page)
        jsonld = build_landing_page_jsonld(page, seo)
        cluster_ctx = _build_cluster_ctx(page)
        recent = _get_recent_briefings(limit=3, sector_filter=page.sector_slug)
        html = render_template(
            template,
            page=page,
            seo=seo,
            jsonld=jsonld,
            cluster_ctx=cluster_ctx,
            recent_briefings=recent,
            **extra_ctx,
        )
        return _gzip_response(html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — Homepage
# ---------------------------------------------------------------------------

@app.route("/")
def homepage():
    def _render():
        db = SessionLocal()
        try:
            total = db.query(BlogPost).count()
            recent_posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .limit(6)
                .all()
            )
            seo = build_seo_base(
                title="Free VA Disability & Military Benefits Tools | VA Claims Workspace",
                description=settings.site_description,
                path="/",
                og_type="website",
            )
            return render_template(
                "homepage.html.j2",
                seo=seo,
                total_briefings=total,
                recent_posts=recent_posts,
            )
        finally:
            db.close()

    html = _cached_page("homepage", _render)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Blog
# ---------------------------------------------------------------------------

@app.route("/briefing/")
def blog_index():
    page_num = request.args.get("page", 1, type=int)
    if page_num < 1:
        page_num = 1

    db = SessionLocal()
    try:
        total = db.query(BlogPost).count()
        posts = (
            db.query(BlogPost)
            .order_by(BlogPost.published_date.desc())
            .offset((page_num - 1) * BLOG_POSTS_PER_PAGE)
            .limit(BLOG_POSTS_PER_PAGE)
            .all()
        )
        total_pages = max(1, (total + BLOG_POSTS_PER_PAGE - 1) // BLOG_POSTS_PER_PAGE)

        seo = build_seo_base(
            title="VA & Military Benefits Briefings | VA Claims Workspace",
            description=(
                "Daily briefings covering VA disability claims, military retirement, "
                "pay tables, legislation, and veteran benefits news."
            ),
            path="/briefing/",
        )
        html = render_template(
            "blog_index.html.j2",
            seo=seo,
            posts=posts,
            page_num=page_num,
            total_pages=total_pages,
            total=total,
        )
        return _gzip_response(html)
    finally:
        db.close()


@app.route("/briefing/feed.xml")
def blog_feed():
    db = SessionLocal()
    try:
        posts = (
            db.query(BlogPost)
            .order_by(BlogPost.published_date.desc())
            .limit(50)
            .all()
        )
        xml = render_blog_feed_xml(posts)
        return Response(xml, status=200, mimetype="application/atom+xml; charset=utf-8")
    finally:
        db.close()


@app.route("/briefing/<slug>")
def blog_post(slug: str):
    db = SessionLocal()
    try:
        post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
        if not post:
            abort(404)
        seo = build_blog_post_seo(post)
        jsonld = build_blog_post_jsonld(post, seo)
        related: list = []
        if post.related_slugs_json:
            related = (
                db.query(BlogPost)
                .filter(BlogPost.slug.in_(post.related_slugs_json))
                .limit(4)
                .all()
            )
        html = render_template(
            "blog_post.html.j2",
            post=post,
            seo=seo,
            jsonld=jsonld,
            related_posts=related,
        )
        return _gzip_response(html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — Sources
# ---------------------------------------------------------------------------

@app.route("/sources/")
def sources():
    seo = build_seo_base(
        title="Our Sources | VA Claims Workspace",
        description=(
            "VA Claims Workspace draws from official VA, DoD, and federal government "
            "sources to deliver accurate veteran benefits information."
        ),
        path="/sources/",
    )
    html = render_template("sources.html.j2", seo=seo)
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — Tools
# ---------------------------------------------------------------------------

@app.route("/tools/")
def tools_index():
    seo = build_seo_base(
        title="Free VA & Military Benefits Tools | VA Claims Workspace",
        description=(
            "Free calculators and tools for VA disability ratings, BAH, military pay, "
            "CRSC/CRDP, and more — no signup required."
        ),
        path="/tools/",
    )
    html = render_template("tools_index.html.j2", seo=seo, tool_slugs=TOOL_SLUGS)
    return _gzip_response(html)


@app.route("/tools/<tool_slug>/")
def tool_page(tool_slug: str):
    if tool_slug not in TOOL_SLUGS:
        abort(404)
    title_map = {
        "va-disability-rating-calculator": "VA Disability Rating Calculator",
        "military-retirement-calculator": "Military Retirement Calculator",
        "bah-calculator": "BAH Calculator",
        "military-pay-calculator": "Military Pay Calculator",
        "crsc-crdp-calculator": "CRSC vs CRDP Calculator",
        "va-claim-checklist": "VA Claim Checklist",
        "secondary-conditions-lookup": "Secondary Conditions Lookup",
    }
    tool_name = title_map.get(tool_slug, tool_slug.replace("-", " ").title())
    seo = build_seo_base(
        title=f"{tool_name} | VA Claims Workspace",
        description=f"Free {tool_name} for veterans — no signup required.",
        path=f"/tools/{tool_slug}/",
    )
    html = render_template(
        "tool_placeholder.html.j2",
        seo=seo,
        tool_slug=tool_slug,
        tool_name=tool_name,
    )
    return _gzip_response(html)


# ---------------------------------------------------------------------------
# Routes — VA Claims pillar + spokes
# ---------------------------------------------------------------------------

@app.route("/va-claims/")
def va_claims_pillar():
    return _serve_landing_page("pillar:va-claims")


@app.route("/va-claims/<spoke>/")
def va_claims_spoke(spoke: str):
    if spoke not in VA_CLAIMS_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:va-claims:{spoke}")


# ---------------------------------------------------------------------------
# Routes — VA Disability pillar + condition pages
# ---------------------------------------------------------------------------

@app.route("/va-disability/")
def va_disability_pillar():
    return _serve_landing_page("pillar:va-disability")


@app.route("/va-disability/<condition>/")
def va_disability_condition(condition: str):
    db = SessionLocal()
    try:
        va_condition = (
            db.query(VACondition).filter(VACondition.slug == condition).first()
        )
        if va_condition:
            # Try a matching LandingPage for richer content; fall back to condition row
            landing = (
                db.query(LandingPage)
                .filter(LandingPage.page_key == f"condition:{condition}")
                .first()
            )
            if landing:
                seo = build_landing_page_seo(landing)
                jsonld = build_landing_page_jsonld(landing, seo)
                cluster_ctx = _build_cluster_ctx(landing)
                recent = _get_recent_briefings(limit=3, sector_filter=landing.sector_slug)
                html = render_template(
                    "condition_detail.html.j2",
                    page=landing,
                    condition=va_condition,
                    seo=seo,
                    jsonld=jsonld,
                    cluster_ctx=cluster_ctx,
                    recent_briefings=recent,
                )
            else:
                seo = build_seo_base(
                    title=f"{va_condition.name} VA Disability | VA Claims Workspace",
                    description=(
                        f"VA disability ratings, evidence requirements, and secondary "
                        f"conditions for {va_condition.name}."
                    ),
                    path=f"/va-disability/{condition}/",
                )
                html = render_template(
                    "condition_detail.html.j2",
                    page=None,
                    condition=va_condition,
                    seo=seo,
                    jsonld="{}",
                    cluster_ctx={},
                    recent_briefings=[],
                )
            return _gzip_response(html)

        # No VACondition row — check for a LandingPage
        landing = (
            db.query(LandingPage)
            .filter(LandingPage.page_key == f"condition:{condition}")
            .first()
        )
        if not landing:
            abort(404)
        seo = build_landing_page_seo(landing)
        jsonld = build_landing_page_jsonld(landing, seo)
        cluster_ctx = _build_cluster_ctx(landing)
        recent = _get_recent_briefings(limit=3, sector_filter=landing.sector_slug)
        html = render_template(
            "landing.html.j2",
            page=landing,
            seo=seo,
            jsonld=jsonld,
            cluster_ctx=cluster_ctx,
            recent_briefings=recent,
        )
        return _gzip_response(html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — Military Retirement
# ---------------------------------------------------------------------------

@app.route("/military-retirement/")
def military_retirement_pillar():
    return _serve_landing_page("pillar:military-retirement")


@app.route("/military-retirement/<spoke>/")
def military_retirement_spoke(spoke: str):
    if spoke not in RETIREMENT_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:military-retirement:{spoke}")


# ---------------------------------------------------------------------------
# Routes — Military Pay
# ---------------------------------------------------------------------------

@app.route("/military-pay/")
def military_pay_pillar():
    return _serve_landing_page("pillar:military-pay")


@app.route("/military-pay/<spoke>/")
def military_pay_spoke(spoke: str):
    if spoke not in MILITARY_PAY_SPOKES:
        abort(404)
    return _serve_landing_page(f"spoke:military-pay:{spoke}")


# ---------------------------------------------------------------------------
# Routes — State Benefits
# ---------------------------------------------------------------------------

@app.route("/state-benefits/")
def state_benefits_hub():
    return _serve_landing_page("pillar:state-benefits")


@app.route("/state-benefits/<state>/")
def state_benefits_page(state: str):
    if state not in US_STATES:
        abort(404)
    return _serve_landing_page(f"state:{state}")


# ---------------------------------------------------------------------------
# Routes — Explainers
# ---------------------------------------------------------------------------

@app.route("/explainers/")
def explainers_index():
    db = SessionLocal()
    try:
        pages = (
            db.query(LandingPage)
            .filter(LandingPage.page_type == "explainer")
            .order_by(LandingPage.title)
            .all()
        )
        seo = build_seo_base(
            title="VA & Military Benefits Explainers | VA Claims Workspace",
            description=(
                "Plain-language explainers for VA disability ratings, military retirement, "
                "BAH, appeals, and more — written for veterans, not lawyers."
            ),
            path="/explainers/",
        )
        html = render_template("explainers_index.html.j2", seo=seo, pages=pages)
        return _gzip_response(html)
    finally:
        db.close()


@app.route("/explainers/<slug>")
def explainer_detail(slug: str):
    if slug not in EXPLAINER_SLUGS:
        abort(404)
    return _serve_landing_page(f"explainer:{slug}")


# ---------------------------------------------------------------------------
# Routes — XML / Technical
# ---------------------------------------------------------------------------

@app.route("/sitemap.xml")
def sitemap():
    base = settings.canonical_site_url
    now = datetime.utcnow().strftime("%Y-%m-%d")

    urls: list[tuple[str, str, str]] = [
        # (loc, lastmod, changefreq)
        (f"{base}/", now, "daily"),
        (f"{base}/briefing/", now, "daily"),
        (f"{base}/tools/", now, "weekly"),
        (f"{base}/sources/", now, "monthly"),
        (f"{base}/explainers/", now, "weekly"),
        (f"{base}/va-claims/", now, "weekly"),
        (f"{base}/va-disability/", now, "weekly"),
        (f"{base}/military-retirement/", now, "weekly"),
        (f"{base}/military-pay/", now, "weekly"),
        (f"{base}/state-benefits/", now, "weekly"),
    ]

    for spoke in sorted(VA_CLAIMS_SPOKES):
        urls.append((f"{base}/va-claims/{spoke}/", now, "monthly"))
    for spoke in sorted(RETIREMENT_SPOKES):
        urls.append((f"{base}/military-retirement/{spoke}/", now, "monthly"))
    for spoke in sorted(MILITARY_PAY_SPOKES):
        urls.append((f"{base}/military-pay/{spoke}/", now, "monthly"))
    for tool in sorted(TOOL_SLUGS):
        urls.append((f"{base}/tools/{tool}/", now, "monthly"))
    for state in sorted(US_STATES):
        urls.append((f"{base}/state-benefits/{state}/", now, "monthly"))
    for slug in sorted(EXPLAINER_SLUGS):
        urls.append((f"{base}/explainers/{slug}", now, "monthly"))

    db = SessionLocal()
    try:
        posts = db.query(BlogPost.slug, BlogPost.updated_at, BlogPost.published_date).all()
        for row in posts:
            if row.updated_at:
                lastmod = row.updated_at.strftime("%Y-%m-%d")
            elif row.published_date:
                lastmod = (
                    row.published_date.isoformat()
                    if hasattr(row.published_date, "isoformat")
                    else str(row.published_date)
                )
            else:
                lastmod = now
            urls.append((f"{base}/briefing/{row.slug}", lastmod, "weekly"))

        lp_rows = db.query(LandingPage.canonical_path, LandingPage.updated_at).all()
        for row in lp_rows:
            path = row.canonical_path or ""
            if not path:
                continue
            if not path.startswith("/"):
                path = "/" + path
            lastmod = row.updated_at.strftime("%Y-%m-%d") if row.updated_at else now
            urls.append((f"{base}{path}", lastmod, "monthly"))

        conditions = db.query(VACondition.slug, VACondition.updated_at).all()
        for row in conditions:
            lastmod = row.updated_at.strftime("%Y-%m-%d") if row.updated_at else now
            urls.append((f"{base}/va-disability/{row.slug}/", lastmod, "monthly"))
    finally:
        db.close()

    url_tags = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lm}</lastmod>\n    "
        f"<changefreq>{cf}</changefreq>\n  </url>"
        for loc, lm, cf in urls
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{url_tags}\n"
        "</urlset>"
    )
    return Response(xml, status=200, mimetype="application/xml; charset=utf-8")


@app.route("/news-sitemap.xml")
def news_sitemap():
    base = settings.canonical_site_url
    cutoff = datetime.utcnow() - timedelta(hours=48)

    db = SessionLocal()
    try:
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.created_at >= cutoff)
            .order_by(BlogPost.published_date.desc())
            .limit(1000)
            .all()
        )
        news_tags = []
        for post in posts:
            canonical = f"{base}/briefing/{post.slug}"
            pub_date = ""
            if post.published_date:
                pub_date = (
                    post.published_date.isoformat() + "T00:00:00Z"
                    if hasattr(post.published_date, "isoformat")
                    else str(post.published_date) + "T00:00:00Z"
                )
            title_esc = _xml_escape(post.title or "")
            news_tags.append(
                f"  <url>\n"
                f"    <loc>{canonical}</loc>\n"
                f"    <news:news>\n"
                f"      <news:publication>\n"
                f"        <news:name>{_xml_escape(settings.site_name)}</news:name>\n"
                f"        <news:language>en</news:language>\n"
                f"      </news:publication>\n"
                f"      <news:publication_date>{pub_date}</news:publication_date>\n"
                f"      <news:title>{title_esc}</news:title>\n"
                f"    </news:news>\n"
                f"  </url>"
            )
    finally:
        db.close()

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
        + "\n".join(news_tags)
        + "\n</urlset>"
    )
    return Response(xml, status=200, mimetype="application/xml; charset=utf-8")


@app.route("/robots.txt")
def robots_txt():
    base = settings.canonical_site_url
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin/\n"
        "Disallow: /health\n"
        f"\nSitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/news-sitemap.xml\n"
    )
    return Response(body, status=200, mimetype="text/plain; charset=utf-8")


@app.route("/<path:key_file>.txt")
def indexnow_key_file(key_file: str):
    """Serve the IndexNow key verification file at /<key>.txt."""
    key = settings.indexnow_key or ""
    if not key or key_file != key:
        abort(404)
    return Response(key, status=200, mimetype="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Routes — OG images
# ---------------------------------------------------------------------------

@app.route("/og/briefing/<slug>.png")
def og_image_briefing(slug: str):
    db = SessionLocal()
    try:
        post = (
            db.query(BlogPost.og_image_bytes, BlogPost.title)
            .filter(BlogPost.slug == slug)
            .first()
        )
        if not post:
            abort(404)
        if post.og_image_bytes:
            return Response(
                post.og_image_bytes,
                status=200,
                mimetype="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        # Fallback: redirect to a static default OG image
        return redirect("/static/og-default.png", code=302)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email address"}), 400

    api_key = settings.buttondown_api_key
    if not api_key:
        logger.warning("/api/subscribe called but BUTTONDOWN_API_KEY not set")
        return jsonify({"ok": False, "error": "Newsletter not configured"}), 503

    try:
        resp = httpx.post(
            "https://api.buttondown.email/v1/subscribers",
            headers={"Authorization": f"Token {api_key}"},
            json={"email_address": email},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return jsonify({"ok": True}), 200
        if resp.status_code == 409:
            # Already subscribed — treat as success
            return jsonify({"ok": True, "already_subscribed": True}), 200
        logger.warning("Buttondown subscribe failed %d: %s", resp.status_code, resp.text[:200])
        return jsonify({"ok": False, "error": "Subscription failed"}), 502
    except Exception as exc:
        logger.error("Buttondown subscribe error: %s", exc)
        return jsonify({"ok": False, "error": "Upstream error"}), 502


@app.route("/api/email-capture", methods=["POST"])
def api_email_capture():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    source_tool = (data.get("source_tool") or "").strip()[:120]

    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email address"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else None

    db = SessionLocal()
    try:
        capture = EmailCapture(
            email=email,
            source_tool=source_tool or None,
            capture_date=date.today(),
            ip_hash=ip_hash,
        )
        db.add(capture)
        db.commit()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        db.rollback()
        logger.error("EmailCapture insert error: %s", exc)
        return jsonify({"ok": False, "error": "Could not save email"}), 500
    finally:
        db.close()


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json(silent=True) or {}
    honeypot = data.get("honeypot") or data.get("website") or ""
    if honeypot:
        # Silently swallow bot submissions
        return jsonify({"ok": True}), 200

    message = (data.get("message") or "").strip()
    page_url = (data.get("page_url") or "").strip()[:500]

    if not message:
        return jsonify({"ok": False, "error": "Message is required"}), 400

    resend_key = settings.resend_api_key
    if not resend_key:
        logger.info("Feedback received (Resend not configured): %s", message[:100])
        return jsonify({"ok": True}), 200

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.newsletter_from_email,
                "to": [settings.seo_email_recipient],
                "subject": f"[{settings.site_name}] User Feedback",
                "text": f"Page: {page_url}\n\nMessage:\n{message}",
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.warning("Resend feedback email failed %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.error("Resend feedback error: %s", exc)

    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------------
# Routes — Admin
# ---------------------------------------------------------------------------

@app.route("/admin/regen-report", methods=["POST"])
@_require_admin
def admin_regen_report():
    """Trigger an in-process regeneration of key landing pages.

    At launch this clears the in-memory page cache so the next request
    re-renders from the DB. A heavier async job can be wired in here later.
    """
    cleared = list(_PAGE_CACHE.keys())
    _PAGE_CACHE.clear()
    logger.info("Cache cleared by /admin/regen-report: %d keys", len(cleared))
    return jsonify({"ok": True, "cleared_keys": cleared}), 200


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    db = SessionLocal()
    db_ok = False
    briefing_count = 0
    last_briefing_age_hours: Optional[float] = None
    try:
        briefing_count = db.query(BlogPost).count()
        db_ok = True
        latest = (
            db.query(BlogPost.published_date)
            .order_by(BlogPost.published_date.desc())
            .first()
        )
        if latest and latest.published_date:
            pub = latest.published_date
            if hasattr(pub, "year"):
                pub_dt = datetime(pub.year, pub.month, pub.day)
            else:
                pub_dt = datetime.utcnow()
            last_briefing_age_hours = round(
                (datetime.utcnow() - pub_dt).total_seconds() / 3600, 1
            )
    except Exception as exc:
        logger.error("Health check DB error: %s", exc)
    finally:
        db.close()

    warnings = []
    if last_briefing_age_hours is not None and last_briefing_age_hours > 25:
        warnings.append(f"Last briefing is {last_briefing_age_hours}h old (threshold: 25h)")

    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "last_briefing_age_hours": last_briefing_age_hours,
        "briefing_count": briefing_count,
    }
    if warnings:
        payload["warnings"] = warnings

    return jsonify(payload), 200 if db_ok else 503


# ---------------------------------------------------------------------------
# Utility — XML escape (duplicated from page_renderer for local use)
# ---------------------------------------------------------------------------

def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.server_port, debug=True)
