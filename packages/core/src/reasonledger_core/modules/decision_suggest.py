"""Where a decision with no working anchor probably belongs.

Two kinds of evidence, both computed from what the repo already says and never from a model:

* **Recorded alongside**: the commit that first added the decision file also changed code, and the
  modules that code sits in are where the decision was made.
* **The old anchor's folder**: an anchor whose file is gone still names a folder, and the files
  still in it say which module that folder became.

Nothing here places anything. A person accepts a suggestion, or picks another module.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.config import HOME_MEDIUM_SHARE, MAX_HOME_SUGGESTIONS
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Manifest
from reasonledger_core.modules.suggest import CoChangeIndex
from reasonledger_core.reasoning.anchors import locus_problem
from reasonledger_core.reasoning.why import locus_file


@dataclass
class HomeSuggestion:
    module: str
    confidence: str = "low"  # high: both kinds agree; medium: one kind, over half; else low
    evidence: list[str] = field(default_factory=list)
    kinds: int = 0
    share: float = 0.0


def _recorded_alongside(
    record: DecisionRecord, history: CoChangeIndex, owner_of: dict[str, str | None]
) -> Counter[str]:
    """Modules of the other files in the commit that first added the decision file."""
    path = f"{DECISIONS_DIR.as_posix()}/{record.frontmatter.id}.md"
    commits = history.commits.get(path)
    if not commits:
        return Counter()
    others = [f for f in commits[-1] if not f.startswith(f"{DECISIONS_DIR.as_posix()}/")]
    return Counter(m for f in others if (m := owner_of.get(f)))


def _old_folder(
    loci: Sequence[str], root: Path, files: Sequence[str], owner_of: dict[str, str | None]
) -> tuple[str, Counter[str]]:
    """Modules of the files still in the nearest folder a dead anchor pointed into."""
    for locus in loci:
        if not locus_problem(root, locus):
            continue
        folder = locus_file(locus).rpartition("/")[0]
        while folder:
            held = [f for f in files if f.startswith(folder + "/")]
            if held:
                return folder, Counter(m for f in held if (m := owner_of.get(f)))
            folder = folder.rpartition("/")[0]
    return "", Counter()


def suggest_homes(
    record: DecisionRecord,
    manifest: Manifest,
    files: Sequence[str],
    root: Path,
    history: CoChangeIndex | None = None,
) -> list[HomeSuggestion]:
    """Up to ``MAX_HOME_SUGGESTIONS`` modules, most likely first; none when nothing points."""
    owner = membership(manifest)
    known = {m.id for m in manifest.modules}
    owner_of = {f: owner.module_of(f) for f in files}
    found: dict[str, HomeSuggestion] = {}

    def add(module: str, share: float, text: str) -> None:
        if module in known:
            hit = found.setdefault(module, HomeSuggestion(module))
            hit.evidence.append(text)
            hit.kinds += 1
            hit.share = max(hit.share, share)

    recorded = _recorded_alongside(record, history, owner_of) if history else Counter()
    total = sum(recorded.values())
    for module, count in recorded.items():
        add(
            module,
            count / total,
            f"recorded in a commit that also changed {count} of {total} files in {module}",
        )
    folder, beside = _old_folder(record.frontmatter.justifies, root, files, owner_of)
    near = sum(beside.values())
    for module, count in beside.items():
        add(
            module,
            count / near,
            f"its anchor in {folder} is gone; {count} of {near} files still there are in {module}",
        )
    for hit in found.values():
        hit.confidence = (
            "high" if hit.kinds >= 2 else "medium" if hit.share >= HOME_MEDIUM_SHARE else "low"
        )
    ranked = sorted(found.values(), key=lambda h: (-h.kinds, -h.share, h.module))
    return ranked[:MAX_HOME_SUGGESTIONS]
