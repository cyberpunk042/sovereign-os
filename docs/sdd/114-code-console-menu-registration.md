# SDD-114 — Register Code Console in the app-shell sidemenu (the "new menu")

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"You can also add it to the new menu when you get there"* (referring to the SDD-112 Code Console panel). Completes the SDD-112 Q-112-D deferral (the sidemenu-GROUPS registration was held back to avoid colliding with the parallel header-sidemenu session's app-shell work).
> Derived from / extends: SDD-112 (Code Console), M067 (app-shell). §1g operator-surface. Recover band (SDD-114 / E11.M114 per SDD-100).

## Mission

Add the **Code Console** panel to the app-shell sidemenu so it is reachable from every panel's left
nav (not only by direct URL / catalog / Cmd-K). The single source of truth for the sidemenu is the
`GROUPS` array in `webapp/_shared/app-shell-snippet.html`; `scripts/webapp/sync-app-shell.py --apply`
distributes the block verbatim into every adopted panel. This increment adds one `GROUPS` entry (in the
**Models & Compute** group, adjacent to D-22 which the console extends) and re-syncs.

## Grounded plan

- **Canonical GROUPS entry** in `webapp/_shared/app-shell-snippet.html`, in the Models & Compute group
  after the D-22 entry: `{id:'—', dir:'code-console', label:'Code Console', ico:'⌘', desc:…,
  menuHover:…}` — with a REAL, specific `menuHover` (not reused from another panel; per the operator's
  standing rule that each menu-hover carries its own assistant data).
- **`sync-app-shell.py --apply`** to propagate the updated block into all adopted panels (incl.
  code-console itself, so its own sidemenu lists it too).
- The app-shell contract lint (`test_app_shell_contract.py`) then passes with every adopted panel
  byte-identical to the new canonical.

## Goals

- Code Console appears in the sidemenu of every panel + its own.
- The canonical app-shell block stays the single source of truth (sync tool, not hand-edits).
- A real, specific `menuHover` for the entry.

## Non-goals

- No change to the Code Console panel's behaviour, API, or the honest-deferred posture (SDD-112).
- No new nav mechanism — reuses the existing GROUPS + sync-app-shell pipeline.
- No Cmd-1..0 digit shortcut (those are D-00..D-09 only; code-console is Cmd-K/palette + sidemenu).

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-114-A | Placement group. | **proposed: Models & Compute, after D-22** — the console extends D-22's loopback chat into a full IDE-style surface. |
| Q-114-B | Icon. | **proposed: `⌘`** — evokes the command/code interface. |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-114 + INDEX + mandate E11.M114.
- **Stage 1** — canonical GROUPS entry + `sync-app-shell.py --apply` + verify app-shell contract.
- **Stage 2** — full gate + Playwright (code-console appears in a panel's sidemenu) + commit/push/draft PR.

## Cross-references

- SDD-112 — the Code Console panel (Q-112-D deferral this closes).
- M067 app-shell + `scripts/webapp/sync-app-shell.py` (the distribution pipeline).
- SDD-100 — parallel-session band scheme (recover band; the app-shell is the header-sidemenu session's
  surface — re-base fresh immediately before syncing to keep the collision window small).
