# SDD-968 — shell-safety-flags contract for entry-point scripts

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-024** (a few scripts lack `set -euo pipefail` without sourcing `common.sh`).
> Mandate module: **E11.M968** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

F-2026-024 flagged that "a few scripts lack `set -euo pipefail` without sourcing `common.sh`" (example: `scripts/webapp/preflight.sh`), and proposed a targeted sweep. Investigation showed the finding's **premise did not hold as an oversight** — every candidate is a deliberate design or a sourced/staged file, not a careless omission:

- **`scripts/build/provision-bake.sh`** uses `set -uo pipefail` **without `-e` by explicit design** — its header says *"NON-FATAL BY DESIGN: `set -uo pipefail` (no -e) and every step ends in…"*; it is the in-image mkosi postinst provisioner where each step handles its own errors. Adding `-e` would break that.
- **`scripts/webapp/preflight.sh`** uses `set -uo pipefail` without `-e` because it is a **fail-counter**: it runs every check, does `fails=$((fails+1))`, and ends with `exit "$fails"`. `-e` would abort on the first failing check before the others run or the count is reported.
- The remaining candidates are **sourced libraries** (`scripts/build/lib/observability.sh` sourced by 61 callers, `logging.sh`, `runtime-profile.sh`, `selfdef-tune.sh`, `scripts/git-hooks/lib/ownership-warn.sh`) — they run under the caller's shell options, and `common.sh` (which they sit beside) already sets `set -euo pipefail` for the run; setting `-e` inside a sourced lib would impose errexit on every caller as a side effect. And one is a **template** (`scripts/claude-code-env/templates/stop-hook-git-check.sh`), an operator-neutralized stub re-staged from the read-only image each session.

Empirically: **0** executable entry-point scripts (excluding libs + templates) ship with *no* safety flags — every one either sources `common.sh` or sets at least `set -uo pipefail`.

## What this SDD does

Rather than force `-e` onto scripts that deliberately omit it (which would introduce bugs), it **locks in the good state** with the correct invariant.

### `tests/lint/test_shell_safety_flags.py` — the contract

`test_entry_points_opt_into_shell_safety` — every executable `scripts/**/*.sh` that is **not** under a `lib/` or `templates/` directory must either source `scripts/build/lib/common.sh` or set a shell-safety flag (`set -e` / `set -u` / `set -o pipefail`). It requires safety flags to be **present** but does **not** mandate `-e` specifically — respecting the two documented non-`-e` designs — so the invariant is "opts into shell safety", not "uses errexit". Guards 91 entry-points; 0 current violations.

Scope: sourced libs are exempt (they run under the caller's options — forcing `-e` there imposes it on every caller); templates are exempt (staged/rendered elsewhere).

## Verification

- Investigation: `provision-bake.sh` carries the "NON-FATAL BY DESIGN" marker; `preflight.sh` has 3 `fails=$((fails+1))` increments + `exit "$fails"`; `ownership-warn.sh`'s own header says "SOURCED, not executed".
- `grep`-sweep of executable entry-points (excl lib/templates) with zero safety flags and not sourcing common.sh → **0**.
- `python3 -m pytest tests/lint/test_shell_safety_flags.py` — **2 passed** (91 entry-points guarded, 0 violations).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Forcing `set -euo pipefail` (with `-e`) everywhere** — two entry points deliberately omit `-e` (non-fatal-by-design + fail-counter); mandating it would break them. The finding's literal wording is superseded by the evidence.
- **Adding flags to sourced libraries** — they inherit the caller's options; `common.sh` is the deliberate flag-setter, the sibling libs deliberately aren't.
- **Editing the neutralized template** — it is re-staged from the read-only image each session; a repo edit wouldn't persist and isn't the durable surface.

## Safety invariants

Adds one read-only lint; changes no script. No crate code, no runtime behavior, no gateway touch. It asserts a property the tree already satisfies and prevents a future regression (a new entry-point with zero fail-fast). R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_shell_safety_flags.py` — the contract
- `scripts/build/lib/common.sh` — the canonical `set -euo pipefail` setter entry-points source
- `scripts/build/provision-bake.sh` / `scripts/webapp/preflight.sh` — the two documented non-`-e` designs
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-024 (source)
- SDD-967 — the sibling hook-hygiene contract (executability + dangling refs)
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
