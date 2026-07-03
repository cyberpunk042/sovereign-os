# SDD-045 — Dashboard control-surface buildout (every dashboard a full control surface)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-07-03
> Closes findings: operator-dashboard-control-surface-directive-2026-07-03
> Supersedes the "way forward" of SDD-044 (which delivered the catalog +
> global view). SDD-044 answered *"where is everything"*; SDD-045 answers
> *"every dashboard must be a control surface — description + features +
> options + profiles — not a read-only tile."*
> Derived from: SDD-040 (cockpit bridge, per-dashboard M060 purpose),
> M060 (21 dashboards, 170 requirements), SDD-039 §1g (8-surface),
> SDD-043 (tier_intent / cpu-features / router / profile generation),
> SDD-001 (selfdef lifecycle), and the full feature inventory below.

---

## 0. The standing rule this plan answers

`<meta name="x-sovereign-standing-rule" content="We do not minimize anything.">`

The operator's directive, verbatim and un-minimized:

> "there is over 20 dashboards and a main one and **everything can be turned
> on and off** and there are also a **tons of modes and profiles**" …
> "**ALL DASHBOARDS ALMOST SHOULD HAVE FEATURES OPTIONS AND PROFILES**" …
> "a **real description** on top of this label" … "1000+ features, 20+
> dashboards, features AVAILABLE, and PROFILES — WHERE IS EVERYTHING?"

This plan makes that literally true across the whole surface. Every
dashboard gains four things it does not uniformly have today:

1. a **real description** (a paragraph from its M060 purpose, not a label),
   shown in **three places** — the master-dashboard list, the `/panels`
   global view, and inside the panel itself;
2. a **Features rail** — the capabilities that dashboard governs, each
   *turnable on/off* or actionable (not a read-only stat);
3. an **Options rail** — the filters/thresholds/settings it exposes;
4. a **Profiles/Modes selector** — the profiles and modes that apply to it.

Nothing here is optional or "phase-2 maybe." The count below is the
contract: **43 dashboards** (38 shipped + 5 net-new), **~1180 features**
across **~85 CLI verb families** and **709 crates**, **68 catalog models**,
and **the full profile/mode/toggle system** — all reachable and
controllable from a dashboard, never CLI-only-and-invisible.

---

## 1. Mission

Turn the dashboard surface from *observation* into *control*. After this
plan, an operator can, from the cockpit alone and without touching a
terminal:

- **See** every surface with a real explanation (list + global view + panel).
- **Toggle** any feature on/off (`dashboards enable/disable`, `selfdef
  on/off`, `perimeter reload`, `inference start/stop`, workload knobs …).
- **Set options** (cost thresholds, trace filters, trust-dimension filters,
  GPU watt caps, CPU governor, auth tier per surface …).
- **Switch profiles & modes** (OS profile, runtime profile §18, CPU mode,
  GPU mode, flex-profile deltas) from a picker that appears on every panel
  the mode affects.

Everything is honest: an action that needs root shows the exact
MS003-signed operator command (the web surface never mutates privileged
state directly — the hardening lint and §1g forbid it); a `snapshot` panel
says so; a `planned` surface shows its CLI today.

---

## 2. The Universal Dashboard Contract (UDC)

Every `webapp/<slug>/index.html` must, after this plan, expose the same
five-region skeleton. This is the anti-minimization lock: a panel that is
missing a region fails lint.

