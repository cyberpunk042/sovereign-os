# SDD-035 — Workload-mode adoption doctrine (E9.M16 / R343)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E9.M16 (mandate decomposition)
> Derived from: R338 workload-mode coordinator + the lived practice
> of R339 (R337 fan-advisor) + R340 (R307 cpu-hotswap) + R341
> (R296 thermal-oc-budget) + R342 (R304 memory-pressure-damper) —
> the 4-shape adoption proof

## Mission

R338 ships the workload-mode coordinator (`idle`,
`inference-ready`, `training`, `oc-burst` — single source of truth
for current operator workload mode). R339-R342 wired 4 downstream
advisors (4 distinct advisor shapes) to read R338 as canonical with
identical structural patterns. SDD-035 codifies the contract so:

- Future advisors adopt the pattern uniformly without each author
  reinventing it
- A L1 lint catches drift across all 5 (current + future) adopters
- The cross-shape pattern surface stays operator-readable for audit

## The contract — every R338 adopter MUST

### 1. Two helper functions

```python
def _read_canonical_mode(cfg: dict) -> tuple[str | None, str]:
    """Read R338 canonical mode. Returns (mode_name, source).
    NEVER raises — graceful on missing / OS error / malformed."""

def _apply_mode_modulation(cfg: dict) -> tuple[dict, str | None, str]:
    """Modulate cfg per canonical mode. Returns (modulated_cfg,
    canonical_mode, source). cfg is COPIED, not mutated."""
```

(R307 cpu-hotswap uses `_derive_pinned_from_workload_mode` for the
governor/EPP shape — equivalent function, same contract.)

### 2. Two overlay knobs

```python
DEFAULTS = {
    # ...other advisor knobs...
    "follow_workload_mode_coordinator": True,
    "workload_mode_overlay_path": "/etc/sovereign-os/workload-mode.toml",
}
```

`follow_workload_mode_coordinator = False` is the operator opt-out.

### 3. A `WORKLOAD_MODE_TO_<SHAPE>` map

```python
WORKLOAD_MODE_TO_<SHAPE>: dict[str, dict[str, Any]] = {
    "idle":           {...per-mode shape..., "rationale": "..."},
    "inference-ready": {...zero-delta default...},
    "training":       {...trades operator-specific param...},
    "oc-burst":       {...transient peak...},
}
```

Per-advisor `<SHAPE>` examples shipped:
- `WORKLOAD_MODE_TO_FAN_DUTY` (R337 — discrete curves)
- `WORKLOAD_MODE_TO_GOV_EPP` (R307 — discrete tuples)
- `WORKLOAD_MODE_TO_MARGIN_DELTA` (R296 — continuous margin deltas)
- `WORKLOAD_MODE_TO_DAMPER_DELTA` (R304 — continuous threshold + step deltas)

Each entry MUST contain a `rationale` string explaining WHY the
mode chose this shape value.

### 4. JSON output fields

Every adopter MUST emit these fields in its `status`/`recommend`
JSON output:

```json
{
  "workload_mode_canonical": "training" | null,
  "workload_mode_source": "R338-canonical" | "<advisor>-overlay" | ...,
  "workload_mode_to_<shape>": {...the full map...},
  ...
}
```

### 5. Precedence rules

Three-tier resolution, highest → lowest:

