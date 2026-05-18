# SDD-032 — Helper-library doctrine (E9.M13 / R330)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E9.M13 (mandate decomposition)
> Derived from: SDD-030 (R283 overlay doctrine) + the lived
> practice of R327 + R328 helper modules

## Mission

`scripts/lib/` is now a 4-module library that every operator-pull
script imports from. The contracts of these modules are operator-
stable — consumer scripts spread across `scripts/hardware/`,
`scripts/diagnostics/`, `scripts/network/`, `scripts/lifecycle/`,
`scripts/intelligence/`, etc. depend on the imports never breaking.

SDD-032 codifies the public API + the import-discovery convention
so a future maintainer who refactors `scripts/lib/` sees the
contracts they must preserve.

## The library — four public modules

### 1. `operator_overlay` (R283 / SDD-030)

The read-side helper. Every script that reads operator-tunable
configuration imports:

```python
from operator_overlay import load_with_overlay
```

Public API:
- `load_with_overlay(script_name, defaults, explicit_path=None) -> dict`
- `resolve_overlay_path(script_name, explicit=None) -> Path | None`
- `deep_merge(base, overlay) -> dict`
- `collect_overlay_keys(overlay) -> list[str]`
- `_env_var_name(script_name) -> str` (semi-private; doctrine-test pins it)

Path resolution precedence: explicit > env var
(`$SOVEREIGN_OS_OVERLAY_<NAME>`) > `/etc/sovereign-os/<name>.toml` >
in-source defaults.

### 2. `apply_audit` (R327)

The audit-write primitive + query side. Every script that mutates
state imports:

```python
import apply_audit  # via sys.path.insert(0, scripts/lib)
```

Public API:
- `record_apply(*, verb, round_origin, gates_satisfied, gates_detail,
  what_was_written=None, target_path=None, wrote=False, rc=0,
  audit_path_override=None) -> dict`
- `query(audit_path_override=None, verb=None, wrote_only=False,
  since_epoch=None, limit=None) -> list[dict]`

Audit row schema (operator-stable, JSONL-friendly):
```
schema_version + round + tick_at + tick_at_epoch +
verb + round_origin +
gates_satisfied + gates_detail +
what_was_written + target_path +
wrote + rc + op_user + host
```

Default audit path: `/var/lib/sovereign-os/apply-audit.jsonl`.
Override via env `$SOVEREIGN_OS_APPLY_AUDIT_PATH` or argument.

NEVER raises — audit failure ≠ apply failure.

### 3. `safe_apply` (R328)

The apply-ceremony wrapper. Future mutating verbs import:

```python
from safe_apply import run_apply_safe
```

Public API:
- `evaluate_triple_gate(apply_flag, confirm_flag, env_var_name,
  env_var_value, confirm_flag_label) -> (gates_dict, ok_bool)`
- `check_maintenance_window(window_name, force=False) -> dict`
- `run_apply_safe(*, verb, round_origin, apply_flag, confirm_flag,
  write_fn=None, what_was_written=None, target_path=None,
  env_var_name, env_var_value, confirm_flag_label,
  maintenance_window=None, force=False,
  audit_path_override=None) -> dict`

Result schema:
```
gates + gates_satisfied + maintenance_window + window_check +
would_write + wrote + write_error + rc + audit_row
```

NEVER raises — all failure paths (gate / window / write) return
structured result. Caller decides rc semantics for its CLI.

### 4. `inventory_consult` (R348)

The R317 inventory-catalog cross-binding helper. Every advisor that
wants to surface operator-actionable caveats tagged for itself imports:

```python
from inventory_consult import find_advisor_caveats
```

Public API:
- `find_advisor_caveats(round_id: str) -> list[dict]` —
  returns `[{slot, sku, model, category, caveat, severity}, ...]`
  for catalog entries whose `related_advisor` field contains
  `round_id` (e.g. `"R315"`) AND whose `operator_caveat` is non-null.
  Severity is heuristic: `"warn"` for caveats matching
  `may fail / exceed / instability / drop to`; `"info"` otherwise.
- `caveats_matching(round_id, *, contains_any=None,
  contains_all=None) -> list[dict]` —
  same shape as above, filtered by case-insensitive substring match
  on the caveat string. Convenience for advisors surfacing specific
  sub-warnings (e.g. R315 wants only XMP-stability hits).

NEVER raises — missing catalog file / OS error / malformed module
all return `[]`. Catalog liveness failure NEVER takes an advisor down.

Promoted from R347 inline-pattern (xmp-oc-room-advisor) at R348 when
R252 power-status became the second consumer. Both consumers refactored
to call the helper in the same commit that ships the helper.

Current consumers:
- R315 xmp-oc-room-advisor → surfaces 4-DIMM XMP-stability warning
- R252 power-status → surfaces UPS SMT2200C refurbished/rating caveat
  when UPS reports OnBattery

## Import convention

Every consumer script:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

from operator_overlay import load_with_overlay  # if read-side
import apply_audit                                # if writes audit
from safe_apply import run_apply_safe              # if applies
```

The `parents[2]` count matches the typical `scripts/<axis>/<name>.py`
layout. Scripts at a deeper or shallower depth adjust accordingly.

## NEVER-raise contract

All three helpers honor the NEVER-raise discipline:

| Helper | Failure mode | Recovery |
|--------|--------------|----------|
| `load_with_overlay` | malformed TOML | returns defaults + sets `_parse_error` |
| `record_apply` | OS-write failure | returns row with `_audit_log_wrote=False` |
| `run_apply_safe` | write_fn raises OSError/RuntimeError/ValueError | returns result with `wrote=False`, `write_error` set, `rc=2` |

Consumer scripts treat helper output as data, not exceptions.

## Why scripts/lib/ not a Python package?

Sovereign-os ships these scripts as standalone Python files
(`#!/usr/bin/env python3` with stdlib-only + minimal deps).
Packaging them as an installable package would force operators to
maintain a `pip install`/`venv` posture; the `sys.path.insert(0,
scripts/lib)` convention keeps the surface flat + Debian-13-Base
friendly.

If sovereign-os ever ships a real `pip install sovereign-os`
package, the conversion is mechanical: rename `scripts/lib/` to
`sovereign_os/`, replace `sys.path.insert` blocks with
`from sovereign_os import ...`, update the consumer scripts in a
single migration round.

## L1 lint enforcement

`tests/lint/test_helper_library_doctrine.py` pins:
- The three modules exist at the expected paths
- Each module exposes its declared public API surface
- The NEVER-raise contract is documented in module docstrings
- This SDD-032 file carries the required sections

A future refactor that breaks any of these breaks the lint at
push-time.

## What this SDD does NOT do

- It does NOT lock in implementation details — internal helpers
  (`_flatten`, `_audit_path`, etc.) are private and may change.
- It does NOT force consumer scripts to use ALL three helpers —
  read-only scripts use only `load_with_overlay`; write scripts
  add the others.
- It does NOT prevent new helpers from joining `scripts/lib/` —
  a future round adds a new module + extends this SDD + the lint
  in the same commit.

## Future helper-library evolution

If a fourth helper joins (e.g., `scripts/lib/notify_dispatch.py` —
hypothetical R254 follow-on), the doctrine evolves: new module
section in this SDD + new public-API assertion in the lint +
adoption announced in the next R285 quarterly review.
