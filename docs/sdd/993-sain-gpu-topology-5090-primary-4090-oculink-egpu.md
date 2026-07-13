# SDD-993 — SAIN GPU topology: RTX PRO 6000 primary (main) + RTX 5090 internal secondary (~350 W) + RTX 4090 OcuLink eGPU

> Topology correction (2026-07-13): the **RTX PRO 6000 96 GB is the primary/main Oracle card** (installed). The **RTX 5090 32 GB** is the new **internal secondary** (~350 W). The **RTX 4090 24 GB** is the **OcuLink eGPU** (third card). All three are in the build; the two internal cards run **x8/x8** and **M.2_2 stays empty**. (The filename slug says "5090-primary" from an earlier misread — the content here is authoritative.)

> Status: active — reconcile landed (definitional anchor + the full SAIN/eGPU reconcile shipped on branch)
> Owner: operator-directed 2026-07-13 (hardware-change directive, verbatim below); agent-authored.
> Derivation: operator directive (new hardware). Definitional anchor + reconcile for the SAIN/eGPU arc.
> Mandate module: **E11.M993**.
> Number band: **950–999 (phase-1 audit / general session)** per SDD-100.
> Decision record: **D-021** (`docs/decisions.md`).

## Operator directive (verbatim — sacrosanct, 2026-07-13)

> "the rtx 4090 is going to become an eGPU connected via oculink via an oculink to m.2 card on the chipset remaining nvme slot and we will replace it with an rtx 5090 which we will also reduce the wattage to ~350 or so based on the right maths and need for performance. new card: TUF-RTX5090-O32G-GAMING."
>
> "the other change is smaller but still big, we are going to use Dspark from Deepseek."
>
> "this involve a lot of update in the documentation first and definition of the SAIN and the places that relates to GPU like the LM Orchestration page which already had an eGPU section prepared at at least one place."

Sequencing (operator, same session): **SAIN / eGPU first; DSpark second.** This SDD is the SAIN/eGPU definitional anchor. The DSpark-from-DeepSeek adoption is a **separate follow-up** (its own SDD) — deliberately out of scope here.

## What changes (the SAIN-01 GPU topology)

**All three cards are in the build.** The RTX PRO 6000 is the **main / primary** card (Oracle Core) and stays exactly where it was. The change is: the RTX 4090 **moves out** of its internal slot to become an **OcuLink eGPU**, and the **new RTX 5090** takes the 4090's vacated internal x8 secondary slot.

| Card | Role | Bus | Power |
|---|---|---|---|
| **RTX PRO 6000 Blackwell 96 GB** | **PRIMARY — Oracle Core (main card)** | internal, PCIEX16_1 **x8** | ~600 W |
| **RTX 5090 32 GB (TUF-RTX5090-O32G-GAMING)** | **secondary** (new card; Blackwell GB202, 512-bit) | internal, PCIEX16_2 **x8** | **~350 W** (power-limited from 575 W stock) |
| **RTX 4090 24 GB** | **secondary / eGPU** (Logic Engine / speculative-decoding draft) | **OcuLink-to-M.2 on a chipset M.2 slot, PCIe 4.0 x4** | ~350 W |

One primary (PRO 6000) + **two secondaries** (the 5090 internal + the 4090 eGPU). No future/missing card — everything is installed.

| | Before this change | After |
|---|---|---|
| Internal card 1 | RTX PRO 6000 (x8, Oracle) | RTX PRO 6000 (x8, Oracle) — **unchanged** |
| Internal card 2 | RTX 4090 (x8, VFIO) | **RTX 5090** (x8, secondary) — the 4090 left this slot |
| eGPU | — | **RTX 4090** on OcuLink (chipset M.2, PCIe 4.0 x4) |
| PCIe split | x8 / x8 (two internal) | **x8 / x8 (two internal) — still applies** |
| M.2_2 | empty (protects PCIEX16_2) | **empty — still required** (it shares lanes with PCIEX16_2 where the 5090 sits) |

**The "M.2_2 must remain empty" rule STANDS.** With two internal cards (PRO 6000 + 5090) the x8/x8 bifurcation is real, and M.2_2 shares lanes with PCIEX16_2 (the 5090's slot). The OcuLink-to-M.2 adapter for the 4090 goes on a **chipset M.2 slot** (the operator's "chipset remaining nvme slot") — **NOT** M.2_2.

## Researched facts (grounded, not invented)

