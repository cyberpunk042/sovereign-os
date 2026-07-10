# SDD-112 — Code Console (a claude.ai/code-style cockpit panel for the sovereign local LM)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"Now we can start to engineer a panel that is exactly like claude.ai code interface, something like this"* (with a claude.ai/code screenshot: left session-list sidebar · center conversation thread · right "Plan" panel · bottom composer with a model selector · top session tabs + repo chips).
> Derived from / extends: SDD-062 + SDD-103 (D-22 loopback chat — the one sanctioned POST), M057 session-registry (task-session lifecycle), M075 (SRP device topology), SDD-045 (control-surface), M067 (app-shell). §1g operator-surface. Recover band (SDD-112 / E11.M112 per SDD-100).

## Mission

Engineer a NEW cockpit panel — **Code Console** (`webapp/code-console/`) — whose layout and interaction
model mirror the **claude.ai/code** interface, but wired to the box's **own sovereign local LM** rather
than any cloud. It is the god-tier "code with your machine" surface: a left session rail, a center
conversation thread, a right Plan/artifact pane, a bottom composer with a model/device selector, and
top session tabs — the full three-pane IDE-style shell. Every pane that has a real producer is
**honest-live**; every pane that does not is an explicit **honest-deferred** state (SB-077 — never a
fabricated conversation, never a faked plan). The console never mutates the box from the web except
through the single already-sanctioned inference read-compute (`POST /api/code-console/chat` → loopback
`/v1/chat/completions`) and the existing R10274 control-exec rail (R10212 preserved).

## The design (the claude.ai/code screenshot — the delivery contract)

The operator's reference screenshot decomposes into six regions. The Code Console re-creates each,
natively (zero external hosts; self-contained SPA), driving the sovereign stack:

1. **Left session rail** — a "Recents"-style list of sessions (claude.ai shows a session list with
   per-item icons + titles). Sovereign mapping: the **M057 task-session registry** (`/api/sessions/active`
   equivalent) — real OS task-sessions (init→inference→response→validation→cleanup, 9 task states).
   Honest empty when the registry is absent.
2. **Top session tabs + repo chips** — claude.ai shows open-session tabs and a breadcrumb with repo
   chips. Sovereign mapping: tabs bind to the active sessions; the **repo chips are honest-deferred**
   (no repo-attach producer on the box yet).
3. **Center conversation thread** — the message list. Sovereign mapping: a **live ephemeral chat**
   against the local LM (the proven D-22 loopback SSE), PLUS an **honest-deferred** persisted-thread
   state (no conversation/message store exists — the box holds no server-side conversation; R10212
   read-compute). We never invent past messages.
4. **Bottom composer** — the prompt textarea + send + model selector (claude.ai shows "Opus 4.8 / High").
   Sovereign mapping: the composer POSTs to the **sanctioned chat endpoint** and streams tokens back;
   the "model selector" maps to the **M075 device/tier targets** (CPU0=Conductor / GPU0=Logic /
   GPU1=Oracle) already used by D-22's chips + the runtime profile.
5. **Right "Plan" panel** — claude.ai shows a Plan/artifact pane. Sovereign mapping: **honest-deferred**
   — there is no plan/artifact producer on the box. Rendered as an explicit "no plan producer yet"
   pane with the shape it *will* take, never a fabricated plan.
6. **Global chrome** — the M067 app-shell (header + sidemenu + assistant rail), the SDD-045
   control-surface, the §1g footer standing rule — carried verbatim like every panel.

## Grounded design — what ships live vs what honest-defers (SB-077)

| Region | Producer (grounded) | Posture |
|---|---|---|
| Left session rail | `scripts/lifecycle/session-registry.py` (M057) via a read-only `GET /api/code-console/sessions` proxy | **honest-live**; honest-empty when `/run/sovereign-os/sessions.json` absent |
| Top session tabs | same session registry | **honest-live**; honest-empty |
| Top repo chips | none on the box | **honest-deferred** — explicit "no repo-attach producer yet" |
| Center thread (live) | loopback router via `POST /api/code-console/chat` → `/v1/chat/completions` (reuse of the D-22 SDD-062/103 proxy, served by THIS daemon so it stays same-origin) | **honest-live**; honest "router unreachable" on no backend |
| Center thread (persisted) | none — box holds no conversation store (R10212 read-compute) | **honest-deferred** — explicit "no persisted-thread producer; this session is in-page only" |
| Bottom composer + model/device selector | the chat endpoint + M075 device targets | **honest-live** |
| Right Plan/artifact pane | none | **honest-deferred** — explicit "no plan producer yet" with the intended shape |
| Global chrome (app-shell / control-surface / footer) | M067 / SDD-045 | shipped verbatim (lockstep-linted) |

### The daemon (`scripts/operator/code-console-api.py`)
Read-only HTTP server on an unused port (env `CODE_CONSOLE_API_BIND`/`_PORT`), modelled on
`sessions-api.py` + `lm-status-operability-api.py`:
- `GET /webapp/` → serves `webapp/code-console/index.html` with the `X-Sovereign-Module` header.
- `GET /api/code-console/sessions` → the M057 registry (read-only; empty when absent). Reuses
  `session-registry.py` so CLI + console never drift.
