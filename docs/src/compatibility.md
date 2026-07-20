# The compatibility module — rules, u64 bit-machine, gate, pane

> Operator directive 2026-07-19 (verbatim, sacrosanct): *"I think we need
> a compatibility module if not already present which talk about
> cross-modules or cross-features compatibility and suggest or even
> force something else off in order to enable one thing, or offer the
> possibility to chose one of many things. like the u64 bit control
> strategy for example."*
>
> Follow-ons 2026-07-20 (verbatim): *"its in the shared component"* ·
> *"if something is off you will have a badge in the header that allow
> you to redisplay the pane if you dismissed it"* · *"you need to
> identify what is Not-compatible with other things. like the u64
> custom bits control"*.

## What it is

One registry of **cross-system compatibility relations** over the
control-systems registry, compiled to u64 mask words (the M002
"policy becomes bits" strategy applied to configuration), enforced at
every mutation point and surfaced in the shared cockpit component.

| Piece | Where |
|---|---|
| Rules (source of truth) | `config/compatibility.yaml` (schema: `schemas/compatibility.schema.yaml`) |
| Compiler / resolver | `scripts/operator/compat.py` |
| CLI | `sovereign-osctl compat {list, compile, check, explain, why}` |
| Exec-rail pre-change gate | `scripts/operator/_action_exec.py` (`execute()`) |
| Read-only web payloads | `GET /api/control/compat` (pane) · `?control_id=X` (per-option preview) on the control-exec-api |
| The ⚖ pane + header badge | shared app-shell component (`webapp/_shared/app-shell-snippet.html`) — every panel |
| Lint | `tests/lint/test_compatibility_rules.py` + `tests/lint/test_compat_pre_change_gate.py` |

## The rule model

Four verbs — `requires` (all targets must also be active),
`conflicts_with`, `forces_off` (the operator's *"force something else
off in order to enable one thing"* — reported as the things to turn
off), `one_of` (cross-system exclusivity). Every rule carries
**reason + remediation** (the hook doctrine: no black-box blocks) and
**refs** grounding it. Three severities:

| Severity | Effect |
|---|---|
| `suggest` | printed, never gates |
| `warn` | printed prominently; gates only under `check --strict` |
| `force` | fails `check` (rc=1); the exec-rail gate **refuses** with reason + remediation |

Every `kind: mode`/`profile` control is an **implicit pick-one group**
— the compiler emits a u64 exclusivity mask per such system (that is
the *"offer the possibility to chose one of many things"* made
structural — e.g. `avx-mode` custom/builtin/hybrid/off).

**Scope v2 — provisioning**: `profiles/*.yaml` + `profiles/mixins/`
join the universe as two virtual systems (`provisioning-profile`
pick-one + `provisioning-mixin`), with implicit per-profile `requires`
derived from each profile's own declared `mixins:` list.

## The bit-machine view

`compat compile` shows the compiled universe: every feature →
a stable bit index, every rule → cond/target u64 mask words.
Validation is pure bitwise: `requires` is a subset test,
`conflicts_with`/`forces_off` an AND, `one_of` a popcount.

## The pre-change gate (exec rail)

Every `execute()` on the control-exec rail overlays the proposed
change on the box's best-effort **current** state (single-value
`state_path` files + `$SOVEREIGN_OS_COMPAT_CURRENT` overrides;
`$SOVEREIGN_OS_COMPAT_STATE=off` for hermetic runs) and evaluates the
rules:

- a **force** finding the change *introduces* → HTTP 409 with the
  rule's reason + remediation; per-call audited override
  `args={"compat_override": "true"}`; metric outcomes
  `compat-reject` / `compat-override`;
- **pre-existing** findings (already tripped by current state alone)
  ride along labeled — one bad state never bricks unrelated actions,
  and the remediation actions themselves stay executable;
- **warn/suggest** findings attach to the result without blocking;
- `$SOVEREIGN_OS_COMPAT_GATE=off` disables; an unreadable registry
  degrades OPEN — the rail never dies with the gate.

A compat-gate refusal also emits through **notifykit** (the
`compat-gate` trigger, when `/etc/sovereign-os/notifykit.toml`
exists) — same pattern as the `stage-gate` trigger.

## The ⚖ pane + header badge (shared component)

Header ⚙ → **Compatibility → Inspect…**, on every panel:

- **Live state verdict** — the rules the box's current state trips
  RIGHT NOW;
- **Preview a control** — the *not-compatible-with* drill-in: every
  rule touching the selected control (the `why` view), its pick-one
  exclusivity (the u64 mask), and the per-option gate verdict
  (⛔ force / ⚠ warn / ✓ clean);
- **All rules** with severity, when→targets, reason, remediation;
- **Header badge `⚖ N`** (amber warn / red force) — appears on every
  page load when something is off, survives dismissing the pane, one
  click redisplays it. Hidden when clean.

The same per-option preview drives the **rail greying**: force-
incompatible options are disabled (⛔ + reason tooltip) on the
frontend / AVX-mode / provider selects.

## Growing the registry

Rules are deliberately few and **grounded** — each cites refs; growing
the registry is per-rule operator review. Current families:

| Rules | Relation |
|---|---|
| C001 | cost-policy halt-cloud **forces off** every anthropic backend (force) |
| C002–C004 | DSpark / deep-context / oc-kiosk **require** their backing tier or backend (warn) |
| C005, C010 | power-posture coherence advisories (suggest) |
| C006 | oracle-hybrid bench serve vs the pure-VRAM Oracle/Logic tiers (warn) |
| C007 | one draft strategy per invocation — DSpark xor DFlash (warn, one_of) |
| C008, C011 | the AVX/u64 bit-machine relations — Pulse and the CPU-only profile vs `avx-mode off` (warn/suggest) |
| C009 | high-concurrency-burst **requires** all three Trinity tiers (warn) |

## CLI quick reference

```
sovereign-osctl compat list                              # rules table
sovereign-osctl compat compile                           # the u64 bit-word view
sovereign-osctl compat check --set sys=opt [--current]   # validate a candidate
sovereign-osctl compat check --current --strict          # live-state audit, warns gate
sovereign-osctl compat explain C008-pulse-tier-conflicts-avx-off
sovereign-osctl compat why avx-mode=off                  # everything touching a feature
```
