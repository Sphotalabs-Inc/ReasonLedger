#!/usr/bin/env bash
# S15 dist check: build all three wheels, install them into a fresh venv with no
# checkout on the path, and drive the CLI end to end.
#
# The builds run `--offline` against uv's cache. The install resolves third-party
# deps from the index exactly as `uv sync` already does, but installs our three
# packages from explicit local wheel paths — so what gets exercised is always the
# artifact we just built, never a same-named release from PyPI.
#
# DIST_DIR (optional, must start empty) builds into that directory and leaves the files
# there. The release workflow sets it so the files uploaded to PyPI are the very ones this
# script installed and exercised, rather than a second build of the same source.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DIST="${DIST_DIR:-$WORK/dist}"
APP="$WORK/app"
VENV="$WORK/venv"
mkdir -p "$DIST" "$APP"

# Both artifacts, not just the wheel: `uv build --wheel` builds straight from the source
# tree, but a bare `uv build` (what you run before `uv publish`) builds the sdist first
# and then the wheel *from that sdist*. Only the second path notices a file the sdist
# cannot carry — which is how three packages sat with a LICENSE symlink escaping the
# archive, wheel-green and unpublishable.
echo "==> Building sdists + wheels (offline)"
for pkg in reasonledger-core reasonledger reasonledger-mcp; do
  uv build --package "$pkg" --offline --out-dir "$DIST"
done

echo "==> Asserting every artifact carries a real LICENSE and NOTICE, not a symlink"
python3 - "$DIST" <<'PY'
import sys, tarfile, zipfile
from pathlib import Path

LEGAL = ("LICENSE", "NOTICE")
dist = Path(sys.argv[1])
sdists = sorted(dist.glob("*.tar.gz"))
wheels = sorted(dist.glob("*.whl"))
assert len(sdists) == 3 and len(wheels) == 3, f"expected 3 sdists and 3 wheels in {dist}"
for sdist in sdists:
    members = tarfile.open(sdist).getmembers()
    for legal in LEGAL:
        found = [m for m in members if m.name.endswith("/" + legal)]
        assert found, f"{sdist.name} ships no {legal}"
        for member in found:
            assert not member.issym(), f"{sdist.name}: {legal} is a symlink -> {member.linkname}"
            assert member.size > 0, f"{sdist.name}: {legal} is empty"
for wheel in wheels:
    names = zipfile.ZipFile(wheel).namelist()
    for legal in LEGAL:
        assert any(n.endswith(f".dist-info/licenses/{legal}") for n in names), f"{wheel.name}: {legal}"
print("legal files ok:", len(sdists), "sdists,", len(wheels), "wheels")
PY

echo "==> Asserting ui_assets shipped in the CLI wheel"
python3 - "$DIST" "$ROOT" <<'PY'
import sys, zipfile
from pathlib import Path

# The source directory is the list: a hard-coded one goes stale each time a page is added.
source = Path(sys.argv[2]) / "packages/cli/src/reasonledger_cli/ui_assets"
expected = {p.name for p in source.iterdir() if p.is_file()}
wheels = [p for p in Path(sys.argv[1]).glob("reasonledger-*.whl")]
assert len(wheels) == 1, f"expected one CLI wheel, got {wheels}"
names = zipfile.ZipFile(wheels[0]).namelist()
shipped = {Path(n).name for n in names if n.startswith("reasonledger_cli/ui_assets/")}
assert shipped == expected, f"ui_assets mismatch in wheel: missing {expected - shipped}, extra {shipped - expected}"
print("ui_assets ok:", len(shipped), "files")
PY

