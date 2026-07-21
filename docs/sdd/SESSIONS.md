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
| phase-1-audit-cont | 700–799 | E11.M700–M799 | `claude/sovereign-os-audit-*` | phase-1 audit continuation — build-and-flash readiness (950–999 band filled) | active |
| cockpit-hotswap | 600–699 | E11.M600–M699 | `claude/sovereign-os-test-perf-*` | top-right settings-pane hotswaps — frontend/GUI · provider/origin · AVX modes (design-lock) | active |
| control-bits | 500–599 | E11.M500–M599 | `claude/glm-colibri-sovereign-os-*` | M002 bit-machine per-token integration — token-law logit mask (SDD-500) · multi-plane grammar∧policy composition (SDD-501) | active |
| chromofold-integration | 400–499 | E11.M400–M499 | `claude/*chromofold*` | ChromoFold (from `warp-solar-system-shaders`) — GPU-resident searchable compression, opt-in complementary capability via native C ABI (SDD-400, design-lock) | active |

> **No shared catch-all band.** Every new unassigned session claims its **own
> disjoint 100-wide block** and adds a row here BEFORE taking numbers (`800–899` +
> `700–799` taken → next free block: `600–699`, then `500–599`, …). This is the rule that
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

Two append-only, `merge=union` surfaces — so any session on any branch (and the
operator) can write, and every branch keeps everything across merges:

- **`docs/sdd/MESSAGES.md`** — the **session message board** (SDD-981): addressed,
  threaded, bidirectional communication between sessions and the operator. Post
  and read with `scripts/git/session_comms.py`:

  ```sh
  python3 scripts/git/session_comms.py whoami                 # which session am I (from the branch)
  python3 scripts/git/session_comms.py inbox                  # my open messages (also runs on `git pull`)
  python3 scripts/git/session_comms.py post --to cockpit-wasm --subject "…" --body "…"
  python3 scripts/git/session_comms.py post --to operator  --subject "…" --body "…"
  python3 scripts/git/session_comms.py post --to all       --subject "…" --body "…"   # broadcast
  python3 scripts/git/session_comms.py reply <msg-id> --body "…"
  python3 scripts/git/session_comms.py thread <msg-id>
  ```

  `from`/`to` are a session-id from the table above, `operator`, or `all`.
  "Answered" is derived (a message is open until its addressee replies), so
  nothing is ever mutated — only appended. The `post-merge` hook nudges you when
  a pull brings new mail.

- **`docs/sdd/RESOLUTION-LOG.md`** — the resolver's automated ledger (SDD-980):
  every SDD-collision auto-fix (or un-fixable case), naming the sessions involved
  and the follow-ups. Machine-written; read it to see what the resolver did.

## Cross-references

- `docs/sdd/README.md` — the band table + how-to-add-an-SDD (human narrative)
- `docs/sdd/100-parallel-session-conflict-avoidance.md` — SDD-100 (the convention)
- `docs/sdd/980-sdd-conflict-auto-resolution.md` — SDD-980 (the auto-resolver)
- `scripts/git/sdd_conflict_resolver.py` — the resolver that reads this registry
- `tests/lint/test_session_registry.py` — the enforcing lint
- `docs/sdd/RESOLUTION-LOG.md` — the cross-session ledger / message board