- **RTX 5090 (TUF-RTX5090-O32G-GAMING)** — the secondary: 32 GB GDDR7, 512-bit, 28 Gbps; 21,760 CUDA cores; Blackwell GB202; PCIe 5.0; **stock TGP 575 W**. Same Blackwell FP4/NVFP4 family + 512-bit bus as the PRO 6000 primary — a capable second Blackwell card, not a downgrade. [ASUS techspec]
- **RTX PRO 6000 Blackwell 96 GB** — the primary/main Oracle Core: 96 GB GDDR7 / 512-bit / 1.8 TB/s / FP4 Tensor Cores / ~600 W. Unchanged by this directive; it remains the large-VRAM Oracle.
- **OcuLink-to-M.2 adapter (SFF-8612 host → SFF-8611)**: exposes a chipset M.2 M-key slot's **PCIe 4.0 x4** as an external OcuLink link — **64 Gbps ≈ 7.9 GB/s**, native PCIe, far above Thunderbolt's effective eGPU bandwidth. Adequate for **inference** (weights VRAM-resident; host↔device traffic is model-load + token I/O); **not** suited to training or cross-link tensor-parallel.

## The ~350 W power limit — the maths (applies to the RTX 5090 secondary)

The 5090's stock TGP is **575 W**. Target ≈ **350 W → 350 / 575 ≈ 61 % of stock.** Blackwell's voltage/frequency curve is steep near stock: the top ~40 % of the power budget buys only single-digit-percent extra throughput, so a limit near ~60 % sits close to the efficiency knee — it keeps the large majority of inference throughput while cutting heat, noise, and sustained draw. It also fits the whole-box budget: PRO 6000 ~600 W (primary) + 5090 ~350 W + 4090 ~350 W + Ryzen 9 9900X ~120 W under the 1600 W-minimum PSU. Applied with `nvidia-smi -pl 350` (persisted via the runtime profile); tunable per measured perf/thermals per the operator's "based on the right maths and need for performance." This extends the operator's prior "the RTX 4090 which should be sli[ght]ly reduce[d]" power-limit discipline to the new 5090.

## The PRO 6000 is the main card (not future)

Earlier spec text framed the PRO 6000 as *future* ("your **future** NVIDIA RTX PRO 6000 Blackwell with your **current** RTX 4090"). That is **superseded**: the PRO 6000 **is installed and is the main/primary Oracle Core.** The reconcile presents the real **three-card build** — PRO 6000 (primary, internal x8) + RTX 5090 (secondary, internal x8) + RTX 4090 (secondary, OcuLink eGPU) — all present.

## VRAM + role implications (for the reconcile)

- The Oracle Core stays on the **PRO 6000 (96 GB)** — the large-VRAM primary, unchanged. The **RTX 5090 (32 GB, Blackwell)** is the new internal secondary (a second Oracle-capable / Logic card); the **RTX 4090 (24 GB)** is the OcuLink eGPU (Logic / speculative-decoding draft).
- Both internal cards are Blackwell (PRO 6000 GB202GL + 5090 GB202) → FP4/NVFP4 native paths run on both.
- The fleet predicate `any_gpu_vram_at_least_80gib` (predicate-coverage dashboard) is satisfied by the 96 GB PRO 6000 primary — no change needed to the threshold.

## VFIO / IOMMU note

The 4090 was VFIO-isolated as an internal card. On the OcuLink eGPU it sits on its own downstream PCIe path — still `vfio-pci`-isolable (arguably a **cleaner** IOMMU-group boundary by construction). The bind script + `vfio-pci.ids` list + IOMMU-group wording are reconciled in lockstep with their pinning lints (below). The two internal cards (PRO 6000 + 5090) keep their x8/x8 IOMMU groups.

## VFIO is OPT-IN — bare-metal is the default (operator directive 2026-07-13)

Operator, verbatim: *"also what is this VFIO GPU thing … I like the idea of a sandbox but at the same time it should be an option, a config I can opt in or not … I want to be able to work locally on my workstation most of the time, not in a VM by default."*

The reconcile flips the **default** from "4090 VFIO-isolated" to **host-resident / bare-metal**: the 4090's declared `role` is `secondary` (directly usable by the host inference stack — Logic Engine / speculative-decoding draft, worked-on locally). The VFIO-isolated sandbox (§17 dual-GPU SRP perimeter) is an **opt-in** mode — set `role: vfio` in the profile and `vfio-bind-4090.sh` binds it at boot; with the default role the bind hook is a clean no-op. **The isolation machinery is preserved, not removed** — this is a default-flip, and it is consistent with the operator's own M040 E0384 "performance profile: 4090 on host" verbatim.

## Scope of THIS SDD — reconcile SHIPPED

This SDD started as a definitional anchor and now carries the **full SAIN/eGPU reconcile** (below). It **states** the new topology + researched facts + power maths + VFIO-opt-in default, and it **drove** the canonical-surface edits — each surface updated in lockstep with its pinning lint (reframed, never silently broken). The DSpark-from-DeepSeek adoption remains a **separate follow-up SDD** (PR 2) per operator sequencing.

