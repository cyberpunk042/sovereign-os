# Deferred-work register (Phase-1 audit — F-2026-037)

> The docs already **promise** the work below across decisions, SDDs, and context.md.
> This register consolidates those promises in one place so they get owners + ordering
> instead of being rediscovered each pass. It is a **pointer index**, not a re-spec —
> each item's authoritative definition stays in its cited source.
>
> **Owner column is `operator-to-assign`** — sequencing/ownership is an operator call
> (a decision-package), not an agent decision. The **Proposed order** is a suggestion.
>
> `tests/lint/test_deferred_work_register.py` verifies every source cited here resolves
> (the SDD / doc files exist), so the register can't rot into dangling references.
> It does **not** assert an item is still open — status reconciliation is per-item
> operator/authoring-session work against the cited source.

| # | Deferred item | Sources | Scope (one line) | Proposed order | Owner |
|---|---|---|---|---|---|
| 1 | Telemetry-sink choice + Grafana JSON dashboards | `docs/decisions.md` | Pick the telemetry sink; ship the Grafana dashboard JSONs (observability foundation). | P1 (foundation) | operator-to-assign |
| 2 | SDD-016 Layer-B Prometheus emission | SDD-016 | The observability-bindings contract is locked but unemitted — wire the emission. | P1 (foundation) | operator-to-assign |
| 3 | Layer-4 QEMU + Layer-5 hardware conformance suites | `docs/decisions.md`, SDD-020 | `tests/qemu` + `tests/chroot` are scaffolds only; build the two upper TDD tiers (F-2026-052 sibling). | P2 (test rigor) | operator-to-assign |
| 4 | SDD-019 apt-snapshot enforcement + `SOURCE_DATE_EPOCH` + in-toto provenance | SDD-019 | Reproducibility: enforce apt-snapshot, set `SOURCE_DATE_EPOCH` in step-04, add in-toto provenance. | P2 (reproducibility) | operator-to-assign |
| 5 | TPM2 disk-encryption PCR binding | SDD-015, SDD-022 | Bind LUKS to TPM2 PCRs (secure-boot + disk-encryption). | P2 (security) | operator-to-assign |
| 6 | SDD-029 roadmap R257–R262 | SDD-029 | XMP detection, wattage sampler, PSU OC toggle, KNOWN_BOARDS TOML, Z-14/Z-19 cards. | P3 (hardware roadmap) | operator-to-assign |
| 7 | MS043 selfdef mirror-crate implementations | `context.md` (MS043 row) | The 9 D-12..D-18 mirror crates are catalog-✓ / impl-pending; verify against the M060 completion claim + close either way. Cross-repo (selfdef). | P3 (cross-repo) | operator-to-assign |
| 8 | selfdef CLI/TUI mirror surface integration + SG7/SG8 stage-gates | `context.md` (MS043 row) | Wire selfdef-cli-mirror + selfdef-tui-mirror surfaces; SG7/SG8 stage-gates beyond catalog. Cross-repo. | P3 (cross-repo) | operator-to-assign |
| 9 | Open question series — SDD-046 Q-046-001..004; root Q-A..Q-D; Q4..Q25 | SDD-046, SDD-003, SDD-025 | Resolve the open-question backlog (mdbook deploy cadence/provider; the Q4..Q25 series across SDD-003..025). | P4 (questions) | operator-to-assign |
| 10 | Q-067-A..F app-shell questions (incl. Q-067-F live-LLM assistant) | `docs/decisions.md` | App-shell question set; **partially overtaken** by the Brain/Code-Console work — reconcile which remain open. | P4 (questions — reconcile) | operator-to-assign |

## Notes

- **Items 7–8 are cross-repo** (selfdef); they can only be closed with the selfdef tree in scope, and item 7's status must be reconciled against the M060 completion claim in `context.md`.
- **Item 10 is partially overtaken** by the July intelligence-layer arc (the Sovereign Brain observatory + Code Console); the reconcile is "which Q-067 questions survive that work."
- **Item 3** is the same surface as **F-2026-052** (the 3-tier test harness is effectively 1-tier) — track them together.
- The **Proposed order** groups by kind (foundation → reproducibility/security → hardware/cross-repo → questions); the operator sets the real sequence.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — F-2026-037 (source), F-2026-052 (Layer-4/5 sibling)
- `tests/lint/test_deferred_work_register.py` — the source-resolution contract
- `docs/sdd/INDEX.md` — the SDDs cited above
