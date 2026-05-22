"""Zenodo (CERN) client stub — reserved for future use."""
from __future__ import annotations
import logging
from src.config import settings

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(settings.zenodo_access_token)
