"""Policy-as-code domain types."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from reasonledger_core.models.oversight import OversightClassification
from reasonledger_core.models.provenance import ProvenanceStatus


class ViolationAction(StrEnum):
    FAIL = "fail"
    WARN = "warn"


class RuleOutcome(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


class CheckOutcome(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class _StrictModel(BaseModel):
    """A policy gate must never silently ignore a condition it does not understand."""

    model_config = ConfigDict(extra="forbid")


class PolicyWhen(_StrictModel):
    """Conditions that select which changes a rule applies to."""

    provenance: ProvenanceStatus | None = None
    paths: list[str] = Field(default_factory=list)


class PolicyRequire(_StrictModel):
    """Requirements that must hold when a rule matches."""

    oversight: OversightClassification | None = None
    approver: Literal["codeowner"] | None = None
    approver_not: Literal["author"] | None = None


class PolicyRule(_StrictModel):
    id: str
    when: PolicyWhen = Field(default_factory=PolicyWhen)
    require: PolicyRequire = Field(default_factory=PolicyRequire)
    on_violation: ViolationAction = ViolationAction.WARN


class PolicyDocument(_StrictModel):
    rules: list[PolicyRule] = Field(default_factory=list)
    version: str | None = None


class ChangePolicyContext(BaseModel):
    """Facts about a change used to evaluate policy rules."""

    provenance: ProvenanceStatus
    oversight: OversightClassification
    changed_paths: list[str] = Field(default_factory=list)
    author_login: str
    approver_logins: list[str] = Field(default_factory=list)
    codeowner_logins: list[str] = Field(default_factory=list)


class RuleEvaluation(BaseModel):
    rule_id: str
    matched: bool
    result: RuleOutcome
    explanation: str


class PolicyEvaluationResult(BaseModel):
    overall: CheckOutcome
    rules: list[RuleEvaluation]
