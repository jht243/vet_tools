"""
Flask web server for Ban the Bots.

Serves AI backlash / responsible AI editorial content.
"""

from __future__ import annotations

import gzip
import io
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

import httpx
from flask import Flask, abort, request, jsonify, Response, redirect
from werkzeug.exceptions import HTTPException

from src.config import settings

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)

_ACRONYMS = {"ai", "eu", "ftc", "bls", "doe", "iea", "llm", "seo"}


def _slug_to_label(slug: str) -> str:
    return " ".join(
        w.upper() if w.lower() in _ACRONYMS else w.title()
        for w in slug.replace("-", " ").split()
    )

app = Flask(
    __name__,
    static_folder=str(_STATIC_DIR),
    static_url_path="/static",
)
app.secret_key = settings.admin_token or "fallback-dev-key"

logger = logging.getLogger(__name__)
OUTPUT_DIR = settings.output_dir

BUTTONDOWN_API_URL = "https://api.buttondown.com/v1/subscribers"

GZIP_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/ld+json",
    "image/svg+xml",
)
GZIP_MIN_BYTES = 500

_NAV_PAGE_CACHE: dict[str, dict] = {}
_NAV_PAGE_CACHE_TTL_SECONDS = 90
_NAV_CACHE_PATHS = frozenset({
    "/briefing",
    "/ai-backlash/",
    "/ai-incidents/",
    "/responsible-ai/",
    "/explainers",
})


@app.after_request
def _gzip_response(response: Response) -> Response:
    try:
        if response.direct_passthrough:
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response
        if "Content-Encoding" in response.headers:
            return response
        if "gzip" not in (request.headers.get("Accept-Encoding", "") or "").lower():
            return response
        mimetype = (response.mimetype or "").lower()
        if not any(mimetype.startswith(p) for p in GZIP_MIME_PREFIXES):
            return response
        data = response.get_data()
        if len(data) < GZIP_MIN_BYTES:
            return response
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
            gz.write(data)
        compressed = buf.getvalue()
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        existing_vary = response.headers.get("Vary", "")
        if "Accept-Encoding" not in existing_vary:
            response.headers["Vary"] = (existing_vary + ", Accept-Encoding").lstrip(", ")
    except Exception as exc:
        logger.warning("gzip middleware skipped: %s", exc)
    return response


@app.before_request
def _serve_nav_page_cache():
    path = request.path
    if request.method != "GET":
        return None
    cached = _NAV_PAGE_CACHE.get(path)
    if cached and time.time() - cached.get("cached_at", 0.0) < _NAV_PAGE_CACHE_TTL_SECONDS:
        resp = Response(cached["body"], mimetype="text/html")
        resp.headers["X-Page-Cache"] = "HIT"
        return resp
    return None


@app.after_request
def _store_nav_page_cache(response: Response) -> Response:
    path = request.path
    if (
        request.method == "GET"
        and path in _NAV_CACHE_PATHS
        and response.status_code == 200
        and response.content_type
        and "text/html" in response.content_type
        and response.headers.get("X-Page-Cache") != "HIT"
    ):
        _NAV_PAGE_CACHE[path] = {
            "body": response.get_data(),
            "cached_at": time.time(),
        }
    return response


def _base_url() -> str:
    return settings.canonical_site_url.rstrip("/")


# ── Homepage ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    try:
        from src.models import BlogPost, AIIncident, SessionLocal, init_db
        from src.page_renderer import render_blog_index

        init_db()
        db = SessionLocal()
        try:
            posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc(), BlogPost.id.desc())
                .limit(10)
                .all()
            )
            incident_count = db.query(AIIncident).count()
            html = render_blog_index(posts, page=1, total_pages=1)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("homepage render failed: %s", exc)
        abort(500)


# ── Briefings ─────────────────────────────────────────────────────────

_BRIEFING_PER_PAGE = 20

