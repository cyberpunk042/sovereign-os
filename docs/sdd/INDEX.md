# SDD index

Reserved slots for the foundation phase (PRs 1–10) per the Plan-agent
macro-arc (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`).
Numbering is three-digit zero-padded, never recycled.

| # | Title | Status | PR | Notes |
|---|---|---|---|---|
| 000 | Project charter | accepted | PR 1 | This repo's foundational charter — mission, SDD+TDD, SFIF, IaC bar, Debian-as-Ark, non-goals. |
| 001 | Cross-repo boundaries | accepted | PR 2 | Cross-repo reference contract (sovereign-os ↔ selfdef ↔ info-hub). Q-011 partial resolution; final closure at CI-guard PR. |
| 002 | Documentation pipeline | accepted | PR 3 | mdbook + MCP config template + CI publishing. Q-A..Q-D open (deploy cadence; missing-page handling; Pages provider; sovereign-os MCP stub). |
| 003 | Substrate survey | review | PR 4 | Resolves Q-001 + Q-016 at Gate 2. Primary recommendation: mkosi-on-Debian-13. Alternatives A (live-build), B (rpm-ostree/Silverblue), C (NixOS). Q4-A..Q4-E open for Gate 2 closure. |
| 004 | Profile schema | review | PR 5 | Resolves Q-002 (in part) at Gate 3. Single-parent inheritance + composition via mixins; YAML; substrate-agnostic. Q5-A..Q5-E open. |
| 005 | Initial profile stubs (sain-01 + old-workstation) | review | PR 6 | Validates schema against real profiles. 2 stubs + 3 mixins + INDEX + validation harness placeholder. Q6-A..Q6-D open. |
| 006 | Debian (or successor) surface audit | review | PR 7 | Whitelabel target inventory. ~50 surfaces / 10 sections / legal floor explicit. Q7-A..Q7-E open. |
| 007 | Whitelabel mechanism | review | PR 8 | Resolves Q-004 (legal scope) at Gate 4; Q-003 may stay open. 7-strategy taxonomy; schema + default whitelabel placeholder. Q8-A..Q8-E open. |
| 008 | TDD harness specification | review | PR 9 | 5-layer pyramid; CI for Layer 1; substantive Layer 3/4/5 added alongside script bodies at Stage 2+. Q9-A..Q9-E open. |
| 009 | TDD harness bootstrap | accepted | PR 10 | Layer 1 schema + lint pytest + shellcheck CI shipped; chroot/nspawn/qemu scaffolds present; substantive Layer 3+ at Stage 2+. |
| 010 | Stage-2 stub | scoping | post-Gate-5 | Build pipeline + hooks + render engine + sovereign-osctl already on main. Subsequent Stage-2 rounds deferred items documented. |
| 011 | Inference backend stack | review | post-Gate-5 | Q-017 resolution path: direct-stack architecture (vLLM + bitnet.cpp + llama.cpp, no unifying abstraction); scripts/inference/ scaffold shipped (router + 3 backends + 3 start scripts). Q11-A..Q11-E open. |
| 012 | Brand identity placeholder strategy | review | post-Gate-5 | Q-003 deferred-with-criteria: placeholder contract specified, legal-floor contract restated, promotion criteria + mechanism for when a real brand lands. CI gates placeholder-leak detection. |
| 013 | Installer experience | review | post-Gate-5 | Q-008 resolution: image-only (mkosi-built bootable image) + cloud-init/preseed pre-supplied answers. No d-i / Calamares / custom TUI. CI gate `test_install_configs.sh` (24 assertions). |
| 014 | Decommission testing scope | review | post-Gate-5 | Q-014 resolution: test gates (require_root + SOVEREIGN_OS_CONFIRM_DESTROY env + interactive confirm + idempotency) not destruction. CI gate `test_decommission_gates.sh` (12 assertions). |
| 015 | Secure-boot posture | review | post-Gate-5 | Q-006 resolution: 3-level posture (none/shim/signed) declared per profile; operator-supplied keys (never in-repo); preflight-tpm + 08-image-sign as the only gates. TPM2 PCR binding partial (PCR-7 + PCR-11 prescribed; disk-encryption binding deferred). Q15-A..Q15-C open. |
| 016 | Observability bindings | review | post-Gate-5 | Q-013 resolution: 3-layer stack (A: JSONL logs, B: Prometheus textfile collector contract, C: sovereign-osctl + Grafana JSON templates). Layer A shipped + gated; Layer B contract locked + emission deferred; Layer C CLI gated. Local-default sovereignty; no black-box dispatchers. Q16-A..Q16-D open. |
| 017 | ZFS root layout | review | post-Gate-5 | Q-005 resolution: `tank` single pool, raid0 across dual NVMe-PCIe-5, three tiered datasets (`models` 1M/lz4, `context` 16k/zstd-9/copies=2/sync=always, `agents` 128k/zstd-3). Mount base `/mnt/vault`. Operator-acknowledged no device-level redundancy; logical redundancy via copies=2 on irreducible state-fabric. Only sain-01 uses zfs-tiered; ext4 profiles SKIP cleanly via gates. |
| 018 | Kernel choice + tuning | review | post-Gate-5 | Q-007 resolution: dual strategy. sain-01 = kernel.org-stable ≥6.12 custom-tuned (-march=znver5, AVX-512, ZFS/VFIO/BPF-LSM built in). old-workstation + minimal = substrate-default (Debian linux-image-amd64). Build pipeline steps 02-04 only run for custom-tuned profiles. Q18-A..Q18-C open. |
| 019 | Reproducibility target | review | post-Gate-5 | Q-015 resolution: strong build-reproducibility (same inputs → same bytes for mkosi image + kernel .deb + whitelabel render + substrate emit, given pinned SOURCE_DATE_EPOCH + apt snapshot + kernel tag + compiler version); NOT bit-identical for operator-key-signed artifacts. Implementation gaps tracked (apt-snapshot enforcement, SOURCE_DATE_EPOCH in step 04, in-toto build provenance — Stage 2+). |
| 020 | CI infrastructure | review | post-Gate-5 | Q-010 resolution: GitHub Actions only for foundation phase. ~19 L3 + Layer 1 + Layer 2 + shellcheck on ubuntu-latest. No self-hosted, no CI-resident keys (SDD-015). Layer 4 (QEMU) + Layer 5 (hardware) deferred to operator-driven runs. Q10-A..Q10-C open. |
| 021 | Distro-base | review | post-Gate-5 | Q-016 resolution: Debian 13 (trixie) as the foundation-phase distro-base. SDD-003 implicitly chose this; SDD-021 makes it explicit + specifies the criteria for reconsideration (operator-driven). "Debian as Ark" framing honored — we depart from Debian visually + via Tetragon perimeter + whitelabel + custom kernel for sain-01, but the Ark stays Debian. |

## Slots reserved for Stage 2 onwards (preview, non-binding)

Subsequent SDDs (011+) cover Stage 2 build scripts, lifecycle management,
first-login assistant, inference-backend stack selection (Q-017), etc.
Numbering continues monotonically; specific titles land when their PR
opens.

## How to add an SDD

1. Pick the next free three-digit number.
2. Create `docs/sdd/NNN-<short-slug>.md`.
3. Open with the canonical status block:
   ```
   > Status: <draft | review | accepted | implemented | abandoned>
   > Owner: <name or team>
   > Last updated: <YYYY-MM-DD>
   > Closes findings: F-NNNN-MMM, ...   (or "none")
   > Derived from: <upstream artifacts>
   ```
4. Sections: Mission · Problem · Required coverage · Goals · Non-goals ·
   Open questions (Q-X rows) · Way forward · Cross-references.
5. Update this INDEX with the new row.
6. When the SDD's open questions resolve, append `D-NNN` entries to
   `docs/decisions.md` and annotate the SDD's `Q-X` rows in place with
   `**answered (D-NNN, YYYY-MM-DD)**`.
