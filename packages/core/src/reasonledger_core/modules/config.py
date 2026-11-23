"""Named, documented thresholds for module detection.

Every value here changes what a scan proposes, so each is a constant that tests pin
(AGENTS.md §4). The numbers are initial guesses, to be calibrated on the corpus in
spec/14 §12 and then frozen; they are never tuned at runtime.
"""

from __future__ import annotations

from pathlib import Path

MANIFEST_PATH = Path(".reasonledger/modules.yml")
MANIFEST_VERSION = "1"

# --- Which files are modelled at all -------------------------------------------------
# Lockfiles, changelogs and assets change with everything or mean nothing to a module.
NOISE_FILE_PATTERNS: tuple[str, ...] = (
    "*.lock",
    "*-lock.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "go.sum",
    "CHANGELOG*",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.snap",
    ".env",
    ".env.*",  # secrets: never listed, never modelled
)
# Directory names that mark generated or packaged output, wherever they sit.
GENERATED_DIR_SUFFIXES: tuple[str, ...] = (".egg-info", ".dist-info")
ASSET_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".pdf",
        ".onnx",
        ".pt",
        ".pth",
        ".bin",
        ".pkl",
        ".h5",
        ".tflite",
        ".parquet",
    }
)

# --- Module size ----------------------------------------------------------------------
MIN_MODULE_FILES = 3  # a "module" of one or two files is a file, not a module

# --- Co-change (git history) ----------------------------------------------------------
MAX_COMMITS_SCANNED = 5000  # most recent commits read
MAX_FILES_PER_COMMIT = 50  # bulk renames and formatters say nothing about coupling
MIN_COCHANGE_COMMITS = 3  # a pair must change together this often to count
COCHANGE_EDGE_THRESHOLD = 0.5  # shared commits / the busier file's commits
MAX_COMPONENT_SHARE = 0.4  # a cluster this large is "everything changes together": noise
SQUASH_SUBJECT_SHARE = 0.5  # share of subjects ending "(#123)" that marks squash-merge history
SCOPE_NAME_SHARE = 0.5  # commit-scope share needed to name a cluster after a scope

# --- Layout ---------------------------------------------------------------------------
LAYOUT_WRAPPER_SHARE = 0.7  # one child holding this share of a directory makes it a wrapper
LAYOUT_MAX_DEPTH = 8  # Java packages nest deep
LAYOUT_MIN_CHILDREN = 3  # a directory with this many substantial children is a namespace
CONTAINER_DIRS: frozenset[str] = frozenset(
    {
        "packages",
        "apps",
        "services",
        "libs",
        "modules",
        "crates",
        "plugins",
        "internal",
        "cmd",
        "pkg",
        "src",
    }
)
# Path segments that say where code lives, not what it is: a module is named after the
# nearest segment that is not one of these (packages/api/src -> "api").
GENERIC_SEGMENTS: frozenset[str] = CONTAINER_DIRS | frozenset(
    {"main", "java", "kotlin", "scala", "python", "code", "source"}
)
# Directories of support code: tests, docs, examples, fixtures. Never modules in their own right.
SUPPORT_DIRS: frozenset[str] = frozenset(
    {
        ".github",
        ".circleci",
        ".vscode",
        ".idea",
        "docs",
        "doc",
        "docs_src",
        "fixtures",
        "testdata",
        "spec",
        "specs",
        "tests",
        "test",
        "e2e",
        "examples",
        "example",
        "benches",
        "benchmarks",
        "playground",
        "__tests__",
        "__mocks__",
        "__fixtures__",
        "__snapshots__",
    }
)

# Sub-structure of a module (not modules): a directory holding only these is one module.
SUBSTRUCTURE_DIRS: frozenset[str] = frozenset(
    {
        "migrations",
        "templates",
        "static",
        "locale",
        "locales",
        "management",
        "assets",
        "styles",
        "types",
        "typings",
        "schemas",
        "__pycache__",
        "public",
    }
)
COCHANGE_MIN_FILES = 5  # smaller clusters are hot spots inside a directory, not modules
COCHANGE_MIN_DIRECTORIES = 2  # a cluster inside one directory adds nothing to the layout signal

