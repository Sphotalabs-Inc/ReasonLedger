"""Aggregate provenance findings into a provenance status."""

from reasonledger_core.models.provenance import (
    ChangeProvenanceInput,
    ProvenanceFinding,
    ProvenanceStatus,
    SignalConfidence,
)
from reasonledger_core.provenance.detectors import detect_provenance_signals


def classify_provenance(
    change: ChangeProvenanceInput,
    findings: list[ProvenanceFinding] | None = None,
) -> tuple[ProvenanceStatus, list[ProvenanceFinding]]:
    """Classify provenance from findings or by running detectors."""
    resolved_findings = findings if findings is not None else detect_provenance_signals(change)
    if not resolved_findings:
        if _has_insufficient_data(change):
            return ProvenanceStatus.UNKNOWN, resolved_findings
        return ProvenanceStatus.HUMAN, resolved_findings

    has_strong = any(f.confidence == SignalConfidence.STRONG for f in resolved_findings)
    if has_strong:
        return ProvenanceStatus.AI_ASSISTED, resolved_findings
    return ProvenanceStatus.LIKELY_AI, resolved_findings


def _has_insufficient_data(change: ChangeProvenanceInput) -> bool:
    """Treat empty inputs as unknown rather than falsely human."""
    return not any(
        [
            change.commit_message,
            change.commit_author_login,
            change.commit_committer_login,
            change.pr_author_login,
            change.pr_labels,
            change.branch_name,
            change.diff_hunks,
        ]
    )
