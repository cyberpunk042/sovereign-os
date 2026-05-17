# SDD-036 — Inference-service hardening doctrine (E2.M8 / R346)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E2.M8 ("systemd service hardening lint (R171 doctrine
> extension)" partial → ✓)
> Derived from: R160 (initial defense-in-depth pass) + R171 (10-key
> baseline lint) + the lived practice of pulse/logic-engine/oracle-core/
> router unit hardening across R225-R310

## Mission

The 4 inference daemons — `sovereign-pulse`, `sovereign-logic-engine`,
`sovereign-oracle-core`, `sovereign-router` — accept **attacker-controlled
prompt text** at runtime and **parse downloaded model files**. They run
inside a process that has CUDA/GPU access. A successful RCE there is a
catastrophic blast-radius incident.

R171 baseline (10 directives, ambient services) is the floor. The 4
inference services deserve a stricter posture on top of it. SDD-036
formalizes that stricter posture so:

- A new inference service added in a future round inherits the bar
  by being added to the lint's `INFERENCE_SERVICES` set.
- An accidental relaxation (operator deletes
  `MemoryDenyWriteExecute=true` while debugging) fails L1 at push.
- The operator-rationale waiver pattern is consistent (inline `#`
  comment on the assignment line; matches the existing
  `RestrictNamespaces=false  # podman compatibility` convention).

## The contract — every inference service MUST

### 1. R171 baseline first

All 10 R171 baseline directives apply unconditionally (`ProtectHome`,
`ProtectKernelTunables`, `ProtectKernelModules`, `ProtectControlGroups`,
`ProtectClock`, `ProtectHostname`, `RestrictRealtime`, `RestrictSUIDSGID`,
`RestrictNamespaces`, `LockPersonality`). R171 lint enforces them already.

### 2. Two harder-posture directives

```ini
[Service]
# REQUIRED — accept true OR false-with-inline-rationale
MemoryDenyWriteExecute=true
# REQUIRED — must enumerate AF list (no AF_UNSPEC, no `any`)
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
```

### 3. Inline-comment waiver pattern

`MemoryDenyWriteExecute=false` is acceptable WHEN AND ONLY WHEN the
service legitimately needs writable-executable mappings (codegen, JIT).
The rationale MUST appear inline on the assignment line:

```ini
MemoryDenyWriteExecute=false  # vLLM/Triton JIT-compile CUDA kernels at request time
```

The lint detects the `#` on the assignment line and accepts. Empty
value (`MemoryDenyWriteExecute=`) is rejected — operator must explicitly
choose true or false-with-rationale.

`RestrictAddressFamilies` requires an enumerated AF list. The lint
rejects `any`, `true`, `false`, or any value containing `AF_UNSPEC`
(which would defeat the directive).

### 4. Whole-unit waiver still honored

A unit-level `# HARDENING-WAIVER: <reason>` (same as R171) opts the unit
out entirely. Operator-pull use case: a sandboxed integration-test unit
that legitimately can't be hardened. SDD-036 keeps this consistent with
R171's whole-unit waiver.

## Current shipped posture

| Service | MDWX | RestrictAddressFamilies |
|---------|------|--------------------------|
| sovereign-pulse | =false (bitnet.cpp dlopen .so) | AF_UNIX AF_INET AF_INET6 |
| sovereign-logic-engine | =false (vLLM/Triton JIT codegen) | AF_UNIX AF_INET AF_INET6 AF_NETLINK |
| sovereign-oracle-core | =false (vLLM/Triton + DFlash JIT codegen) | AF_UNIX AF_INET AF_INET6 AF_NETLINK |
| sovereign-router | =true | AF_UNIX AF_INET AF_INET6 |

Note: `sovereign-router` is the proxy front-end and does NOT do codegen —
it can run with W^X. The 3 backend daemons cannot, and carry inline
rationale. This is the expected pattern; the lint encodes exactly this.

## L1 lint enforcement

`tests/lint/test_systemd_unit_hardening.py` pins:

- `INFERENCE_SERVICES` set lists exactly the 4 services
- `test_inference_units_present` — drift catch (rename / delete)
- `test_inference_service_harder_posture` — per-service requires
  `MemoryDenyWriteExecute` (true OR false+rationale) AND
  `RestrictAddressFamilies` (enumerated AF list)

A future inference service (e.g. a 5th model backend) MUST be added to
`INFERENCE_SERVICES` AND ship the 2-directive posture.

## What this SDD does NOT do

- It does NOT force `MemoryDenyWriteExecute=true` for codegen-needing
  services — the operator-rationale waiver exists precisely because
  CUDA/Triton break under W^X.
- It does NOT pin `SystemCallFilter=` (that's a R171 future extension
  candidate; tracking but not enforced yet — too many false positives
  on first pass).
- It does NOT pin `CapabilityBoundingSet=` (also future R171 extension;
  the inference services drop most caps already but the diff between
  "minimal" and "current" is too small for L1 enforcement).
- It does NOT replace operator judgement — every waiver has a visible
  rationale comment the operator can audit.

## Future-quarter hardening extensions

Tracked as future R171 baseline candidates (not enforced today):

- **`SystemCallFilter=@system-service`** — already on `sovereign-router`;
  needs piloting on a codegen backend before fleet-wide pinning.
- **`CapabilityBoundingSet=`** — most services already drop everything
  except `CAP_NET_BIND_SERVICE` / similar; L1 lint pin pending a
  per-service caps audit.
- **`ProcSubset=pid`** — defeats `/proc`-based info-leaks. May break
  observability tooling; pilot on one service first.

## Doctrine evolution

If a 5th inference backend ships:

1. Add unit `systemd/system/sovereign-<name>.service`
2. Carry R171 baseline (existing lint enforces)
3. Carry SDD-036 harder posture (2 directives + inline rationale if W^X)
4. Add the service name to `INFERENCE_SERVICES` in
   `tests/lint/test_systemd_unit_hardening.py`
5. R285 quarterly review verifies the table in this SDD stays current