echo "==> Installing into a fresh venv"
uv venv "$VENV" >/dev/null
VIRTUAL_ENV="$VENV" uv pip install "$DIST"/*.whl >/dev/null

BIN="$VENV/bin"

# From here on: no checkout on PYTHONPATH, cwd outside the repo. If any command below
# still works by importing this source tree, the wheel is not actually self-sufficient.
run() { (cd "$APP" && env -u PYTHONPATH "$@"); }

echo "==> Verifying the installed package, not the checkout, is what runs"
run "$BIN/python" - "$ROOT" <<'PY'
import sys, reasonledger_cli, reasonledger_core, reasonledger_mcp
checkout = sys.argv[1]
for mod in (reasonledger_cli, reasonledger_core, reasonledger_mcp):
    assert not mod.__file__.startswith(checkout), f"{mod.__name__} resolved to the checkout"
print("imports resolve to the venv")
PY

echo "==> Console scripts"
run "$BIN/reasonledger" --help >/dev/null
run "$BIN/rl" --help >/dev/null
run "$BIN/reasonledger-mcp" --help >/dev/null

echo "==> init / status / --html"
# Cursor only: the Claude Code rule lands in CLAUDE.md, which the import step below must not see.
run "$BIN/reasonledger" init --root "$APP" --agents cursor >/dev/null
test -d "$APP/.reasonledger/decisions"
run "$BIN/reasonledger" status --root "$APP" >/dev/null
run "$BIN/reasonledger" status --root "$APP" --json | python3 -c \
  'import json,sys; json.load(sys.stdin)["counts"]; print("status --json ok")'
run "$BIN/reasonledger" status --root "$APP" --html "$WORK/status.html" >/dev/null
grep -q "ReasonLedger" "$WORK/status.html"

# The install-anywhere contract: cwd is the ledger root. `run` already puts us in $APP
# with the checkout off PYTHONPATH, so dropping --root here is the whole point — a
# regression in the cwd default shows up as `proposed: 0` and nothing else.
echo "==> cwd is the default root (no --root anywhere)"
printf '# Notes\n\nWe store all timestamps in UTC.\n' > "$APP/claude.md"
run "$BIN/reasonledger" import \
  --extracted-by fixture/dist-check \
  --fixture "$ROOT/fixtures/golden/import/extractor_replay.json" >/dev/null
run "$BIN/reasonledger" status --json | python3 -c '
import json, sys
counts = json.load(sys.stdin)["counts"]
assert counts["proposed"] == 1, f"cwd default root staged nothing: {counts}"
print("cwd default root ok:", counts)
'
run "$BIN/reasonledger" confirm --all --confirmed-by dist-check@example.com >/dev/null
run "$BIN/reasonledger" why backend/app/date_utils.py | grep -q "UTC"
echo "why ok (no --root)"

# `init` writes the MCP config each agent reads; if it names a command that is not on PATH,
# MCP silently never starts. PATH includes the venv, as it would after `uv tool install`.
echo "==> init writes an MCP config whose command exists, and the agent rules"
run env PATH="$BIN:$PATH" "$BIN/reasonledger" init --no-scan --agents all >/dev/null
python3 - "$APP" "$BIN" <<'PY'
import json, shutil, sys
from pathlib import Path

app, bin_dir = Path(sys.argv[1]), sys.argv[2]
for config, key in ((".mcp.json", "mcpServers"), (".vscode/mcp.json", "servers")):
    entry = json.loads((app / config).read_text(encoding="utf-8"))[key]["reasonledger"]
    assert "--directory" not in entry["args"], f"init emits --directory: {entry}"
    assert entry["command"] == "reasonledger", entry
    assert entry["args"][0] == "mcp", entry
    assert shutil.which(entry["command"], path=bin_dir), f"{entry['command']} not installed"
for rule in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md"):
    assert "reasonledger:begin" in (app / rule).read_text(encoding="utf-8"), rule
assert (app / ".cursor/rules/reasonledger.mdc").is_file()
print("init ok")
PY

echo "==> version flags match the installed metadata"
run "$BIN/reasonledger" --version | grep -q "^reasonledger [0-9]"
run "$BIN/reasonledger-mcp" --version | grep -q "^reasonledger-mcp [0-9]"

# The clean-machine proof: a record written by an agent through the MCP server
# comes back from `why`, using nothing but the installed wheels.
echo "==> MCP record_decision round trip, then why"
mkdir -p "$APP/src"
printf 'def pick_store():\n    return "sqlite"\n' > "$APP/src/store.py"
run "$BIN/python" - "$APP" "$BIN" <<'PY'
import asyncio, json, sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

app, bin_dir = sys.argv[1], sys.argv[2]
# Absolute: the venv is not necessarily on PATH (it is not in CI).
params = StdioServerParameters(command=f"{bin_dir}/reasonledger-mcp", args=["--repo-root", app])


async def main() -> None:
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {tool.name for tool in (await session.list_tools()).tools}
        assert {"record_decision", "query_decisions", "decisions_for"} <= names, names
        result = await session.call_tool(
            "record_decision",
            {
                "context": "Which store backs the cache?",
                "choice": "Use sqlite",
                "alternatives_rejected": ["Postgres"],
                "ai_tool": "claude-code",
                "model": "dist-check",
                "justifies": ["src/store.py:1-2"],
                "proposed_by": "ai",
            },
        )
        payload = json.loads(result.content[0].text)
        assert payload["ok"], payload
        found = await session.call_tool("decisions_for", {"paths": ["src/store.py"]})
        assert json.loads(found.content[0].text)["decisions"], found


asyncio.run(main())
PY
run "$BIN/reasonledger" why src/store.py:1 | grep -q "Use sqlite"
echo "mcp round trip ok"

echo "==> ui: start, fetch /api/view, stop"
# Deliberately left buffered: reading the URL out of a redirected log is also how we
# confirm the installed build flushes it before serve_forever() blocks.
#
# `exec` makes the backgrounded subshell *be* the server, so $! is the server's pid. Going
# through `run &` left a shell between us and the server: `kill "$UI_PID"` stopped the shell and
# the server outlived the script, one orphan per run.
(cd "$APP" && exec env -u PYTHONPATH "$BIN/reasonledger" ui --root "$APP" --port 0 --no-open) \
  >"$WORK/ui.log" 2>&1 &
UI_PID=$!
trap 'kill "$UI_PID" 2>/dev/null || true; rm -rf "$WORK"' EXIT

python3 - "$WORK/ui.log" <<'PY'
import json, re, sys, time, urllib.request
from pathlib import Path

log = Path(sys.argv[1])
deadline = time.time() + 30
origin = None
while time.time() < deadline:
    match = re.search(r"ReasonLedger UI: (\S+)", log.read_text() if log.exists() else "")
    if match:
        origin = match.group(1)
        break
    time.sleep(0.2)
assert origin, f"ui never printed its origin:\n{log.read_text() if log.exists() else ''}"
assert origin.startswith("http://127.0.0.1:"), f"ui not on loopback: {origin}"

html = urllib.request.urlopen(origin, timeout=10).read().decode("utf-8")
token = re.search(r'"token":"([^"]+)"', html).group(1)

request = urllib.request.Request(
    f"{origin}/api/view", headers={"X-RL-Token": token, "Origin": origin}
)
view = json.load(urllib.request.urlopen(request, timeout=10))
assert set(view["counts"]) >= {"proposed", "confirmed"}, view["counts"]
print("ui ok:", origin, "counts", view["counts"])
PY

kill "$UI_PID" 2>/dev/null || true
wait "$UI_PID" 2>/dev/null || true

echo "==> Dist check passed"
