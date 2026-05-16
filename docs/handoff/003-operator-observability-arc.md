# Handoff 003 — Operator-observability arc + Layer A/B/C symmetry (2026-05-16)

> Read this first if you are starting a new session on `sovereign-os`.
> Supersedes: `002-foundation-substantive-buildout.md` (Phase F close at Round 77).

## TL;DR — where things are

Rounds 78–102 (25 direct-to-main commits) closed the **operator-observability
arc** AND the **role-server hardening IaC arc**. Operators get:

- Three SDD-016 layers with first-class CLI surfaces (read Layer A
  JSONL, inspect Layer B Prometheus textfile, derive rule-based
  alerts) without Grafana / jq / Alertmanager
- Five hardening drop-ins (auditd / fail2ban / unattended-upgrades /
  sshd / pwquality) deployed by a profile-aware hook with idempotency,
  drift detection, and DEST_PREFIX support for chroot/image-build flows

State at HEAD (`main` = `f66b5cc`):
- **56 Layer B metrics** (added `sovereign_os_meta_alert_by_metric` per Q23-B resolution)
- **3 Grafana dashboards** + 3-way CI contract (code ↔ inventory ↔ panels)
- **15 sovereign-osctl verb groups** (`metrics`, `alerts`, `journal`, `history` added; `audit` grew from 4 → 5 subverbs; `maintenance` expanded to 8 subverbs)
- **sovereign-osctl version 0.3.0** — "operator-observability + hardening complete" phase
- **1 new recurrent hook** + systemd timer (`alerts-check`, hourly)
- **15 real bugs caught** by L1/L2/L3 discipline
- **3 new SDDs**: SDD-023 (alerts contract) · SDD-024 (server + workstation hardening) · SDD-025 (observability CLI architecture)
- **4 new decisions**: D-015 (alerts) · D-016 (server hardening) · D-017 (workstation hardening) · D-018 (in-toto --deep + audit drift)
- **4 L2 schema contract gates**: alerts (Q23-A) · audit drift · version --json (R64) · status --json (R83)
- **~56 L3 nspawn tests** · ~110 Layer 1 lint · ~80 Layer 2 unit · shellcheck
- All 5 profiles still pass DRY-RUN smoke + preflight matrix
- Install-runbook §5b walks operators through Layer A/B/C end-to-end
- config/server/README.md + config/workstation/README.md walk operators
  through the override surfaces
- SDD-007 7-strategy whitelabel taxonomy: 7/7 strategies implemented +
  7/7 test-pinned (R122)
- SDD-023 Q23-A,B RESOLVED · SDD-024 Q24-C,D RESOLVED (Q24-A,B + Q23-C,D
  open with documented recommendations)

## What to do FIRST in the next session

Resume the NEVER STOP `/goal` directive. Default cadence:
direct-push-to-main, substantive + tested + goal-traced per commit.

Items from the original priority list (resolved this arc):
- ✅ SDD-023 alerts contract (R94)
- ✅ Headless hardening IaC (R96-102) — all 5 drop-ins + L1 + L3 +
  live-apply path + DEST_PREFIX support
- ✅ Workstation hardening parallel (R104-105) — sain-01 + old-workstation
- ✅ In-toto --deep verifier (R106) — manifest ↔ sums ↔ disk triangle
- ✅ History verb (R107)
- ✅ SDD-007 strategy 7 must-not-touch (R109) — 7/7 strategy coverage

Likely next-most-valuable rounds (operator-priority order):
1. **SDD-025** — codify the observability CLI architecture (metrics /
   alerts / journal / history symmetry now has 4 parallel verbs, all
   sharing dir-resolution + show/list patterns; writing the contract
   keeps future additions consistent).
2. **Q24-C** — `/etc/issue.net` symmetric with `/etc/issue` when the
   whitelabel renderer learns the issue.net surface explicitly.
3. **Substantive step-06 (whitelabel-render) expansion** — operator
   has 7 strategies now; could land per-strategy operator-facing docs
   or expand the per-surface validators.
4. **Layer 4 QEMU substantive** — still gated on KVM-equipped runner;
   `tests/qemu/scaffold.sh` ready when a self-hosted runner lands.
5. **`sovereign-osctl drift` verb** — compares running system state
   vs profile expectations (auditd ruleset matches config/server/?
   sshd_config matches the drop-in? whitelabel surfaces unchanged?
   model catalog matches manifest?).

## Session trajectory (Rounds 78–102)

