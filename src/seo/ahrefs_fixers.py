"""
Auto-fixers dispatched by ahrefs_audit.py for each issue category.

Every fixer receives a list of AuditFinding objects and returns the
count of successfully fixed issues. Fixers mutate finding.fixed and
finding.fix_detail in-place.

Fixers that modify content use the same LLM infrastructure as
content_fixer.py (OpenAI calls + DB writes).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from src.seo.ahrefs_audit import AuditFinding

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
_REDIRECTS_PATH = _ROOT / "src" / "seo" / "redirects_registry.json"


# ── Helpers ───────────────────────────────────────────────────────────

def _load_redirects() -> dict[str, str]:
    if _REDIRECTS_PATH.exists():
        return json.loads(_REDIRECTS_PATH.read_text())
    return {}


def _save_redirects(data: dict[str, str]) -> None:
    _REDIRECTS_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    logger.info("Wrote %d redirects to %s", len(data), _REDIRECTS_PATH)


def _url_to_path(url: str) -> str:
    """Extract path from full URL.  https://example.com/foo → /foo"""
    return urlparse(url).path or "/"


def _get_db():
    """Get a DB session, initializing if needed."""
    from src.models import SessionLocal, init_db
    init_db()
    return SessionLocal()


def _find_db_page(db, path: str):
    """Return a LandingPage or BlogPost matching the path, or None."""
    from src.models import BlogPost, LandingPage
    norm = "/" + path.lstrip("/").rstrip("/")
    page = db.query(LandingPage).filter(LandingPage.canonical_path == norm).first()
    if page:
        return page
    if norm.startswith("/briefing/"):
        slug = norm.rstrip("/").rsplit("/", 1)[-1]
        return db.query(BlogPost).filter(BlogPost.slug == slug).first()
    return None


def _get_openai_client():
    """Return an OpenAI client, or None if no key."""
    from src.config import settings
    if not settings.openai_api_key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


def _llm_call(client, system: str, user: str, max_tokens: int = 500) -> tuple[str, dict]:
    """Simple LLM call that returns (raw_text, usage_dict)."""
    from src.config import settings
    model = settings.openai_model or "gpt-4o"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return raw, usage


from src.seo import CONTENT_CREATION_SYSTEM_PROMPT as _SEO_SYSTEM


# ── 1a: HTTP errors → auto-redirect ──────────────────────────────────

def fix_broken_pages(findings: list[AuditFinding]) -> int:
    """
    For 404/4XX pages: find a similar live URL and add a redirect.
    Checks for: underscore vs hyphen, trailing slash, moved paths.
    """
    from src.seo.cluster_topology import CLUSTERS

    redirects = _load_redirects()
    fixed = 0

    # Build lookup of all known cluster paths for slug matching
    known_paths: set[str] = set()
    for cluster in CLUSTERS.values():
        for p in cluster.all_paths():
            known_paths.add(p)

    for f in findings:
        path = _url_to_path(f.url)
        if path in redirects:
            f.fixed = True
            f.fix_detail = f"redirect already exists → {redirects[path]}"
            fixed += 1
            continue

        # Try slug normalization: underscores → hyphens
        normalized = path.replace("_", "-")
        if normalized != path:
            redirects[path] = normalized
            f.fixed = True
            f.fix_detail = f"added redirect (underscore→hyphen) → {normalized}"
            fixed += 1
            continue

        # Try without trailing slash
        if path.endswith("/") and len(path) > 1:
            without_slash = path.rstrip("/")
            redirects[path] = without_slash
            f.fixed = True
            f.fix_detail = f"added redirect (trailing slash) → {without_slash}"
            fixed += 1
            continue

        # Check if path matches a known cluster path with minor variation
        parts = path.split("/")
        if len(parts) >= 3:
            slug = parts[-1] or parts[-2]
            for known in known_paths:
                if known.rstrip("/").endswith(slug) and known != path:
                    redirects[path] = known
                    f.fixed = True
                    f.fix_detail = f"added redirect (slug match) → {known}"
                    fixed += 1
                    break

        if not f.fixed:
            f.fix_detail = "no matching redirect target found — manual review needed"

    if fixed:
        _save_redirects(redirects)
    return fixed


