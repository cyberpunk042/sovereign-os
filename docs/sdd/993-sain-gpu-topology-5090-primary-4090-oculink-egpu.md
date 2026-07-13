# SDD-993 — SAIN GPU topology change: RTX 5090 internal primary (~350 W) + RTX 4090 as OcuLink eGPU

> Status: draft
> Owner: operator-directed 2026-07-13 (hardware-change directive, verbatim below); agent-authored.
> Derivation: operator directive (new hardware). Definitional anchor for the reconcile arc.
> Mandate module: **E11.M993**.
> Number band: **950–999 (phase-1 audit / general session)** per SDD-100.

## Operator directive (verbatim — sacrosanct, 2026-07-13)

> "the rtx 4090 is going to become an eGPU connected via oculink via an oculink to m.2 card on the chipset remaining nvme slot and we will replace it with an rtx 5090 which we will also reduce the wattage to ~350 or so based on the right maths and need for performance. new card: TUF-RTX5090-O32G-GAMING."
>
> "the other change is smaller but still big, we are going to use Dspark from Deepseek."
>
> "this involve a lot of update in the documentation first and definition of the SAIN and the places that relates to GPU like the LM Orchestration page which already had an eGPU section prepared at at least one place."

Sequencing (operator, same session): **SAIN / eGPU first; DSpark second.** This SDD is the SAIN/eGPU definitional anchor. The DSpark-from-DeepSeek adoption is a **separate follow-up** (its own SDD) — deliberately out of scope here.

## What changes (the new SAIN-01 GPU topology)

| | Old canonical spec | New (this SDD) |
|---|---|---|
| **Internal primary GPU** | RTX PRO 6000 Blackwell 96 GB (Slot 1, x8) — *future/aspirational per operator verbatim* | **RTX 5090 32 GB (TUF-RTX5090-O32G-GAMING), power-limited ~350 W** |
| **Second GPU** | RTX 4090 24 GB (Slot 2, x8, VFIO-isolated) | **RTX 4090 24 GB as an OcuLink eGPU** (external dock) |
| **Internal PCIe split** | x8 / x8 bifurcation across two internal cards | **single internal GPU → full x16** (no bifurcation) |
| **Chipset M.2 slot ("M.2_2")** | MUST remain empty (populating it dropped Slot 2 to x4) | **deliberately populated** with the OcuLink-to-M.2 adapter |
| **4090 link** | internal PCIe (x8) | **OcuLink SFF-8611 → PCIe 4.0 x4** (via the M.2 adapter) |

**The "M.2_2 must remain empty" invariant is RETIRED for this topology.** It existed solely to protect the two-internal-GPU x8/x8 split; with one internal GPU that constraint no longer applies, and the slot's new job is to carry the OcuLink link to the 4090.

## Researched facts (grounded, not invented)

- **RTX 5090 (TUF-RTX5090-O32G-GAMING)**: 32 GB GDDR7, 512-bit, 28 Gbps; 21,760 CUDA cores; Blackwell; PCIe 5.0 x16; **stock TGP 575 W** (1× 12V-2×6 / 12VHPWR). [ASUS techspec]
- **OcuLink-to-M.2 adapter (SFF-8612 host → SFF-8611)**: exposes the M.2 M-key slot's **PCIe 4.0 x4** as an external OcuLink link — **64 Gbps ≈ 7.9 GB/s**, native PCIe, far above Thunderbolt's effective eGPU bandwidth. Adequate for **inference** (weights resident in VRAM; host↔device traffic is model-load + token I/O, not per-layer streaming); **not** suited to training or cross-link tensor-parallel.

## The ~350 W power limit — the maths

Stock TGP is **575 W**. Target ≈ **350 W → 350 / 575 ≈ 61 % of stock.** Blackwell's voltage/frequency curve is steep near stock: the top ~40 % of the power budget buys only single-digit-percent extra throughput, so a limit near ~60 % sits close to the efficiency knee — it keeps the large majority of inference throughput while cutting heat, noise, and sustained draw substantially. It also fits a saner whole-box power/thermal budget: a ~350 W internal 5090 **plus** the OcuLink-attached 4090 (itself ~350–400 W) plus the Ryzen 9 9900X (~120 W) stays within a single quality PSU's sane continuous envelope. Applied with `nvidia-smi -pl 350` (persisted via the runtime profile); the exact value is tunable against measured perf/thermals per the operator's "based on the right maths and need for performance."

This aligns with an existing operator directive already in the mandate ("the RTX 4090 which should be sli[ght]ly reduce[d]") — power-limiting the second card is prior art; this extends the same discipline to the new primary.

## Relationship to the RTX PRO 6000 (additive — not discarded)

The operator's verbatim has always framed the PRO 6000 Blackwell 96 GB as **future** ("your **future** NVIDIA RTX PRO 6000 Blackwell with your **current** RTX 4090", `verbatim-surface.md`). This directive makes the **RTX 5090 the operative *now* internal primary**; the PRO 6000 96 GB stays documented as the **future large-VRAM Oracle-Core upgrade path** (per *adding ≠ discarding*). When/if it lands, the 5090 (32 GB) can move to secondary or to the eGPU dock. The reconcile must therefore present a **three-card reality** — 5090 (now-primary, internal), 4090 (now-secondary, eGPU), PRO 6000 (future primary) — not silently overwrite the PRO-6000 plan.

