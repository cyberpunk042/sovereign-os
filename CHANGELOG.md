# Changelog

All notable changes to sovereign-os land here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
sovereign-os uses date-based phase markers rather than SemVer
until Stage 3+ when a public-distributable artifact lands.

Cross-references:
- Decisions: `docs/decisions.md` (every D-NNN entry)
- SDDs: `docs/sdd/INDEX.md` (every spec)
- Handoffs: `docs/handoff/` (cold-start anchors)

## [Unreleased] — Stage-2 onset (post-Gate-5)

### Added
- 4 new SDDs (012-022): brand-identity placeholder · installer-experience
  · decommission-testing-scope · secure-boot posture · observability
  bindings · ZFS root layout · kernel choice · reproducibility target ·
  CI infrastructure · distro-base lock-in · disk-encryption posture.
- 3 new profiles + 2 new mixins: `minimal` (VM baseline) · `developer`
  (polyglot toolchain) · `headless` (bare-metal server); mixins
  `role-headless`, `role-developer`, `role-server`.
- Substrate-prepare adapter for live-build (was mkosi-only).
- `orchestrate.sh run --dry-run` / `preflight` / `rewind <step>` /
  `skip <step>` operational verbs.
- 4 new pre-install hooks: preflight-network · preflight-tpm ·
  preflight-storage (plus friction-audit-spec was already shipped).
- 2 new recurrent hooks: security-update-check · backup-snapshot.
- Substantive plymouth + GRUB whitelabel overlays — operator-verbatim
  motd ('quality over quantity · honesty over cheats and lies')
  surfaced at boot in 3 surfaces (`/etc/issue`, plymouth splash,
  GRUB menu bottom).
- `sovereign-osctl` 4 new subverbs: `audit provenance`, `inference
  health`, `inference route`, `doctor v2` (profile-conditioned
  multi-section).
- in-toto SLSA v1 build-provenance.json + sha256sums.txt emission
  at step 09; operator-side verification via `audit provenance`.
- SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT propagation through mkosi-emit;
  KBUILD_BUILD_TIMESTAMP recorded in kernel build.
- ZFS encryption (SDD-022): aes-256-gcm on tank/context + tank/agents;
  passphrase + TPM2 PCR-7+11 binding default for sain-01 + headless.
- 16 systemd service units, ALL with defense-in-depth sandboxing
  (ProtectSystem / NoNewPrivileges / PrivateTmp / narrow ReadWritePaths).
- 21 Layer-B Prometheus textfile-collector metrics emitted across
  pipeline + recurrent + inference + perimeter + log-rotation +
  ZFS-health + snapshot + security-updates + image-build + image-sign.
- 2 Grafana JSON dashboard templates (`docs/observability/dashboards/`).
- `scripts/setup.sh` — one-command fresh-clone bootstrap.
- `scripts/git-hooks/pre-commit` — operator-side L1 + profile + L3
  fast-sample gate before every commit.
- `tests/qemu/scaffold.sh` — Layer 4 QEMU integration scaffold (gated
  on KVM + qemu + built image; SKIPs gracefully when absent).

### Test coverage
- Layer 1 (schema + lint): ~25 + 6 lint suites (was 3).
  New: systemd-unit-hardening, dashboard-json-valid, dashboard-metrics-
  lockstep.
- Layer 2 (unit): ~51 (was 51); +10 provenance-manifest shape.
- Layer 3 (nspawn): 35 substantive test scripts (was 7). Coverage:
  every lifecycle stage + every operator-facing CLI verb + every
  build step's gate path + reproducibility chain + image-sign +
  whitelabel overlays + inference router + first-login-assistant +
  decommission gates + during-install gates + new recurrent hooks +
  e2e DRY-RUN smoke across all 5 profiles.
- Layer 4 (QEMU): scaffold ready; substantive run gated on
  KVM-equipped self-hosted runner (Q10-B per SDD-020).
- Layer 5 (hardware): operator-driven on real SAIN-01.

### Fixed (10 real wiring bugs caught by L3 discipline)
1. `whitelabel/default.yaml` template paths
2. `orchestrate.sh` cmd_help sed truncation
3. `state_step_status` empty-string default
4. `logging.sh` log_file parent dir auto-create
5. `sovereign-osctl profiles list` shell-var-vs-export propagation
6. `friction-audit-spec.sh` bash -c profile_field scope
7. `test_decisions_log_sequence.py` regex never matched its target
8. `first-login-assistant.sh` unconditional hostnamectl in containers
9. inference start scripts `${VAR:=…}` defaults not exported
10. `sovereign-osctl doctor` missing load_profile

See `docs/src/tdd/bugs-caught.md` for the ledger + 3 distilled
cross-bug Learnings.

### Question closures (every PR-1-seed Q-X resolved/partial)
| Q | Status | Resolution |
|---|---|---|
| Q-001 | resolved | SDD-003 (substrate survey — mkosi primary) |
| Q-002 | partial  | SDD-004 (profile schema + mixins) |
| Q-003 | deferred-with-criteria | SDD-012 (brand identity placeholder) |
| Q-004 | resolved | SDD-007 (legal scope) |
| Q-005 | resolved | SDD-017 (ZFS root layout) |
| Q-006 | resolved | SDD-015 (secure-boot 3-level posture) |
| Q-007 | resolved | SDD-018 (kernel choice — dual strategy) |
| Q-008 | resolved | SDD-013 (installer experience — image-only) |
| Q-009 | operator-side | hardware procurement |
| Q-010 | resolved | SDD-020 (CI infrastructure — GHA only) |
| Q-011 | resolved | SDD-001 (cross-repo boundaries) |
| Q-012 | resolved | minimal + developer + headless profiles landed |
| Q-013 | resolved | SDD-016 (observability bindings) |
| Q-014 | resolved | SDD-014 (decommission testing scope) |
| Q-015 | resolved | SDD-019 (reproducibility target) |
| Q-016 | resolved | SDD-021 (distro-base — Debian 13) |
| Q-017 | resolved | SDD-011 (inference backend stack) |
| Q-018 | partial  | first-login-assistant + cloud-init pre-add path |
| Q-019 | partial  | sovereign-osctl + L3 management-surface gate |

Plus Stage-2+ sub-questions: Q15-B (SDD-022) + Q18-A (Round 30
short-circuit) resolved; Q15-A/C, Q16-A..D, Q18-B..C, Q22-A..C tracked.

## Pre-history

Foundation-phase PRs 1–10 landed:
- PR 1 — charter + decisions log + INDEX files
- PR 2 — cross-repo boundaries (SDD-001)
- PR 3 — documentation pipeline (SDD-002) + mdbook
- PR 4 — substrate survey (SDD-003 → Gate 2)
- PR 5 — profile schema (SDD-004 → Gate 3)
- PR 6 — initial profile stubs (SDD-005)
- PR 7 — Debian surface audit (SDD-006)
- PR 8 — whitelabel mechanism (SDD-007 → Gate 4)
- PR 9 — TDD harness spec (SDD-008)
- PR 10 — TDD harness bootstrap (SDD-009 → Gate 5)

See `docs/decisions.md` § D-001..D-003 for the pre-PR-4 charter
decisions.