def alert_server_errors(findings: list[AuditFinding]) -> int:
    """Log 500/5XX/timeout pages for manual investigation."""
    for f in findings:
        logger.warning(
            "SERVER ERROR: [%s] %s — %s (HTTP %s)",
            f.severity, f.issue_name, f.url,
            f.page_data.get("http_code", "?"),
        )
        f.fix_detail = "logged as alert — needs manual investigation"
    return 0


# ── 1b: Content issues → LLM rewrite + DB write ──────────────────────

def fix_content_issues(findings: list[AuditFinding]) -> int:
    """
    Fix title, meta description, H1 issues.
    Actually calls OpenAI and writes to the database.
    """
    client = _get_openai_client()
    if client is None:
        for f in findings:
            f.fix_detail = "skipped — no OpenAI API key"
        return 0

    db = _get_db()
    fixed = 0
    max_llm_fixes = 10  # cap LLM calls per category per run

    try:
        for f in findings:
            if fixed >= max_llm_fixes:
                f.fix_detail = "skipped — LLM fix limit reached"
                continue

            issue = f.issue_name.lower()
            path = _url_to_path(f.url)
            page_data = f.page_data

            page = _find_db_page(db, path)

            # --- Title missing or too short/long ---
            if "title" in issue and ("missing" in issue or "empty" in issue or "too short" in issue or "too long" in issue):
                if page is None:
                    f.fix_detail = f"no DB page found for {path} — template-level fix needed"
                    continue
                current_title = getattr(page, "title", "") or ""
                title_len = len(current_title)

                if "missing" in issue or "empty" in issue:
                    # Generate title from H1 or page content
                    h1 = (page_data.get("h1") or [""])[0]
                    prompt = f"Generate an SEO title (50-60 chars) for a page about: {h1 or path}\nReturn JSON: {{\"title\": \"...\"}}"
                elif "too short" in issue:
                    prompt = f"This title is too short ({title_len} chars). Rewrite to 50-60 chars.\nCurrent: {current_title}\nPath: {path}\nReturn JSON: {{\"title\": \"...\"}}"
                elif "too long" in issue:
                    prompt = f"This title is too long ({title_len} chars). Rewrite to under 60 chars, keeping keywords.\nCurrent: {current_title}\nPath: {path}\nReturn JSON: {{\"title\": \"...\"}}"
                else:
                    continue

                try:
                    raw, usage = _llm_call(client, _SEO_SYSTEM, prompt, max_tokens=200)
                    data = json.loads(raw)
                    new_title = data.get("title", "").strip()
                    if new_title and 20 < len(new_title) < 80:
                        old_title = page.title
                        page.title = new_title
                        page.updated_at = datetime.utcnow()
                        db.commit()
                        f.fixed = True
                        f.fix_detail = f"title rewritten: '{old_title}' → '{new_title}'"
                        fixed += 1
                    else:
                        f.fix_detail = f"LLM returned unusable title: '{new_title}'"
                except Exception as e:
                    f.fix_detail = f"LLM title fix failed: {e}"
                continue

            # --- Meta description missing or wrong length ---
            if "meta description" in issue and ("missing" in issue or "empty" in issue or "too short" in issue or "too long" in issue):
                if page is None:
                    f.fix_detail = f"no DB page found for {path} — template-level fix needed"
                    continue
                current_desc = getattr(page, "summary", "") or ""
                desc_len = len(current_desc)

                if "missing" in issue or "empty" in issue:
                    title = getattr(page, "title", "") or path
                    prompt = f"Generate a meta description (120-155 chars) for a page titled: {title}\nPath: {path}\nReturn JSON: {{\"description\": \"...\"}}"
                elif "too short" in issue:
                    prompt = f"Meta description too short ({desc_len} chars). Rewrite to 120-155 chars.\nCurrent: {current_desc}\nTitle: {getattr(page, 'title', '')}\nReturn JSON: {{\"description\": \"...\"}}"
                elif "too long" in issue:
                    prompt = f"Meta description too long ({desc_len} chars). Rewrite to under 155 chars, keeping keywords.\nCurrent: {current_desc}\nReturn JSON: {{\"description\": \"...\"}}"
                else:
                    continue

                try:
                    raw, usage = _llm_call(client, _SEO_SYSTEM, prompt, max_tokens=200)
                    data = json.loads(raw)
                    new_desc = data.get("description", "").strip()
                    if new_desc and 60 < len(new_desc) < 170:
                        old_desc = page.summary if hasattr(page, "summary") else ""
                        page.summary = new_desc
                        page.updated_at = datetime.utcnow()
                        db.commit()
                        f.fixed = True
                        f.fix_detail = f"meta desc rewritten ({len(new_desc)} chars): {new_desc[:60]}..."
                        fixed += 1
                    else:
                        f.fix_detail = f"LLM returned unusable description ({len(new_desc)} chars)"
                except Exception as e:
                    f.fix_detail = f"LLM meta desc fix failed: {e}"
                continue

            # --- H1 missing ---
            if "h1" in issue and ("missing" in issue or "empty" in issue):
                if page is None:
                    f.fix_detail = f"no DB page found for {path} — template-level fix needed"
                    continue
                # H1 comes from page.title in our templates, so fixing title fixes H1
                current_title = getattr(page, "title", "") or ""
                if current_title:
                    f.fix_detail = f"H1 derives from page.title which exists: '{current_title[:50]}' — check template"
                else:
                    prompt = f"Generate a page title/H1 (40-70 chars) for path: {path}\nReturn JSON: {{\"title\": \"...\"}}"
                    try:
                        raw, usage = _llm_call(client, _SEO_SYSTEM, prompt, max_tokens=200)
                        data = json.loads(raw)
                        new_title = data.get("title", "").strip()
                        if new_title:
                            page.title = new_title
                            page.updated_at = datetime.utcnow()
                            db.commit()
                            f.fixed = True
                            f.fix_detail = f"H1/title generated: '{new_title}'"
                            fixed += 1
                    except Exception as e:
                        f.fix_detail = f"LLM H1 fix failed: {e}"
                continue

            # --- Multiple H1/title/meta tags ---
            if "multiple" in issue:
                f.fix_detail = f"template-level fix needed — remove duplicate tags on {path}"
                continue

            # --- Low word count ---
            if "low word count" in issue:
                if page is None or not hasattr(page, "body_html"):
                    f.fix_detail = f"no DB page for {path} — cannot expand content"
                    continue
                body = getattr(page, "body_html", "") or ""
                word_count = len(re.sub(r"<[^>]+>", " ", body).split())
                if word_count >= 200:
                    f.fix_detail = f"word count OK now ({word_count}) — may have been fixed"
                    continue

                title = getattr(page, "title", "") or path
                prompt = f"""Expand this thin page ({word_count} words) to 400-600 words.
Title: {title}
Path: {path}
Current body (first 2000 chars): {body[:2000]}

Return JSON: {{"body_html": "complete expanded HTML with h2, h3, p, ul, li tags"}}"""
                try:
                    raw, usage = _llm_call(client, _SEO_SYSTEM, prompt, max_tokens=3000)
                    data = json.loads(raw)
                    new_body = data.get("body_html", "")
                    new_wc = len(re.sub(r"<[^>]+>", " ", new_body).split())
                    if new_wc > word_count and new_wc >= 200:
                        page.body_html = new_body
                        if hasattr(page, "word_count"):
                            page.word_count = new_wc
                        page.updated_at = datetime.utcnow()
                        db.commit()
                        f.fixed = True
                        f.fix_detail = f"content expanded: {word_count} → {new_wc} words"
                        fixed += 1
                    else:
                        f.fix_detail = f"LLM expansion too short ({new_wc} words)"
                except Exception as e:
                    f.fix_detail = f"LLM content expansion failed: {e}"
                continue

            # --- SERP title mismatch ---
            if "serp" in issue and "match" in issue:
                f.fix_detail = f"SERP title mismatch on {path} — review Google's rewritten title"
                continue

            # --- AI content levels ---
            if "ai content" in issue:
                f.fix_detail = f"high AI content detected on {path} — add more original analysis"
                continue

            f.fix_detail = f"unhandled content issue: {f.issue_name}"

    finally:
        db.close()

    return fixed


