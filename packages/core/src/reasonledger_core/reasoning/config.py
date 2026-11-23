"""Named, documented, test-pinned thresholds for reasoning memory.

Output-affecting values live here (per the engineering charter): retrieval
dimensions, conflict-gate thresholds, precision/recall/FPR floors, and severity
bands. Customer-tunable inference endpoints live in ``settings.py`` instead.

``CONFLICT_CONTEXT_SIM_GATE`` and ``CONFLICT_CHOICE_DIVERGENCE_CEILING`` are the
tested *defaults* — what the smoke test below and every bare
``StubConflictClassifier()`` are pinned against. A repo can override them per
its own decision corpus via ``.reasonledger/conflict.yml``
(``reasoning.conflict_config``, ``reasonledger conflict-config``); that override
never changes what these constants mean.
"""

from __future__ import annotations

# --- Embeddings / retrieval ---------------------------------------------------
# All embedders share one vector width (bge-small-en-v1.5 / MiniLM family).
EMBEDDING_DIM = 384
# CI/test default — deterministic hash stub (offline, dependency-free).
EMBEDDING_PROVIDER_DETERMINISTIC = "deterministic"
DETERMINISTIC_MODEL_ID = "rl-deterministic-hash-v1"
# Local default for real use — fastembed + ONNX, optional extra.
EMBEDDING_PROVIDER_LOCAL = "local"
LOCAL_MODEL_ID = "BAAI/bge-small-en-v1.5"
# Back-compat alias for callers that read a single model id constant.
EMBEDDING_MODEL_ID = DETERMINISTIC_MODEL_ID
SEMANTIC_TOP_K = 5
# Similarity below this is treated as "no meaningful match" in retrieval.
SEMANTIC_MIN_SCORE = 0.05

# --- Related-decision shortlist ---------------------------------------------
# Embeddings only find candidates; a judge decides which are conflicts. Each decision
# contributes its SHORTLIST_K nearest neighbours by context similarity, above a floor
# that depends on the embedder because their similarity scales differ.
SHORTLIST_K = 5
SHORTLIST_K_MAX = 50
# Provisional floors. Hash similarity runs low (the old 0.20 conflict gate). The bge
# floor comes from one 40-decision ledger whose top 40 pairs all scored 0.73 to 0.86;
# a remote model's scale is unknown, so its floor is off and k alone bounds the list.
SHORTLIST_MIN_CONTEXT_SIM = {
    DETERMINISTIC_MODEL_ID: 0.20,
    LOCAL_MODEL_ID: 0.60,
}
SHORTLIST_MIN_CONTEXT_SIM_UNKNOWN = 0.0

# --- Conflict detection (deterministic stub classifier, CI) --------------------
# A pair is a conflict only when the two decisions are about the same subject
# (context similarity at/above the gate) AND their chosen approaches actually
# diverge (choice similarity at/below the ceiling). Requiring explicit
# divergence keeps paraphrased *agreements* from being flagged.
CONFLICT_CONTEXT_SIM_GATE = 0.20
CONFLICT_CHOICE_DIVERGENCE_CEILING = 0.35
# Severity bands over the conflict score = context_sim * (1 - choice_sim).
SEVERITY_HIGH_SCORE = 0.45
SEVERITY_MEDIUM_SCORE = 0.25

# --- Conflict smoke thresholds (NOT a quality gate) --------------------------
# The held-out split is 5 pairs (2 positive, 3 negative) in
# fixtures/golden/conflicts/labeled_pairs.json. A precision floor over 2 positives
# establishes nothing statistically: the 95% CI spans almost the whole [0,1] range,
# and these thresholds were tuned against those same ten hand-written pairs.
#
# They are named SMOKE so that neither a CI summary nor a reader mistakes a green
# run for measured quality. Rename them back to *_FLOOR only when the labelled set
# has grown ~100x and the split is genuinely held out from threshold tuning.
CONFLICT_SMOKE_PRECISION_MIN = 0.80
CONFLICT_SMOKE_RECALL_MIN = 0.80
CONFLICT_SMOKE_FALSE_POSITIVE_MAX = 0.20

# --- Judge smoke thresholds (NOT a quality gate) ------------------------------
# Scored on 22 hand-labelled pairs (fixtures/golden/conflicts/judge_pairs.json)
# against verdicts recorded once from a real model. Same caveat as above: far too
# few pairs to measure quality; they catch a judge that broke, not one that is good.
JUDGE_SMOKE_PRECISION_MIN = 0.80
JUDGE_SMOKE_RECALL_MIN = 0.80
JUDGE_SMOKE_FALSE_POSITIVE_MAX = 0.10

# --- Watchers -----------------------------------------------------------------
# Fraction of the threshold within which a still-satisfied condition is flagged
# "drifting" (early warning before it breaches to "stale").
WATCHER_DRIFT_MARGIN = 0.10
