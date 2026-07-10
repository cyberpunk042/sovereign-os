# SDD-111 — D-21 + D-22 full-layout delivery (de-minimization per the operator's design)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — "when you did it you minimized and didn't deliver those two panels properly. the design is very important and seeing all sections with all content too." (two hand-drawn sketches for D-21 + D-22)
> Derived from / extends: SDD-055 (LM-orchestration button-wiring), M075 (SRP hardware roles), M076 (runtime profiles). §1g operator-surface. Recover band (SDD-111 / E11.M111).

## Mission

Deliver **D-21 (LM Orchestration)** and **D-22 (LM Status & Operability)** to match the operator's
design sketches **in full — every section, all its content, visible**. The delivered panels
minimized the design: D-22's per-device "History | Selected" latency area was collapsed to a single
static row, the per-device Select bar was absent, only 2 of 3 Tests existed, and the operability
cluster wasn't shaped; D-21's Apply sat above the grid, the per-cell Mode was only a derived string,
and Features-CPU lacked the tiering + the Rowhammer row. This completes both to the design while
staying honest (R10212 signed-verb/exec-rail controls; SB-077 — un-backed content is shown as an
explicit **honest-deferred** row, never fabricated or dropped).

## The design (operator sketches — the delivery contract)

### D-21 — Profiles · Language Model
1. Profiles list (full-width): the 5 orchestration profiles — Full orchestration, Coding Focus,
   Thinking Focus, Hybrid Coding-and-Thinking, Full Hybrid (already surfaced; the 3 runtime profiles
   above them are *additive*, not a minimization).
2. **2×2 hardware×model quadrant** with a **central Apply**: GPU0 (RTX 4090) top-left · GPU1
   (RTX 6000 pro Blackwell) top-right · Ext-GPU ("Future Card" → N/A) bottom-left · CPU0 (Ryzen 9
   9900X AM5 AVX-512, core-ranges 1-7/8-15/16-24) bottom-right. Each present cell: Model 0/1/2 +
   an explicit **Mode:** field.
3. **Features CPU** (tiered T1/T2/T3 + "Etc… Rowhammer") | **Features GPUs** (real per-GPU caps).

### D-22 — Language Model Status & Operability
1. Three per-device blocks (CPU0 · GPU0 · GPU1), each: Model 0/1/2 tab row; a **History | Selected**
   two-column latency area (each column with its "Data"); and a right-side operability cluster —
   **Action X/Y/Z**, **Test A/B/C**, and a per-device **Select** bar.
2. Bottom: **Selected [CPU0][GPU0][GPU1]** device selector + **Chat** + **Input textarea**.

## Grounded design — what ships, and what honest-defers

### D-21 (`webapp/d-21-lm-orchestration/index.html`) — three de-minimizations (mostly layout)
- **Apply centered in the quadrant** — reposition `#apply-btn` from above `#grid` to a centered
  overlay of the 2×2 grid (CSS/layout only; the click still `jumpToControl('runtime-mode')` — the
  wired R10274 exec-rail card; R10212 preserved).
- **Explicit per-cell "Mode:" field** in `cellHtml()` — render the cell's mode as a labelled
  `Mode: <value>` read from the grid's `mode` (the derived active/idle) **and** the active profile's
  intent when present. Honest: shown from real state, never a settable/invented value (no producer
  for a settable per-device mode → it is a *display* of the current mode).
- **Features-CPU tiering + Rowhammer** in `renderFeatures()` — group the real AVX-512 flags under
  authored **T1/T2/T3** tier labels (the flags are real; the tiering is an authored presentation),
  and add an **"Etc… Rowhammer"** row rendered as an explicit **honest-deferred** entry ("no
  producer — deferred", never a fabricated ✓).

### D-22 (`webapp/d-22-lm-status-operability/index.html` + `scripts/operator/lm-status-operability-api.py`) — the real build
- **API `devices_view()` passthrough (honest-now):** extend it to include the snapshot's existing
  per-model **`heatmap`** (24h availability series) + **`kvcache`** (KV occupancy) already produced by
  `model-health.py::snapshot()` — no new computation, no fabrication; just surface real data the view
  currently drops.
- **True "History | Selected" two-column area** per device (replaces the single static row):
  - **Selected** column = the current metrics already in `devices_view` (status, context, p50/p95/p99,
    req/min) for the selected Model slot.
  - **History** column = the model's real **24h availability heatmap** (from the passthrough) rendered
    as a compact cell series; when a model has no heatmap series yet, the column renders an explicit
    **honest-deferred** "no history yet" state — **never a synthesized latency history**.
- **Per-device Select bar** inside each block's operability cluster — client-side selection of the
  active Model slot (drives which slot the History|Selected columns show). Pure client-side, no new
  fetch/POST (lint-safe).
- **Test C** — the third test slot the design shows. Tests A/B = the real `eval`/`bench` (→ the
  `eval-run` exec-rail control, already wired). Test C = an explicit **honest-deferred** slot
  ("device-scoped bench — no producer; Stage-N per SDD-055") — visible, disabled, reasoned; never a
  fake control.
- **Right-side operability cluster** — reshape Actions (X/Y/Z = load/toggle/override) + Tests (A/B/C)
  + the Select bar into the sketch's right-side cluster (layout; the wired `jumpToControl` targets +
  copy-signed-verb fallbacks are unchanged).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-111-A | D-22 "History" data source. | **answered: the real 24h availability `heatmap` (+ `kvcache`) from the snapshot, surfaced via `devices_view` passthrough**; honest-deferred when a model has no series. No fabricated latency history (SB-077). |
