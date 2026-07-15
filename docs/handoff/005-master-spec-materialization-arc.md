# Handoff 005 — Master spec materialization arc R145-R163 (2026-05-16)

> Read this first if you are starting a new session on `sovereign-os`.
> Supersedes: `004-operator-friction-audit.md` (Round 144 close).
> Last updated: SDD-716 python3 resolver sweep closure (2026-07-15).
> R201 --apply gate + Q-014 destructive-loop scaffold were closed in the
> prior session. This session completed a systematic linuxbrew-PyYAML-gap
> fix across 15+ scripts and 10+ tests (common.sh, osctl, onboard,
> live-build-emit, friction-audit-spec, eval/info/suggest/fine-tune tests,
> dashboard buffering, oc-headroom GPU-sampler tolerance, stale
> schedule-manifest step counts, first-login-assistant resolver).

## TL;DR — what's at HEAD now

Rounds 145-163 (19 direct-to-main commits) closed the
**master-spec-materialization arc** AND a four-round follow-up arc
that hardened the production surface + made it operator-discoverable. The 1139-line SAIN-01 master
specification (info-hub `raw/dumps/2026-05-15-sain-01-master-spec-...
.md`) now has a real, tested, operator-runnable surface in the repo
for every load-bearing section.

State at HEAD (`main` = `52dcc3d`):

- **Documentation tier (R145-R148)**
  - `README.md` rewritten as a path, not a feature catalog
  - `docs/src/sain-01-master-spec.md` — operator-readable rendering
  - `docs/src/operator-journey.md` — 6-stage lifecycle map
  - 5 per-profile pages: sain-01, old-workstation, minimal, developer, headless

- **Trinity surface (R149-R151)**
  - `sovereign-osctl trinity {status|pulse|weaver|auditor|profile}`
  - 3 runtime profiles (master spec § 18):
    `profiles/runtime/{ultra-sovereign-efficiency, high-concurrency-burst, deep-context-synthesis}.yaml`
  - `scripts/build/lib/runtime-profile.sh` — env-first override library
  - `start-{pulse,logic-engine,oracle-core}.sh` honor active profile

- **Trinity execution machinery (R152-R155)**
  - R152 Pulse: `scripts/pulse/build-bitnet.sh` — bitnet.cpp from
    source with znver5 + AVX-512 (master spec § 15-17)
  - R153 Pulse: `scripts/pulse/wasm-aot.sh` — Wasm-to-AVX-512 AOT
    pipeline (master spec § 20)
  - R154 Weaver: `scripts/weaver/atomic-state.py` — Atomic State
    Transition Protocol (master spec § 21)
  - R155 Auditor: `scripts/auditor/guardian-core.py` +
    `systemd/system/sovereign-guardian-core.service` — eBPF circuit
    breaker (master spec § 10)

- **Inference fabric (R156-R157)**
  - R156 `models/catalog.yaml` + `schemas/model-catalog.schema.yaml` —
    8-entry canonical catalog (5 verified-real on HF Hub + 3
    aspirational with closest_real_alternative)
    `scripts/models/{pull,verify}.sh`
  - R157 `scripts/inference/dflash-wrap.sh` + `docs/sdd/026-...md` —
    task-type-gated speculative decoding (master spec Block 7)

- **Substrate fabric (R158-R159)**
  - R158 `scripts/network/render-asymmetric.sh` — verbatim master
    spec § 8.1 Zero-Trust renderer (Intel I226-V mgmt VLAN 100 + 10.0
    .100.50/24 + gateway; Marvell AQC113C data VLAN 200 + 10.0.200.50
    /24 + MTU 9000 + NO gateway)
  - R159 `scripts/bootstrap/verify.sh` +
    `sovereign-osctl bootstrap verify` — master spec § 22 6-check
    operational grid with lock-state semantics

## Follow-up arc (R160-R163)

