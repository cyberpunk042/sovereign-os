# Review Phase 1 — Findings Ledger: the massive improvement / TODO catalog

> Status: **populated** (audit of 2026-07-12; branch state `7e9dea2`, includes the unmerged intelligence-layer arc `234a474..7e9dea2`)
> Owner: operator + audit sessions
> Last updated: 2026-07-12
> Charter: [00-charter.md](00-charter.md)
> Method: 7 parallel deep-audit passes (crate workspace · webapp · scripts · docs/backlog · core runtime · system/install/CI · recent-arc review) + repo-wide empirical sweeps. Every finding carries evidence paths. Findings are IDs `F-2026-NNN` for future SDD/backlog referencing.

## How to read this file

- **Severity**: `CRIT` (broken/lying/blocking) · `HIGH` (significant debt or missed value) · `MED` (worth a work item) · `LOW` (polish) · `OPP` (untapped potential — not broken, but value on the table).
- Findings graduate out of this ledger by becoming an SDD (`docs/sdd/NNN-*.md`), a backlog row, or a commit that cites the `F-2026-NNN` id.
- Empirical baseline (2026-07-12): **714 crates** (418 `sovereign-cockpit-*`), ~221k LOC Rust · ~50 webapp panels, ~138k LOC HTML/JS/CSS · 706 files under `scripts/` (~189k LOC Python; 9,081-line `sovereign-osctl`) · 129 SDD files (000–204) · 85 milestone files / 14,080 R-rows · 459 lint-contract tests · 53 operator API daemons · 52 systemd API units · 2 CI workflows (8 jobs).

---

## Executive summary — the 12 highest-leverage moves

1. **F-2026-001** — 413 of 418 cockpit crates (58% of the workspace) are consumed by nothing; decide their fate (wire, wasm-bridge, or archive).
2. **F-2026-030** — `context.md`, the mandated "read me first" surface, is ~6 weeks stale, self-contradictory on crate counts (29 vs 476 vs actual 714), and knows nothing of the entire July intelligence layer.
3. **F-2026-031** — SDD INDEX status hygiene collapsed: 77/127 SDDs "draft" including merged-to-main ones; only 4 "accepted" ever.
4. **F-2026-060** — the July 11–12 intelligence-layer arc (brain, CoAT, jobs, plan mode, AUQ, HF tokenizer, gatewayd memory) is unmerged, unpushed until now, undocumented in context.md/SHIPPED/mdbook/handoffs — the biggest recent arc has no cold-start signpost (no handoff 008).
5. **F-2026-034** — SDD-055 / MS003 commit-authority gating is the acknowledged open cross-cutting work for ALL mutation surfaces; every recent SDD ships `unsigned-pending-MS003`.
6. **F-2026-035** — Handoff 007's cockpit functional-execution plan (Execute button → ~175 per-panel actions → contract inversion) is blocked and stalled; it is the single largest planned UX unlock.
7. **F-2026-040** — webapp panel duplication + single-file 250–370KB HTML panels with no build system (findings section B).
8. **F-2026-002** — 35 non-cockpit orphan crates (zfs/vm/network/continuity/holderpo families) need triage: entry point or dead code.
9. **F-2026-050** — CI `cargo-workspace` job: full fmt+clippy+test+release-build of 714 crates under a 10-minute timeout; cold-cache runs will die.
10. **F-2026-032** — MASTER-PLAN vs context.md contradict each other on D-16/D-12 mirror wiring ("not yet wired" vs "shipped, wired") — two authoritative surfaces disagree.
11. **F-2026-033** — mdbook stops at SDD-067; the book publishes a repo that no longer exists (no intelligence layer, no SDD 100/200 bands).
12. **F-2026-003** — placeholder `repository`/`authors` metadata (`example.org/you`) inherited by all 714 crates; docs.rs header links that can never resolve under `publish = false`.

---

## A. Crate workspace (structure) — F-2026-001 .. 009

### F-2026-001 · CRIT · The 413-crate unconsumed cockpit family
- **Evidence**: 418 `sovereign-cockpit-*` crates; only 5 are consumed by anything, and the sole consumer chain (`sovereign-dashboard-snapshot` → `-banner-state`/`-context-panel`/`-toast-tray`/…) is itself an orphan with 0 consumers. Zero hits for `wasm-bindgen|cdylib|wasm32` across all crate manifests/sources. The webapp is hand-written HTML/JS with no Rust binding; scripts referencing "cockpit" reference the concept, not the crates.
- **Meaning**: ~58% of the workspace is a fully-parallel, serde-only UX state-model layer with no runtime binding — pure carrying cost in compile time, CI time, and cognitive surface, OR an enormous untapped asset (a typed contract for every UI behavior) waiting for a bridge.
- **Options to decide (SDD-worthy)**: (a) wasm-pack a `sovereign-cockpit-wasm` facade and progressively move panel state logic into the typed crates; (b) generate JSON-schema/TS types from the cockpit crates and validate panel state against them in `tests/lint` (cheap, immediate value, no wasm); (c) codegen panel JS state machines from the crates; (d) formally archive the family (move out of workspace `members`) until a consumer exists.
- **Related**: F-2026-050 (CI time), F-2026-040 (webapp duplication the crates were meant to prevent).

