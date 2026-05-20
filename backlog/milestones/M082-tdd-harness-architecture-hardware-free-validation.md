# M082 — TDD Harness Architecture — hardware-free validation (macro-arc PRs 9 + 10)

**Parent**: sovereign-os runtime — image-build TDD discipline + Stage Gate 5 foundation-complete checkpoint
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- **PR 9 — TDD Harness SDD** (lines 229–257) — `docs/sdd/008-test-harness.md` ~800 LOC
- **PR 10 — TDD Harness Scaffold + First Passing Tests** (lines 260–285) — `tests/` scaffolding + CI + `docs/sdd/009-test-harness-bootstrap.md` ~1200 LOC mixed
- **Stage Gate 5 — foundation-complete gate** (lines 280–283)
**Operator standing direction** (verbatim, 2026-05-19): *"work in SDD and TDD and be an architect first, then a DevOps Software Engineer and Fullstack and UX Design Specialist"* / *"DO NOT MINIMIZE WHAT I SAY, SAID OR ASKED FOR, NOR THE NEED TO EXPLOIT THE STACK AND TECHNO TO THE MAX"* / *"Make sure your order of execution make sense too. Some things depend on others, all that intelligence must be there too."*
**Companion**: M062 macro-arc scaffold (PRs 9+10 are the FINAL two of the 10-PR foundation arc), M065 five-stage-gates (SG5 is the foundation-complete gate), M064 substrate decision (informs harness choices), M081 whitelabel (informs assertions), selfdef MS020 L1-L5 layered harness (sister discipline; both repos run the SAME 5-layer methodology)
**Project boundary**: sovereign-os ONLY — selfdef IPS has its own MS020 + MS045 test-contract milestones; this M082 is the sovereign-os image-build harness; cross-repo schema-conformance is tested in BOTH harnesses independently

## Doctrinal anchors

> "Specify how an image-build pipeline gets unit-, stage-, and integration-tested without hardware." (macro-arc dump 232)
> "Schema/lint tests — Pure CI. No virtualization." (macro-arc dump 235)
> "Unit tests — individual build scripts tested in isolation (mocked filesystem, mocked apt, mocked dpkg)." (macro-arc dump 236)
> "Hardware-conformance tests — gated tests that only run when matching hardware is present (SAIN-01 hardware, when procured)." (macro-arc dump 239)
> "Virtualization stack: chroot / systemd-nspawn / QEMU (system) / qemu-user." (macro-arc dump 240–244)
> "First executable test code. Validates the harness works end-to-end on the only artifacts that exist (profile YAMLs, whitelabel YAMLs, schemas)." (macro-arc dump 262)
> "Stage Gate 5 (foundation-complete gate): Operator reviews the full 10-PR arc holistically." (macro-arc dump 280)
> *"work in SDD and TDD"* (operator standing direction 2026-05-19)

## Projection statement

Sovereign-OS is an image-build project — it produces a bootable artifact (Debian-13-based, znver5-tuned, ZFS-rooted, IPS-gated, whitelabel-rendered). The TDD Harness Architecture is the **5-layer test pyramid** that validates every layer of that artifact **without requiring the actual hardware** for most signals — only Layer 5 (Hardware-conformance) gates on a procured SAIN-01 node. The harness is built in two paired PRs: **PR 9 specifies** (`docs/sdd/008-test-harness.md` — test layers, virtualization stack, per-stage invariants, naming + discovery + flake policy) and **PR 10 scaffolds** (`tests/schema/`, `tests/lint/`, `tests/chroot/scaffold.sh`, `tests/nspawn/scaffold.sh`, `tests/qemu/scaffold.sh`, `.github/workflows/test.yml`, plus `docs/sdd/009-test-harness-bootstrap.md` + `docs/sdd/010-stage-2-stub.md` placeholder). PR 10 lands the **first passing tests** against the only artifacts that exist after PRs 1-8: profile YAMLs, whitelabel YAMLs, and schemas. Stage Gate 5 marks the **foundation-complete** checkpoint: charter set, substrate chosen, profile schema locked with two conformant instances, whitelabel mechanism specified, harness operational. Stage 2 (actual build scripts) is authorized ONLY after this gate.

## Epics (E0788-E0797)

| epic | name | source |
|---|---|---|
| E0788 | Five-layer test pyramid — schema/lint → unit → stage acceptance → integration → hardware-conformance | macro-arc 235–239 |
| E0789 | Virtualization stack — chroot / systemd-nspawn / QEMU system / qemu-user | macro-arc 240–244 |
| E0790 | Per-stage invariants — explicit assertions per lifecycle stage (pre-install / during-install / post-install-first-boot) | macro-arc 245–246 |
| E0791 | Test discovery + naming convention + CI execution model + flake policy | macro-arc 247 |
| E0792 | tests/INDEX.md + tests/README.md — test catalog + operator onboarding | macro-arc 248 |
| E0793 | Scaffold deliverables — schema/lint/chroot/nspawn/qemu harness skeletons | macro-arc 263–266 |
| E0794 | CI workflow — schema+lint on every PR, chroot/nspawn/qemu on merge/label | macro-arc 268–269 |
| E0795 | docs/sdd/009-test-harness-bootstrap.md — what scaffold delivers + what it explicitly does NOT | macro-arc 270–273 |
| E0796 | docs/sdd/010-stage-2-stub.md — placeholder for Stage 2 actual build-script PR | macro-arc 274 |
| E0797 | Stage Gate 5 — foundation-complete gate — operator reviews full 10-PR arc | macro-arc 280–283 |

## Modules (M01369-M01394)

| module | name | source |
|---|---|---|
| M01369 | sovereign-harness-l1-schema-lint-runner | macro-arc 235 |
| M01370 | sovereign-harness-l1-yaml-schema-validator (profile + whitelabel) | macro-arc 235 + M081 |
| M01371 | sovereign-harness-l1-markdown-linter | macro-arc 264 |
| M01372 | sovereign-harness-l1-decisions-log-linter | macro-arc 264 |
| M01373 | sovereign-harness-l1-sdd-index-consistency-checker | macro-arc 264 |
| M01374 | sovereign-harness-l2-unit-runner (mocked-filesystem + apt + dpkg) | macro-arc 236 |
| M01375 | sovereign-harness-l2-mocked-apt | macro-arc 236 |
| M01376 | sovereign-harness-l2-mocked-dpkg | macro-arc 236 |
| M01377 | sovereign-harness-l2-mocked-filesystem | macro-arc 236 |
| M01378 | sovereign-harness-l3-stage-acceptance-runner (pre/during/post-install) | macro-arc 237 + 245 |
| M01379 | sovereign-harness-l3-chroot-driver | macro-arc 240–241 |
| M01380 | sovereign-harness-l3-nspawn-driver | macro-arc 242 |
| M01381 | sovereign-harness-l4-integration-runner (full image boot in QEMU) | macro-arc 238 |
| M01382 | sovereign-harness-l4-qemu-system-driver (UEFI + secure-boot + PCIe passthrough emul) | macro-arc 243 |
| M01383 | sovereign-harness-l4-qemu-user-driver (cross-arch validation) | macro-arc 244 |
| M01384 | sovereign-harness-l5-hardware-conformance-runner (gated on real hw) | macro-arc 239 |
| M01385 | sovereign-harness-l5-sain01-hardware-detector (procurement gate) | macro-arc 239 |
| M01386 | sovereign-harness-invariant-pre-install-asserter | macro-arc 245 |
| M01387 | sovereign-harness-invariant-during-install-asserter | macro-arc 245 |
| M01388 | sovereign-harness-invariant-post-first-boot-asserter | macro-arc 245–246 |
| M01389 | sovereign-harness-test-discovery (recursive walker + naming-convention parser) | macro-arc 247 |
| M01390 | sovereign-harness-ci-executor (.github/workflows/test.yml) | macro-arc 268 |
| M01391 | sovereign-harness-ci-gating (schema+lint on PR, chroot/nspawn/qemu on merge/label) | macro-arc 268–269 |
| M01392 | sovereign-harness-flake-policy-engine | macro-arc 247 |
| M01393 | sovereign-harness-index-generator (tests/INDEX.md + tests/README.md auto-regen) | macro-arc 248 |
| M01394 | sovereign-harness-sg5-gate-recorder (Stage Gate 5 foundation-complete verdict) | macro-arc 280–283 |

