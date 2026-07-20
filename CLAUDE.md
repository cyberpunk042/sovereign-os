# CLAUDE.md — sovereign-os (Claude Code delta)

> **DRAFT v2 — agent-authored 2026-07-20**, operator revises/promotes.
> Universal cross-tool contract + hard rules + read-order:
> **[AGENTS.md](AGENTS.md)** (read it first — this file only adds the
> Claude-Code-specific delta). Both files are ROUTERS over existing canon
> (standing-directives, SDD catalog, backlog, mdbook docs) — they add no new
> doctrine.

## Claude-Code-specific delta

- **Auto-loaded at session start** — this file + AGENTS.md close the gap
  where sovereign-os sessions previously relied on the agent happening to
  read [docs/standing-directives/](docs/standing-directives/INDEX.md).
- **Plan Mode + User Approval + QCFA + deliberate reasoning** are standing
  operator mandates for AI sessions here:
  [2026-07-11-plan-mode-user-approval.md](docs/standing-directives/2026-07-11-plan-mode-user-approval.md) ·
  [2026-07-11-qcfa-interactive-clarification.md](docs/standing-directives/2026-07-11-qcfa-interactive-clarification.md) ·
  [2026-07-12-deliberate-reasoning.md](docs/standing-directives/2026-07-12-deliberate-reasoning.md)
- **Generated artifacts have generators** — never hand-edit:
  `docs/src/standing-directives.md` + `docs/src/sdd-catalog.md`
  (`scripts/docs/gen-sdd-catalog.py`), `docs/man/*.1`
  (`scripts/docs/build-sovereign-osctl-manpage.sh`), app-shell embeds in
  `webapp/*/index.html` (`scripts/webapp/sync-app-shell.py --apply`).
- **New osctl verbs carry a chain**: dispatch + help text +
  `config/feature-coverage.yaml` accounting + man-topic ownership
  (`docs/man/sovereign-osctl-command-topics.json` + `.SS` sections) + —
  when exec-rail-wired — a `config/control-systems.yaml` entry,
  `EXPECTED_IDS` in its lint, and a sudoers-preview allowlist line.
- **Layer-1 lint is the law** — ~6900 tests; run the suites your change
  touches before pushing (the full run needs CI's dedicated job).

## Pending operator decisions (blocking go-live)

See [AGENTS.md](AGENTS.md) for the full list. The Claude-Code-specific items:

| # | Item | Claude-Code relevance |
|---|---|---|
| E | AGENTS.md / CLAUDE.md promotion (operator review of v2) | This file — the operator revises/promotes or strikes |
| G | ~~notifykit extraction to its own repo~~ **CANCELLED** — stays in-project | N/A |

## Operator-intent routing (delta rows; AGENTS.md has the surfaces table)

| Operator says… | Do |
|---|---|
| "log this" / a verbatim directive | New dated file under `docs/standing-directives/` + regenerate the catalog page |
| "where are the gates" | `sovereign-osctl approvals gates` (M065 SG1–SG5; E0634 is hard) |
| "operate the wiki" | `tools/wikiops.py run --op … --stage …` (dry-run default; the target wiki's engine gates the op) |
| "notify me / notification settings" | `sovereign-osctl notifykit …` or the header ⚙ → Notifications overlay |
| "is X compatible with Y" | `sovereign-osctl compat check --set …` |
