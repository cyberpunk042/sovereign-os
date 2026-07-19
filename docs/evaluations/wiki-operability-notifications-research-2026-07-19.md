# Research — wiki-operability AI mode + ntfy/Resend/Twilio notification layer

> Operator directive 2026-07-19 — verbatim, sacrosanct, logged BEFORE acting at
> [docs/standing-directives/2026-07-19-notification-wiki-operability-mode.md](../standing-directives/2026-07-19-notification-wiki-operability-mode.md):
>
> *"the ai will have a mode where it uses the wiki through python which calls
> make changes, insertions, deletions or whatever operability to the wiki
> aimed at or default one and it will allow to sent notifications of ntly and
> resend emails and even twillo, I think I have this in another
> project,devops-solutions-information-hub has some stuff but
> https://github.com/cyberpunk042/openfleet/tree/3d993f5c5c3ae78be41fa7040fc387f0dbe50c2e/fleet/infra
> has an example ntfy client anda gateway client and such.. and
> https://github.com/cyberpunk042/continuity-orchestrator has probably resend
> and twillio, for sms it will require a high priority, high urgency by
> default and it will be conifugrable and for if with no SMS at all then the
> starting point is resent require urgent and high priority. and the user
> will be able to use and play with those such as setting a global default
> override and only those set to static value modified remain as is. all my
> words matter, take the time to quote me sacrosanct and verbattim.
> Start with proper research"*
>
> This document is the "**Start with proper research**" deliverable. Design
> sketches below are agent-DRAFT proposals for operator review — nothing is
> built.

## Source 1 — sovereign-os itself (in-repo, already shipped)

**R228 / SDD-026 Z-6 notification fan-out** exists:

| Piece | What it does |
|---|---|
| `config/notify.toml.example` | Operator-owned channel config: `file` (JSONL audit, on by default) · `webhook` (generic POST) · `ntfy` (severity → ntfy `Priority` header "so phone notifications ring"). Secrets by env-var NAME indirection — "operator-supplied URLs / tokens NEVER live in-repo" (SDD-009). |
| `scripts/notify/dispatch.py` | Stdlib-only fan-out from R226 health-scan events; **dedup contract** (state file; fire only on first-seen or worse-severity transition — "does NOT spam"); `dispatch` / `test --channel` / `list-channels` / `state` verbs; rc 0/1/2. |
| `scripts/hooks/recurrent/notify-dispatch.sh` | Recurrent hook wiring. |
| `sovereign-osctl notify test --channel <name>` | Operator test surface. |

**Present**: ntfy, dedupe, severity mapping, env-var secret indirection, test verb.
**Absent**: Resend, Twilio, any priority×urgency gating model, any
global-default-override config semantics, any AI wiki-operability mode.

## Source 2 — openfleet `fleet/infra` @ `3d993f5c` (operator-cited; cloned, HEAD verified = cited commit)

- **`ntfy_client.py`** — the cited "example ntfy client": async httpx;
  `PRIORITY_MAP` five levels (`min/low/info/important/urgent` → ntfy 1–5);
  **`TOPIC_MAP` routes by priority** (`fleet-progress` / `fleet-review` /
  `fleet-alert`) — priority picks the *topic*, not just the header; supports
  `Tags` (emoji shortcodes) + `Click` URL. This topic-routing idea is absent
  from sovereign-os's ntfy channel.
- **`gateway_client.py`** — the cited "gateway client": WebSocket JSON-RPC to
  the OpenClaw Gateway (`ws://localhost:18789`) — `sessions.delete`,
  `sessions.compact`, `chat.send`, `sessions.patch`; token from vendor
  config. Relevant as the pattern for an AI-mode driving a live service
  rather than files.
- Siblings in the same dir: `config_loader.py`, `gh_client.py`,
  `irc_client.py`, `mc_client.py`, `plane_client.py`, `cache_sqlite.py` — a
  whole client toolbelt shape.

## Source 3 — continuity-orchestrator (operator-cited; cloned @ `29d4cf6`)

The strongest base for Resend + Twilio, exactly as the operator suspected
("probably resend and twillio" — confirmed):

- **`src/adapters/base.py`** — `Adapter` ABC: `is_enabled(context)` /
  `validate(context)` / `execute(context) → Receipt`; `ExecutionContext`
  carries action + routing + escalation stage + template.
- **`src/adapters/registry.py`** — `AdapterRegistry` with **mock_mode**
  (mock adapters for every channel → testable without credentials).
- **`src/adapters/email_resend.py`** — Resend: `RESEND_API_KEY` /
  `RESEND_FROM_EMAIL` env; graceful degradation when the package is absent;
  template first-`#`-line → subject; stage-themed styled HTML (6 escalation
  themes + urgency bar); channel→recipients routing
  (operator/custodians/subscribers); partial-delivery receipts; retryable
  classification; anti-spam headers.
- **`src/adapters/sms_twilio.py`** — Twilio: SID/token/from-number env;
  E.164 validation; segment counting (160/153); MMS media URL pre-validation
  with a hard-won carrier caveat (webp rejected by Canadian carriers, error
  12300 — "Twilio docs claim support"); retryable Twilio error-code table;
  body truncation at 480 chars.

