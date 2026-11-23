"""Config endpoints for `reasonledger ui` — the UI door onto `.reasonledger/config.yml`.

`reasonledger config` is the other door; both write through the same core functions,
so the two surfaces cannot disagree about what `import` will run.

**No code path here accepts, returns, logs, or persists a raw API key.** The form
collects the env-var *name*; the value is resolved from the environment at call time
and reduced to a boolean before it reaches a response. A request body carrying a
secret-shaped field is refused outright rather than dropped, so a user can never
believe they saved a key that went nowhere. The saved config is built from an explicit
allow-list of the four `ExtractorConfig` fields — request JSON is never validated
straight into the model, which is what keeps an added field from becoming an added
disclosure.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorConfig,
    ExtractorProvider,
    extracted_by_label,
    load_extractor_config,
    parse_extractor_config,
    resolve_api_key,
    write_extractor_config,
)
from reasonledger_core.importer.probe import probe_connection

from reasonledger_cli.config_cmd import PROVIDER_CHOICES, parse_provider

# The four fields the UI may set — mirrors ExtractorConfig, none of which can hold a
# secret. Anything else in a request body is not written.
_ALLOWED_FIELDS = ("provider", "model", "base_url", "api_key_env")

# Refused with 400, never ignored. Normalised so `API-Key`, `apiKey` and `api_key` are
# all the same field to us. `api_key_env` normalises to `apikeyenv` and is unaffected.
_SECRET_FIELDS = frozenset({"apikey", "key", "token", "secret"})

_DISABLED_MESSAGE = "extraction is disabled; configure a provider first"

JsonResponse = tuple[int, dict[str, Any]]


def _normalise(field: str) -> str:
    return field.lower().replace("_", "").replace("-", "")


def _optional_str(body: dict[str, Any], field: str) -> str | None:
    """Read an optional text field, treating blank as unset (as the CLI prompt does)."""
    raw = body.get(field)
    if raw is None:
        return None
    if not isinstance(raw, str):
        msg = f"{field} must be a string"
        raise ValueError(msg)
    return raw.strip() or None


def config_payload(root: Path, config: ExtractorConfig) -> dict[str, Any]:
    """Describe the config for the UI — key *presence* only, never the key.

    ``import_command`` is derived server-side from the saved config so the command the
    user copies records the same extractor identity `catchup` would derive itself.
    """
    return {
        "provider": config.provider.value,
        "model": config.model,
        "base_url": config.base_url,
        "api_key_env": config.api_key_env,
        "api_key_present": resolve_api_key(config) is not None,
        "providers": list(PROVIDER_CHOICES),
        "import_command": (
            f"reasonledger import --root {shlex.quote(str(root))} "
            f"--extracted-by {shlex.quote(extracted_by_label(config))}"
        ),
    }


def handle_get_config(root: Path) -> JsonResponse:
    """GET /api/config — current extractor config; disabled is a valid, quiet state."""
    try:
        config = load_extractor_config(root)
    except ConfigError as exc:
        return 500, {"error": str(exc)}
    return 200, config_payload(root, config)


def handle_post_config(root: Path, body: dict[str, Any]) -> JsonResponse:
    """POST /api/config — persist the four non-secret fields, or refuse the body."""
    for field in body:
        if _normalise(field) in _SECRET_FIELDS:
            return 400, {
                "error": (
                    f"{field!r} is not accepted: ReasonLedger never receives or stores an "
                    "API key. Set api_key_env to the name of an environment variable instead."
                )
            }

    provider_raw = body.get("provider")
    if not isinstance(provider_raw, str) or not provider_raw.strip():
        return 400, {"error": "provider required"}
    try:
        provider = parse_provider(provider_raw.strip())
        values = {field: _optional_str(body, field) for field in _ALLOWED_FIELDS[1:]}
    except ValueError as exc:
        return 400, {"error": str(exc)}

    try:
        config = parse_extractor_config({"provider": provider, **values})
    except ConfigError as exc:
        return 400, {"error": str(exc)}
    path = write_extractor_config(root, config)
    return 200, {"saved": True, "path": str(path), **config_payload(root, config)}


def handle_test_config(root: Path) -> JsonResponse:
    """POST /api/config/test — the one outbound call this server makes, on an explicit click.

    Delegates to `probe_connection`, whose sanitizer strips the resolved key out of any
    provider error before it becomes a response body.
    """
    try:
        config = load_extractor_config(root)
    except ConfigError as exc:
        return 500, {"error": str(exc)}
    if config.provider is ExtractorProvider.DISABLED:
        return 400, {"error": _DISABLED_MESSAGE}
    result = probe_connection(config)
    return 200, {"ok": result.ok, "message": result.message}