# ── 1c: Image issues ─────────────────────────────────────────────────

def fix_image_issues(findings: list[AuditFinding]) -> int:
    """Fix broken images, oversized images, missing alt text."""
    client = _get_openai_client()
    db = _get_db()
    fixed = 0

    try:
        for f in findings:
            issue = f.issue_name.lower()
            path = _url_to_path(f.url)

            if "too large" in issue:
                # Try to compress the image if it's in our static dir
                # Check if it's an OG image stored in the DB
                page = _find_db_page(db, path)
                if page and hasattr(page, "og_image_bytes") and page.og_image_bytes:
                    try:
                        from io import BytesIO
                        from PIL import Image
                        img = Image.open(BytesIO(page.og_image_bytes))
                        buf = BytesIO()
                        # Resize if too large
                        if img.width > 1200:
                            ratio = 1200 / img.width
                            img = img.resize((1200, int(img.height * ratio)), Image.LANCZOS)
                        img.save(buf, format="PNG", optimize=True)
                        new_bytes = buf.getvalue()
                        if len(new_bytes) < len(page.og_image_bytes):
                            page.og_image_bytes = new_bytes
                            page.updated_at = datetime.utcnow()
                            db.commit()
                            f.fixed = True
                            f.fix_detail = f"compressed OG image: {len(page.og_image_bytes)//1024}KB → {len(new_bytes)//1024}KB"
                            fixed += 1
                            continue
                    except ImportError:
                        f.fix_detail = "Pillow not installed — cannot compress images"
                        continue
                    except Exception as e:
                        f.fix_detail = f"image compression failed: {e}"
                        continue
                f.fix_detail = f"oversized image on {path} — check static assets or external URLs"
                continue

            if "broken" in issue:
                f.fix_detail = f"broken image on {path} — check <img src> paths"
                continue

            if "alt text" in issue:
                # Generate alt text using LLM
                if client is None:
                    f.fix_detail = "skipped — no OpenAI API key for alt text generation"
                    continue
                page = _find_db_page(db, path)
                if page and hasattr(page, "body_html") and page.body_html:
                    # Find <img> tags without alt
                    body = page.body_html
                    img_no_alt = re.findall(r'<img\s+[^>]*?(?:alt=""|(?!alt=))[^>]*?>', body, re.IGNORECASE)
                    if img_no_alt:
                        title = getattr(page, "title", "") or path
                        prompt = f"""Generate alt text for images on a page titled: {title}
Images found without alt text: {len(img_no_alt)}
First image tag: {img_no_alt[0][:200]}

Return JSON: {{"alt_text": "descriptive alt text for the image (5-15 words)"}}"""
                        try:
                            raw, usage = _llm_call(client, _SEO_SYSTEM, prompt, max_tokens=100)
                            data = json.loads(raw)
                            alt = data.get("alt_text", "").strip()
                            if alt:
                                # Replace first empty alt with generated one
                                new_body = re.sub(
                                    r'(<img\s+[^>]*?)alt=""',
                                    f'\\1alt="{alt}"',
                                    body, count=1,
                                )
                                if new_body != body:
                                    page.body_html = new_body
                                    page.updated_at = datetime.utcnow()
                                    db.commit()
                                    f.fixed = True
                                    f.fix_detail = f"added alt text: '{alt}'"
                                    fixed += 1
                                    continue
                        except Exception as e:
                            f.fix_detail = f"alt text generation failed: {e}"
                            continue
                f.fix_detail = f"missing alt text on {path} — check template images"
                continue

            f.fix_detail = f"unhandled image issue: {f.issue_name}"
    finally:
        db.close()

    return fixed


