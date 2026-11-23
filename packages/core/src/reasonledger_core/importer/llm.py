"""Provider-neutral structured-JSON calls for the three bring-your-own-model providers.

Both model-backed features — decision import and the related-decision judge — ask a
model for one JSON object matching a schema. The transport, payload shape and response
parsing per provider live here once; each feature supplies only its `StructuredTask`
(system prompt, schema, name). HTTP is injectable so CI never touches the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPMessage
from typing import IO
from urllib import error, request

from pydantic import ValidationError

from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider, resolve_api_key

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 900.0  # local Ollama on CPU
MAX_OUTPUT_TOKENS = 4096
LOCAL_CONTEXT_TOKENS = 16384

HttpPost = Callable[[str, dict[str, object], Mapping[str, str], float], dict[str, object]]
Messages = list[dict[str, object]]


class LlmError(Exception):
    """A model call could not be configured, sent, or parsed."""


class InvalidResponse(LlmError):
    """The model answered twice, and neither answer validated."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class StructuredTask:
    """What one feature asks of a model: its instructions and the JSON it must return."""

    system: str
    schema: dict[str, object]
    name: str  # Anthropic tool name
    schema_name: str  # OpenAI-compatible json_schema name
    description: str


class _RefuseRedirect(request.HTTPRedirectHandler):
    """Follow no redirect: urllib would re-send the API key headers to wherever it points."""

    def redirect_request(
        self,
        req: request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> request.Request | None:
        return None


_OPENER = request.build_opener(_RefuseRedirect)


def http_post_json(
    url: str,
    payload: dict[str, object],
    headers: Mapping[str, str],
    timeout: float,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if HTTPStatus.MULTIPLE_CHOICES <= exc.code < HTTPStatus.BAD_REQUEST:
            raise LlmError(
                f"the provider answered with a redirect (HTTP {exc.code}), which is not "
                "followed so the API key stays with the configured address; set base_url to "
                "the address the provider documents"
            ) from exc
        raise LlmError(f"HTTP request failed: {exc}") from exc
    except error.URLError as exc:
        raise LlmError(f"HTTP request failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise LlmError("HTTP response must be a JSON object")
    return raw


def anthropic_payload(task: StructuredTask, *, model: str, messages: Messages) -> dict[str, object]:
    return {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": task.system,
        "messages": messages,
        "tools": [
            {"name": task.name, "description": task.description, "input_schema": task.schema}
        ],
        "tool_choice": {"type": "tool", "name": task.name},
    }


def openai_compatible_payload(
    task: StructuredTask, *, model: str, messages: Messages
) -> dict[str, object]:
    return {
        "model": model,
        "messages": [{"role": "system", "content": task.system}, *messages],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": task.schema_name, "strict": True, "schema": task.schema},
        },
    }


def local_payload(task: StructuredTask, *, model: str, messages: Messages) -> dict[str, object]:
    return {
        "model": model,
        "messages": [{"role": "system", "content": task.system}, *messages],
        "format": task.schema,
        "stream": False,
        "options": {"num_ctx": LOCAL_CONTEXT_TOKENS},
    }


def _parse_anthropic(raw: dict[str, object]) -> dict[str, object]:
    content = raw.get("content")
    if not isinstance(content, list):
        raise ValueError("anthropic response missing content array")
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            input_data = block.get("input")
            if isinstance(input_data, dict):
                return input_data
    raise ValueError("anthropic response missing tool_use block")


def _parse_json_string(content: object, *, label: str) -> dict[str, object]:
    if not isinstance(content, str):
        raise ValueError(f"{label} content must be a string")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} content is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} content must decode to a JSON object")
    return parsed


def _parse_openai(raw: dict[str, object]) -> dict[str, object]:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("openai response missing choices[0]")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("openai choices[0] must be an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("openai response missing message")
    return _parse_json_string(message.get("content"), label="openai message")


def _parse_ollama(raw: dict[str, object]) -> dict[str, object]:
    message = raw.get("message")
    if not isinstance(message, dict):
        raise ValueError("ollama response missing message")
    return _parse_json_string(message.get("content"), label="ollama message")


PayloadBuilder = Callable[..., dict[str, object]]
Parser = Callable[[dict[str, object]], dict[str, object]]


class StructuredClient:
    """One configured endpoint that answers a task with a JSON object.

    ``call`` raises ``LlmError`` on transport failure and ``ValueError`` when the
    response is not the expected shape, so a caller can retry on the latter only.
    """

    def __init__(
        self,
        *,
        task: StructuredTask,
        url: str,
        model: str,
        headers: Mapping[str, str],
        build: PayloadBuilder,
        parse: Parser,
        http_post: HttpPost,
        timeout_seconds: float,
    ) -> None:
        self.task = task
        self.model = model
        self._url = url
        self._headers = dict(headers)
        self._build = build
        self._parse = parse
        self._http_post = http_post
        self._timeout_seconds = timeout_seconds

    def call(self, messages: Messages) -> dict[str, object]:
        payload = self._build(self.task, model=self.model, messages=messages)
        raw = self._http_post(self._url, payload, self._headers, self._timeout_seconds)
        return self._parse(raw)


def _json_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def build_structured_client(
    config: ExtractorConfig,
    task: StructuredTask,
    *,
    api_key: str | None = None,
    http_post: HttpPost | None = None,
    model: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> StructuredClient:
    """A client for ``config``'s provider; ``model`` overrides the configured one."""
    if config.provider is ExtractorProvider.DISABLED:
        raise LlmError("no model is configured; run `reasonledger config`")
    post = http_post or http_post_json
    key = api_key if api_key is not None else resolve_api_key(config)
    chosen = model or config.model

    def client(
        url: str, headers: Mapping[str, str], build: PayloadBuilder, parse: Parser, name: str
    ) -> StructuredClient:
        return StructuredClient(
            task=task,
            url=url,
            model=name,
            headers=headers,
            build=build,
            parse=parse,
            http_post=post,
            timeout_seconds=timeout_seconds,
        )

    if config.provider is ExtractorProvider.ANTHROPIC:
        if not key:
            raise LlmError("anthropic provider requires an API key (set api_key_env)")
        base = (config.base_url or ANTHROPIC_DEFAULT_BASE_URL).rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        }
        name = chosen or ANTHROPIC_DEFAULT_MODEL
        return client(f"{base}/v1/messages", headers, anthropic_payload, _parse_anthropic, name)

    label = config.provider.value
    if not config.base_url:
        raise LlmError(f"{label} provider requires base_url")
    if not chosen:
        raise LlmError(f"{label} provider requires model")
    base = config.base_url.rstrip("/")
    if config.provider is ExtractorProvider.OPENAI_COMPATIBLE:
        return client(
            f"{base}/chat/completions",
            _json_headers(key),
            openai_compatible_payload,
            _parse_openai,
            chosen,
        )
    return client(f"{base}/api/chat", _json_headers(key), local_payload, _parse_ollama, chosen)


def call_with_retry[T](
    client: StructuredClient,
    messages: Messages,
    validate: Callable[[dict[str, object]], T],
    *,
    correction: Callable[[str], str],
) -> T:
    """Call, validate, and on an invalid answer retry once with a correction message.

    Transport failures (``LlmError``) are not retried; ``InvalidResponse`` carries the
    second validation error.
    """
    sent = list(messages)
    for attempt in range(2):
        try:
            return validate(client.call(sent))
        except (ValueError, ValidationError) as exc:
            if attempt == 1:
                raise InvalidResponse(str(exc)) from exc
            sent = [*messages, {"role": "user", "content": correction(str(exc))}]
    raise InvalidResponse("no answer")