_BRIEFING_POST_CACHE: dict[str, dict] = {}
_BRIEFING_POST_CACHE_TTL_SECONDS = 600
_BRIEFING_POST_CACHE_MAX_ENTRIES = 200


def _briefing_cache_get(slug: str) -> bytes | None:
    cached = _BRIEFING_POST_CACHE.get(slug)
    if not cached:
        return None
    if time.time() - cached.get("cached_at", 0.0) > _BRIEFING_POST_CACHE_TTL_SECONDS:
        return None
    return cached.get("body")


def _briefing_cache_put(slug: str, body: bytes) -> None:
    if len(_BRIEFING_POST_CACHE) >= _BRIEFING_POST_CACHE_MAX_ENTRIES:
        ordered = sorted(
            _BRIEFING_POST_CACHE.items(),
            key=lambda kv: kv[1].get("cached_at", 0.0),
        )
        for evict_slug, _ in ordered[: _BRIEFING_POST_CACHE_MAX_ENTRIES // 4]:
            _BRIEFING_POST_CACHE.pop(evict_slug, None)
    _BRIEFING_POST_CACHE[slug] = {"body": body, "cached_at": time.time()}


@app.route("/briefing")
@app.route("/briefing/")
def briefing_index():
    try:
        from src.models import BlogPost, SessionLocal, init_db
        from src.page_renderer import render_blog_index

        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1

        init_db()
        db = SessionLocal()
        try:
            total = db.query(BlogPost).count()
            total_pages = max(1, (total + _BRIEFING_PER_PAGE - 1) // _BRIEFING_PER_PAGE)
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * _BRIEFING_PER_PAGE
            posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc(), BlogPost.id.desc())
                .offset(offset)
                .limit(_BRIEFING_PER_PAGE)
                .all()
            )
            html = render_blog_index(posts, page=page, total_pages=total_pages)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("briefing index render failed: %s", exc)
        abort(500)


@app.route("/briefing/feed.xml")
def briefing_feed():
    try:
        from src.models import BlogPost, SessionLocal, init_db
        from src.page_renderer import render_blog_feed_xml

        init_db()
        db = SessionLocal()
        try:
            posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc(), BlogPost.id.desc())
                .limit(50)
                .all()
            )
            xml = render_blog_feed_xml(posts)
            return Response(xml, mimetype="application/atom+xml")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("briefing feed render failed: %s", exc)
        abort(500)


@app.route("/briefing/<slug>")
def briefing_post(slug: str):
    cached_body = _briefing_cache_get(slug)
    if cached_body is not None:
        resp = Response(cached_body, mimetype="text/html")
        resp.headers["X-Page-Cache"] = "HIT"
        return resp

    try:
        from src.models import BlogPost, SessionLocal, init_db
        from src.page_renderer import render_blog_post

        init_db()
        db = SessionLocal()
        try:
            post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
            if not post:
                abort(404)

            related_q = db.query(BlogPost).filter(BlogPost.id != post.id)
            if post.primary_sector:
                related_q = related_q.filter(BlogPost.primary_sector == post.primary_sector)
            related = related_q.order_by(BlogPost.published_date.desc()).limit(5).all()
            if len(related) < 3:
                fill = (
                    db.query(BlogPost)
                    .filter(BlogPost.id != post.id)
                    .filter(~BlogPost.id.in_([r.id for r in related]))
                    .order_by(BlogPost.published_date.desc())
                    .limit(5 - len(related))
                    .all()
                )
                related.extend(fill)

            html = render_blog_post(post, related=related)
            body = html.encode("utf-8") if isinstance(html, str) else html
            _briefing_cache_put(slug, body)
            resp = Response(body, mimetype="text/html")
            resp.headers["X-Page-Cache"] = "MISS"
            return resp
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("briefing post render failed for slug=%s: %s", slug, exc)
        abort(500)


# ── Explainers ────────────────────────────────────────────────────────