```
┌─ HEADER ───────────────────────────────────────────────────────────┐
│  <h1> label        [live|snapshot|planned]     [profile: sain-01 ▾] │
│  <p class="desc">  ← the REAL M060 description, co-located in meta   │
├─ FEATURES rail ────────────────────────────────────────────────────┤
│  each capability this dashboard governs, as a toggle/action:        │
│  ▸ [on|off] selfdef IPS     ▸ [start|stop] pulse tier    ▸ [apply]  │
│  every control copies-to-clipboard the exact `sovereign-osctl …`    │
│  verb (web never mutates privileged state — §1g / hardening lint)   │
├─ OPTIONS rail ─────────────────────────────────────────────────────┤
│  filters · thresholds · settings this dashboard exposes:            │
│  [budget $/day ___] [span filter: task=…] [trust dims: 7 ☑] …       │
├─ PROFILES / MODES selector ────────────────────────────────────────┤
│  the profiles & modes that apply here, switchable:                  │
│  OS profile ▾ · runtime mode ▾ · cpu-mode ▾ · gpu-mode ▾ · flex ▾   │
├─ LIVE DATA ────────────────────────────────────────────────────────┤
│  the panel's existing content (stats, tables, charts) from /api/*   │
└────────────────────────────────────────────────────────────────────┘
```

### 2.1 The four data sources behind the UDC

| Region | Single source of truth | Rendered by |
|--------|------------------------|-------------|
| Description | `<meta name="x-sovereign-description">` in the panel + mirrored to `config/dashboard-catalog.yaml` | panel self, `/panels`, master-dashboard list |
| Features | `features:` list per catalog entry → each `{label, verb, kind: toggle\|action\|start-stop, needs_root}` | Features rail |
| Options | `options:` list per catalog entry → each `{label, api_path, kind: threshold\|filter\|enum, default}` | Options rail |
| Profiles/Modes | the shared **control-systems registry** (§4) — which mode families apply to this slug | Profiles/Modes selector |

Descriptions are single-sourced in the panel `<meta>` and *aggregated* into
the catalog by a build step, so they can never drift (closes SDD-044 Q-4:
**both, panel is source, catalog aggregates**).

### 2.2 The shared front-end component

One reusable, framework-free include —
`webapp/_shared/control-surface.js` + `control-surface.css` — renders the
five regions from a small JSON blob each panel embeds
(`<script type="application/json" id="udc">…</script>`). It obeys the
shipped design grammar (`webapp/_shared/design-grammar.md`): monochrome
palette, `--mono`, `.panel .row .stat .pill .ok/.bad/.warn`, no framework,
no CDN. This is the single biggest reuse lever — build it once, every panel
gets the rails.

---

## 3. Descriptions in three places (the "WHERE IS THE DESCRIPTION" fix)

The operator looks at `/master-dashboard/` and saw a flat label list. Fixed
end-to-end:

1. **Panel `<meta>`** — `x-sovereign-description` added to every
   `webapp/<slug>/index.html`, text taken from the M060 purpose (§6 table),
   NOT invented.
2. **`/panels` global view** — already renders the catalog; the catalog's
   `description` is now *aggregated from the panel meta* (not a hand-written
   blurb), so it's the real text.
3. **master-dashboard list** — `scripts/operator/master-dashboard.py`
   `DASHBOARD_ROUTES` gains a `description` field per route, and
   `webapp/master-dashboard/index.html` renders it under each label. The
   hardcoded flat JS array is replaced by a fetch of
   `/master-dashboard/catalog.json`.

Lint (`test_dashboard_catalog_complete.py`, extended) asserts the three
copies are byte-identical to the panel meta — one edit, three surfaces,
never drift.

---

## 4. The reusable control-systems registry (the "modes and profiles")

The investigation found **eleven** distinct on/off + profile + mode systems
already built as CLI/state. They become the shared Profiles/Modes + Features
controls, mapped to the dashboards they affect. This registry lives at
`config/control-systems.yaml` and drives both the selector and the
Features rail.

