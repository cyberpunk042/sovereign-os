# SDD-002 — Documentation pipeline + mdbook publishing + MCP config template

> Status: **accepted** (publishing contract locked by PR 3)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none (foundational)
> Derived from: charter (`docs/sdd/000-charter.md`); SDD-001 (cross-repo boundaries); Plan-agent macro-arc § PR 3

## Problem

PRs 1 and 2 landed the repo skeleton + charter + architecture + cross-repo boundary contract — all as Markdown in `docs/sdd/`, `docs/handoff/`, `docs/review/`, `docs/decisions.md`, `ARCHITECTURE.md`. The content is operator-readable on GitHub raw views, but:

- There's no **operator-facing rendered surface** (mdbook / website) where a fresh reader can navigate the project ergonomically.
- There's no **CI gate** publishing the docs automatically on merge to `main`.
- There's no **MCP configuration template** documenting how a developer working on this repo would hook into the wider four-repo MCP ecosystem (info-hub, selfdef, AICP).

PR 3 closes these three gaps:

1. mdbook layout under `docs/src/` mirroring selfdef's pattern (`docs/book.toml` + `docs/src/SUMMARY.md` + nav stubs that link to the canonical content where it lives).
2. `.github/workflows/mdbook-publish.yml` — CI workflow building the book on PR (validation) and publishing to GitHub Pages on push to `main` (deployment).
3. `.mcp/config.template.json` — documented template; operator copies to `.mcp/config.json` (gitignored) and fills in actual command paths.

## Required coverage

### 1. mdbook layout

Convention follows `cyberpunk042/selfdef/docs/`:

- `docs/book.toml` — mdbook config; navy theme; git-repository-url + edit-url-template pointing at this repo.
- `docs/src/SUMMARY.md` — mdbook navigation. Sections: Introduction · Architecture · Charter & discipline · Open questions · Decisions log · 10-PR foundation phase · Cross-repo boundaries · Profiles · Whitelabel · TDD harness · Lifecycle stages · Operator handbook (Stage 2+).
- `docs/src/intro.md` — entry page; "you want X → read Y" routing table.
- `docs/src/architecture.md` — navigation stub pointing to root `ARCHITECTURE.md`.
- `docs/src/charter.md` — navigation stub summarising `docs/sdd/000-charter.md`.
- `docs/src/questions.md` — Q-001..Q-019 table.
- `docs/src/decisions.md` — D-NNN summary table.

Substantive content for foundation/profile/whitelabel/TDD/lifecycle/operator-handbook sections lands in its gated PR (PR 4–10 + Stage 2+). The `SUMMARY.md` reserves the slots; missing pages produce mdbook warnings (not errors) at build time during the foundation phase.

### 2. Documentation-vs-internal-docs split

Following selfdef's pattern:

| Tree | Audience | Renders in mdbook? |
|---|---|---|
| `docs/src/` | Operator (end-user / developer building / extending the OS) | **Yes** |
| `docs/sdd/` | Agent + reviewer (design specifications, audit-grade) | No |
| `docs/decisions.md` | Agent + reviewer (audit trail) | Mirrored summary in `docs/src/decisions.md`; full doc not in book |
| `docs/handoff/` | Agent (session cold-start signposts) | No |
| `docs/review/` | Agent (audit phase ledgers) | No |
| `README.md`, `ARCHITECTURE.md` | Both (GitHub-rendered first; book has nav stubs) | Linked from book |

The split keeps the operator-facing book focused on running / building / extending the OS, while keeping SDDs / decisions / handoffs / audit ledgers as the agent's authoritative tree (consulted via raw GitHub or `git grep` workflows).

### 3. CI workflow specification

`.github/workflows/mdbook-publish.yml` (this PR):

- **Triggers**: `push` to `main` (paths `docs/**` or workflow file); `pull_request` to `main` (paths `docs/**`); `workflow_dispatch` (manual).
- **mdbook version pin**: pinned to `MDBOOK_VERSION=0.4.40` (env var; bumpable in one place).
- **Cache**: `~/.cargo/bin` keyed by mdbook version to avoid recompiling mdbook every run.
- **Build job**: runs `mdbook build` in `docs/`. Output to `docs/book/` (gitignored per `.gitignore`).
- **Deploy job**: only runs on `push` to `main` (gated by `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`). Uploads `docs/book` to GitHub Pages via `actions/upload-pages-artifact@v3` + `actions/deploy-pages@v4`.
- **Permissions**: `contents: read`, `pages: write`, `id-token: write` (least-privilege).
- **Concurrency**: single in-flight `mdbook-publish` group; cancels in-progress queued runs.

### 4. MCP config template specification