## Features (F06836-F06955)

| feature | name | source |
|---|---|---|
| F06836 | L1 layer — schema/lint tests run in pure CI (no virtualization) | macro-arc 235 |
| F06837 | L1 layer — profile YAML validation against `schemas/profile.schema.yaml` | macro-arc 235 + M064 |
| F06838 | L1 layer — whitelabel YAML validation against `schemas/whitelabel.schema.yaml` | macro-arc 235 + M081 |
| F06839 | L1 layer — markdown lint via markdownlint-cli2 | macro-arc 264 |
| F06840 | L1 layer — decisions-log linter (one entry per decision, monotonic timestamps) | macro-arc 264 |
| F06841 | L1 layer — SDD index consistency checker (every SDD in index, every index row exists) | macro-arc 264 |
| F06842 | L1 layer — exit codes: 0 pass, 1 schema fail, 2 lint fail, 3 SDD index drift | arch + UX |
| F06843 | L1 layer — every artifact emits ≥1 assertion (no orphan files) | arch + macro-arc 264 |
| F06844 | L1 layer — runs in CI as pre-merge required gate | macro-arc 268 |
| F06845 | L1 layer — runtime budget: ≤ 60 seconds wall-clock on standard CI runner | budget |
| F06846 | L2 layer — individual build scripts unit-tested in isolation | macro-arc 236 |
| F06847 | L2 layer — mocked filesystem (overlayfs-backed virtual root) | macro-arc 236 |
| F06848 | L2 layer — mocked apt (`apt-get install` recorded, no network) | macro-arc 236 |
| F06849 | L2 layer — mocked dpkg (`dpkg -i` recorded, no actual install) | macro-arc 236 |
| F06850 | L2 layer — every build script has at least one L2 unit test | arch + macro-arc 236 |
| F06851 | L2 layer — runtime budget: ≤ 120 seconds wall-clock on standard CI runner | budget |
| F06852 | L2 layer — flake policy: 1 retry on transient mock failure | macro-arc 247 |
| F06853 | L3 layer — stage acceptance tests per lifecycle stage (pre-install / during-install / post-first-boot) | macro-arc 237 + 245 |
| F06854 | L3 layer — chroot driver runs package-level assertions | macro-arc 240–241 |
| F06855 | L3 layer — chroot assertions: "package X installed", "file Y present with content Z" | macro-arc 241 |
| F06856 | L3 layer — systemd-nspawn driver runs service-startup assertions | macro-arc 242 |
| F06857 | L3 layer — nspawn assertions: "systemd unit U active", "convergence reached within Δt" | macro-arc 242 |
| F06858 | L3 layer — invariant per-stage: pre-install (substrate readiness) | macro-arc 245 |
| F06859 | L3 layer — invariant per-stage: during-install (package set applied, chroot integrity) | macro-arc 245 |
| F06860 | L3 layer — invariant per-stage: post-install-first-boot (hostname matches profile) | macro-arc 245–246 |
| F06861 | L3 layer — invariant: whitelabel surfaces match whitelabel profile (cross-ref M081 F06782) | macro-arc 246 + M081 |
| F06862 | L3 layer — invariant: ZFS pool present and healthy (cross-ref M068) | macro-arc 246 + M068 |
| F06863 | L3 layer — invariant: expected systemd units active (cross-ref selfdef MS046 friction-audit ordering) | macro-arc 246 + selfdef MS046 |
| F06864 | L3 layer — invariant: selfdef-perimeter.yaml TracingPolicy loaded (cross-ref selfdef MS047) | macro-arc 246 + selfdef MS047 |
| F06865 | L3 layer — runtime budget: ≤ 600 seconds wall-clock on standard CI runner | budget |
| F06866 | L3 layer — runs on merge to main OR via label trigger | macro-arc 268–269 |
| F06867 | L4 layer — full image built and booted in QEMU | macro-arc 238 |
| F06868 | L4 layer — QEMU system driver supports UEFI boot mode | macro-arc 243 |
| F06869 | L4 layer — QEMU system driver supports secure-boot testing | macro-arc 243 |
| F06870 | L4 layer — QEMU system driver supports PCIe passthrough emulation (limited, for VFIO smoke) | macro-arc 243 |
| F06871 | L4 layer — qemu-user driver for cross-arch validation | macro-arc 244 |
| F06872 | L4 layer — smoke tests inside the booted system (ssh + selfdef perimeter + ZFS health) | macro-arc 238 |
| F06873 | L4 layer — boot assertion: GRUB menu entry visible | macro-arc 243 |
| F06874 | L4 layer — boot assertion: kernel cmdline matches profile (znver5 + vfio-pci.ids) | macro-arc 243 + sain-01 §4.3 |
| F06875 | L4 layer — boot assertion: initramfs loads (no kernel panic, no rescue shell) | macro-arc 243 |
| F06876 | L4 layer — boot assertion: systemd reaches multi-user.target within Δt | macro-arc 243 + selfdef MS046 |
| F06877 | L4 layer — runtime budget: ≤ 1800 seconds wall-clock on standard CI runner | budget |
| F06878 | L4 layer — runs on merge to main OR via label trigger | macro-arc 268–269 |
| F06879 | L5 layer — hardware-conformance tests gated on matching hardware presence | macro-arc 239 |
| F06880 | L5 layer — SAIN-01 hardware detector (ProArt X870E-Creator + znver5 + Marvell 10GbE + Intel 2.5GbE + RTX 3090 ×2) | macro-arc 239 + sain-01 §1 |
| F06881 | L5 layer — runs only when hw detected; skipped with reason logged when absent | macro-arc 239 + UX |
| F06882 | L5 layer — VFIO passthrough verification: nvidia-smi inside guest sees the GPU | macro-arc 239 + sain-01 §4.3 |
| F06883 | L5 layer — AVX-512 verification: VPDPBUSD instruction available + cycle-accurate (cross-ref M074) | macro-arc 239 + M074 |
| F06884 | L5 layer — ZFS production-mode verification: tank pool created with operator-spec datasets | macro-arc 239 + M068 |
| F06885 | L5 layer — friction-audit gate verification: PCIe x8/x8 lanes confirmed (cross-ref selfdef MS046) | macro-arc 239 + selfdef MS046 |
| F06886 | L5 layer — perimeter gate verification: unauthorized binary Sigkill'd (cross-ref selfdef MS047) | macro-arc 239 + selfdef MS047 |
| F06887 | L5 layer — runtime budget: ≤ 3600 seconds wall-clock on operator hardware | budget |
| F06888 | L5 layer — operator-triggered only (never automatic; never in CI without operator label) | UX + macro-arc 239 |
| F06889 | Test discovery — recursive walker under `tests/<layer>/` | macro-arc 247 |
| F06890 | Test discovery — naming convention: `test_<topic>_<assertion>.<ext>` | macro-arc 247 |
| F06891 | Test discovery — every test declares its layer via filename prefix or directory | macro-arc 247 |
| F06892 | Test discovery — operator can list all tests with `sovereign test list [--layer N]` | macro-arc 247 + UX |
| F06893 | CI execution model — schema+lint on every PR (required gate) | macro-arc 268 |
| F06894 | CI execution model — chroot/nspawn on merge to main | macro-arc 269 |
| F06895 | CI execution model — qemu on merge to main + label-trigger PRs | macro-arc 269 |
| F06896 | CI execution model — L5 hardware-conformance NEVER runs in CI (operator-local only) | macro-arc 239 + 269 |
| F06897 | CI execution model — workflow file `.github/workflows/test.yml` ~400 LOC | macro-arc 268 + 275 |
| F06898 | CI execution model — separate workflow `test-hardware.yml` for label-triggered + operator-local | macro-arc 269 + arch |
| F06899 | Flake policy — L1 flake = blocker (no retry; assertion bug) | macro-arc 247 + arch |
| F06900 | Flake policy — L2 flake = 1 retry on transient mock failure | macro-arc 247 + F06852 |
| F06901 | Flake policy — L3 flake = 2 retries; 3 consecutive fails = block release | macro-arc 247 + arch |
| F06902 | Flake policy — L4 flake = 2 retries with bisect-on-retry-fail | macro-arc 247 + arch |
| F06903 | Flake policy — L5 flake = operator decision (manual replay) | macro-arc 247 + UX |
| F06904 | tests/INDEX.md — auto-regenerated catalog of every test (file + layer + topic + last-run) | macro-arc 248 |
| F06905 | tests/INDEX.md — sortable by layer, topic, last-pass-date | macro-arc 248 + UX |
| F06906 | tests/README.md — operator-onboarding doc (how to run a layer, how to add a test, how to investigate flakes) | macro-arc 248 |
| F06907 | Scaffold — `tests/schema/` directory with one schema-conformance test per schema | macro-arc 263 |
| F06908 | Scaffold — `tests/lint/` directory with markdown/decisions/SDD linters | macro-arc 264 |
| F06909 | Scaffold — `tests/chroot/scaffold.sh` chroot harness skeleton (substrate-aware) | macro-arc 265 |
| F06910 | Scaffold — `tests/nspawn/scaffold.sh` nspawn harness skeleton | macro-arc 266 |
| F06911 | Scaffold — `tests/qemu/scaffold.sh` QEMU harness skeleton with stubbed boot test | macro-arc 267 |
| F06912 | Scaffold — `.github/workflows/test.yml` CI workflow | macro-arc 268 |
| F06913 | Scaffold — first passing tests against existing artifacts (profiles + whitelabels + schemas) | macro-arc 262 |
| F06914 | Scaffold — `docs/sdd/008-test-harness.md` ~800 LOC (PR 9 deliverable) | macro-arc 254 |
| F06915 | Scaffold — `docs/sdd/009-test-harness-bootstrap.md` ~400 LOC (PR 10 deliverable) | macro-arc 273 + 275 |
| F06916 | Scaffold — `docs/sdd/010-stage-2-stub.md` placeholder (Stage 2 reservation) | macro-arc 274 |
| F06917 | Scaffold — what 009 explicitly does NOT deliver: no image yet, no build scripts yet | macro-arc 273 |
| F06918 | Scaffold — first executable test code total ~1200 LOC (PR 10 estimate) | macro-arc 276 |
| F06919 | Scaffold — CI green on the scaffold without any actual image artifacts | macro-arc 262 + 268 |
| F06920 | Stage Gate 5 — operator reviews full 10-PR arc holistically | macro-arc 280 |
| F06921 | Stage Gate 5 — checkpoint: charter set (PR 1) | macro-arc 281 + cross-ref M062 |
| F06922 | Stage Gate 5 — checkpoint: substrate chosen (PR 4) | macro-arc 281 + M064 |
| F06923 | Stage Gate 5 — checkpoint: profile schema locked with two conformant instances (PR 6) | macro-arc 281 + macro-arc 151–170 |
| F06924 | Stage Gate 5 — checkpoint: whitelabel mechanism specified (PR 8) | macro-arc 281 + M081 |
| F06925 | Stage Gate 5 — checkpoint: hardware-free test harness operational (PR 9 + PR 10) | macro-arc 281–282 |
| F06926 | Stage Gate 5 — Stage 2 (actual build scripts) authorized ONLY after this gate | macro-arc 282 |
| F06927 | Stage Gate 5 — gate output recorded in `docs/decisions/sg5-foundation-complete-<YYYY-MM-DD>.md` | macro-arc 280 + cross-ref M065 |
| F06928 | Stage Gate 5 — gate verdict mirrored via MS007 to selfdef MS043 TUI authority panel | cross-ref MS007 + selfdef MS043 |
| F06929 | Stage Gate 5 — operator may rescind gate verdict (gate is reversible if foundation regresses) | macro-arc 280 + operator agency |
| F06930 | Cockpit binding — M060 dashboard panel "Test Harness" surfaces last-run verdict per layer | cross-ref M060 + UX |
| F06931 | Cockpit binding — panel rows: L1 PASS/FAIL, L2 PASS/FAIL, L3 PASS/FAIL, L4 PASS/FAIL, L5 SKIPPED/PASS | cross-ref M060 + F06892 |
| F06932 | Cockpit binding — panel surfaces flake count + last-flake timestamp | cross-ref M060 + F06899–F06903 |
| F06933 | Cockpit binding — panel READ-ONLY (no harness mutation from cockpit) | cross-ref M060 + safety |
| F06934 | Cockpit binding — operator triggers L4/L5 from CLI only (not cockpit) | F06888 + safety |
| F06935 | CLI — `sovereign test run --layer <N>` runs layer N | F06892 + UX |
| F06936 | CLI — `sovereign test run --topic <name>` runs all tests for a topic | F06889 + UX |
| F06937 | CLI — `sovereign test list [--layer N]` lists discovered tests | F06892 |
| F06938 | CLI — `sovereign test status` shows last-run verdict per layer | F06930 + UX |
| F06939 | CLI — `sovereign test report --since <duration>` shows pass/fail history | UX |
| F06940 | CLI — `sovereign test bundle` produces operator-portable test-evidence bundle | cross-ref M081 R13559 + UX |
| F06941 | CLI — `--json` flag returns structured output (cross-ref selfdef MS043 R10131) | UX + cross-ref selfdef MS043 |
| F06942 | CLI — startup p95 ≤ 50 ms (cross-ref selfdef MS043 R10137) | UX + cross-ref selfdef MS043 |
| F06943 | Sub-requirements accounting — every R-row decomposes into ≥10 sub-requirements per SDD discipline | operator standing 2026-05-19 |
| F06944 | Sub-requirements — sub-requirements live in `docs/sdd/008-test-harness.md` (R-row L-binding) | macro-arc 254 + arch |
| F06945 | Sub-requirements — additional sub-requirements in `docs/sdd/009-test-harness-bootstrap.md` | macro-arc 273 + arch |
| F06946 | Sub-requirements — sub-requirements link to test fixture file paths | arch + F06889 |
| F06947 | Cross-cutting — harness coverage reported in M060 main dashboard top-row summary | cross-ref M060 |
| F06948 | Cross-cutting — harness verdict surfaces in M072 master-bootstrap checklist | cross-ref M072 |
| F06949 | Cross-cutting — harness changes recorded in selfdef MS027 observability stream (read-only) | cross-ref selfdef MS027 |
| F06950 | Cross-cutting — harness participates in selfdef MS009 audit-cycle review | cross-ref selfdef MS009 |
| F06951 | Cross-cutting — harness validates selfdef MS046 friction-audit gate before claiming PASS | cross-ref selfdef MS046 + F06885 |
| F06952 | Cross-cutting — harness validates selfdef MS047 perimeter before claiming PASS | cross-ref selfdef MS047 + F06886 |
| F06953 | Cross-cutting — harness validates whitelabel rendering before claiming PASS (cross-ref M081 R13564) | cross-ref M081 + F06861 |
| F06954 | Cross-cutting — harness flake-policy events emit OCSF Audit 1003 (cross-ref selfdef MS026) | F06899–F06903 + cross-ref selfdef MS026 |
| F06955 | Cross-cutting — harness verdicts NEVER leave the local node by default (no telemetry) | safety + operator agency + M081 R13670 |