1. **explicit operator pin** (advisor's own overlay-level knob)
   → source: `"<advisor>-overlay-explicit"` or `"explicit-flag"`
2. **R338 canonical** (workload-mode.toml)
   → source: `"R338-canonical"`
3. **advisor default** (in-source DEFAULTS)
   → source: `"<advisor>-overlay"` (when overlay loaded but R338 absent)
   or `"<advisor>-overlay-no-mode-set"` (when nothing pins it)

### 6. NEVER-raise contract

Inherited from SDD-032 helper-library doctrine. All 4 shipped
adopters honor:

| Failure | Recovery |
|---------|----------|
| workload-mode.toml absent | falls back to advisor overlay |
| workload-mode.toml unreadable | falls back to advisor overlay |
| workload-mode.toml malformed | falls back to advisor overlay |
| unknown mode in workload-mode.toml | source tagged `-unknown-mode`, no modulation |

### 7. Invariants preserved post-modulation

Each advisor's modulation MUST preserve its own physical invariants.
Examples shipped:

- R296: `critical_margin ≤ watch_margin` (CPU); `critical_temp ≥ watch_temp` (GPU)
- R304: `warn_avg10 ≥ 5%`, `crit_avg10 ≥ warn_avg10`, `mild_step ≥ 0.01`
- R307: derived governor must be in `governors_available` cross-cut
- R337: fan duty% bounded [0, 100]

The L1 lint does NOT enforce per-advisor invariants (different
shapes); the per-advisor L3 test does. SDD-035 just requires that
SOMEWHERE post-modulation the invariants are restored.

## Current 4-adopter registry

| Advisor | Round | Shape | Map name |
|---------|-------|-------|----------|
| R337 fan-advisor | R339 | discrete curves | `(implicit via mode catalog)` |
| R307 cpu-hotswap | R340 | discrete (gov, EPP) tuples | `WORKLOAD_MODE_TO_GOV_EPP` |
| R296 thermal-oc-budget | R341 | continuous margin deltas | `WORKLOAD_MODE_TO_MARGIN_DELTA` |
| R304 memory-pressure-damper | R342 | continuous threshold + step | `WORKLOAD_MODE_TO_DAMPER_DELTA` |

## L1 lint enforcement

`tests/lint/test_workload_mode_adoption_doctrine.py` pins:

- R338 workload-mode coordinator script + the 4 named modes exist
- Each adopter script declares `follow_workload_mode_coordinator`
  + `workload_mode_overlay_path` in DEFAULTS
- Each adopter script defines `_read_canonical_mode` (or
  `_derive_*_from_workload_mode` for derive-shape advisors)
- Each adopter script emits `workload_mode_canonical` + 
  `workload_mode_source` fields in its build_report
- This SDD-035 file carries required sections + cross-links all
  4 current adopter rounds (R339, R340, R341, R342)

A future advisor that adopts R338 adds its script to the lint's
`ADOPTERS` list; the lint then auto-verifies the contract on it.

## What this SDD does NOT do

- It does NOT lock in per-advisor map SHAPES — each advisor models
  the mode → action in its own type (curves / tuples / deltas).
- It does NOT freeze the 4-mode catalog — a future round could add
  a 5th mode (e.g. `dev-build`) by updating R338 + each adopter's
  map.
- It does NOT prevent OPT-OUT — `follow_workload_mode_coordinator
  = False` lets operator isolate any adopter from canonical.
- It does NOT mandate mutation — every shipped adopter is READ-ONLY
  (resolves a derived value); future apply-side adopters use R328
  safe_apply ceremony orthogonally.

## Future-quarter adoption candidates

- **R293 power-profiles** — different shape (lifecycle profiles vs
  CPU performance profile); adoption requires modulation of which
  lifecycle profile to recommend per mode (e.g. training → "thermal-
  budget-throttle" profile; idle → "ac-loss-graceful-suspend").
- **R315 xmp-oc-room-advisor** — natural adopter: training mode →
  budget includes sustained-load PSU draw; idle → only single-GPU
  draw counted.
- **R293 / R295 etc.** — future round candidates as new advisors
  ship; each follows the SDD-035 contract.

## Doctrine evolution

If the operator adds a new mode (e.g., `dev-build`), the workflow:

1. Update R338 MODES list (1 entry add)
2. Update each adopter's WORKLOAD_MODE_TO_<SHAPE> map (per-advisor)
3. Update R338 affected-advisors registry (if entries reference modes)
4. Update R339-R342 L3 tests to cover the new mode
5. The L1 lint does NOT need updating (it doesn't enforce mode list)

R285 quarterly review captures the doctrine state + adoption tally.
