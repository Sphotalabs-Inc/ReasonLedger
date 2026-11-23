"""`reasonledger ui` — "Check for conflicts": the judge, started by a person's click.

The one place the UI server calls a model about decisions, and only when asked: loading a
page never starts it. It is the same run as `reasonledger judge` (same queue, same verdict
file, saved pair by pair), on a background thread so the page can show progress and stop
it. Before anything is sent it checks what the command checks: a model is configured, and
a model off this machine has consent for decision text. The UI cannot grant that consent
here; the person does it in Settings.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from reasonledger_core.consent import DataClass, destination, missing_classes
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.llm import LlmError
from reasonledger_core.models.reasoning import Relation
from reasonledger_core.reasoning import CachingEmbedder
from reasonledger_core.reasoning.conflict_config import (
    effective_conflict_config,
    resolve_conflict_embedder_with_status,
)
from reasonledger_core.reasoning.dismissals import pair_key
from reasonledger_core.reasoning.judge import (
    ModelJudge,
    build_model_judge,
    judge_pending,
    pending_pairs,
)
from reasonledger_core.reasoning.related import Candidate
from reasonledger_core.reasoning.verdicts import VerdictsError

JsonResponse = tuple[int, dict[str, Any]]
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409

JudgeBuilder = Callable[[ExtractorConfig, str | None], ModelJudge]


def _default_builder(config: ExtractorConfig, model: str | None) -> ModelJudge:
    return build_model_judge(config, model=model)


@dataclass
class _Progress:
    """What the page shows.

    ``state`` is idle, running, stopping (asked to stop; the pair in flight is finishing),
    finished, stopped or failed. ``current`` is the pair being compared right now.
    """

    state: str = "idle"
    total: int = 0
    checked: int = 0
    conflicts: int = 0
    compatible: int = 0
    failed: int = 0
    model: str | None = None
    error: str | None = None
    current: list[str] | None = None


class JudgeSession:
    """One judge run at a time for the life of the UI server."""

    def __init__(self, root: Path, *, build_judge: JudgeBuilder = _default_builder) -> None:
        self._root = root
        self._build_judge = build_judge
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._progress = _Progress()

    def get(self) -> JsonResponse:
        with self._lock:
            return HTTP_OK, asdict(self._progress)

    def post(self, action: str, body: dict[str, Any]) -> JsonResponse:
        if action == "start":
            return self._start(body)
        if action == "stop":
            self._stop.set()
            with self._lock:
                # Said at once: the model call in flight cannot be cancelled and may take a while.
                if self._progress.state == "running":
                    self._progress.state = "stopping"
            return self.get()
        return HTTP_NOT_FOUND, {"error": "not found"}

    def wait(self, timeout: float) -> None:
        """Block until the run in flight, if any, has ended (tests; the page polls)."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _refusal(self, config: ExtractorConfig) -> JsonResponse | None:
        """Why nothing may be sent yet, with ``need`` naming what the person must do."""
        if config.provider is ExtractorProvider.DISABLED:
            return HTTP_CONFLICT, {
                "error": "No model is configured. Choose one in Settings, or ask your "
                "coding agent to check the pairs.",
                "need": "model",
            }
        if missing_classes(self._root, config, [DataClass.DECISION_TEXT]):
            return HTTP_CONFLICT, {
                "error": f"Checking sends decision text to {destination(config)}, which is off "
                "your machine. Allow it in Settings first.",
                "need": "consent",
            }
        return None

    def _start(self, body: dict[str, Any]) -> JsonResponse:
        pair = body.get("pair")
        only: str | None = None
        if pair is not None:
            if not (
                isinstance(pair, list) and len(pair) == 2 and all(isinstance(i, str) for i in pair)
            ):
                return HTTP_BAD_REQUEST, {"error": "pair must be two decision ids"}
            only = pair_key(pair[0], pair[1])
        with self._lock:
            if self._progress.state in {"running", "stopping"}:
                return HTTP_CONFLICT, {"error": "A check is already running."}
            try:
                config = load_extractor_config(self._root)
            except ConfigError as exc:
                return HTTP_BAD_REQUEST, {"error": str(exc)}
            refusal = self._refusal(config)
            if refusal is not None:
                return refusal
            try:
                judge = self._build_judge(config, effective_conflict_config(self._root).judge_model)
            except LlmError as exc:
                return HTTP_BAD_REQUEST, {"error": str(exc)}
            self._stop.clear()
            self._progress = _Progress(state="running", model=judge.model)
            self._thread = threading.Thread(target=self._run, args=(judge, only), daemon=True)
            self._thread.start()
            return HTTP_OK, asdict(self._progress)

    def _before(self, candidate: Candidate) -> bool:
        """Name the pair about to be sent, unless the person asked to stop."""
        if self._stop.is_set():
            return False
        with self._lock:
            self._progress.current = [candidate.a.frontmatter.id, candidate.b.frontmatter.id]
        return True

    def _on_result(self, _candidate: Candidate, relation: Relation | None, _note: str) -> None:
        with self._lock:
            self._progress.checked += 1
            if relation is None:
                self._progress.failed += 1
            elif relation is Relation.CONFLICT:
                self._progress.conflicts += 1
            else:
                self._progress.compatible += 1

    def _run(self, judge: ModelJudge, only: str | None) -> None:
        try:
            embedder, _status = resolve_conflict_embedder_with_status(self._root)
            cached = CachingEmbedder(embedder, root=self._root)
            total = 1 if only else len(pending_pairs(self._root, embedder=cached).pending)
            with self._lock:
                self._progress.total = total
            judge_pending(
                self._root,
                judge=judge,
                embedder=cached,
                only=only,
                before_each=self._before,
                on_result=self._on_result,
            )
        except (VerdictsError, OSError, ValueError) as exc:
            with self._lock:
                self._progress.state = "failed"
                self._progress.error = str(exc)
                self._progress.current = None
            return
        with self._lock:
            self._progress.state = "stopped" if self._stop.is_set() else "finished"
            self._progress.current = None
