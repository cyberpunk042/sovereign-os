# Reference shapes

Per SDD-001 § 3, hybrid posture per artifact-type:

| Artifact | Reference shape | Rationale |
|---|---|---|
| SDDs (`docs/sdd/*.md`) | **Symbolic** (path-only) | CI guards path existence; SDDs evolve in place |
| Decisions log (`docs/decisions.md`) | **Symbolic + verbatim quote** | Decision text quotes the source phrase; ref-rot doesn't change interpretation |
| Handoffs (`docs/handoff/*.md`) | **Symbolic** | Point-in-time documents; acknowledge upstream evolution |
| Review ledgers (`docs/review/phase-N/`) | **Hard-pinned** | Audits are forensic; reference stability matters |
| Release tags | **Hard-pinned** | All cross-repo refs frozen at release time |

## Q-011 — final closure

The CI reference-guard workflow (planned at PR 10 or its successor) verifies:

- Every reference to `info-hub <path>` resolves at HEAD of `cyberpunk042/devops-solutions-information-hub`
- Every reference to `selfdef <path>` resolves similarly
- Broken references fail the build with file:line + reference shape + what's missing

Scope: `*.md` files in `docs/sdd/`, `docs/handoff/`, `docs/review/`, plus `docs/decisions.md`, `README.md`, `ARCHITECTURE.md`. Substrate-independent.
