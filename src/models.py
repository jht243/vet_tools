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
    """Tell SQLAlchemy to use enum .value (lowercase) instead of .name (uppercase)
    when serializing to Postgres, and bind to the snake_case Postgres enum type
    name (e.g. SourceType -> source_type). Without values_callable, inserts send
    the uppercase Python identifier (e.g. "GOOGLE_NEWS") which doesn't match the
    lowercase Postgres enum values (e.g. "google_news").
    """
    return Enum(
        enum_cls,
        values_callable=lambda x: [e.value for e in x],
        name=_snake_case(enum_cls.__name__),
    )


class SourceType(str, enum.Enum):
    GOOGLE_NEWS = "google_news"
    FEDERAL_REGISTER = "federal_register"
    VA_NEWS = "va_news"
    DOD_NEWS = "dod_news"
    CONGRESS_VA = "congress_va"
    VA_RATES = "va_rates"
    BAH_RATES = "bah_rates"
    MILITARY_PAY = "military_pay"
    OPM_SHUTDOWN = "opm_shutdown"
    MILITARY_NEWS = "military_news"
    VSO_NEWS = "vso_news"


class CredibilityTier(str, enum.Enum):
    OFFICIAL = "official"
    TIER1 = "tier1"
    TIER2 = "tier2"
    STATE = "state"


class GazetteStatus(str, enum.Enum):
    """Article processing lifecycle status (name carried over from ven_biz_network)."""

    SCRAPED = "scraped"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    SENT = "sent"


class ExternalArticleEntry(Base):
    """Articles from external sources (Federal Register, VA News, DoD, etc.)."""

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
    status = Column(_enum_values(GazetteStatus), default=GazetteStatus.SCRAPED)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlogPost(Base):
    """
    Long-form LLM-generated analysis post tied to a source entry.
    One blog post per ExternalArticle row that crosses the relevance threshold
    and has not yet been written about. Generated on a separate budget so the
    daily report run can stay cheap.

    Primary sector tags: va_claims, disability_ratings, retirement,
    military_pay, legislation, appeals, pact_act
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

    # Conversational, ~180-250 char "social hook" — written from one analyst to
    # another. Surfaces the tension or insight without restating the title.
    # Generated in the same LLM call as the post body for new briefings; backfilled
    # separately for old ones. Used by social syndication so posts read like a human
    # wrote them rather than an RSS bot.
    social_hook = Column(Text, nullable=True)

    # Pre-rendered 1200x630 PNG bytes of the briefing's per-post Open Graph card.
    # Rendered once at blog-creation time so every share preview shows the
    # briefing's own headline. Served by /og/briefing/<slug>.png. Typically ~50-80 KB.
    og_image_bytes = Column(LargeBinary, nullable=True)

    primary_sector = Column(String(80), nullable=True, index=True)
    sectors_json = Column(JSON, nullable=True)
    keywords_json = Column(JSON, nullable=True)
    related_slugs_json = Column(JSON, nullable=True)

    # 3-5 short "Key takeaways" bullets rendered as a scannable aside at the top
    # of /briefing/<slug>. Generated in the same LLM call as the post body and
    # backfilled for legacy posts. Scannable bullets correlate with better on-page
    # CTR and time-on-page.
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
    Evergreen landing pages — the pillar /va-disability-claims, sector pages,
    explainers. Generated less frequently than blog posts (e.g. weekly) and with
    the premium LLM model. Stored as pre-rendered HTML so the request path stays
    cheap.
    """

    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_key = Column(String(120), nullable=False, unique=True, index=True)
    page_type = Column(String(40), nullable=False, index=True)

    title = Column(Text, nullable=False)
    subtitle = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    body_html = Column(Text, nullable=False)
    keywords_json = Column(JSON, nullable=True)
    sections_json = Column(JSON, nullable=True)
    faq_json = Column(JSON, nullable=True)

    sector_slug = Column(String(80), nullable=True, index=True)
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
    """
    Tracks every outbound distribution event (Google Indexing ping, newsletter
    send, etc.). One row per (url, channel) attempt. Used for idempotency (don't
    re-ping the same URL on the same channel within a cooldown window) and for
    operational diagnostics.

    Channels written into this table:
      - google_indexing      Google's Indexing API URL_UPDATED notification
      - indexnow             IndexNow ping (Bing, Yandex, etc.)
      - newsletter           Buttondown / Resend newsletter send
      - internet_archive     archive.org upload
      - zenodo               Zenodo deposit
      - osf                  OSF Preprints deposit
    """

    __tablename__ = "distribution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    channel = Column(String(40), nullable=False, index=True)
    url = Column(String(1000), nullable=False, index=True)

    entity_type = Column(String(40), nullable=True)  # blog_post | landing_page | static
    entity_id = Column(Integer, nullable=True)

    success = Column(Boolean, nullable=False, default=False, index=True)
    response_code = Column(Integer, nullable=True)
    response_snippet = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ScrapeLog(Base):
    """Tracks every scrape attempt for diagnostics and retry logic."""

    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(_enum_values(SourceType), nullable=False)
    scrape_date = Column(Date, nullable=False)
    success = Column(Boolean, nullable=False)
    entries_found = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Domain-specific tables ─────────────────────────────────────────────────────


