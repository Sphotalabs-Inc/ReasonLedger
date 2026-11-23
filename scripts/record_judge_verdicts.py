"""Record a real model's verdicts on the hand-labelled judge pairs, for CI to replay.

CI never calls a model. This script is run by hand, once per prompt or model change,
against a repo whose `.reasonledger/config.yml` names the model (`reasonledger
config`). It writes fixtures/golden/conflicts/judge_verdicts.json in the format
`ReplayConflictClassifier` reads, and prints how the verdicts agree with the labels.

    uv run python scripts/record_judge_verdicts.py --root /path/to/configured/repo
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reasonledger_core.importer.config import load_extractor_config
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.reasoning.judge import agreement, build_model_judge

CONFLICTS = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "conflicts"
PAIRS = CONFLICTS / "judge_pairs.json"
VERDICTS = CONFLICTS / "judge_verdicts.json"


def _record(spec: dict[str, Any]) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=spec["id"],
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            context=spec["context"],
            choice=spec["choice"],
        ),
        body="",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, required=True, help="Repo with a configured model")
    parser.add_argument("--model", default=None, help="Override the configured model")
    args = parser.parse_args(argv)

    judge = build_model_judge(load_extractor_config(args.root), model=args.model)
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))["pairs"]
    rows: list[dict[str, Any]] = []
    predictions: list[tuple[bool, bool]] = []
    for pair in pairs:
        answer = judge.judge(_record(pair["a"]), _record(pair["b"]))
        predictions.append((answer.is_conflict, bool(pair["is_conflict"])))
        mark = "ok " if answer.is_conflict == pair["is_conflict"] else "MISS"
        print(f"{mark} {pair['id']}: judged {'conflict' if answer.is_conflict else 'not'}")
        rows.append(
            {
                "pair_id": pair["id"],
                "decision_a": pair["a"]["id"],
                "decision_b": pair["b"]["id"],
                "is_conflict": answer.is_conflict,
                "severity": answer.severity.value,
                "explanation": answer.to_verdict(score=1.0).explanation,
                "score": 1.0 if answer.is_conflict else 0.0,
            }
        )

    VERDICTS.write_text(
        json.dumps(
            {
                "model": judge.model,
                "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "pairs": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    precision, recall, fpr = agreement(predictions)
    print(f"precision {precision:.2f}  recall {recall:.2f}  false-positive rate {fpr:.2f}")
    print(f"wrote {VERDICTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
