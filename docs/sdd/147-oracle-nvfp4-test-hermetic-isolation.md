# SDD-147 — Oracle NVFP4/BF16 default-selection tests: hermetic runtime-profile isolation

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: `tests/lint/test_oracle_blackwell_nvfp4.py::test_dry_run_explicit_nvfp4_selects_nvfp4_path` + `::test_dry_run_explicit_bf16_selects_bf16_path` failed on any box carrying `/etc/sovereign-os/active-runtime-profile` (this dev box: `high-concurrency-burst`). Operator: "we can fix the failures". Recover band (SDD-147 / E11.M147 per SDD-100).
> Derived from / extends: R455 (E11.M4 — Blackwell-aware Oracle Core quantization). §1g.

## Mission

Make the Oracle Core quantization→model default-selection tests truly hermetic so they exercise the start script's OWN default logic regardless of the box's active runtime profile.

## Problem

`scripts/inference/start-oracle-core.sh` fills an empty `ORACLE_MODEL` from the active runtime profile (R151 — `runtime_profile_override ORACLE_MODEL`, legitimate behaviour). `runtime_profile_active_file` (scripts/build/lib/runtime-profile.sh) resolves the active profile from three sources, in precedence order:

1. `$SOVEREIGN_OS_RUNTIME_PROFILE`
2. `/etc/sovereign-os/active-runtime-profile`
3. `~/.sovereign-os/active-runtime-profile`

The two failing tests set `ORACLE_QUANTIZATION=nvfp4`/`bf16` with an empty `ORACLE_MODEL` and assert the dry-run output names the matching model variant (`…-NVFP4` / `…-BF16`). The test's `_dry_run_env` tried to neutralize the profile by **deleting** source 1 and repointing `$HOME` (source 3) — but source 2 (`/etc/…`) is a system path that cannot be redirected without root. On this box `/etc/sovereign-os/active-runtime-profile` = `high-concurrency-burst`, which pins the oracle model to `DeepSeek-R1-Distill-Llama-70B-FP16` — so the script's default-selection branch never runs, the output names neither NVFP4 nor BF16, and the tests fail. On a clean CI box (no `/etc` profile) they pass — a box-dependent flake, not a script bug.

## Fix (test-only)

`tests/lint/test_oracle_blackwell_nvfp4.py::_dry_run_env` — instead of deleting `$SOVEREIGN_OS_RUNTIME_PROFILE`, **pin it to a deliberately-absent sentinel id** (`__hermetic_test_no_profile__`). Source 1 takes precedence and, being non-empty, short-circuits the `/etc` + `$HOME` file lookups; `runtime_profile_active_file` then resolves `profiles/runtime/__hermetic_test_no_profile__.yaml`, finds no such file, and reports "none active". No ambient profile (env, `/etc`, or `$HOME`) can leak, so the test exercises the script's own default selection on every box. `$HOME` is still repointed as defence-in-depth. The docstring is rewritten to explain the precedence + why deletion was insufficient.

No production code changed — `start-oracle-core.sh` and `runtime-profile.sh` are untouched (their behaviour was correct).

## Verification

- `tests/lint/test_oracle_blackwell_nvfp4.py` — 23 passed (was 2 failed / 21 passed), on this box which carries an active `/etc` runtime profile.
- Full lint suite green.

## On completion

The Oracle NVFP4/BF16 default-selection tests are box-independent: they pass whether or not the host has an active `/etc` runtime profile.

## Cross-references

- `scripts/inference/start-oracle-core.sh` (R455 Blackwell-aware default); `scripts/build/lib/runtime-profile.sh` `runtime_profile_active_file` (the 3-source resolution). SDD-100 — band scheme.
