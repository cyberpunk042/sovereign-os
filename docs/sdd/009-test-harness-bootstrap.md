# SDD-009 — TDD harness bootstrap (Plan-agent PR 10)

> Status: **accepted** (scaffold + first passing tests shipped)
> Owner: operator-supervised
> Last updated: 2026-05-16

## What this ships

Per SDD-008 (harness specification), this PR ships the scaffold + first
passing Layer 1 + Layer 3 tests:

### tests/ tree
- `tests/README.md` — overview + how to run each layer
- `tests/schema/test_profile_schema_conformance.py` — every profile validates against `schemas/profile.schema.yaml` + per-profile semantic checks (sain-01 tank/context sync=always; VFIO companion present; M.2_2 blocker declared)
- `tests/schema/test_whitelabel_schema_conformance.py` — every whitelabel validates + legal-floor enforcement + operator-verbatim motd present in default
- `tests/lint/test_decisions_log_sequence.py` — D-NNN monotonic + Q-NNN presence
- `tests/lint/test_sdd_index_consistency.py` — bidirectional SDD/INDEX consistency
- `tests/lint/test_hook_script_paths.py` — every profile-referenced hook script exists + is executable
- `tests/chroot/scaffold.sh` — Layer 3 chroot harness scaffold
- `tests/nspawn/scaffold.sh` — Layer 3 nspawn scaffold
- `tests/qemu/scaffold.sh` — Layer 4 QEMU scaffold (bridges to build/09-image-verify.sh)

### CI workflow
- `.github/workflows/test.yml` — runs Layer 1 (pytest schema + lint) + shellcheck on every PR

### What's NOT in this PR (Stage 2+)
- Layer 2 unit tests for whitelabel render engine, profile merger, kernel config gen — added alongside their bodies (some already shipped; tests follow when test harness has examples to assert against)
- Layer 3 substantive chroot/nspawn tests per the per-stage invariants in SDD-008 (PRE-INV / INST-INV / FB-INV / REC-INV / DEC-INV)
- Layer 4 substantive QEMU inside-VM assertions (require guest-agent integration)
- Layer 5 hardware-conformance tests (require real SAIN-01)

## Stage Gate 5 closure

With this PR merged: foundation phase complete. Stage 2 build scripts
already started landing (see scripts/build/01..09 + scripts/hooks/*).
Stage 2+ adds substantive Layer 2/3/4 test bodies alongside each
script delta.

## Cross-references

- SDD-008 (harness specification): `docs/sdd/008-test-harness.md`
- SDD-010 (Stage 2 stub): `docs/sdd/010-stage-2-stub.md`
- Plan-agent macro-arc § PR 10: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