| Q-111-B | Un-backed design bits (Rowhammer, Test C). | **answered: render them as explicit honest-deferred rows/slots** (visible + reasoned, disabled) — "all sections shown" without fabrication. |
| Q-111-C | Per-device Mode / Select mutation. | **answered: display + client-side selection only.** Mode is displayed from real state; Select is client-side UI. Any actual mutation stays the signed profile/tier verb via the exec-rail (R10212). |

## Non-goals (Stage N)

- A settable per-device Mode or a per-slot "assign model to GPU" web mutation (that is the signed
  profile-switch verb — R10212; unchanged).
- A real Rowhammer probe / a device-scoped bench producer (no backing — honest-deferred).
- A synthesized latency time-series (SB-077 — History uses only the real heatmap or defers).
- New POST targets (only `/api/control/execute` + `/api/lm-status/chat` remain permitted).

## Stage 0 — this SDD + INDEX 111 + mandate E11.M111 + SDD-055 cross-ref

Specify the full sketched layout for both panels, the honest-now vs honest-defer split, the
lint-pin-preservation contract. Q-111-A/B/C. Recover band. (Cross-reference SDD-055 as the
button-wiring predecessor this completes the layout for.)

## Stage 1a — D-21 full layout

`webapp/d-21-lm-orchestration/index.html`: Apply-center overlay; per-cell `Mode:` field in
`cellHtml()`; Features-CPU T1/T2/T3 tiering + Rowhammer honest-defer row in `renderFeatures()`.
Extend `tests/lint/test_d21_lm_orchestration_webapp_contract.py` (Mode field present; the tier
labels; the Rowhammer deferred row is non-✓). Keep the 3-model-slot + `[GPU0,GPU1,EXT_GPU,CPU0]`
pins.

## Stage 1b — D-22 full layout + API extension

`scripts/operator/lm-status-operability-api.py` `devices_view()` → add `heatmap` + `kvcache`
passthrough (+ its API-contract-lint assertion). `webapp/d-22-lm-status-operability/index.html`:
the History|Selected two-column per device; the per-device Select bar; Test C honest-defer; the
right-side operability cluster. Extend `tests/lint/test_d22_lm_status_operability_webapp_contract.py`
(History + Selected columns; per-device select; 3 test slots incl. the deferred one; no new POST
target). Keep `[CPU0,GPU0,GPU1]` + 3-slot pins + the one-sanctioned-chat-POST lock.

## Stage 2 — verify + ship

- **Full gate** (`make test`) + the dispatch nspawn (grid `[GPU0,GPU1,EXT_GPU,CPU0]` / devices
  `[CPU0,GPU0,GPU1]` shapes + POST→405 + chat-is-the-one-POST) + `bash -n`.
- e2e (static + Node): both panels render every design section; the History column shows the real
  heatmap or an explicit deferred state (never fabricated); Rowhammer + Test C are visible-deferred;
  Apply is centered + still jumps to the exec-rail; no new fetch/POST target introduced.
- Commit the stages, push to `claude/recover-projects-b0oT6`, open a draft PR. Number SDD-111 /
  E11.M111. Re-branch from origin/main first.

## Safety invariants

R10212 — no new web-mutation: Apply/Actions/Tests remain `jumpToControl(...)` exec-rail cards + copy
signed verbs; Mode/Select are display + client-side selection; the only POSTs stay
`/api/control/execute` + `/api/lm-status/chat`; every other method 405. **SB-077** — un-backed
content (Rowhammer, Test C, a missing heatmap) renders as an explicit honest-deferred row, never
fabricated; the History column uses only the real `heatmap`. The `devices_view` passthrough surfaces
real snapshot data only. All contract-lint pins preserved (3 model slots; `[GPU0,GPU1,EXT_GPU,CPU0]`
/ `[CPU0,GPU0,GPU1]`; same-origin GET; standing-rule footer). MS003 `unsigned-pending-MS003`.

## Cross-references

- `webapp/d-21-lm-orchestration/index.html` + `scripts/operator/lm-orchestration-api.py` (grid /
  profiles / features).
- `webapp/d-22-lm-status-operability/index.html` + `scripts/operator/lm-status-operability-api.py`
  (`devices_view` / `_send_chat`) + `scripts/inference/model-health.py` (`snapshot`/`heatmap`/`kvcache`).
- `docs/sdd/055-lm-orchestration-wiring.md` — the button-wiring predecessor this completes the layout for.
- `tests/lint/test_d21_lm_orchestration_webapp_contract.py` + `test_d22_lm_status_operability_webapp_contract.py`
  + `test_lm_status_operability_api_contract.py`.
- M075 (SRP hardware roles), M076 (runtime profiles), R10212, SB-077.