## VRAM + role implications (for the reconcile)

- Internal primary VRAM: **24 GB (4090) → 32 GB (5090)** — a real bump for the now-config, still well short of the 96 GB PRO-6000 future.
- The Oracle-Core / Logic-Engine SRP mapping needs re-seating: the 5090 (32 GB) is the new host-resident primary; the 4090 (24 GB) is the isolable eGPU. Model→GPU placement tables (`sain-01-master-spec.md` §, `trinity-runtime-profiles.md`, `model-catalog.md` VRAM-ceiling claims) must reflect a 32 GB internal ceiling and a 24 GB eGPU.
- The fleet predicate `any_gpu_vram_at_least_80gib` (predicate-coverage dashboard) still requires the 96 GB PRO 6000 to pass — the 5090's 32 GB does not clear an 80 GiB bar; that threshold's semantics are a reconcile decision, not a silent change.

## VFIO / IOMMU note

The 4090 was VFIO-isolated as an internal card sharing the CPU's IOMMU topology. On an OcuLink eGPU it sits on its own downstream PCIe path — still `vfio-pci`-isolable (arguably a **cleaner** isolation boundary, its own IOMMU group by construction), but the bind script, the `vfio-pci.ids` list, the "distinct IOMMU groups" wording, and the boot-time bifurcation notes all need reconcile **in lockstep with their pinning lints** (see below).

## Scope of THIS SDD

Definitional only: this SDD **states** the new topology, the researched facts, the power maths, and the reconcile roadmap. It **edits no pinned hardware surface** — so it cannot break the verbatim-pinning lints — and registers the operator directive (mandate row E11.M993). Every canonical-surface change lands in the follow-up reconcile increments below, each updating its surface **and its lockstep lint together**.

## Reconcile roadmap (named follow-ups — the "lot of documentation update")

Ordered, each a coherent surface-group + its lockstep lint(s):

1. **Canonical machine-readable** — `profiles/sain-01.yaml` GPU block (5090 primary + 4090-eGPU; PCI IDs; power `tdp_watts: 350`; retire/rewrite the "M.2_2 must remain empty" note; VFIO/IOMMU) **+ `tests/lint/test_sain01_profile_verbatim.py` + `test_vfio_bind_verbatim.py`** in lockstep.
2. **Operator-readable spec** — `docs/src/sain-01-master-spec.md` §1 hardware table + PCIe-lane §, `docs/src/profiles/sain-01.md` **+ its 4 pinning lints** (`test_handoff_docs_content.py`, `test_pulse_build_bitnet_contract.py`, `test_trinity_tui_contract.py`, `test_trinity_webapp_contract.py` — verify which strings each pins).
3. **The LM Orchestration prepared eGPU slot** — the D-21 "Ext-GPU" cell (`docs/operator/d21-lm-orchestration-cockpit.md`, `scripts/operator/lm-orchestration-api.py`, `webapp/d-21-lm-orchestration/index.html`, `docs/sdd/111-d21-d22-full-layout.md` grid contract): relabel `Future / External GPU` → the registered **RTX 4090 (OcuLink eGPU)**, and give the slot a real registration/role path.
4. **eGPU milestone reframe** — `backlog/milestones/M040-*.md` E0383/E0384: the operator's eGPU is **OcuLink (PCIe-native), not USB4 "not ideal"** — reframe accordingly **+ `test_m040_hyper_features.py`**.
5. **Runtime power profiles** — `profiles/runtime/*.yaml` (source of the generated `trinity-runtime-profiles.md`; do-not-edit the generated file): primary 350 W (was 600), re-seat the 5090/4090 device roles **+ `test_runtime_profiles_verbatim.py`**.
6. **Model catalog + placement** — `docs/src/model-catalog.md` VRAM-ceiling claims (24 GB → 32 GB internal; 24 GB eGPU).
7. **Install / lifecycle runbooks** — `install-runbook.md`, `ops/install.md`, `operator-journey.md`, `bootstrap-phases.md`, `lifecycle/post-install.md`, `m060-deployment-guide.md`: the `vfio-bind-4090` flow + PCI IDs + power-limit step for an OcuLink 4090.
8. **Observability dashboards** — the hardcoded `4090`/`3090`/`Blackwell` GPU labels + `selfdef_scheduler_gpu3090_util` metric names + the `any_gpu_vram_at_least_80gib` predicate.
9. **Verbatim + decisions** — append the new directive to `docs/src/verbatim-surface.md` (additive; its lint enforces a *minimum* size) and add a `docs/decisions.md` entry; refresh the mandate GPU rows.
10. **DSpark-from-DeepSeek** — separate SDD (PR 2): research what "DSpark" is (candidate: an NVIDIA DGX-Spark-class node running DeepSeek, or a DeepSeek serving artifact) and slot it into the compute-plane device registry (`SDD-207` phases, `compute_plane.py`) / gateway `/v1/models/background`+`register` proxy (`SDD-902`) — the same registration path the Ext-GPU cell scaffolds toward.

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
