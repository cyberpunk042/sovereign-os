# SDD-046 — root-ghostproxy endpoint binding (proxy mode disabled)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-03
> Closes findings: none (activates the fourth repo's consumption surface)
> Derived from: operator directive 2026-07-03 (verbatim, sacrosanct): *"Lets prepare root-ghostproxy for sovereign-os usage, we will use use the repo without the proxy mode enabled."*; root-ghostproxy PR #3 (merged 2026-07-03) `docs/sovereign-os-endpoint-usage.md`; SDD-001 (boundary contract); SDD-038 (cross-repo binding doctrine)

## Mission

`cyberpunk042/root-ghostproxy` — the ecosystem's system-AI-safety-setup
IaC (machine-level Claude Code + opencode safety envelope, agent brain,
integrity sentinel) — moves from **dormant** to **consumed** on
sovereign-os nodes. The consumption posture is **endpoint mode**: the
proxy/IPS half of root-ghostproxy (transparent L2 bridge, management
wifi, Suricata/PolarProxy modules) stays **disabled**, per the operator
directive verbatim above. sovereign-os binds the endpoint AI agent
safety foundation into the SAIN-01 lifecycle the same way it binds
selfdef: consume from the sister repo's own install surface, never fork
or re-derive it.

## Problem

SDD-001 explicitly scoped root-ghostproxy re-activation OUT of the
boundary contract ("Does NOT decide how root-ghostproxy re-activates").
The operator has now directed the re-activation. Without a binding SDD:

- The "dormant" rows across README / ARCHITECTURE / xrepo direction
  rot into falsehood the moment a sovereign node consumes the repo.
- The install step has no lifecycle placement — an operator would run
  root-ghostproxy's installer ad-hoc, outside the profile's declared
  hook chain, invisible to observability and drift detection.
- Nothing distinguishes the sanctioned posture (endpoint mode, proxy
  OFF) from an accidental full install: root-ghostproxy's own
  `--mode auto` promotes to `bridge` on multi-NIC hosts — and SAIN-01
  has two NICs (mgmt i226-v + data aqc113c), so auto-detection on the
  target WOULD enable the proxy half unless the mode is pinned.

## Required coverage

A1. The binding MUST consume root-ghostproxy through its own install
surface (`install.sh`), per its canonical guide
`docs/sovereign-os-endpoint-usage.md`. sovereign-os does not copy,
fork, or re-derive the safety envelope (SDD-001 authority table).

A2. The mode MUST be pinned explicitly: `--mode endpoint`. Never
`auto` (see Problem — SAIN-01's dual NICs auto-promote to bridge).
Canonical invocation: `./install.sh --profile base --mode endpoint`.

A3. Lifecycle placement: a `post_install_first_boot` hook (install,
gated) + a `post_install_recurrent` hook (weekly read-only drift
verify via `install.sh --check`). Same triple-gate convention as
`selfdef-sync.sh` (report-only default; explicit CONFIRM env to
apply; `SOVEREIGN_OS_DRY_RUN=1` honored; absent checkout = report,
not failure).

A4. Observability: both hooks emit Layer B metrics
(`sovereign_os_ghostproxy_endpoint_*`) so the cockpit/alert layer can
witness install state and drift without parsing logs.

A5. A lint contract test MUST lock the binding: hooks exist +
executable, profile wiring present, mode pinned to endpoint, env
overridability, report-only default.

## Goals

G1. A SAIN-01 node reaches "AI-agent-safety-governed" state through
the declared hook chain, not ad-hoc operator action.

G2. Drift between deployed endpoint-safety state and root-ghostproxy's
spec surfaces as a metric + `--check` report the operator sees.

G3. The proxy half stays re-enable-able by deliberate operator action
only (editing the hook env/profile) — never by auto-detection.

G4. Status rows across the repo's docs say the truth: root-ghostproxy
is active as an endpoint-mode consumption dependency.

## Non-goals

- Does NOT enable the proxy/IPS half (bridge / wifi / Suricata /
  PolarProxy). Operator directive: without the proxy mode.
- Does NOT replace selfdef. Composition per root-ghostproxy's usage
  doc: root-ghostproxy governs the AI-agent tool-call surface;
  selfdef governs the OS runtime-defense surface (Tetragon perimeter,
  notifiers, escalations). Both run on the node.
- Does NOT bake root-ghostproxy into the OS image at build time —
  the binding is a first-boot/lifecycle concern (the envelope
  installs into `$HOME`/user scope, which does not exist at image
  build). Revisit at Q-046-002 if image-baking becomes desirable.
- Does NOT author a typed-TOML mirror (SDD-038 shape) yet — the
  binding is one-directional consumption of an installer, not a
  taxonomy shared across repos. Revisit at Q-046-003 if
  root-ghostproxy state should feed compliance rollups.

## Open questions

| ID | Question | Resolution |
|----|----------|------------|
| Q-046-001 | Should the first-boot install hook be `mandatory: true` once the operator has run it successfully on real hardware? Today it is `mandatory: false` + absent-tolerant (checkout may not exist at first boot). | open |
| Q-046-002 | Should the root-ghostproxy checkout + endpoint install be baked into the image build (mkosi skeleton/postinst) instead of first-boot? Trade-off: reproducible image vs $HOME-scoped install semantics. | open |
| Q-046-003 | Should root-ghostproxy publish a typed manifest (SDD-038 shape) so `sovereign-osctl compliance status` gains a ninth instrument axis (AI-agent-envelope state)? | open |
| Q-046-004 | Which user's `$HOME` receives the envelope on SAIN-01 — root, the operator user, or both? root-ghostproxy is type=root by scope (not path); the hook currently installs for the invoking user's `$HOME`. | open |

## Way forward

### Binding shape (this SDD ships)

| Artifact | Purpose |
|---|---|
| `scripts/hooks/post-install/root-ghostproxy-endpoint-install.sh` | First-boot install hook. Triple-gate: report-only dry-run by default; `SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL=YES` applies; `SOVEREIGN_OS_DRY_RUN=1` forces report-only. Mode pinned `endpoint`; profile default `base` (env-overridable); checkout dir `SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR` (default `${HOME}/root-ghostproxy`). |
| `scripts/hooks/recurrent/root-ghostproxy-verify.sh` | Weekly read-only drift verify: `install.sh --check --profile base --mode endpoint`. OBSERVATION, not REMEDIATION (same contract as `audit drift`, D-018). |
| `profiles/sain-01.yaml` hooks wiring | `post_install_first_boot` entry (type `security`, `mandatory: false` per Q-046-001) + `post_install_recurrent` entry (type `security`, `schedule: weekly`). |
| `tests/lint/test_root_ghostproxy_binding_contract.py` | L1 lint locking A1–A5. |
| Status-row updates | README.md · ARCHITECTURE.md · docs/src/xrepo/direction.md · docs/src/architecture.md · SDD-001 repo table (additive pointer) · docs/decisions.md D-019. |

### Upstream contract (root-ghostproxy side, already merged)

root-ghostproxy PR #3 (merged 2026-07-03) ships the consumption guide
`docs/sovereign-os-endpoint-usage.md` + a 10/10 regression test
(`test-sovereign-endpoint-mode.py`) locking that `--mode endpoint`
excludes bridge+wifi for both `base` and `full` profiles while
retaining the safety foundation. This SDD's hooks call that locked
surface; drift on the upstream side fails upstream tests first.

### Sequencing

1. This PR: hooks + profile wiring + lint + status rows + D-019.
2. Operator-driven: real first-boot run on SAIN-01 hardware
   (sets `SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL=YES` deliberately).
3. Q-046-001/004 resolve from that empirical run → D-NNN entries.
4. Q-046-002/003 revisit post-Gate-5 alongside the compliance-
   instrument roadmap.

## Cross-references

- Operator directive verbatim + reading: `cyberpunk042/root-ghostproxy
  wiki/log/2026-07-03-sovereign-os-endpoint-prep-directive.md`
- Upstream consumption guide: `cyberpunk042/root-ghostproxy
  docs/sovereign-os-endpoint-usage.md`
- Boundary contract: `docs/sdd/001-cross-repo-boundaries.md`
- Cross-repo binding doctrine (selfdef precedent): `docs/sdd/038-cross-repo-binding-doctrine.md`
- Sister hook precedent: `scripts/hooks/recurrent/selfdef-sync.sh`
- Decisions log: `docs/decisions.md` D-019
