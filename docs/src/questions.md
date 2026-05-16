# Open questions

> **The canonical questions list is at**:
> [`docs/decisions.md`](https://github.com/cyberpunk042/sovereign-os/blob/main/docs/decisions.md).
> This page surfaces the table for the mdbook reader.

Q-001..Q-019 are the open design questions seeded at PR 1 +
PR 1's L0 limit-continuation addendum (info-hub PR #8). Each resolves
at a specific PR and produces a `D-NNN` entry in the decisions log.

| Q | Topic | Resolves at | Status |
|---|---|---|---|
| Q-001 | Substrate selection (live-build · mkosi · debootstrap · ostree · Nix · …) | PR 4 → Gate 2 | **resolved (SDD-003, 2026-05-16)** — mkosi primary, live-build as ALT-A (substrate-agnostic content); both adapters shipped under `scripts/build/adapters/`; Q4-A..Q4-E sub-questions tracked in SDD-003 |
| Q-002 | Profile inheritance model (single-parent · composition) | PR 5 → Gate 3 | **partial (SDD-004, 2026-05-16)** — single-parent inheritance + composition via mixins; 5 profiles + 6 mixins shipped; schema validates raw + resolved at L1; Q5-A..Q5-E sub-questions tracked in SDD-004 (partial because some operator-driven workflows around forking/overlay are still future work) |
| Q-003 | Whitelabel brand identity (name · palette · logo) | deferrable past PR 8 | **deferred-with-criteria (SDD-012)** — placeholder contract specified; real brand lands as data when operator promotes |
| Q-004 | Legal scope (public-distributable vs internal) | PR 7/8 → Gate 4 | **resolved (SDD-007, 2026-05-16)** — `dfsg-only` legal compliance target; 7-strategy whitelabel taxonomy (all 7 implemented + 7/7 test-pinned at R122); legal-floor list enforced at render time (SDD-006) |
| Q-005 | ZFS root layout details | Stage 2+ | **resolved (SDD-017, 2026-05-16)** — tank/single pool, raid0 across dual NVMe-PCIe-5, 3 tiered datasets with explicit recordsize/compression/sync; durability via copies=2 on state-fabric |
| Q-006 | Secure-boot posture | Stage 2+ | **resolved (SDD-015, 2026-05-16)** — 3-level posture (none/shim/signed) per-profile; operator-supplied keys; preflight-tpm + 08-image-sign as the only gates |
| Q-007 | Kernel choice (stock · custom-tuned) | Stage 2+ | **resolved (SDD-018, 2026-05-16)** — dual strategy: sain-01 = kernel.org-stable custom Zen-5-tuned; old-workstation + minimal = substrate-default |
| Q-008 | Installer experience (debian-installer · Calamares · custom TUI · image-only) | Stage 2+ | **resolved (SDD-013, 2026-05-16)** — image-only + cloud-init/preseed pre-supplied answers; no installer UI |
| Q-009 | SAIN-01 hardware procurement timeline | operator-side | open |
| Q-010 | CI infrastructure (GHA · self-hosted) | PR 3 + PR 10 | **resolved (SDD-020, 2026-05-16)** — GitHub Actions only for foundation phase; self-hosted deferred (hardware-conformance only) |
| Q-011 | Cross-repo commit-pinning posture | PR 2 (partial) + CI-guard PR (final) | partial (per-artifact rule locked in SDD-001) |
| Q-012 | Future-profile timeline (`minimal` · `developer` · `headless`) | Stage 2+ | **resolved (3/3, 2026-05-16)** — all three slots filled: `minimal` (VM baseline) + `developer` (polyglot toolchain) + `headless` (bare-metal server with auditd/fail2ban/chrony) |
| Q-013 | Observability bindings | Stage 2+ | **resolved (SDD-016, 2026-05-16)** — 3-layer stack: JSONL logs (shipped) + Prometheus textfile collector contract (locked, emission Stage 2+) + sovereign-osctl + Grafana JSON templates (deferred). Local-default sovereignty. |
| Q-014 | Decommission / wipe testing scope | PR 9/10 | **resolved (SDD-014, 2026-05-16)** — gates tested in Layer 3; destruction in Layer 5 only (operator-driven) |
| Q-015 | Reproducibility target | PR 4 (substrate constrains) | **resolved (SDD-019, 2026-05-16)** — strong build-reproducibility (mkosi image + kernel + whitelabel + substrate emit) given pinned inputs; signed artifacts intentionally not cross-operator bit-identical |
| Q-016 | Distro-base reconsideration ("Debian-as-Ark") | PR 4 → Gate 2 | **resolved (SDD-021, 2026-05-16)** — Debian 13 (trixie) is the Ark; reconsideration criteria specified for operator-on-demand revisit |
| Q-017 | Inference-backend stack (LocalAI vs vLLM · llama.cpp · custom) | dedicated SDD post-PR-10 | **resolved (SDD-011, 2026-05-16)** — direct-stack architecture (vLLM + bitnet.cpp + llama.cpp, no unifying abstraction); router + 3 backends + 3 start scripts shipped; `sovereign-osctl inference health/route/start/stop/restart/logs` + per-tier Layer B metrics shipped; Q11-A..Q11-E sub-questions tracked in SDD-011 |
| Q-018 | First-login post-install assistant | Stage 2+ Stage 6 | **resolved (Round 67 + 86, 2026-05-16)** — assistant + cloud-init pre-add path shipped; sovereign-osctl assistant surface expanded to full/status/reset/list (R67); Layer B emission added in R86; 16-assertion L3 + idempotency + state-shape + force-rerun gates pass |
| Q-019 | Lifecycle-management surface (`sovereign-osctl` · systemd-units · hybrid) | Stage 2+ Stage 7 | **resolved (Round 68 + 88-91 + 107 + 111, 2026-05-16)** — hybrid shipped: sovereign-osctl 2000+ lines · 15 verb groups · 30+ subverbs · 16 systemd unit files; observability CLI surface (metrics/alerts/journal/history + audit drift + audit provenance --deep) codified in SDD-025; 37-assertion dispatch-surface L3 gate |
