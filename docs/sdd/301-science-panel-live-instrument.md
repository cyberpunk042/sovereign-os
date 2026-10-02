# SDD-301 — Science panel: from static catalog to live instrument

> Status: draft — implementing (operator directive 2026-10-02)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-10-02
> Closes findings: E11.M301 (science-tools band, SDD-100)
> Derived from: operator directive 2026-10-02 — *"Lets improve sovereign-os cockpit Science Tools.. it does almost nothing for now. I would expect so much more, lets develop it, you can use SDD and sub-agents"*. First-round follow-on to SDD-070 (the 7-tool catalog + particle-sim stub panel); the companion SDD-300 already turned the *Warp engine* into real management (relations + one-click Render/Bench + latest-render preview). This SDD does the same for the **Science Tools** panel itself. Reconciles with: SDD-045/047 (control-exec rail), SDD-116 (DEMO mode — every new section ships demo data, always-badged), the 2026-09-10 standing directive (download readiness: *make missing artifacts visible, and tell the operator how to get them first*).

## Mission

The Science Tools panel today **does almost nothing**: a Warp status strip, a flat
6-column catalog table, and a copy-only run command. It cannot execute, has no
memory of what has run, says nothing about whether the six cataloged tools exist
on this box or how to get them, and ignores the GPUs sitting idle. This SDD turns
it into a **live scientific instrument**:

1. **Execute** — one-click, parameterized sample-sim runs through the sanctioned
   exec-rail (the SDD-300 `warp-render` precedent: user-level, no redundant
   confirmation), with structured results rendered inline.
2. **Remember** — a persistent run history (JSONL) with per-device performance
   comparison, served by the API and rendered as a recent-runs table.
3. **Readiness** — live per-tool detection (installed / artifacts-present /
   downloadable) + a grounded download plan per cataloged tool (size, VRAM,
   exact command), replacing the static `cataloged` pill.
4. **Context** — the compute context (per-GPU name/capacity/free-VRAM from
   nvidia-smi, honestly degraded) + a tier-readiness matrix ("what can *this*
   box run right now") + a cross-link into the Warp Management panel.

All four phases ship in one PR. Stage N (real DNA/protein runners) stays a
documented follow-on, not minimized away — it needs multi-GB model downloads and
is a separate, operator-gated round (SDD-070 Q-065-C).

## Problem

The operator named it: the panel "does almost nothing". Concretely:

- No execution path from the UI — the run command is copy-only (the Warp panel
  got one-click execution in SDD-300; Science got nothing).
- No history — every run is forgotten; nothing to compare (GPU vs CPU timing).
- The catalog's six non-Warp tools are data-only rows: no signal whether they're
  installed here, no sizes, no install/download commands, no "what does it need"
  — the 2026-09-10 directive's download-readiness pattern ("tell me to download
  it and how first") is not applied to science tools.
- No GPU context — the box's three cards (RTX PRO 6000 95 GiB / RTX 5090 31 GiB /
  RTX 4090 24 GiB) are never shown, so the operator cannot see what compute
  capacity a science run would draw from.
- A latent bug: the man page documents `science run [--device cpu|cuda]
  [--particles N] [--steps M]`, but the `run` subparser uses `argparse.REMAINDER`
  and rejects any option before the first positional — the documented command
  errors with `unrecognized arguments: --device` (verified 2026-10-02).

## Grounded reality (verified 2026-10-02)

- Sample sim timing on this host: `warp-runner.py run --device cuda --particles
  100000 --steps 200` → **0.9 s wall** total (warp init + cached JIT), kernel
  `wall_ms: 2.2`. Comfortably inside the exec-rail 30 s default timeout
  (`SOVEREIGN_OS_ACTION_TIMEOUT`); even 1 M-particle presets stay well under.
- GPUs (nvidia-smi): idx0 RTX PRO 6000 Blackwell 97 887 MiB · idx1 RTX 5090
  32 607 MiB · idx2 RTX 4090 24 564 MiB. **Warp's cuda:N order differs from
  nvidia-smi's index order on this host** (warp cuda:0 = the 4090) — so the
  GPU-context strip (nvidia-smi truth) and the runner's device reports (warp
  truth) are shown side by side, never conflated (SB-077).
- The exec rail (`scripts/operator/_action_exec.py`) supports enum placeholders
  `{auto|cuda|cpu}` (keyed `verb`) and free `<name>` placeholders validated by
  `_SAFE_VALUE` — a numeric `--particles <particles>` passes. `execute()`
  returns `{ok, code, exit_code, stdout (≤4000 B), stderr (≤2000 B)}`; the
  warp panel's `warpExec()` one-click pattern (webapp/warp/index.html) mirrors
  that response contract and is the template for the science panel's Run card.