@app.route("/explainers")
@app.route("/explainers/")
def explainers_index():
    try:
        from src.models import LandingPage, SessionLocal, init_db
        from src.page_renderer import _env as _pr_env

        init_db()
        db = SessionLocal()
        try:
            pages = (
                db.query(LandingPage)
                .filter(LandingPage.page_type == "explainer")
                .order_by(LandingPage.last_generated_at.desc())
                .all()
            )
            try:
                tmpl = _pr_env.get_template("explainers_index.html.j2")
                html = tmpl.render(
                    pages=pages,
                    site_name=settings.site_name,
                    canonical_url=f"{_base_url()}/explainers",
                )
            except Exception:
                return redirect("/briefing", code=302)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("explainers index render failed: %s", exc)
        abort(500)


@app.route("/explainers/<slug>")
def explainer_page(slug: str):
    try:
        from src.models import LandingPage, BlogPost, SessionLocal, init_db
        from src.page_renderer import render_landing_page, _env as _pr_env

        init_db()
        db = SessionLocal()
        try:
            page = (
                db.query(LandingPage)
                .filter(LandingPage.page_key == f"explainer:{slug}")
                .first()
            )
            if not page:
                label = _slug_to_label(slug)
                _tool = {
                    "slug": slug,
                    "title": label,
                    "subtitle": "In-depth coverage for this topic is on the way.",
                    "description": (
                        "Our editorial team is preparing a plain-English explainer for this topic. "
                        "Browse our daily briefings while you wait."
                    ),
                }
                tmpl = _pr_env.get_template("tool_placeholder.html.j2")
                stub_html = tmpl.render(
                    tool=_tool,
                    site_name=settings.site_name,
                    canonical_url=f"{_base_url()}/explainers/{slug}",
                )
                return Response(stub_html, mimetype="text/html")
            recent = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .limit(5)
                .all()
            )
            html = render_landing_page(page, recent_briefings=recent)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("explainer page render failed for slug=%s: %s", slug, exc)
        abort(500)


# ── Landing Pages ─────────────────────────────────────────────────────

@app.route("/ai-backlash/")
@app.route("/ai-backlash")
def ai_backlash_pillar():
    return _serve_landing_page("pillar:ai-backlash")


@app.route("/responsible-ai/")
@app.route("/responsible-ai")
def responsible_ai_index():
    _INDUSTRY_SLUGS = [
        "healthcare", "finance", "legal", "retail",
        "education", "manufacturing", "real-estate", "marketing",
    ]
    try:
        from src.models import LandingPage, SessionLocal, init_db

        init_db()
        db = SessionLocal()
        try:
            pages = (
                db.query(LandingPage)
                .filter(LandingPage.page_type == "industry")
                .all()
            )
            pages_by_slug = {p.sector_slug: p for p in pages}
            industries = []
            for slug in _INDUSTRY_SLUGS:
                p = pages_by_slug.get(slug)
                industries.append({
                    "slug": slug,
                    "label": p.title if p else _slug_to_label(slug),
                    "summary": p.summary if p else "",
                })

            try:
                from src.page_renderer import _env as _pr_env
                tmpl = _pr_env.get_template("responsible_ai_index.html.j2")
                html = tmpl.render(
                    industries=industries,
                    site_name=settings.site_name,
                    canonical_url=f"{_base_url()}/responsible-ai/",
                )
            except Exception:
                return redirect("/briefing", code=302)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("responsible-ai index render failed: %s", exc)
        abort(500)


@app.route("/responsible-ai/<industry>/")
@app.route("/responsible-ai/<industry>")
def responsible_ai_industry(industry: str):
    return _serve_landing_page(f"industry:{industry}")


