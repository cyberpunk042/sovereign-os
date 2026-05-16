# Handoff 003 — Operator-observability arc + Layer A/B/C symmetry (2026-05-16)

> Read this first if you are starting a new session on `sovereign-os`.
> Supersedes: `002-foundation-substantive-buildout.md` (Phase F close at Round 77).

## TL;DR — where things are

Rounds 78–92 (15 direct-to-main commits) closed the **operator-observability
arc**: the three SDD-016 layers now have first-class CLI surfaces. An
operator running on a `sovereign-os` install can read Layer A (JSONL),
inspect Layer B (Prometheus textfile), and act on rule-derived alerts
**without installing Grafana, jq, or Alertmanager** — they ship in
`sovereign-osctl` itself.

State at HEAD (`main` = `192a5d7`):
- **51 Layer B metrics** emitted across 9 build steps + 22 lifecycle hooks
- **3 Grafana dashboards** + 3-way CI contract (code ↔ inventory ↔ panels)
- **14 sovereign-osctl verb groups** (added: `metrics`, `alerts`, `journal`)
- **1 new recurrent hook** + systemd timer (`alerts-check`, hourly)
- **14 real bugs caught** by L3 discipline (running tally)
- **~52 L3 nspawn tests** · ~98 Layer 1 lint · ~62 Layer 2 unit · shellcheck
- All 5 profiles still pass DRY-RUN smoke + preflight matrix
- Install-runbook §5b now walks operators through Layer A/B/C end-to-end

## What to do FIRST in the next session

Resume the NEVER STOP `/goal` directive. Default cadence:
direct-push-to-main, substantive + tested + goal-traced per commit.

Likely next-most-valuable rounds (operator-priority order):
1. **SDD-023** — formalize the rules-engine + alerts contract (currently
   only documented in code comments + install-runbook §5b).
2. **Substantive build-step expansions** — step 06 (whitelabel-render)
   has a Python engine but the per-surface strategy coverage could deepen
   beyond template-render + skeleton-copy.
3. **A `sovereign-osctl history` verb** showing per-profile pipeline run
   history (consume the build-state JSONL + .prom timestamps).
4. **In-toto verifier** — step 09 emits a skeleton manifest; a Stage-2+
   verifier would cross-check the signature chain against operator PK.
5. **Headless profile hardening expansion** — role-server has auditd +
   fail2ban + chrony + unattended-upgrades; a Layer 2 unit test could
   pin the expected /etc/audit/rules.d/ + jail.local content as IaC.

## Session trajectory (Rounds 78–92)

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

- `scripts/sovereign-osctl:869` — `cmd_metrics` (Round 88)
- `scripts/sovereign-osctl:~1050` — `cmd_alerts` (Round 89; 6 rules in python heredoc)
- `scripts/sovereign-osctl:~1250` — `cmd_journal` (Round 91)
- `scripts/hooks/recurrent/alerts-check.sh` — meta-observability hook (Round 90)
- `systemd/system/sovereign-alerts-check.{service,timer}` — hourly cadence
- `docs/observability/dashboards/README.md` — 51-metric inventory (Round 87)
- `tests/lint/test_hook_layer_b_coverage.py` — gate against silent gaps
- `tests/lint/test_metric_inventory_lockstep.py` — code ↔ inventory contract
- `docs/src/install-runbook.md:225` — §5b Observability walkthrough

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
