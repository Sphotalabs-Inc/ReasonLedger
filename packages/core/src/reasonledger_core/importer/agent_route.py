"""The agent route for backfill: the coding agent extracts proposals over MCP.

``import_task`` names the documents and commit messages the scan already accepts.
Document bodies stay in the files the agent can open. A commit message is included
because it is not a file. ``submit_candidates`` validates what comes back and writes
proposals through the same gate as ``reasonledger import``. Nothing here calls a model.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.outgoing import repo_text_sources
from reasonledger_core.importer.prompt import EXTRACTION_SYSTEM_PROMPT
from reasonledger_core.importer.propose import ImportResult, propose_decisions
from reasonledger_core.importer.scan import COMMIT_PATH_PREFIX, ImportSource

SEEN_PATH = Path(".reasonledger/import-seen.yml")
DEFAULT_BATCH = 8
MAX_BATCH = 20
_SEEN_KEY = "import_seen"

_ANSWER = (
    "\nRead each document at its path yourself. Do not read source code. A commit source "
    "includes its message and has no file to open. Extract only real decisions. "
    "Answer by calling submit_candidates(candidates, extracted_by, covered). "
    "candidates is a list of {context, choice, source_ref, alternatives_rejected, "
    'assumptions, justifies, confidence}. source_ref is "<path>#<topic>" using the path '
    "exactly as given. covered is every path from this task, including a path that contains "
    "no decision. extracted_by is your tool and model, for example cursor/grok-4.7. "
    "Call get_import_task again for the next batch. These are proposals: do not approve them. "
    "After every submit_candidates, tell the user in one plain line what the result's summary "
    "says, including when no decision was found, so a quiet batch is never mistaken for a "
    "stalled import."
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_seen(root: Path) -> dict[str, str]:
    path = root / SEEN_PATH
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    section = data.get(_SEEN_KEY, {}) if isinstance(data, dict) else {}
    if not isinstance(section, dict):
        return {}
    return {str(key): str(value) for key, value in section.items()}


def _save_seen(root: Path, seen: Mapping[str, str]) -> None:
    path = root / SEEN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {_SEEN_KEY: dict(sorted(seen.items()))}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _pending(root: Path) -> list[ImportSource]:
    seen = _load_seen(root)
    return [
        source
        for source in repo_text_sources(root)
        if seen.get(source.path) != _digest(source.text)
    ]


def _source_path(source_ref: str) -> str:
    return source_ref.split("#", 1)[0]


def import_task(root: Path, *, limit: int = DEFAULT_BATCH) -> dict[str, Any]:
    """The next batch of sources to read, and how many are still unseen."""
    batch_size = max(1, min(limit, MAX_BATCH))
    total = len(repo_text_sources(root))
    pending = _pending(root)
    batch = pending[:batch_size]
    sources: list[dict[str, str]] = []
    for source in batch:
        kind = "commit" if source.path.startswith(COMMIT_PATH_PREFIX) else "doc"
        item = {"path": source.path, "kind": kind}
        if kind == "commit":
            item["text"] = source.text
        sources.append(item)
    return {
        "instructions": EXTRACTION_SYSTEM_PROMPT + _ANSWER,
        "sources": sources,
        "returned": len(sources),
        "pending": len(pending),
        "total": total,
        "done": total - len(pending),
    }


def _summary(read: int, result: ImportResult, rejected: int, remaining: int) -> str:
    """One line the agent relays to the user, so a batch with no decisions is not silent."""
    proposals = result.created + result.updated
    found = f"{proposals} proposal(s) staged" if proposals else "no decisions found in them"
    parts = [f"Read {read} source(s): {found}."]
    if rejected:
        parts.append(f"{rejected} candidate(s) were rejected; fix the source_ref and resubmit.")
    if remaining:
        parts.append(
            f"{remaining} source(s) still unread; call get_import_task for the next batch."
        )
    else:
        parts.append("Nothing left to read. Review any proposals in `reasonledger ui`.")
    return " ".join(parts)


def _strings(value: object) -> object:
    if not isinstance(value, list):
        return value
    return [str(item) for item in value]


def _candidate(entry: Mapping[str, Any], source_ref: str) -> DecisionCandidate:
    return DecisionCandidate.model_validate(
        {
            "context": entry.get("context"),
            "choice": entry.get("choice"),
            "source_ref": source_ref,
            "alternatives_rejected": _strings(entry.get("alternatives_rejected") or []),
            "assumptions": _strings(entry.get("assumptions") or []),
            "justifies": _strings(entry.get("justifies") or []),
            "confidence": entry.get("confidence"),
        }
    )


def submit_candidates(
    root: Path,
    candidates: Sequence[Mapping[str, Any]],
    extracted_by: str,
    covered: Sequence[str] | None = None,
    *,
    extracted_at: datetime | None = None,
) -> dict[str, Any]:
    """Write an agent's extractions as proposals and remember the sources it finished.

    A source stays in the next task when one of its candidates was rejected, so a bad
    ``source_ref`` can be corrected. A source the agent covered and that validated is
    remembered by a hash of its text, and comes back only when that text changes.
    """
    extracted_by = extracted_by.strip()
    if not extracted_by:
        return {"ok": False, "error": "extracted_by is required", "created": 0, "rejected": []}
    known = {source.path: source for source in repo_text_sources(root)}
    accepted: list[DecisionCandidate] = []
    rejected: list[str] = []
    rejected_paths: set[str] = set()
    for entry in candidates:
        source_ref = str(entry.get("source_ref") or "")
        path = _source_path(source_ref)
        label = source_ref or "(missing source_ref)"
        if "#" not in source_ref or path not in known:
            rejected.append(f"{label}: source_ref must be <path>#<topic> for a source in the task")
            if path in known:
                rejected_paths.add(path)
            continue
        try:
            accepted.append(_candidate(entry, source_ref))
        except ValidationError as exc:
            rejected.append(f"{label}: invalid candidate ({exc.errors()[0]['loc']})")
            rejected_paths.add(path)
    when = extracted_at or datetime.now(UTC)
    result = (
        propose_decisions(accepted, root=root, extracted_by=extracted_by, extracted_at=when)
        if accepted
        else ImportResult()
    )
    finished = {path for path in (covered or ()) if path in known and path not in rejected_paths}
    finished.update(
        _source_path(candidate.source_ref)
        for candidate in accepted
        if _source_path(candidate.source_ref) not in rejected_paths
    )
    if finished:
        seen = _load_seen(root)
        for path in finished:
            seen[path] = _digest(known[path].text)
        _save_seen(root, seen)
    remaining = len(_pending(root))
    return {
        "ok": True,
        "summary": _summary(len(finished), result, len(rejected), remaining),
        "created": result.created,
        "updated": result.updated,
        "skipped_unchanged": result.skipped_unchanged,
        "skipped_confirmed": result.skipped_confirmed,
        "skipped_pii": result.skipped_pii,
        "proposed_ids": result.proposed_ids,
        "rejected": rejected,
        "remaining": remaining,
    }
