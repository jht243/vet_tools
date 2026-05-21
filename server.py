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
    "/ai-layoffs/",
    "/ai-lawsuits/",
    "/fighting-back/",
    "/responsible-ai/",
    "/explainers",
    "/parents/",
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
        from src.page_renderer import render_homepage

        init_db()
        db = SessionLocal()
        try:
            posts = (
                db.query(BlogPost)
                .order_by(BlogPost.published_date.desc(), BlogPost.id.desc())
                .limit(6)
                .all()
            )
            briefing_count = db.query(BlogPost).count()
            incident_count = db.query(AIIncident).count()
            html = render_homepage(
                posts,
                briefing_count=briefing_count,
                incident_count=incident_count,
            )
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


# ── Data Center Map ───────────────────────────────────────────────────

@app.route("/data-center-map/")
@app.route("/data-center-map")
def data_center_map():
    try:
        from src.models import DataCenter, SessionLocal, init_db
        from src.page_renderer import _env as _pr_env

        init_db()
        db = SessionLocal()
        try:
            data_centers = (
                db.query(DataCenter)
                .order_by(DataCenter.state, DataCenter.name)
                .all()
            )

            total = len(data_centers)
            proposed_count = sum(
                1 for dc in data_centers
                if dc.status in ("proposed", "under_construction")
            )
            total_mw = sum(dc.capacity_mw for dc in data_centers if dc.capacity_mw)

            map_data = []
            for dc in data_centers:
                if dc.lat is None or dc.lng is None:
                    continue
                map_data.append({
                    "name": dc.name,
                    "operator": dc.operator,
                    "status": dc.status,
                    "city": dc.city,
                    "state": dc.state,
                    "county": dc.county,
                    "country": dc.country,
                    "lat": dc.lat,
                    "lng": dc.lng,
                    "capacity_mw": dc.capacity_mw,
                    "water_source": dc.water_source,
                    "announced_date": dc.announced_date.isoformat() if dc.announced_date else None,
                    "notes": dc.notes,
                    "source_url": dc.source_url,
                })

            tmpl = _pr_env.get_template("data_center_map.html.j2")
            html = tmpl.render(
                data_centers=data_centers,
                map_data=map_data,
                total=total,
                proposed_count=proposed_count,
                total_mw=total_mw or 0,
                site_name=settings.site_name,
                canonical_url=f"{_base_url()}/data-center-map/",
            )
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except Exception as exc:
        logger.exception("data-center-map render failed: %s", exc)
        abort(500)


# ── AI-Proof Jobs ─────────────────────────────────────────────────────

@app.route("/ai-proof-jobs/")
@app.route("/ai-proof-jobs")
def ai_proof_jobs():
    return _serve_landing_page("pillar:ai-proof-jobs")


@app.route("/will-ai-replace-my-job/")
@app.route("/will-ai-replace-my-job")
def will_ai_replace_my_job():
    try:
        import json
        from src.page_renderer import _env as _pr_env
        from pathlib import Path

        job_data_path = Path(__file__).resolve().parent / "static" / "data" / "job_risk.json"
        job_data = json.loads(job_data_path.read_text())

        tmpl = _pr_env.get_template("tools/job_checker.html.j2")
        html = tmpl.render(
            job_data=job_data,
            site_name=settings.site_name,
            canonical_url=f"{_base_url()}/will-ai-replace-my-job/",
        )
        return Response(html, mimetype="text/html")
    except Exception as exc:
        logger.exception("job checker render failed: %s", exc)
        abort(500)


# ── AI Layoffs ────────────────────────────────────────────────────────

_LAYOFFS_PER_PAGE = 30