## Requirements (R13671-R13910)

| req | name | source |
|---|---|---|
| R13671 | L1 layer — schema/lint tests run in pure CI without virtualization | F06836 + macro-arc 235 |
| R13672 | L1 layer — profile YAML validated against `schemas/profile.schema.yaml` | F06837 |
| R13673 | L1 layer — whitelabel YAML validated against `schemas/whitelabel.schema.yaml` | F06838 + M081 |
| R13674 | L1 layer — markdown linted via markdownlint-cli2 with project rules | F06839 |
| R13675 | L1 layer — decisions log linted: one entry per decision, monotonic timestamps | F06840 |
| R13676 | L1 layer — SDD index consistency: every SDD in index AND every index row corresponds to an SDD | F06841 |
| R13677 | L1 layer — exit codes 0/1/2/3 per F06842 | F06842 |
| R13678 | L1 layer — every artifact (YAML / SDD / decisions row) emits ≥1 assertion | F06843 |
| R13679 | L1 layer — runs in CI as pre-merge required gate (no merge without L1 green) | F06844 |
| R13680 | L1 layer — runtime budget p95 ≤ 60 s on standard CI runner | F06845 |
| R13681 | L1 layer — flake = blocker (no retry; assertion bug) | F06899 |
| R13682 | L2 layer — every build script has ≥1 L2 unit test | F06850 |
| R13683 | L2 layer — mocked filesystem via overlayfs-backed virtual root | F06847 |
| R13684 | L2 layer — mocked apt records `apt-get install` calls without network access | F06848 |
| R13685 | L2 layer — mocked dpkg records `dpkg -i` calls without actual installation | F06849 |
| R13686 | L2 layer — runtime budget p95 ≤ 120 s on standard CI runner | F06851 |
| R13687 | L2 layer — flake = 1 retry on transient mock failure | F06900 + F06852 |
| R13688 | L3 layer — stage acceptance tests per lifecycle stage (pre-install, during-install, post-first-boot) | F06853 |
| R13689 | L3 layer — chroot driver runs package-level assertions | F06854 |
| R13690 | L3 layer — chroot assertion form: "package X installed" + "file Y present with content Z" | F06855 |
| R13691 | L3 layer — nspawn driver runs service-startup assertions | F06856 |
| R13692 | L3 layer — nspawn assertion form: "unit U active" + "convergence within Δt" | F06857 |
| R13693 | L3 layer — pre-install invariant: substrate readiness verified | F06858 |
| R13694 | L3 layer — during-install invariant: package set applied + chroot integrity | F06859 |
| R13695 | L3 layer — post-install-first-boot invariant: hostname matches profile | F06860 |
| R13696 | L3 layer — invariant: whitelabel surfaces match whitelabel profile (M081 R13564 binding) | F06861 + M081 R13564 |
| R13697 | L3 layer — invariant: ZFS pool present and healthy (M068 binding) | F06862 + M068 |
| R13698 | L3 layer — invariant: expected systemd units active (selfdef MS046 friction-audit binding) | F06863 + selfdef MS046 |
| R13699 | L3 layer — invariant: selfdef-perimeter.yaml TracingPolicy loaded (MS047 binding) | F06864 + selfdef MS047 |
| R13700 | L3 layer — runtime budget p95 ≤ 600 s on standard CI runner | F06865 |
| R13701 | L3 layer — runs on merge to main OR via label trigger | F06866 |
| R13702 | L3 layer — flake = 2 retries; 3 consecutive fails = block release | F06901 |
| R13703 | L4 layer — full image built and booted in QEMU | F06867 |
| R13704 | L4 layer — QEMU system supports UEFI boot mode | F06868 |
| R13705 | L4 layer — QEMU system supports secure-boot testing | F06869 |
| R13706 | L4 layer — QEMU system supports PCIe passthrough emulation (limited) | F06870 |
| R13707 | L4 layer — qemu-user supports cross-arch validation | F06871 |
| R13708 | L4 layer — smoke tests inside booted system: ssh reachable + selfdef perimeter loaded + ZFS healthy | F06872 |
| R13709 | L4 layer — boot assertion: GRUB menu entry visible | F06873 |
| R13710 | L4 layer — boot assertion: kernel cmdline matches profile (znver5 + vfio-pci.ids from sain-01 §4.3) | F06874 |
| R13711 | L4 layer — boot assertion: initramfs loads (no kernel panic, no rescue shell) | F06875 |
| R13712 | L4 layer — boot assertion: systemd reaches multi-user.target within budget | F06876 |
| R13713 | L4 layer — runtime budget p95 ≤ 1800 s on standard CI runner | F06877 |
| R13714 | L4 layer — runs on merge to main OR via label trigger | F06878 |
| R13715 | L4 layer — flake = 2 retries with bisect-on-retry-fail | F06902 |
| R13716 | L5 layer — hardware-conformance gated on matching hardware presence | F06879 |
| R13717 | L5 layer — SAIN-01 detector: ProArt X870E-Creator + znver5 + Marvell 10GbE + Intel 2.5GbE + RTX 3090 ×2 | F06880 + sain-01 §1 |
| R13718 | L5 layer — runs only when hw detected; skipped with reason logged when absent | F06881 |
| R13719 | L5 layer — VFIO passthrough verification: nvidia-smi inside guest sees the GPU | F06882 + sain-01 §4.3 |
| R13720 | L5 layer — AVX-512 verification: VPDPBUSD instruction available + cycle-accurate (M074 binding) | F06883 + M074 |
| R13721 | L5 layer — ZFS production-mode verification: tank pool with operator-spec datasets (M068 binding) | F06884 + M068 |
| R13722 | L5 layer — friction-audit gate verification: PCIe x8/x8 lanes confirmed (selfdef MS046 R10814 binding) | F06885 + selfdef MS046 |
| R13723 | L5 layer — perimeter gate verification: unauthorized binary Sigkill'd (selfdef MS047 R11071 binding) | F06886 + selfdef MS047 |
| R13724 | L5 layer — runtime budget p95 ≤ 3600 s on operator hardware | F06887 |
| R13725 | L5 layer — operator-triggered only (never automatic; never in CI without operator label) | F06888 + F06896 |
| R13726 | L5 layer — flake = operator decision (manual replay) | F06903 |
| R13727 | Test discovery — recursive walker under `tests/<layer>/<topic>/` | F06889 |
| R13728 | Test discovery — naming convention `test_<topic>_<assertion>.<ext>` (case-sensitive) | F06890 |
| R13729 | Test discovery — every test declares its layer via filename prefix OR directory ancestor | F06891 |
| R13730 | Test discovery — `sovereign test list [--layer N]` returns alphabetically-sorted list | F06892 + F06937 |
| R13731 | CI workflow — file `.github/workflows/test.yml` ~400 LOC | F06897 |
| R13732 | CI workflow — schema+lint on every PR (required gate) | F06893 |
| R13733 | CI workflow — chroot/nspawn on merge to main | F06894 |
| R13734 | CI workflow — qemu on merge to main + label-trigger PRs | F06895 |
| R13735 | CI workflow — L5 hardware-conformance NEVER in CI (operator-local only) | F06896 + R13725 |
| R13736 | CI workflow — separate `test-hardware.yml` for L5 (label-triggered + operator-local) | F06898 |
| R13737 | tests/INDEX.md — auto-regenerated on every `sovereign test run` invocation | F06904 |
| R13738 | tests/INDEX.md — sortable by layer, topic, last-pass-date | F06905 |
| R13739 | tests/INDEX.md — committed via signed commit (selfdef MS041 binding) | cross-ref selfdef MS041 |
| R13740 | tests/README.md — operator-onboarding doc: how to run a layer, how to add a test, how to investigate flakes | F06906 |
| R13741 | Scaffold deliverable — `tests/schema/` directory exists with ≥1 test per schema | F06907 |
| R13742 | Scaffold deliverable — `tests/lint/` directory exists with markdown + decisions + SDD linters wired | F06908 |
| R13743 | Scaffold deliverable — `tests/chroot/scaffold.sh` substrate-aware (calls into PR-4-decided tooling) | F06909 + M064 |
| R13744 | Scaffold deliverable — `tests/nspawn/scaffold.sh` skeleton boots a minimal nspawn machine | F06910 |
| R13745 | Scaffold deliverable — `tests/qemu/scaffold.sh` skeleton with stubbed boot test of minimal image | F06911 |
| R13746 | Scaffold deliverable — `.github/workflows/test.yml` wired to schema+lint on PR | F06912 + R13732 |
| R13747 | Scaffold deliverable — first passing tests on profile YAMLs + whitelabel YAMLs + schemas | F06913 + macro-arc 262 |
| R13748 | Scaffold deliverable — `docs/sdd/008-test-harness.md` ~800 LOC (PR 9) | F06914 |
| R13749 | Scaffold deliverable — `docs/sdd/009-test-harness-bootstrap.md` ~400 LOC (PR 10) | F06915 |
| R13750 | Scaffold deliverable — `docs/sdd/010-stage-2-stub.md` placeholder for Stage 2 reservation | F06916 |
| R13751 | Scaffold deliverable — 009 SDD explicitly documents what is NOT delivered (no image; no build scripts) | F06917 |
| R13752 | Scaffold deliverable — total LOC ≈ 1200 ± 10% (PR 10 estimate) | F06918 + macro-arc 276 |
| R13753 | Scaffold deliverable — CI green on scaffold without any actual image artifact | F06919 |
| R13754 | Stage Gate 5 — operator reviews full 10-PR arc holistically before authorizing Stage 2 | F06920 + macro-arc 280 |
| R13755 | Stage Gate 5 — checkpoint 1: charter set (PR 1 merged) | F06921 + cross-ref M062 |
| R13756 | Stage Gate 5 — checkpoint 2: substrate chosen (PR 4 merged; M064 binding) | F06922 + M064 |
| R13757 | Stage Gate 5 — checkpoint 3: profile schema locked with ≥2 conformant instances (PR 6 merged) | F06923 + macro-arc 151–170 |
| R13758 | Stage Gate 5 — checkpoint 4: whitelabel mechanism specified (PR 8 merged; M081 binding) | F06924 + M081 |
| R13759 | Stage Gate 5 — checkpoint 5: hardware-free test harness operational (PRs 9+10 merged) | F06925 + R13731–R13753 |
| R13760 | Stage Gate 5 — Stage 2 (actual build scripts) authorized ONLY after this gate | F06926 + macro-arc 282 |
| R13761 | Stage Gate 5 — gate output recorded in `docs/decisions/sg5-foundation-complete-<YYYY-MM-DD>.md` | F06927 |
| R13762 | Stage Gate 5 — verdict mirrored via MS007 to selfdef MS043 TUI authority panel | F06928 + cross-ref MS007 + selfdef MS043 |
| R13763 | Stage Gate 5 — operator may rescind gate verdict if foundation regresses | F06929 + operator agency |
| R13764 | Stage Gate 5 — rescission recorded as new SG5 entry (not in-place edit) | R13763 + cross-ref M065 |
| R13765 | Stage Gate 5 — operator-signed manifest required for verdict + rescission (MS003 binding) | cross-ref selfdef MS003 + F06927 |
| R13766 | Cockpit binding — M060 dashboard panel "Test Harness" exists | F06930 + M060 |
| R13767 | Cockpit panel — rows per layer L1..L5 with verdict + last-run timestamp | F06931 |
| R13768 | Cockpit panel — flake count + last-flake timestamp visible | F06932 |
| R13769 | Cockpit panel — READ-ONLY (no harness mutation from cockpit) | F06933 + safety |
| R13770 | Cockpit panel — operator triggers L4/L5 from CLI only (not cockpit) | F06934 + safety |
| R13771 | Cockpit panel — WCAG 2.1 AA contrast 4.5:1 (cross-ref selfdef MS043 R10175) | UX + cross-ref selfdef MS043 |
| R13772 | Cockpit panel — typed mirror crate `sovereign-cockpit-test-harness-mirror` (MS007 binding) | cross-ref MS007 + sovereign-os M060 |
| R13773 | Cockpit panel — TTL freshness ≤ 1000 ms (consistent with selfdef MS046 R10971 convention) | cross-ref selfdef MS046 |
| R13774 | CLI — `sovereign test run --layer <N>` runs layer N tests | F06935 |
| R13775 | CLI — `sovereign test run --topic <name>` runs all tests for a topic | F06936 |
| R13776 | CLI — `sovereign test list [--layer N]` lists discovered tests sorted | F06937 + R13730 |
| R13777 | CLI — `sovereign test status` shows last-run verdict per layer | F06938 |
| R13778 | CLI — `sovereign test report --since <duration>` shows pass/fail history | F06939 |
| R13779 | CLI — `sovereign test bundle` produces operator-portable test-evidence bundle | F06940 |
| R13780 | CLI — `--json` flag returns structured output | F06941 + cross-ref selfdef MS043 R10131 |
| R13781 | CLI — startup p95 ≤ 50 ms | F06942 + cross-ref selfdef MS043 R10137 |
| R13782 | CLI — operator-signed extension manifest required for L4/L5 triggers (selfdef MS003 binding) | safety + cross-ref selfdef MS003 |
| R13783 | Per-stage invariants — pre-install: substrate readiness verified before chroot | F06858 + macro-arc 245 |
| R13784 | Per-stage invariants — during-install: package set applied + chroot integrity preserved | F06859 + macro-arc 245 |
| R13785 | Per-stage invariants — post-first-boot: hostname matches profile + ZFS pool present + perimeter loaded + friction-audit pass | F06860–F06864 + macro-arc 246 |
| R13786 | Per-stage invariants — invariant assertion failure surfaces in M060 cockpit panel + selfdef MS027 stream | cross-ref selfdef MS027 + M060 |
| R13787 | Per-stage invariants — invariant text matches the exact form documented in `docs/sdd/008-test-harness.md` §invariants | F06914 + arch |
| R13788 | Virtualization stack — chroot is fastest (package-level assertions) | F06854 + macro-arc 241 |
| R13789 | Virtualization stack — systemd-nspawn (service-startup assertions) | F06856 + macro-arc 242 |
| R13790 | Virtualization stack — QEMU system (boot + initramfs + GRUB + cmdline; UEFI + secure-boot; PCIe passthrough emulation limited) | F06868–F06870 + macro-arc 243 |
| R13791 | Virtualization stack — qemu-user (cross-arch validation, non-amd64) | F06871 + macro-arc 244 |
| R13792 | Virtualization stack — operator can list available drivers via `sovereign test drivers` | UX + R13730 |
| R13793 | Flake policy — flake count tracked per (test, layer, day) | F06899–F06903 |
| R13794 | Flake policy — flake count > 3 per (test, layer, week) → ESCALATE to operator review | F06901 + ops |
| R13795 | Flake policy — flake events emit OCSF Audit 1003 (cross-ref selfdef MS026) | F06954 + cross-ref selfdef MS026 |
| R13796 | Flake policy — flake events recorded in tests/INDEX.md (last-flake column) | F06905 + R13738 |
| R13797 | Flake policy — operator can quarantine a flaky test via `sovereign test quarantine <id>` (label-skipped in CI) | UX + F06937 |
| R13798 | Flake policy — quarantined test triggers MEDIUM-severity cockpit banner | F06797 + M060 |
| R13799 | Cross-cutting — harness coverage reported in M060 main dashboard top-row | F06947 + M060 |
| R13800 | Cross-cutting — harness verdict surfaces in M072 master-bootstrap checklist | F06948 + cross-ref M072 |
| R13801 | Cross-cutting — harness changes recorded in selfdef MS027 observability stream (read-only) | F06949 + cross-ref selfdef MS027 |
| R13802 | Cross-cutting — harness participates in selfdef MS009 audit-cycle review | F06950 + cross-ref selfdef MS009 |
| R13803 | Cross-cutting — harness validates selfdef MS046 friction-audit before claiming PASS | F06951 + selfdef MS046 |
| R13804 | Cross-cutting — harness validates selfdef MS047 perimeter before claiming PASS | F06952 + selfdef MS047 |
| R13805 | Cross-cutting — harness validates whitelabel rendering (M081 R13564 binding) | F06953 + M081 |
| R13806 | Cross-cutting — harness verdicts NEVER leave local node by default (no telemetry) | F06955 + safety + M081 R13670 |
| R13807 | Documentation — `docs/sdd/008-test-harness.md` ~800 LOC, lints clean | R13748 + F06914 + arch |
| R13808 | Documentation — `docs/sdd/009-test-harness-bootstrap.md` ~400 LOC, lints clean | R13749 + F06915 + arch |
| R13809 | Documentation — `docs/sdd/010-stage-2-stub.md` placeholder, ≤ 100 LOC (just reserves slot) | R13750 + F06916 |
| R13810 | Documentation — every section H2/H3-anchored for direct linking | arch + cross-ref M081 R13593 |
| R13811 | Documentation — info-hub second-brain page `wiki/test-harness/<topic>.md` per layer | cross-ref selfdef MS027 + arch |
| R13812 | Documentation — info-hub runbook `wiki/runbooks/test-harness-investigate-flake.md` | F06906 + ops |
| R13813 | Documentation — info-hub runbook `wiki/runbooks/test-harness-add-l3-test.md` | F06906 + ops |
| R13814 | Documentation — info-hub runbook `wiki/runbooks/test-harness-l5-hardware-procurement.md` | F06880 + ops |
| R13815 | Documentation — every operator-facing CLI subcommand has a `--help` synopsis matching SDD | UX + cross-ref M081 R13594 |
| R13816 | Sub-requirements — each R-row decomposes into ≥10 sub-requirements per SDD discipline | F06943 + operator standing |
| R13817 | Sub-requirements — sub-requirements documented in `docs/sdd/008-test-harness.md` SDD body | F06944 |
| R13818 | Sub-requirements — sub-requirements link to test fixture file paths | F06946 |
| R13819 | Sub-requirements — sub-requirements cross-reference sister milestones (M062-M068, M070-M072, M081, selfdef MS003/007/009/020/026/027/041/043/046/047) | arch |
| R13820 | Threat-model — adversary injecting a malicious test → schema validation rejects unknown-shape tests | arch + R13672–R13673 |
| R13821 | Threat-model — adversary modifying CI workflow → branch protection + signed-commit gate detects | safety + cross-ref selfdef MS041 |
| R13822 | Threat-model — adversary skipping L1 → required-gate enforcement on GitHub prevents merge | R13679 |
| R13823 | Threat-model — adversary disabling L5 hardware check → operator-only trigger prevents CI bypass | R13725 |
| R13824 | Threat-model — adversary forging test verdict → typed mirror schema validation rejects malformed verdict | cross-ref MS007 + R13772 |
| R13825 | Threat-model — adversary disabling friction-audit cross-check (R13803) → cockpit panel goes red immediately | R13803 + M060 |
| R13826 | Audit-cycle — harness participates in selfdef MS009 audit-cycle (cross-ref R13802) | R13802 |
| R13827 | Audit-cycle — every gate verdict (SG5 + per-layer) reviewed at audit-cycle cadence | cross-ref selfdef MS009 + R13754 |
| R13828 | Audit-cycle — broken cross-repo schema (selfdef ↔ sovereign-os mirror) detected by audit cycle | cross-ref selfdef MS009 + cross-ref MS007 |
| R13829 | Audit-cycle — substrate-base re-decision (M064 Q-016) triggers harness re-audit | cross-ref M064 + R13756 |
| R13830 | Audit-cycle — whitelabel mechanism re-spec (M081 schema bump) triggers harness re-audit | cross-ref M081 + R13758 |
| R13831 | Performance — total CI runtime (L1+L2) p95 ≤ 180 s wall-clock | R13680 + R13686 |
| R13832 | Performance — total CI runtime on merge (L1+L2+L3) p95 ≤ 780 s wall-clock | R13680 + R13686 + R13700 |
| R13833 | Performance — total CI runtime with L4 (label-triggered) p95 ≤ 2580 s wall-clock | + R13713 |
| R13834 | Performance — L5 operator-local runtime p95 ≤ 3600 s wall-clock | R13724 |
| R13835 | Performance — performance regression budget: ≥ 10% drift over 30-day window triggers selfdef MS027 alert | cross-ref selfdef MS027 + ops |
| R13836 | Operator agency — L4/L5 NEVER triggered by AI; operator-only via signed manifest | F06888 + R13725 + R13782 |
| R13837 | Operator agency — test additions/removals go through Code Review (no AI auto-merge) | safety + operator agency |
| R13838 | Operator agency — Stage Gate 5 verdict is OPERATOR DECISION (not AI synthesis) | R13754 + operator agency |
| R13839 | Operator agency — quarantine of a flaky test requires operator action (R13797) | R13797 + operator agency |
| R13840 | Operator agency — harness configuration changes (e.g. add a layer) recorded in MS041 commit-authority | cross-ref selfdef MS041 + ops |
| R13841 | Sovereign-OS / selfdef independence — sovereign-os harness M082 does NOT replace selfdef MS020 | project boundary + cross-ref selfdef MS020 |
| R13842 | Sovereign-OS / selfdef independence — each repo runs its own 5-layer pyramid | project boundary + R13841 |
| R13843 | Sovereign-OS / selfdef independence — cross-repo contract (typed mirrors) tested by BOTH harnesses | cross-ref MS007 + R13824 |
| R13844 | Sovereign-OS / selfdef independence — verdict from one harness does NOT imply verdict in the other | project boundary + R13841 |
| R13845 | Sovereign-OS / selfdef independence — SG5 (sovereign-os) and selfdef analogous gate are independent | macro-arc 280 + cross-ref selfdef macro-arc-equivalent |
| R13846 | Cross-repo mirror — typed mirror `sovereign-cockpit-test-harness-mirror` exports per-layer Verdict | R13772 + cross-ref MS007 |
| R13847 | Cross-repo mirror — Verdict struct: `layer: u8, status: enum, last_run_ts_ms, flake_count_24h, signer_kid` | R13772 + cross-ref MS007 |
| R13848 | Cross-repo mirror — read-only; selfdef MS043 TUI shows "Sovereign test harness" row (informational) | cross-ref selfdef MS043 + project boundary |
| R13849 | Cross-repo mirror — schema_version bump is breaking change → coordinated bump in both repos | cross-ref MS007 + cross-ref selfdef MS007 |
| R13850 | Cross-repo mirror — mismatch detected → cockpit panel goes degraded with stale-banner | cross-ref MS007 + R13772 |
| R13851 | UX — every operator-facing exit code documented in CLI `--help` output | UX + arch |
| R13852 | UX — failure diagnostic includes the assertion source file:line | UX + ops |
| R13853 | UX — failure diagnostic includes the actual vs expected value pair | UX + ops |
| R13854 | UX — failure diagnostic links to runbook for the failed layer | F06906 + R13812 |
| R13855 | UX — pretty-prints with WCAG-compliant colors AND `--no-color` opt-out | cross-ref selfdef MS043 R10185 |
| R13856 | UX — operator can re-run a failed test with `sovereign test rerun <id>` | UX + R13774 |
| R13857 | UX — `sovereign test status --watch` streams live verdict updates | UX + R13773 |
| R13858 | UX — cockpit panel surfaces operator-actionable diagnostic on tap (no buried logs) | F06930 + UX |
| R13859 | UX — operator can preview a test's source from CLI with `sovereign test show <id>` | UX + R13776 |
| R13860 | UX — accessibility — screen-reader-friendly CLI output (structured TTY with semantic markers) | UX + accessibility |
| R13861 | Schema evolution — test harness schema bump REQUIRES migration script | arch + cross-ref M081 R13631 |
| R13862 | Schema evolution — migration script tested under L1 | R13861 + F06832 |
| R13863 | Schema evolution — operator notified of pending migrations via M060 cockpit banner | cross-ref M060 + UX |
| R13864 | Schema evolution — old-version YAMLs loaded read-only until migrated | arch + cross-ref M081 R13634 |
| R13865 | Schema evolution — every schema version retains backward-compatible read for ≥ 2 major bumps | arch + cross-ref M081 R13635 |
| R13866 | Substrate dependency — substrate-switch (M064) invalidates pre-build harness assumptions → harness re-audit | cross-ref M064 + R13829 |
| R13867 | Substrate dependency — substrate-switch decision recorded in `docs/decisions/Q-016-substrate-base.md` | cross-ref M064 |
| R13868 | Substrate dependency — chroot driver substrate-aware (delegates to substrate tooling per PR 4) | F06909 + R13743 + M064 |
| R13869 | Atomicity — multi-layer parallel test execution uses ZFS clone (cross-ref M068) | arch + cross-ref M068 |
| R13870 | Atomicity — test apply failure auto-rollback via ZFS snapshot (M071 binding) | arch + cross-ref M071 |
| R13871 | Atomicity — operator sees rollback verdict in M060 cockpit | F06930 + cross-ref M071 |
| R13872 | Atomicity — partial-test state NEVER persisted to git (all-or-nothing) | arch + cross-ref M071 |
| R13873 | Documentation — second-brain (info-hub) `wiki/test-harness/INDEX.md` lists all topics | R13811 + arch |
| R13874 | Documentation — info-hub link from M060 cockpit panel diagnostics (operator one-click) | UX + R13854 |
| R13875 | Documentation — every R-row in M082 has a corresponding test fixture | F06946 + R13818 |
| R13876 | Documentation — second-brain test-harness pages auto-update on `sovereign test report` | cross-ref selfdef MS027 + R13778 |
| R13877 | Documentation — info-hub respects same "read-only knowledge layer" doctrine (knowledge = second-brain) | operator standing 2026-05-19 |
| R13878 | Audit-cycle — harness execution time tracked for performance regression detection (cross-ref M082 R13835) | R13835 + cross-ref selfdef MS027 |
| R13879 | Audit-cycle — quarantined-test count tracked over time | R13797 + cross-ref selfdef MS009 |
| R13880 | Audit-cycle — stale (>30 day) quarantine triggers operator review | R13839 + cross-ref selfdef MS009 |
| R13881 | Operator agency — every harness run produces a deterministic verdict (no flaky-by-design) | R13871 + R13793 + operator agency |
| R13882 | Operator agency — operator may add new layers (e.g. L6 chaos) via signed extension | safety + arch |
| R13883 | Operator agency — operator may rescind quarantine via signed action (R13797) | R13797 + R13839 |
| R13884 | Self-defending — harness verdict cannot be silently mutated (write-once + signed audit) | safety + cross-ref selfdef MS041 |
| R13885 | Self-defending — harness CANNOT mutate selfdef IPS state (read-only cross-repo binding) | project boundary + cross-ref MS007 |
| R13886 | Self-defending — test fixtures are signed (MS003 binding) to prevent injection | safety + cross-ref selfdef MS003 |
| R13887 | Self-defending — flake events that recur > 5x same test/week → automatic operator escalation | R13794 + ops |
| R13888 | Substrate independence — harness is substrate-agnostic at L1 (schema validation does not depend on substrate) | arch + R13743 |
| R13889 | Substrate independence — harness is substrate-aware at L3 (chroot driver delegates to substrate) | R13743 + R13868 |
| R13890 | Substrate independence — alt-substrate test-fixture path: `tests/<layer>/<substrate>/` | arch + R13727 |
| R13891 | Test fixture file integrity — every test fixture has SHA-256 in `tests/INDEX.md` | R13737 + safety |
| R13892 | Test fixture file integrity — fixture modification detected as L1 lint failure | R13674 + R13891 |
| R13893 | Test fixture file integrity — fixture modification gated through Code Review (no AI auto-modify) | safety + R13837 |
| R13894 | Test fixture file integrity — signed-commit gate per selfdef MS041 | cross-ref selfdef MS041 + R13838 |
| R13895 | Cross-cutting — every R-row in selfdef MS046 + MS047 has a sovereign-os harness L1-L5 assertion | cross-ref selfdef MS046 + MS047 + arch |
| R13896 | Cross-cutting — every R-row in M081 has a sovereign-os harness L1-L5 assertion | cross-ref M081 + arch |
| R13897 | Cross-cutting — assertion failure on cross-repo binding emits OCSF Detection 2008 (`cross_repo_drift`) | cross-ref selfdef MS026 + R13824 |
| R13898 | Cross-cutting — harness scaffold landing (PR 10 merge) gates `sovereign-os main` Stage 2 work | macro-arc 282 + R13760 |
| R13899 | Cross-cutting — Stage 2 (actual build scripts) is OUT OF SCOPE for this milestone | R13760 + macro-arc 282 |
| R13900 | Cross-cutting — Stage 2 ID range begins at M083+ (next milestone) | catalog discipline + R13899 |
| R13901 | Cross-cutting — every catalog change committed via signed commit (selfdef MS041 binding) | cross-ref selfdef MS041 + R13894 |
| R13902 | Knowledge integration — second-brain `wiki/` is READ-ONLY for AI; AI writes via SDD docs first | operator standing 2026-05-19 + R13811 |
| R13903 | Knowledge integration — info-hub second-brain `~/devops-solutions-information-hub/` is the operator's knowledge source | operator standing 2026-05-19 |
| R13904 | Knowledge integration — second-brain `wiki/` pages link back to SDD R-rows by id | R13818 + arch |
| R13905 | Knowledge integration — SDD R-rows take precedence over wiki when they disagree | R13902 + R13904 |
| R13906 | Order-of-execution — M082 (TDD harness) MUST be operational before any Stage 2 milestone | macro-arc 282 + R13760 |
| R13907 | Order-of-execution — selfdef MS046 + MS047 + M081 (this catalog round) precede Stage 2 by design | this catalog round + R13906 |
| R13908 | Order-of-execution — operator may impose alternate ordering via signed manifest | operator agency + R13760 |
| R13909 | Order-of-execution — milestone-dependency graph rendered in M060 cockpit panel | F06930 + M060 |
| R13910 | Order-of-execution — operator-facing dependency graph is the SOURCE OF TRUTH for ordering | R13909 + operator agency |

