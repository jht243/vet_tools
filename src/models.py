import enum
from datetime import datetime, date
from threading import Lock

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Float,
    Date,
    DateTime,
    Enum,
    Boolean,
    JSON,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy import inspect as sa_inspect, text as sa_text
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings

Base = declarative_base()


def _snake_case(name: str) -> str:
    """SourceType -> source_type"""
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _enum_values(enum_cls):
    """Bind SQLAlchemy enum to lowercase Postgres enum values."""
    return Enum(
        enum_cls,
        values_callable=lambda x: [e.value for e in x],
        name=_snake_case(enum_cls.__name__),
    )


class SourceType(str, enum.Enum):
    GOOGLE_NEWS    = "google_news"
    AI_INCIDENT_DB = "ai_incident_db"
    AIAAIC         = "aiaaic"
    EU_AI_ACT      = "eu_ai_act"
    FTC_AI         = "ftc_ai"
    NIST_RMF       = "nist_rmf"
    CONGRESS_AI    = "congress_ai"
    DOE_ENERGY     = "doe_energy"
    BLS_LABOR      = "bls_labor"
    LAYOFF_FYI     = "layoff_fyi"
    ARXIV_AI       = "arxiv_ai"
    SEJ_ALGO       = "sej_algo"


class CredibilityTier(str, enum.Enum):
    OFFICIAL = "official"
    TIER1 = "tier1"
    TIER2 = "tier2"
    STATE = "state"


class ArticleStatus(str, enum.Enum):
    SCRAPED  = "scraped"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    SENT     = "sent"


