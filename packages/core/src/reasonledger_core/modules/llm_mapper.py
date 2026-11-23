"""Ask the configured model for a module map, a name for a new module, or a placement for files.

Every answer is parsed against a schema and then checked in code (`mapper_check`); this module
only talks to the provider. It uses the repo's own extractor provider, so the quality of a map is
the quality of the model the owner integrated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.endpoint import is_loopback
from reasonledger_core.importer.llm import (
    HttpPost,
    StructuredClient,
    StructuredTask,
    build_structured_client,
    call_with_retry,
)
from reasonledger_core.modules.config import ASSIGN_BATCH_FILES, FOUNDATIONS_TO_WATCH
from reasonledger_core.modules.digest import Digest
from reasonledger_core.modules.drift import NewModuleGroup
from reasonledger_core.modules.models import Module

MapMode = Literal["auto", "single", "staged"]

_RULES = f"""\
You map the logical modules of one software application from its file paths and HTTP routes.
A module is a business capability (promo codes, projects, document review, exports) or a foundation
the features sit on. Foundations to watch for: {", ".join(FOUNDATIONS_TO_WATCH)}. Include a
foundation only if the code has it. Layers (models, routes, services, components, hooks) are NOT
modules. Keep frontend and backend apart: when the repository has separate frontend and backend
code, a capability is two modules, the backend one holding its logic, API and data and the
frontend one holding the screens and client code that consume it (name them alike, for example
subscriptions and subscriptions-ui). Never mix the two in one module. An app with no separate
frontend keeps a capability in one module. Shared code is a layer too: never make a module of the
app shell, common or shared components, contexts, hooks, API clients, state stores or generic
utilities, and never use a module to hold files that fit nowhere else. Put each such file with
the capability it serves. A foundation has a purpose you can state in a few words
(authentication, theming, internationalization), not "code everything uses".
Route paths show the domain nouns and capabilities. Prefer a modest number of modules a maintainer
would accept as they are. kind is "foundation" for things other modules build on, else "feature".
Never include names, email addresses or other personal data."""

SINGLE_SYSTEM = (
    _RULES
    + """
