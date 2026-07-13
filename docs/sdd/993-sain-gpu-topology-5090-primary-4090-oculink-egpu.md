# SDD-993 — SAIN GPU topology change: RTX 5090 internal primary (~350 W) + RTX 4090 as OcuLink eGPU

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

## VFIO is OPT-IN — bare-metal is the default (operator directive 2026-07-13)

Operator, verbatim: *"also what is this VFIO GPU thing … I like the idea of a sandbox but at the same time it should be an option, a config I can opt in or not … I want to be able to work locally on my workstation most of the time, not in a VM by default."*

The reconcile flips the **default** from "4090 VFIO-isolated" to **host-resident / bare-metal**: the 4090's declared `role` is `secondary` (directly usable by the host inference stack — Logic Engine / speculative-decoding draft, worked-on locally). The VFIO-isolated sandbox (§17 dual-GPU SRP perimeter) is an **opt-in** mode — set `role: vfio` in the profile and `vfio-bind-4090.sh` binds it at boot; with the default role the bind hook is a clean no-op. **The isolation machinery is preserved, not removed** — this is a default-flip, and it is consistent with the operator's own M040 E0384 "performance profile: 4090 on host" verbatim.

## Scope of THIS SDD — reconcile SHIPPED

This SDD started as a definitional anchor and now carries the **full SAIN/eGPU reconcile** (below). It **states** the new topology + researched facts + power maths + VFIO-opt-in default, and it **drove** the canonical-surface edits — each surface updated in lockstep with its pinning lint (reframed, never silently broken). The DSpark-from-DeepSeek adoption remains a **separate follow-up SDD** (PR 2) per operator sequencing.

## Reconcile roadmap — status (the "lot of documentation update")

Each a coherent surface-group + its lockstep lint(s). ✅ = landed this session.

1. ✅ **Canonical machine-readable** — `profiles/sain-01.yaml` GPU block (5090 primary + 4090 secondary/host-resident + PRO 6000 future; PCI IDs; power `tdp_watts: 350`; `m2_2_empty` → `m2_2_oculink_egpu`; VFIO opt-in) + `schemas/profile.schema.yaml` (sku/connection/link props + `secondary`/`future` role enum) + `crates/sovereign-pcie-topology` recommended layout + `friction-audit-spec.sh`, with `test_sain01_profile_verbatim.py`, `test_vfio_bind_verbatim.py`, `test_profile_schema_conformance.py` reframed in lockstep.
2. ✅ **Operator-readable spec** — `docs/src/sain-01-master-spec.md` §1 hardware table + PCIe-topology § + Weaver/Phase-IV VFIO-opt-in reframe; `docs/src/profiles/sain-01.md` (3-GPU table, first-boot hook note, recovery table); the 4 pinning lints verified green.
3. ✅ **The LM Orchestration prepared eGPU slot** — the D-21 "Ext-GPU" cell (`docs/operator/d21-lm-orchestration-cockpit.md`, `scripts/operator/lm-orchestration-api.py`, `webapp/d-21-lm-orchestration/index.html`): `Future / External GPU` → registered **RTX 4090 (OcuLink eGPU)**; `test_d21_lm_orchestration_webapp_contract.py` green.
4. ✅ **eGPU milestone reframe** — `backlog/milestones/M040-*.md`: additive OcuLink-vs-USB4 reconcile note (verbatim rows untouched; the operator's own "performance: 4090 on host" now the default); `test_m040_hyper_features.py` green.
5. ✅ **Runtime power profiles** — `profiles/runtime/{high-concurrency-burst,deep-context-synthesis}.yaml` primary 600 → 350 W + NOW-vs-future reconcile notes; `trinity-runtime-profiles.md` regenerated; `test_runtime_profiles_verbatim.py` green. Also `generate-runtime-profile.py` excludes `role: future` GPUs and the high-concurrency oracle intent gains `multimodal` so the 32 GB primary lands the Nemotron-NVFP4 reasoner.
6. ✅ **Model catalog + placement** — `docs/src/model-catalog.md`: the Nemotron-NVFP4 entry now names the 32 GB internal 5090 as the SAIN NOW Oracle-Core pick + the 4090 as the OcuLink eGPU.
7. ⏳ **Install / lifecycle runbooks** — `install-runbook.md`, `ops/install.md`, `operator-journey.md`, `bootstrap-phases.md`, `lifecycle/post-install.md`, `m060-deployment-guide.md`: the `vfio-bind-4090` flow + PCI IDs + power-limit step. (The bind hook is already opt-in-safe; the runbook prose reconcile is the remaining tail — low blast-radius, no behaviour change.)
8. ✅ **Observability dashboards** — the `any_gpu_vram_at_least_80gib` predicate comment reflects the three-card reality (a NOW 5090/4090 SAIN does not clear 80 GiB; only future PRO 6000 boxes do). The `selfdef_scheduler_gpu3090_*` metric names are deliberately preserved for the prometheus contract (labels already read "4090").
9. ✅ **Decisions + mandate** — `docs/decisions.md` **D-021**; mandate row E11.M993 already registers the directive verbatim. (`verbatim-surface.md` is GENERATED with a drift detector — the directive is registered in the mandate + this SDD + INDEX, NOT hand-appended to the generated file.)
10. ⏳ **DSpark-from-DeepSeek** — separate SDD (PR 2): DSpark is DeepSeek's open-source speculative-decoding framework (Markov-head draft + semi-autoregressive chunking; "DeepSpec"); slot it into the Logic Engine speculative-decoding role (draft on the 4090 eGPU, verify on the 5090). Deferred per operator sequencing.

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
