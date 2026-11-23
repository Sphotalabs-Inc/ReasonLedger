"""Phase 5 — the model-first mapper: digest, validation and the provider calls (stubbed)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from modules_helpers import tree, write_files
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.endpoint import is_loopback
from reasonledger_core.modules.config import ASSIGN_BATCH_FILES, BROAD_MODULE_SHARE
from reasonledger_core.modules.digest import build_digest, extract_routes
from reasonledger_core.modules.drift import candidate_groups
from reasonledger_core.modules.llm_mapper import NAME_SYSTEM, SINGLE_SYSTEM, LlmMapper
from reasonledger_core.modules.mapper_check import validate_map

SECRET = "TOP_SECRET_BODY_MARKER"


def _reply(answer: object) -> dict[str, object]:
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}}]}


class Provider:
    """A recorded provider: replies in order, remembers every request body."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.seen: list[dict[str, object]] = []

    def __call__(
        self, url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        self.seen.append(payload)
        return _reply(self.answers.pop(0))

    def prompts(self) -> str:
        return json.dumps(self.seen)


def local_mapper(provider: Provider) -> LlmMapper:
    config = ExtractorConfig(
        provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="http://127.0.0.1:9/v1", model="m"
    )
    return LlmMapper(config, http_post=provider)


def _app(tmp_path: Path) -> Path:
    files = {
        **tree("backend/app/models", 3),
        **tree("backend/app/routes", 3),
        **tree("frontend/src/components/client", 4),
        "backend/app/routes/client_routes.py": (
            f"# {SECRET}\n"
            "@client_bp.route('/clients/<string:id>', methods=['PUT', 'GET'])\n"
            "def update():\n    pass\n"
        ),
        "api/users.ts": "router.get('/users/:id', handler)\n@Post('/login')\n",
        "svc/Pets.java": '@GetMapping("/pets")\n',
        "backend/app/.env": "TOKEN=1\n",
        "backend/tests/test_a.py": "",
        "deploy/up.sh": "",
    }
    write_files(tmp_path, files)
    return tmp_path


@pytest.mark.phase_5
def test_digest_holds_paths_and_routes_but_never_contents_secrets_or_tests(tmp_path: Path) -> None:
    digest = build_digest(_app(tmp_path), ["users", "roles"])
    assert "backend/app/routes/: " in digest.text and "client_routes.py" in digest.text
    assert "PUT,GET /clients/<string:id>" in digest.text or "GET /clients" in digest.text
    assert "GET /users/:id" in digest.text and "GET /pets" in digest.text
    assert "MODULES THE OWNER EXPECTS" in digest.text and "users, roles" in digest.text
    assert SECRET not in digest.text  # contents never leave
    assert ".env" not in digest.text and "test_a.py" not in digest.text  # secrets and tests
    assert "deploy/up.sh" in digest.source_files or "up.sh" in digest.text  # tooling is mapped


@pytest.mark.phase_5
def test_route_extraction_covers_flask_fastapi_express_nest_and_spring(tmp_path: Path) -> None:
    write_files(
        tmp_path,
        {
            "a.py": "@bp.route('/flask', methods=['POST'])\n@router.get('/fast')\n",
            "b.js": "app.post('/express')\n",
            "c.ts": "@Delete('/nest')\n",
            "d.java": '@PutMapping(value = "/spring")\n',
        },
    )
    lines = extract_routes(tmp_path, ["a.py", "b.js", "c.ts", "d.java"])
    text = "\n".join(lines)
    for expected in ("POST /flask", "GET /fast", "POST /express", "DELETE /nest", "PUT /spring"):
        assert expected in text


@pytest.mark.phase_5
def test_validation_drops_invented_paths_tiny_modules_and_flags_broad_ones() -> None:
    source = [*tree("app/orders", 4), *tree("app/pay", 3), "lone.py", *tree("rest", 12)]

    def mod(module_id: str, paths: list[str], kind: str = "feature") -> dict[str, object]:
        return {
            "id": module_id,
            "name": module_id.title(),
            "kind": kind,
            "description": "d",
            "paths": paths,
        }

    proposed = [
        mod("Orders", ["app/orders/**", "app/orders/ghost.py", "nowhere/**"]),
        mod("pay", ["app/pay/f0.py", "app/pay/f1.py", "app/pay/f2.py"], "foundation"),
        mod("tiny", ["lone.py"]),
        mod("ghosts", ["nope/x.py"]),
        mod("orders", ["rest/**"]),
    ]
    result = validate_map(proposed, source, source)
    by_id = {m.id: m for m in result.modules}
    assert set(by_id) == {"orders", "pay", "orders-2"}  # ids slugged and made unique
    assert by_id["orders"].paths == ["app/orders/**"] and by_id["pay"].paths == ["app/pay/**"]
    assert by_id["pay"].kind.value == "foundation"
    joined = " | ".join(result.issues)
    assert "dropped 2 path(s)" in joined and "tiny: dropped, only 1 file" in joined
    assert "ghosts: dropped, no valid path" in joined
    assert (
        f"orders-2: broad, claims 12 of {len(source)}" in joined
        and BROAD_MODULE_SHARE * len(source) < 12
    )
    assert result.unplaced == ["lone.py"] and result.placed == len(source) - 1


@pytest.mark.phase_5
def test_single_mode_sends_the_digest_and_nothing_else(tmp_path: Path) -> None:
    root = _app(tmp_path)
    provider = Provider(
        {
            "modules": [
                {
                    "id": "clients",
                    "name": "Clients",
                    "kind": "feature",
                    "description": "d",
                    "paths": ["frontend/src/components/client/**"],
                }
            ]
        }
    )
    digest = build_digest(root)
    modules = local_mapper(provider).propose(digest, "single")
    assert modules[0]["id"] == "clients"
    assert SECRET not in provider.prompts() and ".env" not in provider.prompts()
    assert len(provider.seen) == 1


@pytest.mark.phase_5
def test_staged_mode_names_first_then_assigns_in_batches_against_a_closed_list(
    tmp_path: Path,
) -> None:
    files = {f"app/{'a' if i % 2 else 'b'}/f{i}.py": "" for i in range(ASSIGN_BATCH_FILES + 5)}
    write_files(tmp_path, files)
    names = {
        "modules": [
            {"id": "alpha", "name": "Alpha", "kind": "feature", "description": "odd files"},
            {"id": "beta", "name": "Beta", "kind": "foundation", "description": "even files"},
        ]
    }

    def answer(batch: list[str]) -> dict[str, object]:
        return {
            "assignments": [{"file": f, "module": "alpha" if "/a/" in f else "beta"} for f in batch]
            + [{"file": "app/invented.py", "module": "alpha"}]
        }

    digest = build_digest(tmp_path)
    ordered = list(digest.source_files)
    provider = Provider(
        names, answer(ordered[:ASSIGN_BATCH_FILES]), answer(ordered[ASSIGN_BATCH_FILES:])
    )
    modules = local_mapper(provider).propose(digest, "staged")
    assert len(provider.seen) == 3  # one naming call, two assignment batches
    assert json.dumps(provider.seen[1]).count("\\n- ") == 0 or "alpha" in json.dumps(
        provider.seen[1]
    )
    assert "enum" in json.dumps(provider.seen[1]) and "none" in json.dumps(provider.seen[1])
    owned = {m["id"]: m["paths"] for m in modules}
    assert sum(len(v) for v in owned.values()) == len(ordered)  # the invented file was ignored
    assert all("/a/" in p for p in owned["alpha"]) and all("/b/" in p for p in owned["beta"])


@pytest.mark.phase_5
def test_mode_and_consent_follow_where_the_provider_is() -> None:
    def mapper(provider: ExtractorProvider, url: str | None) -> LlmMapper:
        return LlmMapper(ExtractorConfig(provider=provider, base_url=url, model="m"))

    local = mapper(ExtractorProvider.LOCAL, "http://localhost:11434")
    box = mapper(ExtractorProvider.OPENAI_COMPATIBLE, "http://127.0.0.1:18080/v1")
    hosted = mapper(ExtractorProvider.OPENAI_COMPATIBLE, "https://api.example.com/v1")
    claude = mapper(ExtractorProvider.ANTHROPIC, None)
    assert [x.default_mode() for x in (local, box, hosted, claude)] == [
        "staged",
        "staged",
        "single",
        "single",
    ]
    assert [x.sends_off_machine for x in (local, box, hosted, claude)] == [False, False, True, True]
    assert (
        is_loopback("http://[::1]:8080")
        and not is_loopback(None)
        and is_loopback("http://x.localhost")
    )


@pytest.mark.phase_5
def test_new_module_groups_come_from_shared_prefixes_then_folders() -> None:
    unplaced = [
        "svc/export_sage_service.py",
        "svc/export_tally_service.py",
        "svc/export_qb_service.py",
        "svc/index.js",
        "svc/index.css",
        "svc/index.html",
        "web/pages/a.js",
        "web/pages/b.js",
        "web/pages/c.js",
        "x/one.py",
        "x/two.py",
    ]
    groups = {g.name: g for g in candidate_groups(unplaced)}
    # three index.* files in one folder form a folder group; the two x/ files are too few
    assert set(groups) == {"export", "pages", "svc"}
    assert groups["svc"].files == ["svc/index.css", "svc/index.html", "svc/index.js"]
    assert groups["export"].files == sorted(f for f in unplaced if "export_" in f)
    assert "3 files" in groups["export"].reason


@pytest.mark.phase_5
def test_a_feature_repeated_across_layers_joins_the_group_of_the_same_name() -> None:
    unplaced = [
        "web/user/profile.js",
        "web/user/settings.js",
        "web/user/avatar.js",
        "models/user.py",
        "routes/user_routes.py",
        "services/user_service.py",
        "models/invoice.py",
        "routes/invoice_routes.py",
        "services/invoice_service.py",
    ]
    groups = {g.name: g for g in candidate_groups(unplaced, total=200)}
    assert set(groups) == {"user", "invoice"}
    assert groups["user"].files == sorted(f for f in unplaced if "user" in f)
    assert "across" in groups["user"].reason and "3 files in web/user" in groups["user"].reason


@pytest.mark.phase_5
def test_every_route_tells_the_model_to_split_tiers_and_not_to_bucket_shared_code() -> None:
    # The owner rejected an "app shell" module of shared components, hooks and utilities, and
    # wants frontend and backend kept as separate modules.
    # The agent route sends SINGLE_SYSTEM and the staged route sends NAME_SYSTEM.
    for instructions in (SINGLE_SYSTEM, NAME_SYSTEM):
        text = " ".join(instructions.split())  # the prompt is wrapped for line length
        assert "Shared code is a layer too" in text
        assert "never use a module to hold files that fit nowhere else" in text
        assert "Keep frontend and backend apart" in text
        assert "Never mix the two in one module" in text
