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
| 004 | Profile schema | — | PR 5 | Resolves Q-002 (in part) at Gate 3. |
| 005 | Initial profile stubs (sain-01 + old-workstation) | review | PR 6 | Validates schema against real profiles. 2 stubs + 3 mixins + INDEX + validation harness placeholder. Q6-A..Q6-D open. |
| 006 | Debian (or successor) surface audit | — | PR 7 | Whitelabel target inventory. |
| 007 | Whitelabel mechanism | — | PR 8 | Resolves Q-004 (legal scope) at Gate 4; Q-003 may stay open. |
| 008 | TDD harness specification | — | PR 9 | Resolves Q-010 + Q-014 + Q-015 (in part). |
| 009 | TDD harness bootstrap | — | PR 10 | First passing tests. |
| 010 | Stage-2 first-build-scripts stub | — | PR 10 | Reserves slot for post-Gate-5 work. |

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
