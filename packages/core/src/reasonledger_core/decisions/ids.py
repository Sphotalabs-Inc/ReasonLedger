"""Stable decision id generation."""

from __future__ import annotations

import hashlib
import secrets
import string

DECISION_ID_PREFIX = "dec_"
DECISION_ID_SUFFIX_LEN = 6
CONTENT_ID_HASH_LEN = 12
_ALPHABET = string.ascii_lowercase + string.digits


def generate_decision_id() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(DECISION_ID_SUFFIX_LEN))
    return f"{DECISION_ID_PREFIX}{suffix}"


def _content_decision_id(source_key: str) -> str:
    """Deterministic ``dec_<hash>`` from a stable source key.

    Uses SHA-256 (not the salted builtin ``hash``) so ids are identical across
    runs and processes — the property that makes re-harvest / re-import
    idempotent.
    """
    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:CONTENT_ID_HASH_LEN]
    return f"{DECISION_ID_PREFIX}{digest}"


def harvest_decision_id(source_key: str) -> str:
    """Deterministic id for a harvested PR so re-runs are idempotent."""
    return _content_decision_id(source_key)


def import_decision_id(source_key: str) -> str:
    """Deterministic id for a doc-imported decision so re-imports are idempotent."""
    return _content_decision_id(source_key)


def supersede_decision_id(source_key: str, content_key: str) -> str:
    """Deterministic id for a record that would supersede an earlier import.

    Keyed on the content as well as the source, so a doc that changed under a
    confirmed decision yields an id *distinct* from the record it replaces (both
    must coexist in the ledger), while re-running the same import stays
    idempotent.
    """
    return _content_decision_id(f"{source_key}\x00{content_key}")