def _serve_landing_page(page_key: str) -> Response:
    try:
        from src.models import LandingPage, BlogPost, SessionLocal, init_db
        from src.page_renderer import render_landing_page

        init_db()
        db = SessionLocal()
        try:
            page = db.query(LandingPage).filter(LandingPage.page_key == page_key).first()
            if not page:
                # Content not yet generated — render holding page via tool_placeholder template.
                from src.page_renderer import _env as _pr_env
                slug = page_key.split(":", 1)[-1]
                label = _slug_to_label(slug)
                _tool = {
                    "slug": slug,
                    "title": label,
                    "subtitle": "In-depth coverage for this topic is on the way.",
                    "description": (
                        "Our editorial team is preparing detailed analysis for this page. "
                        "It will be available shortly. Browse our daily briefings or explore "
                        "the AI Incident Tracker in the meantime."
                    ),
                }
                tmpl = _pr_env.get_template("tool_placeholder.html.j2")
                stub_html = tmpl.render(tool=_tool, site_name=settings.site_name, canonical_url=f"{_base_url()}/{slug}/")
                return Response(stub_html, mimetype="text/html")
            recent = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .limit(5)
                .all()
            )
            html = render_landing_page(page, recent_briefings=recent)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("landing page render failed for page_key=%s: %s", page_key, exc)
        abort(500)


# ── AI Incidents ──────────────────────────────────────────────────────

@app.route("/ai-incidents/")
@app.route("/ai-incidents")
def ai_incidents_index():
    try:
        from src.models import AIIncident, SessionLocal, init_db
        from jinja2 import Environment, FileSystemLoader

        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        sector_filter = request.args.get("sector", "").strip()
        severity_filter = request.args.get("severity", "").strip()

        _PER_PAGE = 25
        init_db()
        db = SessionLocal()
        try:
            q = db.query(AIIncident).order_by(AIIncident.incident_date.desc(), AIIncident.id.desc())
            if sector_filter:
                q = q.filter(AIIncident.sector == sector_filter)
            if severity_filter:
                q = q.filter(AIIncident.severity == severity_filter)
            total = q.count()
            total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)
            incidents = q.offset((page - 1) * _PER_PAGE).limit(_PER_PAGE).all()

            sectors = [r[0] for r in db.query(AIIncident.sector).distinct().order_by(AIIncident.sector).all() if r[0]]
            severities = ["critical", "high", "medium", "low"]

            env = Environment(loader=FileSystemLoader("templates"))
            try:
                tmpl = env.get_template("ai_incidents.html.j2")
                html = tmpl.render(
                    incidents=incidents,
                    page=page,
                    total_pages=total_pages,
                    total=total,
                    sector_filter=sector_filter,
                    severity_filter=severity_filter,
                    sectors=sectors,
                    severities=severities,
                    site_name=settings.site_name,
                    canonical_url=f"{_base_url()}/ai-incidents/",
                )
            except Exception:
                return redirect("/briefing", code=302)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ai-incidents index render failed: %s", exc)
        abort(500)


@app.route("/ai-incidents/<int:incident_id>")
@app.route("/ai-incidents/<int:incident_id>/")
def ai_incident_detail(incident_id: int):
    try:
        from src.models import AIIncident, BlogPost, SessionLocal, init_db
        from jinja2 import Environment, FileSystemLoader

        init_db()
        db = SessionLocal()
        try:
            incident = db.query(AIIncident).filter(AIIncident.id == incident_id).first()
            if not incident:
                abort(404)
            related_briefings = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .limit(3)
                .all()
            )
            env = Environment(loader=FileSystemLoader("templates"))
            try:
                tmpl = env.get_template("ai_incident_detail.html.j2")
                html = tmpl.render(
                    incident=incident,
                    related_briefings=related_briefings,
                    site_name=settings.site_name,
                    canonical_url=f"{_base_url()}/ai-incidents/{incident_id}",
                )
            except Exception:
                return redirect("/ai-incidents/", code=302)
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ai-incident detail render failed id=%d: %s", incident_id, exc)
        abort(500)


# ── Tool Placeholders ─────────────────────────────────────────────────

