"""Classify contributor identity kind."""

from reasonledger_core.provenance.detectors import KNOWN_BOT_LOGINS

AGENT_LOGIN_MARKERS: tuple[str, ...] = ("devin", "cursor", "codex", "aider")


def contributor_kind(login: str) -> str:
    lowered = login.lower()
    if lowered in KNOWN_BOT_LOGINS or lowered.endswith("[bot]"):
        return "bot"
    if any(marker in lowered for marker in AGENT_LOGIN_MARKERS):
        return "agent"
    return "human"
