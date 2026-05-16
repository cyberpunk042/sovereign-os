# tests/

Five-layer TDD harness for sovereign-os per [SDD-008](../docs/sdd/008-test-harness.md)
and SDD-009 (bootstrap).

## Layers

| Layer | Path | Stack | CI | What it asserts |
|---|---|---|---|---|
| 1 | `schema/` + `lint/` | pure Python (jsonschema + ruff) | every PR; <30s | YAML/JSON schema-conformance; markdown lint; decisions-log sequence; SDD-index consistency; hook script path resolution |
| 2 | `unit/` | pytest | every PR; <2 min | whitelabel render engine; profile mixin merger; kernel config generator (when impl lands) |
| 3 | `chroot/` + `nspawn/` | chroot + systemd-nspawn | label / main; <20 min | per-lifecycle-stage invariants (PRE-INV / INST-INV / FB-INV / REC-INV / DEC-INV per SDD-008) |
| 4 | `qemu/` | QEMU + OVMF | main + label-trigger + nightly | full image boot + inside-VM smoke |
| 5 | `hardware/` | bare-metal SAIN-01 | operator-side; never CI | friction-audit on real hw, throughput, perimeter SIGKILL latency |

## Running locally

```bash
# Layer 1 (schema + lint)
python3 -m pytest tests/schema tests/lint -v

# Layer 2 (unit)
python3 -m pytest tests/unit -v

# Layer 3 (chroot / nspawn)
bash tests/chroot/scaffold.sh sain-01
bash tests/nspawn/scaffold.sh sain-01

# Layer 4 (QEMU)
bash tests/qemu/scaffold.sh sain-01

# Layer 5 (hardware-gated; only on real SAIN-01)
bash tests/hardware/sain-01-friction.sh
```

## Test discovery + naming

- Python: `test_<area>_<subject>.py` (pytest-discovered)
- Shell: `<stage>_<subject>.sh` (operator-invoked)

## Adding tests

Each new script/feature lands with at least one Layer 1 or Layer 2
test alongside (TDD-first per the operator's bar). See SDD-008 for
the per-stage invariants list (PRE-INV-1..4, INST-INV-1..5,
FB-INV-1..7, REC-INV-1..3, DEC-INV-1..3).