| Round | Surface | Description |
|---|---|---|
| 78–84 | (Phase F closer) | Round-84 self-test gate + 13th bug caught (live-build-emit non-reproducibility) |
| **85** | pre-install | Layer B emit_metric in all 4 preflight hooks (friction-audit-spec, preflight-network/storage/tpm) |
| **86** | post-install + lint | 14th bug (first-login-assistant missing Layer B) + `test_hook_layer_b_coverage.py` Layer-1 lint preventing the regression class |
| **87** | docs + lint | 51-metric inventory restructured into 7 labeled sections + `test_metric_inventory_lockstep.py` two-way contract |
| **88** | sovereign-osctl | New `metrics` verb: list / show / tail / health — 20-assertion L3 |
| **89** | sovereign-osctl | New `alerts` verb: 6-rule engine + --json mode — 13-assertion L3 |
| **90** | recurrent + systemd | `alerts-check.sh` hook + `sovereign-alerts-check.{service,timer}` (hourly) + `maintenance alerts-check` subverb — 15-assertion L3 |
| **91** | sovereign-osctl | New `journal` verb (Layer A surface): list / show / tail / errors — 21-assertion L3 |
| **92** | docs | install-runbook §5b — Layer A/B/C operator walkthrough (3 surfaces, 51 metrics, sovereignty posture) |
| **93** | docs/handoff | Handoff 003 — operator-observability arc cold-start signpost |
| **94** | sdd | SDD-023 alerts contract — 6 rules, 2 levels, 5 tunables, 5 test gates codified |
| **95** | docs/changelog | CHANGELOG Rounds 61-94 captured (Phase F + Phase G; 14-bug ledger) |
| **96** | post-install hardening | `config/server/{auditd, fail2ban, unattended-upgrades}` + `apply-server-hardening.sh` + L1 invariant lint + L3 hook gate |
| **97** | docs/decisions | D-015 (alerts contract) + D-016 (hardening IaC) entries — decisions log re-aligned with codebase reality |
| **98** | post-install hardening | SSH hardening drop-in (5th: `config/server/sshd.conf`) + L1 sshd invariants suite (no SHA-1, no cbc-mode, pubkey-only, no forwarding) |
| **99** | docs | `config/server/README.md` — operator-facing override surface + deactivation recipes |
| **100** | sdd | SDD-024 role-server hardening posture — 5-drop-in inventory + hook contract + override map + Q24-A..D |
| **101** | post-install hardening | pwquality drop-in (closes SDD-024 Q24-D) — minlen 14 + 4 classes + enforce_for_root; CIS Debian 12 § 5.4.1 baseline met |
| **102** | post-install + tests(L3) | DEST_PREFIX support + 25-assertion L3 (was 11): live apply, idempotency, drift detection, mode 0644, byte-identity, reload-skipped-in-prefix-mode |
| **103** | docs/handoff | Handoff 003 trajectory refresh through Round 102; priority list updated (✅ on closed items) |
| **104** | post-install hardening (workstation) | apply-workstation-hardening.sh + config/workstation/sshd.conf (sain-01 + old-workstation); 4 drop-ins (no fail2ban); L1 invariants pin deltas vs server posture |
| **105** | docs(sdd+decisions) | SDD-024 + D-017 + config/workstation/README updated for workstation hardening |
| **106** | sovereign-osctl audit | `audit provenance --deep` recomputes SHA256 on disk vs manifest digest; closes manifest↔sums↔disk triangle; 14-assertion L3 (was 9) |
| **107** | sovereign-osctl | New `history` verb: per-run summary derived from JSONL (list + show); 19-assertion L3 |
| **108** | tests(L2) + bug fix | 15th bug caught (Rule 6 reacted to meta_alerts_check_last_run_timestamp → self-reinforcing loop); fix + 9-assertion L2 schema contract test (SDD-023 Q23-A) |
| **109** | whitelabel renderer | SDD-007 strategy 7 (must-not-touch) implementation + 2 L2 tests; closes 7-strategy taxonomy |
| **110** | docs/handoff | Handoff 003 refresh through R109 |
| **111** | sovereign-osctl audit | `audit drift` verb (deployed vs source) + 10-assertion L3 + JSON mode |
| **112** | hardening + sdd | SDD-024 Q24-C RESOLVED: sshd Banner → /etc/issue.net (standard pre-auth convention) + issue.net legal-language line |
| **113** | sdd | SDD-025 codifies observability CLI architecture (4-verb pattern + dir resolution + exit codes + --json contract) |
| **114** | tests(L2) | audit drift --json schema contract (8 assertions; parallels alerts schema test) |
| **115** | docs/changelog | CHANGELOG Rounds 95-114 captured (Phase H) |
| **116** | docs/decisions | D-018 (in-toto --deep + audit drift; closes SDD-019 triangle) |
| **117** | docs/tdd | bugs-caught Learnings 4 + 5 (SDD-vs-code drift; test-pattern pluralization) |
| **118** | chore | version bump 0.2.0 → 0.3.0; phase = 'operator-observability + hardening complete' |
| **119** | docs/readme | README catch-up to Phase H state (15 verb groups · 55 metrics · 15 bugs · SDD-024/025) |
| **120** | tests(L2) | version --json (7-key) + status --json (8-key) schema contracts; 4 L2 schema gates now |
| **121** | recurrent + sdd | SDD-023 Q23-B RESOLVED: alerts-check hook now emits per-(metric,level) histogram via `sovereign_os_meta_alert_by_metric` gauge |
| **122** | tests(L2) | SDD-007 7-strategy taxonomy fully test-pinned (file-overlay + package-replacement + 7/7 meta-test) |

