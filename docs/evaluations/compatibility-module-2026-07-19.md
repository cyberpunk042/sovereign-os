# Evaluation + design record — the cross-system compatibility module

> Operator directive 2026-07-19 (verbatim, sacrosanct): *"I think we need a
> compatibility module if not already present which talk about cross-modules
> or cross-features compatibility and suggest or even force something else
> off in order to enable one thing, or offer the possibility to chose one of
> many things. like the u64 bit control strategy for example. lets evaluate
> this together."*

## Was it already present? (inventory, empirically verified 2026-07-19)

| Mechanism | What it covers | What it lacks |
|---|---|---|
| `config/control-systems.yaml` (SDD-045 §4) | 47 registered on/off/mode/profile systems; `kind: mode/profile` encodes pick-one *within* one system; dashboard control rail renders from it | No relation fields — no cross-system requires/conflicts |
| `avx-mode` (SDD-600) + M002 bit-machine | One-of-four exclusive master switch; the u64 control word ("policy becomes bits") the operator cited | Exclusivity only within the switch |
| workload-mode coordinator (R338/R345) | power-profiles / fan / memory-damper / thermal-budget follow workload-mode | Hard-coded per script; suggest-tier only; not declarative |
| heat-oc-autothrottle / psu-oc-mode | Real force-off behavior in the power domain | Domain-local, imperative |
| profile `pcie_constraints` | Declarative constraints WITH severity (blocker) | Hardware-only |

**Verdict: not present.** Cross-module compatibility existed only as islands —
no central declarative layer, no resolver, no one place that can say "to
enable X, Y must go off."

## Operator-confirmed design decisions (2026-07-19)

| Decision | Choice |
|---|---|
| Representation | **YAML → u64 masks**: `config/compatibility.yaml` is the authoring source of truth; `scripts/operator/compat.py` compiles features to bit indexes + u64 mask words — the M002 strategy applied to configuration (requires = subset test, conflicts = AND, one_of = popcount) |
| Enforcement | **Per-rule severity** (`suggest` / `warn` / `force`), per the `pcie_constraints` severity precedent + strictness graduation |
| Scope v1 | **The control-systems registry** (47 systems + options). Provisioning modules + full feature space are explicit follow-ups |

## What shipped

- `schemas/compatibility.schema.yaml` — rule shape: `requires` /
  `conflicts_with` / `forces_off` / `one_of` × severity × **mandatory
  reason + remediation** (hook doctrine: no black-box blocks)
- `config/compatibility.yaml` — 5 grounded starter rules (C001–C005),
  incl. the operator's force-off case: `cost-policy=halt-cloud` forces
  the four `*-backend=anthropic` systems off
- `scripts/operator/compat.py` + `sovereign-osctl compat
  {list,compile,check,explain,why}` — 92 features → 2 × u64 words,
  13 implicit pick-one groups emitted structurally from `kind:
  mode/profile` (nothing to author for "choose one of many")
- `tests/lint/test_compatibility_rules.py` — 7 gates: schema
  conformance, registry-reference resolution, reason/remediation
  present, unique ids, bit-universe roundtrip, severity semantics
  end-to-end, CLI rc contract

## rc contract

`compat check` returns 0 on clean or suggest-only findings; 1 on any
`force` violation (or `warn` under `--strict`); 2 on unknown
system/option or usage error.

## Follow-ups (operator-gated, in rough order)

1. **Pre-change gate** — control-mutating osctl verbs call `compat
   check` on the proposed change (suggest prints, force refuses with
   reason + remediation + documented bypass env).
2. **Dashboard rail integration** — the control-surface component greys
   out / annotates incompatible options from `compat compile --json`
   (then move the `compat` verb from `cli_only` to a coverage slug).
3. **Scope v2** — provisioning modules (selfdef / ghostproxy / openclaw /
   open_computer / tetragon scope / VFIO role), where QEMU-vs-VFIO-class
   collisions live.
4. **Rule growth** — per-rule operator review; candidates noted during
   the oracle-alternatives work: oracle-hybrid trial (:8086) vs
   Oracle/Logic tier RAM+VRAM budgets; DFlash vs DSpark on the same
   draft card.
