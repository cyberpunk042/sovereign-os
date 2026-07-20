# SDD directory — numbering + parallel-session conventions

Spec-Driven Development docs live here as `NNN-<slug>.md`, catalogued in
[`INDEX.md`](INDEX.md). Each SDD also gets a mandate row `E11.M##` in
[`../standing-directives/2026-05-17-operator-mandate.md`](../standing-directives/2026-05-17-operator-mandate.md).

## Per-session number bands (SDD-100)

**sovereign-os is worked by 3 sessions in parallel**, each on its own branch merging to
`main`. To stop the two sessions ever picking the same `SDD-NNN` / `E11.M##` (which collided
on 2026-07-09 — SDD-070), each session allocates numbers **within its own disjoint band**:

| Session / workstream | SDD band | mandate E11 band |
|---|---|---|
| **recover-projects** (Memory-OS + infra) | **100–199** | **E11.M100–M199** |
| **header-sidemenu** (cockpit app-shell) | **200–299** | **E11.M200–M299** |
| **science-tools** | **300–399** | **E11.M300–M399** |
| **cockpit-wasm bridge** (F-2026-001) | **800–899** | **E11.M800–M899** |
| **compute-plane** (multi-model / GPU) | **900–949** | **E11.M900–M949** |
| **phase-1 audit** / improvement | **950–999** | **E11.M950–M999** |
| **phase-1 audit — continuation** (build-and-flash readiness) | **700–799** | **E11.M700–M799** |
| **control-bits** (M002 bit-machine per-token integration) | **500–599** | **E11.M500–M599** |
| **cockpit-hotswap** (settings-pane hotswaps) | **600–699** | **E11.M600–M699** |
| **chromofold-integration** (ChromoFold compressed-domain, opt-in) | **500–599** | **E11.M500–M599** |

> There is **no shared "any new / unassigned → 900–999" catch-all** — it was itself a collision
> source (two unassigned sessions both grabbed the next free 900-number: SDD-900 on 2026-07-12,
> SDD-969 on 2026-07-13). **Every new unassigned session claims its OWN disjoint 100-wide block**
> and adds a row here (`800–899` + `700–799` + `600–699` + `500–599` are taken → next free block: `400–499`, …).
> See SDD-100 amendments (2026-07-12, 2026-07-13).

The historical `064–071` / `E11.M32–M38` numbers (allocated before banding) stay as-is — the
bands apply going **forward**. Gaps between bands are intentional and allowed (the lint
enforces tightness only *within* a hundreds-block; see
[`../../tests/lint/test_sdd_content_extended.py`](../../tests/lint/test_sdd_content_extended.py)
`test_sdd_numbers_sequential_no_huge_gaps` +
[`../../tests/lint/test_mandate_section_1_subsections.py`](../../tests/lint/test_mandate_section_1_subsections.py)
`test_e11_modules_sequential`).

## How to add an SDD (in your band)

1. Pick the **next free number in YOUR session's band** (e.g. recover-projects: after 100,
   use 101, 102, …).
2. Create `docs/sdd/<NNN>-<slug>.md` + append the `| NNN | … |` row to `INDEX.md` + the
   `| E11.M## | … |` row to the operator-mandate (use the matching E11 band number).
3. These registries are `merge=union` (see [`../../.gitattributes`](../../.gitattributes)) —
   two branches appending different rows merge cleanly (both kept), so you never resolve a
   registry conflict by hand.
4. **Don't hardcode registry counts** (e.g. "N recurrent hooks", "N timers") in prose or test
   docstrings — a count is a shared integer two sessions both bump. The real assertions are
   glob/set-based; keep the prose count-free.

## Conflict-avoidance mechanism (SDD-100)

- **`.gitattributes merge=union`** on the append-only registries (INDEX / mandate / ongoing /
  dashboards / decisions) → git keeps both sides' added rows on a merge.
- **Per-session number bands** (this table) → distinct numbers, no collision.
- **De-magic'd counts** → no shared-integer churn.

See [`100-parallel-session-conflict-avoidance.md`](100-parallel-session-conflict-avoidance.md).