Notable: continuity's escalation stages (OK → REMIND_1 → REMIND_2 →
PRE_RELEASE …) are an urgency ladder in practice — but it has **no
per-channel priority×urgency gate** either; channel choice is policy-driven.
The operator's gating rules are NEW design on top of these adapters.

## Source 4 — devops-solutions-information-hub ("has some stuff")

- **The wiki-through-python operability already IS this project's tool
  layer**: `tools/pipeline.py` (fetch / post 6-step validation chain /
  scaffold / crossref / evolve), `tools/gateway.py` (orient / query /
  contribute / template / move / archive), `wiki_log`, `tools/view`,
  `tools/mcp_server.py` (28 MCP tools) — changes, insertions, deletions with
  quality gates. "whatever operability to the wiki" exists here, per-wiki.
- **Cross-project awareness**: `tools/_cross_project_common.py`,
  `tools/sister_project.py`, `tools/cross_project_note.py` — seeds for the
  "aimed at" (target-wiki) parameter.
- **No ntfy / Resend / Twilio anywhere in its tools** (grep-verified; only
  incidental mentions in ingested articles).

## Source 5 — sister precedents

- **AICP** (`devops-expert-local-ai`): `aicp/core/health_report.py` takes an
  ntfy topic URL (`notify_url`) — ntfy precedent #3 in the ecosystem.
- **project-maintainer**: the "**aimed at or default one**" pattern already
  codified — every verb takes `--target <path>` / `--project <name>` via a
  registry, with policy per target (`language_policy`). The registry +
  per-target-policy shape maps directly onto "the wiki aimed at or default
  one".

## Gap analysis (what exists nowhere)

1. **Resend + Twilio channels** in any sovereign-os-reachable dispatcher.
2. **The priority × urgency gating model** — operator verbatim: *"for sms it
   will require a high priority, high urgency by default and it will be
   conifugrable"* and *"if with no SMS at all then the starting point is
   resent require urgent and high priority"*. Note BOTH dimensions appear,
   separately, in both clauses — priority and urgency are two axes, not one.
3. **The global-default-override config semantics** — verbatim: *"setting a
   global default override and only those set to static value modified
   remain as is"* — a global sweep that respects per-item static pins.
4. **The AI wiki-operability MODE** — a mode where the AI mutates "the wiki
   aimed at or default one" through python and notifies through the channel
   stack.

## Agent-DRAFT design sketch (for operator review — NOT built)

- **Notification layer home**: extend sovereign-os R228 (`dispatch.py` +
  `notify.toml`) — it already owns channels/dedupe/test verbs. Add `resend`
  + `twilio` channels adapted from continuity's adapters (env-var
  indirection per SDD-009; graceful degradation; mock/test mode per
  continuity's registry pattern; openfleet's priority→topic routing for
  ntfy).
- **Event model**: events carry `priority ∈ {low, normal, high}` ×
  `urgency ∈ {low, normal, high, urgent}` (two axes, per the verbatim).
- **Gating defaults** (all configurable):
  - `twilio`: deliver only when `priority ≥ high AND urgency ≥ high`
    (verbatim default).
  - `resend` when NO twilio channel is configured at all: starting point
    `urgency ≥ urgent AND priority ≥ high` (verbatim); when twilio exists,
    resend's own configured thresholds apply.
- **Global default override**: `[defaults]` block + per-channel-per-key
  `static = true` pins; applying a global override rewrites every non-static
  value; *"only those set to static value modified remain as is"*.
- **Wiki-operability mode**: a target-wiki registry (project-maintainer
  shape: named wikis + a default) whose operations dispatch to the target
  wiki's OWN python tools (info-hub: `pipeline post` / `gateway contribute`
  / `wiki_log`), with notification hooks on operation outcomes.

## Open questions (operator decisions needed before design lands)

1. **The READ-ONLY tension**: the standing directive "two ultimate
   solutions" declares info-hub *"READ-ONLY"* from sovereign-os + selfdef
   sessions, while this directive's mode "make[s] changes, insertions,
   deletions or whatever operability to the wiki aimed at or default one".
   Options: (a) the mode lives IN the info-hub (its tools already mutate
   itself; sovereign-os invokes them remotely as the info-hub's own
   channel); (b) an operator-sanctioned exception narrows READ-ONLY to
   "mutations only through the target wiki's own validated tool chain";
   (c) the "default" wiki is NOT the info-hub but a sovereign-os-local wiki.
   Which wiki is "the default one"?
2. **Where the notification layer lives**: extend R228 in sovereign-os
   (recommended above), or a shared library sister projects consume?
3. **Priority/urgency enums**: are the two axes + levels sketched above the
   shape you want, or do you want ntfy's five levels as the shared scale?

## Provenance

- openfleet clone HEAD `3d993f5c5c3ae78be41fa7040fc387f0dbe50c2e` — exactly
  the operator-cited commit; continuity-orchestrator HEAD `29d4cf6`.
- All greps/reads performed 2026-07-19 in this session; sources quoted are
  in-tree at those revisions.