`.mcp/config.template.json`:

- Documents (via `_purpose` and `_invocation` keys; underscore-prefixed = documentation-only) the four MCP servers a developer might want: info-hub, selfdef, AICP, GitHub.
- Sovereign-os does NOT expose its own MCP server in this PR. A lifecycle-management MCP for sovereign-os is a **Q-019 question** — when that SDD opens, this template gets a real entry.
- The operator copies this template to `.mcp/config.json` (gitignored in `.gitignore`) and fills in actual command paths + env-var bindings. Secrets stay in env vars, never in the template or its copy.

## Goals

1. **Operator-facing surface ready** — mdbook builds and renders on every PR; publishes to GitHub Pages on merge to `main`.
2. **Discoverability** — fresh reader lands on the rendered book and finds the right doc in one click via the SUMMARY nav.
3. **No duplication of authoritative content** — book pages are navigation stubs linking to the canonical content; updates to `ARCHITECTURE.md` / `docs/sdd/*` don't require parallel updates in `docs/src/*` (except for table summaries).
4. **CI is non-blocking for non-doc PRs** — `paths:` filter ensures the workflow doesn't trigger on PRs that don't touch `docs/`.
5. **MCP ecosystem-aware** — developers know which sister-project MCPs are relevant (info-hub for baseline; selfdef for Stage-2 integration; AICP for Q-017 evaluation).

## Non-goals (this SDD)

- Does NOT author Stage-2+ operator handbook pages (build / install / manage / profiles / whitelabel). Those pages reserve slots in SUMMARY.md but stay TBD until their gated PR.
- Does NOT decide GitHub Pages setup (the repo's GitHub Settings → Pages → "Build and deployment" → "GitHub Actions" — operator-side toggle). The workflow assumes Pages is enabled; if not, the deploy job fails gracefully with a Pages error and the build job still verifies docs render.
- Does NOT ship the cross-repo reference-guard CI workflow (SDD-001 Q-A/Q-B/Q-C). That lands at PR 10 (TDD harness) — separate workflow scope.
- Does NOT decide on multiple mdbook themes / branding. Default navy theme mirrors selfdef. Whitelabel-aware book theming is Q-003-adjacent and defers.

## Open questions

- **Q-A** — Should the mdbook deploy on every push to `main`, or only on tagged releases? Trade-off: continuous-deploy serves real-time operator-readers but exposes WIP; tag-only is reproducible but stale.
- **Q-B** — Should missing pages (reserved in SUMMARY but not yet authored) produce mdbook errors (CI fail) or warnings? Plan-agent recommends warnings during foundation phase, errors post-Gate-5.
- **Q-C** — GitHub Pages or alternative (Cloudflare Pages, Vercel, self-hosted)? GHA + GH Pages is the lowest-friction option; alternatives revisit-able if needed.
- **Q-D** — Should the MCP template grow a real sovereign-os MCP server entry now (stub for future Q-019), or stay strictly template-only until Q-019 resolves? **Resolved by R286 / SDD-031** — sovereign-os does not run its own MCP listener (template stays template-only); instead a manifest-first aggregator (`sovereign-osctl mcp-aggregate`) emits a unified cross-repo tool catalog that MCP clients consume to wire both repos without an additional listener.

These can be resolved at Stage Gate 1 or deferred to PR 10 (the TDD-harness PR has the natural surface for CI conventions).

## Way forward

1. PR 3 (this PR): mdbook scaffolding + workflow + MCP template + this SDD.
2. PR 3 merges → **Stage Gate 1 fires**: operator reviews PRs 1–3 holistically. Confirms structural foundation matches selfdef rhythm. Authorizes Foundation tier (PRs 4–8).
3. PR 4 onwards fills in the substantive content (substrate survey, profile schema, profile stubs, whitelabel) — much of which references the mdbook nav slots reserved here.
4. Stage 2+ operator handbook pages fill in.

## Cross-references

- Charter: `docs/sdd/000-charter.md` (§ SDD+TDD discipline; § SFIF discipline)
- SDD-001 cross-repo boundaries: `docs/sdd/001-cross-repo-boundaries.md` (especially § 3 reference shapes — book stubs use symbolic refs)
- Plan-agent macro-arc § PR 3: info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- selfdef mdbook reference: `cyberpunk042/selfdef/docs/book.toml` + `docs/src/SUMMARY.md`
- selfdef CI reference: `cyberpunk042/selfdef/.github/workflows/ci.yml`
- R286 / SDD-031 cross-repo MCP-tool aggregator: closes Q-019 — `sovereign-osctl mcp-aggregate manifest` ships the unified catalog without a sovereign-os MCP listener; the SDD-002 template stays template-only.
