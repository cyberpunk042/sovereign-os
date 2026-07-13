# SDD-981 — the parallel-session communication protocol (sessions talk to each other, and to the operator)

> Status: draft
> Owner: operator-directed 2026-07-13 ("what about the communication protocol between each sessions and me yeah, lets do, point 1. and lets do this right and make sure its documented properly"); agent-authored.
> Builds on: SDD-980 (session registry + the resolver's ledger — the "seed" this turns into a real channel).
> Mandate module: **E11.M981**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-980 gave sessions an **identity** (`docs/sdd/SESSIONS.md`) and a resolver that
writes notes to an append-only ledger. This turns that seed into a **real,
bidirectional communication protocol**: any parallel session can send an
addressed, threaded message to another session or to the operator, the operator
can message any session, and each party has a **derived inbox** — all
collision-safe across the parallel branches, docs + scripts only.

## Design principles ("done right")

The whole protocol falls out of four constraints, chosen so it can never
conflict across the parallel branches:

1. **One message = one line.** The board `docs/sdd/MESSAGES.md` is a Markdown
   table; each message is a self-contained row. Two sessions on two branches
   both appending a row at end-of-file produce non-overlapping additions, so
   `.gitattributes merge=union` keeps BOTH with no conflict, order-independent.
   (Multi-line blocks would risk hunk interleaving under union — hence one line.)
2. **Append-only, never mutate.** "Read" / "answered" is **derived**, not a
   stored flag: a message addressed to X is *open* until X appends a reply whose
   `re` points at it. A mutable flag would be a cross-branch edit-conflict; a
   derived one never is.
3. **Ids unique without coordination.** `msg-id = <from>-<utcstamp>-<rand8>`, so
   two sessions minting messages at the same instant still never collide.
4. **Identity from the branch.** `whoami` matches the current git branch against
   the `branch` glob in `SESSIONS.md` — the same registry the SDD-980 resolver
   trusts. No separate identity store to drift.

## The record

`docs/sdd/MESSAGES.md`, 7 columns (a literal `|` in text is stored as `&#124;`,
newlines flattened to ` / `, so a message is always exactly one row):

```
| msg-id | utc | from | to | re | subject | body |
```

- **from / to** — a session-id from `SESSIONS.md`, `operator`, or `all` (broadcast;
  `to` only). Unknown parties are rejected at post time and by the lint.
- **re** — an in-reply-to `msg-id` (empty for a new thread).

## The tool

`scripts/git/session_comms.py` (stdlib only):

| Command | What it does |
|---|---|
| `whoami` | resolve this branch → session-id |
| `inbox [--for WHO] [--all]` | messages addressed to WHO (default: `whoami`), **open first**; exit 1 if any open (so hooks/CI can gate) |
| `post --to WHO [--re ID] --subject S --body B [--from WHO]` | send a message |
| `reply ID --body B [--to WHO]` | reply in-thread (`re` defaults to `ID`) |
| `ack ID` | terse reply "acknowledged" (clears it from your open inbox) |
| `thread ID` | a message + its whole reply chain, time-ordered |
| `list [--from WHO] [--to WHO]` | filtered raw view |

`from` defaults to `whoami`; pass `--from operator` to speak as the operator.

## Discovery — you always see your mail

A message board is useless if nobody reads it. Two surfaces make mail visible:

- **On pull**: the `post-merge` hook (`lib/session-inbox-notify.sh`) prints a
  one-line nudge — *"you (phase-1-audit) have N open message(s) — run … inbox"* —
  the instant a merge brings new mail. Silent when the inbox is empty.
- **On demand**: `session_comms.py inbox` any time; `SESSIONS.md` documents the
  commands next to the session table.

## Worked example (real, observed)

```
$ session_comms.py whoami
phase-1-audit
$ session_comms.py post --to cockpit-wasm --subject "band check" \
    --body "confirm your band is 800-899 after the SDD-974→800 renumber"
posted phase-1-audit-20260713T152320-a9c9f8c6  (phase-1-audit → cockpit-wasm)
# … cockpit-wasm pulls, the hook nudges "1 open message", they read + reply:
$ session_comms.py reply phase-1-audit-…-a9c9f8c6 --from cockpit-wasm \
    --body "Confirmed, band 800-899."
$ session_comms.py inbox --for cockpit-wasm          # band-check now ANSWERED
$ session_comms.py thread phase-1-audit-…-a9c9f8c6   # shows both, time-ordered
```

`post --to operator` reaches the operator's inbox; `post --to all` broadcasts to
every session; the operator replies with `--from operator`.

## Verification (real, observed)

- **Live** on this branch: `whoami` → `phase-1-audit`; posted direct + broadcast +
  to-operator; `inbox --for cockpit-wasm` showed the direct + broadcast as OPEN
  (exit 1); a reply from cockpit-wasm flipped the direct message to ANSWERED
  while the broadcast stayed open; `thread` rendered the chain; a `|`+newline body
  round-tripped intact.
- **`tests/lint/test_session_comms.py`** — 9 hermetic cases: identity from branch,
  direct+broadcast delivery, derived-answered, inbox exit-code, unknown-id /
  unknown-recipient rejection, pipe+newline round-trip, thread chaining, two
  independent appends both parse (union-safety proxy).
- **`tests/lint/test_messages_board.py`** — board integrity on the real tree
  (7-column header; every from/to registered; re resolves; ids unique).

## Non-goals

- Real-time delivery / notifications beyond the pull-time hook nudge and on-demand
  `inbox` — the board is pull-based (it lives in git), by design.
- Encryption / access control — the board is in-repo, readable by anyone with the
  repo (same trust boundary as every other doc).
- Rich bodies (attachments, multi-paragraph) — a body is one line; long detail
  lives in a referenced SDD/file. Deliberate, for union-safety.
- Mutating/deleting messages — append-only; a correction is a new reply.

## Safety invariants

Docs + scripts + `.gitattributes` only. No gatewayd, no cockpit, no `unsafe`, no
crate edits. Append-only + derived state → no cross-branch mutation conflict.
R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/git/session_comms.py` — the protocol tool
- `docs/sdd/MESSAGES.md` — the board (7-column append-only table)
- `docs/sdd/SESSIONS.md` — the session registry (identity); "Talking across sessions" section
- `scripts/git-hooks/lib/session-inbox-notify.sh` + `post-merge` — the pull-time nudge
- `tests/lint/test_session_comms.py` / `test_messages_board.py` — the lints
- `docs/sdd/980-sdd-conflict-auto-resolution.md` — SDD-980 (identity + the ledger seed this builds on)
- `docs/sdd/RESOLUTION-LOG.md` — the resolver's automated ledger (the other append-only surface)
- `docs/sdd/100-parallel-session-conflict-avoidance.md` — SDD-100 (the parallel-session model)