- The science panel **already inlines the SDD-045 control surface** with
  `filterSlug:'science'` — a new registry control `applies_to: [science]`
  appears in its grid automatically.
- Adding an exec-rail-wired action to a panel requires regenerating
  `scripts/webapp/controls-audit-baseline.json` (`controls-audit.py --json`),
  pinned by `tests/lint/test_controls_audit_baseline.py`; new registry ids go in
  `tests/lint/test_control_systems_registry.py EXPECTED_IDS`; the inlined
  control surface must stay verbatim-locked (test_control_surface_component /
  _execute_boundary).
- `sovereign-osctl science` dispatches `"$@"` straight to `science.py` — new
  subcommands work without touching the osctl bridge; the man page
  (`docs/man/sovereign-osctl.1.md`) documents the subverbs and must be kept in
  step. `config/feature-coverage.yaml` is module-level (`science: [science]`) —
  unchanged.
- DEMO mode (SDD-116): the panel renders `DEMO_SCIENCE` when the
  `sovereign-os.demo` flag is on, always-badged — every new section must have
  demo data so the panel is explorable with no daemon.
- Band: science-tools = 300–399 (SDD-100); SDD-300 is taken; this is SDD-301.

## Phase A — execute + remember (the "do something" core)

### scripts/science/warp-runner.py — run history (EXTENDED)
On every `run` (success **and** domain failure) append one JSONL record to the
run store: `{ts, tool: "warp-lang", sim: "particle-drop", device,
num_particles, steps, dt, wall_ms, mean_final_height, settled, warp_version,
error}`. Store path: `SOVEREIGN_OS_SCIENCE_RUNS` env override, default
`~/.local/state/sovereign-os/science-runs.jsonl` (mirrors the SDD-300
warp-renders store). Bounded: keep the last 1000 records (drop oldest). History
writing never fails the run (best-effort, exit code unchanged).

### scripts/science/science.py — argument fix + history (EXTENDED)
- **Fix the latent bug**: `run` stops using `argparse.REMAINDER`; it parses
  `--device {auto,cuda,cpu}`, `--particles N`, `--steps M`, `--json` natively
  and forwards the exact flags to warp-runner (the man page's documented syntax
  now works).
- New `history [--limit N] [--json]` subcommand: read the run store (same env
  override), newest-first, default limit 30, plus `--json` machine output.
  `status` unchanged in shape (the API extends, not the CLI contract).

### scripts/operator/science-api.py — richer /science.json (EXTENDED)
Assembled payload gains: `recent_runs` (last 30, newest-first) and
`run_stats` (count + per-device median `wall_ms`, computed from the store —
served, not re-simulated). Still read-only, still shells `science.py`
(`history --json`), still 405 on POST, still stdlib-only, port 8134.
`--self-check` reports the new keys.

### config/control-systems.yaml — `science-sim` control (NEW)
`kind: lifecycle`, `scope: scoped`, **`privileged: false`** (user-level compute
— the SDD-300 `warp-render` precedent: retain validation/audit, no sudo, no
redundant confirmation),
`change_cli: "sovereign-osctl science run --device {auto|cuda|cpu}
--particles <particles> --steps <steps> --json"`, `state_cli:
"sovereign-osctl science status"`, `applies_to: [science]`,
`refs: [SDD-301, config/science-tools.yaml]`. Appears automatically in the
science panel's inlined control-surface grid (filterSlug 'science').
`EXPECTED_IDS` updated in the registry lint.

### webapp/science/index.html — Run card + history (EXTENDED)
- **Run sample sim card**: device segmented control (auto/cuda/cpu), workload
  presets (light 10 k×100 · standard 100 k×200 · heavy 1 M×500 · custom with
  numeric particles/steps inputs), one-click **Execute** through the same
  sanctioned rail (`POST /api/control/execute`, the warp panel's `warpExec`
  response contract mirrored verbatim: dry-run → confirm-on-403 → result),
  inline result rendering the parsed `--json` payload as metric chips
  (device · N×steps · wall_ms · ms-per-M-particles · settled) + a raw-output
  disclosure. Copy-command stays as labelled fallback.
- **Recent runs table**: time · device · workload (N×steps) · wall_ms ·
  ms/M-particles · settled · status (ok/error).
- **Device comparison strip**: median wall_ms per device from `run_stats` when
  ≥1 run per device (the GPU-vs-CPU read the operator asked to see).
- `DEMO_SCIENCE` extended with demo `recent_runs` + `run_stats` + `gpu` +
  per-tool readiness so DEMO mode stays explorable (SDD-116, always-badged).

## Phase B — per-tool readiness + download plan