| # | System | State | CLI verb | On which dashboards |
|---|--------|-------|----------|---------------------|
| 1 | **OS profiles** (5: sain-01/developer/minimal/headless/old-workstation) | `/etc/sovereign-os/active-profile` | `profiles {list,show,switch,active,compare,fork,validate}` | D-02, Build-Configurator, Personalization, **global header** |
| 2 | **Runtime profiles / modes** (§18: ultra-sovereign-efficiency / high-concurrency-burst / deep-context-synthesis) | `/run/sovereign-os/active-runtime-mode` | `trinity profile {list,show,active,switch}` | Trinity, Runtime-Modes, D-01, D-03, Router, Orchestration(new) |
| 3 | **Flex-profiles** (per-alloc deltas: gpu.util, kv_cache_dtype, tensor_parallel) | `/var/lib/sovereign-os/flex-profile.json` | `profiles flex {show,set,reset,history,export,import}` | Runtime-Modes, D-02, D-03, Trinity |
| 4 | **CPU modes** (ultra-low-power/balanced/sustained-burst/peak-inference) | `scaling_governor` (kernel) | `cpu-mode {show,list,set,auto}` | Runtime-Modes, D-09, CPU/AVX(new) |
| 5 | **GPU modes** (conservative/balanced/sustained/peak) | `/etc/sovereign-os/gpu-policy.toml` | `gpu-mode {show,list,set,auto}` | Runtime-Modes, D-09 |
| 6 | **Dashboard toggles** (every dashboard on/off) | `/etc/sovereign-os/dashboards.toml` | `dashboards {list,status,enable,disable}` | Master-Dashboard, **every panel header** |
| 7 | **Auth tiers** (6-tier ladder per surface) | `/etc/sovereign-os/auth-tier.toml` | `auth-tier {list-tiers,registry,show,matrix,set}` | Auth-Tier, **every panel header (badge)** |
| 8 | **selfdef IPS** (on/off + lifecycle) | systemd units + `/run` marker | `selfdef {status,on,off,start,stop,restart,sync,doctor}` | selfdef(new), D-13..D-18, Auditor |
| 9 | **Perimeter** (Tetragon on/off + reload) | `tetragon.service` + policies | `perimeter {status,verify,reload,check-overlap}` | Auditor, D-16, selfdef(new) |
| 10 | **Inference tiers** (per-tier start/stop) | 4 systemd units | `inference {status,health,start,stop,restart,route}` | Trinity, Router, D-03 |
| 11 | **Workload knobs** (MPS/hugepages/THP/IRQ/cpu-isolation/persistence) | kernel + systemd fragments | `workload-knobs`, `nvidia-mps`, `hugepages`, `thp-mode`, `irq-affinity`, `cpu-isolation`, `nvidia-persistence` | Runtime-Modes, D-09 |