## Sub-requirements accounting

Per operator standing direction *"every of those requirements is in reality already quite specific and with at least 10 hard non-negotiable requirements each"*: each R-row above decomposes into ≥10 sub-requirements under SDD discipline. The sub-requirements live in:
- `docs/sdd/008-test-harness.md` (R-row L-binding for layers L1-L5)
- `docs/sdd/009-test-harness-bootstrap.md` (scaffold deliverable R-binding)
- `docs/sdd/010-stage-2-stub.md` (Stage 2 reservation slot)
- `tests/INDEX.md` + `tests/README.md` (test catalog + onboarding)
- `wiki/test-harness/<topic>.md` (per-topic operator pages)
- `wiki/runbooks/test-harness-{investigate-flake, add-l3-test, l5-hardware-procurement}.md` (operator runbooks)

This milestone catalogues the **top-level R-rows** that anchor the sub-requirement decomposition. Every R-row sourced from macro-arc dump §PR 9 + §PR 10 + §Stage Gate 5 verbatim, cross-referenced to prior sovereign-os milestones (M060 cockpit, M062 macro-arc, M064 substrate, M065 gates, M068 ZFS, M071 atomic, M072 bootstrap, M074 AVX, M081 whitelabel), or cross-referenced to selfdef sister milestones (MS003/MS007/MS009/MS020/MS026/MS027/MS041/MS043/MS046/MS047). No row invented; per operator direction.

