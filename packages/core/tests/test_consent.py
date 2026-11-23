"""Phase 5 — consent to send repo data to a model that is off this machine."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.consent import (
    ConsentError,
    DataClass,
    consent_dir,
    destination,
    grant,
    granted_classes,
    missing_classes,
    parse_classes,
    repo_key,
    revoke,
)
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider

WHEN = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
LOCAL = ExtractorConfig(
    provider=ExtractorProvider.LOCAL, base_url="http://localhost:11434", model="llama3.1"
)
CLOUD = ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-5")
GATEWAY = ExtractorConfig(
    provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="https://llm.example.com/v1", model="m"
)


@pytest.mark.phase_5
def test_a_model_on_this_machine_or_no_model_needs_no_consent(tmp_path: Path) -> None:
    for config in (ExtractorConfig(), LOCAL):
        assert destination(config) is None
        assert missing_classes(tmp_path, config, list(DataClass)) == []


@pytest.mark.phase_5
def test_destination_names_the_origin_that_receives_the_prompt() -> None:
    assert destination(CLOUD) == "https://api.anthropic.com"
    assert destination(GATEWAY) == "https://llm.example.com"


@pytest.mark.phase_5
def test_nothing_is_granted_by_default_and_a_grant_covers_only_what_was_named(
    tmp_path: Path,
) -> None:
    assert missing_classes(tmp_path, CLOUD, [DataClass.PATHS]) == [DataClass.PATHS]

    grant(tmp_path, CLOUD, [DataClass.PATHS], now=WHEN)

    assert missing_classes(tmp_path, CLOUD, [DataClass.PATHS]) == []
    assert missing_classes(tmp_path, CLOUD, [DataClass.PATHS, DataClass.DECISION_TEXT]) == [
        DataClass.DECISION_TEXT
    ]
    assert granted_classes(tmp_path, CLOUD) == {DataClass.PATHS}


@pytest.mark.phase_5
def test_a_grant_does_not_follow_the_repo_to_a_different_destination(tmp_path: Path) -> None:
    grant(tmp_path, CLOUD, [DataClass.DECISION_TEXT], now=WHEN)
    assert missing_classes(tmp_path, GATEWAY, [DataClass.DECISION_TEXT]) == [
        DataClass.DECISION_TEXT
    ]


@pytest.mark.phase_5
def test_revoke_takes_effect_at_once_for_named_classes_or_everything(tmp_path: Path) -> None:
    grant(tmp_path, CLOUD, list(DataClass), now=WHEN)
    revoke(tmp_path, [DataClass.PATHS])
    assert granted_classes(tmp_path, CLOUD) == {DataClass.DECISION_TEXT, DataClass.REPO_TEXT}
    revoke(tmp_path)
    assert granted_classes(tmp_path, CLOUD) == set()


@pytest.mark.phase_5
def test_each_repo_has_its_own_grants(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    grant(first, CLOUD, [DataClass.PATHS], now=WHEN)
    assert missing_classes(second, CLOUD, [DataClass.PATHS]) == [DataClass.PATHS]


@pytest.mark.phase_5
def test_granting_for_a_model_on_this_machine_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConsentError):
        grant(tmp_path, LOCAL, [DataClass.PATHS])


@pytest.mark.phase_5
def test_an_unknown_class_names_the_valid_ones() -> None:
    with pytest.raises(ConsentError, match="decision_text"):
        parse_classes(["everything"])


@pytest.mark.phase_5
def test_an_unreadable_consent_file_grants_nothing(tmp_path: Path) -> None:
    grant(tmp_path, CLOUD, [DataClass.PATHS], now=WHEN)
    (consent_dir() / "consent.yml").write_text(": : not yaml [", encoding="utf-8")
    assert missing_classes(tmp_path, CLOUD, [DataClass.PATHS]) == [DataClass.PATHS]


@pytest.mark.phase_5
def test_the_consent_file_never_lands_in_the_repo(tmp_path: Path) -> None:
    grant(tmp_path, CLOUD, [DataClass.PATHS], now=WHEN)
    assert not any(tmp_path.rglob("consent.yml"))
    assert (consent_dir() / "consent.yml").is_file()
    assert repo_key(tmp_path) == str(tmp_path.resolve())  # not a git repo: keyed by path