- **R160** — Long-running systemd service hardening pass (defense-in
  -depth directives across pulse/logic-engine/oracle-core/router) +
  extended `tests/lint/test_systemd_unit_hardening.py` with the
  ProtectHome/ProtectKernelTunables/ProtectControlGroups/
  LockPersonality/RestrictRealtime bar for long-running services.
  Also extended metric-inventory lint to detect Python `_emit_metric`
  call sites (caught 6 weaver+auditor metrics the prior pattern missed)
  + added 18 missing metric inventory rows + missing SDD-026 INDEX row.
- **R161** — Router task_type classification (closes the R157
  follow-up explicitly noted in SDD-026). `classify_task_type()` over
  request body; per-request `X-Sovereign-Task-Type` HTTP response
  header; `sovereign_os_inference_router_task_type_total{task_type}`
  Layer B counter; operator override via `sovereign_os_task_type`
  request field.
- **R162** — `sovereign-osctl bootstrap phases` — master spec § 12
  chronological 5-phase pipeline artifact inventory. Companion to R159
  verify (§ 22): verify runs the LIVE grid; phases inventories the
  AUTHORING artifacts that build to that gate. 25 artifacts inventoried
  across Phase I-V, all present at HEAD.
- **R163** — `sovereign-osctl overview` — consolidated single-screen
  status snapshot composing phases (§ 12), verify (§ 22), trinity
  (§ 17), models (§ 17/18), perimeter (§ 10) into one observable
  surface. JSON output for fleet aggregation; drill-down hints in
  human output. The "first command to run" after fresh clone or
  post-install.

## Continuation arc (R164-R203, in progress)

Continued NEVER STOP execution past the R145-R163 arc. Highlights:

- **R164-R199** — cycle-2/cycle-3 selfdef bridges + cross-repo
  observability fabric: hardware-aware module gate mirror (R170/R193),
  model-registry mirror + checksum verification (R182/R190/R196),
  recommendation matrix shared helper (R185/R186/R188), per-profile
  thermal thresholds (R172/R175), wasm-aot bridges (R167/R168),
  pulse/router task_type (R178), Grafana dashboards (R197), capabilities
  JSON lockstep (R189), signing-audit + resources-audit cross-repo
  audits (R195/R198), fleet-aggregate file-based variant (R199).

- **R200** — `sovereign-osctl audit cycle3` — single-entry-point
  umbrella that runs every cycle-2+3 audit sub-tool
  (signing-audit + resources-audit + cycle2-status) and aggregates
  the exit code. Operators get one verb instead of three.

- **R201** — `sovereign-osctl bootstrap run --phase N [--json]` —
  master spec § 12 phase executor (DRY-RUN-ONLY). Closes the long-
  standing handoff item: phases (R162) inventories artifact presence,
  verify (R159) runs the live § 22 grid, run (R201) emits the
  execution plan + classifies each artifact's runtime surface
  (build-step / installer-hook / post-install-hook / recurrent-hook
  / systemd-unit / tooling). --apply intentionally not wired this
  round (Phase III-V artifacts are destructive — needs L5 + a
  SOVEREIGN_OS_CONFIRM_DESTROY gate).

- **R202** — `config/bootstrap/phases.yaml` canonical source +
  `scripts/bootstrap/lib/load-phases.py` loader. Collapses the two
  duplicated PHASES arrays in phases.sh + run.sh into ONE YAML; both
  scripts re-parse on every invocation. R201's drift guard moves from
  "count match" to "byte-identical source" since drift is structurally
  impossible.

- **R203** — phase pre/post-conditions added to phases.yaml +
  `scripts/bootstrap/lib/render-phases-md.py` doc renderer +
  `docs/src/bootstrap-phases.md` operator-readable rundown
  auto-generated from the same source.
  `sovereign-osctl bootstrap docs --check` (CI-gated) catches stale
  on-disk doc edits. Five complete consumer surfaces now share the
  same YAML: inventory (phases.sh), executor (run.sh), doc
  (bootstrap-phases.md), schema lint (test_bootstrap_phases_yaml.py),
  freshness gate (--check).