@app.route("/ai-layoffs/")
@app.route("/ai-layoffs")
def ai_layoffs_index():
    try:
        from src.models import AILayoff, SessionLocal, init_db
        from src.page_renderer import _env as _pr_env

        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        industry_filter = request.args.get("industry", "").strip()
        state_filter = request.args.get("state", "").strip()
        year_filter = request.args.get("year", "").strip()

        init_db()
        db = SessionLocal()
        try:
            q = db.query(AILayoff).order_by(AILayoff.announced_date.desc(), AILayoff.id.desc())
            if industry_filter:
                q = q.filter(AILayoff.industry == industry_filter)
            if state_filter:
                q = q.filter(AILayoff.state == state_filter)
            if year_filter:
                import sqlalchemy
                q = q.filter(sqlalchemy.extract("year", AILayoff.announced_date) == int(year_filter))

            total = q.count()
            total_pages = max(1, (total + _LAYOFFS_PER_PAGE - 1) // _LAYOFFS_PER_PAGE)
            page = min(page, total_pages)
            layoffs = q.offset((page - 1) * _LAYOFFS_PER_PAGE).limit(_LAYOFFS_PER_PAGE).all()

            total_jobs_row = db.query(AILayoff.job_count).all()
            total_jobs = sum(r[0] for r in total_jobs_row if r[0])

            industries = [
                r[0] for r in
                db.query(AILayoff.industry).filter(AILayoff.industry.isnot(None))
                .distinct().order_by(AILayoff.industry).all()
            ]
            states = [
                r[0] for r in
                db.query(AILayoff.state).filter(AILayoff.state.isnot(None))
                .distinct().order_by(AILayoff.state).all()
            ]
            import datetime as _dt
            years = sorted({
                r[0].year for r in db.query(AILayoff.announced_date).all()
                if r[0]
            }, reverse=True)

            tmpl = _pr_env.get_template("ai_layoffs.html.j2")
            html = tmpl.render(
                layoffs=layoffs,
                page=page,
                total_pages=total_pages,
                total=total,
                total_jobs=total_jobs,
                industry_filter=industry_filter,
                state_filter=state_filter,
                year_filter=year_filter,
                industries=industries,
                states=states,
                years=years,
                site_name=settings.site_name,
                canonical_url=f"{_base_url()}/ai-layoffs/",
            )
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except Exception as exc:
        logger.exception("ai-layoffs index render failed: %s", exc)
        abort(500)


# ── AI Lawsuits ───────────────────────────────────────────────────────

_LAWSUITS_PER_PAGE = 25


@app.route("/ai-lawsuits/")
@app.route("/ai-lawsuits")
def ai_lawsuits_index():
    try:
        from src.models import AILawsuit, SessionLocal, init_db
        from src.page_renderer import _env as _pr_env

        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        claim_type_filter = request.args.get("claim_type", "").strip()
        defendant_filter = request.args.get("defendant", "").strip()
        status_filter = request.args.get("status", "").strip()

        init_db()
        db = SessionLocal()
        try:
            q = db.query(AILawsuit).order_by(AILawsuit.filed_date.desc(), AILawsuit.id.desc())
            if claim_type_filter:
                q = q.filter(AILawsuit.claim_type == claim_type_filter)
            if defendant_filter:
                q = q.filter(AILawsuit.defendant.ilike(f"%{defendant_filter}%"))
            if status_filter:
                q = q.filter(AILawsuit.status == status_filter)

            total = q.count()
            total_pages = max(1, (total + _LAWSUITS_PER_PAGE - 1) // _LAWSUITS_PER_PAGE)
            page = min(page, total_pages)
            lawsuits = q.offset((page - 1) * _LAWSUITS_PER_PAGE).limit(_LAWSUITS_PER_PAGE).all()

            claim_types = [
                r[0] for r in
                db.query(AILawsuit.claim_type).filter(AILawsuit.claim_type.isnot(None))
                .distinct().order_by(AILawsuit.claim_type).all()
            ]
            defendants = [
                r[0] for r in
                db.query(AILawsuit.defendant).distinct().order_by(AILawsuit.defendant).all()
                if r[0]
            ]
            statuses = [r[0] for r in db.query(AILawsuit.status).distinct().order_by(AILawsuit.status).all()]

            tmpl = _pr_env.get_template("ai_lawsuits.html.j2")
            html = tmpl.render(
                lawsuits=lawsuits,
                page=page,
                total_pages=total_pages,
                total=total,
                claim_type_filter=claim_type_filter,
                defendant_filter=defendant_filter,
                status_filter=status_filter,
                claim_types=claim_types,
                defendants=defendants,
                statuses=statuses,
                site_name=settings.site_name,
                canonical_url=f"{_base_url()}/ai-lawsuits/",
            )
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except Exception as exc:
        logger.exception("ai-lawsuits index render failed: %s", exc)
        abort(500)


# ── Fighting Back ─────────────────────────────────────────────────────

_RESISTANCE_PER_PAGE = 24


@app.route("/fighting-back/")
@app.route("/fighting-back")
def fighting_back_index():
    try:
        from src.models import AIResistanceAction, SessionLocal, init_db
        from src.page_renderer import _env as _pr_env

        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        actor_type_filter = request.args.get("actor_type", "").strip()
        action_type_filter = request.args.get("action_type", "").strip()
        industry_filter = request.args.get("industry", "").strip()

        init_db()
        db = SessionLocal()
        try:
            q = db.query(AIResistanceAction).order_by(
                AIResistanceAction.announced_date.desc(), AIResistanceAction.id.desc()
            )
            if actor_type_filter:
                q = q.filter(AIResistanceAction.actor_type == actor_type_filter)
            if action_type_filter:
                q = q.filter(AIResistanceAction.action_type == action_type_filter)
            if industry_filter:
                q = q.filter(AIResistanceAction.industry.ilike(f"%{industry_filter}%"))

            total = q.count()
            total_pages = max(1, (total + _RESISTANCE_PER_PAGE - 1) // _RESISTANCE_PER_PAGE)
            page = min(page, total_pages)
            actions = q.offset((page - 1) * _RESISTANCE_PER_PAGE).limit(_RESISTANCE_PER_PAGE).all()

            actor_types = [
                r[0] for r in
                db.query(AIResistanceAction.actor_type).distinct().order_by(AIResistanceAction.actor_type).all()
            ]
            action_types = [
                r[0] for r in
                db.query(AIResistanceAction.action_type).distinct().order_by(AIResistanceAction.action_type).all()
            ]
            industries = [
                r[0] for r in
                db.query(AIResistanceAction.industry).filter(AIResistanceAction.industry.isnot(None))
                .distinct().order_by(AIResistanceAction.industry).all()
            ]

            tmpl = _pr_env.get_template("fighting_back.html.j2")
            html = tmpl.render(
                actions=actions,
                page=page,
                total_pages=total_pages,
                total=total,
                actor_type_filter=actor_type_filter,
                action_type_filter=action_type_filter,
                industry_filter=industry_filter,
                actor_types=actor_types,
                action_types=action_types,
                industries=industries,
                site_name=settings.site_name,
                canonical_url=f"{_base_url()}/fighting-back/",
            )
            return Response(html, mimetype="text/html")
        finally:
            db.close()
    except Exception as exc:
        logger.exception("fighting-back index render failed: %s", exc)
        abort(500)


# ── Parenting Hub ────────────────────────────────────────────────────

@app.route("/parents/")
@app.route("/parents")
def parents_hub():
    try:
        from src.page_renderer import _env as _pr_env

        tmpl = _pr_env.get_template("parents_index.html.j2")
        html = tmpl.render(
            site_name=settings.site_name,
            canonical_url=f"{_base_url()}/parents/",
        )
        return Response(html, mimetype="text/html")
    except Exception as exc:
        logger.exception("parents hub render failed: %s", exc)
        abort(500)


_VALID_PARENT_SPOKES = frozenset({
    "screen-time", "what-to-study", "ai-safety", "how-to-use-ai-for-good", "social-media"
})


@app.route("/parents/<spoke>/")
@app.route("/parents/<spoke>")
def parent_spoke(spoke: str):
    if spoke not in _VALID_PARENT_SPOKES:
        abort(404)
    return _serve_landing_page(f"parent:{spoke}")


# ── Tool Placeholders ─────────────────────────────────────────────────

_TOOL_PAGES = {
    "ai-risk-assessment": {
        "title": "How AI Could Affect Your Life",
        "subtitle": "10 questions about your job, your community, and your family. Find out what's actually at risk for you.",
        "description": (
            "Not sure how AI affects you personally? This short quiz walks you through the real "
            "risks — for your job, your neighborhood, your kids, and your data. You'll get a "
            "plain-English picture of where you're most exposed and what you can do about it. "
            "Takes about 3 minutes. No corporate jargon."
        ),
        "canonical_path": "/ai-risk-assessment/",
    },
    "no-ai-policy-template": {
        "title": "No-AI Policy Template",
        "subtitle": "A plain-English pledge for freelancers, artists, teachers, and anyone who wants to draw the line.",
        "description": (
            "Not everyone wants AI in their work — and that's a completely legitimate choice. "
            "This template gives you a clear, human-readable statement you can publish on your "
            "website, share with clients, or post in your classroom. Covers your creative work, "
            "communications, and decisions. Free to use, easy to customize."
        ),
        "canonical_path": "/no-ai-policy-template/",
    },
    "human-made-policy-template": {
        "title": "Human-Made Label Template",
        "subtitle": "Tell the world your work is made by a real person — and mean it.",
        "description": (
            "In a world flooded with AI-generated content, 'made by a human' is becoming "
            "something people actually care about. This template gives you the language to say "
            "it clearly and credibly — on your site, in your portfolio, in your contracts. "
            "Includes a simple checklist to keep yourself honest. For creators, teachers, "
            "journalists, and anyone whose craft depends on trust."
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
        {"loc": f"{base}/ai-layoffs/", "lastmod": today_iso, "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base}/ai-lawsuits/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/fighting-back/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/ai-proof-jobs/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/will-ai-replace-my-job/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base}/data-center-map/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/parents/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.85"},
        {"loc": f"{base}/ai-risk-assessment/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base}/no-ai-policy-template/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base}/human-made-policy-template/", "lastmod": today_iso, "changefreq": "weekly", "priority": "0.7"},
    ]

    # Parent spoke pages
    for spoke in ["screen-time", "what-to-study", "ai-safety", "how-to-use-ai-for-good", "social-media"]:
        static_urls.append({
            "loc": f"{base}/parents/{spoke}/",
            "lastmod": today_iso,
            "changefreq": "biweekly",
            "priority": "0.8",
        })

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
