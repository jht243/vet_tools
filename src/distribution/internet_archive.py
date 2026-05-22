"""Internet Archive (archive.org) client stub — reserved for future use."""
from __future__ import annotations
import logging
from src.config import settings

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(settings.internet_archive_access_key and settings.internet_archive_secret_key)