_TOOL_PAGES = {
    "ai-risk-assessment": {
        "title": "AI Risk Assessment",
        "subtitle": "See exactly where your business is exposed before your first AI deployment.",
        "description": (
            "Our AI Risk Assessment tool walks you through 15 key questions about your current "
            "AI usage, vendor relationships, and customer-facing workflows. You'll get a scored "
            "risk profile across five dimensions: regulatory, reputational, operational, labor, "
            "and environmental. Know what you're signing up for before you sign anything."
        ),
        "canonical_path": "/ai-risk-assessment/",
    },
    "no-ai-policy-template": {
        "title": "No-AI Policy Template",
        "subtitle": "A ready-to-use policy telling customers, clients, and staff where you draw the line on AI.",
        "description": (
            "Not every business wants AI in their workflow — and that's a legitimate position. "
            "Our No-AI Policy Template gives you a clear, plain-English document you can publish "
            "on your website, share with clients, and distribute to staff. Covers content, "
            "customer service, hiring, and data handling. Editable in Word or Google Docs."
        ),
        "canonical_path": "/no-ai-policy-template/",
    },
    "human-made-policy-template": {
        "title": "Human-Made Policy Template",
        "subtitle": "Certify and communicate that your content, services, and decisions are created by humans.",
        "description": (
            "The 'Human Made' label is becoming a competitive advantage in industries where "
            "trust and craft matter. Our template gives you the language to certify your work "
            "publicly — on your site, in proposals, and in client contracts. Includes a "
            "simple audit checklist to help you stay honest about what qualifies."
        ),
        "canonical_path": "/human-made-policy-template/",
    },
}


def _render_tool_placeholder(slug: str) -> Response:
    tool = _TOOL_PAGES.get(slug)
    if not tool:
        abort(404)
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("templates"))
        try:
            tmpl = env.get_template("tool_placeholder.html.j2")
            html = tmpl.render(
                tool={"slug": slug, **tool},
                site_name=settings.site_name,
                canonical_url=f"{_base_url()}{tool['canonical_path']}",
            )
        except Exception:
            # Minimal fallback
            html = (
                f"<!doctype html><html><head><title>{tool['title']} — {settings.site_name}</title></head>"
                f"<body><h1>{tool['title']}</h1><p>{tool['subtitle']}</p><p>{tool['description']}</p></body></html>"
            )
        return Response(html, mimetype="text/html")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("tool placeholder render failed for slug=%s: %s", slug, exc)
        abort(500)


@app.route("/ai-risk-assessment/")
@app.route("/ai-risk-assessment")
def tool_ai_risk_assessment():
    return _render_tool_placeholder("ai-risk-assessment")


@app.route("/no-ai-policy-template/")
@app.route("/no-ai-policy-template")
def tool_no_ai_policy():
    return _render_tool_placeholder("no-ai-policy-template")


@app.route("/human-made-policy-template/")
@app.route("/human-made-policy-template")
def tool_human_made_policy():
    return _render_tool_placeholder("human-made-policy-template")


# ── API endpoints ─────────────────────────────────────────────────────

@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Valid email required"}), 400

    api_key = settings.buttondown_api_key
    if not api_key:
        logger.error("BUTTONDOWN_API_KEY not configured")
        return jsonify({"ok": False, "error": "Newsletter signup is not configured"}), 503

    subscriber_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if subscriber_ip and "," in subscriber_ip:
        subscriber_ip = subscriber_ip.split(",")[0].strip()

    try:
        resp = httpx.post(
            BUTTONDOWN_API_URL,
            json={
                "email_address": email,
                "type": "regular",
                "ip_address": subscriber_ip,
                "metadata": {"site": settings.site_name, "site_url": _base_url()},
            },
            headers={"Authorization": f"Token {api_key}"},
            timeout=15,
        )

        if resp.status_code in (200, 201):
            return jsonify({"ok": True})

        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        code = body.get("code", "")

        if resp.status_code == 409 or code == "email_already_exists":
            return jsonify({"ok": True, "note": "Already subscribed"})
        if code == "email_invalid":
            return jsonify({"ok": False, "error": "Please enter a valid email address"}), 400
        if code == "subscriber_blocked":
            resp2 = httpx.post(
                BUTTONDOWN_API_URL,
                json={"email_address": email, "type": "regular", "metadata": {"site": settings.site_name}},
                headers={"Authorization": f"Token {api_key}", "X-Buttondown-Bypass-Firewall": "true"},
                timeout=15,
            )
            if resp2.status_code in (200, 201):
                return jsonify({"ok": True})
            if resp2.status_code == 409:
                return jsonify({"ok": True, "note": "Already subscribed"})

        logger.error("Buttondown API error %d (code=%s): %s", resp.status_code, code, resp.text)
        return jsonify({"ok": False, "error": "Subscription failed, please try again"}), 502

    except Exception as e:
        logger.error("Buttondown request failed: %s", e)
        return jsonify({"ok": False, "error": "Service unavailable"}), 503


