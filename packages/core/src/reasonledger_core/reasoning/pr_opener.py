"""PROpener port + a recording (sandbox) implementation.

The same port drives a real GitHub PR in production; CI/sandbox uses the
recording opener so the watcher pipeline stays deterministic and offline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from reasonledger_core.models.reasoning import PullRequestDraft, PullRequestRef


@runtime_checkable
class PROpener(Protocol):
    def open_pr(self, draft: PullRequestDraft) -> PullRequestRef: ...


class RecordingPROpener:
    """Records PR intents without touching a VCS — deterministic for tests."""

    def __init__(self) -> None:
        self.opened: list[PullRequestRef] = []

    def open_pr(self, draft: PullRequestDraft) -> PullRequestRef:
        number = len(self.opened) + 1
        ref = PullRequestRef(
            number=number,
            url=f"sandbox://pr/{draft.decision_id}/{number}",
            draft=draft,
        )
        self.opened.append(ref)
        return ref
