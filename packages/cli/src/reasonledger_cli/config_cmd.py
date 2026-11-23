"""`reasonledger config` — BYOM extractor configuration (no secrets on disk)."""

from __future__ import annotations

import sys
from pathlib import Path

from reasonledger_core.importer.config import (
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
    parse_extractor_config,
    write_extractor_config,
)
from reasonledger_core.importer.probe import probe_connection

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

PROVIDER_CHOICES = [p.value for p in ExtractorProvider if p is not ExtractorProvider.DISABLED]


def parse_provider(raw: str) -> ExtractorProvider:
    try:
        return ExtractorProvider(raw)
    except ValueError as exc:
        choices = ", ".join(PROVIDER_CHOICES)
        raise ValueError(f"unsupported provider {raw!r}; choose from: {choices}") from exc


def _prompt_choice(label: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _prompt_provider() -> ExtractorProvider:
    print("Select extractor provider:")
    for index, value in enumerate(PROVIDER_CHOICES, start=1):
        print(f"  {index}. {value}")
    while True:
        choice = _prompt_choice("Provider", default="1")
        if choice.isdigit() and 1 <= int(choice) <= len(PROVIDER_CHOICES):
            return ExtractorProvider(PROVIDER_CHOICES[int(choice) - 1])
        if choice in PROVIDER_CHOICES:
            return ExtractorProvider(choice)
        print("Invalid choice — try again.")


def _interactive_config() -> ExtractorConfig:
    provider = _prompt_provider()
    model = _prompt_choice("Model")
    base_url = _prompt_choice("Base URL (optional)")
    api_key_env = _prompt_choice("API key env var name (optional)")
    return parse_extractor_config(
        {
            "provider": provider,
            "model": model or None,
            "base_url": base_url or None,
            "api_key_env": api_key_env or None,
        }
    )


def run_config(
    *,
    root: Path,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    test: bool = False,
) -> int:
    """Write or test BYOM extractor config. Returns a process exit code."""
    try:
        if provider is not None:
            config = parse_extractor_config(
                {
                    "provider": parse_provider(provider),
                    "model": model,
                    "base_url": base_url,
                    "api_key_env": api_key_env,
                }
            )
            path = write_extractor_config(root, config)
            print(f"wrote {path}")
        elif test:
            config = load_extractor_config(root)
            if config.provider is ExtractorProvider.DISABLED:
                print(
                    "error: extraction is disabled; configure a provider first",
                    file=sys.stderr,
                )
                return EXIT_USAGE
        else:
            config = _interactive_config()
            path = write_extractor_config(root, config)
            print(f"wrote {path}")

        if test:
            result = probe_connection(config)
            print(result.message)
            return EXIT_PASS if result.ok else EXIT_FAIL
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    return EXIT_PASS
