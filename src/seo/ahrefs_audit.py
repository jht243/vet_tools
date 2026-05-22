"""Ahrefs API stub — extend when Ahrefs subscription is active."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def run_ahrefs_audit() -> dict:
    logger.info("ahrefs_audit: stub — configure AHREFS_API_KEY to enable")
    return {"status": "skipped", "reason": "stub"}