Two of these are **global** (appear on *every* panel header): the OS-profile
picker (#1) and the per-surface auth-tier badge + dashboard on/off toggle
(#6, #7). The rest attach to the dashboards listed.

---

## 5. The 5 net-new dashboards (the invisible feature domains)

The domains the operator called out as missing — Models, AVX-choice,
orchestration, profiles — get real panels, each a full UDC control surface.

| New slug | Description | Features | Options | Profiles/Modes | Backing |
|----------|-------------|----------|---------|----------------|---------|
| **models-catalog** | Browse/select the 68-model catalog across Pulse/Logic/Oracle tiers + quant + purpose; VRAM-aware selection; eval + fine-tune status. | pull/verify/remove model · run eval · start fine-tune · set as tier default | filter class/quant/tier/vram/purpose · sort by size/latency | runtime-mode (which tier), flex (kv dtype) | new `models-api` over `models/catalog.yaml` + `scripts/models/*` |
| **cpu-avx-choice** | Which AVX-512/VNNI/BF16/AMX instructions this CPU exposes → 9 AI-workload fit verdicts → the KCFLAGS + crate feature-flags the build uses. | rebuild-with-features (copy cmd) · cpu-mode set · run avx512 probe | workload filter · tier filter | cpu-mode, runtime-mode | `cpu-features.py` + `avx512-advisor.py` |
| **orchestration** | Live routing decisions (7-axis) + the thinking_policy escalation editor (CoT→validator→self-consistency→MoE) per runtime profile. | edit thinking_policy · test-route a prompt · toggle escalation stages | task-type · think depth · validator tiers | runtime-mode (edits its policy block) | `router {plan,classify,rules,metrics}` + thinking-plan |
| **profile-generation** | Wizard: hardware × strategy → resolved runtime profile (tier allocations + tier_intent + VRAM budget) preview before apply. | generate · preview · apply/export · fork | strategy (efficiency/burst/deep) · vram budget | OS profile, runtime-mode | `profiles generate-runtime` + `select-by-intent.py` |
| **selfdef-management** | Unify D-13..D-18 mirrors under one IPS control: on/off, sync, doctor, perimeter reload, unit health. | selfdef on/off/sync/doctor · perimeter reload · install-units | mirror freshness window | (none — global on/off) | `selfdef {…}` + `perimeter {…}` |

Closes SDD-044 Q-2: **one shared `panel-api` pattern reused** (each new
dashboard gets a thin `*-api` matching the existing 37, not a monolith).
Closes Q-3: the thinking_policy + profile-generation editors **emit an
overlay the operator applies** (never silently mutate the active profile) —
consistent with the "web never mutates privileged state" rule.

---

## 6. Per-dashboard buildout — all 38 shipped dashboards

For each: the **real description** (M060 purpose, source for the `<meta>`),
the **Features** (on/off + actions), the **Options**, and the
**Profiles/Modes** that attach. This is the exhaustive worklist — one row
is one panel's UDC spec.

### 6a. Trinity & runtime (the inference core)

| Dashboard | Description (→ meta) | Features (on/off · action) | Options | Profiles/Modes |
|-----------|---------------------|----------------------------|---------|----------------|
| **trinity** | The 3-tier runtime hub — Pulse (AVX-512 bitnet.cpp, CPU), Logic/Weaver (vLLM, GPU0), Oracle/Auditor (Blackwell gatekeeper). Live tier health + endpoints + backend. | start/stop/restart per tier · route-test · zmm-ternary probe | tier filter · endpoint override | runtime-mode, flex, inference tiers |
| **router** | OpenAI-compatible front-end + 7-axis request routing (SDD-011) + thinking orchestration (SDD-043). | reload rules · test classify · toggle thinking | task-type · think depth · rule filters | runtime-mode (thinking_policy) |
| **weaver** | State-fabric surface — IDENTITY/SOUL/AGENTS/CLAUDE atomic state files; read/write/watch. | read/write state file · watch | state-file filter | OS profile |
| **auditor** | Tetragon + Guardian violation tail — perimeter posture, last violation, history. | perimeter reload/verify · selfdef on/off | violation-type filter · window | selfdef, perimeter |
| **runtime-modes** | The workload-mode cockpit: runtime profile §18 + CPU/GPU modes + workload knobs (MPS/hugepages/THP/IRQ/isolation). | switch runtime mode · cpu-mode/gpu-mode set · workload-knobs set · hugepages/THP/IRQ/MPS apply | auto-recommend toggle · aggressive | runtime-mode, cpu-mode, gpu-mode, flex, workload-knobs |
| **D-01 active-sessions** | Per-task M057 lifecycle (12-step) + profile + ETA; hibernate/resume/kill. | hibernate · resume · kill · inspect (per session) | status filter · profile filter | runtime-mode |
| **D-03 model-health** | Per-tier inference health — Blackwell/4090/CPU + VRAM + KV cache + p50/p95/p99 + heatmap. | restart tier · switch tier model | latency percentile · tier filter | runtime-mode, flex (kv dtype) |

### 6b. Models, cost, memory, eval (the AI operations)

| Dashboard | Description (→ meta) | Features | Options | Profiles/Modes |
|-----------|---------------------|----------|---------|----------------|
| **D-02 profile-choices** | Six-profile selector + L0..L6 envelope + Ring 0..4 highlights + history + predeclared-gate editor. | switch profile · fork · edit predeclared gate · apply hooks | ring filter · history window | OS profile, flex, hooks |
| **D-04 costs** | Daily budget + per-request + project/profile/model breakdown + forecast + alert thresholds. | set alert threshold · set daily budget | breakdown by project/profile/model · forecast window | OS profile |
| **D-05 traces** | Distributed span search — 13-field tree, OCSF classes, replay bookmarks. | replay span · bookmark · export bundle | 13-field span filter · time window | (none) |
| **D-07 memory-changes** | 8-type agent-memory graph diff — trust-scored mutations. | approve/revert mutation | 7-dimension trust filter · type filter | (none) |
| **D-10 eval-history** | MMLU/HumanEval/GSM8K/ARC results — white/black-box, per-model. | run eval · compare runs | suite filter · model filter | runtime-mode |
| **D-11 adapter-status** | LoRA adapter inventory + rollback state. | apply adapter · rollback · start fine-tune | base-model filter | runtime-mode |
| **D-19 super-model-manifest** | Live super-model version + M001..M080 module table (M053 11-phase). | (informational) | family/status filter | (none) |
| **D-20 peace-machine-health** | M059 5-property "is the system at peace" signal. | acknowledge · drill into property | property filter | (none) |

### 6c. Hardware & power

| Dashboard | Description (→ meta) | Features | Options | Profiles/Modes |
|-----------|---------------------|----------|---------|----------------|
| **D-09 hardware-pressure** | PSI + per-CCD load + GPU util + power (PSU/UPS) + thermal + ZFS health + DIMM/PCIe/RAM verdicts. | cpu-mode/gpu-mode set · gpu-remediate · power-shutdown plan · nvidia-mps/persistence | sensor filter · threshold set | cpu-mode, gpu-mode, workload-knobs |
| **D-08 rollback-points** | ZFS snapshots + dataset layout + dry-run preview + apply. | snapshot · dry-run · apply rollback | dataset filter | OS profile |

### 6d. Security & selfdef mirrors (D-13..D-18)

| Dashboard | Description (→ meta) | Features | Options | Profiles/Modes |
|-----------|---------------------|----------|---------|----------------|
| **D-06 pending-approvals** | Approval queue + stage gates. | approve · deny · defer · batch-approve | stage filter · age filter | (none) |
| **D-13 filesystem-grants** | selfdef filesystem-grant mirror (read-only). | selfdef sync | grant-scope filter | selfdef |
| **D-14 capability-tokens** | selfdef capability-token mirror. | selfdef sync | token-type filter | selfdef |
| **D-15 sandboxes** | selfdef sandbox + isolation-state mirror. | selfdef sync | isolation filter | selfdef |
| **D-16 audit** | selfdef append-only audit-chain mirror. | perimeter reload · selfdef sync | event-class filter · window | selfdef, perimeter |
| **D-17 quarantine** | selfdef quarantine mirror. | selfdef sync | reason filter | selfdef |
| **D-18 trust-scores** | selfdef trust-score mirror. | selfdef sync | dimension filter | selfdef |
| **edge-firewall** | nftables/fail2ban/crowdsec/suricata posture + install plan. | install · recommend · wizard | component filter | (none) |
| **network-edge** | Edge topology — OPNsense, NAT layers, VPN, per-interface. | detect · nat-chain inspect | interface filter | (none) |
| **auth-tier** | 6-tier auth ladder registry per surface (no-auth → network-level). | set tier (triple-gated) | current/recommended matrix filter | auth-tier |

### 6e. Governance, meta & build

| Dashboard | Description (→ meta) | Features | Options | Profiles/Modes |
|-----------|---------------------|----------|---------|----------------|
| **compliance** | §1g/§1h compliance aggregator — 4 instruments, per-module worst-of. | snapshot · watch | module filter · window | (none) |
| **surface-map** | 8-surface taxonomy coverage (core/CLI/TUI/API/MCP/Dashboard/WebApp/Service). | scan · waivers | surface filter | (none) |
| **doc-coverage** | 6-surface documentation coverage per module. | scan · gaps | kind filter | (none) |
| **ux-design-audit** | 6-dimension UX consistency audit + score + report. | audit · score · report | dimension filter | (none) |
| **anti-minimization-audit** | 8-pattern scope-minimization scan + waivers. | scan · cross-module · waivers | pattern filter | (none) |
| **build-configurator** | Image compose + build execution (bake dev-tools / selfdef / node major) + Run console. | run build · set bake flags · operator-deps apply · install image | profile · bake toggles · node major | OS profile |
| **global-history** | Unified 6-source change log (apt/dpkg/shell/osctl/events/modules). | tail · delta · summary | source filter · window | (none) |
| **personalization** | Whitelabel + operator identity + per-operator preferences. | whitelabel apply · diff | surface filter | OS profile, whitelabel |
| **master-dashboard** | The front door — index cards for all 42 dashboards + global health + active-session count + quick-action bar + Cmd-K palette + dashboard on/off + collision/health probes. | enable/disable any dashboard · navigate · run quick-action · health probe | search/filter · category filter | OS profile (global), all toggles |

---

## 7. The completeness proof (nothing CLI-only-and-invisible)

The inventory categorizes **~1180 features** and assigns each a home:

| Category | Features | CLI families | Crate families | Home dashboards |
|----------|---------:|--------------|----------------|-----------------|
| Trinity & orchestration | ~200 | trinity, inference, router, metrics, alerts | trinity, weaver, auditor, agent, routing, moe, orchestration, workload | Trinity, Router, Runtime-Modes, Orchestration(new) |
| Models & compute | ~280 | models, profiles, router-plan | quant, attention, tokenizer, embedding, eval, lora | Models-Catalog(new), Profile-Generation(new), CPU/AVX(new), D-03/10/11 |
| Hardware & operations | ~180 | gpu-*, cpu-mode, thermals, power-*, memory-*, fs, raid, bios-info, pcie-policy | gpu, power-thermal, workload, memory, storage, cpu-dispatch, avx-512 | D-09, Runtime-Modes |
| Security & selfdef | ~160 | perimeter, selfdef, audit, edge-firewall, network-edge, auth-tier, compliance | security-crypto, audit, trust, capability, sandbox, perimeter, firewall | Auditor, D-13..D-18, Edge-Firewall, Network-Edge, Auth-Tier, Compliance, selfdef(new) |
| Governance & meta | ~180 | master-dashboard, surface-map, doc-coverage, ux-design-audit, anti-min, severity, service-deps | compliance-audit, policy, documentation, ux-accessibility, observability, alerts | Master-Dashboard, Surface-Map, Doc-Coverage, UX-Audit, Anti-Min |
| Dashboard UI widgets | ~418 | (n/a) | cockpit-* (reusable component library) | all panels (front-end) |
| Observability & monitoring | ~50 | metrics, journal, global-history, severity, next-steps, diagnose | observability, metrics, alerts, monitoring, telemetry, logging | Global-History, Master-Dashboard |
| Network & storage | ~80 | network, net-perf, dns-advisor, services-advisor, fs, raid, reverse-proxy | network, firewall, dns, vpn-mesh, proxy, zfs | D-12, Network-Edge |
| Build & config | ~50 | install, init, wizard, decommission, operator-deps, whitelabel | build-system, config, profile-runtime, versioning | Build-Configurator, D-02, Personalization |
| **Total** | **~1180** | **~85 families / 285+ verbs** | **709 crates / 528 prefixes** | **43 dashboards** |

Lint gate: `test_feature_coverage.py` (new) asserts every top-level
`sovereign-osctl` verb family maps to at least one dashboard in the catalog
(or an explicit `cli-only` waiver with a rationale). This is the mechanical
proof that "1000+ features" are reachable — regressions fail CI.

---

## 8. Phased roadmap (the "1000 hours", ordered)

Each phase ends green (lint + panels render). No phase is a stub.

- **Phase A — the shared control-surface component + registry.**
  Build `webapp/_shared/control-surface.{js,css}` (the 5-region UDC
  renderer) + `config/control-systems.yaml` (§4 registry). Extend the
  catalog schema with `features:`, `options:`, `modes:` per entry. Lint:
  UDC blob validates against schema. *This unblocks every later phase.*

- **Phase B — descriptions in three places (the visible win).**
  Add `x-sovereign-description` to all 38 panel `<meta>` from the §6
  table; build the catalog-aggregation step; add `description` to
  `master-dashboard.py` routes; replace the master-dashboard hardcoded
  list with a `catalog.json` fetch that renders label + description. Lint:
  three copies byte-identical. *This is what the operator sees first.*

- **Phase C — global controls on every header.**
  Wire the OS-profile picker (#1), auth-tier badge (#7), and dashboard
  on/off toggle (#6) into the UDC header shared component → appears on all
  38 panels at once. Each copies the exact operator command.

- **Phase D — runtime & hardware control rails (highest-value features).**
  Runtime-Modes, Trinity, Router, D-03, D-09 get their full Features +
  Options + Modes rails (runtime-mode/cpu-mode/gpu-mode/flex/workload-knobs
  /inference tiers). These govern the most operator-impactful on/off state.

- **Phase E — the 5 net-new dashboards (§5).**
  models-catalog → cpu-avx-choice → orchestration → profile-generation →
  selfdef-management, each a full UDC panel with a thin `*-api`. Flip their
  catalog status `planned → live`.

- **Phase F — remaining panels' Features/Options rails.**
  Systematically fill the §6 rails for the rest (D-01/02/04/05/06/07/08/10
  /11, security mirrors, governance, build, personalization). One panel per
  work-unit; each ends with its UDC lint passing.

- **Phase G — the completeness gate + master-dashboard front door.**
  `test_feature_coverage.py` (every verb family → a dashboard); upgrade the
  master-dashboard page into the quick-action + Cmd-K front door over the
  full catalog. Close all §9 questions.

---

## 9. Open questions

| Q | Question | Status |
|---|----------|--------|
| Q-1 | Global header controls (profile/auth/toggle) as a shared web-component include, or server-rendered by each `*-api`? (leaning shared include — one build, all panels) | open |
| Q-2 | Do the Features rail's on/off controls ever call a *loopback-only, no-auth* mutate endpoint for non-privileged toggles (dashboard on/off, flex-set), or always copy-command? (§1g says copy-command for privileged; loopback dashboard-toggle may be safe to mutate) | open |
| Q-3 | Runtime-mode switch from a panel: does it invoke `trinity profile switch` (which touches systemd) via an operator-confirmation modal, or strictly copy-command like other privileged ops? | open |
| Q-4 | The `cli-only` waiver list for §7 completeness — which verb families legitimately have no dashboard home (pure internal libs, first-boot-only wizards)? Needs an explicit reviewed list. | open |

---

## 10. Cross-references

- SDD-044 (catalog + global view — the substrate this builds on)
- SDD-040 (cockpit bridge — per-dashboard M060 purpose, description source)
- M060 milestone (21 dashboards, 170 requirements)
- SDD-043 (tier_intent / cpu-features / router / profile generation — the
  5 net-new dashboards' backing)
- SDD-001 (selfdef lifecycle — selfdef-management dashboard)
- SDD-039 §1g (8-surface delivery + "web never mutates privileged state")
- `config/dashboard-catalog.yaml`, `config/control-systems.yaml` (new)
- `webapp/_shared/control-surface.{js,css}` (new), `design-grammar.md`
- `tests/lint/test_dashboard_catalog_complete.py` (extended),
  `tests/lint/test_feature_coverage.py` (new)
- `scripts/operator/master-dashboard.py`, `webapp/master-dashboard/index.html`