@app.post("/api/subscribe-tool/<slug>")
def subscribe_tool(slug: str):
    """Email capture for tool waitlists. Tags the subscriber in Buttondown."""
    if slug not in _TOOL_PAGES:
        abort(404)

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Valid email required"}), 400

    api_key = settings.buttondown_api_key
    if not api_key:
        return jsonify({"ok": True, "note": "Waitlist noted (newsletter not configured)"}), 200

    try:
        resp = httpx.post(
            BUTTONDOWN_API_URL,
            json={
                "email_address": email,
                "type": "regular",
                "tags": [f"tool-waitlist-{slug}"],
                "metadata": {"tool": slug, "site": settings.site_name},
            },
            headers={"Authorization": f"Token {api_key}"},
            timeout=15,
        )
        if resp.status_code in (200, 201, 409):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Signup failed"}), 502
    except Exception as e:
        logger.error("Tool subscribe failed: %s", e)
        return jsonify({"ok": False, "error": "Service unavailable"}), 503


@app.post("/api/feedback")
def feedback():
    from src.newsletter import send_email

    data = request.get_json(silent=True) or {}
    honeypot = str(data.get("company") or data.get("website") or "").strip()
    if honeypot:
        return jsonify({"ok": False, "error": "Invalid submission"}), 400

    feedback_text = str(data.get("feedback") or "").strip()
    if not feedback_text:
        return jsonify({"ok": False, "error": "Feedback is required"}), 400
    if len(feedback_text) > 4000:
        return jsonify({"ok": False, "error": "Feedback is too long"}), 400

    email_raw = str(data.get("email") or "").strip()
    reply_email = ""
    if email_raw:
        if len(email_raw) > 254:
            return jsonify({"ok": False, "error": "Email is too long"}), 400
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email_raw):
            return jsonify({"ok": False, "error": "Please enter a valid email or leave it blank"}), 400
        reply_email = email_raw

    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    page_url = str(data.get("page_url") or request.referrer or "").strip()
    page_title = str(data.get("page_title") or "").strip()

    html_body = f"""
    <h2>New {settings.site_name} feedback</h2>
    <table cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;">
      <tr><td><strong>Date</strong></td><td>{_xml_escape(submitted_at)}</td></tr>
      <tr><td><strong>Reply email</strong></td><td>{_xml_escape(reply_email or '(not provided)')}</td></tr>
      <tr><td><strong>Page title</strong></td><td>{_xml_escape(page_title or 'Unknown')}</td></tr>
      <tr><td><strong>Page URL</strong></td><td>{_xml_escape(page_url or 'Unknown')}</td></tr>
    </table>
    <h3>Feedback</h3>
    <p style="white-space:pre-wrap;font-family:Arial,sans-serif;font-size:15px;line-height:1.5;">{_xml_escape(feedback_text)}</p>
    """

    result = send_email(
        to=settings.seo_email_recipient,
        subject=f"New {settings.site_name} feedback",
        html_body=html_body,
        reply_to=reply_email or None,
    )
    if not result.get("success"):
        logger.error("Feedback email failed: %s", result)
        return jsonify({"ok": False, "error": "Feedback could not be sent"}), 502

    return jsonify({"ok": True})


# ── Admin ─────────────────────────────────────────────────────────────

