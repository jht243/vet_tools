"""OSF Preprints client stub — reserved for future use."""
from __future__ import annotations
import logging
from src.config import settings

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(settings.osf_access_token and settings.osf_project_node_id)