## Layer-A/B/C operator entry points (cold-start reference)

```sh
# Layer A — structured logs
sovereign-osctl journal {list|show <f>|tail [N]|errors}

# Layer B — metrics
sovereign-osctl metrics {list|show <name>|tail [N]|health}

# Layer B → derived alerts
sovereign-osctl alerts [--json]
sovereign-osctl maintenance alerts-check     # on-demand; or hourly timer

# Layer C — operator overview
sovereign-osctl {status [--json]|doctor|audit {friction|provenance|...}}
```

## Cross-repo state map (unchanged this arc)

| Repo | Status |
|---|---|
| `cyberpunk042/sovereign-os` | `main` 134 commits in (continues direct-push pattern) |
| `cyberpunk042/selfdef` | unchanged this arc |
| `cyberpunk042/devops-solutions-information-hub` | unchanged this arc |
| `cyberpunk042/sovereign-os-charter` (charter repo if any) | unchanged this arc |

## Repo signposts (file:line pointers for the new arc)

Observability surface (Rounds 87-92):
- `scripts/sovereign-osctl:869` — `cmd_metrics` (Round 88)
- `scripts/sovereign-osctl:~1050` — `cmd_alerts` (Round 89; 6 rules in python heredoc)
- `scripts/sovereign-osctl:~1250` — `cmd_journal` (Round 91)
- `scripts/hooks/recurrent/alerts-check.sh` — meta-observability hook (Round 90)
- `systemd/system/sovereign-alerts-check.{service,timer}` — hourly cadence
- `docs/observability/dashboards/README.md` — 53-metric inventory (Rounds 87, 96, 101)
- `tests/lint/test_hook_layer_b_coverage.py` — gate against silent gaps
- `tests/lint/test_metric_inventory_lockstep.py` — code ↔ inventory contract
- `docs/src/install-runbook.md:225` — §5b Observability walkthrough

Hardening surface (Rounds 96-102):
- `config/server/{auditd.rules, fail2ban-jail.local, unattended-upgrades.conf, sshd.conf, pwquality.conf, README.md}` — IaC drop-ins
- `scripts/hooks/post-install/apply-server-hardening.sh` — applier (DRY-RUN-safe; DEST_PREFIX-aware; profile-aware)
- `profiles/headless.yaml` § hooks.post_install_first_boot — registration
- `tests/lint/test_server_hardening_config.py` — 8-suite invariant gate
- `tests/nspawn/test_apply_server_hardening.sh` — 25-assertion hook gate
- `docs/sdd/{023, 024}-*.md` — contracts

## Standing rules (carried unchanged)

- **Direct push to `main`** for sovereign-os; no PR ceremony.
- Each commit substantive + tested + goal-traced.
- Never include the model identifier in any pushed artifact.
- Operator words sacrosanct — quote verbatim in SDDs.
- Layer 3 tests non-optional for any new script/verb.
- Bug ledger (`docs/src/tdd/bugs-caught.md`) tracks every real wiring
  bug L3 catches; running tally now at 14.

## Operator verbatim (sacrosanct) re-stated

> "continue till we reach the point we have the whole series of scripts
> to generate and configure and build a custom image / custom OS and all
> the customization that is possible and even needed. to the point pre,
> during and post. all in Spec Driven Development and Test Driven
> Development."

> "Do not rush anything and do not minimize anything nor should you
> compress or conflate or hallucinate anything"

> "we do this clean and right and professional"

> "We want quality over quantity and honesty over cheats and lies.
> We do not want hacks, quick fixes, and shortcuts."

> "every word counts"

> "we always deliver IaC"

> "Reach our ultimate sovereignty"

## What this session arc produced

The OS-image-pipeline goal now satisfies operator-observability sovereignty:
**every byte that the build, install, and operate phases emit is
discoverable, readable, and actionable through `sovereign-osctl`
alone**. No Grafana, no Alertmanager, no jq, no third-party SaaS
required. Operators with Grafana get the convenience dashboards;
operators without get exactly the same authoritative data, surfaced
through the CLI. The contract is enforced at lint time (3 lockstep
gates) so it cannot silently drift.

The arc preserves the foundation rule: sovereign-os ships local-default,
phone-home-free, with every customization knob inspectable in code.