@app.route("/admin/regen-report", methods=["POST"])
def admin_regen_report():
    """Trigger a re-analysis + blog generation pass without a full scrape."""
    auth = request.headers.get("Authorization", "")
    token = settings.admin_token
    if not token or auth != f"Bearer {token}":
        abort(401)
    try:
        from src.analyzer import run_analysis
        from src.blog_generator import run_blog_generation
        analysis = run_analysis()
        blog = run_blog_generation()
        return jsonify({"ok": True, "analysis": analysis, "blog": blog})
    except Exception as exc:
        logger.exception("admin regen-report failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── SEO / crawl infrastructure ────────────────────────────────────────

@app.route("/robots.txt")
def robots_txt():
    base = settings.canonical_site_url.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin/\n"
        "Disallow: /health\n"
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/news-sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    from datetime import date as _date, datetime as _datetime, timezone as _tz

    base = settings.canonical_site_url.rstrip("/")
    today_iso = _datetime.utcnow().replace(tzinfo=_tz.utc).date().isoformat()

    static_urls = [
        {"loc": f"{base}/", "lastmod": today_iso, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base}/briefing", "lastmod": today_iso, "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base}/ai-backlash/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base}/ai-incidents/", "lastmod": today_iso, "changefreq": "daily", "priority": "0.85"},
        {"loc": f"{base}/responsible-ai/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/explainers", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base}/ai-risk-assessment/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base}/no-ai-policy-template/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base}/human-made-policy-template/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
    ]

    # Industry landing pages
    for slug in ["healthcare", "finance", "legal", "retail", "education", "manufacturing", "real-estate", "marketing"]:
        static_urls.append({
            "loc": f"{base}/responsible-ai/{slug}/",
            "lastmod": today_iso,
            "changefreq": "weekly",
            "priority": "0.85",
        })

    # BlogPosts
    try:
        from src.models import BlogPost, SessionLocal, init_db
        init_db()
        db = SessionLocal()
        try:
            posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc())
                .all()
            )
            for p in posts:
                lastmod = p.updated_at.date().isoformat() if p.updated_at else today_iso
                static_urls.append({
                    "loc": f"{base}/briefing/{p.slug}",
                    "lastmod": lastmod,
                    "changefreq": "weekly",
                    "priority": "0.8",
                })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("sitemap: blog posts walk failed: %s", exc)

    # LandingPages (explainers)
    try:
        from src.models import LandingPage, SessionLocal as SL2, init_db as idb2
        idb2()
        db2 = SL2()
        try:
            lps = db2.query(LandingPage).filter(LandingPage.page_type == "explainer").all()
            for lp in lps:
                path = (lp.canonical_path or "").strip()
                if path:
                    static_urls.append({
                        "loc": f"{base}{path}",
                        "lastmod": today_iso,
                        "changefreq": "weekly",
                        "priority": "0.75",
                    })
        finally:
            db2.close()
    except Exception as exc:
        logger.warning("sitemap: landing pages walk failed: %s", exc)

    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in static_urls:
        parts.append("<url>")
        parts.append(f"<loc>{_xml_escape(u['loc'])}</loc>")
        if u.get("lastmod"):
            parts.append(f"<lastmod>{_xml_escape(u['lastmod'])}</lastmod>")
        if u.get("changefreq"):
            parts.append(f"<changefreq>{_xml_escape(u['changefreq'])}</changefreq>")
        if u.get("priority"):
            parts.append(f"<priority>{_xml_escape(u['priority'])}</priority>")
        parts.append("</url>")
    parts.append("</urlset>")

    resp = Response("".join(parts), mimetype="application/xml")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/news-sitemap.xml")
