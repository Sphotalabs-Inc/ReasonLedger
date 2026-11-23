"""P0-4 S3: source doc scanner — globs, excludes, determinism."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.importer.scan import commit_sources, scan_docs, scannable_paths


def _write(root: Path, rel: str, text: str = "x") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.phase_3
def test_scan_finds_docs_and_excludes_noise(tmp_path: Path) -> None:
    _write(tmp_path, "claude.md")
    _write(tmp_path, ".cursorrules")
    _write(tmp_path, "docs/adr.md")
    _write(tmp_path, "backend/docs/date-semantics.md")
    _write(tmp_path, "node_modules/pkg/readme.md")
    _write(tmp_path, ".venv/lib/x.md")
    _write(tmp_path, "backend/.ragvenv/site-packages/y.md")

    paths = [source.path for source in scan_docs(tmp_path)]
    assert paths == [
        ".cursorrules",
        "backend/docs/date-semantics.md",
        "claude.md",
        "docs/adr.md",
    ]


@pytest.mark.phase_3
def test_scan_reads_text_and_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "claude.md", "hello world")
    first = scan_docs(tmp_path)
    second = scan_docs(tmp_path)
    assert first == second
    assert first[0].text == "hello world"


@pytest.mark.phase_3
def test_scan_skips_reasonledgers_own_records(tmp_path: Path) -> None:
    """Decision records are markdown; without this the extractor imports its own output."""
    (tmp_path / ".reasonledger" / "decisions").mkdir(parents=True)
    (tmp_path / ".reasonledger" / "proposed").mkdir(parents=True)
    (tmp_path / ".reasonledger" / "decisions" / "dec_abc.md").write_text("UTC", encoding="utf-8")
    (tmp_path / ".reasonledger" / "proposed" / "dec_def.md").write_text("redis", encoding="utf-8")
    (tmp_path / "claude.md").write_text("# Decisions", encoding="utf-8")

    assert [source.path for source in scan_docs(tmp_path)] == ["claude.md"]


@pytest.mark.phase_3
def test_scannable_paths_narrows_a_git_delta(tmp_path: Path) -> None:
    """A raw delta is mostly source files; reporting its size would overstate the gap."""
    assert scannable_paths(
        [
            "docs/arch.md",
            "src/app.py",
            ".reasonledger/state.yml",
            ".reasonledger/proposed/dec_abc.md",
            ".cursorrules",
            "node_modules/pkg/readme.md",
        ]
    ) == [".cursorrules", "docs/arch.md"]


@pytest.mark.phase_3
def test_commit_sources_keep_only_messages_that_explain() -> None:
    """A model call per "fix typo" is money spent to generate junk proposals."""
    explained = (
        "Switch session cache to Redis\n\n"
        "We evaluated Memcached and Redis. Redis wins because we already run it for "
        "queues, and its persistence lets a restart keep warm sessions rather than "
        "stampeding the database on every deploy."
    )
    sources = commit_sources(
        [
            ("a" * 40, "fix typo"),
            ("b" * 40, "bump deps\n\nroutine"),
            ("c" * 40, explained),
        ]
    )

    assert [source.path for source in sources] == ["git:" + "c" * 12]
    assert "Memcached" in sources[0].text


@pytest.mark.phase_3
def test_commit_source_path_is_not_a_file_path() -> None:
    """`git:` marks the origin as history, and keeps it out of any filesystem lookup."""
    body = "Adopt UTC\n\n" + "Because clients span timezones and comparisons must be total. " * 3
    (source,) = commit_sources([("d" * 40, body)])
    assert source.path.startswith("git:")
    assert scannable_paths([source.path]) == []


@pytest.mark.phase_5
def test_person_trailers_never_leave_and_never_count_towards_the_floor() -> None:
    """Co-authored-by and Signed-off-by carry names and emails: author identity, never sent."""
    explained = (
        "Adopt UTC\n\n"
        + "Because clients span timezones and comparisons must be total. " * 3
        + "\n\nCo-Authored-By: Some Agent <agent@example.com>"
        + "\nSigned-off-by: A Person <p@example.com>"
    )
    only_trailers = "Bump deps\n\n" + "Co-authored-by: Some Agent <agent@example.com>\n" * 4

    sources = commit_sources([("e" * 40, explained), ("f" * 40, only_trailers)])

    assert [source.path for source in sources] == ["git:" + "e" * 12]
    assert "example.com" not in sources[0].text and "-by:" not in sources[0].text
    assert sources[0].text.endswith("comparisons must be total.")
