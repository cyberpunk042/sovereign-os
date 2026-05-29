# M060 — operator deployment guide

End-to-end recipe to bring the M060 cross-repo mirror chain up on a
co-located host running both `selfdefd` (the IPS) and the sovereign-os
cockpit. Each dashboard (D-02 active-profile, D-12 rules, D-13 grants,
D-14 capability-tokens, D-15 sandboxes, D-16 audit-chain, D-17
quarantine, D-18 trust-scores) flips from `mirror: offline` (red
banner) to `mirror: online` (green banner) once you complete this
guide.

The complete chain (per direction of data flow):

```
operator                                     sovereign-os
  │                                              │
  ▼                                              │
selfdefctl <verb>                                │  (read-only)
  │                                              ▼
  │  POST /v1/<domain>/{issue|allocate|admit}   /api/d-NN/snapshot
  ▼                                              │
selfdef-daemon API                               ▼
  │  persists /var/lib/selfdef/<domain>.json    sovereign-os reader
  │                                              │ scripts/mirror/selfdef-<domain>-mirror.py
  ▼                                              ▲
selfdef-daemon mirror-export loop                │
  │  atomic write every 30s                      │
  ▼                                              │
/run/sovereign-os/selfdef-mirror/<domain>.json───┘
```

## Companion guide — selfdef-side producer wiring

This document covers the **sovereign-os consumer side** of the M060
cross-repo chain. The **selfdef producer side** — what files selfdefd
publishes, how the cli-mirror systemd one-shot
(`selfdef-cli-mirror-emit.service`) feeds the daemon's prefer-resident
path, per-artifact onboarding verbs, and the daemon-side failure-mode
crib sheet — is documented at:

