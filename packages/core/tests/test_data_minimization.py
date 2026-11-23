"""Data minimization enforcement tests."""

import pytest
from reasonledger_core.privacy.data_minimization import assert_metadata_only


@pytest.mark.phase_1
def test_rejects_source_code_fields() -> None:
    with pytest.raises(ValueError, match="source code persistence forbidden"):
        assert_metadata_only({"change_id": "c1", "source_code": "print('secret')"})


@pytest.mark.phase_1
def test_allows_metadata_pointers() -> None:
    assert_metadata_only(
        {
            "change_id": "c1",
            "commit_sha": "abc123",
            "evidence_pointer": "Co-Authored-By: Claude",
        }
    )