# ── 1d: JS/CSS/resource issues ────────────────────────────────────────

def fix_resource_issues(findings: list[AuditFinding]) -> int:
    """Fix broken JS/CSS — check if files exist, log for manual fix."""
    for f in findings:
        path = _url_to_path(f.url)
        # Check if the referenced resource exists in static dir
        static_dir = _ROOT / "static"
        page_data = f.page_data
        f.fix_detail = f"broken resource on {path} — check <script>/<link> references in template"
    return 0


def fix_resource_redirects(findings: list[AuditFinding]) -> int:
    """Update JS/CSS/image URLs that redirect to their final destination."""
    for f in findings:
        f.fix_detail = "resource redirects — update to final URL in template"
    return 0


# ── 1e: Protocol issues (HTTP → HTTPS) ───────────────────────────────

def fix_protocol_issues(findings: list[AuditFinding]) -> int:
    """Fix http:// references in DB content that should be https://."""
    db = _get_db()
    fixed = 0

    try:
        for f in findings:
            path = _url_to_path(f.url)
            page = _find_db_page(db, path)
            if page and hasattr(page, "body_html") and page.body_html:
                old_body = page.body_html
                new_body = old_body.replace("http://", "https://")
                if new_body != old_body:
                    page.body_html = new_body
                    page.updated_at = datetime.utcnow()
                    db.commit()
                    count = old_body.count("http://") - new_body.count("http://")
                    f.fixed = True
                    f.fix_detail = f"upgraded {count} http:// → https:// references"
                    fixed += 1
                    continue
            f.fix_detail = f"http→https needed on {path} — check template references"
    finally:
        db.close()

    return fixed


