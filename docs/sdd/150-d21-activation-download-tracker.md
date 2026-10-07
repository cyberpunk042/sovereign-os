# SDD-150 — D-21 profile activation & download tracker modal (whole-pipeline progress)

> Status: complete — shipped + verified on branch
> Owner: operator-directed; agent-authored
> Last updated: 2026-10-07
> Closes findings: operator directive 2026-10-07 — *"We need to add a modal for the sovereign-os profile activation and download, so we can track the whole progress including what is hidden by the backend and the language model being loaded (page / cockpit d-21-lm-orchestration)"*. Before this, the D-21 profile bring-up was three disconnected inline fragments: the inspector's download line (`queued/preflight/downloading/verifying` + raw GiB text, no phase meaning), the Apply result one-liner, and per-model download status rows that only appeared while the SSE refresh happened to catch them. The download job's real sub-states (transfer-lock queue, repo preflight, disk-space gate, SHA-256 verification, interrupted-resume) and the actual language-model load evidence (declared model vs model resident per tier) were invisible. Recover band (SDD-150 / E11.M150 per SDD-100).
> Derived from / extends: SDD-043 (orchestration-profile families + Apply), SDD-045 §4 (the `model-download` control-system + exec-rail posture), SDD-049 (signed model-load + `model-state.json` residency), SDD-116/117 (DEMO-mode posture this modal obeys), `scripts/models/download-job.py` (the job state machine surfaced here), and the deployment deck's doctrine "applying a profile is not evidence that its models became resident." §1g operator-surface.

## Mission

One modal on D-21 that tracks the WHOLE profile bring-up end-to-end: (1) every
catalog model download with its backend phase named and byte progress shown,
(2) the signed apply (`trinity profile switch` through the control-exec rail),
and (3) each declared tier's language model becoming **resident** on its device
— the part the backend hides: after the switch returns, models unload/reload
per tier, and only the live grid proves it happened.

## Design

**Trigger.** The profile inspector gains a `Progress tracker` button on every
non-generated profile (openable any time, not only at act time), and both
`Download / resume missing models` and `Apply this profile` open the modal as
they start. Modal id `#so-act-modal`; same chrome/posture as the provider /
notification / compat modals (fixed overlay, `role="dialog"` +
`aria-modal`, Escape + backdrop close, theme-aware light overrides).

**Three stages, one pipeline:**

1. **① Catalog model downloads** — one row per declared-but-absent model from
   `missing_models[].download` (the `model-download` job state written by
   `scripts/models/download-job.py`). The chip shows the job state verbatim
   (`queued / preflight / downloading / verifying / complete / failed /
   interrupted`), a bar + GiB counts while running, and a plain-language phase
   line exposing what the backend is actually doing: transfer-lock queue
   (one large transfer at a time), HF repo listing + artifact selection +
   vault disk-space gate, streaming with partial-file resume, SHA-256 + size
   verification, and interrupted-job resume semantics. Failures show
   `error_stage` + `error_type` (the job deliberately carries no raw HTTP text).
2. **② Signed profile apply** — the `runtime-mode` / `orchestration-profile`
   control through the sanctioned `:8130` rail (same `applyProfile()` path the
   card buttons use; family-routed enum). States map the rail's real answers:
   waiting / posting / dry-run / applied / active / conflict (single-flight
   lock) / blocked (422 prerequisites) / denied (403 key) / read-only origin /
   rail-unreachable — with the exact CLI copyable throughout.
3. **③ Language model loading** — per declared tier: the profile's model vs
   the model actually bound on the role's device (the deck's role mapping,
   `router` resolving `embed`/`rerank`). `pending` before the marker moves,
   `loading` when the profile is active but the binding is stale or not yet
   `active`-mode, `live` when declared == resident && serving. A profile that
   prescribes no catalog models says `not prescribed` — honest, not empty.

**Completion** = active marker names the profile AND every declared tier's
model is resident — never "the apply returned OK" (the deck's doctrine). The
poller stops once settled; the modal stays open as an evidence surface.

**Data + writes.** Live state comes only from the panel's read-only endpoints
(`/api/lm-orchestration/profiles` + `/api/lm-orchestration/grid`), polled at
2 s ONLY while the modal is open; polls also feed the normal panel renderers so
there is no second divergent view. Writes reuse the existing sanctioned rail
controls (`model-download`, `runtime-mode`/`orchestration-profile`) — no new
control, no new daemon, no sudoers/osctl-chain edit (R10212 preserved; the web
never mutates directly).

**DEMO mode (SDD-116/117 posture).** `actOpen()` returns before starting any
timer when DEMO is on; the modal renders a badged sample pipeline (`demo/…`
ids, one downloading row, one complete, one not-started, mixed tier residency)
with action buttons disabled — zero network, never confusable with live.

## Doctrine notes

- "We do not minimize anything" (§1g): the tracker surfaces the download
  job's hidden phases and the per-tier residency evidence rather than a
  generic spinner; every refusal state (denied/blocked/conflict/read-only)
  says what it means and carries the copyable exact command.
- SB-077: no fabricated progress — byte counts come from the job's own
  progress monitor; the load stage is inferred ONLY from declared-vs-resident
  grid data, labeled per state.
- **Residence ≠ traffic (2026-10-07 addendum, operator report):** an early
  revision gated the per-tier `live` chip on the grid's `mode` field — which
  is `util_pct > 0`, i.e. TRAFFIC — so an idle-but-correctly-bound oracle and
  logic pair sat at `loading` forever. Load-complete is exactly one fact:
  `resident == want` (the binding). Utilization now only decorates the row
  (`· serving` vs `· bound, route idle`). Pinned both ways in the contract
  lint (required expression + banned util-gated form).
- An interrupted download job (rebooted worker) is surfaced as `interrupted`
  with resume guidance, never a permanent spinner (the job file's own PID
  liveness rule is what feeds it).

## Verification

- `tests/lint/test_d21_lm_orchestration_webapp_contract.py` — new
  `test_activation_tracker_modal` (modal chrome, three stage anchors, phase
  vocabulary from the job state machine, exec-rail reuse, completion semantics,
  per-profile Track button) + all pre-existing D-21 pins green.
- `tests/lint/test_demo_mode_contract.py` — D-21 demo pins extended:
  `actDemoState` + `actOpen` returns before any poll in DEMO (zero network).
- Live smoke (jsdom harness against the real `lm-orchestration-api` daemon on
  this host, 29 live profiles): Track button renders in the inspector, modal
  opens with all three stages populated from live data, close hides + clears
  the timer, zero page JS errors.