def news_sitemap_xml():
    from datetime import datetime as _datetime, timezone as _tz, timedelta as _td

    base = settings.canonical_site_url.rstrip("/")
    publication_name = settings.site_name
    publication_lang = (settings.site_locale or "en_US").split("_", 1)[0] or "en"
    cutoff = _datetime.now(_tz.utc) - _td(hours=48)

    items: list[dict] = []
    try:
        from src.models import SessionLocal, init_db, BlogPost
        init_db()
        db = SessionLocal()
        try:
            recent_posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc(), BlogPost.id.desc())
                .limit(1000)
                .all()
            )
            for p in recent_posts:
                pub_dt = p.created_at or p.updated_at
                if pub_dt is None:
                    from datetime import datetime as _dt
                    pub_dt = _dt.combine(p.published_date, _dt.min.time())
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=_tz.utc)
                if pub_dt < cutoff:
                    continue
                kws = p.keywords_json or []
                if isinstance(kws, str):
                    kws = [k.strip() for k in kws.split(",") if k.strip()]
                items.append({
                    "loc": f"{base}/briefing/{p.slug}",
                    "publication_date": pub_dt.isoformat(),
                    "title": (p.title or "")[:300],
                    "keywords": ", ".join(kws[:10]),
                })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("news-sitemap failed, returning empty: %s", exc)

    parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    parts.append(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
    )
    for it in items:
        parts.append("<url>")
        parts.append(f"<loc>{_xml_escape(it['loc'])}</loc>")
        parts.append("<news:news>")
        parts.append("<news:publication>")
        parts.append(f"<news:name>{_xml_escape(publication_name)}</news:name>")
        parts.append(f"<news:language>{_xml_escape(publication_lang)}</news:language>")
        parts.append("</news:publication>")
        parts.append(f"<news:publication_date>{_xml_escape(it['publication_date'])}</news:publication_date>")
        parts.append(f"<news:title>{_xml_escape(it['title'])}</news:title>")
        if it["keywords"]:
            parts.append(f"<news:keywords>{_xml_escape(it['keywords'])}</news:keywords>")
        parts.append("</news:news>")
        parts.append("</url>")
    parts.append("</urlset>")

    resp = Response("".join(parts), mimetype="application/xml")
    resp.headers["Cache-Control"] = "public, max-age=900"
    return resp


@app.route("/og/briefing/<slug>.png")
def briefing_og_image(slug: str):
    try:
        from src.models import BlogPost, SessionLocal, init_db
        init_db()
        db = SessionLocal()
        try:
            row = db.query(BlogPost.og_image_bytes).filter(BlogPost.slug == slug).first()
            if row is None:
                abort(404)
            png_bytes = row[0]
            if not png_bytes:
                fallback = f"{settings.canonical_site_url.rstrip('/')}/static/og-image.png?v=1"
                resp = redirect(fallback, code=302)
                resp.headers["Cache-Control"] = "public, max-age=300"
                return resp
            resp = Response(png_bytes, mimetype="image/png")
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("og card serve failed for slug=%s: %s", slug, exc)
        abort(500)


@app.route("/<key>.txt")
def indexnow_key_file(key: str):
    configured = (settings.indexnow_key or "").strip()
    if configured and key == configured:
        return Response(configured, mimetype="text/plain")
    abort(404)


@app.route("/health")
def health():
    try:
        from src.models import BlogPost, SessionLocal, init_db
        from datetime import datetime, timezone, timedelta
        init_db()
        db = SessionLocal()
        try:
            latest = (
                db.query(BlogPost.created_at)
                .order_by(BlogPost.created_at.desc())
                .first()
            )
            db_reachable = True
            if latest and latest[0]:
                age = datetime.now(timezone.utc) - latest[0].replace(tzinfo=timezone.utc)
                latest_briefing_age_hours = round(age.total_seconds() / 3600, 1)
            else:
                latest_briefing_age_hours = None
        except Exception:
            db_reachable = False
            latest_briefing_age_hours = None
        finally:
            db.close()
    except Exception:
        db_reachable = False
        latest_briefing_age_hours = None

    return {
        "status": "ok",
        "db_reachable": db_reachable,
        "latest_briefing_age_hours": latest_briefing_age_hours,
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.server_port, debug=True)
