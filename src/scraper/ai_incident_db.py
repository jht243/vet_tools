"""
AI Incident Database scraper.

Sources:
  1. AIID (incidentdatabase.ai) — GraphQL API, free tier, no key required.
  2. AIAAIC (aiaaic.org) — CSV export from their public Google Sheet.

Both sources write to the `ai_incidents` table. For each incident that
passes the daily cap, we also emit a ScrapedArticle so the blog pipeline
can decide whether to generate a briefing from it.

The daily cap (settings.ai_incidents_daily_cap, default 20) limits how
many NEW incidents get ingested per run to avoid LLM cost spikes.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from src.config import settings
from src.models import AIIncident, SessionLocal, init_db
from src.scraper.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# ── AIID GraphQL ──────────────────────────────────────────────────────────────
AIID_GRAPHQL_URL = "https://incidentdatabase.ai/api/graphql"

_AIID_QUERY = """
query RecentIncidents($limit: Int!, $skip: Int!) {
  incidents(
    sort: { incident_id: DESC }
    pagination: { limit: $limit, skip: $skip }
  ) {
    incident_id
    title
    date
    description
    AllegedDeployerOfAISystem { name }
    AllegedDeveloperOfAISystem { name }
    reports {
      url
      title
      source_domain
    }
  }
}
"""

# ── AIAAIC CSV ────────────────────────────────────────────────────────────────
# Public CSV export of the AIAAIC incident repository spreadsheet.
AIAAIC_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/1Bn55B4xz21-_Rgdr8BBb2lt0n_4rzLGxFADMlVW0PYI"
    "/export?format=csv&gid=888071280"
)

# ── Sector / harm-type normalisation ─────────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "health": "healthcare",
    "medical": "healthcare",
    "hospital": "healthcare",
    "clinical": "healthcare",
    "financ": "finance",
    "bank": "finance",
    "insurance": "finance",
    "lending": "finance",
    "legal": "legal",
    "law": "legal",
    "court": "legal",
    "retail": "retail",
    "ecommerce": "retail",
    "e-commerce": "retail",
    "education": "education",
    "school": "education",
    "university": "education",
    "manufactur": "manufacturing",
    "automotive": "manufacturing",
    "transport": "manufacturing",
    "real estate": "real-estate",
    "housing": "real-estate",
    "marketing": "marketing",
    "advertis": "marketing",
    "media": "marketing",
    "social media": "marketing",
    "government": "government",
    "policing": "government",
    "surveillance": "government",
    "military": "government",
    "recruit": "hr",
    "hiring": "hr",
    "employment": "hr",
}

_SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "critical": ["death", "fatality", "fatal", "killed", "serious injury", "criminal", "fraud", "discrimination lawsuit"],
    "high": ["injury", "bias", "lawsuit", "sued", "fired", "arrested", "misinformation", "deepfake", "privacy breach", "data breach"],
    "medium": ["error", "mistake", "incorrect", "hallucination", "false", "offensive", "harmful", "unfair"],
    "low": [],
}


def _normalise_sector(text: str) -> Optional[str]:
    if not text:
        return None
    lower = text.lower()
    for keyword, sector in _SECTOR_MAP.items():
        if keyword in lower:
            return sector
    return None


def _infer_severity(text: str) -> str:
    lower = (text or "").lower()
    for level in ("critical", "high", "medium"):
        if any(kw in lower for kw in _SEVERITY_KEYWORDS[level]):
            return level
    return "low"


def _parse_aiid_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            import datetime as _dt
            return _dt.datetime.strptime(date_str[:len(fmt.replace("%Y","2024").replace("%m","01").replace("%d","01"))], fmt).date()
        except ValueError:
            continue
    return None


class AIIncidentDBScraper(BaseScraper):
    """
    Scrapes AIID (GraphQL) and AIAAIC (CSV) into the ai_incidents table.

    Each new incident is also emitted as a ScrapedArticle so the
    blog pipeline can optionally generate a briefing from it.
    """

    def get_source_id(self) -> str:
        return "ai_incident_db"

    def scrape(self, target_date: Optional[date] = None) -> ScrapeResult:
        init_db()
        articles: list[ScrapedArticle] = []
        ingested = 0
        errors: list[str] = []

        cap = settings.ai_incidents_daily_cap
        lookback = date.today() - timedelta(days=settings.scraper_lookback_days)

        db = SessionLocal()
        try:
            # 1. AIID via GraphQL
            try:
                aiid_articles = self._scrape_aiid(db, lookback=lookback, cap=cap)
                articles.extend(aiid_articles)
                ingested += len(aiid_articles)
                logger.info("AIID: ingested %d new incidents", len(aiid_articles))
            except Exception as exc:
                logger.warning("AIID scrape failed: %s", exc)
                errors.append(f"AIID: {exc}")

            remaining_cap = max(0, cap - ingested)

            # 2. AIAAIC via CSV (fill remaining cap)
            if remaining_cap > 0:
                try:
                    aiaaic_articles = self._scrape_aiaaic(db, lookback=lookback, cap=remaining_cap)
                    articles.extend(aiaaic_articles)
                    ingested += len(aiaaic_articles)
                    logger.info("AIAAIC: ingested %d new incidents", len(aiaaic_articles))
                except Exception as exc:
                    logger.warning("AIAAIC scrape failed: %s", exc)
                    errors.append(f"AIAAIC: {exc}")

            db.commit()
        except Exception as exc:
            logger.exception("AIIncidentDBScraper fatal error: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return ScrapeResult(
                source=self.get_source_id(),
                success=False,
                error=str(exc),
            )
        finally:
            db.close()

        return ScrapeResult(
            source=self.get_source_id(),
            success=True,
            articles=articles,
            error="; ".join(errors) if errors else None,
        )

    # ── AIID ──────────────────────────────────────────────────────────────────

    def _scrape_aiid(
        self,
        db,
        *,
        lookback: date,
        cap: int,
        page_size: int = 50,
    ) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []
        skip = 0

        while len(articles) < cap:
            try:
                resp = httpx.post(
                    AIID_GRAPHQL_URL,
                    json={"query": _AIID_QUERY, "variables": {"limit": page_size, "skip": skip}},
                    headers={"Content-Type": "application/json", "User-Agent": "banthebots-scraper/1.0"},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("AIID GraphQL request failed (skip=%d): %s", skip, exc)
                break

            incidents = (data.get("data") or {}).get("incidents") or []
            if not incidents:
                break

            for raw in incidents:
                if len(articles) >= cap:
                    break

                incident_id = f"aiid-{raw.get('incident_id', '')}"
                existing = db.query(AIIncident).filter(AIIncident.incident_id == incident_id).first()
                if existing:
                    continue

                incident_date = _parse_aiid_date(raw.get("date", ""))
                if incident_date and incident_date < lookback:
                    # AIID is sorted desc by id; once we go past lookback, stop
                    return articles

                title = raw.get("title") or ""
                description = raw.get("description") or ""
                combined_text = f"{title} {description}"

                deployers = [e.get("name", "") for e in (raw.get("AllegedDeployerOfAISystem") or [])]
                developers = [e.get("name", "") for e in (raw.get("AllegedDeveloperOfAISystem") or [])]
                company = ", ".join(filter(None, deployers + developers))[:200] or None

                reports = raw.get("reports") or []
                source_url = reports[0].get("url") if reports else None

                row = AIIncident(
                    incident_id=incident_id,
                    source="aiid",
                    title=title[:2000],
                    description=description[:4000] if description else None,
                    incident_date=incident_date,
                    ingested_date=date.today(),
                    severity=_infer_severity(combined_text),
                    sector=_normalise_sector(combined_text),
                    company=company,
                    source_url=source_url,
                )
                db.add(row)

                if source_url and title:
                    articles.append(ScrapedArticle(
                        headline=title,
                        published_date=incident_date or date.today(),
                        source_url=source_url,
                        body_text=description,
                        source_name="AI Incident Database",
                        source_credibility="tier1",
                        article_type="incident",
                        extra_metadata={"incident_id": incident_id, "company": company},
                    ))

            if len(incidents) < page_size:
                break
            skip += page_size

        return articles

    # ── AIAAIC ────────────────────────────────────────────────────────────────

    def _scrape_aiaaic(self, db, *, lookback: date, cap: int) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []

        try:
            resp = httpx.get(
                AIAAIC_CSV_URL,
                headers={"User-Agent": "banthebots-scraper/1.0"},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            content = resp.text
        except Exception as exc:
            raise RuntimeError(f"AIAAIC CSV fetch failed: {exc}") from exc

        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            if len(articles) >= cap:
                break

            # AIAAIC column names vary; try common variants
            title = (
                row.get("Incident") or row.get("incident") or
                row.get("Title") or row.get("title") or ""
            ).strip()
            if not title:
                continue

            date_str = (
                row.get("Occurred") or row.get("occurred") or
                row.get("Date") or row.get("date") or ""
            ).strip()
            incident_date = _parse_aiid_date(date_str[:10]) if date_str else None
            if incident_date and incident_date < lookback:
                continue

            source_url = (
                row.get("URL") or row.get("url") or
                row.get("Source") or row.get("source") or ""
            ).strip() or None

            # Use title as a dedup key for AIAAIC (no stable ID)
            import hashlib as _hl
            incident_id = "aiaaic-" + _hl.md5(title.encode()).hexdigest()[:12]
            existing = db.query(AIIncident).filter(AIIncident.incident_id == incident_id).first()
            if existing:
                continue

            description = (
                row.get("Summary") or row.get("summary") or
                row.get("Description") or row.get("description") or ""
            ).strip()
            sector_hint = (
                row.get("Sector") or row.get("sector") or
                row.get("Technology") or row.get("technology") or ""
            )
            company = (
                row.get("Developer") or row.get("developer") or
                row.get("Deployer") or row.get("deployer") or
                row.get("Company") or row.get("company") or ""
            ).strip()[:200] or None

            combined = f"{title} {description} {sector_hint}"
            row_obj = AIIncident(
                incident_id=incident_id,
                source="aiaaic",
                title=title[:2000],
                description=description[:4000] if description else None,
                incident_date=incident_date,
                ingested_date=date.today(),
                severity=_infer_severity(combined),
                sector=_normalise_sector(sector_hint or combined),
                company=company,
                source_url=source_url,
            )
            db.add(row_obj)

            if source_url and title:
                articles.append(ScrapedArticle(
                    headline=title,
                    published_date=incident_date or date.today(),
                    source_url=source_url,
                    body_text=description,
                    source_name="AIAAIC",
                    source_credibility="tier1",
                    article_type="incident",
                    extra_metadata={"incident_id": incident_id, "company": company},
                ))

        return articles