## Reconcile roadmap — status (the "lot of documentation update")

Each a coherent surface-group + its lockstep lint(s). ✅ = landed this session.

1. ✅ **Canonical machine-readable** — `profiles/sain-01.yaml` GPU block (PRO 6000 `role: primary` + RTX 5090 `role: secondary` + RTX 4090 `role: egpu`; power; `m2_2_empty` blocker RESTORED; VFIO opt-in) + `schemas/profile.schema.yaml` (`egpu` role) + `crates/sovereign-pcie-topology` + `sovereign-pcie-advisor` (x8/x8 layout, M.2_2 empty) + `friction-audit-spec.sh`, with `test_sain01_profile_verbatim.py`, `test_profile_schema_conformance.py` reframed in lockstep.
2. ✅ **Operator-readable spec** — `docs/src/sain-01-master-spec.md` §1 hardware table (3 cards: PRO 6000 primary + 5090 secondary + 4090 eGPU) + PCIe-topology § (x8/x8, M.2_2 empty); `docs/src/profiles/sain-01.md` (hardware table, inference stack, first-boot + recovery); the 4 pinning lints green.
3. ✅ **LM Orchestration panel** — the D-21 grid (`d21-lm-orchestration-cockpit.md`, `lm-orchestration-api.py`, `webapp/d-21-lm-orchestration/index.html`): the three installed cards — GPU0 = PRO 6000 (Oracle primary), GPU1 = RTX 5090 (secondary), Ext-GPU = RTX 4090 (OcuLink eGPU); `test_d21_lm_orchestration_webapp_contract.py` green.
4. ✅ **eGPU milestone reframe** — `backlog/milestones/M040-*.md`: additive OcuLink-vs-USB4 reconcile note (verbatim rows untouched); `test_m040_hyper_features.py` green.
5. ✅ **Hardware/inference config reconciles** — `config/hardware/m003-hardware-topology.yaml` + `config/inference/m077-nvfp4-pipeline.yaml`: additive `sdd_993_reconcile` blocks (verbatim inventory untouched; both internal cards are Blackwell FP4; the Oracle stays on the PRO 6000); `profiles/runtime/*.yaml` + `trinity-runtime-profiles.md`.
6. ✅ **Model catalog + placement** — `models/catalog.yaml` (regenerates `model-catalog.md`): the Nemotron-NVFP4 note names the PRO 6000 primary Oracle + the 5090 secondary + the 4090 eGPU (all Blackwell FP4).
7. ⏳ **Install / lifecycle runbooks** — remaining prose (`ops/install.md`, `bootstrap-phases.md`, `lifecycle/post-install.md`, `m060-deployment-guide.md`) referencing the vfio-bind flow — low blast-radius, no behaviour change.
8. ✅ **Observability dashboards** — the `any_gpu_vram_at_least_80gib` predicate is SATISFIED by the 96 GB PRO 6000 primary; comment updated. The `selfdef_scheduler_gpu3090_*` metric names are deliberately preserved for the prometheus contract (labels already read "4090").
9. ✅ **Decisions + mandate** — `docs/decisions.md` **D-021**; INDEX row 993 corrected; mandate row E11.M993 registers the directive verbatim.
10. ⏳ **DSpark-from-DeepSeek** — separate SDD (PR 2): DSpark is DeepSeek's open-source speculative-decoding framework (Markov-head draft + semi-autoregressive chunking; "DeepSpec"); slot it into the Logic Engine speculative-decoding role (draft on the 4090 eGPU, verify on the PRO 6000 / 5090). Deferred per operator sequencing.

## Non-goals

- Editing any pinned hardware surface in THIS SDD (that is the reconcile arc, each with lockstep lints).
- The DSpark/DeepSeek adoption (its own SDD).
- Deleting the RTX PRO 6000 future path (preserved additively).
- Choosing final numeric power limits / PCI IDs before the operator confirms the physical build (documented as the intended target; tunable).

## Cross-references

- `docs/src/sain-01-master-spec.md` · `docs/src/profiles/sain-01.md` · `profiles/sain-01.yaml` — the SAIN definition (reconcile targets)
- `docs/operator/d21-lm-orchestration-cockpit.md` + `docs/sdd/111-d21-d22-full-layout.md` — the prepared "Ext-GPU" eGPU slot
- `backlog/milestones/M040-hyper-features-mig-fp4-vfio-zfs-commit-gate.md` — the eGPU/VFIO milestone (USB4 → OcuLink reframe)
- `docs/src/verbatim-surface.md` — operator's "future PRO 6000 / current 4090" framing (now extended by the 5090)
- ASUS TUF-RTX5090-O32G-GAMING techspec (575 W TGP, 32 GB GDDR7); OcuLink-M.2 = PCIe 4.0 x4 / 64 Gbps