[`cyberpunk042/selfdef` → `docs/operator/m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)

Operators running BOTH halves of the system on the same host read both
guides — selfdef-side covers what gets written to
`/run/sovereign-os/selfdef-mirror/*.json` (the wire); sovereign-os-side
(this guide) covers what the cockpit does with those files (the
render). The two halves are bound by wire-shape contract tests on
**both sides**:

- selfdef: `crates/selfdef-daemon/tests/m060_cli_mirror_emit_unit_contract.rs` (and the per-domain tests in `mirror_export_loop`)
- sovereign-os: `tests/lint/test_m060_cross_repo_chain_contract.py` (per-domain producer→consumer fixtures × 11)

Drift on either side fails tests on **both** sides.

## Prerequisites

1. `selfdefd` built + installed (`cargo build --release -p selfdef-daemon`
   then deploy `target/release/selfdefd` to `/usr/bin/`).
2. `selfdefctl` built + installed (`cargo build --release -p selfdef-cli`
   then `/usr/bin/selfdefctl`).
3. sovereign-os api daemons installed (the `scripts/operator/*-api.py`
   set), serving the cockpit web + the `/api/d-NN/*` JSON endpoints.
4. `minisign` CLI installed for MS003 operator-signed verbs.

## Step 1 — enable the export in `/etc/selfdef/selfdef.toml`

```toml
[deployment]
selfdef_mirror_dir = "/run/sovereign-os/selfdef-mirror"
```

That's the only required knob. The daemon creates the directory at
startup if missing. The 8 published files
(`active-profile.json`, `rules.json`, `grants.json`,
`capability-tokens.json`, `sandboxes.json`, `audit.json`,
`quarantine.json`, `trust-scores.json`) appear as the corresponding
resident registries get populated.

Optional per-domain overrides (only if you've relocated the daemon's
persistent state — both the daemon writer and the API reader honor
the same env vars):

```bash
export SELFDEF_GRANTS_PATH=/srv/selfdef/grants.json
export SELFDEF_CAPABILITY_TOKENS_PATH=/srv/selfdef/capability-tokens.json
export SELFDEF_SANDBOXES_PATH=/srv/selfdef/sandboxes.json
export SELFDEF_AUDIT_PATH=/srv/selfdef/audit.json
export SELFDEF_RULES_PATH=/srv/selfdef/rules.json
export SELFDEF_QUARANTINE_PATH=/srv/selfdef/quarantine.json
export SELFDEF_TRUST_SCORES_PATH=/srv/selfdef/trust-scores.json
```

Restart `selfdefd` (`systemctl restart selfdefd`). The journal should
show:

```
INFO M060: mirror export enabled — 8/8 mirror domains
     (active-profile + rules + grants + capability-tokens + sandboxes
      + audit + quarantine + trust-scores, read-only)
```

## Step 2 — verify D-02 (always-published) goes live

D-02 publishes immediately at startup (the MS040 R09535 Private default
when no `/var/lib/selfdef/flex-profile.json` exists is the honest
value):

```bash
ls /run/sovereign-os/selfdef-mirror/active-profile.json
cat /run/sovereign-os/selfdef-mirror/active-profile.json | jq .
```

Open the D-02 dashboard in your browser. The mirror-status banner
should be **green**, "mirror: online", showing the active profile
(default Private) + envelope (`max authority L1Suggest · max trust Ring2`)
+ a last-update timestamp.

If D-02 stays red, check:
- `selfdef_mirror_dir` is writable by the daemon's uid.
- `selfdefd` is actually running (`systemctl status selfdefd`).
- The api daemon for D-02 is running and pointing at the same
  `/run/sovereign-os/selfdef-mirror` (sovereign-os side).

## Step 3 — populate the operator-issued domains

The 3 operator-issued domains (D-13, D-14, D-15) need at least one
entry before they flip from red to green (no fabricated empty-online
state — honest offline until the operator acts).

### D-13 grants

```bash
selfdefctl grants issue \
    --kind filesystem \
    --scope "/workspace/**" \
    --reason "smoke-test grant for the cockpit chain" \
    --profile careful \
    --actor "$(your-ms003-fingerprint)" \
    --ttl-seconds 3600 \
    --signature "$(minisign -Sm <payload> -s ~/.minisign/selfdef.key | tail -1)"
```

### D-14 capability-tokens

```bash
selfdefctl capability-tokens issue \
    --actor "$(your-ms003-fingerprint)" \
    --tool read-only-host --tool tests \
    --trust-ring ring2 \
    --authority-level l4_execute \
    --sandbox-tier A \
    --ttl-seconds 3600 \
    --signature "$(minisign -Sm <payload> -s ~/.minisign/selfdef.key | tail -1)"
```

### D-15 sandboxes

```bash
selfdefctl sandboxes allocate \
    --actor "$(your-ms003-fingerprint)" \
    --tier tier-a --ms032-tier 1 \
    --isolation host_seccomp \
    --tool rg \
    --capability-token-id "tok-$(...)" \
    --ttl-seconds 3600 \
    --signature "$(minisign -Sm <payload> -s ~/.minisign/selfdef.key | tail -1)"
```

Each command writes through the daemon API
(`POST /v1/<domain>/{issue|allocate}` → registry persist), and the
export loop publishes the snapshot within 30s. The corresponding
dashboard banner flips green.

## Step 4 — daemon-populated domains (D-12, D-16, D-17, D-18)

D-12 rules + D-16 audit-chain + D-17 quarantine + D-18 trust-scores
are populated by the daemon's own collector / append / detection /
scoring loops (not operator verbs). Their dashboards stay honestly
red until:

- **D-12**: the daemon's nft collector loop reads
  `nft list ruleset --json`, projects each rule into the
  `selfdef-rules-registry` 13-field RuleEntry shape, and the export
  loop publishes `rules.json`. The operator never appends through
  this surface — rules are installed via `selfdefctl + nft` at the
  IPS layer; the registry only CONSUMES the live nft state.
- **D-16**: a daemon-side authority decision, file/process/network
  event, or host snapshot closes a span and `selfdef-audit-registry`
  appends it to the SHA-256 chain (MS016 R03567 — append-only; the
  operator has NO mutation surface). Verify with
  `selfdefctl audit verify --tail 256` or `--full`.
- **D-17**: an MS042 declaration-vs-observed mismatch fires and the
  daemon calls `record_block` (auto-populated as Quarantined entries).
- **D-18**: the scoring loop calls `record_delta` after a tool
  execution / mismatch (auto-populated as ToolScoreEntry deltas).

To seed manually for testing:

```bash
# D-18 — admit a tool with a starting score (operator-signed)
selfdefctl trust-scores admit \
    --tool rg --declarer "$(your-ms003-fingerprint)" \
    --initial-score 750 \
    --signature "$(...)"
```

Operator overrides (release a quarantined entry; manually adjust a
trust score):

```bash
selfdefctl quarantine release <quarantine_id> \
    --actor "$(...)" --signature "$(...)"
selfdefctl trust-scores operator-delta \
    --tool rg --actor "$(...)" --reason operator_adjustment \
    --delta -50 --signature "$(...)"
```

## Step 5 — verify from the cockpit hub

Open `http://<host>:<master-dashboard-port>/webapp/` (the D-00 master).
The **M060 mirror producers** panel shows 8 tiles, one per dashboard,
with green/red status dots. Click any tile to drill into that
dashboard.

The routes table also shows per-route reachability + an on/off pill
for each toggleable dashboard, with per-row `copy: disable` / `copy:
enable` buttons that copy the right `sovereign-osctl dashboards
{enable|disable} <slug>` command to your clipboard.

## Step 6 — enable chain-health observability

Once the chain is publishing, deploy the chain-health proxy + alert
rules so a paged operator sees outages in real time rather than
discovering them next time they open the dashboard.

```bash
# 1. Install the chain-health api daemon unit
sudo cp systemd/system/sovereign-m060-health-api.service \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sovereign-m060-health-api

# 2. Deploy the Prometheus alert rules
sudo install -m 0644 \
    config/prometheus/alerts/m060-chain-health.rules.yml \
    /etc/prometheus/alerts/
# Add to /etc/prometheus/prometheus.yml under rule_files:
#   - /etc/prometheus/alerts/m060-chain-health.rules.yml
sudo systemctl reload prometheus
```

Once both are up:

```bash
# Verify the chain-health proxy is serving
curl -s http://127.0.0.1:8160/api/m060/health | jq .state

# Verify Prometheus picked up the rules
curl -s http://127.0.0.1:9090/api/v1/rules \
  | jq '.data.groups[] | select(.name == "m060-chain-health")'

# Verify the textfile metric is exporting
cat /var/lib/node_exporter/textfile_collector/sovereign-os-m060-health-api.prom
```

## Incident-response surface ladder

When a chain alert fires or the master-dashboard shows a degraded state,
walk these surfaces in order of "blast radius" — each works under a
different failure mode of the stack above it:

| Surface | Question it answers | Works when this is DOWN |
|---|---|---|
| master-dashboard chain-health banner | "what's the chain rollup state?" | — (operator's first glance) |
| master-dashboard mirror grid (per-tile) | "which mirror is in what state?" | — |
| `sovereign-osctl m060-health probe` | "what does the chain-health proxy see?" | master-dashboard, browser |
| `selfdefctl m060-doctor` | "is the filesystem-state OK on the host?" | **selfdefd daemon** (filesystem only) |
| `selfdefctl m060-metrics` | "what do the daemon's per-artifact counters say?" | **Prometheus**, sovereign-os api proxy |
| `selfdefctl m060-metrics --artifact <name>` | "is THIS specific publisher healthy?" | as above; focuses one row |
| Grafana M060 row | "what's the trend over the last N hours?" | — (needs Prometheus + Grafana up) |
| 8 Prometheus alerts (3 selfdef + 5 sovereign-os) | "page me when..." | — (3 AM unattended) |

The two CLI verbs (`m060-doctor` + `m060-metrics`) are the load-bearing
ones during incident response: they query selfdefd directly (no
Prometheus dependency, no sovereign-os daemon dependency) so they work
even when the rest of the observability stack is the unhealthy
component. Run them BEFORE chasing the alert if you're unsure whether
the alert source itself is healthy.

```bash
# Quick triage flow:
selfdefctl m060-doctor --json | jq .                       # filesystem state
selfdefctl m060-metrics                                    # daemon counters
selfdefctl m060-metrics --artifact <suspect>               # drill on one
```

## Troubleshooting

| symptom | cause | fix |
|---|---|---|
| All 10 mirrors stay red | `selfdef_mirror_dir` not set or daemon not running | check `journalctl -u selfdefd` for the "M060: mirror export enabled" line |
| D-16 stays red while D-13/14/15 are green | audit chain has zero entries (no decisions/events yet) — honest offline | run `selfdefctl audit verify --tail 256`; the chain populates as the daemon decides/observes |
| D-02 only stays red | flex-profile path mismatch | check `selfdef_flex_profile::DEFAULT_STATE_PATH` (`/var/lib/selfdef/flex-profile.json`) |
| D-13/D-14/D-15 stay red after `selfdefctl issue` | API daemon not running, or `SELFDEF_<DOMAIN>_PATH` mismatch between writer (API) + reader (export) | check both honor the same path |
| Mirror flips green then back to red | export loop crashed | check `journalctl -u selfdefd` for "mirror export: ... write failed" |
| Dashboard shows `mirror_status=online` but old data | snapshot stale | the export refreshes every 30s; check `captured_at` timestamp in the banner |
| TUI mirror always red on a host where 8/10 others are green | unreachable means the daemon is up but `selfdef-tui-mirror::canonical_snapshot` failed at startup — extremely unlikely; check `journalctl -u selfdefd | grep tui` | restart selfdefd, then file an issue with the journal output |
| CLI mirror red but others green | `selfdefctl` not on the daemon's PATH (the daemon shells out to it once at startup to introspect the clap tree) | install selfdefctl on the same host as selfdefd, then `systemctl restart selfdefd` to reprime the cache |
| chain-health banner says `unreachable` | sovereign-m060-health-api can't reach selfdefd | check `systemctl status sovereign-m060-health-api` and `journalctl -u sovereign-m060-health-api`; if the UNIX socket is set but missing, verify selfdefd is running |

### Alert runbook

The 5 Prometheus alerts in `config/prometheus/alerts/m060-chain-health.rules.yml`
each correspond to one chain-state failure mode. When a page fires, walk these
in order.

#### M060ChainOffline (critical)

**Meaning:** `/v1/m060/health` reported `state=offline` — zero mirror
artifacts present in `/run/sovereign-os/selfdef-mirror/`.

**Diagnosis:**

```bash
# 1. Is selfdefd running?
systemctl status selfdefd
# 2. Is the export configured?
grep '^selfdef_mirror_dir' /etc/selfdef/selfdef.toml
# 3. Did the export loop announce itself?
journalctl -u selfdefd --since "10 min ago" | grep "M060: mirror export"
# 4. Does the publish dir even exist + is it writable by selfdefd's uid?
sudo -u selfdef ls -la /run/sovereign-os/selfdef-mirror/
```

**Fix:** set `selfdef_mirror_dir` in `/etc/selfdef/selfdef.toml`,
`systemctl restart selfdefd`, wait 30s.

#### M060ChainUnreachable (critical)

**Meaning:** sovereign-m060-health-api could not reach selfdefd at
all — UNIX socket missing AND TCP fallback unset/failed.

**Diagnosis:**

```bash
# 1. Is selfdefd up?
systemctl status selfdefd
# 2. Does the UNIX socket exist + is it accessible from this user?
ls -la "${SELFDEF_SOCKET:-/run/selfdef.sock}"
# 3. If using TCP transport instead, are the env vars set in the
#    health-api unit drop-in?
systemctl cat sovereign-m060-health-api | grep -i 'SELFDEF_API_'
# 4. Try the endpoint by hand
curl -s --unix-socket /run/selfdef.sock http://localhost/v1/m060/health
```

**Fix:** restart selfdefd OR fix the SELFDEF_API_URL+SELFDEF_API_TOKEN
drop-in OR fix socket permissions so the health-api uid can read it.

#### M060ChainStale (warning)

**Meaning:** every artifact is present but the newest is older than 5
minutes. The export loop is stuck.

**Diagnosis:**

```bash
# 1. Check for repeated write failures (likely cause)
journalctl -u selfdefd --since "20 min ago" | grep "mirror export"
# 2. Confirm the mtime drift directly
ls -la --time=mtime /run/sovereign-os/selfdef-mirror/
# 3. Check if the daemon itself is wedged on something else
systemctl status selfdefd | head -8
journalctl -u selfdefd --since "20 min ago" | grep -iE "error|panic|deadlock"
```

**Fix:** `systemctl restart selfdefd`. If it recurs, investigate the
specific publisher reported in the journal warnings — likely a
permission or disk-space issue on the resident-store path.

#### M060ChainDegradedSustained (warning)

**Meaning:** the chain has been in `degraded` for > 30 minutes —
either some mirrors are persistently absent (operator hasn't
onboarded them) OR at least one published artifact fails JSON-parse.

**Diagnosis:**

```bash
# 1. Identify WHICH artifacts are problematic
curl -s http://127.0.0.1:8160/api/m060/health | jq '.artifacts[] | {artifact, present, parses_as_json}'
# 2. If any parses_as_json:false, inspect the file
cat /run/sovereign-os/selfdef-mirror/<artifact>.json | head -20
```

**Fix paths:**
- Missing operator-issued artifacts (grants/capability/sandboxes):
  the operator must `selfdefctl <verb> issue` at least one item.
- `parses_as_json: false` on a present artifact: this is a real bug.
  `systemctl restart selfdefd` to retry the publisher; if the corrupt
  JSON persists, file an issue against selfdef with the file contents
  + the journal output:

```bash
journalctl -u selfdefd --since "20 min ago" | grep -i "mirror export"
```

#### M060HealthApiSilent (critical)

**Meaning:** no `/api/m060/health` requests have been served in 5
minutes. Either the chain-health-api daemon is down OR nothing is
polling it.

**Diagnosis:**

```bash
# 1. Is the daemon running?
systemctl status sovereign-m060-health-api
# 2. Is something polling it (master-dashboard normally hits it every 30s)?
journalctl -u sovereign-m060-health-api --since "10 min ago" | head -10
# 3. Try the endpoint by hand
curl -sv http://127.0.0.1:8160/api/m060/health | head -20
```

**Fix:** `systemctl restart sovereign-m060-health-api`. If the daemon
is healthy but no consumer is polling, that's an operator-deployment
gap — either no dashboard is up, or the master-dashboard isn't
configured to poll this host.

#### M060CliMirrorChainDegraded (warning)

**Meaning:** the selfdef-side `selfdefctl cli-mirror doctor`
reports at least one of its 4 D-CLI sub-chain checks
(schema-version / resident-store / systemd-unit / published-mirror)
in WARN state. `selfdef_cli_mirror_doctor_worst_severity == 1`.

**Diagnosis:**

```bash
# 1. Get the per-check breakdown from the textfile metric.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_cli_mirror_doctor_severity
# 2. Operator-actionable fix line per failing check.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_cli_mirror_doctor_check_info
# 3. Or run the doctor live on the selfdef host:
ssh <selfdef-host> sudo selfdefctl cli-mirror doctor
```

**Fix:** the most common D-CLI warn is "resident-store absent"
because the operator hasn't started the producer one-shot. Kick it:

```bash
ssh <selfdef-host> sudo systemctl start \
  selfdef-cli-mirror-emit.service
```

See the selfdef-side
[`m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)
for the full producer-side runbook.

#### M060CliMirrorChainBroken (critical)

**Meaning:** the selfdef-side `selfdefctl cli-mirror doctor`
reports at least one of its 4 D-CLI checks in FAIL state.
`selfdef_cli_mirror_doctor_worst_severity == 2`. Structural break
— operator action required.

**Diagnosis:**

```bash
# Per-check fix line carries the right remediation.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_cli_mirror_doctor_check_info \
  | grep -v 'severity="0"'
```

**Fix:** depends on which check failed. Common causes:

* resident-store malformed JSON:
  ```bash
  ssh <selfdef-host> sudo rm /var/lib/selfdef/cli-mirror.json
  ssh <selfdef-host> sudo systemctl start \
    selfdef-cli-mirror-emit.service
  ```
* schema-version drift (operator running mismatched selfdefctl
  + selfdef-daemon versions): co-upgrade.
* systemd unit non-zero exit:
  ```bash
  ssh <selfdef-host> sudo journalctl -u \
    selfdef-cli-mirror-emit.service -n 50
  ```

See the selfdef-side producer guide for deeper context:
[`m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)

#### M060MirrorDomainChainDegraded (warning)

**Meaning:** the selfdef-side `selfdefctl m060-doctor` reports at
least one of the 6 mirror domains (D-02/D-13/D-14/D-15/D-17/D-18) in
WARN state. `selfdef_m060_doctor_worst_severity == 1`.

**Diagnosis:**

```bash
# Per-domain breakdown.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_m060_doctor_severity
# Operator-readable per-domain note.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_m060_doctor_domain_info
# Or live on the selfdef host:
ssh <selfdef-host> sudo selfdefctl m060-doctor
```

**Fix:** typical D-13/D-14/D-15 warn = operator hasn't issued any
grant/token/sandbox yet. Issue one to flip the domain online:

```bash
ssh <selfdef-host> sudo selfdefctl grants issue ...
ssh <selfdef-host> sudo selfdefctl capability-tokens issue ...
ssh <selfdef-host> sudo selfdefctl sandboxes allocate ...
# Confirm the m060-doctor timer is actually firing.
ssh <selfdef-host> sudo systemctl status selfdef-m060-doctor.timer
```

See [`m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)
for the full producer-side onboarding recipe per domain.

#### M060MirrorDomainChainBroken (critical)

**Meaning:** at least one mirror domain in FAIL state — resident
store exists but the daemon's mirror_export_loop hasn't published it
to `<mirror_dir>/<domain>.json`. The export loop is wedged for that
specific domain.

**Diagnosis:**

```bash
# Which domain is published_present=0?
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_m060_doctor_published_present \
  | grep ' 0$'
# Daemon journal for the wedge.
ssh <selfdef-host> sudo journalctl -u selfdefd \
  | grep "mirror export"
```

**Fix:**

```bash
# Restart the daemon to clear the wedge.
ssh <selfdef-host> sudo systemctl restart selfdefd
# Verify the export loop announces all domains on restart.
ssh <selfdef-host> sudo journalctl -u selfdefd --since "1 min ago" \
  | grep "M060: mirror-export loop running"
```

See [`m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)
for the per-domain mirror_export_loop architecture.

#### M060MirrorDomainObserverSilent (critical)

**Meaning:** `selfdef_m060_doctor_last_run_unix` is more than 5
minutes old. The `selfdef-m060-doctor.timer` has stopped firing.
**Per-domain observability signal is lost** — the chain may be
healthy, but other M060MirrorDomain alerts cannot fire to confirm.

**Diagnosis:**

```bash
ssh <selfdef-host> sudo systemctl status \
  selfdef-m060-doctor.timer
ssh <selfdef-host> sudo systemctl list-timers \
  | grep m060-doctor
ssh <selfdef-host> ls -l \
  /var/lib/node_exporter/textfile_collector/selfdef-m060-doctor.prom
ssh <selfdef-host> sudo journalctl -u \
  selfdef-m060-doctor.service -n 30
```

**Fix:**

```bash
ssh <selfdef-host> sudo systemctl restart \
  selfdef-m060-doctor.timer
ssh <selfdef-host> sudo systemctl start \
  selfdef-m060-doctor.service
```

#### M060CliMirrorObserverSilent (critical)

**Meaning:** `selfdef_cli_mirror_doctor_last_run_unix` is more than
5 minutes old (~5 missed ticks of the 60s timer cadence). Either
the `selfdef-cli-mirror-doctor.timer` is wedged / disabled, OR
node_exporter stopped exposing the textfile_collector. **The
D-CLI chain may be healthy — but we've lost the observability
signal**. Other D-CLI alerts (degraded / broken) cannot fire.

**Diagnosis:**

```bash
# 1. Is the timer running?
ssh <selfdef-host> sudo systemctl status \
  selfdef-cli-mirror-doctor.timer
# 2. Last fire + next-fire timestamps.
ssh <selfdef-host> sudo systemctl list-timers \
  | grep cli-mirror-doctor
# 3. Did node_exporter pick up the textfile?
ssh <selfdef-host> ls -l \
  /var/lib/node_exporter/textfile_collector/selfdef-cli-mirror.prom
# 4. Service log if the timer fired but the doctor failed.
ssh <selfdef-host> sudo journalctl -u \
  selfdef-cli-mirror-doctor.service -n 30
```

**Fix:**

```bash
ssh <selfdef-host> sudo systemctl restart \
  selfdef-cli-mirror-doctor.timer
ssh <selfdef-host> sudo systemctl start \
  selfdef-cli-mirror-doctor.service
```

If node_exporter is the gap (file missing from
textfile_collector), check `systemctl status prometheus-node-exporter`
and the `--collector.textfile.directory=` flag.

#### MS022SseGlobalQuotaApproaching (warning)

**Meaning:** the selfdef daemon's SSE subscriber count is more than
85% of the configured global cap (`selfdef_sse_subscribers_global_saturation > 0.85`)
for 5+ minutes. Operators reaching 100% saturation will see per-request
HTTP 429s on `/events/stream`.

**Diagnosis:**

```bash
# Current saturation + cap.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep -E "selfdef_sse_subscribers_global_(active|cap|saturation)"
# Which tokens are holding the most subscriber slots?
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep "selfdef_sse_subscribers_per_token{" | sort -t' ' -k2 -nr | head -10
```

**Fix:** rotate stale subscribers (browser refreshes leak slots until
the per-token map purge fires) OR raise
`[api].max_sse_subscribers` in `/etc/selfdef/selfdef.toml`:

```toml
[api]
max_sse_subscribers = 128  # default 64
```

Then `sudo systemctl restart selfdefd` to pick up the new cap.

#### MS022SseGlobalQuotaSaturated (critical)

**Meaning:** the global SSE cap is fully saturated; new subscribers
across ALL tokens are being refused with HTTP 429 for 2+ minutes.

**Diagnosis:**

```bash
# Active count at or above cap.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep -E "selfdef_sse_subscribers_global_(active|cap)"
# Recent 429s in the daemon journal.
ssh <selfdef-host> sudo journalctl -u selfdefd --since "5 min ago" \
  | grep -i "sse.*cap\|429\|GlobalCap"
```

**Fix:** likely a subscriber leak (clients not properly closing
connections). Restart the daemon to clear the leaked subscribers:

```bash
ssh <selfdef-host> sudo systemctl restart selfdefd
```

Then identify the leak source via the per-token saturated count
(the `MS022SsePerTokenQuotaSaturated` alert below covers the
per-token diagnostic path).

#### MS022SsePerTokenQuotaSaturated (warning)

**Meaning:** at least one token has reached the per-token SSE
subscriber cap (`selfdef_sse_subscribers_per_token_saturated > 0`)
for 5+ minutes. Subsequent `/events/stream` connections under those
tokens get HTTP 429.

**Diagnosis:**

```bash
# Identify which token fingerprint(s) are saturated.
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep "selfdef_sse_subscribers_per_token{" \
  | awk '$2 >= 8 {print}'    # 8 = compiled default per-token cap
# Cap value (may be operator-overridden).
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep selfdef_sse_subscribers_per_token_cap
```

The `token_fp` label is the privacy-preserving 8-hex-char prefix of
the SHA-256 of the bearer token (matches the daemon's `tracing`
output). Cross-reference with daemon logs to identify the operator
or service holding the saturated slots.

**Fix:** common causes:
- orphaned browser tabs holding SSE connections open → close them
- a runaway test loop → kill the loop and verify the per-token
  count drops within 30s
- legitimate operator demand → raise the cap in
  `/etc/selfdef/selfdef.toml`:

```toml
[api]
max_sse_subscribers_per_token = 16  # default 8
```

Then `sudo systemctl restart selfdefd`.

#### FourWatchdogWorstSeverityCritical (critical)

**Meaning:** the selfdef daemon's four-watchdog rollup gauge
(`selfdef_four_watchdog_worst_severity >= 2`) reports CRITICAL for
2+ minutes. At least one of the 4 IPS-spine watchdogs (MS046
process / MS047 perimeter / MS044 tamper / MS048 config) has fired
its CRITICAL classification — an enforcement subsystem has degraded
to a state that requires immediate operator attention.

**Diagnosis:**

```bash
# Identify which watchdog fired (alert/ms/series labels).
curl -s http://localhost:9100/metrics 2>/dev/null \
  | grep 'selfdef_four_watchdog_severity{' \
  | awk '$NF == 2 {print}'
# Confirm against the daemon-side authoritative classifier.
selfdefctl alerts --json | jq '.alerts[] | select(.state=="critical")'
```

**Fix:** route by milestone family:
- `ms="MS046"` → process-watchdog runbook; check `selfdef-guardian.service`
  and the process-tree integrity
- `ms="MS047"` → perimeter engine; check Tetragon policies and
  the sovereign-perimeter contract
- `ms="MS044"` → tamper detection; check filesystem-integrity baselines
- `ms="MS048"` → config watchdog; check `/etc/selfdef/selfdef.toml`
  drift and the config-baseline manifest

After the underlying watchdog returns to OK, the textfile observer
flips the rollup gauge back to 0 within 60s on the next timer fire.

#### FourWatchdogAnyWarn (warning)

**Meaning:** the four-watchdog rollup gauge equals WARN
(`selfdef_four_watchdog_worst_severity == 1`) for 5+ minutes — a
non-CRITICAL degradation in progress.

**Diagnosis:** same as the critical alert above but filter for
`state="warn"` in the JSON output:

```bash
selfdefctl alerts --json | jq '.alerts[] | select(.state=="warn")'
```

**Fix:** investigate before WARN escalates to CRITICAL. The 5-minute
window gives operators time to plan a graceful intervention.

#### FourWatchdogTextfileEmitFailed (critical)

**Meaning:** `selfdef-four-watchdog-doctor.service` is reporting
wrapper failure (`selfdef_four_watchdog_textfile_emit_failed > 0`)
for 5+ minutes. The wrapper at `/usr/share/selfdef/
four-watchdog-textfile.sh` could not produce the 4 gauges because
`selfdefctl` was absent, `jq` was absent, the daemon was unreachable,
OR the `/v1/alerts` JSON envelope was malformed.

**Honest-offline contract:** when this alert is firing, the operator
CANNOT trust the other `selfdef_four_watchdog_*` gauges to reflect
current state — they may be stale or fabricated. This alert ALWAYS
takes precedence over the rollup-severity alerts above.

**Diagnosis:**

```bash
# Check the doctor service's last run state.
systemctl status selfdef-four-watchdog-doctor.service
journalctl -u selfdef-four-watchdog-doctor.service --since '10 min ago'
# Sanity-check the wrapper's preconditions directly.
which selfdefctl jq
selfdefctl alerts --json   # must succeed and return {worst,alerts}
```

**Fix:** restore the wrapper's preconditions:
- Missing `selfdefctl` → reinstall the `selfdef` deb
- Missing `jq` → `sudo apt install jq`
- Daemon unreachable → `systemctl status selfdefd`,
  `journalctl -u selfdefd --since '10 min ago'`

#### FourWatchdogObserverSilent (critical)

**Meaning:** `selfdef-four-watchdog-doctor.timer` hasn't fired in
5+ minutes (`time() - selfdef_four_watchdog_last_run_unix > 300`).
The IPS-spine observability surface is silently degraded — the 4
watchdog severities cannot be trusted to reflect current state.

**Diagnosis:**

```bash
systemctl status selfdef-four-watchdog-doctor.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-four-watchdog.prom
# Confirm node_exporter's textfile_collector dir is writable by selfdef.
sudo -u selfdef test -w /var/lib/node_exporter/textfile_collector \
  && echo OK || echo "selfdef cannot write — chown/chmod the dir"
```

**Fix:**

```bash
sudo systemctl enable --now selfdef-four-watchdog-doctor.timer
# If the unit is failing — check logs and the textfile_collector
# dir ownership.
sudo chown selfdef:selfdef /var/lib/node_exporter/textfile_collector
sudo chmod 0755            /var/lib/node_exporter/textfile_collector
```

The threshold of 300s mirrors the M060 chain-stale and observer-silent
threshold — locked in the cross-surface threshold-lockstep contract
test for the four-watchdog producer pair (selfdef commits `7869a45` +
`a009b39`).

#### SelfdefModulesTextfileEmitFailed (critical)

**Meaning:** `selfdef-modules-textfile.service` is reporting wrapper
failure (`selfdef_modules_textfile_emit_failed > 0`) for 5+ minutes.
The wrapper at `/usr/share/selfdef/selfdef-modules-textfile.sh` could
not produce the `selfdef_modules_*` gauges because `selfdefctl` was
absent, `jq` was absent, the daemon was unreachable, OR the
`modules list --json` envelope was malformed.

**Honest-offline precedence:** when this alert is firing, the operator
CANNOT trust the other `selfdef_modules_*` gauges to reflect current
state. This alert ALWAYS takes precedence over the rollup alerts below.

**Diagnosis:**

```bash
systemctl status selfdef-modules-textfile.service
journalctl -u selfdef-modules-textfile.service --since '10 min ago'
which selfdefctl jq
selfdefctl modules list --json | jq 'length'   # must succeed
```

**Fix:** restore the wrapper's preconditions:
- Missing `selfdefctl` → reinstall the `selfdef` deb
- Missing `jq` → `sudo apt install jq`
- Daemon unreachable → `systemctl status selfdefd`,
  `journalctl -u selfdefd --since '10 min ago'`

#### SelfdefModulesObserverSilent (critical)

**Meaning:** `selfdef-modules-textfile.timer` hasn't fired in 5+
minutes (`time() - selfdef_modules_last_run_unix > 300`). The
module-catalog observability surface is silently degraded — the
per-category counts cannot be trusted to reflect current state.

**Diagnosis:**

```bash
systemctl status selfdef-modules-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-modules.prom
sudo -u selfdef test -w /var/lib/node_exporter/textfile_collector \
  && echo OK || echo "selfdef cannot write — chown/chmod the dir"
```

**Fix:**

```bash
sudo systemctl enable --now selfdef-modules-textfile.timer
sudo chown selfdef:selfdef /var/lib/node_exporter/textfile_collector
sudo chmod 0755            /var/lib/node_exporter/textfile_collector
```

The threshold of 300s mirrors the M060 + four-watchdog observer-silent
thresholds — locked across all 3 observability verticals.

#### SelfdefModulesCountLow (warning)

**Meaning:** `selfdef_modules_total < 100` for 10+ minutes. selfdef
ships 188+ modules at install time; a drop below this generous floor
suggests an incomplete deb install OR a corrupted
`/usr/share/selfdef/modules/` directory.

**Diagnosis:**

```bash
selfdefctl modules list --json | jq 'length'
ls /usr/share/selfdef/modules/ | wc -l
dpkg -l | grep selfdef
# Cross-check the per-category breakdown:
curl -s http://localhost:9100/metrics | grep selfdef_modules_by_category
```

**Fix:** depending on root cause:
- Incomplete install → `sudo apt install --reinstall selfdef`
- Corrupted dir → restore from backup OR reinstall the deb
- Intentional pruning (operator removed modules deliberately) →
  raise the threshold in `selfdef-modules-catalog.rules.yml`

## Project-boundary discipline (MS043 R10212)

- IPS state mutation lives in **selfdef only** (selfdefd + selfdefctl +
  /v1/ API).
- sovereign-os renders **READ-ONLY**. Webapp NEVER mutates IPS state.
  When you click a "copy: disable" or any dashboard "revoke" / "release"
  button, the webapp copies the right shell command to clipboard for
  you to paste — it never posts to selfdef.
- The export is one-directional: selfdef → `/run/sovereign-os/selfdef-mirror`
  → sovereign-os reads. There is no reverse channel.

See `context.md` § "Current arc (2026-05-28): M060 cross-repo mirror
producers — COMPLETE" for the per-domain registry crate map.
