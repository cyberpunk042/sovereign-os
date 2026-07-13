# SDD-966 — per-unit systemd coverage contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-054** (~41 of 111 units had no name-specific test).
> Mandate module: **E11.M966** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The 111 systemd units are hardened in aggregate (`test_sovereign_systemd_fleet_hardening.py` etc.) and ~70 unit names appear in bespoke tests, but **~41 units had no name-specific assertion** — so a single orphaned (nobody-enables-it) or malformed (service with no `ExecStart`, timer with no schedule) unit could slip through. The install-coverage contract (SDD-964) proved the units' `ExecStart` scripts exist and install-wire; this SDD gives **every unit its own coverage case**.

## What this SDD builds

### `tests/lint/test_systemd_unit_coverage.py` — a per-unit, dynamically-parametrized contract

`pytest.mark.parametrize` over every `systemd/system/*.{service,timer,target}` (generated from the listing, so new units are covered automatically — the finding's "cheap dynamic parametrization"). Each unit gets two name-specific cases:

- **`test_unit_is_reachable[<unit>]`** — the unit is not a dead file: it has an `[Install]` section (directly enableable), OR it is a `.service` paired with a same-stem `.timer` (timer-triggered), OR it is named in another unit's dependency directive (`Wants`/`Requires`/`Before`/`After`/`PartOf`/`BindsTo`/`WantedBy`/…), OR it is referenced in `config/bootstrap/phases.yaml` or a `scripts/install/*.sh` installer.
- **`test_unit_is_structurally_valid[<unit>]`** — a `.service` has `[Service]` + an `Exec*`; a `.timer` has `[Timer]` + a schedule (`OnCalendar`/`OnBootSec`/`OnUnitActiveSec`/…); a `.target` has `[Unit]`.

So an orphaned unit (the F-2026-021 pattern, at the unit level) or a malformed unit fails CI with a name-specific test id pointing straight at it. It **complements** SDD-964: install-coverage checks the units' scripts exist + install-wire; unit-coverage checks each unit is reachable + well-formed.

## Verification

- `python3 -m pytest tests/lint/test_systemd_unit_coverage.py` — **223 passed** (111 reachability + 111 validity + 1 non-empty guard); **0 orphans, 0 malformed** across the fleet.
- Each unit has a distinct parametrized id (e.g. `test_unit_is_reachable[sovereign-zfs-scrub.timer]`).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Runtime enable-state / activation** — this is static-file coverage (reachable + well-formed); actually enabling units on a booted box is the operator's `systemctl` step (SDD-964 non-goal, unchanged).
- **Per-unit hardening posture** — already covered by `test_systemd_hardening_posture.py` / `test_sovereign_systemd_fleet_hardening.py`; this contract is about coverage completeness, not the hardening rules themselves.
- **The two-prefix / install-path doctrine** — that is SDD-964's contract; this one is orthogonal.

## Safety invariants

Read-only lint only — no unit files changed, no crate code, no runtime behavior, no gateway touch. It asserts properties of units the repo already ships; invents nothing. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_systemd_unit_coverage.py` — the per-unit contract
- `tests/lint/test_systemd_install_coverage.py` (SDD-964) — the complementary install-coverage contract
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-054 (source); F-2026-021 (the orphaned-hook sibling, the same pattern at the script level)
- SDD-964 — the sibling systemd contract; SDD-955 / SDD-962 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
