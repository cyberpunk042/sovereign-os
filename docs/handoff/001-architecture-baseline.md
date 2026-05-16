# Handoff 001 — Architecture baseline (post-PR-2 checkpoint)

> Read this if you are starting a new session on `sovereign-os` after
> PR 2 has landed.
> Supersedes: none (first sovereign-os handoff anchor).
> Last updated: 2026-05-16.

## TL;DR — where things are at PR 2

- **Scaffold tier in progress** (PRs 1–3): PR 1 landed the charter +
  decisions log + INDEX files + LICENSE + .gitignore + README; PR 2
  (this) lands `ARCHITECTURE.md` + `docs/sdd/001-cross-repo-boundaries.md`
  + this handoff anchor; PR 3 lands mdbook + MCP template + first CI.
- **The boundary contract is locked** at SDD-001: sovereign-os
  CONSUMES-FROM info-hub; selfdef CONSUMES-FROM info-hub +
  sovereign-os; info-hub OBSERVES both. Reverse flows forbidden.
- **Reference shape**: hybrid per artifact-type (symbolic by default;
  hard-pin for audits + release tags). CI guard for reference rot
  lands at PR 3 or PR 10.
- **Q-011 partially resolved** (per-artifact rule defined in SDD-001);
  final closure at the CI-guard PR.
- **Open questions still seeded**: Q-001..Q-019. PR 2 surfaces a few
  PR-2-local Q-A..Q-D in SDD-001 (CI guard scope + naming + config
  shape + selfdef SDD version-pin).

## What to do FIRST in the next session

1. **Verify PR 2 merged cleanly**: `docs/sdd/INDEX.md` row 001
   updated to `status: accepted`; `docs/decisions.md` shows no
   regression; `ARCHITECTURE.md` at root accessible.
2. **Open PR 3** per Plan-agent (info-hub
   `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` § PR 3):
   - `docs/src/SUMMARY.md` (mdbook nav)
   - `book.toml` (mirroring selfdef)
   - `.github/workflows/mdbook-publish.yml`
   - `.mcp/config.template.json` (operator placeholders only)
   - `docs/sdd/002-documentation-pipeline.md` (publishing contract)
3. **Open the cross-repo-reference CI guard** as part of PR 3 (or
   defer to PR 10 per operator preference). The boundary contract in
   SDD-001 is its specification.
4. **After PR 3 merges → Stage Gate 1**: operator reviews PRs 1–3
   holistically; confirms structural foundation matches selfdef
   rhythm; authorizes Foundation tier (PR 4 substrate survey).

## Session trajectory — Scaffold tier

| PR | Status | Files |
|---|---|---|
| **PR 1** — repo skeleton + charter stub | merged | `LICENSE`, `.gitignore`, `README.md`, `docs/sdd/000-charter.md`, `docs/decisions.md`, `docs/sdd/INDEX.md`, `docs/handoff/INDEX.md`, `docs/review/INDEX.md` |
| **PR 2** — ARCHITECTURE.md + cross-repo refs | (this PR) | `ARCHITECTURE.md`, `docs/sdd/001-cross-repo-boundaries.md`, `docs/handoff/001-architecture-baseline.md` |
| **PR 3** — mdbook + MCP template | pending | `docs/src/SUMMARY.md`, `book.toml`, `.github/workflows/mdbook-publish.yml`, `.mcp/config.template.json`, `docs/sdd/002-documentation-pipeline.md` |

## Cross-repo state map (after PR 2)

| Repo | Status | Recent landings |
|---|---|---|
| **`cyberpunk042/sovereign-os`** (this) | active; Scaffold tier in progress | PR 1 (charter) + PR 2 (architecture) |
| **`cyberpunk042/devops-solutions-information-hub`** | active; L0 directive log + limit-continuation captured (PR #8) | PR #8 lands the L0 addendum + Q-017/Q-018/Q-019 surfacing |
| **`cyberpunk042/selfdef`** | active; Stage-2 anchored at SDD-010 (downstream of sovereign-os) | unchanged since PR #184 (sovereign-os arc-opening handoff) |
| **`cyberpunk042/root-ghostproxy`** | dormant | n/a |

## Standing rules (carried unchanged)

- Never minimize, conflate, hack, shortcut.
- Never `--no-verify`; never force-push to main; never include the
  model identifier in any committed/pushed artifact.
- Verbatim quoting of operator directives — never paraphrase the
  load-bearing ones.
- Stage gates are real: no PR opens past Gate N without operator
  sign-off.
- Always surface PR links to the operator when a PR opens (per the
  operator's 2026-05-16 standing rule).
- Push retries: exponential backoff (2s → 4s → 8s → 16s), up to 4
  attempts on network failures only (not on auth errors).
- After every push, ALWAYS create the corresponding PR as a draft if
  one doesn't already exist.

## Repo signposts

| Topic | Path |
|---|---|
| Charter | `docs/sdd/000-charter.md` |
| Cross-repo boundaries | `docs/sdd/001-cross-repo-boundaries.md` (this PR) |
| Architecture overview | `ARCHITECTURE.md` (this PR) |
| Decisions log | `docs/decisions.md` (D-001..D-003 + Q-001..Q-019) |
| SDD index | `docs/sdd/INDEX.md` |
| Handoff index | `docs/handoff/INDEX.md` |
| Review (audit) index | `docs/review/INDEX.md` |
| Plan-agent macro-arc | info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` |
| Operator directive verbatim | info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md` + `…-limit-continuation.md` |
| SAIN-01 milestone | info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md` |

## Open items (deferred-by-design)

| Item | Status | Where |
|---|---|---|
| CI reference-guard workflow | Pending (PR 3 or PR 10) | SDD-001 § 4 + Q-A/Q-B/Q-C |
| Q-011 final closure | Pending CI guard PR | SDD-001 § 5 |
| All Q-001..Q-019 | Open per their target PRs | `docs/decisions.md` |