### config/science-tools.yaml — grounded enrichment (EXTENDED)
Optional per-tool fields added (schema-validated): `size_gb` (artifact size),
`vram_gb` (minimum working VRAM for the stated tier), `run_cmd` (integrated
tools), `detect` (machine check: `{method: import|pip|hf|checkout, ref}`),
`docs` (link). Values **grounded, not guessed** — each number verified against
the project/HF page at authoring time (research sub-agent pass); where a figure
cannot be verified it is omitted rather than estimated.

### schemas/science-tools.schema.yaml + conformance (EXTENDED)
Accept the new optional fields; conformance test updated.

### scripts/science/science.py — live detection (EXTENDED)
`status` gains per-tool `tools_status`: for each tool, run its `detect` spec —
`import` (short-timeout `python3 -c "import …"`), `pip` (`pip show`), `hf`
(model ref present in the HF hub cache or the sovereign model vault,
`SOVEREIGN_OS_MODELS_DIR`/`/mnt/vault/models`), `checkout` (known path, env
overridable) — and report `state ∈ {installed, artifacts-present, downloadable,
unknown}` + `install_cmd` + the size/vram hints. Honest degradation: detection
failures report `unknown`, never fake `installed`.

### webapp/science/index.html — readiness (EXTENDED)
- Catalog table → **per-domain sections** (particles / DNA / protein header
  cards with integrated/cataloged counts) and **expandable rows**: click a tool
  → detail drawer with notes, source + docs links, license, kind, tier chips
  (this box's tiers highlighted), **live state pill** (installed /
  artifacts-present / downloadable / unknown — from `tools_status`), size/VRAM
  hints, and the **download plan**: the exact install/download command +
  copy (the 2026-09-10 pattern — missing artifacts visible, how-to-first).
- **Tier-readiness matrix**: tools × tiers (cpu / rtx-4090 / rtx-pro), filled
  cell = can run there, this-box tiers highlighted — the "what can *this* box
  run right now" read.
- **Readiness strip**: N cataloged · M installed · the not-yet-present ones
  named with their one-line download plan.

## Phase C — compute context + cross-links

### scripts/operator/science-api.py — GPU context (EXTENDED)
`/science.json` gains `gpu`: per-card `{index, name, memory_total_mib,
memory_free_mib, utilization_pct}` from `nvidia-smi --query-gpu=…` (short
timeout, honest `{available:false, reason}` when nvidia-smi is absent —
dev/CI box doctrine). No warp import; the warp device list stays the runner's
`warp.devices` (shown separately — the cuda:N order is NOT nvidia-smi's order
on this host).

### webapp/science/index.html — context (EXTENDED)
- **Compute context strip**: per-GPU cards (name · total/free GiB · bar · util)
  + the standing note that science runs draw from the same VRAM budget
  inference uses (D-09 cross-ref), plus the runner's warp device list side by
  side with its source labelled.
- **Warp engine cross-link card**: one line into the Warp Management panel
  (the 217-scene engine — SDD-300), so the tool entry and the engine panel
  find each other.
- SO_ASSIST gold data refreshed for every new section (the app-shell Assistant
  pane reads it); assistant `context` blurb updated to describe the instrument.

## Wiring

- Lint: `EXPECTED_IDS` (+`science-sim`); `controls-audit-baseline.json`
  regenerated (science moves toward wired); control-surface verbatim lock kept
  (no edits inside the inlined component).
- Man: `docs/man/sovereign-osctl.1.md` — `science` subverb list gains
  `history`; the `run` line now matches the (fixed) real syntax.
- Catalog: `config/dashboard-catalog.yaml` — science entry blurb updated
  (execution + readiness + history).
- Tests: runner history (write/read/bound/env-override + no-failure),
  `science run` arg fix (documented syntax runs), `history` subcommand,
  detection (each method + honest unknown), schema conformance (new fields),
  registry lint, science-api `--self-check` keys, nspawn panel test updated.
- `docs/src/sdd-catalog.md` regenerated (`scripts/docs/gen-sdd-catalog.py`).
- Service: unchanged (`sovereign-science-api.service`, loopback 8134 — the API
  only gains read endpoints/keys; no unit change needed).

## Out of scope (Stage N — proposed, not minimized)

| Q | item | status |
|---|------|--------|
| Q-301-A | Real DNA/protein runners (ESMFold first — cheapest rung; then HyenaDNA / Evo / OpenFold) with model-download readiness wired to the vault. Needs multi-GB downloads + GPU-only deps → its own operator-gated round (SDD-070 Q-065-C). | proposed |
| Q-301-B | tui / mcp rungs for the science module (SDD-070 Q-065-D). | proposed |
| Q-301-C | Run-history retention policy beyond the 1000-record bound (aggregation, pruning by age) if history grows into observability territory. | proposed |
| Q-301-D | Flip the SDD-070 wiki `warp-lang` entry to point at this panel's instrument surface (cross-repo, SDD-001 boundary — operator's call). | proposed |