### F-2026-002 · HIGH · 35 non-cockpit orphan crates need entry-point-or-dead triage
> **Status (2026-07-13):** **CLOSED by SDD-955** (island register) — annotated by SDD-962. The per-crate disposition table this asks for shipped as `docs/review/phase-1/island-register.md`: 35 crates (now 33 — a parallel session wired `rate-limit` + `observability-events`, enforced by the register's lint), each with a `wireable`/`aspirational` disposition + a concrete trigger. The two headline crates named here (`sovereign-holderpo`, `sovereign-worker-fleet`) are registered `aspirational` with triggers.
- **Evidence**: 0 internal consumers, not binaries: `sovereign-base-os, -cgroup-systemd, -continuity-levels, -continuity-manager, -cpu-dispatch, -cpu-topology, -dashboard-layout, -dashboard-snapshot, -data-plane, -execution-env, -fs-boundary, -hardware-dispatch-eligibility, -harness-layers, -hibernation, -holderpo, -inheritance-artifacts, -intake, -mode-transition-log, -module-facets, -network-boundary, -network-zerotrust, -observability-events, -pcie-topology, -rate-limit, -replay-export-bundle, -replay-playback-rate, -sandbox-profile, -save-state, -vm-channel, -vm-workload, -whitelabel, -worker-fleet, -zfs-commit-gate, -zfs-provisioning-plan, -zfs-snapshot-policy`.
- **Action**: per-crate one-line disposition table (consumed-by-scripts / future-entry-point / wire-me / archive-me). Special note: `sovereign-holderpo` (the HölderPO post-training pillar) and `sovereign-worker-fleet` are headline features of the two-ultimate-solutions doctrine yet nothing consumes them — either wire into `sovereign-cortex`/`gatewayd` or mark explicitly aspirational.

### F-2026-003 · HIGH · Placeholder workspace metadata + unreachable docs.rs links
> **Status (2026-07-13):** **CLOSED by SDD-960** (`docs/sdd/960-workspace-metadata-and-dead-doc-links.md`). Root `Cargo.toml` metadata is now real (`repository = github.com/cyberpunk042/sovereign-os`, `authors = ["cyberpunk042"]` — the already-public identity, inherited by all 714 crates); the 23 dead `docs.rs/sovereign-*` header links are repointed to the GitHub source; `tests/lint/test_workspace_metadata.py` blocks placeholder metadata + dead docs.rs links from returning. Building local rustdoc as a panel (the alternative) stays a follow-up (F-2026-093).
- **Evidence**: root `Cargo.toml`: `repository = "https://example.org/you/sovereign-os"`, `authors = ["You <you@example.org>"]`, inherited by all 714 crates. Crate lib.rs headers link `https://docs.rs/sovereign-*` which cannot resolve (`publish = false` workspace-wide).
- **Action**: set the real repo URL/author; either drop docs.rs header links or build+publish local rustdoc (see F-2026-093 rustdoc-as-panel opportunity).

### F-2026-004 · LOW · Workspace hygiene is otherwise exemplary (baseline to protect)
- 0 crates missing descriptions; all inherit workspace lints (`unsafe_code = "forbid"`, `missing_docs = "warn"`); 713/714 crates carry tests (sole exception `sovereign-feature-selftest`, by design); **zero** real `TODO/FIXME/unimplemented!/todo!()` in code; zero hardcoded `/home|/Users|/root` paths in sources; core crates compile clean.
- **Action**: add a lint-contract test asserting these invariants so the bar never silently drops (marker-free code, per-crate tests, no absolute paths).

### F-2026-005 · MED · The 9 binaries are the real runtime surface — document them as such
> **Status (2026-07-13):** **CLOSED by SDD-962** (`docs/src/binaries.md`). All 9 binary crates mapped to role → invocation → purpose (production daemon `gatewayd`; periodic `telemetry`; helpers `resource-control` / `feature-selftest`; dev/demo `cortex` / `agent-runtime` / `inference-demo` / `chat` / `serve`) + a compose diagram, wired into the mdbook; `tests/lint/test_binaries_doc.py` enforces every binary crate stays documented.
- `sovereign-agent-runtime, -chat, -cortex, -feature-selftest, -gatewayd, -inference-demo, -resource-control, -serve, -telemetry`. No single doc lists "these are the executables, this is what each is for, this is how they compose." Action: a `docs/architecture/binaries.md` (or mdbook page) mapping binary → systemd unit → panel → script callers.

### F-2026-006 · MED · `sovereign-inference-demo` runs on untrained pseudo-weights
- **Evidence**: crate explicitly notes weights are deterministic pseudo-values — "demonstrates that the engine runs and composes, not that it produces trained output" (2,605-line bin).
- **Action/OPP**: now that `sovereign-hf-tokenizer` + `sovereign-safetensors-loader` exist, upgrade the demo to load a real small model end-to-end (see F-2026-070 runtime section) — the single most convincing proof-of-life the repo could add.

### F-2026-007 · OPP · `sovereign-trinity` is a typed-mirror only by design — make the boundary self-verifying
- Auditor implementation lives in selfdef; the crate carries the mirror surface. Action: cross-repo contract test (like `test_m060_cross_repo_chain_contract.py`) that pins the trinity mirror schema against selfdef's producer, so drift is caught at CI instead of at runtime.

### F-2026-008 · LOW · Version freeze at 0.1.0 vs pre-1.0 promises
- Workspace `version = "0.1.0"` while `context.md:134` defers "MS007 crate version + schema_version bumps (Patch Pass B+C) to pre-1.0 lockdown". Action: keep, but record the trigger condition in one place (currently only in stale context.md).

### F-2026-009 · OPP · Dependency-graph guard
- The orphan analysis in this audit was ad-hoc. Action: commit a `tests/lint/test_crate_graph_contract.py` that (a) regenerates the internal dependency graph from `cargo metadata`, (b) asserts the known-consumed set, (c) fails when a NEW orphan appears — turning the 413-orphan discovery from an archaeology event into a CI signal.

---

## C. Scripts + operator surface — F-2026-020 .. 029

### F-2026-020 · LOW · Health baseline (protect it)
- 397 scripts (103 sh / 294 py): **0** `bash -n` failures, **0** `py_compile` failures. `sovereign-osctl` (9,081 lines, 30 `cmd_*` verbs): every dispatch target exists. 53 operator API daemons with a collision-free sequential port map (8090–8135, 8140, 8142, 8160, 7711–7713, 8787) guarded by `tests/lint/test_dashboard_port_and_reference_integrity.py`. systemd↔API pairing is 1:1 (52 units; `build-configurator-api` intentionally unit-less via `make panel`).

### F-2026-021 · MED · Orphaned hook: `scripts/hooks/post-install/vfio-bind-3090.sh`
- Referenced by nothing; its sibling `vfio-bind-4090.sh` is wired into `sovereign-vfio-bind.service`, `config/bootstrap/phases.yaml`, and 8 docs. Action: either wire the 3090 variant in as a hardware-profile alternative (probably the intent) or delete it.

### F-2026-022 · MED · Local test/lint entrypoints assume pytest that setup never installs
- `Makefile` `lint`/`unit`/`test`/`ci`/`dashboards-lint` all run `python3 -m pytest`; pytest is only installed inside CI (`pip install pytest pyyaml jsonschema` in test.yml). No root `requirements.txt`, no dev-env bootstrap target. Action: `make dev-deps` (or extend `setup.sh`) installing `pytest pyyaml jsonschema`, plus a friendly "pytest missing — run make dev-deps" guard in the Makefile.

### F-2026-023 · LOW · Glob-dispatch depends on the executable bit
- `scripts/build/orchestrate.sh:352` dispatches hooks via `find … -executable`; a hook that loses `+x` is silently skipped (0 currently non-executable). Action: lint test asserting every `scripts/hooks/**/*.sh` is executable.

### F-2026-024 · LOW · A few scripts lack `set -euo pipefail` without sourcing `common.sh`
- e.g. `scripts/webapp/preflight.sh`. Action: targeted sweep of the handful that neither set it nor source `scripts/build/lib/common.sh` (which sets it at line 44).

### F-2026-025 · MED · The 9,081-line `sovereign-osctl` monolith
- Single bash file, 376KB, 30 verbs. It works, but it is the largest untestable unit in the repo (bash, no unit tests of its dispatch/parsing). Options: (a) split verbs into `scripts/osctl.d/<verb>.sh` sourced modules with a thin dispatcher; (b) golden-output tests for `--help`/`status --json` shapes; (c) longer-term: promote to a Rust binary (the workspace already has the discipline) — candidate `sovereign-osctl` crate.

### F-2026-026 · OPP · `__pycache__` dirs in the working tree (untracked, but noise)
- Present across `scripts/*/`; correctly gitignored. Action: add a `make clean-pyc` or pre-commit hook step; cosmetic.

### F-2026-027 · OPP · Exotic one-script domains are hidden capabilities
- `scripts/science/warp-runner.py`, `scripts/research/loop.py`, `scripts/insights/synthesize.py`, `scripts/history/aggregate.py`, `scripts/weaver/atomic-state.py`, `scripts/pulse/{build-bitnet.sh,wasm-aot.sh}` — each is a lone entry point with no panel/doc/osctl verb exposing it (SDD band 300–399 "science-tools" is reserved and entirely unused). Action: either surface them (osctl verbs + docs + panel cards) or fold them into their parent domains; the science-tools SDD band is the natural home.

---

## D. Docs, backlog, planning surfaces — F-2026-030 .. 039

> **Status (2026-07-12):** **CLOSED by SDD-952** (`docs/sdd/952-context-md-counts-contract.md`). `context.md` gained a machine-verified `COUNTS-CONTRACT` block (crates/dashboards/panels/SDDs/milestones) + a current-state section, and `tests/lint/test_context_md_counts.py` fails CI on drift — so the counts can't silently rot again. The sibling doc-drift on MASTER-PLAN (F-2026-032) and mdbook SUMMARY (F-2026-033) is the same pattern applied elsewhere, still open.

### F-2026-030 · CRIT · context.md violates its own no-drift mandate
- **Evidence**: header rule "*If anything below is stale, fix it before continuing — never silently let it drift*"; `Last updated: 2026-05-19`, current arc dated 2026-05-28; HEAD is 2026-07-12. Zero mentions of: CoAT, intelligence layer, jobs runtime, plan mode, AUQ/QCFA, tokenizer, gatewayd, Code Console, Sovereign Brain observatory. Crate count stated as **29** (line 290) and **476** (later) vs actual **714**. Dashboard inventory stops at D-20 (reality: D-21..D-25 + brain + code-console). "29 SDDs (000-039)" vs actual 127 files reaching SDD-204. A 2026-05-27 "STALE-QUEUE CORRECTION" already flagged the drift pattern — never repaired.
- **Action**: full context.md refresh (new "2026-07 intelligence-layer arc" section, corrected counts, corrected dashboard list, corrected SDD range, new Last-updated), PLUS a structural fix: a lint test that greps context.md's stated crate/dashboard/SDD counts against reality so drift fails CI (counts-as-contract).

### F-2026-031 · HIGH · SDD status hygiene collapsed
> **Status (2026-07-13):** **objective core CLOSED by SDD-961** (`docs/sdd/961-sdd-index-status-hygiene.md`). The 71 stale `on branch claude/recover-projects-b0oT6` provenance refs are dropped (→ `(recover-projects session)`), a Status vocabulary legend is added to the INDEX header, and `tests/lint/test_sdd_index_hygiene.py` blocks feature-branch refs + undocumented status words. **Still open (deliberately, per-SDD judgement)**: the subjective status-value reconciliation (flip merged `draft` SDDs → `accepted`/`complete`) is left to each authoring session against the legend — a committed SDD can legitimately still be draft-stage, and the rows are owned by several sessions, so a unilateral mass-relabel would misrepresent their work. Per-row status-block dates are also a follow-up.
- 127 SDD files (bands: 000–071 used, 100–149 used, 200–204 used; 072–099/150–199/300–999 reserved). INDEX tally: **4 accepted · 77 draft · 41 review · 1 scoping**. SDD-142..149 are merged to main (PRs #117/#118) yet still `draft` + "on branch claude/recover-projects-b0oT6" in INDEX. Action: reconcile INDEX statuses (merged ⇒ implemented/accepted), drop stale branch refs, and add the status-block dates to the INDEX so staleness is visible; optionally a lint test that any SDD cited by a merged commit cannot remain `draft`.

### F-2026-032 · HIGH · Authoritative surfaces contradict each other
> **Status (2026-07-12):** **CLOSED by SDD-959** (`docs/sdd/959-master-plan-count-reconciliation.md`). MASTER-PLAN's milestone count is now single-valued at 132 (was self-contradictory 128/130); the sovereign-os cell is 84 (matching the file tree — M085/M086 were missing, now enumerated); the D-16/D-12 rows are `at prod` (cited to the on-disk dashboards + context.md M060 arc). `tests/lint/test_master_plan_counts.py` enforces enumeration completeness + count self-consistency, so it can't silently drift again. Scope limit: the cross-repo selfdef count (48) is checked only for internal consistency, not against the selfdef tree (not in this checkout).
- `docs/MASTER-PLAN.md:41-42` says D-16 audit-chain + D-12 rules mirrors "catalog ✓ (not yet wired)" while `context.md` (M060 arc) declares them shipped/wired end-to-end and `webapp/d-16-audit/` exists. Milestone counts disagree: INDEX says 82 (85 files exist), MASTER-PLAN says both 128 and 130. Action: single-source the counts (generate MASTER-PLAN/INDEX numbers from the file tree, as INDEX already claims to be auto-generated) and reconcile the D-12/D-16 wiring rows.

### F-2026-033 · HIGH · mdbook publishes an obsolete repo
> **Status (2026-07-12):** **CLOSED by SDD-958** (`docs/sdd/958-mdbook-catalog-sync.md`). `scripts/docs/gen-sdd-catalog.py` generates `docs/src/sdd-catalog.md` (all 140 SDDs) + `docs/src/standing-directives.md` (incl the 3 July directives) from the file tree; both are wired into a new SUMMARY "Design record" section; `tests/lint/test_mdbook_catalog_sync.py` fails CI (regen-and-compare + newest-SDD guard) if the book drifts — so it can never freeze behind the design record again. Per-crate narrative chapters for the intelligence layer remain a larger follow-up; `docs/src/questions.md` (frozen Q-001..Q-019) is a smaller sibling refresh, tracked separately.
- `docs/src/SUMMARY.md` newest SDD reference is 067; zero hits for brain/coat/reasoning/jobs/plan-mode/AUQ/intelligence/console/tokenizer; `docs/src/questions.md` frozen at Q-001..Q-019 foundation-era set. Action: regenerate SUMMARY from `docs/sdd/INDEX.md` (script it — don't hand-maintain), add pages for the three July standing-directives and the intelligence-layer crates/binaries.

### F-2026-034 · CRIT · SDD-055 / MS003 commit-authority gating — the acknowledged cross-cutting hole
- Every SDD-142..204 ships `unsigned-pending-MS003`; `context.md:51` names it "the open cross-cutting work for all mutation surfaces". Action: this is the top candidate for the next real SDD-driven arc — define the signing/authority mechanism once, then sweep the mutation surfaces (osctl verbs, operator APIs, selfdefctl parity verbs).

### F-2026-035 · HIGH · Handoff 007's cockpit-execution plan is stalled and blocked on one operator word
- Blocked on Q-047-D ("recreate" decision — branch `claude/recover-projects-b0oT6` unrelated-history vs main; that branch has since been merged via PRs, verify and close the question). Pending phases: fold controls into `operator-sudoers.sh` (retire DRAFT `config/sudoers.d/sovereign-os-cockpit`); Phase 1 Execute button in `webapp/_shared/control-surface.js` (lights all 47 panels); Phase 2 ~175 per-panel action buttons; Phase 3 invert ~48 read-only contracts + `cockpit_action_total` alert rules; Q-047-B selfdef signed-proxy ratification.
- **Action**: re-validate the blocker (likely obsolete), then execute the 3 phases — this is the biggest planned operator-value unlock already specced.

### F-2026-036 · HIGH · No handoff exists for the July 11–12 intelligence arc
- Handoff INDEX tops out at 007 (2026-07-08). The largest recent arc (15 commits) has no cold-start anchor, no SHIPPED.md rows, no decisions.md entries (last is D-019, 2026-07-03), no backlog note. Only the three standing-directives (2026-07-11/12) document it — and nothing cross-links them. Action: author handoff 008 + SHIPPED rows + D-020+ decisions entries.

### F-2026-037 · MED · Deferred-work items promised in docs (consolidated register)
The docs already promise these; they need owners/ordering, not rediscovery:
1. Telemetry-sink choice + Grafana JSON dashboards (`docs/decisions.md:205,411,427`).
2. Layer 4 QEMU + Layer 5 hardware conformance suites (`docs/decisions.md:547`, SDD-020; `tests/chroot` + `tests/qemu` are scaffolds only).
3. TPM2 disk-encryption PCR binding (SDD-015/022).
4. SDD-016 Layer B Prometheus emission (contract locked, unemitted).
5. SDD-019 apt-snapshot enforcement + `SOURCE_DATE_EPOCH` in step-04 + in-toto provenance.
6. SDD-029 roadmap R257–R262 (XMP detection, wattage sampler, PSU OC toggle, KNOWN_BOARDS TOML, Z-14/Z-19 cards).
7. SDD-046 Q-046-001..004; root Q-A..Q-D (mdbook deploy cadence/provider); Q4..Q25 series across SDD-003..025.
8. Q-067-A..F app-shell questions incl. Q-067-F live-LLM assistant (network/trust tension) — now partially overtaken by the Brain/Code-Console work; reconcile.
9. selfdef-cli-mirror + selfdef-tui-mirror surface integration; SG7/SG8 stage-gates beyond catalog (MASTER-PLAN).
10. MS043 selfdef mirror-crate implementations marked "impl pending" (`context.md:203`) — verify against the M060 completion claim and close one way or the other.

### F-2026-038 · MED · Backlog granularity gap
- `backlog/epics|features|modules|requirements/` each contain only an INDEX.md — the 14,080 R-rows live embedded in 85 milestone files; SHIPPED.md self-describes as a "SAMPLED snapshot" with a literal "state TBD" section (line 962). Action: accept the R-row model but add the missing axis: a generated per-milestone shipped-percentage roll-up (script that counts SHIPPED rows vs R-rows per milestone) so "how done is M0xx" becomes queryable instead of TBD.

### F-2026-039 · LOW · Giant single-file standing directive
- `docs/standing-directives/2026-05-17-operator-mandate.md` is 564KB — unreadable/undiffable as one file. Action: split by section with an index, preserving verbatim content byte-for-byte (sacrosanct), or at minimum add a TOC + anchor map companion.

---

## F. System, install, CI — F-2026-050 .. 059

### F-2026-050 · HIGH · CI cargo-workspace job: 714 crates under `timeout-minutes: 10`
- `.github/workflows/test.yml:530-549`: fmt --check + clippy `--workspace --all-targets -D warnings` + `cargo test --workspace` + `cargo build --release --workspace`, all in one 10-minute job. `Swatinem/rust-cache` saves warm runs, but any cold-cache run (toolchain bump, lockfile change, cache eviction) will exceed 10 minutes and fail spuriously. Action: raise the timeout, split release-build into its own job, or scope release-build to the 9 binaries (`make bins` already knows the set). Related: retiring the 413 unconsumed cockpit crates (F-2026-001) would cut this job's cost by half or more.

### F-2026-051 · MED · systemd install-prefix split; `make install` installs no units
- 111 units total (91 service / 19 timer / 1 target). Two ExecStart prefixes coexist: hook/inference/hardware units use `/opt/sovereign-os/scripts/...`; the ~54 operator-API units use `/usr/local/lib/sovereign-os/scripts/operator/...`. `make install` (Makefile:104-133) populates only `lib/ hooks/ inference/ profiles/ whitelabel/` under `$(PREFIX)/lib/sovereign-os/` — never `scripts/operator/`, never `/opt/sovereign-os/`, and installs zero `.service`/`.timer` files. All referenced source scripts exist in-repo (0 missing), so this is install-wiring/doc drift, not missing code — but a `make install` operator following `systemd/system/README.md` (which documents only 4 inference units) gets a fleet whose paths don't exist.
- **Action**: pick ONE prefix doctrine, make `make install` (or an explicit `make install-units`) own the full 111-unit fleet, and extend the README beyond the 4 inference units.

### F-2026-052 · MED · The 3-tier test harness is effectively 1-tier
- `tests/nspawn/` is rich (235 files); `tests/qemu/` and `tests/chroot/` are each a single `scaffold.sh` stub, while ARCHITECTURE.md + SDD-008 advertise a three-tier harness (and decisions.md already defers Layer 4/5). Action: either build the qemu tier (boot the baked image headless, run the feature-selftest binary inside) or mark the tiers explicitly deferred in SDD-008 so docs stop over-claiming.

### F-2026-053 · MED · ARCHITECTURE.md is scaffold-era stale
- `Last updated: 2026-05-16`; still describes PR 5/6 profile stubs as future ("Features | Stage 2+") while 5 full profiles + mixins/runtime/orchestration families exist and README declares Stage-2 onset. Action: refresh alongside context.md (F-2026-030); add the intelligence layer + binary/daemon topology.

### F-2026-054 · LOW · ~41 of 111 systemd units have no name-specific test
- 70 unit names appear in tests; fleet-wide hardening lints cover the rest in aggregate. Action: extend the fleet lint to assert existence/enable-wiring per unit name generated from the `systemd/system/` listing (cheap dynamic parametrization).

### F-2026-055 · LOW · README prerequisites omit the Rust 1.89 pin
- Debian stable ships 1.85; the repo needs rustup-pinned 1.89 via `scripts/install/rust-toolchain.sh` — not mentioned in README prerequisites. Action: one paragraph.

### F-2026-056 · LOW · Local dev-deps bootstrap missing (same root cause as F-2026-022)
- CI installs `pytest pyyaml jsonschema` inline in every job; nothing installs them locally (`validate-profiles.sh` exits 2 without jsonschema). Action: `make dev-deps` + mention in README/setup.sh.

### F-2026-057 · INFO · Healthy baselines worth protecting (system surfaces)
- config/: 40+ files all consumed, example-file discipline lint-enforced (`test_config_example_files.py`), no committed secrets. profiles/schemas: all 7 schemas have conformance tests + real consumers; CI validates raw + mixin-resolved profiles. models/catalog.yaml: honest `verified-real / aspirational / operator-must-confirm` provenance labels + webapp lockstep lint. whitelabel/share/assets: all live. .gitignore comprehensive; zero tracked junk; no files >5MB. CHANGELOG actively maintained (50 entries, current to HEAD). CODEOWNERS/LICENSE/rust-toolchain valid and consistent.

---

## G. The unmerged July 11–12 intelligence-layer arc (`234a474..7e9dea2`) — F-2026-060 .. 069

> Overall verdict from the arc review: high-quality, internally consistent; reuses existing crates via traits (CoAT drives M007 `BranchTree` + cortex value-plane + Memory-OS recall); CHANGELOG + 3 standing-directives + SDD-204 updated; real behavioral tests (14 CoAT unit tests + gatewayd integration tests). Items below are the hardening/wiring tail.

### F-2026-060 · CRIT · The arc exists only on this branch and in CHANGELOG/directives — no state surface knows it
- Unmerged, was-unpushed (pushed with this audit), zero coverage in context.md / SHIPPED.md / backlog / decisions.md / handoffs / mdbook. Action: land it (PR), then handoff 008 + context.md arc section + SHIPPED rows + D-020+ decision entries (same items as F-2026-036 — this is the producing side).

### F-2026-061 · MED · Auto-mode safety classifier over-claims "auto-blocks destructive"
- `scripts/operator/lib/permission_classifier.py` is honest heuristics (regex + allowlists) but evadable: `rm -rf /x` → block ✓; `rm -r -f /x` → confirm ✗; `rm -R -f /x` → confirm ✗; shell obfuscation (vars, quoting, `$IFS`) escapes entirely. Fails toward `confirm`, never silent-allow — good — but the doctrine text ("auto-BLOCKS destructive ops") overstates it. Action: normalize flags before matching + add `rm -r -f`/`-R` regression cases, AND re-frame the doctrine as best-effort UX (the security boundary is selfdef/sudoers, not this classifier).

### F-2026-062 · MED · jobs-api generic runners vs systemd sandbox mismatch (latent)
- `_run_command` (jobs-api.py:127) runs `eval`/`model-load`/`gpu-job` commands with `cwd=REPO`, but `sovereign-jobs-api.service` sets `ProtectSystem=strict` + `ReadWritePaths=/var/lib/sovereign-os/jobs` only — those job kinds will hit read-only FS the day a real runner ships. Action: decide per-kind ReadWritePaths (or a jobs-output dataset) before the first non-demo runner.

### F-2026-063 · MED · Model-backed `/v1/coat` runs synchronously on the gateway request thread
- `gatewayd lib.rs:888` — one model call per expansion (≤12 iters) blocks the HTTP handler; the jobs runtime already provides the correct off-path escape (`_run_deliberation`). Action: timeout on the sync path + steer the brain webapp to the background-jobs path for model-backed deliberation.

### F-2026-064 · LOW · `/v1/simple-explain` (and `/v1/simple`, `/v1/deliberate`) undocumented
- Only CHANGELOG + code comments; `/v1/coat` by contrast has a standing directive. Also: `/v1/deliberate` (cortex best-of-N) vs `/v1/coat` (CoAT ladder) overlap in naming — delineate or fold best-of-N into the ladder narrative. Action: a gateway API reference page (see also H-section: the Anthropic-compliance conversation will need exactly this page).

### F-2026-065 · LOW · Daemon-path `.expect()` invariants
- `sovereign-coat/src/lib.rs:568,820` + gatewayd `.lock().expect("poisoned")` — invariant-guarded today, but reachable from `/v1/coat`; a future refactor panics the request thread, and lock poisoning would cascade to every request. Action: convert to error returns on the daemon path; keep expects in pure-lib contexts.

### F-2026-066 · LOW · Cross-daemon integration untested
- brain-api→gatewayd and jobs-api→osctl paths each have per-component tests but no end-to-end spin-up test; model-backed CoAT (non-heuristic `ModelThoughts`) is untested. Action: one nspawn/CI integration test that boots gatewayd + brain-api and round-trips `/brain/chat`.

### F-2026-067 · INFO · Verified-good properties of the arc (keep)
- All brain/code-console webapp fetches map to real server routes (brain-api.py:319-371; code-console-api.py:121,292). Jobs registry is durable (atomic temp+rename at `/var/lib/sovereign-os/jobs/registry.json`, orphan-resume on startup). Ports clean and env-overridable (brain 8141, jobs 8142, gateway 8787, loopback-forced). Units auto-installed via the existing service glob; R171-hardened. CoAT traces honestly flag `thought_source = model|heuristic`.

---

## B. Webapp cockpit — F-2026-070 .. 079

> 55 panels, each a single `index.html` (total 136k lines), served statically by build-configurator `:8100`; data via `scripts/operator/*-api.py`. All 55 are in the master-dashboard `GROUPS` catalog (7 groups). Uniform positives: app-shell + course block byte-identical across all 55 (sync-tool + drift-lint enforced), ⌘K palette + control-surface `.cs-` classes in all 55, honest-offline (SB-077) is a designed feature not an accident.

### F-2026-070 · HIGH · Four duplicate panel-fork clusters (~5 forks × ~2000 lines)
- **models-catalog vs d-23-models-catalog** (different backends: `models-catalog.json` vs `/api/models-catalog/catalog`) · **cpu-features vs d-24-cpu-features** (both back `/cpu-avx.json`) · **selfdef-management vs d-25-selfdef-management** · **network-edge vs edge-firewall vs d-12-networking** (3-way fork). Catalogued as intentionally-distinct "views" but carrying massive duplicated bodies. The `d-NN-*` variants are the ones wired into the aggregator route table + selfdef-mirror chain (canonical); the bare-slug variants are newer static-only reskins.
- **Action**: consolidate each cluster to one shared body + `?view=` param; ~10k lines reclaimable. Decide which of each pair is canonical and redirect the other.

### F-2026-071 · MED · Confirmed dead fetch: `/api/node-exporter/metrics` → no handler
- `master-dashboard/index.html:2370` fetches it; grep of all `scripts/` = no handler (master-dashboard-api.py serves only routes/health/catalog/control-systems/collisions/discover/toggles/feature-coverage/version). The panel's own comment admits node_exporter "haven't published yet." Consequence: the master-dashboard AppArmor + four-watchdog + selfdef-metrics security banners are permanently stuck offline. Action: build the node-exporter proxy (m060-health-api was meant to) or remove the banners' live pretension.

### F-2026-072 · MED · Aggregator route table (26) is stale vs 55-panel reality
- `scripts/operator/master-dashboard.py` `DASHBOARD_ROUTES` covers only d-01..d-20 + trinity/router/grafana/node_exporter; the ~29 non-`d` panels + d-21..d-25 (brain, code-console, weaver, auditor, build-configurator, emulate, flash, ups, science, orchestration, compliance, auth-tier, anti-minimization-audit, surface-map, doc-coverage, ux-design-audit, feature-test-lab, personalization, global-history, course, …) are reachable only via the `:8100` static server. Action: reconcile the reverse-proxy table with reality, or explicitly document it as static-only and delete the partial aggregator.

### F-2026-073 · HIGH · No webapp build system → ~49% of 136k lines is verbatim-duplicated
- By explicit "sovereignty-clean" doctrine there is zero runtime shared asset (0 panels link external CSS/JS); the app-shell block (711 lines) + course block (503 lines) are duplicated byte-for-byte into all 55 panels (~66,770 of 136,082 lines ≈ 49%). Two blocks are sync-tool-managed with drift lints; the other 5 `_shared/` snippets (control-surface.js/css, a11y, demo-mode, nav, responsive) have **no sync tool and no drift gate** — the real drift risk. Per-panel JS helpers (`esc()`, `fmtBytes`, `poll()`) are copy-pasted and inconsistent.
- **Action**: either (a) extend the sync-tool + drift-lint pattern to the 5 unmanaged snippets and dedupe the ad-hoc helpers into a synced `_shared/helpers.js` block, or (b) reconsider the no-build doctrine for a minimal inline-at-build bundler. Two 4500/3645-line monoliths (build-configurator, master-dashboard) especially need componentization.

### F-2026-074 · MED · skip-link a11y missing in 20/55 panels
- Present in 35/55; absent in the newer batch: `brain, build-configurator, code-console, course, cpu-features, d-21..d-25, emulate, feature-test-lab, flash, models-catalog, orchestration, profile-generation, runtime-modes, science, selfdef-management, ups`. The a11y snippet was inlined into the original batch and never back-ported. Action: back-port skip-link (and fold the a11y snippet into the synced app-shell block so it can never drift again).

### F-2026-075 · LOW · Port-collision guards are load-bearing tribal knowledge
- `scripts/operator/panel.sh:150-200` documents two real past incidents (build-configurator-api unit-less `|| true` trap fix; ux-design-audit-api PORT=8100 collision). The guards work but encode incident history in comments. Action: promote the port map to a single generated source (config) consumed by both the guard and the port-integrity lint (F-2026-020 already has the lint — unify the source).

## E. Core runtime + intelligence (the deep spine) — F-2026-080 .. 099

> The through-line: **a large library of well-built, well-tested crates, only a thin spine of which is wired into the running daemon.** `sovereign-gatewayd` is the real daemon; `sovereign-cortex` (routing/value/memory, 58 tests) and the safetensors→quant-model→hf-tokenizer generation path are what actually run. Much of the safety, batching, agent, and orchestration machinery is built, tested, and one wiring commit from real.

> **Arc-1 status (2026-07-12):** **CLOSED by SDD-950** (`docs/sdd/950-real-rope-theta-scaling.md`). `rope_theta` + `rope_scaling` are now parsed from `config.json` and threaded into every block via `MhaDecoderBlock::with_rope` — Llama-3/Qwen2/Mistral decode at their trained base. The remaining Arc-1 work (F-2026-085 quantized loading, F-2026-086 sampling params + chat template) is unchanged.

### F-2026-080 · CRIT · `rope_theta` hardcoded to 10000 → modern models decode garbage
- **Verified**: `sovereign-mha-block/src/lib.rs:254` `rope: Rope::new(hd)` (base 10000); `sovereign-safetensors-loader` `Config` never parses `rope_theta` and its own doc-comment (`lib.rs:23`) lists it as an unfixed "Out" item. Llama-3 (500000), Qwen2 (1000000), Mistral all need non-default theta and will produce incoherent output. `sovereign-rope` **already has** `with_base` and `ntk_aware_base` (`rope/src/lib.rs:91,114`) — it is purely unplumbed. This is the single biggest blocker to "point it at a real model."
- **Action**: parse `rope_theta`/`rope_scaling` from config → thread through loader → `Rope::with_base`. Small, high-impact; unblocks the whole "real local model" premise and directly complements the parallel Anthropic-compat work (a compat API is worthless if generation is garbage).

> **Arc-2 status (2026-07-12):** F-2026-081 + F-2026-082 are being closed by **SDD-206** (`docs/sdd/206-gateway-safety-spine.md`) — the safety spine (injection screen + secret/PII redaction + toxicity flag) is now wired into `generate_chat`, and the transport gained bearer auth + per-connection timeouts + honest over-cap back-pressure. TLS (part of F-2026-082) remains deferred as an SDD-206 non-goal (Q-206-003).

### F-2026-081 · HIGH · Security crates exist but NONE are wired into the daemon
- **Verified**: `sovereign-gatewayd/Cargo.toml` depends on none of pii-redact/secret-scan/injection-detect/toxicity; those are wired into `sovereign-serve` (the parallel, non-daemon orchestrator) and `sovereign-llm`, not the running path. `sovereign-sandbox-profile`, `-network-zerotrust`, `-fs-boundary` have **0 consumers anywhere**. So in the running system, prompts and generated text pass through `gatewayd::generate_chat` (`lib.rs:666`) unfiltered; the gateway's own declared Privacy+Redaction responsibilities are unimplemented in the daemon path.
- **Action** (highest-leverage untapped potential in the repo): wire pii-redact + secret-scan on input AND output of `generate_chat`; call injection-detect on incoming prompts; give network-zerotrust a chokepoint at outbound provider calls (literally its doctrinal reason to exist). Each is built + tested + one wiring commit away.

### F-2026-082 · HIGH · Gateway has no auth, no TLS, no socket timeouts
- **Verified**: no `Authorization|Bearer|api_key` in gateway crates; no rustls/TLS; `main.rs` never sets read/write timeouts. `--addr 0.0.0.0:9000` is a documented first-class mode, so a keyless, plaintext daemon whose `/v1/messages` mutates learned memory and whose `/admin/ledger` is open can be exposed to a LAN. Thread-per-connection capped at 256 → 256 slow-loris clients wedge the daemon (byte caps defend memory, not time). The 256-cap "backpressure" `drop(stream)` on fresh accept gives clients a connection reset, not a `503`.
- **Action**: bearer-token gate keyed on an env secret (1-day win; also required for real OpenAI/Anthropic clients that expect 401s); rustls; per-connection deadlines; `503 + Retry-After` on the cap path. Directly adjacent to the Anthropic-compat arc.

### F-2026-083 · HIGH · Generation is globally serialized behind one mutex
- `Generator` behind a single `Mutex` (`gatewayd/src/lib.rs:532`, locked in `generate_chat:677`) → one in-flight generation at a time for the whole daemon; no batching/queue/fairness. Meanwhile `sovereign-continuous-batch` + `sovereign-paged-kv` are built but consumed **only by inference-demo**, and `sovereign-worker-fleet` (0 consumers) + `sovereign-load-balance` (demo-only) exist unused. Action: assemble worker-fleet + load-balance + continuous-batch + paged-kv into an actual N-worker generation queue — the built-but-unwired path to concurrency, and the thing that makes the "fleet/orchestration" vocabulary true.

> **Arc-3 status (2026-07-12):** **PARTIALLY CLOSED by SDD-951** (`docs/sdd/951-durable-memory-corruption-safety.md`). Corruption no longer discards learned memory — an unparseable store is moved aside to `<path>.corrupt` and reseeded loudly (`load_memory_from`); and the store is now capped (`MemoryStore::set_capacity` + `SOVEREIGN_GATEWAY_MEMORY_CAP`) so it can't grow unbounded. **The decay half remains OPEN** (Q-901-001): the M028 `maintain` pass is still unscheduled — it needs a unified monotonic admission clock first (request `now` is ad-hoc today), so a decay thread on an independent clock could over- or under-age. Bounded growth caps the accumulation symptom clock-independently in the meantime.

### F-2026-084 · HIGH · Durable memory: corruption = silent total loss; decay never runs
- **Verified**: load is `serde_json::from_str(&json).unwrap_or_else(|_| seed_memory())` (`lib.rs:608`) — a truncated file or schema change silently discards ALL learned memory and reseeds, despite `MemoryStore` having a `schema_version` + `SchemaMismatch` error the daemon doesn't use. `maintain()` (M028 decay) exists (`lib.rs:963`) but `main.rs` spawns only the persist thread (`main.rs:96`) — **decay never runs in production**, so stale memory accumulates forever and the daemon's advertised "long-running hygiene" is dead. Snapshot is a whole-file rewrite every ~10s with no size ceiling (daemon uses `with_memory`, not the existing `Cortex::bounded`).
- **Action**: use the versioned loader + back up to `.corrupt` on mismatch (never silently reseed); add a `maintain` timer thread; switch to `Cortex::bounded`; adopt the unused `save-state`/`checkpoint` crates instead of inline JSON.

### F-2026-085 · HIGH · "Quant" loader loads dense F32 only; no quantized weight loading; no GPU
> **Status (2026-07-12):** **PARTIALLY CLOSED by SDD-953** (`docs/sdd/953-configurable-model-load.md`). The load side is no longer f32-only: `load_at_precision` / `load_configured` thread a caller-chosen `Precision` into `MhaDecoderBlock::from_weights` (which already accepts any precision), so a real safetensors checkpoint now loads as Ternary / NVFP4 / INT8 / BF16 in-memory via the already-tested quantize-from-f32 machinery (a 7B at ~7GB INT8 / ~14GB BF16 instead of ~28GB f32) — `load` still defaults to F32 (additive). **Still OPEN:** loading an *already*-quantized checkpoint (GGUF Q4_K/Q8_0, GPTQ, AWQ) — no dequant-from-disk path exists in the workspace; that + the GPU backend remain milestone-scoped.
- Despite the name, `safetensors-loader::load` builds every layer at `Precision::F32` (`lib.rs:373`); GGUF Q4_K/Q8_0 dequant is a named-but-unbuilt follow-up. No int8/int4/NVFP4 **load** path from real weights — the NVFP4/ternary machinery only runs on synthetic fixtures in inference-demo. No CUDA/Metal/Vulkan backend (`unsafe_code = forbid` workspace-wide). Consequence: a 7B model needs ~28GB as f32 and runs slowly on CPU — undercutting the "local sovereign" premise. The `LayerStack` is already precision-heterogeneous; only the load side is f32-only. Action: implement GGUF/int-quant dequant into the existing stack; scope a GPU story (even a single optional backend) as a milestone.

### F-2026-086 · MED · OpenAI shim drops all sampling params + has no chat template
> **Status (2026-07-12):** **PARTIALLY CLOSED by SDD-953** (`docs/sdd/953-configurable-model-load.md`) — the **model-side** half. The loader no longer hardwires greedy: `load_with_sampler` / `load_configured` thread a caller `Sampler`, and NEW `QuantModel::with_sampler` + `sampler()` make sampling configurable + introspectable at the model level — so `temperature`/`top_p`/`top_k` are now reachable in the generation core. **Still OPEN (deliberately, coordination):** threading per-request HTTP params (`chat_prompt` / `generate_chat` signature in `main.rs`) → the sampler, the chat template + `tokenizer_config.json` pre-tokenizer read, and the non-streaming JSON shape — that surface is owned by the parallel Anthropic-Messages-API session; SDD-953 provides the model-side hook it plugs into.
- `chat_prompt` (`main.rs:411`) newline-joins message content — no roles, no system prompt, no chat template. Honors only `max_tokens` (clamped 1..1024); ignores `temperature/top_p/top_k/stop/n/penalties/logit_bias/response_format/tools/stream:false`. The loader hardwires `Sampler::greedy()` so temperature can't be honored even if parsed. The 790-line `sovereign-sampler` (mirostat/typical/xtc/dry/gumbel) + decoder-stack's dozen `generate_*` variants are unreachable. Always SSE (no non-streaming JSON shape). Action: thread request params → `SamplerConfig`; read real chat template + pre-tokenizer from `tokenizer_config.json` (the hf-tokenizer pretokenizer is a hand-rolled GPT-2 approximation, `lib.rs:273`, that mis-segments Llama/Metaspace models); add a non-streaming response shape. **This section is the direct substrate the Anthropic-compat conversation depends on** — flag for coordination.

### F-2026-087 · MED · SSE robustness gaps
- No heartbeat/keepalive during first-token latency (client idle-timeouts fire); no `id:`/`retry:`/`event:` framing; mid-stream errors emitted as a content delta then `finish_reason:stop` (client can't distinguish error from completion); constant `chatcmpl-sovereign` id (not unique per request). Action: unique ids, distinct SSE error framing, periodic keepalive comments.

### F-2026-088 · MED · ReAct agent + tools built but unwired from the daemon
- `sovereign-agent-loop` (clean ReAct, repeat-guard, step-cap) + `sovereign-agent-runtime` (LlmResponder) exist and are tested but consumed only by inference-demo + retrieval — `/v1/chat/completions` can't use tools. Tool syntax is a bespoke `[[tool:NAME|ARGS]]`, not OpenAI/Anthropic `tool_use`. Also agent-runtime "decodes from a fresh model clone each call" (`agent-runtime/src/lib.rs:8`) — prohibitively expensive for a real model, discards KV across steps. Action: bridge `tool_use` ↔ `[[tool:…]]`, let the gateway run the loop, share one model instance across agent steps.

### F-2026-089 · MED · `sovereign-serve` (the safer path) is dead relative to the daemon
> **Status (2026-07-12):** **SCOPED by SDD-957** (`docs/sdd/957-serve-vs-gatewayd-architecture-decision.md`) — **OPEN, awaiting operator decision Q-957-A**. Two premise corrections: serve's real *library* pipeline is only cache→complexity→budget (pii/secret/toxicity are opt-in flags in its demo *binary*, not the pipeline), and SDD-206 already put injection/secret/pii/toxicity into `gatewayd::generate_chat` default-on. serve **cannot be the daemon** (no network interface; toy model) and is **dead** (0 non-test consumers). The only real delta post-206: completion-cache + token-budget (complexity is superseded by router-7axis). **Recommendation: Option A** — fold cache+token-meter into `generate_chat` (the SDD-206 insertion pattern), skip complexity, retire serve; sequenced with the parallel sessions that own `generate_chat`. Implementation gates F-2026-081/086 and waits on Q-957-A.
- `serve` composes cache + complexity + token-budget + pii-redact + secret-scan + toxicity — everything the daemon lacks — but is NOT the daemon and gatewayd never invokes it. Two parallel serving orchestrators; the richer, safer one doesn't run. Action: decide the architecture — either fold serve's filter chain into gatewayd or promote serve to be the daemon. This decision gates F-2026-081/086.

### F-2026-090 · OPP · CoAT engine is the most mature new piece — protect + extend it
- `sovereign-coat` (1262 LOC, 14 tests): one real MCTS parameterized into CoT/ToT/MCTS/C-MCTS/CoAT presets, model-gated via `ThoughtSource`+`AssociativeMemory` traits, honesty-enforced (`thought_source: heuristic|model` in the trace), wired live into `/v1/coat` recalling from the daemon's real Cortex memory. Gap: model-backed CoAT calls the model once per expansion holding the generation mutex (bounded ≤12 iters, rollout off) — serially blocks all other generation. Opportunity: route model-backed CoAT through the background-jobs runtime (already exists) so deliberation never blocks the request path; add a model-backed integration test (only heuristic path is tested).

### F-2026-091 · OPP · Background-jobs runtime is real and mature (Python) — grow it
- `jobs_store.py` + `jobs-api.py`: durable atomic JSON registry, thread pool, per-job cancel events, orphan-resume on startup, a `/v1/coat` deliberation runner. Gaps: jobs run in-process (daemon restart mid-job = lost, only "mark failed" on resume, no work checkpoint); no per-job resource limits/priority; generic subprocess runner (`_run_command`) vs the systemd `ReadWritePaths=/var/lib/sovereign-os/jobs`-only sandbox will fail for `eval`/`model-load`/`gpu-job` kinds writing elsewhere. Action: per-kind ReadWritePaths, work checkpointing, resource caps; it's the natural home for all long-running deliberation/eval/model-load.

### F-2026-092 · MED · Auto-mode safety classifier is an evadable denylist, mis-framed as a boundary
> **Status (2026-07-12):** **CLOSED by SDD-954** (`docs/sdd/954-permission-classifier-flag-normalization.md`). The `rm` gap is fixed by flag normalization (`_rm_recursive_or_force` — split `rm -r -f`, uppercase `-R`, reordered, and long `--recursive --force` forms all classify `destructive` now, tightening-only, fail-safe preserved), and the classifier is reframed in its docstring + the plan-mode directive as a **best-effort UX heuristic, not a security boundary**. The **real boundary** (sandbox-profile / fs-enforcement around the execution paths; calling it from agent-loop / the jobs runner) remains F-2026-081 — this closure makes the classifier honest about being the UX layer on top of that, not a substitute for it.
- `permission_classifier.py`: ~17 regexes; `rm -rf /x`→block ✓ but `rm -r -f /x`/`rm -R -f /x`→confirm ✗, and var/quoting/`$IFS` obfuscation escapes entirely (fails toward `confirm`, never silent-allow). It is Python, disjoint from the Rust security crates, and NOT called by `agent-loop` or the jobs subprocess runner — so tool/command execution is effectively ungated except by this advisory heuristic. Action: normalize flags + add `rm -r -f`/`-R` regressions; re-frame doctrine text from "auto-blocks destructive" to "best-effort UX"; put the real boundary in sandbox-profile/fs-boundary enforcement around the execution paths (ties to F-2026-081).

### F-2026-093 · OPP · Untapped assets worth surfacing
> **Status (2026-07-12):** **CLOSED by SDD-955** (`docs/sdd/955-wire-the-island-register.md`) — as a machine-enforced register, not a one-time list. `docs/review/phase-1/island-register.md` enumerates the **35 pure-library `sovereign-*` crates with zero reverse-dependencies** (holderpo, save-state, worker-fleet, the ZFS/VM/network/sandbox family, …), each with a disposition (14 aspirational / 21 wireable) + a trigger; `tests/lint/test_island_register.py` keeps it honest both directions (a new orphan or a newly-wired island fails CI). **Correction to this finding as written:** `sovereign-world-model` and `sovereign-hrm-runtime` are NOT islands — both are dependencies of `sovereign-cortex` (a direct gatewayd dep), so they run in the daemon. The actual highest-leverage wiring (a real `sovereign-llm` consumer in cortex/gateway, which lights up most wireable islands transitively) remains F-2026-083/088/089; `sovereign-inference-demo` still runs synthetic weights (a real-model upgrade needs weights/network, unavailable here).
- `sovereign-inference-demo` runs on deterministic pseudo-weights (a composition proof, not a model demo) — now that safetensors-loader + hf-tokenizer exist, upgrade it to load a real small model as the repo's proof-of-life (gated on F-2026-080 rope fix). The 790-line sampler, the checkpoint/save-state crates, HölderPO (`sovereign-holderpo`, 0 consumers — a headline "post-training" pillar nothing calls), and world-model/hrm-runtime are all built and under-exposed. Action: a "wire the island" backlog epic that, per crate, either wires it into cortex/gatewayd or marks it explicitly aspirational with a tracked trigger.

### F-2026-095 · MED · The July intelligence-layer arc never passed `cargo fmt --all --check`
- **Verified live**: when the branch was first CI'd (PR #119), the `cargo fmt --all --check` step failed with **52 violations** — `sovereign-coat/src/lib.rs` (39), `sovereign-gatewayd/src/{http.rs,lib.rs,main.rs}` (13). The intelligence-layer commits (`234a474..7e9dea2`) were authored and landed on the branch without ever going through the fmt gate, because they were never opened as a PR until this audit. Fixed in this ledger's PR via a dedicated `cargo fmt --all` commit (mechanical; both crates still compile).
- **Root-cause action**: this is process, not code — the parallel-session workflow committed to a long-lived branch that bypassed CI. Add a `pre-commit`/`pre-push` git hook running `cargo fmt --all --check` (the repo already has `scripts/git-hooks/`), so unformatted Rust can't land locally regardless of whether a PR is open. Cousin to F-2026-060 (the arc bypassed every state surface AND the CI gate).

### F-2026-094 · MED · `/v1/deliberate` vs `/v1/coat` naming overlap; disjoint "brains"
> **Status (2026-07-12):** **CLOSED by SDD-956** (`docs/sdd/956-gateway-api-route-parity.md`). The single gateway API reference already existed (`docs/src/ai-backend.md`, all 19 routes); the gap — nothing kept it honest against the code — is closed by `tests/lint/test_gateway_route_parity.py`, which asserts the served route set (from the daemon dispatch) equals the documented set both directions (parity 19==19 today). The routing-vs-generation "two brains" split (cortex routes + produces decisions/traces, **never text**; the safetensors path generates text) and the `/v1/deliberate` (best-of-N) vs `/v1/coat` (CoAT ladder trace) distinction are documented in SDD-956. The optional "fold best-of-N into the ladder" is recorded as a future runtime consolidation, not done.
- `/v1/deliberate` (cortex best-of-N) and `/v1/coat` (CoAT ladder) coexist with overlapping names; separately, the routing "brain" (cortex) and the generation "brain" (safetensors path) are disjoint — cortex generates no text. Action: a single gateway API reference (also needed by the Anthropic-compat arc) that delineates every `/v1/*` surface and clarifies the routing-vs-generation split; consider folding best-of-N into the ladder narrative.

## H. Cross-cutting themes + recommended sequencing

**The five recurring patterns across all findings:**

1. **Built-but-unwired islands.** The dominant motif: security crates, agent loop, continuous-batch/paged-kv, worker-fleet/load-balance, HölderPO, save-state/checkpoint, and 448 orphan crates (413 cockpit) are all real, tested, and consumed by nothing that runs. The repo's value is disproportionately locked in unwired libraries. → The highest-ROI work is *wiring*, not building.
2. **Living-doc drift.** context.md (self-violating its no-drift rule), ARCHITECTURE.md, mdbook, SDD INDEX statuses, SHIPPED.md, and MASTER-PLAN all trail the code by weeks-to-months and contradict each other. → Structural fix: generate the counts/statuses/summaries from the file tree + git, and lint them (counts-as-contract) so drift fails CI instead of accumulating.
3. **Doctrine over-claim vs runtime reality.** "Auto-blocks destructive," gateway "Privacy/Redaction," "three-tier test harness," "fleet/orchestration" — each is asserted in docs/naming but absent or partial in the running path. → Reconcile every doctrinal claim with an implementing-or-explicitly-deferred status.
4. **Verbatim/copy-paste as design.** 49% of the webapp and the whole cockpit-crate family are deliberate duplication for "sovereignty-clean" isolation. → Not wrong, but needs the sync-tool+drift-lint discipline extended to ALL duplicated surfaces, or the duplication silently rots.
5. **Excellent discipline where it exists.** 713/714 crates tested, zero real TODO/FIXME, no unsafe, no hardcoded paths, collision-free port map, schema-conformance tests, honest-offline provenance, atomic persistence. → Protect these with invariant lints so the bar never drops.

**Recommended sequencing for the next SDD-driven arcs (dependency-ordered):**

- **Arc 1 — "make the real model real" (unblocks everything downstream + the Anthropic-compat arc):** F-2026-080 (rope_theta), F-2026-086 (sampling params + chat template + pre-tokenizer), F-2026-085 (quantized load), F-2026-093 (real-model demo). Without this, every generation surface produces garbage on modern models.
- **Arc 2 — "wire the safety spine into the daemon":** F-2026-081 (security crates → gatewayd), F-2026-082 (auth/TLS/timeouts), F-2026-089 (serve-vs-gatewayd decision), F-2026-092 (classifier reframe + real sandbox).
- **Arc 3 — "lift the concurrency ceiling":** F-2026-083 (worker-fleet/load-balance/batch), F-2026-084 (memory corruption + decay), F-2026-088 (agent/tools wiring).
- **Arc 4 — "commit-authority + mutation-surface gating" (SDD-055/MS003):** F-2026-034 — the acknowledged cross-cutting hole; sweep osctl verbs + operator APIs + selfdefctl parity verbs.
- **Arc 5 — "state-surface truth" (docs + drift lints):** F-2026-030/031/032/033/036/060 — refresh + generate + lint; author handoff 008; land the July arc.
- **Arc 6 — "cockpit consolidation":** F-2026-001 (413 crate fate), F-2026-070 (panel forks), F-2026-073 (webapp dedup), F-2026-035 (functional-execution phases).
- **Continuous — "protect the baseline":** invariant lints per F-2026-004/009/020, plus F-2026-021/023/024/037/051/052/071/074 as fill-in polish.

---

*End of Phase-1 findings ledger. Each `F-2026-NNN` is a candidate for an SDD (`docs/sdd/NNN-*.md`), a backlog milestone R-row, or a directly-cited commit. Nothing here has been fixed — Phase 1 produces the map.*
