# Test layers + invariants

Per SDD-008. 5-layer pyramid; 73 tests passing today (Layer 1 + Layer 2).

## Layer 1 — Schema/lint (<30s)

| File | Asserts |
|---|---|
| `tests/schema/test_profile_schema_conformance.py` | Every profile validates; sain-01-specific invariants (sync=always on tank/context, vfio_companion present, m2_2_empty blocker declared) |
| `tests/schema/test_whitelabel_schema_conformance.py` | Every whitelabel validates; legal-floor pattern check; operator-verbatim motd present |
| `tests/lint/test_decisions_log_sequence.py` | D-NNN monotonic + gap-free; Q-001, Q-017, Q-019 present |
| `tests/lint/test_sdd_index_consistency.py` | Bidirectional SDD ↔ INDEX consistency |
| `tests/lint/test_hook_script_paths.py` | Every profile-referenced hook script exists + executable |

## Layer 2 — Unit (<2 min)

| File | Asserts |
|---|---|
| `tests/unit/test_router_classify.py` | 5-rule deterministic routing in `scripts/inference/router.py` (ternary → Pulse; code/math → Oracle; long ctx → Oracle; JSON-mode → Logic; default → Logic; priority tests) |
| `tests/unit/test_whitelabel_render.py` | All 7 strategies in `scripts/whitelabel/render.py`; legal-floor enforcement; compliance-mismatch detection |
| `tests/unit/test_profile_merger.py` | Q-002 hybrid merge: scalar precedence; list dedup; map deep-merge; deny-list strip; cycle detection; mixin scalar-conflict raises |

## Layer 3 — Stage acceptance (chroot + systemd-nspawn; 2–10 min)

Scaffolds: `tests/chroot/scaffold.sh` + `tests/nspawn/scaffold.sh`. Substantive per-stage invariants land alongside their script bodies at Stage 2+ (per SDD-008 PRE-INV-1..4, INST-INV-1..5, FB-INV-1..7, REC-INV-1..3, DEC-INV-1..3).

## Layer 4 — Integration (QEMU; 10–30 min)

`tests/qemu/scaffold.sh` bridges to `scripts/build/09-image-verify.sh`. Full inside-VM assertions require guest-agent integration; ships at Stage 2+.

## Layer 5 — Hardware-conformance

`tests/hardware/` (empty; runs only on real SAIN-01 once procured per Q-009).