# --- Resolution -----------------------------------------------------------------------
BOUNDARY_AGREEMENT_JACCARD = 0.6  # two candidates this similar are one module

MIN_REMAINDER_SHARE = 0.7  # a weak candidate keeps this share of its files, or it is a container
CORROBORATION_CONTAINMENT = 0.75  # a convention or co-change group this inside a module backs it

# --- Foundations ----------------------------------------------------------------------
FOUNDATION_NAME_HINTS: frozenset[str] = frozenset(
    {
        "platform",
        "core",
        "common",
        "shared",
        "utils",
        "util",
        "lib",
        "config",
        "base",
        "dates",
        "tooling",
    }
)
FOUNDATION_DEPENDENTS = 4  # this many other modules routinely change together with it
FOUNDATION_DEPENDENT_SHARE = 0.3  # "routinely": this share of the other module's commits
FOUNDATION_MIN_SHARED_COMMITS = 3  # and at least this many commits

# --- Tooling: build, deploy and maintenance code. It belongs to the platform, not to a feature.
TOOLING_DIR_PATTERN = (
    r"^(deploy(ment)?s?|scripts?|tools?|tooling|infra(structure)?|ops|devops|docker|ci|bin"
    r"|cleanup|maintenance|manual|k8s|terraform|helm|charts)([-_].*)?$"
)
TOOLING_MODULE_ID = "tooling"
# A tooling module folds into the first of these that a scan already proposes.
PLATFORM_MODULE_IDS: tuple[str, ...] = ("platform", "infrastructure", "devops")
LICENSE_FILE_PATTERN = (
    r"^(licen[sc]e|copying|notice)(\.[a-z]+)?$"  # a vendored project keeps its own
)

# --- Layer convention: one feature, one name, repeated across model/route/service folders.
CONVENTION_MIN_LAYERS = 2  # a name must appear in this many different layers
LAYER_DIRS: frozenset[str] = frozenset(
    {
        "model",
        "entity",
        "domain",
        "schema",
        "route",
        "router",
        "controller",
        "handler",
        "view",
        "api",
        "service",
        "usecase",
        "repository",
        "repo",
        "dao",
        "store",
        "slice",
        "reducer",
        "action",
        "component",
        "page",
        "hook",
        "container",
        "resolver",
        "mutation",
        "query",
        "serializer",
        "form",
    }
)  # singular; a folder called "services" counts as "service"
# Folder names that are a layer of an app, never a feature of it ("api" may be a package).
NON_FEATURE_LAYERS: frozenset[str] = frozenset(
    {
        "model",
        "entity",
        "schema",
        "route",
        "router",
        "controller",
        "handler",
        "view",
        "service",
        "repository",
        "repo",
        "dao",
        "slice",
        "reducer",
        "action",
        "component",
        "hook",
        "container",
        "resolver",
        "mutation",
        "serializer",
        "dto",
        "decorator",
        "interceptor",
        "listener",
        "validator",
        "guard",
        "middleware",
        "pipe",
        "constant",
        "helper",
        "util",
        "context",
        "provider",
        "common",
        "shared",
        "lib",
    }
)
STEM_SUFFIX_WORDS: frozenset[str] = LAYER_DIRS | frozenset(
    {"routes", "dto", "impl", "spec", "test", "tests", "client", "provider", "manager"}
)
STEM_PREFIX_WORDS: frozenset[str] = frozenset({"use", "test", "get", "create", "update", "delete"})
GENERIC_STEMS: frozenset[str] = frozenset(
    {
        "index",
        "init",
        "main",
        "app",
        "base",
        "common",
        "config",
        "util",
        "utils",
        "helper",
        "helpers",
        "type",
        "types",
        "constant",
        "constants",
        "setup",
        "server",
        "mod",
        "lib",
        "core",
        "default",
        "error",
        "errors",
        "exception",
        "exceptions",
        "settings",
        "version",
    }
)

