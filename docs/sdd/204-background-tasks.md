# SDD-204 — Background Tasks (a job runtime + a Code Console Plan-pane split, like claude.ai/code)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-12
> Closes findings: operator directive 2026-07-12 — *"do we also support Background Tasks, like on Claude ai code, (my rtx4090 jobs I guess or a secondary model in general), there is a supplementary pane that can be displayed to look at what those tasks are doing … it resize the Plan pane on the right to make it half and half."* Plan approved (runtime + Plan-pane split + 4090-VM bridge).
> Derived from / extends: SDD-112 (Code Console — the right Plan/artifact pane this splits), SDD-045 (control-surface / control-exec-api — the sanctioned execute path), the CoAT engine (`/v1/coat` — a background job kind), R10212 (read-only panels), SB-077 (honest live vs deferred). §1g operator-surface.

## Mission

Give the box **Background Tasks** the way claude.ai/code has them: long-running work runs OFF the request
path, and a **supplementary pane splits the Code Console's right Plan pane 50/50** so the operator watches
what those tasks are doing — a background CoAT deliberation, a model eval, a secondary-model load, a GPU
job, and jobs mirrored from the **RTX-4090 passthrough VM**.

## What ships

1. **Runtime** — `scripts/operator/jobs-api.py` (:8142) over `scripts/operator/lib/jobs_store.py`, a
   PERSISTED registry (atomic temp+rename → survives restart) + a bounded worker pool that drives a job
   queued→running→(done|failed|cancelled) with live progress. Kinds: `deliberation` (calls the gateway
   `/v1/coat`), `eval` / `model-load` / `gpu-job` (a generic no-shell subprocess runner with PID-tracked
   cancellation), `demo` (dependency-free lifecycle), and `vm-job` (mirrored, not host-run). Orphaned
   `running` jobs from a dead worker are marked failed on restart (never a zombie).
2. **CLI + sanctioned write path** — `sovereign-osctl jobs list|status|submit|cancel`
   (`scripts/operator/lib/jobs_cli.py`). `list`/`status` are read-only; **submit/cancel are the ACTIONS**
   the cockpit routes through `control-exec-api` (allowlist + dry-run-default + operator-key + audit) — the
   pane itself never POSTs a mutation (R10212).
3. **The Plan-pane split** — the Code Console's `#cc-plan` right pane divides 50/50: Plan/artifact on top,
   a live **Background Tasks** list below (state · progress bar · kind · device · elapsed · cancel), fed by
   a read-only `code-console-api` proxy `/api/code-console/jobs`. A header toggle shows/hides it (persisted);
   cancel + "＋ deliberate" copy the signed `sovereign-osctl jobs …` verb (never a web mutation). Graceful
   when the runtime is down ("runtime offline"). DEMO-safe (zero network in DEMO — SB-077).
4. **4090-VM bridge** — the RTX 4090/3090 are VFIO-passed to a guest VM, so the host can't see their GPU
   jobs directly. `scripts/jobs/vm-bridge-guest.py` runs INSIDE the guest, probes its `nvidia-smi`, and
   POSTs entries to the host `jobs-api` `POST /jobs/ingest`, which upserts them as `vm-job` rows.
5. **Fleet** — `systemd/system/sovereign-jobs-api.service` (R171-hardened; jobs dir read-write),
   feature-coverage maps `jobs → code-console`, contract test `tests/lint/test_jobs_runtime_contract.py`.

## Honest gating (SB-077)

The runtime, the pane, the CLI, and the ingest protocol are **live and tested**. The one deployment-specific
piece is the guest→host **channel** for the VM bridge (the guest must reach the host jobs-api — libvirt NAT
gateway IP or a virtio-vsock proxy, set via `SOVEREIGN_JOBS_HOST`); until wired, the guest agent is inert
(it probes but does not report) and says so. Model-backed thought generation for `deliberation` jobs is the
same model-gating the CoAT engine already discloses.