- `GET /api/code-console/stream` → SSE `session-step-advance` passthrough (optional; refresh fallback if absent).
- `POST /api/code-console/chat` → the **one sanctioned mutating POST** (the loopback chat proxy, same
  request/response contract as `/api/lm-status/chat`: body `{messages:[{role,content}]}` bounded to the
  last 8 turns, SSE frames `{type:'token'|'error'|'done'}`; 200 or 503, never fabricated). Reuses the
  D-22 proxy logic so the two never drift.
- Every other verb/route → **405/404** (read-only cockpit; R10212).

### The web (`webapp/code-console/index.html`)
Self-contained SPA carrying the full boilerplate (head metas, personalization pre-paint, palette vars,
M067 app-shell, SDD-045 control-surface, nav/a11y/responsive snippets, `SO_ASSIST`, §1g footer). The
three-pane grid: `.cc-rail` (left sessions) · `.cc-thread` (center) · `.cc-plan` (right), a `.cc-tabs`
top strip, a `.cc-composer` bottom bar with a device/model `<select>` + textarea + Send. Same-origin
fetch only; the ONLY POST is `/api/code-console/chat`. Honest-deferred panes render an explicit
deferred card (not blank — the D-21/D-22 "seeing all sections" lesson applied from birth: the console
renders its full three-pane scaffold even with every daemon offline).

## Goals

- A faithful claude.ai/code **layout + interaction shell** as a native sovereign cockpit panel.
- A **working composer** that talks to the box's own local LM (loopback SSE), streaming tokens.
- A **live session rail** off the real M057 registry.
- **Honest-deferred** center-persistence + Plan pane + repo chips — visible scaffold, explicit
  "no producer yet", never fabricated.
- Full cockpit compliance: app-shell, control-surface, palette, a11y/keyboard/responsive snippets,
  contract lint, surface-map registration, catalog + nav registration.
- **Always-visible** even with every daemon down (the SDD-111 de-minimization lesson, built-in).

## Non-goals (this increment)

- No conversation/message **persistence** producer (honest-deferred; a later SDD).
- No **Plan/artifact** producer (honest-deferred; a later SDD).
- No **repo-attach** producer (honest-deferred).
- No new web **mutation** beyond the sanctioned chat POST (R10212).
- No D-number assignment (ships as slug `code-console`, id `—`; operator may promote to a D-number).
- No change to D-22 or the existing chat proxy contract (the console reuses it, does not alter it).

## Open questions

| Q | Question | Proposed |
|---|---|---|
| Q-112-A | Does the composer drive the **local LM** (loopback chat) as the honest "code with your sovereign machine" interpretation? | **proposed: yes** — reuse the sanctioned `/api/...chat` SSE proxy on this daemon (same-origin), M075 device selector. Revisit at review. |
| Q-112-B | Left rail = the **M057 task-session** registry (not Claude-Code chat threads, which the box does not store)? | **proposed: yes, relabelled** — the rail shows real OS task-sessions; a Claude-Code-thread producer is a future SDD. |
| Q-112-C | Center **persisted thread** + right **Plan** pane + **repo chips** honest-deferred this increment (visible scaffold, "no producer yet")? | **proposed: yes** (SB-077) — deliver the shell + the live composer/rail now; wire persistence/plan/repo when producers land. |
| Q-112-D | Slug/placement: `code-console`, id `—`, group **Models & Compute** (adjacent to D-22)? Or a D-number + its own group? | **proposed: `code-console` id `—` in Models & Compute**; operator promotes to a D-number if desired. |
| Q-112-E | New daemon **port**? | **proposed: an unused port in the operator-API range** (e.g. 8140); confirm no collision at Stage 1. |

## Way forward (stages)

- **Stage 0 (this doc)** — SDD-112 + INDEX row + mandate E11.M112 (§1g). Recover band.
- **Stage 1** — `scripts/operator/code-console-api.py` (read-only + sanctioned chat proxy + sessions
  proxy) + `webapp/code-console/index.html` (full three-pane shell, live composer + rail, honest-deferred
  panes, all boilerplate) + `tests/lint/test_code_console_webapp_contract.py` + catalog + nav-snippet +
  surface-map + systemd unit registrations.
- **Stage 2** — full gate + Playwright (daemon-down: full three-pane scaffold visible, honest-deferred
  cards, zero page errors; daemon-up: live rail + streaming composer) + commit/push/draft PR.

## Cross-references

- SDD-062 / SDD-103 — D-22 loopback chat (the reused sanctioned POST + SSE contract).
- SDD-111 — the "seeing all sections / always-visible when offline" de-minimization lesson (built-in here).
- SDD-045 — control-surface; M067 — app-shell; M075 — SRP device topology; M057 — session registry.
- SDD-100 — parallel-session band scheme (recover band 100–199 / E11.M100–199).