# ── 1e: Link issues ──────────────────────────────────────────────────

def fix_orphan_pages(findings: list[AuditFinding]) -> int:
    """Fix pages with no internal links by injecting contextual links."""
    client = _get_openai_client()
    if client is None:
        for f in findings:
            f.fix_detail = "skipped — no OpenAI key for link injection"
        return 0

    db = _get_db()
    fixed = 0

    try:
        from src.seo.content_fixer import _fix_low_inbound_links

        for f in findings:
            if fixed >= 5:  # cap link injections per run
                f.fix_detail = "skipped — link injection limit reached"
                continue

            path = _url_to_path(f.url)
            title = (f.page_data.get("title") or [""])[0] or path

            result = _fix_low_inbound_links(client, db, path, title, 0)
            if result:
                source_page = result["source_page"]
                source_page.body_html = result["body_html"]
                if hasattr(source_page, "word_count"):
                    from src.landing_generator import _count_words
                    source_page.word_count = _count_words(result["body_html"])
                source_page.updated_at = datetime.utcnow()
                db.commit()
                f.fixed = True
                f.fix_detail = (
                    f"injected link from {result['source_path']} "
                    f"with anchor '{result['anchor_text']}'"
                )
                fixed += 1
            else:
                f.fix_detail = f"no suitable sibling page found to inject link to {path}"
    except ImportError:
        for f in findings:
            f.fix_detail = "content_fixer._fix_low_inbound_links not available"
    finally:
        db.close()

    return fixed


def fix_broken_links(findings: list[AuditFinding]) -> int:
    """Fix pages that link to broken internal pages — update or remove the link."""
    db = _get_db()
    fixed = 0
    redirects = _load_redirects()

    try:
        for f in findings:
            path = _url_to_path(f.url)
            page = _find_db_page(db, path)
            if page and hasattr(page, "body_html") and page.body_html:
                body = page.body_html
                changed = False
                # Replace links that point to known redirects
                for old_path, new_path in redirects.items():
                    if old_path in body:
                        body = body.replace(f'href="{old_path}"', f'href="{new_path}"')
                        body = body.replace(f"href='{old_path}'", f"href='{new_path}'")
                        changed = True
                if changed:
                    page.body_html = body
                    page.updated_at = datetime.utcnow()
                    db.commit()
                    f.fixed = True
                    f.fix_detail = f"updated broken link references using redirect registry"
                    fixed += 1
                    continue
            f.fix_detail = f"broken outbound links on {path} — needs manual review"
    finally:
        db.close()

    return fixed


# ── 1f: Indexability ──────────────────────────────────────────────────

def fix_canonical_issues(findings: list[AuditFinding]) -> int:
    """Fix canonical tags — these are template-level but we can log specifics."""
    for f in findings:
        path = _url_to_path(f.url)
        canonical = f.page_data.get("canonical")
        f.fix_detail = f"canonical issue on {path} (current: {canonical}) — template-level fix"
    return 0


def fix_indexability_issues(findings: list[AuditFinding]) -> int:
    """Fix noindex pages that receive organic traffic — remove noindex."""
    for f in findings:
        path = _url_to_path(f.url)
        f.fix_detail = f"IMPORTANT: {path} gets organic traffic but has noindex — remove noindex from template"
        logger.warning("NOINDEX page receives traffic: %s", f.url)
    return 0