## Cross-references

- **Source dump**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` §PR 9 lines 229–257 + §PR 10 lines 260–278 + §Stage Gate 5 lines 280–283
- **Companion**: M062 Macro-Arc 10-PR Foundation Scaffold (this milestone is PR 9 + PR 10 of the 10-PR arc — the FINAL two PRs)
- **Companion**: M081 Whitelabel Architecture (PR 8 — informs harness assertions per F06861 / R13696)
- **Companion**: M064 "Debian as Ark" + Q-016 substrate decision (PR 4 — informs harness driver per F06909 / R13743 / R13868)
- **Stage Gate**: M065 Five Stage Gates SG1-SG5 (SG5 = foundation-complete gate; this milestone closes SG5 prerequisites)
- **Cockpit dependency**: M060 Cockpit + 20+ dashboards + UX surface
- **Atomicity dependency**: M068 ZFS storage architecture + M071 Atomic State Transition Protocol
- **Bootstrap dependency**: M072 Master Bootstrap Verification Checklist
- **Hardware dependency**: M074 AVX-512 VNNI hardware fusion (L5 hardware-conformance VPDPBUSD verification per R13720)
- **Cross-repo bindings (selfdef)**: MS003 signing, MS007 typed-mirror, MS009 audit-cycle, MS020 L1-L5 sister harness, MS026 OCSF, MS027 observability, MS041 commit authority, MS043 IPS operator surface, MS046 friction-audit (R13698 / R13722), MS047 perimeter (R13699 / R13723)
- **Project boundary**: sovereign-os ONLY; selfdef IPS has its own MS020/MS045 harness milestones; cross-repo schema tested by BOTH harnesses independently (R13841–R13845)

## Schema

```text
schema_version: "1.0.0"
LayerVerdict.fields:
  - layer: u8 (1..=5)
  - status: enum { Pass, Fail(String), Skipped(String), Quarantined }
  - last_run_ts_ms: u64
  - flake_count_24h: u32
  - signer_kid: String  # cross-ref selfdef MS003
```

— End of M082.
