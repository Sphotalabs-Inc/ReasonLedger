"""Decision extraction over the shared bring-your-own-model client.

Provider transport, payloads and parsing live in ``importer.llm``; this module adds
only what is specific to extraction: the task, candidate validation, and one retry
with a correction message when the model's JSON does not validate.
"""

from __future__ import annotations

from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.extractor import DecisionCandidate, Extractor
from reasonledger_core.importer.llm import (
    HttpPost,
    InvalidResponse,
    LlmError,
    StructuredClient,
    StructuredTask,
    build_structured_client,
    call_with_retry,
)
from reasonledger_core.importer.prompt import (
    CANDIDATES_JSON_SCHEMA,
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_TOOL_NAME,
    build_user_prompt,
)
from reasonledger_core.importer.scan import ImportSource

EXTRACTION_TASK = StructuredTask(
    system=EXTRACTION_SYSTEM_PROMPT,
    schema=CANDIDATES_JSON_SCHEMA,
    name=EXTRACTION_TOOL_NAME,
    schema_name="decision_candidates",
    description="Extract decision candidates from the document.",
)


class ExtractorError(LlmError):
    """Raised when extraction fails after validate-and-retry."""


def _validate_candidates(payload: object) -> list[DecisionCandidate]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("payload.decisions must be an array")
    return [DecisionCandidate.model_validate(item) for item in decisions]


def _correction_message(error: str) -> str:
    return (
        f"Your previous response was invalid: {error}. "
        "Respond with schema-valid JSON containing a decisions array."
    )


class StructuredExtractor:
    """Extracts candidates through any configured provider."""

    def __init__(self, client: StructuredClient) -> None:
        self._client = client

    def extract(self, source: ImportSource) -> list[DecisionCandidate]:
        messages: list[dict[str, object]] = [{"role": "user", "content": build_user_prompt(source)}]
        try:
            return call_with_retry(
                self._client, messages, _validate_candidates, correction=_correction_message
            )
        except InvalidResponse as exc:
            raise ExtractorError(f"extraction failed after retry: {exc.detail}") from exc
        except LlmError as exc:
            raise ExtractorError(str(exc)) from exc


def build_extractor(
    config: ExtractorConfig,
    *,
    api_key: str | None = None,
    http_post: HttpPost | None = None,
) -> Extractor:
    """Return an extractor for the configured provider."""
    if config.provider is ExtractorProvider.DISABLED:
        raise ExtractorError("extraction is disabled; run `reasonledger config`")
    try:
        client = build_structured_client(
            config, EXTRACTION_TASK, api_key=api_key, http_post=http_post
        )
    except LlmError as exc:
        raise ExtractorError(str(exc)) from exc
    return StructuredExtractor(client)