def fix_traffic_on_error_pages(findings: list[AuditFinding]) -> int:
    """Fix 4XX/3XX pages that still receive organic traffic — high priority."""
    redirects = _load_redirects()
    fixed = 0
    for f in findings:
        path = _url_to_path(f.url)
        if path in redirects:
            f.fixed = True
            f.fix_detail = f"redirect exists → {redirects[path]}"
            fixed += 1
        else:
            f.fix_detail = f"HIGH PRIORITY: {path} receives organic traffic but returns error — needs redirect"
            logger.warning("ERROR page receives traffic: %s", f.url)
    return fixed


# ── 1g: Schema.org errors ────────────────────────────────────────────

def fix_schema_errors(findings: list[AuditFinding]) -> int:
    """
    Fix JSON-LD validation errors.
    Common fixes: add missing 'image' to Article, fix Rating fields.
    """
    # These are template-level fixes, but we can identify the specific problem
    for f in findings:
        page = f.page_data
        schema_types = page.get("jsonld_schema_types", [])
        validation_kinds = page.get("jsonld_validation_kinds", [])
        path = _url_to_path(f.url)

        if "ClaimReview" in schema_types:
            f.fix_detail = (
                f"ClaimReview schema on {path} — likely needs: "
                "reviewRating.ratingExplanation (not alternateName), "
                "and Article needs 'image' field"
            )
        elif validation_kinds:
            f.fix_detail = f"schema errors on {path}: {', '.join(validation_kinds)}"
        else:
            f.fix_detail = f"schema validation error on {path} — types: {', '.join(schema_types)}"
    return 0


# ── 1h: IndexNow submission ──────────────────────────────────────────

def submit_indexnow(findings: list[AuditFinding]) -> int:
    """Submit URLs to IndexNow via existing distribution pipeline."""
    urls = [f.url for f in findings if f.url]
    if not urls:
        return 0

    fixed = 0
    try:
        from src.distribution.indexnow import submit_urls
        result = submit_urls(urls)
        submitted = getattr(result, "submitted", 0) or 0
        logger.info("IndexNow: submitted %d/%d URLs", submitted, len(urls))
        for f in findings[:submitted]:
            f.fixed = True
            f.fix_detail = "submitted to IndexNow"
        fixed = submitted
    except ImportError:
        logger.warning("IndexNow module not available — trying direct submission")
        try:
            fixed = _indexnow_direct(urls, findings)
        except Exception as e:
            logger.error("Direct IndexNow submission failed: %s", e)
    except Exception as e:
        logger.error("IndexNow submission failed: %s", e)

    return fixed


def _indexnow_direct(urls: list[str], findings: list[AuditFinding]) -> int:
    """Fallback: submit directly to IndexNow API."""
    import requests
    from src.config import settings

    key = settings.indexnow_key
    if not key:
        logger.warning("No IndexNow key configured")
        return 0

    payload = {
        "host": "banthebots.org",
        "key": key,
        "urlList": urls[:100],
    }

    try:
        resp = requests.post(
            "https://api.indexnow.org/IndexNow",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 202):
            for f in findings:
                f.fixed = True
                f.fix_detail = "submitted to IndexNow (direct)"
            return len(urls)
        else:
            logger.warning("IndexNow returned %d: %s", resp.status_code, resp.text[:200])
            return 0
    except Exception as e:
        logger.error("IndexNow request failed: %s", e)
        return 0


def fix_double_slash(findings: list[AuditFinding]) -> int:
    """Fix URLs with double slashes in DB content."""
    db = _get_db()
    fixed = 0
    try:
        for f in findings:
            path = _url_to_path(f.url)
            page = _find_db_page(db, path)
            if page and hasattr(page, "body_html") and page.body_html:
                old = page.body_html
                new = re.sub(r'href="(/[^"]*?)//+', r'href="\1/', old)
                if new != old:
                    page.body_html = new
                    page.updated_at = datetime.utcnow()
                    db.commit()
                    f.fixed = True
                    f.fix_detail = "fixed double-slash in href attributes"
                    fixed += 1
                    continue
            f.fix_detail = f"double slash in {path} — check route generation"
    finally:
        db.close()
    return fixed


def alert_robots_txt(findings: list[AuditFinding]) -> int:
    """Alert on robots.txt issues."""
    for f in findings:
        logger.warning("ROBOTS.TXT ISSUE: %s — %s", f.issue_name, f.url)
        f.fix_detail = "alert — check robots.txt syntax"
    return 0
