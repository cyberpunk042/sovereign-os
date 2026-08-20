# Tetragon kernel-fence not enforcing — root-cause findings — 2026-08-20

Source: first real end-to-end test of the Auditor perimeter on the SAIN-01 node (ai-workstation). A controlled capstone (throwaway podman container execs a non-allowlisted binary; expect SIGKILL) showed the fence **does not block** — the canary ran to completion. Everything upstream reported "green" because it only ever checked that files/services *exist*, never that the fence *enforces*.

## What was actually wrong (three layers)

1. **Policy in a directory the daemon never reads (FIXED).**
   `tetragon-policy-load.sh` writes to `SOVEREIGN_OS_TETRAGON_POLICY_DIR=/etc/tetragon/tracing-policies`, but Cilium's Tetragon 1.7.0 auto-loads from its configured `tracing-policy-dir` — package default **`/etc/tetragon/tetragon.tp.d`** (confirmed in the daemon config dump). So `tetra tracingpolicy list` was **empty**; the kprobe never attached. Fix: also install the fence into the daemon's effective dir + **verify load via `tetra tracingpolicy list`** (fail-loud). `doctor`/`auditor full` now report LOADED state, not file presence — the "green but blind" mode is closed.

2. **Ruled out (via monitor-mode isolation, action:Post, kills nothing):**
   - Syscall symbol: both `sys_execve` and `__x64_sys_execve` fire on host execs (29 / 20 events). Not the bug.
   - `execveat`: hooking it added zero events; the container entrypoint is not an `execveat` we can catch this way. Not the bug.
   - `enable-process-ns`: docs confirm `matchNamespaces host_ns` resolves in-kernel; not required.

3. **The real design flaw (DEFERRED — needs a design decision):**
   **`matchNamespaces: Mnt NotIn host_ns` is the wrong mechanism for "in a container."** On a systemd host, many *host* services run in private mount namespaces. Monitor evidence: the events that passed the `NotIn host_ns` filter were **`/usr/bin/python3.14` (16), `/usr/bin/udevadm` (2)** — host services — while the busybox container's own `id`/`busybox` execs never appeared. So the clause simultaneously:
   - **false-matches sandboxed host services** (a *safety* landmine: if enforcement ever fired, it could SIGKILL host services like `python3.14`, which is not in the 4-binary allowlist), and
   - **fails to reliably catch the podman container entrypoint** (the actual target — Weaver agents).
   The full enforce selector (`matchPIDs` + `matchBinaries` + `matchNamespaces` AND-ed) fired **zero** times (`NENFORCE=0`).

## Why this matters

This box is a **desktop workstation**, not the minimal SAIN-01 **appliance** the host-wide fence was designed for. Host scope would brick the desktop (561 live executables); container scope via `NotIn host_ns` is unsound here. So the enforcing fence is fundamentally awkward on this host.

## Options for the deferred design decision

- **A. Fence belongs on the minimal appliance only.** On this desktop, run the Auditor in observe/monitor (Post) mode, not enforce. Document that enforcement is an appliance-profile concern.
- **B. Real container identification.** Replace `matchNamespaces host_ns` with a mechanism that actually means "container": Tetragon cgroup/CRI container tracking (`enable-cri` / cgidmap), or a cgroup-path `matchData` filter, or `matchBinaries followChildren` seeded from the podman/conmon parent. Requires design + end-to-end validation (the capstone test is the acceptance gate).

Recommendation: pick A or B deliberately; do NOT ship the current `NotIn host_ns` enforce policy on a desktop — it is both ineffective and a latent danger to host services.

### Resolution (2026-08-20): A′ shipped — arming knob

Option A as literal "monitor/Post mode" was rejected: it violates the §4.1 operator-verbatim (`action: Sigkill`, NOT log-only; lint `test_load_hook_action_is_sigkill`). Instead shipped **A′**: `SOVEREIGN_OS_TETRAGON_ARMED` / `provisioning.tetragon.armed` (default **armed** = appliance posture). The action stays `Sigkill` (verbatim intact); the knob controls only whether the fence is **loaded** into the daemon. Disarmed = the policy file is written (verify.sh path preserved) but not loaded, and any loaded instance is removed → the desktop can never SIGKILL host services. Disarm this box: `sudo env SOVEREIGN_OS_TETRAGON_ARMED=0 bash scripts/hooks/post-install/tetragon-policy-load.sh`. (Minor follow-up: `auditor full` reports a disarmed fence as "NOT loaded (perimeter blind)" — technically true but should distinguish intentional disarm from accidental blind.)

### Resolution (2026-08-20): B solved — cgroup matchData container scope

The container scope's `matchNamespaces: Mnt NotIn host_ns` was replaced. Two mechanisms were empirically disproven in monitor mode: matchNamespaces (matched every sandboxed host service — systemd/NetworkManager/python), and `matchParentBinaries(conmon,crun) followChildren` (matched podman's host-side network cascade — netavark + triggered nm-dispatchers + host python3.14). The precise discriminator is the **cgroup**: podman gives a container's workload a leaf cgroup literally named `container` (`.../libpod-<id>.scope/container`); host services carry their `*.service` name. A `matchData` block resolving `cgroups.dfl_cgrp.kn.name` + `Equal "container"` matched **only** the container's execs (`/bin/sh`, crun's `/dev/fd/3`) and **zero** host binaries in monitor validation. Implemented in `tetragon-policy-load.sh` (container scope) + knobs lint + `test_container_scope_uses_cgroup_matchdata`. Needs no extra daemon flags (unlike matchParentBinaries, which needs `--parents-map-enabled`). Acceptance gate: `perimeter-capstone.sh` — canary dies, host services live. Known refinement: a container entrypoint that IS an allowlisted binary (e.g. python3 agent) is fexecve'd as `/dev/fd/N`, which isn't in the allowlist — may need `/dev/fd/*`-aware handling so legitimate allowlisted agents aren't killed at launch.

## Acceptance test (already written)

`~/.openclaw/workspace/perimeter-capstone.sh` (+ `tetragon-fence-diagnose{,2,3}.sh`) — the canary must die (rc≠0) and a `security_audit.log` line must appear. Wire an equivalent into `bootstrap verify` so "fence enforces" is checked, not just "fence file present."

## Related latent bug (separate)

Even once the fence enforces, Guardian's `parse_event` expects a flat `action`/`process.docker` shape; the real Tetragon event is nested `process_kprobe` with `action: "KPROBE_ACTION_*"` and `process.binary`/`process.exec_id` (sample captured 2026-08-20). Guardian will read real violations as benign until `parse_event` is updated to the nested shape.