class ExternalArticleEntry(Base):
    """Articles from external sources (Google News, incident DBs, regulators, etc.)."""

    __tablename__ = "external_articles"
    __table_args__ = (UniqueConstraint("source", "source_url", name="uq_ext_source_url"),)

    id = Column(Integer, primary_key=True, autoincrement=True)

    source = Column(_enum_values(SourceType), nullable=False, index=True)
    source_url = Column(String(1000), nullable=False)
    source_name = Column(String(200), nullable=True)
    credibility = Column(_enum_values(CredibilityTier), default=CredibilityTier.TIER2)

    headline = Column(Text, nullable=False)
    published_date = Column(Date, nullable=False, index=True)
    body_text = Column(Text, nullable=True)
    article_type = Column(String(100), nullable=True)

    tone_score = Column(Float, nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    analysis_json = Column(JSON, nullable=True)
    status = Column(_enum_values(ArticleStatus), default=ArticleStatus.SCRAPED)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlogPost(Base):
    """
    Long-form LLM-generated briefing tied to one ExternalArticleEntry.
    One post per article that crosses the relevance threshold (score ≥ 5).
    """

    __tablename__ = "blog_posts"
    __table_args__ = (
        UniqueConstraint("source_table", "source_id", name="uq_blog_source"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    source_table = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)

    slug = Column(String(200), nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    subtitle = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    body_html = Column(Text, nullable=False)

    # Pre-rendered 1200x630 OG card PNG, served by /og/briefing/<slug>.png
    og_image_bytes = Column(LargeBinary, nullable=True)

    primary_sector = Column(String(80), nullable=True, index=True)
    sectors_json = Column(JSON, nullable=True)
    keywords_json = Column(JSON, nullable=True)
    related_slugs_json = Column(JSON, nullable=True)

    # 3-5 "Key takeaways" bullets rendered as a scannable aside on /briefing/<slug>
    takeaways_json = Column(JSON, nullable=True)

    word_count = Column(Integer, nullable=True)
    reading_minutes = Column(Integer, nullable=True)

    published_date = Column(Date, nullable=False, index=True)
    canonical_source_url = Column(String(1000), nullable=True)

    llm_model = Column(String(100), nullable=True)
    llm_input_tokens = Column(Integer, nullable=True)
    llm_output_tokens = Column(Integer, nullable=True)
    llm_cost_usd = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LandingPage(Base):
    """
    Evergreen landing pages — the /ai-backlash/ pillar, /responsible-ai/{industry}/
    spoke pages, and /explainers/{slug} pages. Generated weekly with the premium
    LLM model and stored as pre-rendered HTML so request path stays cheap.
    """

    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_key = Column(String(120), nullable=False, unique=True, index=True)
    page_type = Column(String(40), nullable=False, index=True)  # pillar | industry | explainer

    title = Column(Text, nullable=False)
    subtitle = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)       # used as meta description
    body_html = Column(Text, nullable=False)
    keywords_json = Column(JSON, nullable=True)
    sections_json = Column(JSON, nullable=True)

    # faq_json: array of {question, answer} objects, 3-5 per page.
    # Rendered as <details>/<summary> accordion + FAQPage JSON-LD.
    faq_json = Column(JSON, nullable=True)

    sector_slug = Column(String(80), nullable=True, index=True)  # industry slug for spoke pages
    canonical_path = Column(String(200), nullable=False)
    word_count = Column(Integer, nullable=True)

    llm_model = Column(String(120), nullable=True)
    llm_input_tokens = Column(Integer, nullable=True)
    llm_output_tokens = Column(Integer, nullable=True)
    llm_cost_usd = Column(Float, nullable=True)

    last_generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DistributionLog(Base):
    """Tracks every outbound distribution event (Google Indexing ping, IndexNow, etc.)."""

    __tablename__ = "distribution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    channel = Column(String(40), nullable=False, index=True)   # google_indexing | indexnow
    url = Column(String(1000), nullable=False, index=True)

    entity_type = Column(String(40), nullable=True)            # blog_post | landing_page | static
    entity_id = Column(Integer, nullable=True)

    success = Column(Boolean, nullable=False, default=False, index=True)
    response_code = Column(Integer, nullable=True)
    response_snippet = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ScrapeLog(Base):
    """Tracks every scrape attempt for diagnostics."""

    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(_enum_values(SourceType), nullable=False)
    scrape_date = Column(Date, nullable=False)
    success = Column(Boolean, nullable=False)
    entries_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIRiskSnapshot(Base):
    """
    One row per reporting period. Stores the AI risk scorecard for that period
    plus the raw evidence used to derive it. Recomputed periodically; the row
    for the current period is upserted in place (keyed on period_label).
    """

    __tablename__ = "ai_risk_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)

    period_label = Column(String(16), nullable=False, unique=True, index=True)
    period_start = Column(Date, nullable=False, index=True)

    composite_score = Column(Float, nullable=True)
    methodology = Column(Text, nullable=True)

    bars_json = Column(JSON, nullable=False)
    evidence_json = Column(JSON, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIIncident(Base):
    """
    AI incident records from AIID (incidentdatabase.ai) and AIAAIC.
    Powers the /ai-incidents/ tracker page.
    """

    __tablename__ = "ai_incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), nullable=True, unique=True, index=True)
    source = Column(String(40), nullable=False, index=True)    # "aiid" | "aiaaic"

    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    incident_date = Column(Date, nullable=True, index=True)
    ingested_date = Column(Date, nullable=False, index=True)

    severity = Column(String(20), nullable=True, index=True)   # critical | high | medium | low
    sector = Column(String(80), nullable=True, index=True)     # healthcare | finance | legal | etc.
    company = Column(String(200), nullable=True, index=True)
    technology = Column(String(200), nullable=True)            # LLM | CV | recommendation | etc.
    harm_type = Column(String(200), nullable=True)             # bias | hallucination | privacy | etc.

    source_url = Column(String(1000), nullable=True)
    summary_html = Column(Text, nullable=True)
    analysis_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AILayoff(Base):
    """
    Companies that announced layoffs attributed to AI automation.
    Powers the /ai-layoffs/ tracker page.
    """

    __tablename__ = "ai_layoffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String(200), nullable=False, index=True)
    industry = Column(String(80), nullable=True, index=True)
    country = Column(String(80), nullable=True, default="US")
    state = Column(String(80), nullable=True, index=True)
    job_count = Column(Integer, nullable=True)
    announced_date = Column(Date, nullable=True, index=True)
    ai_cause_notes = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    source_name = Column(String(200), nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataCenter(Base):
    """
    Known and proposed AI data centers.
    Powers the /data-centers/ list and /data-center-map/ interactive map.
    """

    __tablename__ = "data_centers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    operator = Column(String(200), nullable=True, index=True)
    status = Column(String(40), nullable=False, index=True, default="operating")
    city = Column(String(100), nullable=True)
    state = Column(String(80), nullable=True, index=True)
    county = Column(String(100), nullable=True)
    country = Column(String(80), nullable=True, default="US")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    capacity_mw = Column(Float, nullable=True)
    water_source = Column(String(200), nullable=True)
    announced_date = Column(Date, nullable=True)
    source_url = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AILawsuit(Base):
    """
    Lawsuits filed against AI companies by creators, publishers, and individuals.
    Powers the /ai-lawsuits/ tracker page.
    """

    __tablename__ = "ai_lawsuits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_name = Column(String(300), nullable=False)
    plaintiff = Column(String(300), nullable=False, index=True)
    defendant = Column(String(300), nullable=False, index=True)
    filed_date = Column(Date, nullable=True, index=True)
    court = Column(String(200), nullable=True)
    claim_type = Column(String(100), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="ongoing", index=True)
    amount_sought_usd = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIResistanceAction(Base):
    """
    Companies, unions, and governments that are pushing back against AI —
    no-AI policies, worker protections, legislation, and bans.
    Powers the /fighting-back/ tracker page.
    """

    __tablename__ = "ai_resistance_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(300), nullable=False, index=True)
    actor_type = Column(String(40), nullable=False, index=True)
    action_type = Column(String(80), nullable=False, index=True)
    country = Column(String(80), nullable=True, default="US")
    state = Column(String(80), nullable=True, index=True)
    industry = Column(String(80), nullable=True, index=True)
    announced_date = Column(Date, nullable=True, index=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    still_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RiskAssessmentLead(Base):
    """Email captures from /ai-risk-assessment/ tool waitlist."""

    __tablename__ = "risk_assessment_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=True)
    industry = Column(String(80), nullable=True)
    email = Column(String(200), nullable=True, index=True)
    score = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=True)
    form_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)
_init_lock = Lock()
_db_initialized = False


def init_db(*, force: bool = False):
    """Create tables once per process. Runs idempotent column/enum additions."""
    global _db_initialized
    if _db_initialized and not force:
        return
    with _init_lock:
        if _db_initialized and not force:
            return
        Base.metadata.create_all(engine)
        _ensure_columns()
        _ensure_enum_values()
        _db_initialized = True


def _ensure_columns() -> None:
    """Add columns introduced after a table was first created."""
    insp = sa_inspect(engine)
    dialect = engine.dialect.name

    blob_type = "BYTEA" if dialect == "postgresql" else "BLOB"
    json_type = "JSONB" if dialect == "postgresql" else "TEXT"

    additions = [
        ("blog_posts", "og_image_bytes", blob_type),
        ("blog_posts", "takeaways_json", json_type),
        ("landing_pages", "faq_json", json_type),
    ]

    for table_name, column_name, column_type in additions:
        if table_name not in insp.get_table_names():
            continue
        existing = {c["name"] for c in insp.get_columns(table_name)}
        if column_name in existing:
            continue
        with engine.begin() as conn:
            conn.execute(
                sa_text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


_SOURCE_TYPE_ENUM_ADDITIONS: tuple[tuple[str, str], ...] = (
    ("source_type", "google_news"),
    ("source_type", "ai_incident_db"),
    ("source_type", "aiaaic"),
    ("source_type", "eu_ai_act"),
    ("source_type", "ftc_ai"),
    ("source_type", "nist_rmf"),
    ("source_type", "congress_ai"),
    ("source_type", "doe_energy"),
    ("source_type", "bls_labor"),
    ("source_type", "layoff_fyi"),
    ("source_type", "arxiv_ai"),
    ("source_type", "sej_algo"),
)


def _ensure_enum_values() -> None:
    if engine.dialect.name != "postgresql":
        return

    import logging
    log = logging.getLogger(__name__)

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for enum_name, value in _SOURCE_TYPE_ENUM_ADDITIONS:
            try:
                conn.execute(
                    sa_text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
                )
            except Exception as exc:
                log.warning(
                    "Could not add enum value %r to %s (continuing anyway): %s",
                    value, enum_name, exc,
                )
