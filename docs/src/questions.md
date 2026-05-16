# Open questions

> **The canonical questions list is at**:
> [`docs/decisions.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/decisions.md).
> This page surfaces the table for the mdbook reader.

Q-001..Q-019 are the open design questions seeded at PR 1 +
PR 1's L0 limit-continuation addendum (info-hub PR #8). Each resolves
at a specific PR and produces a `D-NNN` entry in the decisions log.

| Q | Topic | Resolves at | Status |
|---|---|---|---|
| Q-001 | Substrate selection (live-build · mkosi · debootstrap · ostree · Nix · …) | PR 4 → Gate 2 | open |
| Q-002 | Profile inheritance model (single-parent · composition) | PR 5 → Gate 3 | open |
| Q-003 | Whitelabel brand identity (name · palette · logo) | deferrable past PR 8 | **deferred-with-criteria (SDD-012)** — placeholder contract specified; real brand lands as data when operator promotes |
| Q-004 | Legal scope (public-distributable vs internal) | PR 7/8 → Gate 4 | open |
| Q-005 | ZFS root layout details | Stage 2+ | open |
| Q-006 | Secure-boot posture | Stage 2+ | open |
| Q-007 | Kernel choice (stock · custom-tuned) | Stage 2+ | open |
| Q-008 | Installer experience (debian-installer · Calamares · custom TUI · image-only) | Stage 2+ | **resolved (SDD-013, 2026-05-16)** — image-only + cloud-init/preseed pre-supplied answers; no installer UI |
| Q-009 | SAIN-01 hardware procurement timeline | operator-side | open |
| Q-010 | CI infrastructure (GHA · self-hosted) | PR 3 + PR 10 | open |
| Q-011 | Cross-repo commit-pinning posture | PR 2 (partial) + CI-guard PR (final) | partial (per-artifact rule locked in SDD-001) |
| Q-012 | Future-profile timeline (`minimal` · `developer` · `headless`) | Stage 2+ | **partial** — `minimal` substantive body lands as Q-012 demonstration; `developer` + `headless` remain reserved |
| Q-013 | Observability bindings | Stage 2+ | open |
| Q-014 | Decommission / wipe testing scope | PR 9/10 | **resolved (SDD-014, 2026-05-16)** — gates tested in Layer 3; destruction in Layer 5 only (operator-driven) |
| Q-015 | Reproducibility target | PR 4 (substrate constrains) | open |
| Q-016 | Distro-base reconsideration ("Debian-as-Ark") | PR 4 → Gate 2 | open |
| Q-017 | Inference-backend stack (LocalAI vs vLLM · llama.cpp · custom) | dedicated SDD post-PR-10 | open |
| Q-018 | First-login post-install assistant | Stage 2+ Stage 6 | open |
| Q-019 | Lifecycle-management surface (`sovereign-osctl` · systemd-units · hybrid) | Stage 2+ Stage 7 | open |
