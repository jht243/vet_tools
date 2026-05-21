"""
Ahrefs-powered site audit — pulls all issues with crawled > 0,
fetches affected URLs, and dispatches to auto-fixers.

Entry point:  run_ahrefs_audit(weekly=True)
Called from:   run_daily.py Phase 6b
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.seo.ahrefs_client import AhrefsClient, AhrefsAPIError

logger = logging.getLogger(__name__)

# ── Issue category → fixer mapping ────────────────────────────────────
# Maps Ahrefs issue category names to the fixer module function that
# handles them.  Only issues with an entry here are auto-fixed; the
# rest are logged as alerts.

_ISSUE_DISPATCH: dict[str, str] = {
    # 1a: HTTP errors
    "404 page": "fix_broken_pages",
    "4XX page": "fix_broken_pages",
    "500 page": "alert_server_errors",
    "5XX page": "alert_server_errors",
    "Timed out": "alert_server_errors",
    # 1b: Content
    "Title tag missing or empty": "fix_content_issues",
    "Multiple title tags": "fix_content_issues",
    "Title too short": "fix_content_issues",
    "Title too long": "fix_content_issues",
    "Meta description tag missing or empty": "fix_content_issues",
    "Meta description too short": "fix_content_issues",
    "Meta description too long": "fix_content_issues",
    "Multiple meta description tags": "fix_content_issues",
    "H1 tag missing or empty": "fix_content_issues",
    "Multiple H1 tags": "fix_content_issues",
    "Low word count": "fix_content_issues",
    "Page and SERP titles do not match": "fix_content_issues",
    # 1c: Images
    "Image file size too large": "fix_image_issues",
    "Image broken": "fix_image_issues",
    "Page has broken image": "fix_image_issues",
    "Missing alt text": "fix_image_issues",
    "HTTPS page links to HTTP image": "fix_protocol_issues",
    "Image redirects": "fix_resource_redirects",
    "Page has redirected image": "fix_resource_redirects",
    # 1d: JS & CSS
    "JavaScript broken": "fix_resource_issues",
    "Page has broken JavaScript": "fix_resource_issues",
    "CSS broken": "fix_resource_issues",
    "Page has broken CSS": "fix_resource_issues",
    "HTTPS page links to HTTP JavaScript": "fix_protocol_issues",
    "HTTPS page links to HTTP CSS": "fix_protocol_issues",
    "JavaScript redirects": "fix_resource_redirects",
    "CSS redirects": "fix_resource_redirects",
    "Page has redirected JavaScript": "fix_resource_redirects",
    "Page has redirected CSS": "fix_resource_redirects",
    # 1e: Links
    "Orphan page (has no incoming internal links)": "fix_orphan_pages",
    "Canonical URL has no incoming internal links": "fix_orphan_pages",
    "Page has links to broken page": "fix_broken_links",
    "HTTPS page has internal links to HTTP": "fix_protocol_issues",
    # 1f: Indexability
    "Canonical points to 4XX": "fix_canonical_issues",
    "Canonical points to 5XX": "fix_canonical_issues",
    "Canonical points to redirect": "fix_canonical_issues",
    "Duplicate pages without canonical": "fix_canonical_issues",
    "Non-canonical page specified as canonical one": "fix_canonical_issues",
    "Noindex page receives organic traffic": "fix_indexability_issues",
    "4XX page receives organic traffic": "fix_traffic_on_error_pages",
    "3XX page receives organic traffic": "fix_traffic_on_error_pages",
    # 1g: Structured data
    "Structured data has schema.org validation error": "fix_schema_errors",
    "Structured data has Google rich results validation error": "fix_schema_errors",
    # 1h: Other
    "Pages to submit to IndexNow": "submit_indexnow",
    "Double slash in URL": "fix_double_slash",
    "Robots.txt has syntax error": "alert_robots_txt",
}

# Issues we only log, never auto-fix
_ALERT_ONLY = {
    "alert_server_errors",
    "alert_robots_txt",
}


@dataclass
class AuditFinding:
    """One issue found on one URL."""
    issue_name: str
    issue_id: str
    severity: str  # Error, Warning, Notice
    category: str
    url: str
    fixer: str  # function name from _ISSUE_DISPATCH, or "manual"
    page_data: dict = field(default_factory=dict)
    fixed: bool = False
    fix_detail: str = ""


@dataclass
class AuditReport:
    """Aggregate result of an Ahrefs audit run."""
    run_at: str = ""
    is_weekly: bool = False
    health_score: int | None = None
    total_issue_types_checked: int = 0
    total_findings: int = 0
    auto_fixed: int = 0
    alerts: int = 0
    manual_needed: int = 0
    units_used: int = 0
    findings: list[AuditFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "run_at": self.run_at,
            "health_score": self.health_score,
            "issue_types_checked": self.total_issue_types_checked,
            "findings": self.total_findings,
            "auto_fixed": self.auto_fixed,
            "alerts": self.alerts,
            "manual_needed": self.manual_needed,
            "units_used": self.units_used,
        }


def run_ahrefs_audit(weekly: bool = False) -> AuditReport:
    """
    Main entry point.

    - Daily mode (weekly=False): only IndexNow submission
    - Weekly mode (weekly=True): full 100-issue-type scan + all fixers
    """
    client = AhrefsClient()
    report = AuditReport(
        run_at=datetime.utcnow().isoformat(),
        is_weekly=weekly,
    )

    # ── Health score ──────────────────────────────────────────────────
    try:
        health = client.site_audit_health()
        report.health_score = health.get("health_score")
        logger.info("Ahrefs health score: %s", report.health_score)
    except Exception as e:
        logger.warning("Failed to get health score: %s", e)

    # ── Get issues with hits ──────────────────────────────────────────
    try:
        issues = client.site_audit_issues_with_hits()
    except Exception as e:
        report.errors.append(f"Failed to get issues: {e}")
        logger.error("Ahrefs issues fetch failed: %s", e)
        report.units_used = client.units_used
        return report

    report.total_issue_types_checked = len(issues)
    logger.info("Ahrefs found %d issue types with hits", len(issues))

    # ── Daily mode: only IndexNow ─────────────────────────────────────
    if not weekly:
        indexnow_issues = [
            i for i in issues if i["name"] == "Pages to submit to IndexNow"
        ]
        if indexnow_issues:
            _process_issue(client, indexnow_issues[0], report)
        report.units_used = client.units_used
        return report

    # ── Weekly mode: process all issues ───────────────────────────────
    for issue in issues:
        try:
            _process_issue(client, issue, report)
        except Exception as e:
            logger.error("Error processing issue %s: %s", issue["name"], e)
            report.errors.append(f"{issue['name']}: {e}")

    report.units_used = client.units_used
    logger.info(
        "Ahrefs audit done: %d findings, %d fixed, %d alerts, %d manual, %d units",
        report.total_findings,
        report.auto_fixed,
        report.alerts,
        report.manual_needed,
        report.units_used,
    )
    return report


def _process_issue(client: AhrefsClient, issue: dict, report: AuditReport) -> None:
    """Fetch affected pages for one issue type and dispatch to fixer."""
    name = issue["name"]
    issue_id = issue["issue_id"]
    severity = issue["importance"]
    category = issue["category"]
    crawled = issue.get("crawled") or 0

    fixer_name = _ISSUE_DISPATCH.get(name, "manual")

    logger.info(
        "Processing: [%s] %s — %d pages (fixer: %s)",
        severity, name, crawled, fixer_name,
    )

    # Fetch affected URLs
    pages = client.site_audit_pages_for_issue(issue_id, limit=min(crawled, 250))

    for page in pages:
        url = page.get("url", "")
        finding = AuditFinding(
            issue_name=name,
            issue_id=issue_id,
            severity=severity,
            category=category,
            url=url,
            fixer=fixer_name,
            page_data=page,
        )
        report.findings.append(finding)
        report.total_findings += 1

    # Dispatch to fixer
    if fixer_name == "manual":
        report.manual_needed += len(pages)
        return

    if fixer_name in _ALERT_ONLY:
        report.alerts += len(pages)
        for f in report.findings[-len(pages):]:
            f.fix_detail = "alert_only"
        return

    # Import and call the fixer
    try:
        from src.seo import ahrefs_fixers
        fixer_fn = getattr(ahrefs_fixers, fixer_name, None)
        if fixer_fn is None:
            logger.warning("Fixer %s not implemented yet", fixer_name)
            report.manual_needed += len(pages)
            return

        findings_for_issue = report.findings[-len(pages):]
        fixed_count = fixer_fn(findings_for_issue)
        report.auto_fixed += fixed_count
        logger.info("  → %s fixed %d/%d pages", fixer_name, fixed_count, len(pages))

    except Exception as e:
        logger.error("Fixer %s failed: %s", fixer_name, e, exc_info=True)
        report.errors.append(f"Fixer {fixer_name}: {e}")
