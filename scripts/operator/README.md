# `scripts/operator/` — Operator-Discoverable §1g/§1h Surface

Per operator §1g verbatim:

> "very clear and well defined documentation through and through which
>  follow the high standards"

Per operator §1h verbatim:

> "two ultimate solutions and their perfectioning and high UX/DX"

This directory is the home of **operator-facing modules**: every
script here is reachable from `sovereign-osctl <verb>`, ships as a
distinct verb in `sovereign-osctl help`, emits a Layer B metric
(SDD-016), and is enforced by at least one L1 contract lint under
`tests/lint/`.

## Module catalog (11 modules)

| Module | osctl verb | R-round | E11.M | §1g binding |
|--------|------------|---------|-------|-------------|
| [auth-tier.py](#auth-tierpy) | `auth-tier {list-tiers,registry,show,matrix,set}` | R450 | M7 | 6-tier auth ladder |
| [bashrc-install.sh](#bashrc-installsh) | `bashrc {install,uninstall,status,dump}` | R447 | M6 | autocompletes + aliases + menus |
| [global-history.py](#global-historypy) | `global-history {recent,summary,sources,delta}` | R448 | M5 | delta/differentials across 6 sources |
| [network-topology.py](#network-topologypy) | `network-edge {detect,opnsense,interfaces,nat-chain}` | R449 | M8 | multi-NAT / VPN bridge / OPNsense |
| [auth-tier.py](#auth-tierpy) | `auth-tier {list-tiers,registry,show,matrix,set}` | R450 | M7 | 6-tier auth ladder |
| [edge-firewall.py](#edge-firewallpy) | `edge-firewall {state,candidates,recommend,install-plan,install}` | R451 | M9 | workstation-side IPS alternative |
| [master-dashboard.py](#master-dashboardpy) | `master-dashboard {list,routes,collisions,render,health}` | R452 | M2 | reverse-proxy aggregator |
| [surface-map.py](#surface-mappy) | `surface-map {surfaces,modules,coverage,gaps,waivers}` | R453 | M3 | 8-surface delivery contract |
| [doc-coverage.py](#doc-coveragepy) | `doc-coverage {kinds,modules,scan,coverage,gaps}` | R454 | M1 | doc-through-and-through scanner |
| [anti-minimization-audit.py](#anti-minimization-auditpy) | `anti-minimization-audit {patterns,scan,module,cross-module,report}` | R456 | M11 | "do not minimize or settle for less" |
| [ux-design-audit.py](#ux-design-auditpy) | `ux-design-audit {dimensions,modules,audit,score,report}` | R457 | M10 | "thorough UX Design stage" |
| [compliance.py](#compliancepy) | `compliance {status,module,worst,history,snapshot}` | R458 | — | §1g/§1h dashboard aggregator |

## Standing conventions

Every script in this directory follows the same operator-discovery
conventions (enforced by L1 lint at `tests/lint/test_*_contract.py`):

- **Operator §1g verbatim preservation**: every script's docstring
  quotes the operator's actual words VERBATIM (the lint greps for
  specific phrases per script).
- **Layer B metric**: every script emits a Prometheus textfile counter
  `sovereign_os_operator_<name>_query_total{verb,...,result}` per
  SDD-016. `# HELP` and `# TYPE` lines per metric-inventory-lockstep.
- **Triple-gate on destructive ops**: mutating verbs require
  `--apply` + `--confirm-<verb>` (preview-by-default).
  Pattern shipped in R411 (decommission), reused in R450 (set),
  R451 (install), R452 (render), R458 (snapshot).
- **DRY_RUN safety**: both `SOVEREIGN_OS_DRY_RUN` (sovereign-wide)
  AND a per-module `SOVEREIGN_OS_<MODULE>_DRY_RUN` are honored.
- **`--json` + `--human` output**: every verb supports both formats
  via mutually-exclusive flags.
- **Operator-keys NEVER in-repo**: any API key / secret comes from
  an environment variable (NEVER a config file in the repo).
  Operator §1g sacrosanct directive.

## §1g/§1h compliance instrument suite

Four of these modules are the **§1g compliance instruments** — each
measures a different axis of operator standards:

- **R453 surface-map** — Are operator-facing modules shipping on
  enough of the 8 §1g surfaces (core/cli/tui/api/mcp/dashboard/
  webapp/service)?
- **R454 doc-coverage** — Are modules documented across the 6 doc
  surfaces (readme/sdd/helptext/metric-inventory/mandate-row/man-page)?
- **R456 anti-minimization-audit** — Does the codebase contain
  minimization patterns (todo-no-anchor, empty-stub, "for now",
  etc.) the operator wants tracked-and-closed?
- **R457 ux-design-audit** — Do modules meet the 6 UX-quality
  dimensions (action-budget, discoverable, recoverable, next-step,
  operator-named, readable-30s)?

The **R458 compliance** aggregator consolidates all 4 into one rollup
— the operator's single-command §1g state check
(`sovereign-osctl compliance status`).

---

## auth-tier.py

R450 (E11.M7). Per operator §1g verbatim:

> "a mode of access from no auth at all by default to basic auth to
>  advanced auth to social auth to enterprise auth and network level
>  access and etc."

6-tier auth ladder per-dashboard: `no-auth` → `basic` → `advanced` →
`social` → `enterprise` → `network-level`. Operator-overrideable via
`/etc/sovereign-os/auth-tier.toml`
(`SOVEREIGN_OS_AUTH_TIER_CONFIG` env-override).

```bash
sovereign-osctl auth-tier list-tiers      # enumerate 6 tiers
sovereign-osctl auth-tier registry        # which dashboard at which tier
sovereign-osctl auth-tier matrix          # upgrade matrix (largest gap first)
sovereign-osctl auth-tier set grafana-dashboard social \
    --apply --confirm-tier-set            # triple-gated mutation
```

---

## bashrc-install.sh

R447 (E11.M6). Per operator §1g verbatim:

> "the bashrc we can offer to configure it too and we can add our
>  autocompletes and aliases and manual / helps and menus"

Sentinel-bounded block pattern — edits OUTSIDE the sentinels survive
every install/uninstall cycle. Ships 10 operator-discoverable aliases
(`sosctl`, `soshelp`, `sosstatus`, `sosmodels`, `soshealth`,
`sosdoctor`, `sosthermal`, `soswatt`, `soshist`, `sosmorning`),
`soshelp-menu` quick-help function, and tab completion across 25+
top-level subcommands.

```bash
sovereign-osctl bashrc install            # idempotent install
sovereign-osctl bashrc status             # show installed block
sovereign-osctl bashrc dump               # print block to stdout
sovereign-osctl bashrc uninstall          # reversible (.sovereign-os-bak)
```

`SOVEREIGN_OS_BASHRC_PATH` env-override for zsh / macOS adaptation.

---

## global-history.py

R448 (E11.M5). Per operator §1g verbatim:

> "Some kind of global history too. tracking things happening, delta,
>  differentials... apt changes and operations, or any cli or tool
>  call I guess... more reliable and adapted than simply aggregating
>  the .bash_history's"

6-source taxonomy: `apt` (history.log) + `dpkg` (dpkg.log) + `shell`
(.bash_history with HISTTIMEFORMAT support) + `osctl`
(~/.sovereign-os/history/*.jsonl) + `events` (cross-cutting JSONL
state) + `modules` (selfdef + sovereign-os module events).

```bash
sovereign-osctl global-history recent --since 24h --limit 50
sovereign-osctl global-history summary       # per-source counts, 7d
sovereign-osctl global-history delta 2026-05-17T00:00Z
sovereign-osctl global-history sources       # known sources + status
```

Read-only — lint enforces only the metric-emit `write_text` call.

---

## network-topology.py

R449 (E11.M8). Dispatched as `network-edge` in `sovereign-osctl`
(distinct from the R359 NIC-level `network-topology` master-spec §8
surface). Per operator §1g verbatim multi-NAT topology (workstation
→ OPNsense → ISP → public) + VPN bridge across two LANs/WANs +
OPNsense state-awareness.

5-tier capability ladder: `absent` → `unreachable` →
`reachable-no-credentials` → `reachable-credentials-rejected` →
`full-api`. RFC 1918 + RFC 6598 (CGNAT) private-IP detection.
VPN bridge auto-detection by interface name (wireguard / openvpn /
tailscale).

```bash
sovereign-osctl network-edge detect          # full multi-NAT chain
sovereign-osctl network-edge opnsense status # 5-tier API capability
sovereign-osctl network-edge interfaces      # per-NIC state
sovereign-osctl network-edge nat-chain       # NAT layers from this host
```

Operator-named edge hardware preserved verbatim: Sharevdi Fanless
Firewall Mini PC + Intel J3710/N3710 + 4× i226-V + AES-NI.

API keys via `SOVEREIGN_OS_OPNSENSE_{HOST,API_KEY,API_SECRET,API_PORT}`
env (NEVER in-repo per operator standing rule).

---

## edge-firewall.py

R451 (E11.M9). Per operator §1g verbatim:

> "even if there isn't an Edge firewall its possible to install the
>  equivalent or even more advanced if we want on this machine if we
>  would be ready to pay the performance price"

Workstation-side IPS-class alternative + defense-in-depth layer.
4 install-class candidates (LOW → HIGH overhead):

1. **nftables-baseline** — kernel-firewall, negligible cost
2. **fail2ban** — log-reactive, low cost (~50 MB)
3. **crowdsec** — behavioral-ips, moderate cost (~200-400 MB)
4. **suricata** — full IDS/IPS, HIGH cost (1-2 CPU + 1-2 GB)

```bash
sovereign-osctl edge-firewall candidates                 # 4 options
sovereign-osctl edge-firewall recommend                  # upstream-aware
sovereign-osctl edge-firewall install-plan fail2ban      # dry-run
sovereign-osctl edge-firewall install fail2ban \
    --apply --confirm-install                            # triple-gated
```

Recommendation logic shells into R449 `network-topology.py` for
upstream state — when upstream is `absent`, bumps suricata priority.

---

## master-dashboard.py

R452 (E11.M2). Per operator §1g verbatim:

> "Maybe there can even be an option to add a reverse proxy nginx or
>  such to do a master dashboard which regroup all those of different
>  port under a single port and super-dashboard"

Reverse-proxy aggregator consolidating per-port dashboards under
a single super-port (default `:8000`,
`SOVEREIGN_OS_MASTER_DASHBOARD_PORT` env-override).

3 modes: `per-port-direct` / `reverse-proxied` /
`alternative-aggregator`. 3 backends each with dedicated renderer:
`render_nginx` / `render_caddy` / `render_traefik`.

6 default-aggregated dashboards:

```
trinity-pulse        :8081 → /pulse/
trinity-logic-engine :8082 → /logic/
trinity-oracle-core  :8083 → /oracle/
router               :8080 → /router/
grafana-dashboard    :3000 → /grafana/
metrics-textfile     :9100 → /metrics/
```

```bash
sovereign-osctl master-dashboard routes                   # show route table
sovereign-osctl master-dashboard collisions               # safety-check
sovereign-osctl master-dashboard render --backend nginx \
    --apply --confirm-render                              # triple-gated
sovereign-osctl master-dashboard health                   # probe upstreams
```

Render REFUSES on detected collisions (operator-discoverable;
aggregator never ships in broken state).

---

## surface-map.py

R453 (E11.M3). Per operator §1g verbatim:

> "Everything is not just core, not just cli, not just TUI, not just
>  API, not just tool and MCP but also Dashboards and Web Apps and
>  Services"

8-surface taxonomy, operator-named order:

```
1. core     2. cli         3. tui          4. api
5. mcp      6. dashboard   7. webapp       8. service
```

Per-module hand-maintained coverage table (surfaces are intentional
contracts, not observational state — operator-named waivers preserve
opt-outs with rationale).

```bash
sovereign-osctl surface-map surfaces                  # 8 §1g surfaces
sovereign-osctl surface-map coverage --module trinity # matrix
sovereign-osctl surface-map gaps --threshold 3        # below N surfaces
sovereign-osctl surface-map waivers --module trinity  # opt-out rationale
```

---

## doc-coverage.py

R454 (E11.M1). Per operator §1g verbatim:

> "very clear and well defined documentation through and through
>  which follow the high standards"

Auto-discovery doc scanner — greps the repo for module presence
across 6 doc surfaces:

```
1. readme            top-level README.md
2. sdd               docs/sdd/ chapter
3. helptext          sovereign-osctl cmd_help section
4. metric-inventory  docs/observability/dashboards/README.md
5. mandate-row       operator-mandate row
6. man-page          docs/man/
```

Docs ARE the source of truth — no hand-maintained truth table to
drift (unlike R453 surface-map which DOES hand-edit; surfaces are
contracts, doc presence is observational).

```bash
sovereign-osctl doc-coverage scan --module auth-tier  # live grep
sovereign-osctl doc-coverage gaps --threshold 3       # below N docs
sovereign-osctl doc-coverage coverage                 # full matrix
```

---

## anti-minimization-audit.py

R456 (E11.M11). Per operator §1g standing rule (VERBATIM):

> "If you think something is really already done, ask yourself if you
>  covered all angles and levels and layers and even if then improve
>  it. Do not minimize or settle for less."

> "We do not minimize anything."

Source-code-level + cross-axis minimization-pattern scanner. 8
operator-named patterns:

```
todo-no-anchor       TODO/FIXME without R-number/SDD anchor
empty-stub           Python pass-only function body
skipped-no-followup  "skipped"/"deferred" without ticket reference
surface-gap          Module below R453 surface-map threshold
doc-gap              Module below R454 doc-coverage threshold
mandate-todo         Mandate E11.Mx or E10.Mx row still TODO
minimize-phrase      "for now"/"minimize"/"placeholder"/"simplified"
partial-status       Mandate row status="partial" or "in-flight"
```

Bridges R453 + R454 for cross-module gap detection. Exit-code-2
RESERVED but UNUSED — audit explicitly never "fails" because
non-zero-exit would itself be minimization.

```bash
sovereign-osctl anti-minimization-audit patterns        # 8 patterns
sovereign-osctl anti-minimization-audit report          # one-screen
sovereign-osctl anti-minimization-audit cross-module    # both-axes
sovereign-osctl anti-minimization-audit module trinity  # per-module
```

---

## ux-design-audit.py

R457 (E11.M10). Per operator §1g verbatim:

> "everything will also need to go through a thorough UX Design stage
>  in order to be of quality"

6 operator-named UX dimensions, each with live auditor:

```
action-budget    reach goal in N (default 3) actions or fewer
discoverable     verbs in sovereign-osctl cmd_help
recoverable      destructive ops triple-gated (--apply + --confirm-)
next-step        verbs surface 'next_action'/'next:'/'Run:' hints
operator-named   §1g/§1h verbatim discipline (anti-fabrication)
readable-30s     help text 100..1500 chars, ≥3 lines
```

```bash
sovereign-osctl ux-design-audit dimensions         # 6 dimensions
sovereign-osctl ux-design-audit score              # 0..6 per module
sovereign-osctl ux-design-audit audit --module bashrc  # per-cell rationale
sovereign-osctl ux-design-audit report --threshold 5   # below N
```

---

## compliance.py

R458. §1g/§1h compliance dashboard aggregator. Consolidates
R453 + R454 + R456 + R457 into a single operator-discoverable view.

```bash
sovereign-osctl compliance status                  # all 4 instruments
sovereign-osctl compliance worst --limit 5         # top-N modules
sovereign-osctl compliance module trinity          # per-module rollup
sovereign-osctl compliance history                 # recent snapshots
sovereign-osctl compliance snapshot \
    --apply --confirm-snapshot                     # triple-gated record
```

Snapshots stored at `/var/lib/sovereign-os/compliance/snapshots.jsonl`
(append-only, `SOVEREIGN_OS_COMPLIANCE_OUT` env-override). Operator
can detect compliance improvement OR regression over time.

The aggregator eats its own UX dogfood: it reduces the operator
action-budget from 4 commands to 1, satisfying the R457 action-budget
dimension that it itself measures.
