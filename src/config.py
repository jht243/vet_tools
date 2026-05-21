from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    database_url: str = "sqlite:///./ban_the_bots.db"
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
    # Cheaper model used for short, prose-only generation tasks where the
    # facts are already structured. Keeps cost trivial: ~$0.0002/page at
    # gpt-4o-mini pricing, cached by content fingerprint so reruns are free.
    openai_narrative_model: str = "gpt-4o-mini"
    analysis_min_relevance: int = 5
    report_lookback_days: int = 120
    # Hard cap on LLM calls per pipeline run. Default 200 calls/run
    # ≈ ~$1.20 at current gpt-4o pricing. Override via LLM_CALL_BUDGET_PER_RUN.
    llm_call_budget_per_run: int = 200
    llm_input_price_per_mtok: float = 2.50
    llm_output_price_per_mtok: float = 10.00

    # Premium model — used ONLY for evergreen, high-traffic landing content
    # (pillar page, industry pages, evergreen explainers).
    openai_premium_model: str = "gpt-5.2"
    llm_premium_input_price_per_mtok: float = 5.00
    llm_premium_output_price_per_mtok: float = 15.00

    # Newsletter
    newsletter_provider: str = "console"
    newsletter_from_email: str = "briefing@banthebots.org"
    newsletter_api_key: str = ""
    subscriber_list_path: str = "subscribers.json"
    seo_email_provider: str = "resend"
    seo_email_recipient: str = "<RECIPIENT_EMAIL>"
    seo_email_subject: str = "Ban the Bots — Daily SEO"
    resend_api_key: str = ""

    # GA4 Measurement Protocol (server-side events, e.g. purchase)
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

    # Supabase Storage
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_report_bucket: str = "reports"
    supabase_report_object_key: str = "report.html"
    lead_magnet_bucket: str = "lead-magnets"

    # Server
    server_port: int = 8080

    # ── Admin endpoints ────────────────────────────────────────────────
    # Bearer token for /admin/* routes. Leave blank to disable entirely.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    admin_token: str = ""

    # SEO / canonical URL
    site_url: str = "https://banthebots.org"
    site_name: str = "Ban the Bots"
    site_owner_org: str = "Ban the Bots"
    site_locale: str = "en_US"

    @property
    def canonical_site_url(self) -> str:
        """Customer-facing base URL (emails, sitemap entries, JSON-LD identifiers).

        Render and other hosts may set SITE_URL to a *.onrender.com hostname.
        We always prefer the live bare domain.
        """
        u = (self.site_url or "").strip().rstrip("/")
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        lower = u.lower()
        if (
            not u
            or "onrender.com" in lower
            or lower in {"https://www.banthebots.org", "http://www.banthebots.org"}
        ):
            return "https://banthebots.org"
        return u

    # Long-form blog post generator. Each post is roughly 700-900 words.
    # An LLM curation call picks the best 10 from all candidates each run.
    blog_gen_budget_per_run: int = 10
    blog_gen_min_relevance: int = 5
    blog_gen_lookback_days: int = 14
    blog_gen_max_words: int = 900

    # ── Google News intake cap ─────────────────────────────────────────
    # Allow more articles in so the LLM curator has a good pool to choose
    # from across all scrapers. Hard daily briefing cap is blog_gen_budget_per_run.
    google_news_daily_cap: int = 20

    # ── AI Incidents ───────────────────────────────────────────────────
    ai_incidents_daily_cap: int = 20
    ai_risk_snapshot_days: int = 90

    # ── SEO: Semrush API ──────────────────────────────────────────────
    semrush_api_key: str = ""
    semrush_database: str = "us"

    # ── Distribution: IndexNow (Bing, Yandex, Seznam, Naver, Mojeek) ──
    indexnow_key: str = "0b2fff2a4cb56ba2c10382745f51cdd8"

    # ── Distribution: Google Indexing API ──────────────────────────────
    google_indexing_sa_json: str = ""
    google_indexing_sa_file: str = ""
    google_indexing_lookback_days: int = 7
    google_indexing_max_per_run: int = 50


settings = Settings()

# Ensure directories exist
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.google_reporting_output_dir.mkdir(parents=True, exist_ok=True)
