"""P0-4 S2: import_decision_id — deterministic, idempotent, salt-free."""

from __future__ import annotations

import hashlib

import pytest
from reasonledger_core.decisions.ids import harvest_decision_id, import_decision_id


@pytest.mark.phase_3
def test_import_decision_id_deterministic() -> None:
    key = "acme/docs#claude.md#architecture"
    first = import_decision_id(key)
    second = import_decision_id(key)
    assert first == second
    assert first.startswith("dec_")
    # Pinned to SHA-256 (salt-free) so ids are stable across runs AND processes,
    # which is what makes re-import idempotent.
    expected = "dec_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    assert first == expected


@pytest.mark.phase_3
def test_import_decision_id_distinct_keys() -> None:
    assert import_decision_id("acme/docs#a") != import_decision_id("acme/docs#b")


@pytest.mark.phase_3
def test_import_and_harvest_ids_share_formula() -> None:
    # Same stable source key yields the same id regardless of entry point;
    # in practice harvest ("repo#pr") and import ("path#anchor") key spaces
    # never collide.
    key = "acme/thing#same"
    assert import_decision_id(key) == harvest_decision_id(key)
