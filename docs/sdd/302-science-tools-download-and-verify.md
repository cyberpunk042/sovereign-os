# SDD-302 — Science tools: download + verify (a real instrument, not a catalog)

> Status: shipped (2026-10-06 audit: download + verify live on-host)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-10-02
> Closes findings: operator directive 2026-10-02 — *"download button and test the download"*
> Derived from: SDD-070 (the 7-tool catalog), SDD-301 (the live instrument — execute/remember/
> readiness/context; its **render was never fully landed**, so the panel still shows a flat
> table). This SDD adds the two capabilities SDD-301 named but left copy-only: an actual
> **Download** action and a **Verify** ("test the download") action, plus the minimal render
> wiring that makes them meaningful (live per-tool state). Reconciles with: the `models
> download` precedent (`scripts/models/download-job.py` + d-21 button), SDD-045/047 (the
> control-exec rail), SDD-116 (DEMO — new sections ship badged demo data), the 2026-09-10
> download-readiness directive, and SB-077 (never fake `installed`).

## Mission

The Science Tools panel can already *run* a sample sim (SDD-301 run-card) and the API already
*knows* whether each cataloged tool is installed / downloadable (`tools_status`). But it cannot
**download** a tool or **test that a download worked** — both are copy-only today ("click a tool
for its download plan"). The operator named the exact gap: *"download button and test the
download."*

This SDD turns the cataloged tools from *data rows* into *provisionable artifacts*:

1. **Download** — one button per tool that starts a **background** download job (a large `hf`
   pull takes minutes, so it must outlive the exec-rail's 30 s window) and reports
   queued → downloading → verifying → complete / failed, resumable across a restart.
2. **Verify ("test the download")** — a first-class action that re-checks an already-downloaded
   tool (artifact present **and** usable: a canonical import where one exists, else the exact
   weight file) and returns a grounded pass/fail. Never reports `installed` on a bare directory
   (SB-077) — a directory alone is not readiness (the `download-job.py` precedent).
3. **Render** — the panel's catalog table shows each tool's **live state** (installed /
   artifacts-present / downloadable / unknown, from `tools_status`) and a **Download / Verify**
   action row per tool, with the download job's progress rendered from the data refresh.

All three ship in one PR. Real DNA/protein *runners* (executing Evo/ESMFold/AlphaFold3 on real
input) remain the documented Stage-N follow-on (Q-302-A) — this SDD makes the artifacts
*provisionable and verifiable*, not executable.

## Problem

Concretely, on this host (verified 2026-10-02):

- The daemon (`sovereign-science-api`, loopback `:8134`) serves `/science.json` with
  `tools`, `tools_status` (per-tool live state), `recent_runs`, `run_stats`, `gpu` — but the
  panel's `render(d)` (webapp/science/index.html) is still the **flat SDD-070 table** (name ·
  domain · kind · install · tiers · status). It renders none of `tools_status`, the run
  history, or the GPU context. The operator's read is correct: it "does almost nothing."
- Each cataloged tool shows a **copy-only** install command. There is no `sovereign-osctl
  science download <id>` and no `… verify <id>` — the CLI has `list/status/install/info/run/
  history` only. So there is nothing for a Download button to call.
- The SDD-301 run-card Execute button POSTs directly to `/api/control/execute`; the
  controls-audit baseline records science as `exec_rail: 0, status: no-actions` (the audit only
  counts `jumpToControl(`), so the run-card was never reconciled into the audit. SDD-302's
  Download button follows the **same direct-POST pattern** (the d-21 `model-download`
  precedent) and reconciles the audit baseline honestly.

## Grounded reality (verified 2026-10-02)

- **Download job precedent (mirrored, not invented):** `sovereign-osctl models download <id>` →
  `scripts/models/download-job.py` spawns a **detached background worker** that streams a
  progress monitor into a **state file** (`/var/lib/sovereign-os/model-downloads/<id>.json`,
  fields `status ∈ {queued,preflight,downloading,verifying,complete,failed,interrupted}`,
  `bytes_done/bytes_total`, `error`, `pid`, `updated_at`), then **verifies** (file size +
  sha256). The d-21 button POSTs `{control_id:'model-download', args:{model:id}, confirm:true}`
  to the exec-rail and the panel reads progress from its data refresh; `readiness()` treats an
  interrupted job (dead PID) as `interrupted`, and a bare directory is never "ready."
- **Exec rail (SDD-045/047, `scripts/operator/_action_exec.py`):** a control executes by
  substituting into its `change_cli`; `privileged: false` controls run **directly as the
  invoking user** (no `sudo`); the default window is `SOVEREIGN_OS_ACTION_TIMEOUT` (30 s).
  Science downloads are **user-level** (pip `--user` / `hf download` to the HF hub cache /
  `git clone` to a user dir) → `privileged: false`, **no sudoers change**, and the verb must
  **spawn-and-return in well under 30 s** so the exec-rail call completes while the download
  runs on.
- **Multi-method reality:** the science catalog's `install.method` is not always `hf` — it is
  `pip` (warp-lang), `hf` (evo / hyenadna / esmfold), `github` (RFAA / openfold / alphafold3),
  or `checkout` (a local path). The download job + verify must branch on `install.method`, and
  the **verify check branches on `detect`** (import module vs. weight-file presence) — the
  catalog already carries `detect: {method, ref, import_module?}` and `size_gb`/`vram_gb`.
- **Detection (SDD-301) already does the presence work:** `science.py detect_tool()` reports
  `state ∈ {installed, artifacts-present, downloadable, unknown}` per method and never fakes
  `installed` (SB-077). The **verify** action reuses the same method dispatch, but is a
  *deliberate, structured, re-checkable* action with an explicit `{check, ok, detail}` result
  and a written record — distinct from the passive per-refresh `detect`.
- **State root:** downloads are user-level → state lives in the **user-local** convention
  `~/.local/state/sovereign-os/science-downloads/<tool-id>.json` (env override
  `SOVEREIGN_OS_SCIENCE_DOWNLOADS`), mirroring the science-runs store — **not**
  `/var/lib/sovereign-os` (root-owned; the model-download precedent needs root because it writes
  to `/mnt/vault`, which science downloads do not).
- **Honest-degrade + DEMO:** nvidia-smi / `hf` / `git` / `pip` may be absent (dev/CI box);
  every path degrades to a structured `unknown`/`{available:false,reason}`, never a 500 and
  never a fake `installed`. DEMO mode (SDD-116) ships badged demo `download_jobs` so the panel is
  explorable with no daemon.
- **Band:** science-tools = 300–399 (SDD-100); SDD-300 (warp) and SDD-301 (live instrument) are
  taken → this is **SDD-302**.

## The state contract (single source — backend AND panel build to this)

**Download-job state file** — `~/.local/state/sovereign-os/science-downloads/<tool-id>.json`
(env `SOVEREIGN_OS_SCIENCE_DOWNLOADS`). One file per tool; atomic write (tmp + replace):

```json
{
  "tool_id": "esmfold",
  "status": "downloading",        // queued|preflight|downloading|verifying|complete|failed|interrupted
  "method": "hf",                 // install.method at start
  "pid": 41234,
  "bytes_done": 4200000000,
  "bytes_total": 8440000000,
  "dest": "~/.cache/huggingface/hub/models--facebook--esmfold_v1",
  "error": null,                  // human string, or null
  "updated_at": 1762032000.0
}
```

**`/science.json` gains one key** — `download_jobs`: an object keyed by `tool_id`, each value the
state file's contents above (or absent when no job exists for that tool). The API reads the state
dir read-only; it never starts a job. An `interrupted` job is detected (dead PID) exactly as
`download-job.py readiness()` does.

**Verify result** (`science verify <id>` → JSON, and rendered by the panel):

```json
{ "tool_id": "esmfold", "method": "hf", "state": "installed",
  "checks": [
    { "check": "artifact-present", "ok": true,  "detail": "snapshot dir non-empty (8.44 GB)" },
    { "check": "import", "ok": true, "detail": "import esm → ok" }
  ],
  "ok": true }
```

`state` reuses the `detect_tool` vocabulary (`installed` / `artifacts-present` / `downloadable` /
`unknown`); `ok` is true only when the artifact is present **and** the method's usability check
passes (import where a module is declared; else weight-file presence). `ok:false` + `state` is
honest (SB-077) — a present-but-unimportable artifact is `artifacts-present`, not `installed`.

## Phase A — download (the "get it" core)

### `scripts/science/science-download.py` (NEW — mirrors `download-job.py`, user-level)
- Two modes: `start <tool-id>` (spawn-and-return) and `--worker <tool-id>` (the detached job).
- Reads the tool from `config/science-tools.yaml`; refuses ids not in the catalog or with an
  `install` it cannot action (no user-provided paths/commands — catalog-only, like
  `download-job.py`). Ids validated against a strict `SAFE_ID` token.
- **Dispatch on `install.method`:**
  - `pip` → `pip install --user <ref>` (or the system interpreter); **verify** via
    `detect.import_module` if declared, else the `detect.ref` module.
  - `hf` → `huggingface_hub.snapshot_download(ref, …)` into the **HF hub cache** (the default
    `~/.cache/huggingface/hub`, where `detect` already looks) — reusing `scripts/models/
    hf-auth.py` for the token, exactly as `download-job.py` does. Progress monitor thread writes
    `bytes_done` every ~2 s.
  - `github` → `git clone <ref> <dest>` into `~/.local/share/sovereign-os/science/<tool-id>`
    (env override `SOVEREIGN_OS_SCIENCE_GIT_DIR`); then a tool-specific weight fetch only when
    the catalog declares a `verify.weight_file` under the repo (else the clone is the artifact).
  - `checkout` → no download; the job is a **verify-only** pass over the declared local path.
- **Verify stage** (runs after download, or standalone): branches on `detect` — `import`
  (short-timeout `python3 -c "import <mod>"`) and/or `weight_file` presence + size vs the
  catalog `size_gb`. Produces the verify result contract above.
- **Spawn-and-return:** `start` writes `queued`, `Popen(..., start_new_session=True)` the worker,
  records the `pid`, writes `accepted`, and exits **immediately** (well under the 30 s rail).
  The worker streams `downloading`→`verifying`→`complete`/`failed` to the state file. On a
  restart, a job whose PID is dead is surfaced as `interrupted` (the panel offers retry).
- Exit codes: 0 clean / accepted; 2 usage / unknown tool; 1 worker-domain error (never on a
  mere spawn).

### `scripts/science/science.py` — `download` + `verify` (EXTENDED)
- `science download <tool-id> [--json]` → shell `science-download.py start <id>`; print the
  accepted-job line (or `--json` the state).
- `science verify <tool-id> [--json]` → shell `science-download.py --verify <id>` (verify-only,
  no download) → the verify result contract.
- `science status` **gains** `download_jobs` (the state-dir contents, keyed by tool_id) so the
  existing status/API surface carries it; `--json` only (human `status` stays unchanged).

### `scripts/operator/science-api.py` — expose `download_jobs` (EXTENDED)
- `/science.json` gains `download_jobs` (assembled from `science status --json`'s new key — the
  daemon stays stdlib-only, shells `science.py`, stays read-only, stays 405 on POST).
- `--self-check` reports `download_jobs_count`.

### `config/control-systems.yaml` — `science-download` control (NEW)
`kind: lifecycle`, `scope: scoped`, **`privileged: false`** (user-level — the
`science-sim` precedent; no sudo, retain validation/audit),
`change_cli: "sovereign-osctl science download <tool-id>"`, `state_cli:
"sovereign-osctl science status"`, `applies_to: [science]`, `refs: [SDD-302,
config/science-tools.yaml]`. Appears automatically in the science panel's inlined control-surface
grid (`filterSlug:'science'`). `science-verify` is a second scoped, `privileged: false` control
(`change_cli: "sovereign-osctl science verify <tool-id>"`) so both verbs are registry-visible and
lint-covered. `EXPECTED_IDS` += both.

### `webapp/science/index.html` — Download + Verify (EXTENDED)
- The catalog table becomes **per-tool rows with a live state pill** (installed /
  artifacts-present / downloadable / unknown — from `tools_status`) and an **action cell**:
  - **Download** button (shown when state is `downloadable` or a job is `interrupted`/`failed`)
    → **direct POST** to `/api/control/execute` with `{control_id:'science-download', args:{id:
    tool_id}, confirm:true}` (the d-21 `model-download` pattern, mirrored verbatim:
    dry-run → "preview only — download service not enabled", ok → "download accepted, progress
    below"). `setTimeout(load, 1500)` picks up progress (the panel already polls `/science.json`
    every 5 s).
  - **Verify** button (always) → POST `{control_id:'science-verify', args:{id:tool_id},
    confirm:true}` → render the `{check, ok, detail}` lines as ok/error chips.
  - **Job status line** under the row when `download_jobs[tool_id]` exists: status +
    `bytes_done/bytes_total` (GiB) + error, exactly like d-21's `.inspector-status` read.
- Copy-command (the exact `hf download`/`pip install`/`git clone`) stays as the labelled
  §1g fallback next to each button.
- `DEMO_SCIENCE` extended with demo `tools_status` + `download_jobs` (one `downloading`, one
  `complete`, one `failed`) so DEMO mode is explorable (SDD-116, always-badged).

## Phase B — verify ("test the download") as a first-class action

Covered in Phase A's `science verify` + the panel Verify button. The deliberate, standalone
`verify` exists so the operator can **re-test** a tool whose download is stale or was placed
manually (the 2026-09-10 "test the download" pattern), independent of a fresh download. Its
honest-degrade + SB-077 rules are the state contract above.

## Wiring

- **Lint:** `tests/lint/test_control_systems_registry.py EXPECTED_IDS` += `science-download`,
  `science-verify`. Regenerate `scripts/webapp/controls-audit-baseline.json`
  (`python3 scripts/webapp/controls-audit.py --json`) — science's audit entry is reconciled
  honestly (the direct-POST Download button is the d-21 `model-download` pattern; if the audit
  keeps science at `no-actions` because it only counts `jumpToControl(`, that is the correct,
  documented outcome and the baseline is updated to match the actual scan).
- **osctl:** `sovereign-osctl` `science` dispatch already forwards `"$@"` to `science.py` — the
  new subcommands work without touching the bridge. The `science` help block (osctl `293:…`)
  gains `download` + `verify` lines.
- **Man:** `docs/man/sovereign-osctl.1.md` — the `science` subverb list gains `download <id>`
  and `verify <id>`; the run line stays as the (SDD-301-fixed) real syntax.
- **feature-coverage.yaml:** unchanged at module level (`science: [science]`).
- **Schema:** `schemas/science-tools.schema.yaml` accepts the new optional per-tool
  `verify: {import_module?, weight_file?}` field; conformance test updated.
- **Catalog enrichment:** `config/science-tools.yaml` — add `verify` per tool from the grounded
  research pass (never guessed); confirm/correct `size_gb`/`vram_gb`.
- **Tests:** `science-download.py` (spawn-and-return shape, SAFE_ID refusal, per-method dispatch
  dry-run, state write + bound, interrupted-PID detection, verify contract per method,
  honest-unknown); `science.py download/verify/status.download_jobs`; `science-api`
  `--self-check` key; registry lint; nspawn panel test updated for the new action cells.
- **SDD catalog:** `docs/src/sdd-catalog.md` regenerated (`scripts/docs/gen-sdd-catalog.py`).
- **Service:** unchanged (`sovereign-science-api.service`, loopback `:8134` — read-only API only
  gains a key; no unit change).

## Out of scope (Stage N — proposed, not minimized)

| Q | item | status |
|---|------|--------|
| Q-302-A | **Real DNA/protein runners** — execute Evo / ESMFold / HyenaDNA / OpenFold / AlphaFold3 on real input (the SDD-301 Q-301-A Stage N). This SDD makes their artifacts *provisionable + verifiable*, not executable. | proposed |
| Q-302-B | **Checksum pinning** for `github`-distributed weights (openfold params, alphafold3 af3.bin.zst, RFAA .pt) once a stable sha256 source is confirmed — the `hf` path already verifies size + (LFS) sha256. | proposed |
| Q-302-C | **Download concurrency / queue** across tools (the model path serializes on a transfer lock; science tools are user-level and smaller) if the operator provisions several at once. | proposed |
| Q-302-D | Land the **full SDD-301 render** (run-history table + per-device comparison + GPU context strip) so the instrument is complete — SDD-302 deliberately keeps the render change minimal (live state + Download/Verify) and leaves the rest to SDD-301. | proposed |
| Q-302-E | **Remove / reinstall** verb for a science tool (mirrors `models remove`) once the operator wants lifecycle, not just download+verify. | proposed |
