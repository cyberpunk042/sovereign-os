# AGENTS.md — sovereign-os (universal cross-tool agent contract)

> **DRAFT v1 — agent-authored 2026-07-19** per the operator's
> methodology-respect directive ("do we have the right setup for the AI
> supertool to respect the methodology ?" → "lets address those"). Operator
> revises/promotes. This file is a ROUTER over existing canon — it adds no
> new doctrine. Auto-loaded by agent harnesses that read AGENTS.md;
> Claude-Code-specific delta: [CLAUDE.md](CLAUDE.md).

## What this project IS

**Solution 1 of the two ultimate solutions** — the local AI workstation
runtime (cockpit, gateway, model orchestration, SRP Trinity, 21+ dashboards).
Independent of selfdef (Solution 2) yet combining with it; the info-hub is
the brain, NOT a third solution. Canonical statement (operator-verbatim):
[docs/standing-directives/two-ultimate-solutions.md](docs/standing-directives/two-ultimate-solutions.md).
*"Respect the projects."* — IPS features belong in selfdef; knowledge belongs
in the info-hub.

## Hard rules (every session)

| # | Rule | Canon |
|---|---|---|
| 1 | **Operator words are sacrosanct** — quote verbatim, never paraphrase; directives are logged verbatim under [docs/standing-directives/](docs/standing-directives/INDEX.md) BEFORE acting. | ecosystem-wide rule + the verbatim-preservation doctrine (SDD-037) |
| 2 | **Permission modes govern mutation** — default `manual` ("never act unreviewed"); destructive actions are confirm-gated + DANGER-flagged; the exec rail is dry-run until `SOVEREIGN_OS_ACTION_EXEC_LIVE=1`. | [config/permission-modes.yaml](config/permission-modes.yaml) + [2026-07-11-plan-mode-user-approval.md](docs/standing-directives/2026-07-11-plan-mode-user-approval.md) |
| 3 | **Stage gates are hard** — E0634 (M065, verbatim): *"No PR opens past a gate without operator sign-off."* Gate state: `sovereign-osctl approvals gates`. | [backlog/milestones/M065-…](backlog/milestones/M065-five-stage-gates-sg1-sg5-checkpoint-ritual.md) |
| 4 | **Wiki mutations ONLY through the target wiki's own tool chain** — `tools/wikiops.py`, dry-run default; pass `--stage` so the target wiki's methodology engine ALLOWED/FORBIDDEN gates the op; the info-hub is otherwise READ-ONLY from here. | wikiops + [2026-07-19-notification-wiki-operability-mode.md](docs/standing-directives/2026-07-19-notification-wiki-operability-mode.md) |
| 5 | **Secrets: names in configs, values in `/etc/sovereign-os/*.env`** — never a repo `.env`, never values in TOML. | [docs/src/operator-env-files.md](docs/src/operator-env-files.md) |
| 6 | **The web never arbitrarily mutates** (R10212) — the ONE write endpoint is the control-exec-api over allowlisted, validated, confirmed, audited control verbs. | [config/control-systems.yaml](config/control-systems.yaml) + sudoers preview |
| 7 | **Verify before claiming** — status claims inline the verifying command's output; regenerated artifacts (man pages, standing-directives page, app-shell embeds) go through their generators, never hand-edits. | repo lint suite (6900+ tests) is the enforcement |

## Read-order for a cold session

1. [context.md](context.md) — current position
2. [docs/standing-directives/INDEX.md](docs/standing-directives/INDEX.md) — operator mandates (verbatim)
3. [backlog/INDEX.md](backlog/INDEX.md) — milestones/epics/features state
4. [docs/src/sdd-catalog.md](docs/src/sdd-catalog.md) — the SDD doctrine index
5. `sovereign-osctl approvals gates` — where the SG1–SG5 ritual stands

## The AI supertool surfaces (methodology-respecting entry points)

| Intent | Surface |
|---|---|
| Operate a wiki ("aimed at or default one") | `sovereign-osctl`-adjacent `tools/wikiops.py` — `targets · ops · run --op X --stage S [--apply]` |
| Notifications (whole settings range) | `sovereign-osctl notifykit {show,set,global-override,trigger,test}` + the header ⚙ → Notifications overlay |
| Cross-system compatibility | `sovereign-osctl compat {list,compile,check,explain,why}` |
| Model lifecycle + eval | `sovereign-osctl models …` (+ `eval run <id> --benchmark throughput --min-tok-s N` as the promotion gate) |
| Approvals / gates | `sovereign-osctl approvals {pending,gates,key,approve,deny,defer,request}` |
