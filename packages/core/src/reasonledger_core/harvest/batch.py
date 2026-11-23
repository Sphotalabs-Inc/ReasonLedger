"""Batch PR harvest — write idempotent decision records to the app repo."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    read_decision_file,
    render_decision_markdown,
    write_decision_file,
)
from reasonledger_core.harvest.deterministic import harvest_decision_from_pr
from reasonledger_core.privacy.pii_linter import PiiLintError, lint_decision_text
from reasonledger_core.repo_files import contained_dir


@dataclass(frozen=True)
class PrHarvestInput:
    source_key: str
    pr_title: str
    pr_body: str = ""
    diff_text: str = ""


@dataclass
class HarvestResult:
    created: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    skipped_pii: list[str] = field(default_factory=list)


def harvest_pull_requests(
    prs: Iterable[PrHarvestInput],
    *,
    root: Path,
    decisions_dir: Path | None = None,
) -> HarvestResult:
    """Harvest merged PRs into `.reasonledger/decisions/` (idempotent)."""
    target_dir = contained_dir(root, decisions_dir or DECISIONS_DIR)
    result = HarvestResult()

    for pr in prs:
        record = harvest_decision_from_pr(
            pr_title=pr.pr_title,
            pr_body=pr.pr_body,
            diff_text=pr.diff_text,
            source_key=pr.source_key,
        )
        try:
            lint_decision_text(record)
        except PiiLintError:
            result.skipped_pii.append(pr.source_key)
            continue

        target_path = target_dir / decision_filename(record.frontmatter.id)
        if target_path.is_file():
            existing = read_decision_file(target_path)
            # A rerun is not a new recording: keep the first date (or its absence) so an
            # unchanged PR stays unchanged and an old file is not backfilled.
            record.frontmatter.recorded_at = existing.frontmatter.recorded_at
            rendered = render_decision_markdown(record)
            if render_decision_markdown(existing) == rendered:
                result.skipped_unchanged += 1
                continue
            write_decision_file(target_path, record)
            result.updated += 1
            continue

        write_decision_file(target_path, record)
        result.created += 1

    return result
