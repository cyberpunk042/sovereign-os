# SDD-148 — test_trinity profile-switch assertions: reconcile stale wording drift

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: `tests/nspawn/test_trinity.sh` failed 3/45 (`profile show missing-gate`, `profile switch`, `profile switch missing-gate`) — the CI "layer 3 — stage acceptance (nspawn-style)" gate red on PR #118. Pre-existing on `main` (unrelated to SDD-147). Operator: "we can fix the failures". Recover band (SDD-148 / E11.M148 per SDD-100).
> Derived from / extends: commit 4ab38148 (D-21 D21-2 — make orchestration/user profiles apply-able via osctl), which generalized profile messaging to families. §1g.

## Mission

Get the layer-3 nspawn acceptance gate green by reconciling `test_trinity.sh`'s stale expected wording with the current, authoritative `sovereign-osctl` output.

## Problem

`sovereign-osctl`'s profile messaging was generalized to profile *families* (coding-focus / thinking-focus / hybrid / … alongside runtime) — commit 4ab38148. Its messages now consistently say "profile" (not "runtime profile") across **9 call sites**:

- `active profile set to: <id>` / `active profile set to: <id> (family: <fam>)`
- `no such profile: <id>` (×7)

`tests/nspawn/test_trinity.sh` was the **sole straggler** still grepping the old wording, so 3 gate-checks failed even though the commands behave correctly (right exit codes, sensible errors):

| Test grepped (stale) | osctl emits (current, authoritative) |
|---|---|
| `no such runtime profile` (×2 — profile show/switch missing-gate) | `no such profile: <id>` |
| `active runtime profile set to: high-concurrency-burst` | `active profile set to: high-concurrency-burst (family: runtime)` |

The exit codes were already correct (1 for missing, 0 for switch) — only the substring greps were stale. No other test references either wording; the impl wording is authoritative (9 consistent call sites).

## Fix (test-only)

`tests/nspawn/test_trinity.sh` — update the 3 stale greps to the current wording: `no such runtime profile` → `no such profile` (×2), `active runtime profile set to:` → `active profile set to:` (substring match, so the `(family: runtime)` suffix is fine). No production code changed — `sovereign-osctl` is authoritative and untouched.

## Verification

- `tests/nspawn/test_trinity.sh` — **45/45 passed** (was 42/45). The other layer-3 nspawn suites (test_hooks 21/21, test_audit_customization 13/13) were already green.
- Full pytest lint suite unaffected (bash nspawn test only).

## On completion

The layer-3 nspawn acceptance gate is green; `test_trinity.sh` tracks the current osctl profile-family wording.

## Cross-references

- `scripts/sovereign-osctl` (profile messaging, 9 call sites — authoritative); commit 4ab38148 (family generalization). SDD-147 (sibling test-drift reconciliation — oracle NVFP4); SDD-100 — band scheme.
