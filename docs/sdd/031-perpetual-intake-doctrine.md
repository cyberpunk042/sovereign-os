# SDD-031 — Perpetual-intake doctrine (E9.M10 / R326)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E9.M10 (mandate decomposition)
> Derived from: §1.0 of the operator mandate ("the goal is constantly
> being defined ... NEVER STOP") + R285 mandate-review-2026-Q2 §5
> ("new-axis intake process") + the lived practice of R278 → R325

## Mission

The operator's mandate is a perpetual direction vector, not a
finite checklist (R278 — multi-`/goal`-paste compounding doctrine
+ R285 §5 — new-axis intake process). Rounds keep landing as long
as new §1b verbatim phrases are identified or operator-named
vectors arrive. SDD-031 formalizes the pattern so future agents +
operators see the same loop the existing 45-round continuation
session has been running.

## The doctrine — five-step round template

Every round shipped in the perpetual loop follows the same five
steps:

### 1. Locate the §1b verbatim phrase

The operator-named axis lives somewhere in the active mandate
(`docs/standing-directives/2026-05-17-operator-mandate.md` §1b or
in operator chat spec drops). The agent re-reads the raw dump
(R278 E9.M8 protocol) before fabricating any new axis name.

If the verbatim phrase doesn't exist in the mandate, the round
adds a new axis — but only with operator confirmation OR with a
clear cross-reference to where the operator named it (e.g., chat
spec drop "I guess there is also a memory place..." → R317
hardware-inventory catalog cites the chat turn verbatim).

### 2. File a TODO mandate row

A new module row goes into the mandate table:

```
| E<n>.M<m> | **<short title>** — <operator-readable description>
  [from §1b verbatim: "<exact phrase>"] | **TODO** | — |
```

The `[from §1b verbatim: "..."]` is mandatory — the audit trail
from operator phrase → module → round is permanent + queryable
via R321 `sovereign-osctl rounds show`.

### 3. Ship an operator-runnable verb

The round implements:
- a script (`scripts/<axis>/<name>.py` or `.sh`)
- a `sovereign-osctl` subcommand dispatching to it
- at minimum 2 verbs (`status` + one other, e.g. `recommend`,
  `apply`, `troubleshoot`, `show`)
- JSON output as the operator-stable contract; human as fallback
- operator-overlay support via R283 `load_with_overlay` when the
  script has configurable knobs
- exit codes that match operator-pull semantics:
  `0 = ok / 1 = attention / 2 = critical or usage error`

### 4. Author an L3 test

A 10-assertion shell test at `tests/nspawn/test_<name>.sh`:
- envelope assertion (round / schema_version / sdd_vector present)
- operator-named anchors present
- per-entry schema
- exit-code matrix
- operator-overlay path
- malformed overlay → defaults + parse_error
- `sovereign-osctl` dispatch
- 3-4 axis-specific assertions

### 5. Flip the mandate row + commit

After L3 passes, the mandate row flips `**TODO** | —` →
`✓ shipped | R<n> (`sovereign-osctl <verb> ...`)`. The commit
message cites the Epic/Module ID (R265 E9.M2 in-practice
doctrine).

## Acceptance criteria for a round to count

A round counts as shipped iff ALL of:

- [x] Verbatim §1b phrase OR operator-confirmed chat phrase cited
- [x] Mandate row added with `[from §1b verbatim: "..."]` tag
- [x] Operator-runnable script + sovereign-osctl wiring
- [x] L3 test with ≥8 assertions, all green
- [x] Operator-overlay support (when script has knobs)
- [x] Mandate row flipped `**TODO** → ✓ shipped`
- [x] Commit pushed to main (sovereign-os) or PR branch (selfdef)

## Composition patterns shipped via this doctrine

The loop has produced 45+ rounds over the continuation session
covering 33+ axes. Composition patterns that emerged:

### Probe → advisor → rollup → meta

```
R252 power-status (raw probe)
  → R294 psu-oc (advisor over R252)
    → R296 thermal-oc-budget (rollup over R294 + R265 heat)
      → R300 operator-posture (meta-rollup over R296 + R298 + ...)
        → R308 autohealth (periodic synth over R300 + R226 + R266 + ...)
          → R322 state-snapshot (parallel run of ALL read-only verbs)
            → R324 fleet-aggregator (cross-host roll-up over R322)
```

Each layer composes the previous via subprocess-spawn-and-parse-JSON.

### Triple-gate apply pattern (R318)

When a round needs to MUTATE state, the doctrine requires:
1. `--apply` flag (CLI intent declaration)
2. `--confirm-<verb>` flag (per-verb confirmation)
3. `SOVEREIGN_OS_CONFIRM_DESTROY=YES` env var (host-level gate)

Without ALL THREE → dry-run + `wrote=false`. Preserves the
operator's NEVER-AUTO-MUTATES doctrine.

### Operator-overlay-doctrine (R283 / SDD-030)

Every script with configurable knobs adopts `load_with_overlay`.
Operator-overlay TOML at:
- explicit `--config <path>` (highest precedence)
- `$SOVEREIGN_OS_OVERLAY_<NAME>` env var
- `/etc/sovereign-os/<name>.toml`
- in-source DEFAULTS

R325 overlay-drift detector audits which overlays the operator
has set.

## Round-template scaffold for future authors

A new round looks structurally identical to R325 (or any other
recent round). Copy R325 as the template + replace:
- script path + verb names
- DEFAULTS dict + per-knob fields
- catalog entries (if catalog-shaped) or verdict logic (if
  advisor-shaped)
- L3 assertion bodies
- mandate row + commit message body

The R285 quarterly review file gets a §3 line added at quarter
close (e.g., 2026-Q2 review covers R279-R325; 2026-Q3 review will
cover R326-onward).

## L1 lint enforcement

`tests/lint/test_perpetual_intake_doctrine.py` pins the required
sections of this SDD (`## Mission` / `## The doctrine` /
`## Acceptance criteria` / `## Composition patterns shipped` /
`## Round-template scaffold` / `## L1 lint enforcement`) so a
future edit that strips a section fails at push.

R320 (E9.M4) SDD cross-link audit already pins the `Closes
findings:` line at the top of this file.

## What this SDD does NOT do

- It does NOT constrain WHICH axes get rounds — operator picks via
  §1b drops + chat.
- It does NOT enforce ROUND ORDER — agent picks the most concrete
  unaddressed axis per stop-hook feedback.
- It does NOT auto-fire rounds — every round is operator-driven
  via the standing `/goal` "continue endlessly" mandate.
- It does NOT bound the total round count — the loop is perpetual
  by §1.0 design.

## Future-quarter SDD evolution

If the operator names a NEW process pattern (e.g., a new gate
beyond the triple-gate, a new composition layer above
fleet-aggregator), a new SDD captures it + cross-links back here.
The doctrine is itself versioned via the per-SDD `> Last updated:`
line + the R285 quarterly review process.