class VACondition(Base):
    """A VA-recognized disability condition with typical rating breakpoints
    and secondary service-connection relationships. Powers the condition
    landing pages (e.g. /conditions/tinnitus, /conditions/sleep-apnea).
    """

    __tablename__ = "va_conditions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    icd_codes_json = Column(JSON, nullable=True)           # list of ICD-10 codes
    typical_ratings_json = Column(JSON, nullable=True)     # e.g. [10, 30, 50, 70, 100]
    evidence_notes = Column(Text, nullable=True)
    secondary_conditions_json = Column(JSON, nullable=True)  # list of condition slugs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VABenefitsRate(Base):
    """Annual VA compensation rate tables — disability, SMC, DIC.
    One row per (year, rate_type) pair; rate_table_json holds the full table
    keyed by rating percentage or dependent count.
    """

    __tablename__ = "va_benefits_rates"
    __table_args__ = (
        UniqueConstraint("year", "rate_type", name="uq_va_rate_year_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    rate_type = Column(String(40), nullable=False)   # disability | smc | dic
    rate_table_json = Column(JSON, nullable=False)
    effective_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BAHRate(Base):
    """Basic Allowance for Housing rate for a single (year, MHA, pay grade,
    dependency status) combination. Rates are in cents to avoid floating-point
    representation issues.
    """

    __tablename__ = "bah_rates"
    __table_args__ = (
        UniqueConstraint(
            "year", "mha_code", "pay_grade", "with_dependents", name="uq_bah_rate"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    mha_code = Column(String(10), nullable=False, index=True)
    mha_name = Column(String(200), nullable=False)
    pay_grade = Column(String(10), nullable=False)     # E-1, O-3, W-2, etc.
    with_dependents = Column(Boolean, nullable=False, default=True)
    monthly_rate = Column(Integer, nullable=False)     # in cents
    created_at = Column(DateTime, default=datetime.utcnow)


class MilitaryPayTable(Base):
    """Monthly basic pay for a (year, pay grade, years-of-service) bracket.
    Pay is stored in cents to avoid floating-point issues.
    """

    __tablename__ = "military_pay_tables"
    __table_args__ = (
        UniqueConstraint("year", "pay_grade", "yos_min", name="uq_pay_table"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    pay_grade = Column(String(10), nullable=False)
    yos_min = Column(Integer, nullable=False)
    yos_max = Column(Integer, nullable=True)
    monthly_pay_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailCapture(Base):
    """Email addresses collected via on-site tools (rating calculator, BAH
    estimator, etc.). source_tool identifies which tool/page drove the signup.
    ip_hash is a one-way hash of the submitter's IP for basic deduplication
    without storing PII in plain text.
    """

    __tablename__ = "email_captures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), nullable=False, index=True)
    source_tool = Column(String(120), nullable=True)
    capture_date = Column(Date, nullable=False, default=date.today)
    ip_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── DB engine / session ────────────────────────────────────────────────────────

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=280,
)
SessionLocal = sessionmaker(bind=engine)
_init_lock = Lock()
_db_initialized = False


def init_db(*, force: bool = False):
    """Create tables once per process, not once per request.

    Also runs lightweight, idempotent column-additions for ALTERations that
    can't be expressed by `create_all` on a pre-existing table. We deliberately
    stop short of a full Alembic setup — for a single-writer schema this stays
    simpler and safer.
    """
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
    """Add columns that were introduced after the table was first created.
    Cross-DB (SQLite + Postgres) safe — uses the SQLAlchemy inspector to check
    for existence before issuing an ALTER.
    """
    insp = sa_inspect(engine)
    dialect = engine.dialect.name

    # Per-dialect column type. SQLite uses BLOB for binary, Postgres BYTEA.
    blob_type = "BYTEA" if dialect == "postgresql" else "BLOB"
    # SQLAlchemy's JSON type maps to JSONB on Postgres and TEXT on SQLite.
    json_type = "JSONB" if dialect == "postgresql" else "TEXT"

    additions = [
        ("blog_posts", "social_hook", "TEXT"),
        ("blog_posts", "og_image_bytes", blob_type),
        ("blog_posts", "takeaways_json", json_type),
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


# ── Enum value additions ───────────────────────────────────────────────────────
# Postgres enum types are immutable once created — SQLAlchemy's create_all()
# will create the enum with the values present at first run but WILL NOT add
# new values when the Python enum grows. We have to ALTER TYPE manually. SQLite
# stores enum columns as VARCHAR so this is a no-op there.
#
# Idempotent via "ADD VALUE IF NOT EXISTS". The ALTER must run outside an
# explicit transaction on older PG versions, so we use AUTOCOMMIT. Failures are
# logged but never raise — a missing enum value will surface as a row-insert
# error downstream, which is preferable to a crashed init.
_SOURCE_TYPE_ENUM_ADDITIONS: tuple[tuple[str, str], ...] = (
    ("source_type", "google_news"),
    ("source_type", "federal_register"),
    ("source_type", "va_news"),
    ("source_type", "dod_news"),
    ("source_type", "congress_va"),
    ("source_type", "va_rates"),
    ("source_type", "bah_rates"),
    ("source_type", "military_pay"),
    ("source_type", "opm_shutdown"),
    ("source_type", "military_news"),
    ("source_type", "vso_news"),
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
                    value,
                    enum_name,
                    exc,
                )