Cover every source file; leave out one that fits no capability rather than invent a catch-all.
Give folder globs (dir/**), name patterns (dir/prefix*) or exact paths; the most specific pattern
wins. Do not invent paths."""
)
NAME_SYSTEM = _RULES + "\nName and describe the modules only; files are assigned in a later step."
ASSIGN_SYSTEM = (
    "You assign source files of one application to its modules, judging by the file path "
    "(folder and file name). Use none only when nothing fits."
)
PLACE_SYSTEM = (
    "You place newly added source files into the modules of an application, judging by the file "
    "paths. For each group choose an existing module, or new (with a short name) when the group "
    "is its own capability."
)

_STR = {"type": "string"}
_KIND = {"type": "string", "enum": ["feature", "foundation"]}


def _object(properties: dict[str, object], required: list[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _list_of(item: dict[str, object], key: str) -> dict[str, object]:
    return _object({key: {"type": "array", "items": item}}, [key])


_MODULE_FIELDS = {"id": _STR, "name": _STR, "kind": _KIND, "description": _STR}
SINGLE_SCHEMA = _list_of(
    _object(
        {**_MODULE_FIELDS, "paths": {"type": "array", "items": _STR}},
        ["id", "name", "kind", "description", "paths"],
    ),
    "modules",
)
NAME_SCHEMA = _list_of(_object(_MODULE_FIELDS, ["id", "name", "kind", "description"]), "modules")


class SingleModule(BaseModel):
    id: str
    name: str
    kind: Literal["feature", "foundation"]
    description: str
    paths: list[str]


class SingleAnswer(BaseModel):
    modules: list[SingleModule]


class NamedModule(BaseModel):
    id: str
    name: str
    kind: Literal["feature", "foundation"]
    description: str


class NameAnswer(BaseModel):
    modules: list[NamedModule]


class Assignment(BaseModel):
    file: str
    module: str


class AssignAnswer(BaseModel):
    assignments: list[Assignment]


class Placement(BaseModel):
    group: str
    module: str
    new_module_name: str = ""


class PlaceAnswer(BaseModel):
    placements: list[Placement]


def _correction(error: str) -> str:
    return f"Your previous response was invalid: {error}. Respond with schema-valid JSON only."


class LlmMapper:
    """One configured model, used for mapping, naming and placing."""

    def __init__(
        self,
        config: ExtractorConfig,
        *,
        model: str | None = None,
        api_key: str | None = None,
        http_post: HttpPost | None = None,
    ) -> None:
        self._config, self._model = config, model
        self._api_key, self._http_post = api_key, http_post
        self.name = f"{config.provider.value}:{model or config.model or '?'}"

    @property
    def sends_off_machine(self) -> bool:
        """Whether a prompt leaves this machine (the consent question, spec/14 S37)."""
        if self._config.provider is ExtractorProvider.ANTHROPIC:
            return True
        return not is_loopback(self._config.base_url)

    def default_mode(self) -> Literal["single", "staged"]:
        """Small local models need the staged route; hosted models do it in one call."""
        return (
            "staged"
            if self._config.provider is ExtractorProvider.LOCAL or not self.sends_off_machine
            else "single"
        )

    def _ask[T: BaseModel](self, task: StructuredTask, prompt: str, answer: type[T]) -> T:
        client: StructuredClient = build_structured_client(
            self._config, task, api_key=self._api_key, http_post=self._http_post, model=self._model
        )
        messages: list[dict[str, object]] = [{"role": "user", "content": prompt}]
        return call_with_retry(client, messages, answer.model_validate, correction=_correction)

    def propose(self, digest: Digest, mode: MapMode = "auto") -> list[dict[str, object]]:
        """Raw module proposals, to be validated by `mapper_check.validate_map`."""
        chosen = self.default_mode() if mode == "auto" else mode
        if chosen == "single":
            task = StructuredTask(SINGLE_SYSTEM, SINGLE_SCHEMA, "map_modules", "module_map", "Map")
            return [m.model_dump() for m in self._ask(task, digest.text, SingleAnswer).modules]
        return self._propose_staged(digest)

    def _propose_staged(self, digest: Digest) -> list[dict[str, object]]:
        task = StructuredTask(NAME_SYSTEM, NAME_SCHEMA, "name_modules", "module_names", "Name")
        named = self._ask(task, digest.text, NameAnswer).modules
        listing = "\n".join(f"- {m.id}: {m.description}" for m in named)
        owned = self.assign(listing, [m.id for m in named], digest.source_files)
        return [
            {**m.model_dump(), "paths": sorted(owned.get(m.id, []))}
            for m in named
            if owned.get(m.id)
        ]

    def assign(
        self, listing: str, module_ids: Sequence[str], files: Sequence[str]
    ) -> dict[str, list[str]]:
        """Closed-list assignment of files to modules, in batches a small model can handle."""
        schema = _list_of(
            _object(
                {"file": _STR, "module": {"type": "string", "enum": [*module_ids, "none"]}},
                ["file", "module"],
            ),
            "assignments",
        )
        task = StructuredTask(ASSIGN_SYSTEM, schema, "assign_files", "file_assignments", "Assign")
        owned: dict[str, list[str]] = {}
        for start in range(0, len(files), ASSIGN_BATCH_FILES):
            batch = files[start : start + ASSIGN_BATCH_FILES]
            prompt = f"Modules:\n{listing}\n\nFiles:\n" + "\n".join(batch)
            for item in self._ask(task, prompt, AssignAnswer).assignments:
                if item.file in batch and item.module in module_ids:
                    owned.setdefault(item.module, []).append(item.file)
        return owned

    def place_groups(
        self, existing: Sequence[Module], groups: Sequence[NewModuleGroup]
    ) -> list[Placement]:
        """For each candidate group: an existing module, or a name for a new one."""
        ids = [m.id for m in existing]
        schema = _list_of(
            _object(
                {
                    "group": _STR,
                    "module": {"type": "string", "enum": [*ids, "new"]},
                    "new_module_name": _STR,
                },
                ["group", "module", "new_module_name"],
            ),
            "placements",
        )
        task = StructuredTask(PLACE_SYSTEM, schema, "place_groups", "group_placements", "Place")
        listing = "\n".join(f"- {m.id}: {m.description}" for m in existing)
        blocks = "\n\n".join(f"Group {g.name}:\n" + "\n".join(g.files) for g in groups)
        prompt = f"Existing modules:\n{listing}\n\nNew file groups:\n{blocks}"
        known = {g.name for g in groups}
        return [p for p in self._ask(task, prompt, PlaceAnswer).placements if p.group in known]
