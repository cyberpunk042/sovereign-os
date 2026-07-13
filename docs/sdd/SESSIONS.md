# Parallel-session registry (SDD-980)

> **Who is working sovereign-os right now, and which number band is theirs.**
>
> sovereign-os is worked by several sessions in parallel, each on its own branch
> merging to `main` (SDD-100). This registry is the **authoritative, machine-read
> map** of session → band, so a session can *identify itself* and tooling can tell
> which session owns any `SDD-NNN` / `E11.M###` number. It is the spine the
> auto-resolver (`scripts/git/sdd_conflict_resolver.py`, SDD-980) trusts, and
> `tests/lint/test_session_registry.py` enforces it (bands disjoint; every SDD
> file's number lands in exactly one registered band; every SDD's declared
> `Number band:` matches a registered session band).
>
> `.gitattributes merge=union` keeps every session's row across merges — so
> updating your own row never conflicts with another session updating theirs.

## Registered sessions

| session-id | SDD band | mandate E11 band | branch (prefix) | purpose | status |
|---|---|---|---|---|---|
| recover-projects | 100–199 | E11.M100–M199 | `claude/recover-projects-*` | Memory-OS + infra recovery | active |
| header-sidemenu | 200–299 | E11.M200–M299 | `claude/header-sidemenu-*` | cockpit app-shell | active |
| science-tools | 300–399 | E11.M300–M399 | `claude/science-tools-*` | science tooling | active |
| cockpit-wasm | 800–899 | E11.M800–M899 | `claude/*cockpit-wasm*` | cockpit-wasm bridge (F-2026-001) | active |
| compute-plane | 900–949 | E11.M900–M949 | `claude/*compute-plane*` | multi-model / GPU compute plane | active |
| phase-1-audit | 950–999 | E11.M950–M999 | `claude/sovereign-os-audit-*` | phase-1 audit / improvement | active |

> **No shared catch-all band.** Every new unassigned session claims its **own
> disjoint 100-wide block** and adds a row here BEFORE taking numbers (next free
> block: `800–899` taken → `700–799`, then `600–699`, …). This is the rule that
> makes collisions the exception the resolver cleans up, not the norm.

## How a session identifies itself

1. Add (or confirm) your row above — pick a free 100-wide band, name your branch
   prefix + purpose.
2. Allocate SDD / `E11.M###` numbers **only inside your band**, and set the
   `> Number band: **<lo>–<hi>** …` line in each SDD you author to your band.
3. That declared band is your **authorship signature**: on a duplicate number the
   resolver renumbers whichever file's declared band does *not* contain the number
   (the out-of-band intruder), into the next free slot of *its own* band.

## Talking across sessions (and to the operator)

`docs/sdd/RESOLUTION-LOG.md` is the append-only cross-session ledger — the
resolver writes there whenever it auto-fixes (or can't fix) a collision, naming
the sessions involved and the residual follow-ups. Because it is `merge=union`,
any session (or the operator) can append a note addressed to another session or
to the operator, and every branch keeps every note across merges. It is the seed
of the fuller session-to-session / session-to-operator message board sketched in
SDD-980 "sessions talk to each other."

## Cross-references

- `docs/sdd/README.md` — the band table + how-to-add-an-SDD (human narrative)
- `docs/sdd/100-parallel-session-conflict-avoidance.md` — SDD-100 (the convention)
- `docs/sdd/980-sdd-conflict-auto-resolution.md` — SDD-980 (the auto-resolver)
- `scripts/git/sdd_conflict_resolver.py` — the resolver that reads this registry
- `tests/lint/test_session_registry.py` — the enforcing lint
- `docs/sdd/RESOLUTION-LOG.md` — the cross-session ledger / message board