## Continuation arc (R204-R217) — cross-repo SD-R64..R73 alignment

- **R204** — handoff doc trajectory update through R203.

- **R205-R208** — SDD-028 canonical-source pattern codification +
  four applications: model catalog doc renderer (R206), verify-grid
  doc renderer (R207), trinity runtime-profile doc renderer (R208).
  Doctrine: drift between rendered docs and canonical YAML is
  structurally impossible — every consumer re-parses on invocation.

- **R209-R211** — sovereign-os mirrors of the selfdef SD-R64/R66/R67/
  R68 hardware-exploit surface (cross-repo lockstep per SDD-022):
  R209 mirrors SD-R64 (ternary_aot_capable + zmm_int8_lane_capacity
  predicates) on the R170 modules-gate, R210 ports SD-R67 posture
  verb to `sovereign-osctl bootstrap posture`, R211 mirrors SD-R68
  `host_features_required` predicate + lockstep R189 fixture to
  schema 1.4.0.

- **R212** — model-catalog R212 expansion (schema 1.0.0 → 1.1.0):
  full taxonomy (class × quantization × size_class × purpose ×
  vram_gib_min × context_window_tokens × base_model), 8 → 17
  curated entries spanning LLM / SLM / RLM / TernaryLM /
  LoRA-adapter / Embed / Vision / Multimodal / Code / Mixture /
  Speculative / Reranker. Operator-directive verbatim ("all the
  best selection of models adapted for various size and at various
  quantization or for various specific purpose").

- **R213** — `sovereign-osctl models query` filter surface over the
  R212 catalog (class / tier / purpose / size / quant / max-vram /
  min-context / status / engine / base-model — AND-composing). One
  command answers "which models fit my budget for this purpose?".

- **R214** — `sovereign-osctl models suggest --runtime-profile <id>`
  profile-aware super-feature. Cross-references each master-spec § 18
  allocation against the catalog, flags aspirational/VRAM-overrun,
  suggests smaller-quant alternatives.

- **R215** — router `sovereign_os_inference_router_class_total{class}`
  Layer B counter + `X-Sovereign-Model-Class` response header.
  Operators observe model-class demand cross-tabbed with tier
  routing. Inference table maps well-known model ids to R212 class
  values (bitnet → ternary-lm, r1-distill → rlm, coder → code, …).

- **R216** — `models suggest --gpu-vram-gib X,Y` host-budget override.
  Operators on non-SAIN-01 hosts get advice tuned to actual hardware,
  not the pinned profile defaults.

- **R217** — `sovereign-osctl overview` surfaces R214 suggester
  result for active runtime profile (defaults to
  high-concurrency-burst; SOVEREIGN_OS_RUNTIME_PROFILE env override).
  Single overview verb now also answers "is my profile fittable?".

Cross-repo: SD-R64..R73 land in lockstep on selfdef PR #192
(never-ending cycle-3 branch). SDD-022 (hardware-exploit doctrine)
+ SDD-023 (model-taxonomy mirror doctrine) codify the cadence so
future operator-pulled fields follow the same 6-layer pattern.

## Continuation arc (R218-R228) — operator dashboard + autohealth + notify

Closes the SDD-026 dashboard / Z-vector grid named by the operator's
2026-05-17 expansion ("LM Studio / dashboard / scans / autohealth /
notification / messaging / multi-tier REPL"). Each Z-vector is a
named operator surface; rounds below close one each.

- **R218-R224** — Z-3/Z-4/Z-5/Z-7/Z-9/Z-10 read-only hardware probes:
  flex profile, cpu-mode show, gpu-watch deviance, network-status,
  raid-status, fs-insights. All ship as operator-card + JSON for
  cross-surface consumption (terminal, dashboard, future MCP).
- **R225** — Z-1 dashboard SEED: stdlib http.server aggregator with
  --render-only + --once + --bind, /api/health + /api/<card> JSON
  endpoints. 23-assertion L3.
- **R226** — Z-6 SCAN layer: `sovereign-osctl health scan` composite
  autohealth/doctor across all 6 probes with severity model
  (ok/attention/informational/down). rc=1 when any probe needs
  operator attention. 21-assertion L3.
- **R227** — dashboard `Models` tab + `Health` tab: R225 grows two
  more cards (R212 catalog × R214 suggester × 3 runtime profiles +
  R226 health rollup). Card count 6 → 8.
- **R228** — Z-6 FAN-OUT: `sovereign-osctl notify dispatch` reads R226
  --json + delivers to file/webhook/ntfy channels. Per-probe dedupe
  via state file (transitions only — no spam). Env-var keys per
  SDD-009 (operator secrets never in-repo). 25-assertion L3.

Cross-repo cycle-8 selfdef rounds in lockstep: SD-R83 modules-diff
(Z-13 partial), SD-R84 MCP tool manifest (Z-11), SD-R85 REPL Tier 1
Python bootstrap (Z-12).

## Test inventory added this arc

| Round | L3 test | Tests | Layer |
|-------|---------|-------|-------|
| 149+150 | test_trinity.sh | 45 | L3 |
| 150 | test_runtime_profile_schema_conformance.py | 11 | L1 |
| 151 | test_runtime_profile_honoring.sh | 16 | L3 |
| 152 | test_pulse_build_bitnet.sh | 29 | L3 |
| 153 | test_pulse_wasm_aot.sh | 18 | L3 |
| 154 | test_weaver_atomic_state.sh | 28 | L3 |
| 155 | test_auditor_guardian_core.sh | 38 | L3 |
| 156 | test_model_catalog_schema_conformance.py | 8 | L1 |
| 156 | test_models_catalog.sh | 28 | L3 |
| 157 | test_dflash_wrap.sh | 21 | L3 |
| 158 | test_network_asymmetric.sh | 39 | L3 |
| 159 | test_bootstrap_verify.sh | 33 | L3 |
| 160 | test_systemd_unit_hardening.py (extended) | +12 | L1 |
| 161 | test_inference_router_http.sh (extended) | +8 | L3 |
| 162 | test_bootstrap_phases.sh | 31 | L3 |
| 163 | test_sovereign_osctl_overview.sh | 22 | L3 |

Total: 11 new L3 tests + 2 new L1 schema-conformance suites + 1 L1
hardening lint extension + 1 L1 metric-inventory lint extension. CI
wired in `.github/workflows/test.yml`.

## What to do FIRST in the next session

Resume the NEVER STOP `/goal` directive. Status of prior follow-ups:

- ~~Q-012 closure (Q3 → 3/3)~~ — DONE (headless profile shipped earlier
  with role-headless mixin + auditd/fail2ban posture).
- ~~Reproducibility wiring (SDD-019 gap)~~ — DONE (SOURCE_DATE_EPOCH +
  DEBIAN_SNAPSHOT propagation present in 04-kernel-compile.sh +
  mkosi-emit.sh; 09-image-verify.sh emits sha256sums.txt).
- ~~Build-step source short-circuit (Q18-A)~~ — DONE (steps 02-04
  exit-0-skip when `profile.kernel.source` is substrate-default).
- ~~systemd unit hardening pass~~ — DONE (all 21 service units carry
  ProtectSystem=strict + NoNewPrivileges + PrivateTmp at HEAD).
- ~~R157 follow-up~~ — DONE in R161 (router classifies task_type +
  emits `sovereign_os_inference_router_task_type_total`).
- ~~Master spec § 12 chronological pipeline phases (bootstrap run
  --phase 1..5)~~ — DONE in R201/R202/R203 (DRY-RUN-ONLY executor +
  canonical YAML source + auto-rendered operator doc).

Genuinely open + concrete:

- ~~**R201 --apply gate**~~ — DONE. Triple-gate (`--apply` +
  `--confirm-apply` + `SOVEREIGN_OS_CONFIRM_DESTROY=YES`) wired in
  `run.sh` with interactive confirm / `--force` override. Phase I
  safe-skip test passes L3 (build-step + config skipped). Phase
  III-V execution requires Layer 5 SAIN-01 hardware; gate semantics
  verified in CI.
- ~~**Q-014 Layer 4/5 destructive-loop test**~~ — DONE (scaffold +
  disk-safe probe). `tests/qemu/destructive-loop.sh` boots the image
  with `-snapshot` (disk writes discarded) + serial-socket monitor,
  verifies the guest reaches the login prompt and carries sovereign
  branding. Full SSH-injection destructive command loop remains
  operator-driven on real hardware; the scaffold is now executable
  code, not a comment block.
- ~~**SDD-716 python3 resolver sweep**~~ — DONE. linuxbrew Python 3.14
  lacks PyYAML; first-in-PATH python3 on the dev host caused ~15 scripts
  and ~10 tests to fail. Centralized resolver in `common.sh` + targeted
  fixes in `osctl`, `onboard.sh`, `live-build-emit.sh`,
  `friction-audit-spec.sh`, and the affected L3 tests.
- **SDD-021 W-5 sigstore integration** — LOW priority; minisign is
  the in-tree signing primitive, sigstore is the cross-fleet option.
- **Cross-repo: selfdef SDD-020 V-3/V-4/V-6** — out of scope for the
  sovereign-os main workflow per the original plan envelope; revisit
  if operator redirects.

## Standing rules (unchanged across arcs)

- Direct push to `sovereign-os` `main` — no PR ceremony.
- Every commit substantive + tested + goal-traced commit message.
- Never include the model identifier in any pushed artifact.
- Operator words sacrosanct — quote verbatim in SDDs + scripts.
- SOVEREIGN_OS_CONFIRM_DESTROY=YES required for destructive operations.
- Operator-supplied signing keys (PK/KEK/db) NEVER live in-repo.
- After every round, the trajectory tracker (this file or a new
  handoff anchor) gets a single-line update.

## Critical files (high-traffic across this arc)

- `scripts/{pulse,weaver,auditor,models,network,bootstrap}/*` — newly
  authored Trinity execution + substrate scripts
- `scripts/inference/{dflash-wrap,start-*}.sh` — speculative decoding +
  start-script honoring
- `scripts/sovereign-osctl` — bootstrap + trinity verbs
- `profiles/runtime/*.yaml` — 3 master-spec § 18 profiles
- `profiles/sain-01.yaml` — verbatim § 8.1 network values
- `models/catalog.yaml` — declared model catalog
- `schemas/{model-catalog,runtime-profile,profile}.schema.yaml`
- `systemd/system/sovereign-guardian-core.service` — § 10.2 verbatim
  unit declarations
- `tests/nspawn/test_*.sh` — 9 new L3 tests
- `tests/schema/test_*.py` — 2 new L1 schema-conformance suites
- `docs/sdd/026-dflash-speculative-decoding.md` — gating policy SDD
- `docs/src/sain-01-master-spec.md` — operator-readable spec rendering
- `docs/src/operator-journey.md` — 6-stage lifecycle map

## Verification per round (unchanged)

Each round's L3 test passes locally before push; CI on `main`
(now 28+ L3 + Layer 1 + Layer 2 + shellcheck + 3 dashboard contract
gates) stays green. Any new bug surfaced during L3 authoring gets
fixed in the same commit.

## Trajectory update

R201 --apply gate wired (triple-gate + interactive confirm + --force)
+ Q-014 destructive-loop.sh expanded from comment-scaffold to
snapshot-boot + serial-socket monitor + login-prompt probe.
Both items removed from open-gaps list; handoff updated.