# --- Tiers and buckets ---------------------------------------------
# A directory with one of these names marks its files as one tier. The first such name on a path
# decides (frontend/src/services/api is frontend), and tiers exist only in a repo that has both.
FRONTEND_DIRS: frozenset[str] = frozenset(
    {"frontend", "front-end", "client", "web", "webapp", "ui"}
)
BACKEND_DIRS: frozenset[str] = frozenset({"backend", "back-end", "server", "api"})
TIER_DOMINANCE_SHARE = 0.6  # a module has a tier when this share of its files sits in one
UI_SUFFIX = "-ui"  # the frontend half of a capability: subscriptions (backend), subscriptions-ui
HOME_MEDIUM_SHARE = 0.5  # one kind of evidence naming a module for over this share is "medium"
MAX_HOME_SUGGESTIONS = 3  # modules offered for a decision with no working anchor
FOLD_MIN_PARTS = 3  # parts of one feature that earn it a module of its own when it has none
FOLD_DESCRIBED = 6  # folder names listed in the description of a module made by folding
SHARED_BUCKET_ID = "shared"  # files no capability owns; per tier it is shared-frontend/-backend
# A configuration file sitting directly in an app's own folder (apps/server/package.json,
# backend/Dockerfile) is tooling. A source file there (backend/run.py) and a data file deeper
# down (src/data/seed.json) stay shared code.
CONFIG_SUFFIXES: frozenset[str] = frozenset(
    {".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".md", ".txt", ".html"}
)
CONFIG_NAME_PATTERN = (
    r"^(\..+|dockerfile.*|makefile|.+\.config\.[a-z]+)$"  # .gitignore, vite.config.ts
)

# --- Confirming modules ------------------------------------------------------
PENDING_QUEUE_CAP = 5  # proposals shown at a time, so confirming does not turn into a click-through
REJECT_REAPPEAR_JACCARD = (
    0.7  # a rejected module stays down while a proposal covers this much of it
)

# --- Suggesting a home for a new file -----------------------------------
MIN_FOLDER_SIBLINGS = 2  # a folder says something about a file only with this many others in it
SIBLING_MAJORITY = 0.5  # more than this share of the files beside it must sit in one module
NAME_FAMILY_MIN_FILES = 2  # files of a module that share the new file's leading name word
NAME_FAMILY_SHARE = 0.5  # share of all files with that word that the module must hold
SIBLING_WEIGHT = 3.0  # how much each kind of evidence counts toward a module's score
NAME_WEIGHT = 2.0
COCHANGE_WEIGHT = 2.0
MEDIUM_SCORE = 2.0  # one kind of evidence is "medium" at this score; two kinds agreeing is "high"
ALTERNATIVE_SCORE_SHARE = 0.5  # a runner-up is shown when it scores at least this share of the best
RULE_PROMOTION_MIN_LABELS = (
    3  # files a person placed by hand in one folder before a rule is offered
)
INBOX_MAX_ITEMS = 50  # items the inbox carries; the screen shows PENDING_QUEUE_CAP at a time

# --- Decisions on the module map -----------------------------------------
MAX_MODULES_PER_DECISION = 4  # a decision anchored in more modules is cross-cutting, listed apart
SEARCH_TEXT_CHARS = 160  # how much of a decision's context and choice the map search reads

# --- Model-first mapper ------------------------------------------------
MAPPER_PROMPT_VERSION = "3"
DIGEST_MAX_CHARS = 120_000  # a digest beyond this is not sent whole (large repos: spec/14 §15)
ASSIGN_BATCH_FILES = 45  # files per call when a small model assigns files to named modules
BROAD_MODULE_SHARE = 0.25  # a proposed module claiming more of the source files is flagged
MAX_ROUTES_IN_DIGEST = 400
ROUTE_SCAN_MAX_BYTES = 300_000  # larger source files are skipped when reading route paths
DRIFT_FAIL_SHARE = 0.10  # `map --drift` exits 1 when more of the source files are unplaced
GENERIC_PREFIXES: frozenset[str] = frozenset(
    {
        "index",
        "test",
        "tests",
        "util",
        "utils",
        "base",
        "common",
        "helper",
        "helpers",
        "main",
        "app",
    }
)
FOUNDATIONS_TO_WATCH: tuple[str, ...] = (
    "authentication",
    "users",
    "roles and permissions",
    "organizations or tenants",
    "notifications and email",
    "configuration and platform",
    "files and storage",
    "audit logging",
)
