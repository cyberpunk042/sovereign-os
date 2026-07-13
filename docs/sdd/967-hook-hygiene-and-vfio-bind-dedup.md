# SDD-967 — hook hygiene: delete the legacy vfio-bind duplicate + executability & dangling-reference contracts

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-021** (orphaned `vfio-bind-3090.sh`); **F-2026-023** (glob-dispatch depends on the +x bit).
> Mandate module: **E11.M967** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

Two hook-hygiene findings, both about the ways a hook can silently do the wrong thing:

- **F-2026-021** — `scripts/hooks/post-install/vfio-bind-3090.sh` was flagged as orphaned (its sibling `vfio-bind-4090.sh` is wired into `sovereign-vfio-bind.service`, `config/bootstrap/phases.yaml`, and 8 docs). Investigation resolved the ambiguity decisively: the two scripts are **byte-identical except the self-naming comment on line 2** (`diff` shows only that line differs), both read the PCI IDs from the profile (no GPU-specific logic), and the build-configurator's own entry called `vfio-bind-3090` a *"legacy name"* that *"binds the 4090"*. So it is not a 3090-specific alternative to wire — it is a **legacy-named duplicate to delete**.
- **F-2026-023** — `scripts/build/orchestrate.sh` dispatches pre-install hooks via `find … -type f -executable`; a hook that loses its `+x` bit is silently skipped with no error.

## What this SDD does

### 1. Delete the legacy duplicate + repoint its one referrer

- Removed `scripts/hooks/post-install/vfio-bind-3090.sh` (`git rm`). The canonical, profile-driven `vfio-bind-4090.sh` — wired in `phases.yaml`, `sovereign-vfio-bind.service`, and the docs — is unchanged.
- The **only** source referrer was the build-configurator (`webapp/build-configurator/index.html`), which listed `vfio-bind-3090` as its single vfio-bind build-step (self-noting the legacy name). Repointed the step id + its description-map key to `vfio-bind-4090` and dropped the "legacy name" wording. After the change, no source file references the deleted hook.

### 2. `tests/lint/test_hook_hygiene.py` — two contracts

- **`test_all_hooks_executable`** (F-2026-023) — every `scripts/hooks/**/*.sh` has its executable bit, so `orchestrate.sh`'s `find -executable` dispatch can never silently drop one.
- **`test_no_dangling_hook_path_references`** — every `scripts/hooks/**/<name>.sh` PATH in the **dispatch wiring** (`config/bootstrap/phases.yaml` + the systemd units) resolves to a file that exists. This is exactly the failure the SDD-967 deletion could have caused (a hook removed while the wiring still points at it), now impossible. Scoped to the wiring surfaces on purpose: prose docs legitimately mention hook paths illustratively (a tutorial `my-hook.sh`), as planned work, or historically (this repo's own findings ledger names the deleted hook), so the dangling check covers where a dangling path is a real install/boot bug, not documentation.

## Verification

- `diff scripts/hooks/post-install/vfio-bind-{3090,4090}.sh` (pre-deletion) — identical but the self-naming comment.
- `grep -rl vfio-bind-3090` (excluding `target/`, `.git/`, the ledger) — **0 source references** after the deletion + webapp repoint.
- `python3 -m pytest tests/lint/test_hook_hygiene.py` — **3 passed** (hooks exist; all executable; 30 wiring hook-paths resolve, incl. `vfio-bind-4090.sh`, 0 dangling).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Wiring a real 3090-specific hook** — there is none; the script was a profile-driven duplicate. A future genuinely-different GPU-bind hook would be its own addition.
- **A per-hook dispatch-coverage lint** (every hook is reached by some phase) — glob-dispatched hooks aren't name-wired, so that check is fragile; this SDD covers executability + no-dangling-wiring, which are the two silent-failure modes the findings named.
- **The +x lint replacing orchestrate.sh's runtime `find -executable`** — the dispatch is unchanged; the lint is a repo-time guard so a non-+x hook is caught in CI, not silently at install.

## Safety invariants

Deletes one byte-identical duplicate script + repoints its single webapp referrer; adds a read-only lint. No crate code, no runtime behavior, no gateway touch. The canonical `vfio-bind-4090.sh` and all its wiring are untouched; the build-configurator now points at the real, existing, wired hook. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/hooks/post-install/vfio-bind-4090.sh` — the canonical, retained hook
- `webapp/build-configurator/index.html` — the repointed build-step
- `tests/lint/test_hook_hygiene.py` — the executability + dangling-reference contracts
- `scripts/build/orchestrate.sh` — the `find -executable` dispatch the +x contract guards
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-021, F-2026-023 (sources)
- SDD-964 / SDD-966 — the sibling systemd install + unit-coverage contracts
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
