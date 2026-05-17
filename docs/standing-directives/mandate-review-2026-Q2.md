# Mandate review — 2026-Q2 (R285 / E9.M3)

> Status: **review-record**
> Owner: sovereign-os core
> Closes findings: E9.M3 (quarterly mandate review + new-axis intake process)
> Derived from: §1.0 of the operator mandate ("the goal is constantly
> being defined ... NEVER STOP"), and the §1b mandate rows where the
> operator named the Modules being reviewed below.

## 1. Why this file exists

Quarterly anchor that snapshots the mandate's current state, names
the rounds shipped this quarter, and surfaces the next-quarter
candidates so neither agents nor operators have to grep the mandate
table to know "where are we." E9.M3 of the mandate explicitly calls
for this discipline: *"Quarterly mandate review + new-axis intake
process."*

The doc does NOT replace the mandate file — the mandate stays the
single source of truth. This file is operator-readable companion
context, refreshed once per quarter.

## 2. Mandate-table tally as of this review

Counted from `docs/standing-directives/2026-05-17-operator-mandate.md`:

| Status         | Count |
|----------------|-------|
| ✓ shipped / in-practice | 69 (was 65 at quarter open) |
| **TODO**       | 13 (was 17 at quarter open) |
| partial        | 4-5 (lifecycle in flight) |

(Refresh the numbers by running
`grep -c '✓ shipped\|✓ in-practice' docs/standing-directives/2026-05-17-operator-mandate.md`
+ `grep -c 'TODO' ...` next quarter; do NOT lock these in code —
they're a checkpoint, not a contract.)

## 3. Rounds that landed in 2026-Q2 (selected, mandate-anchored)

The full list is in the Rounds log + per-commit messages. Highlights:

- **R279** (E1.M16) — 256 GB DDR5 RAM-specific advisor; ZFS ARC clamp
  = 128 GB per master spec §19.
- **R280** (E1.M18) — 1-bit / ternary ZMM utilization probe via
  `perf stat -e instructions/cycles` measuring VPDPBUSD fast-path use.
- **R281** (E1.M17) — Wasm-to-AVX-512 AOT pipeline; znver5 target
  enforcement via `WASMTIME_COMPARE_OPTIONS`.
- **R283** (E5.M11) — SDD-030 operator-overlay-doctrine
  (`scripts/lib/operator_overlay.py`): shared 5-tier path
  resolution + deep-merge + audit metadata.
- **R284** (E7.M6) — Declarative operator dep-install hook
  (`scripts/install/operator-deps.py`): first cross-script consumer
  of the R283 helper; triple-gated curl|sh installs.
- **SD-R97** (selfdef cycle-9 / E8.M6) — REPL token-saving aliases
  (14 compact one/two-letter wrappers) + `@track` wasted-path tracker
  decorator that records empty/ok/raised outcomes to
  `SELFDEF_REPL_HISTORY`.
- **SD-R98** (selfdef cycle-9 / E8.M4) — `@selfdef_macro`
  integrated-intelligence registry: `list_macros()` / `macro_info()`
  / `run_macro()` for operator-pull CoT routines.
- **SD-R99** (selfdef cycle-9 / E2.M6) — module features
  sub-configuration: `[features]` table on `ModuleManifest`,
  `selfdefctl modules features <slug>` verb adopting the SDD-030
  4-tier overlay-doctrine for selfdef modules.
- **SD-R100** (selfdef cycle-9 / E2.M7) — advanced module-features
  lifecycle: `--enabled-only / --disabled-only` filters,
  `modules feature-set <slug> <key> <value>`,
  `modules feature-clear <slug> <key>`. Round-100 milestone.

## 4. Next-quarter candidates (operator-preference-driven; no implied order)

From the remaining TODO list as of this review:

- **E1.M19** — Hardware-exploit-to-the-max research loop (continuous
  upstream-tracking SDD/TDD evolution).
- **E4.M8** — Mobile-friendly card layout (dashboard CSS only).
- **E4.M9** — Dashboard editable forms for module configuration —
  natural follow-on to SD-R99 + SD-R100 (the back-end is now ready
  for a UI to drive it).
- **E5.M6** — End-to-end fine-tune lifecycle (training → eval →
  register).
- **E5.M9** — Operator-mutable flexible profile.
- **E7.M5** — Cross-repo MCP-tool aggregator (sovereign-os surfaces
  selfdef tools too) — leverages SD-R94 (TCP MCP) + SD-R96 (write
  gate) groundwork.
- **E8.M5** — Tier 3 native pyo3 bindings (zero-subprocess Tier 1).

E1.M19 is process-shaped — the doctrine is the deliverable, not a
single artifact. E4.M9 + E7.M5 + E5.M9 each have substantial existing
groundwork to leverage. The operator picks; this list is a menu.

## 5. New-axis intake process (E9.M3 process clause)

When the operator adds a new `/goal` paste (§1.0 compounding doctrine
R278), the agent:

1. **Re-reads** the operator's raw dump under
   `devops-solutions-information-hub/raw/` (operator's "RETURN REREAD
   ALL THE RAW DUMP" §1.0 directive) before asking clarifying
   questions.
2. **Decomposes** the new paste into Epic/Module rows under the
   existing 9 Epics, OR opens a new Epic when the axis is genuinely
   new (e.g. a new hardware tier, a new workflow class).
3. **Quotes** the operator-named §1b text verbatim in the new
   Modules' descriptions (never minimize, never paraphrase, never
   conflate).
4. **Files** the Module as TODO with no Round number until shipped.
5. **Updates** the next quarterly review to include the new axis in
   §2 + §4 above.

The compounding rule (§1.0) means a new `/goal` paste ADDS — it never
REPLACES — prior Modules. Modules graduate to ✓ only via real rounds
with passing L3 tests.

## 6. Review cadence + ownership

- Cadence: once per calendar quarter (mid-quarter). Q3 review due
  ~mid-August 2026.
- Owner: whichever agent or operator runs the review touches this
  file + the date header. New files for future quarters
  (`mandate-review-2026-Q3.md`, etc.) — do NOT overwrite this one;
  the trail is the audit.
- L1 lint: none for now. The file is operator-readable text; missing
  it is visible (E9.M3 row reverts to TODO).

## 7. What this file does NOT do

- It does NOT change the mandate's row statuses — those flip via
  per-round commits to `docs/standing-directives/2026-05-17-operator-mandate.md`.
- It does NOT prescribe round order — the operator decides which
  candidate fires next.
- It does NOT capture cross-repo work outside the five-repo scope
  (cyberpunk042/{selfdef, root-ghostproxy, devops-solutions-information-hub,
  sovereign-os, devops-expert-local-ai}).
