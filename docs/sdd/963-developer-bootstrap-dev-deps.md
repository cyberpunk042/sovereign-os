# SDD-963 — developer bootstrap: single-source dev deps + pyc hygiene + README prerequisites

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-022** (pytest never installed locally); **F-2026-056** (dev-deps bootstrap missing — same root cause); **F-2026-026** (`__pycache__` cruft); **F-2026-055** (README omits the Rust 1.89 pin).
> Mandate module: **E11.M963** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

Four small dev-experience findings that all share one root: **a fresh clone can't reach a working test/lint loop, and CI's Python deps were declared in four places instead of one.**

- **F-2026-022 / F-2026-056** — `make lint`/`unit`/`test`/`ci`/`dashboards-lint` all run `python3 -m pytest`, but nothing installed pytest locally. `setup.sh` only *verified* `yaml`+`jsonschema` (not pytest) and told you to `apt install`/`pip install` by hand. CI installed `pytest pyyaml jsonschema` with an **inline list repeated in four jobs** — a set that could silently drift from whatever a developer happened to have.
- **F-2026-026** — `__pycache__/` dirs litter `scripts/*/` in the working tree (correctly gitignored, but noise); no `make` target cleaned them.
- **F-2026-055** — README prerequisites never mentioned that the `crates/` intelligence layer needs **Rust 1.89** (edition 2024) via rustup, while Debian stable ships 1.85.

## What this SDD builds

### 1. `requirements-dev.txt` — the ONE dev-dependency list

Root file naming the three packages the harness needs (`pytest`, `pyyaml`, `jsonschema`), with a header explaining it is the single source that both `make dev-deps` and every CI job install from.

### 2. `make dev-deps` + a friendly guard

- `make dev-deps` → `python3 -m pip install -r requirements-dev.txt` (fresh-clone bootstrap).
- `_require-pytest` guard target: `lint`, `unit`, `dashboards-lint` now depend on it, so a clone without pytest gets **"run `make dev-deps`"** instead of a raw `ModuleNotFoundError` (and `test`/`ci`, which chain `lint`+`unit`, inherit the guard).
- `setup.sh` now checks pytest too and points its remediation at `make dev-deps`.

### 3. `make clean-pyc` + fold into `clean`

`make clean-pyc` removes `__pycache__/` dirs + `*.pyc`; `make clean` now calls it. F-2026-026 closed functionally (the sweep cleared all in-tree `__pycache__` dirs).

### 4. CI single-sourced

The four inline `pip install pytest pyyaml jsonschema` in `.github/workflows/test.yml` (layer 1, layer 1b gates, layer 2, layer 3) become `pip install -r requirements-dev.txt`. One list, four consumers.

### 5. README prerequisites

Python line now points at `make dev-deps`; a new **Rust 1.89** paragraph names `scripts/install/rust-toolchain.sh` (rustup, user-level, never apt; also run by `make provision`) — closing F-2026-055.

### 6. `tests/lint/test_dev_deps_single_source.py` — the drift contract

Fails CI if: `requirements-dev.txt` goes missing or stops covering `{pytest, pyyaml, jsonschema}`; any CI job reintroduces an inline `pip install pytest|pyyaml|jsonschema` instead of `-r requirements-dev.txt`; `make dev-deps` disappears or stops installing from the file; or the `_require-pytest` guard is lost from the pytest-invoking targets. So the local dev env and the CI env can never silently diverge again — the same self-maintaining discipline as the island register (SDD-955), route-parity (SDD-956), and binaries-doc (SDD-962) contracts.

## Verification

- `python3 -m pytest tests/lint/test_dev_deps_single_source.py` — 5 passed.
- `make clean-pyc` → in-tree `__pycache__` count 0 after run.
- `make _require-pytest` passes through when pytest present; the guard's shell path prints the "run `make dev-deps`" hint when the import fails.
- `make -n dev-deps` → `python3 -m pip install -r requirements-dev.txt`.
- test.yml: 4/4 install lines now `-r requirements-dev.txt`, 0 inline triple installs; `ruff` install (a different dep) left inline as intended.
- Full `tests/lint` + `tests/schema` green; `ruff` clean.

## Non-goals

- **Pinning the dev deps to exact versions** — kept unpinned to match the historical CI behaviour (latest on the runner); a future SDD can pin `requirements-dev.txt` for reproducible dev environments.
- **A `requirements.txt` for the shipped image** — this file is dev/test-only; runtime Python deps (operator APIs) are a separate surface.
- **`ruff` into requirements-dev.txt** — ruff is a standalone linter installed in its own job on a different Python; the contract deliberately scopes to the pytest/pyyaml/jsonschema harness triple.
- **The `make install` unit-fleet split (F-2026-051)** and **ARCHITECTURE.md staleness (F-2026-053)** — sibling system/docs findings, tracked separately.

## Safety invariants

Build-tooling + docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. `make dev-deps` installs into the operator's own Python (never root-privileged, no apt). The CI change is install-source-only; the installed set is byte-identical to before. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `requirements-dev.txt` — the single source
- `Makefile` — `dev-deps`, `clean-pyc`, `_require-pytest` targets
- `.github/workflows/test.yml` — the four single-sourced installs
- `scripts/setup.sh` — pytest check + `make dev-deps` remediation
- `README.md` — Python `make dev-deps` + Rust 1.89 prerequisite paragraphs
- `tests/lint/test_dev_deps_single_source.py` — the drift contract
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-022, F-2026-056, F-2026-026, F-2026-055 (sources)
- SDD-955 / SDD-956 / SDD-962 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
