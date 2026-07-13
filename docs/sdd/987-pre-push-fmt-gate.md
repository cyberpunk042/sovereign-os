# SDD-987 — local pre-push `cargo fmt` gate: unformatted Rust can't reach the remote (F-2026-095)

> Status: draft
> Owner: operator-directed 2026-07-13 ("we continue"); agent-authored.
> Closes: **F-2026-095** (MED) — root-cause half (the fmt violations themselves were fixed in the audit's PR).
> Mandate module: **E11.M987**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

The July 11–12 intelligence-layer arc landed with **52 `cargo fmt` violations**
(`sovereign-coat` 39, `sovereign-gatewayd` 13) — not because CI lacks a fmt gate,
but because the arc was authored on a **long-lived branch that never opened a PR**,
so it bypassed CI entirely until the audit (F-2026-095). The violations were
mechanical and already fixed; this closes the **root cause** — the process hole
that let unformatted Rust accumulate off-CI — by mirroring the CI gate locally at
push time.

## What this SDD builds

**`scripts/git-hooks/pre-push`** — runs the CI-exact **`cargo fmt --all --check`**
(the same command as `.github/workflows/test.yml`) before a push reaches the
remote:

- reads cargo's exit code **directly** (never through a pipe — a pipe reports the
  `tail`/`grep` exit and masks a fmt failure; a lesson from this session's own CI
  debugging);
- on violations, **blocks the push** and prints `cargo fmt --all` as the one-line
  fix (+ the `--no-verify` bypass);
- **skips gracefully** when the Rust toolchain (or the rustfmt component) is
  absent, so docs-only machines are never blocked;
- installs automatically via `scripts/git-hooks/install.sh` (its glob picks up any
  hook in the dir).

**`tests/lint/test_fmt_hook_contract.py`** — keeps the hook and CI in **lockstep**:
the hook exists + is executable + is valid bash + runs `cargo fmt --all --check`,
AND CI still runs that exact command. If either side changes the gate, the test
fails — so the local gate can never silently stop matching CI.

## Why pre-push (not pre-commit)

Pre-push mirrors CI's *push-time* gate exactly and fires far less often than the
operator's frequent commits, so it adds no per-commit latency; `cargo fmt --check`
is parse-only (no compile), so a whole-workspace check is seconds. The existing
`pre-commit` hook stays focused on the pytest/profile/shellcheck gate.

## Verification (real, observed)

- `bash -n scripts/git-hooks/pre-push` clean; hook executable.
- `cargo fmt --all --check` on the current tree → **exit 0** (the hook allows the
  push).
- `tests/lint/test_fmt_hook_contract.py` — **4 passed** (hook exists/executable,
  valid bash, runs the CI gate, CI still runs it).
- `test_hook_hygiene.py` + `test_scripts_health_baseline.py` + `test_shell_safety_flags.py`
  still green with the new hook (8 passed).
- `ruff` clean.

## Non-goals

- The other half of F-2026-095 (fixing the 52 violations) — already done in the
  audit's PR; this is the recurrence-prevention half.
- Gating anything beyond fmt (clippy/test) at push time — fmt is the cheap,
  deterministic, always-safe check; heavier gates stay in CI + the opt-in
  pre-commit full gate.

## Safety invariants

One new hook + one new `tests/lint/` file + README + this SDD + registries. No
gatewayd/cockpit/`unsafe`/crate edits. The hook only ever *reads* (fmt --check)
and blocks a push; it never rewrites code. Bypassable with `--no-verify`.
R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/git-hooks/pre-push` — the hook · `scripts/git-hooks/README.md` — its docs
- `tests/lint/test_fmt_hook_contract.py` — the hook↔CI lockstep contract
- `.github/workflows/test.yml` — the `cargo fmt --all --check` CI gate this mirrors
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-095
- `docs/handoff/008-july-intelligence-layer-arc.md` — the arc whose off-CI branch caused the drift
