"""Google Indexing API client."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Optional
import httpx
from src.config import settings

logger = logging.getLogger(__name__)
_INDEXING_SCOPE = "https://www.googleapis.com/auth/indexing"
_INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

@dataclass
class IndexingResult:
    success: bool
    status_code: int | None
    response_snippet: str

def is_enabled() -> bool:
    return bool(settings.google_indexing_sa_json or settings.google_indexing_sa_file)

def _load_sa_credentials():
    from google.oauth2 import service_account
    raw = (settings.google_indexing_sa_json or "").strip()
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=[_INDEXING_SCOPE])
    path = (settings.google_indexing_sa_file or "").strip()
    if path:
        return service_account.Credentials.from_service_account_file(path, scopes=[_INDEXING_SCOPE])
    return None

class GoogleIndexingClient:
    def __init__(self, credentials):
        self._creds = credentials

    def _get_token(self) -> str:
        import google.auth.transport.requests
        req = google.auth.transport.requests.Request()
        if not self._creds.valid:
            self._creds.refresh(req)
        return self._creds.token

    def publish_url_updated(self, url: str) -> IndexingResult:
        try:
            token = self._get_token()
            resp = httpx.post(
                _INDEXING_ENDPOINT,
                json={"url": url, "type": "URL_UPDATED"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=20,
            )
            snippet = (resp.text or "")[:300]
            success = resp.status_code in (200, 204)
            if success:
                logger.info("Google Indexing: pinged %s", url)
            else:
                logger.warning("Google Indexing: %d for %s: %s", resp.status_code, url, snippet)
            return IndexingResult(success=success, status_code=resp.status_code, response_snippet=snippet)
        except Exception as exc:
            logger.error("Google Indexing error for %s: %s", url, exc)
            return IndexingResult(success=False, status_code=None, response_snippet=str(exc)[:300])

def get_client() -> Optional[GoogleIndexingClient]:
    if not is_enabled():
        return None
    try:
        creds = _load_sa_credentials()
        if creds is None:
            return None
        return GoogleIndexingClient(creds)
    except Exception as exc:
        logger.error("Could not load Google Indexing credentials: %s", exc)
        return None
