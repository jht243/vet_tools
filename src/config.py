from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    database_url: str = "sqlite:///./vet_tools.db"
    storage_dir: Path = Path("./storage")
    output_dir: Path = Path("./output")

    log_level: str = "INFO"

    # Scraper
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    scraper_retry_delay_seconds: int = 60
    scraper_lookback_days: int = 30

    # LLM Analysis
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    # Cheaper model for short, prose-only generation tasks where facts are already
    # structured (e.g. entity-page narratives). ~$0.0002/page at gpt-4o-mini pricing,
    # and cached by content fingerprint so reruns are free. Override via
    # OPENAI_NARRATIVE_MODEL env var.
    openai_narrative_model: str = "gpt-4o-mini"
    # Lower than ven_biz_network (was 5) because VA/military news volume is lighter;
    # we want to surface more of the available signal rather than discard it.
    analysis_min_relevance: int = 4
    # Wide enough to cover a full year of backfilled official-source content by
    # default. Override via REPORT_LOOKBACK_DAYS in env for a shorter window.
    report_lookback_days: int = 120
    # Hard cap on LLM calls per pipeline run. Default 200 calls/run ≈ ~$1.20 at
    # current gpt-4o pricing (~$0.006/call). With the cron firing twice a day that's
    # ~$2.40/day worst case, well inside a $5/day budget. Override via
    # LLM_CALL_BUDGET_PER_RUN env var.
    llm_call_budget_per_run: int = 200
    # Approximate gpt-4o pricing for the cost-estimate log line. Update if you
    # switch models or pricing changes. Values are USD per 1M tokens.
    llm_input_price_per_mtok: float = 2.50
    llm_output_price_per_mtok: float = 10.00

    # Premium model — used ONLY for evergreen, high-traffic landing content
    # (pillar page, sector landing pages, evergreen explainers). Keep gpt-4o for
    # the daily news churn (analyzer + blog_generator) because that runs hundreds
    # of times/day; reserve the premium model for the ~10 pages that need to read
    # like a senior analyst wrote them. Override via OPENAI_PREMIUM_MODEL env var.
    openai_premium_model: str = "gpt-4o"
    llm_premium_input_price_per_mtok: float = 5.00
    llm_premium_output_price_per_mtok: float = 15.00

    # Newsletter
    newsletter_provider: str = "console"
    newsletter_from_email: str = "briefing@rankandpay.org"
    newsletter_api_key: str = ""
    subscriber_list_path: str = "subscribers.json"
    seo_email_provider: str = "resend"
    seo_email_recipient: str = "<RECIPIENT_EMAIL>"
    seo_email_subject: str = "SEO Updates <SITE_NAME>"
    resend_api_key: str = ""

    # GA4 Measurement Protocol (server-side events)
    ga4_measurement_id: str = ""
    ga4_api_secret: str = ""

    # Google reporting (GA4 + Search Console)
    google_reporting_sa_json: str = ""
    google_reporting_sa_file: str = ""
    google_reporting_ga4_property_id: str = ""
    google_reporting_gsc_site_url: str = ""
    google_reporting_output_dir: Path = Path("./output/google_reporting")
    google_reporting_ga_lookback_days: int = 30
    google_reporting_gsc_lookback_days: int = 90

    # Buttondown (subscriber signup)
    buttondown_api_key: str = ""

    # Supabase Storage (used to share report.html between cron + web on Render)
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_report_bucket: str = "reports"
    # Object key for the homepage report HTML inside the bucket. MUST be unique
    # per project when multiple projects share a Supabase bucket to avoid
    # cross-project collisions. Override via SUPABASE_REPORT_OBJECT_KEY env var.
    supabase_report_object_key: str = "va-report.html"

    # Server
    server_port: int = 8080

    # ── Admin endpoints ────────────────────────────────────────────────────────
    # Bearer token for /admin/* routes (e.g. /admin/regen-report). Leave blank
    # to disable the endpoints entirely.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    admin_token: str = ""

    # SEO / canonical URL — base URL of the deployed site. Used for canonical
    # <link>, sitemap entries, JSON-LD identifiers, and OG share URLs. Override
    # via SITE_URL env var when a custom domain is added.
    site_url: str = "https://www.rankandpay.org"
    site_name: str = "Rank and Pay"
    site_owner_org: str = "Rank and Pay"
    site_locale: str = "en_US"
    site_description: str = (
        "Free tools and daily briefings covering military pay tables, BAH rates, "
        "VA disability ratings, retirement calculators, and benefits guides."
    )

    @property
    def canonical_site_url(self) -> str:
        """Customer-facing base URL (emails, canonical links, sitemap).

        Always returns https://www.rankandpay.org unless a different custom
        domain is explicitly set via SITE_URL env var. Render hostnames
        (*.onrender.com) are ignored and fall back to the www canonical.
        """
        u = (self.site_url or "").strip().rstrip("/")
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        lower = u.lower()
        # Fall back to www canonical for Render preview URLs or missing config
        if not u or "onrender.com" in lower:
            return "https://www.rankandpay.org"
        # Normalise bare domain → www
        if lower in {"https://rankandpay.org", "http://rankandpay.org"}:
            return "https://www.rankandpay.org"
        return u

    # Long-form blog post generator. Each post is roughly 700-900 words and uses
    # ~2-3k completion tokens, so each call costs ~$0.04. The budget caps total
    # post generations per pipeline run.
    blog_gen_budget_per_run: int = 6
    blog_gen_min_relevance: int = 5
    blog_gen_lookback_days: int = 14
    blog_gen_max_words: int = 900

    # ── Google News intake cap ─────────────────────────────────────────────────
    # Maximum number of NEW Google News articles to persist per calendar day. The
    # pipeline ranks all candidates by a veteran-interest heuristic and persists
    # only the top N. Intentionally aligned with blog_gen_budget_per_run so that
    # every persisted article has a 1:1 chance of becoming a blog post on the same
    # cron tick. Set to 0 to disable Google News intake without removing the scraper.
    google_news_daily_cap: int = 6

    # ── SEO: Semrush API ──────────────────────────────────────────────────────
    # API key from https://www.semrush.com/accounts/subscription-info/api-units/
    semrush_api_key: str = ""
    semrush_database: str = "us"

    # ── Congress.gov API ──────────────────────────────────────────────────────
    # Free API key — sign up at https://api.congress.gov/sign-up/
    # Enables the CongressVAScraper to pull recent bills and committee activity.
    # Leave blank to disable; scraper will fall back to committee RSS only.
    congress_api_key: str = ""

    # ── Press-Release Radar ───────────────────────────────────────────────────
    # Recipient for the daily press-radar digest (qualifying findings only).
    press_radar_recipient_email: str = ""
    # From-address for press radar emails. Must use a verified Resend domain.
    press_radar_from_email: str = ""

    # ── Distribution: IndexNow (Bing, Yandex, Seznam, Naver, Mojeek) ─────────
    # The IndexNow key — generated in Bing Webmaster Tools. Not a secret: it's
    # publicly hosted at /{key}.txt to prove domain ownership. Override via
    # INDEXNOW_KEY env var in production.
    indexnow_key: str = ""

    # ── Distribution: Google Indexing API ─────────────────────────────────────
    # Service-account JSON pasted as a single env var (the entire JSON blob,
    # including curly braces and embedded \n in private_key). Leave blank to
    # disable.
    google_indexing_sa_json: str = ""
    # Alternate: path to the JSON file on disk (Render "secret files" mounts).
    # Only consulted when google_indexing_sa_json is empty.
    google_indexing_sa_file: str = ""
    # Only ping URLs newer than this many days.
    google_indexing_lookback_days: int = 7
    # Hard cap per pipeline run — Indexing API quota is 200 URLs/day per GCP
    # project.
    google_indexing_max_per_run: int = 50

    # ── Distribution: Internet Archive (archive.org) ──────────────────────────
    # S3-like access keys from https://archive.org/account/s3.php
    internet_archive_access_key: str = ""
    internet_archive_secret_key: str = ""
    internet_archive_collection: str = "opensource"
    internet_archive_max_per_run: int = 5

    # ── Distribution: Zenodo (CERN-operated open repository) ─────────────────
    # Generate at https://zenodo.org/account/settings/applications/tokens/new/
    # with scopes `deposit:write` and `deposit:actions`. Leave blank to disable.
    zenodo_access_token: str = ""
    zenodo_use_sandbox: bool = False
    zenodo_community: str = ""
    zenodo_max_per_run: int = 3

    # ── Distribution: OSF Preprints (Open Science Framework) ─────────────────
    # Generate a Personal Access Token at https://osf.io/settings/tokens/ with
    # scope `osf.full_write`. Leave blank to disable.
    osf_access_token: str = ""
    # The OSF "node" (project) GUID — 5-char ID from the URL at osf.io.
    osf_project_node_id: str = ""
    osf_preprint_provider: str = "osf"
    # BePress taxonomy ID: "Social and Behavioral Sciences" → "Economics"
    osf_subject_id: str = "584240da54be81056cecaab4"
    osf_license_name: str = "CC-By Attribution 4.0 International"
    osf_max_per_run: int = 3


settings = Settings()

# Ensure directories exist
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.google_reporting_output_dir.mkdir(parents=True, exist_ok=True)
