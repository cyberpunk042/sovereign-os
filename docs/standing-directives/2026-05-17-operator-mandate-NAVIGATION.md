# Navigation — 2026-05-17 operator mandate

> Companion index for [`2026-05-17-operator-mandate.md`](./2026-05-17-operator-mandate.md) — a
> ~640 KB single file whose individual mandate-table rows are multi-KB, making it slow to open
> and hard to diff. This map lets a reader (or agent) jump to the right section without loading
> the whole file. **It does not reproduce or replace any content** — the mandate file remains the
> single sacrosanct source; this is navigation only.
>
> `tests/lint/test_mandate_navigation.py` fails CI if a section heading is added, renamed, or
> removed in the mandate without being reflected here — so the map can't silently drift from the
> file's structure. (Adding an `E11.M###` mandate *row* does not change a heading, so routine
> mandate-row appends need no update here.)

## Top-level sections

| § | Section | What's inside |
|---|---|---|
| 1 | [1. The operator mandate (verbatim, sacrosanct)](./2026-05-17-operator-mandate.md#1-the-operator-mandate-verbatim-sacrosanct) | The union of every `/goal` operator paste, verbatim + additive. The sacrosanct primary source — never edited, only appended. Sub-directives §1.0–§1h below. |
| 2 | [2. Standing rules (sacrosanct — applies to EVERY round)](./2026-05-17-operator-mandate.md#2-standing-rules-sacrosanct--applies-to-every-round) | The cross-round rules every future `/goal` honors. |
| 3 | [3. Epic / Module / Task decomposition](./2026-05-17-operator-mandate.md#3-epic--module--task-decomposition) | The agent-maintained backlog derived from the mandate — Epics E1–E11 below. **The `E11.M###` mandate-module table lives under Epic E11.** |
| 4 | [4. How future rounds use this file](./2026-05-17-operator-mandate.md#4-how-future-rounds-use-this-file) | The read/append protocol for future rounds. |
| 5 | [5. What this file does NOT do](./2026-05-17-operator-mandate.md#5-what-this-file-does-not-do) | Scope boundaries. |
| 6 | [6. Anti-corruption invariants](./2026-05-17-operator-mandate.md#6-anti-corruption-invariants) | The rules protecting the verbatim content from drift. |

## §1 sub-directives (verbatim operator pastes)

Each is a distinct `/goal` paste, reproduced verbatim in section 1:

- §1.0 — Re-instate directive (2026-05-17, operator paste-record session)
- §1a — Branch + PR + ultimate-OS posture
- §1b — Multi-mode functioning + grey-out UX + REPL tiers (2026-05-17)
- §1c, §1d, §1e — Hardware-stack expansion (2026-05-17, three times)
- §1f — full operator paste reproduced verbatim below (unchanged)
- §1g — Documentation + master-dashboard + global history + auth tiers + firewall/VPN-bridge topology (2026-05-18, operator paste-record session)
- §1h — Two ultimate solutions + perfectioning + high UX/DX (2026-05-18, operator paste-record session — 6th /goal)

## §3 epics (backlog decomposition)

- Epic E1 — Hardware-stack visibility & control
- Epic E2 — Software-stack visibility & control
- Epic E3 — Network visibility & control
- Epic E4 — Dashboard / Operator UX
- Epic E5 — AI / LLM / Training-station
- Epic E6 — Health / Doctor / Autonomy
- Epic E7 — Interop / MCP / Tools / Deps
- Epic E8 — Python REPL / Programming tiers / Integrated intelligence
- Epic E9 — Operator-mandate process discipline
- Epic E10 — AI as guide (operator-pull narrative entry-points)
- Epic E11 — §1g "Ultimate Sovereign OS" expansion (docs + master-dashboard + global history + auth tiers + network topology + edge-firewall + Nemotron 3) — **holds the `E11.M###` mandate-module rows** (the per-SDD cross-link table)
- Cross-repo selfdef-side typed-mirror crates — SATURATED 8/8 (R471)

## Finding a specific `E11.M###` mandate module

The mandate modules (one per audit-session SDD — `E11.M952` … onward) are table rows under **Epic E11**. To find one, open the mandate file and search for its id (e.g. `E11.M964`); each row carries its SDD number, the §1g surface keyword, the change summary, and its verification. The per-SDD catalog at [`docs/sdd/INDEX.md`](../sdd/INDEX.md) and the generated [`docs/src/sdd-catalog.md`](../src/sdd-catalog.md) cross-reference the same SDDs.
