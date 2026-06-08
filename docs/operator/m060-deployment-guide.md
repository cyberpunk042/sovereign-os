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

#### SelfdefDaemonProcessTextfileEmitFailed (critical)

**Meaning:** `selfdef-daemon-process-textfile.service` is reporting
wrapper failure (`selfdef_daemon_process_textfile_emit_failed > 0`)
for 5+ minutes. Either selfdefd is not running, systemctl failed, or
`/proc/<pid>/` is inaccessible.

**Honest-offline precedence:** when this fires, do NOT trust the
other 7 process-state gauges. Always investigate this alert first.

**Diagnosis:**

```bash
systemctl status selfdef-daemon-process-textfile.service
journalctl -u selfdef-daemon-process-textfile.service --since '10 min ago'
systemctl status selfdefd
systemctl show -p MainPID --value selfdefd
```

**Fix:** restore preconditions:
- selfdefd down → `systemctl status selfdefd` + `journalctl -u selfdefd`
- systemctl failed → check D-Bus connectivity
- /proc/ inaccessible → check kernel hardening / namespace restrictions

#### SelfdefDaemonProcessObserverSilent (critical)

**Meaning:** `selfdef-daemon-process-textfile.timer` hasn't fired in
5+ minutes. Process-state gauges are stale.

**Diagnosis:**

```bash
systemctl status selfdef-daemon-process-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-daemon-process.prom
sudo -u selfdef test -w /var/lib/node_exporter/textfile_collector \
  && echo OK || echo "selfdef cannot write the textfile collector dir"
```

**Fix:**

```bash
sudo systemctl enable --now selfdef-daemon-process-textfile.timer
sudo chown selfdef:selfdef /var/lib/node_exporter/textfile_collector
sudo chmod 0755            /var/lib/node_exporter/textfile_collector
```

#### SelfdefDaemonProcessMemoryHigh (warning)

**Meaning:** `selfdef_daemon_process_memory_rss_bytes > 1 GiB` for
30+ minutes. selfdefd's defensive-daemon baseline is small; sustained
growth above 1 GiB suggests a leak or unbounded queue.

**Diagnosis:**

```bash
# Live RSS check.
ps -o pid,rss,vsize,comm -p "$(systemctl show -p MainPID --value selfdefd)"
# Per-thread memory if available.
cat /proc/"$(systemctl show -p MainPID --value selfdefd)"/status | grep ^Vm
# Look for repeated allocation log lines.
journalctl -u selfdefd --since '1 hour ago' | grep -i 'queue\|alloc\|leak'
```

**Fix:** depending on root cause:
- Genuine queue backlog → check upstream pressure
- Leak → `sudo systemctl restart selfdefd` (mitigation) + file an
  issue with the RSS curve from Grafana
- Legitimate load → raise the threshold in
  `selfdef-daemon-process.rules.yml`

#### SelfdefDaemonProcessFdExhaustionApproaching (critical)

**Meaning:** open FD count > 819 (80% of default 1024 ulimit) for
10+ minutes. FD exhaustion blocks new socket accepts and file opens.

**Diagnosis:**

```bash
# Current FD count.
ls /proc/"$(systemctl show -p MainPID --value selfdefd)"/fd | wc -l
# Current ulimit.
cat /proc/"$(systemctl show -p MainPID --value selfdefd)"/limits | grep 'Max open files'
# What kind of FDs?
ls -l /proc/"$(systemctl show -p MainPID --value selfdefd)"/fd | head -20
```

**Fix:**
- Raise ulimit: add `LimitNOFILE=4096` to a drop-in
  `/etc/systemd/system/selfdefd.service.d/limits.conf` then
  `systemctl daemon-reload && systemctl restart selfdefd`
- Investigate FD leak: which FDs dominate? Sockets / files / pipes?

#### SelfdefDaemonProcessRestartLoop (critical)

**Meaning:** `increase(selfdef_daemon_process_restart_count[10m]) >= 3`
for 1+ minute. selfdefd has restarted 3+ times in the last 10 minutes
— crashloop in progress.

**Diagnosis:**

```bash
journalctl -u selfdefd --since '15 min ago' | grep -E 'panic|exit|signal'
systemctl status selfdefd
# Check systemd's StartLimit*  — when it gives up, restarts stop.
systemctl show -p StartLimitBurst,StartLimitIntervalSec selfdefd
```

**Fix:** investigate the panic / OOM / config-load failure in the
journal, fix the root cause, then `systemctl reset-failed selfdefd`
followed by `systemctl start selfdefd` to re-arm the unit.

#### SelfdefApparmorTextfileEmitFailed (critical)

**Meaning:** `selfdef-apparmor-textfile.service` is reporting wrapper
failure for 5+ minutes. Kernel AppArmor absent, `/sys/kernel/security/
apparmor/profiles` unreadable, or wrapper preconditions broken.

**Honest-offline precedence:** when this fires, do NOT trust the
other AppArmor gauges.

**Diagnosis:**

```bash
systemctl status selfdef-apparmor-textfile.service
journalctl -u selfdef-apparmor-textfile.service --since '10 min ago'
ls -la /sys/kernel/security/apparmor/profiles
zgrep CONFIG_SECURITY_APPARMOR /proc/config.gz 2>/dev/null \
  || zcat /boot/config-"$(uname -r)" | grep CONFIG_SECURITY_APPARMOR
```

**Fix:** kernel AppArmor must be `=y` AND `apparmor=1 security=apparmor`
on the boot cmdline. If kernel lacks AppArmor, this alert reflects
reality — operators MUST switch to selinux OR an AppArmor-enabled
kernel.

#### SelfdefApparmorObserverSilent (critical)

**Meaning:** observer timer hasn't fired in 5+ minutes. AppArmor
state gauges are stale.

**Diagnosis:**

```bash
systemctl status selfdef-apparmor-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-apparmor.prom
```

**Fix:**

```bash
sudo systemctl enable --now selfdef-apparmor-textfile.timer
sudo chown selfdef:selfdef /var/lib/node_exporter/textfile_collector
```

#### SelfdefApparmorProfileNotLoaded (critical)

**Meaning:** `selfdef_apparmor_profile_loaded == 0` for the
selfdefd profile for 10+ minutes. selfdefd is running WITHOUT
AppArmor confinement — IPS defensive posture compromised.

**Diagnosis:**

```bash
aa-status 2>/dev/null | grep -i selfdef \
  || sudo cat /sys/kernel/security/apparmor/profiles | grep selfdef
ls /etc/apparmor.d/usr.bin.selfdefd
```

**Fix:**

```bash
# Reinstall + load the profile.
sudo cp /etc/apparmor.d/usr.bin.selfdefd /etc/apparmor.d/usr.bin.selfdefd
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.selfdefd
sudo systemctl restart selfdefd
# Verify.
aa-status | grep selfdefd
```

#### SelfdefApparmorProfileInComplainMode (critical)

**Meaning:** `selfdef_apparmor_profile_complain == 1` for the
selfdefd profile for 5+ minutes. Profile is loaded but only LOGS
violations — does NOT enforce. Operator likely flipped with
`aa-complain` for debugging and forgot to restore.

**Diagnosis:**

```bash
aa-status | head -20
sudo cat /sys/kernel/security/apparmor/profiles | grep selfdefd
```

**Fix:**

```bash
sudo aa-enforce /etc/apparmor.d/usr.bin.selfdefd
# Verify.
sudo cat /sys/kernel/security/apparmor/profiles | grep selfdefd
# Should print: /usr/bin/selfdefd (enforce)
```

This is the signature operator-drift hazard the AppArmor observer
was built to catch — silent posture degradation that no other
alarm fires on.

#### SelfdefAuthEventsTextfileEmitFailed (critical)

**Meaning:** auth-events wrapper failure for 5+ minutes.

**Diagnosis:**

```bash
systemctl status selfdef-auth-events-textfile.service
journalctl -u selfdef-auth-events-textfile.service --since '10 min ago'
# Check the selfdef user can read journal.
sudo -u selfdef journalctl -n 1 --facility=auth 2>&1 | head -3
```

**Fix:** add `SupplementaryGroups=systemd-journal` drop-in:

```bash
sudo systemctl edit selfdef-auth-events-textfile.service
# Add under [Service]:
#   SupplementaryGroups=systemd-journal
sudo systemctl daemon-reload
sudo systemctl restart selfdef-auth-events-textfile.service
```

#### SelfdefAuthEventsObserverSilent (critical)

Same shape as the other observer-silent runbooks; check the timer.

#### SelfdefAuthEventsBruteForceDetected (critical)

**Meaning:** > 20 login failures in the 5m rolling window for 2+
minutes. Brute-force attack in progress.

**Diagnosis:**

```bash
# Identify the attacking source IPs (sshd logs).
journalctl --since '10 min ago' --facility=auth | grep 'Failed password\|Invalid user' \
  | awk '{for(i=1;i<=NF;i++) if($i=="from") print $(i+1)}' | sort | uniq -c | sort -rn
# Check per-target user counts.
journalctl --since '10 min ago' --facility=auth | grep 'Failed password' \
  | sed 's/.*Failed password for //' | awk '{print $1}' | sort | uniq -c | sort -rn
```

**Fix:** block the source IPs:

```bash
# Option A: fail2ban.
sudo systemctl status fail2ban
sudo fail2ban-client status sshd

# Option B: direct nftables drop.
sudo nft add rule inet filter input ip saddr <IP> drop
# Persist via /etc/nftables.conf.

# Option C: sshd_config hardening — disable password auth entirely.
sudo sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' \
  /etc/ssh/sshd_config
sudo systemctl reload sshd
```

#### SelfdefAuthEventsSshInvalidUserAttempts (warning)

**Meaning:** > 5 ssh invalid-user attempts in 5m for 5+ minutes —
credential-guessing reconnaissance.

**Diagnosis:**

```bash
journalctl --since '15 min ago' --facility=auth | grep 'Invalid user'
```

**Fix:** PubkeyAuthentication-only is the strongest mitigation:

```bash
sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd
```

#### SelfdefAuthEventsSudoSpike (warning)

**Meaning:** > 10 sudo invocations in 5m for 5+ minutes.

**Diagnosis:**

```bash
journalctl --since '15 min ago' _COMM=sudo | grep -E 'COMMAND|PWD'
last -F | head -5      # recent operator sessions
```

**Fix:** investigate. Legitimate admin work, scripted deployment,
OR a compromised user — operator judgment call. If unexpected,
rotate the affected user's credentials.

#### SelfdefSystemdUnitsTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-systemd-units-textfile.service
journalctl -u selfdef-systemd-units-textfile.service --since '10 min ago'
which systemctl
```

**Fix:** systemctl/D-Bus availability are baseline requirements; if
they're broken, the host itself is in trouble.

#### SelfdefSystemdUnitsObserverSilent (critical)

Same shape as the other observer-silent runbooks.

#### SelfdefSystemdUnitFailed (critical)

**Meaning:** at least one selfdef-* systemd unit is in failed state
for 5+ minutes. Silent unit failure = downstream observability is
degraded.

**Diagnosis:**

```bash
# Identify failed units.
systemctl --failed --all 'selfdef-*'

# Per-unit forensics.
for u in $(systemctl --failed --no-legend 'selfdef-*' | awk '{print $1}'); do
  echo "=== $u ==="
  systemctl status "$u" --no-pager | head -20
  journalctl -u "$u" --since '15 min ago' | tail -20
done
```

**Fix:** depends on root cause. Common patterns:
- Operator drop-in misconfiguration → fix drop-in + reload
- Permission drift after manual chown → restore selfdef:selfdef
- Disk-full on textfile_collector → free space + retry
- Selfdefd binary missing/corrupt → reinstall the deb

```bash
sudo systemctl reset-failed 'selfdef-*'
sudo systemctl daemon-reload
sudo systemctl restart <failed-unit>
```

#### SelfdefSystemdUnitsCountLow (warning)

**Meaning:** `selfdef_systemd_units_total < 8` for 10+ minutes.
Incomplete deb install OR operator-disabled units.

**Diagnosis:**

```bash
systemctl list-units --all 'selfdef-*' | head -30
dpkg -l | grep selfdef
```

**Fix:** depending on root cause:
- Incomplete install → `sudo apt install --reinstall selfdef-daemon`
- Intentional disable → raise the threshold in the rules YAML

#### SelfdefListeningSocketsTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-listening-sockets-textfile.service
journalctl -u selfdef-listening-sockets-textfile.service --since '10 min ago'
which ss
ls -la /proc/net/tcp /proc/net/tcp6
```

**Fix:** ss is the modern default but optional; the wrapper falls back
to /proc/net parsing. If both are unavailable, kernel /proc is
restricted — investigate kernel hardening or namespace state.

#### SelfdefListeningSocketsObserverSilent (critical)

Same shape as the other observer-silent runbooks.

#### SelfdefListeningSocketsTcpCountHigh (warning)

**Meaning:** > 20 TCP listeners for 10+ minutes. Operator baseline
exceeded.

**Diagnosis:**

```bash
ss -ltn       # IPv4 TCP listeners
ss -ltn6      # IPv6 TCP listeners
# Per-process attribution.
sudo ss -ltnp
# Compare against the host's expected-listener baseline.
```

**Fix:** depending on root cause:
- Legitimate new service → adjust threshold in
  `selfdef-listening-sockets.rules.yml`
- Forgotten dev server → stop it (`systemctl stop <unit>` or kill PID)
- Post-exploitation backdoor → see SECURITY.md incident-response
  section. Block via nftables, rotate credentials, audit auth logs
  (selfdef_auth_events_* gauges)

#### SelfdefListeningSocketsZeroTcp (critical)

**Meaning:** zero TCP listeners for 5+ minutes. selfdefd's API
socket is always-on — zero = selfdefd wedged OR uninstalled.

**Diagnosis:**

```bash
systemctl status selfdefd
ss -ltn  # confirm zero listeners directly
selfdefctl status   # if works, the observer is wrong; if fails,
                    # selfdefd really is down
```

**Fix:**

```bash
sudo systemctl restart selfdefd
sudo journalctl -u selfdefd --since '15 min ago' | grep -iE 'panic|exit'
```

#### SelfdefDiskUsageTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-disk-usage-textfile.service
journalctl -u selfdef-disk-usage-textfile.service --since '10 min ago'
which du
```

**Fix:** du is part of coreutils; if absent, the host install is
broken. Reinstall via `apt install --reinstall coreutils`.

#### SelfdefDiskUsageObserverSilent (critical)

Same shape as the other observer-silent runbooks.

#### SelfdefDiskUsageVarHigh (critical)

**Meaning:** `selfdef_disk_usage_var_used_percent > 90` for 5+
minutes. IPS spine has < 10% headroom — observer wrappers + audit
chain will wedge soon.

**Diagnosis:**

```bash
df -h /var
du -sh /var/log/* /var/lib/* 2>/dev/null | sort -rh | head -10
# Per-systemd-journal size.
journalctl --disk-usage
```

**Fix:** depending on root cause:
- Journal growth → `sudo journalctl --vacuum-time=7d`
- /var/log/selfdef growth → see SelfdefLogHigh runbook below
- ZFS-no-quota loop → set per-dataset quota
- Genuine workload → expand /var filesystem OR mount
  /var/lib/selfdef on a larger volume

#### SelfdefDiskUsageVarApproaching (warning)

Early-warning. Same diagnosis pattern as VarHigh — just earlier.

#### SelfdefDiskUsageSelfdefLogHigh (warning)

**Meaning:** `selfdef_disk_usage_log_bytes > 5 GiB`. logrotate
failure or misconfigured retention.

**Diagnosis:**

```bash
ls -la /var/log/selfdef/ | head
cat /etc/logrotate.d/selfdef
journalctl -u logrotate.timer --since '24 hours ago' | grep -E 'error|fail'
```

**Fix:**

```bash
# Force logrotate to run now.
sudo /usr/sbin/logrotate -fv /etc/logrotate.d/selfdef
# Tighten retention if needed.
sudo sed -i 's/rotate [0-9]\+/rotate 7/' /etc/logrotate.d/selfdef
```

#### SelfdefTimeSyncTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-time-sync-textfile.service
which timedatectl
timedatectl status
```

**Fix:** if timedatectl is missing, install systemd via the host's
package manager.

#### SelfdefTimeSyncObserverSilent (critical)

Same shape as the other observer-silent runbooks.

#### SelfdefTimeSyncNotSynced (critical)

**Meaning:** `selfdef_time_sync_synced == 0` for 10+ minutes —
audit-trail timestamps silently unreliable.

**Diagnosis:**

```bash
timedatectl status
journalctl -u systemd-timesyncd --since '1 hour ago' | tail
journalctl -u chronyd --since '1 hour ago' | tail
```

**Fix:**

```bash
sudo timedatectl set-ntp true
sudo systemctl enable --now systemd-timesyncd
# OR if using chronyd:
sudo systemctl enable --now chronyd
sudo chronyc makestep
```

#### SelfdefTimeSyncNtpInactive (critical)

**Fix:**

```bash
sudo systemctl enable --now systemd-timesyncd
# OR
sudo systemctl enable --now chronyd
```

#### SelfdefTimeSyncDriftHigh (warning)

**Meaning:** RTC vs system drift > 60 seconds.

**Diagnosis:**

```bash
sudo hwclock --show
date
timedatectl status
```

**Fix:**

```bash
sudo hwclock --systohc   # Sync RTC to system (if system canonical)
sudo hwclock --hctosys   # Sync system to RTC (if RTC canonical)
```

#### SelfdefTimeSyncRtcLocalTz (warning)

**Meaning:** RTC in local TZ — DST transitions break correlation.

**Fix:**

```bash
sudo timedatectl set-local-rtc 0   # UTC = secure default
```

#### SelfdefKernelModulesTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-kernel-modules-textfile.service
ls -la /proc/modules /proc/sys/kernel/tainted
```

**Fix:** /proc is kernel-served; if unreadable, the host is in a
broken namespace state.

#### SelfdefKernelModulesObserverSilent (critical)

Same shape as the other observer-silent runbooks.

#### SelfdefKernelTaintedUnsigned (critical)

**Meaning:** unsigned kernel module loaded — rootkit signature.
PAGE-WORTHY. 1m for-window because rootkits are time-sensitive.

**Diagnosis:**

```bash
cat /proc/sys/kernel/tainted
dmesg | grep -iE 'taint|unsigned|module' | tail -30
lsmod
# Identify unsigned module via /sys/module/*/sig_id.
```

**Fix:** ISOLATE THE HOST IMMEDIATELY. See SECURITY.md
incident-response section. Snapshot memory (lime/avml), rotate
credentials, reimage from known-good baseline.

#### SelfdefKernelTaintedAny (warning)

**Diagnosis:**

```bash
cat /proc/sys/kernel/tainted
# Decode via https://www.kernel.org/doc/html/latest/admin-guide/tainted-kernels.html
```

#### SelfdefKernelModulesCountHigh (warning)

**Diagnosis:**

```bash
lsmod | wc -l
journalctl --since '24 hours ago' | grep -E 'modprobe|insmod' | head -10
```

#### SelfdefFail2banTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-fail2ban-textfile.service
journalctl -u selfdef-fail2ban-textfile.service --since '30 minutes ago'
```

**Cause:** wrapper failed (fail2ban-client invocation error or
runtime-socket race). Defensive-response gauges UNRELIABLE.

#### SelfdefFail2banObserverSilent (critical)

**Diagnosis:**

```bash
systemctl status selfdef-fail2ban-textfile.timer
systemctl list-timers selfdef-fail2ban-textfile.timer
```

**Cause:** 13th sibling observer timer not firing. Fail2ban
defensive-response state is stale — fail2ban could be silently
mitigating (or failing to mitigate) attacks without visibility.

#### SelfdefFail2banServerDown (critical)

**Diagnosis:**

```bash
systemctl status fail2ban
fail2ban-client ping
journalctl -u fail2ban --since '30 minutes ago' | tail -50
```

**Cause:** fail2ban-server is installed but not responding to ping
for 2+ minutes. **This is a defensive-tier outage** — failed login
attempts (recorded by SelfdefAuthEvents*) will NOT be auto-blocked.

**Pairs with auth-events.** Cross-check
`selfdef_auth_events_login_failures` — if BOTH alerts fire, the
operator is under attack AND defenseless.

**Remediation:**

```bash
systemctl restart fail2ban
fail2ban-client status     # confirm jails reload
```

#### SelfdefFail2banZeroJails (warning)

**Diagnosis:**

```bash
fail2ban-client status
ls /etc/fail2ban/jail.d/
```

**Cause:** fail2ban-server is up but no jails configured/enabled.
No defensive response can trigger. Legitimate during bring-up;
otherwise drift hazard.

**Remediation (sshd jail bring-up):**

```bash
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
bantime = 1h
findtime = 10m
maxretry = 5
EOF
fail2ban-client reload
```

#### SelfdefFail2banActiveBanSpike (warning)

**Diagnosis:**

```bash
fail2ban-client status sshd     # source-IP geography
fail2ban-client banned          # full ban list
journalctl -u fail2ban --since '1 hour ago' | grep -E 'NOTICE|WARNING'
```

**Cause:** > 50 currently-banned IPs across all jails for 10+ minutes.
Sustained distributed brute-force wave. Consider:

- Raising `bantime` from 1h to 24h in the affected jail
- Pushing IP-block rules upstream (router/firewall)
- Investigating whether a single ASN is dominating the source IPs

#### SelfdefNftablesObserverFault (critical)

**Diagnosis:**

```bash
systemctl status selfdef-nftables-textfile.service
journalctl -u selfdef-nftables-textfile.service --since '30 minutes ago'
```

**Cause:** wrapper failure (often CAP_NET_ADMIN was stripped by an
operator hardening sweep). Firewall + conntrack gauges UNRELIABLE.

#### SelfdefNftablesObserverSilent (critical)

**Diagnosis:**

```bash
systemctl status selfdef-nftables-textfile.timer
systemctl list-timers selfdef-nftables-textfile.timer
```

#### SelfdefNftablesRulesetEmpty (critical)

**Diagnosis:**

```bash
nft list ruleset
```

**Cause:** the kernel packet-filter has 0 rules. **This is a perimeter
outage** — fail2ban bans cannot take effect; the host is open.

**Pairs with fail2ban.** Cross-check
`selfdef_fail2ban_current_bans_sum` — if fail2ban thinks IPs are
banned but nftables has no rules, the bans are theoretical only.

**Remediation:**

```bash
# Restore from baseline:
nft -f /etc/nftables.conf
systemctl restart nftables    # if systemd unit exists
nft list ruleset              # confirm rules present
```

#### SelfdefConntrackTableNearFull (critical)

**Diagnosis:**

```bash
cat /proc/sys/net/netfilter/nf_conntrack_count
cat /proc/sys/net/netfilter/nf_conntrack_max
conntrack -L | head -20        # if conntrack-tools installed
ss -s                          # TCP/UDP socket summary
```

**Cause:** conntrack table > 90% full. New connection attempts are
being silently dropped at kernel level — DoS-equivalent symptom for
legitimate clients.

**Remediation (immediate):**

```bash
# Double the max (immediate relief):
current=$(cat /proc/sys/net/netfilter/nf_conntrack_max)
sysctl -w net.netfilter.nf_conntrack_max=$((current*2))

# Persist:
echo "net.netfilter.nf_conntrack_max=$((current*2))" \
  > /etc/sysctl.d/99-conntrack.conf
```

Then investigate WHY conntrack filled — long-lived connection burst,
DDoS, or undersized default for the workload.

#### SelfdefConntrackTableHigh (warning)

**Diagnosis:** same commands as `SelfdefConntrackTableNearFull`.
Conntrack at > 75% sustained — pre-emptive expansion recommended
before reaching the kernel-drop ceiling.

#### SelfdefCronObserverFault (critical)

**Diagnosis:**

```bash
systemctl status selfdef-cron-textfile.service
journalctl -u selfdef-cron-textfile.service --since '30 minutes ago'
```

**Cause:** wrapper failure (often a cron-surface directory was made
unreadable by an operator hardening change). Persistence drift
detection lost.

#### SelfdefCronObserverSilent (critical)

**Diagnosis:**

```bash
systemctl status selfdef-cron-textfile.timer
systemctl list-timers selfdef-cron-textfile.timer
```

#### SelfdefCronEntryDriftHigh (warning)

**Diagnosis:**

```bash
# Enumerate all cron surfaces:
ls -la /etc/cron.d/ /etc/cron.{hourly,daily,weekly,monthly}/
cat /etc/crontab
ls -la /var/spool/cron/crontabs/ /var/spool/cron/

# Find files modified in last 24h:
find /etc/cron.d /etc/cron.* /etc/crontab /var/spool/cron \
  -type f -mtime -1 2>/dev/null
```

**Cause:** total actionable cron-entry count changed > 2 times in
1 hour. Either legitimate operator activity (deployment, package
upgrade) OR an attacker dropped a persistence rule.

**Diagnostic correlation:** check auth-events for recent shell
sessions; check kernel-modules for unsigned-module loads (rootkit
on top of cron persistence).

#### SelfdefCronDFileCountDrift (warning)

**Diagnosis:**

```bash
ls -la /etc/cron.d/
cat /etc/cron.d/*
find /etc/cron.d -type f -newer /tmp/cron-baseline 2>/dev/null
```

**Cause:** a file was added/removed from `/etc/cron.d/` (the
highest-risk persistence surface — root-level scheduled execution).
For an attacker: dropping a file here gives recurring root.

**Remediation if hostile:**

```bash
# Identify the new file:
ls -la /etc/cron.d/ --time=mtime | head
# Disable (rename to .disabled):
mv /etc/cron.d/<suspect> /etc/cron.d/<suspect>.disabled
# Capture for forensics:
cp /etc/cron.d/<suspect>.disabled /var/log/forensics/
```

#### SelfdefSystemdTimerDrift (warning)

**Diagnosis:**

```bash
systemctl list-timers --all
systemctl list-unit-files --type=timer
# Find recently-modified .timer files:
find /etc/systemd/system /usr/lib/systemd/system -name '*.timer' \
  -mtime -1 2>/dev/null
```

**Cause:** systemd .timer unit count changed. Modern persistence
technique — attacker drops a `.timer` + `.service` pair.

**Remediation if hostile:**

```bash
systemctl stop <suspect>.timer
systemctl disable <suspect>.timer
# Capture before removal:
cp /etc/systemd/system/<suspect>.{timer,service} /var/log/forensics/
rm /etc/systemd/system/<suspect>.{timer,service}
systemctl daemon-reload
```

#### SelfdefSshdConfigTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-sshd-config-textfile.service
journalctl -u selfdef-sshd-config-textfile.service --since '30 minutes ago'
```

**Cause:** wrapper failure (often /etc/ssh permissions or
sshd_config moved). Hardening drift detection lost.

#### SelfdefSshdConfigObserverSilent (critical)

```bash
systemctl status selfdef-sshd-config-textfile.timer
```

#### SelfdefSshdPermitRootLoginEnabled (critical)

**Diagnosis:**

```bash
grep -E '^[[:space:]]*PermitRootLogin' /etc/ssh/sshd_config
sshd -T | grep -i permitrootlogin   # effective value
```

**Cause:** sshd_config has `PermitRootLogin yes`. Remote root SSH
login is permitted. **Pairs with auth-events**: any successful
root login bypasses the entire fail2ban-mitigated user-attack
defense.

**Remediation:**

```bash
sed -i 's/^[[:space:]]*PermitRootLogin.*/PermitRootLogin prohibit-password/' \
  /etc/ssh/sshd_config
sshd -t                              # syntax check FIRST
systemctl reload sshd
```

#### SelfdefSshdPermitEmptyPasswords (critical)

**Diagnosis:**

```bash
grep -E '^[[:space:]]*PermitEmptyPasswords' /etc/ssh/sshd_config
sshd -T | grep -i permitemptypasswords
```

**Remediation:**

```bash
sed -i 's/^[[:space:]]*PermitEmptyPasswords.*/PermitEmptyPasswords no/' \
  /etc/ssh/sshd_config
sshd -t && systemctl reload sshd
```

#### SelfdefSshdPasswordAuthEnabled (warning)

**Diagnosis:**

```bash
grep -E '^[[:space:]]*PasswordAuthentication' /etc/ssh/sshd_config
sshd -T | grep -i passwordauthentication
```

**Cause:** password authentication is permitted (default).
fail2ban mitigates brute force; key-only is stronger.

**Remediation (BEFORE you do this, verify you have working SSH
keys on the host):**

```bash
# Verify key auth works first:
ssh -o PreferredAuthentications=publickey -o PasswordAuthentication=no \
  user@<this-host> echo OK

# Then flip:
sed -i 's/^[[:space:]]*PasswordAuthentication.*/PasswordAuthentication no/' \
  /etc/ssh/sshd_config
sshd -t && systemctl reload sshd
```

#### SelfdefSshdConfigHashDrift (warning)

**Diagnosis:**

```bash
# If etckeeper is installed:
cd /etc && git log --since '1 hour ago' -- ssh/sshd_config

# Otherwise, find the change:
stat /etc/ssh/sshd_config
# Compare to last-known-good:
diff /var/backups/sshd_config.last-good /etc/ssh/sshd_config

# Verify effective sshd config:
sshd -T | sort > /tmp/effective.now
diff /var/backups/sshd_effective.last-good /tmp/effective.now
```

**Cause:** sshd_config content changed. Could be legitimate
operator change OR an attacker weakening server hardening.

#### SelfdefPackageStateTextfileEmitFailed (critical)

**Diagnosis:**

```bash
systemctl status selfdef-package-state-textfile.service
journalctl -u selfdef-package-state-textfile.service --since '30 minutes ago'
```

**Cause:** wrapper failure (often /var/lib/apt or /var/lib/dpkg
made unreadable, or `apt-get -s upgrade` timed out > 60s on a busy
host).

#### SelfdefPackageStateObserverSilent (critical)

```bash
systemctl status selfdef-package-state-textfile.timer
```

#### SelfdefAptSecurityUpdatesPending (critical)

**Diagnosis:**

```bash
apt list --upgradable 2>/dev/null | grep -i security
# Or full breakdown:
apt-get -s upgrade | grep '^Inst ' | grep -- '-security'
# Operator-readable CVE mapping:
apt changelog <pkg> | head -50
```

**Cause:** packages from `-security` repos are pending. The host
runs known-vulnerable code.

**Remediation:**

```bash
# Refresh visibility:
apt update

# Apply ONLY security updates (most operators prefer this in
# unattended-upgrades mode):
apt -y -o "Dpkg::Options::=--force-confold" \
    -o "Dpkg::Options::=--force-confdef" \
    install $(apt list --upgradable 2>/dev/null \
              | grep -i security \
              | awk -F/ '{print $1}')

# Reboot if kernel was updated:
[ -f /var/run/reboot-required ] && systemctl reboot
```

#### SelfdefDpkgBrokenPackages (critical)

**Diagnosis:**

```bash
dpkg --audit                  # full list of broken pkgs
dpkg -l | grep -vE '^(ii|rc|un) '
```

**Remediation (try in this order):**

```bash
dpkg --configure -a           # finalize half-configured pkgs
apt --fix-broken install      # let apt resolve deps
# Last resort — re-install:
apt install --reinstall <broken-pkg>
```

#### SelfdefAptUpdateStale (warning)

**Diagnosis:**

```bash
ls -lh /var/lib/apt/lists/   # mtime of the most recent file
stat /var/cache/apt/pkgcache.bin
```

**Cause:** `apt update` hasn't run for > 7 days. New CVE-patched
packages are invisible.

**Remediation:**

```bash
apt update
# If unattended-upgrades is installed, verify it's running:
systemctl status apt-daily.timer apt-daily-upgrade.timer
```

#### SelfdefAptPendingBacklog (warning)

**Diagnosis:**

```bash
apt list --upgradable 2>/dev/null | wc -l
apt-get -s upgrade | grep '^Inst ' | head -20
```

**Cause:** > 50 packages pending upgrade for > 1 hour. Non-security
backlog still matters (bug fixes, dependency rot).

**Remediation:** schedule a maintenance window for `apt upgrade`.

#### SelfdefJournalDiskTextfileEmitFailed (critical)

```bash
systemctl status selfdef-journal-disk-textfile.service
journalctl -u selfdef-journal-disk-textfile.service --since '30 minutes ago'
```

#### SelfdefJournalDiskObserverSilent (critical)

```bash
systemctl status selfdef-journal-disk-textfile.timer
```

#### SelfdefJournalDiskRunaway (critical)

**Diagnosis:**

```bash
# Total + per-file breakdown:
journalctl --disk-usage
journalctl --header | grep -E '^File|Sealed|Vacuumed'

# Top emitter — top services by message count:
journalctl --since '1 hour ago' --output cat \
  | head -100000 \
  | awk '{print $1}' \
  | sort | uniq -c | sort -rn | head

# Per-service journal byte count (one_liner):
journalctl --since '1 hour ago' -o json --no-pager 2>/dev/null \
  | jq -r '.SYSLOG_IDENTIFIER // "unknown"' \
  | sort | uniq -c | sort -rn | head
```

**Cause:** journal > 5 GiB. A single service is generating
excessive logs (debug logging left on, crash loop, log injection
attack).

**Remediation (short-term):**

```bash
# Force vacuum to a cap:
journalctl --vacuum-size=1G
```

**Remediation (root cause):**

```bash
# Find the offender (see commands above), then either fix the
# service or muzzle it:
systemctl edit <noisy-service>
# Add: [Service]
#      LogLevelMax=warning
systemctl restart <noisy-service>
```

#### SelfdefJournalNoPersistentStorage (critical)

**Diagnosis:**

```bash
ls -la /var/log/journal/    # should be non-empty
ls -la /run/log/journal/    # volatile fallback
grep -E '^Storage' /etc/systemd/journald.conf
```

**Cause:** `/var/log/journal/` is empty so systemd is writing only
to `/run/log/journal/` (volatile). **A reboot loses the entire
forensic trail** — a serious IPS gap for incident response.

**Remediation:**

```bash
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
# Optionally lock in:
sed -i 's/^#*Storage=.*/Storage=persistent/' \
  /etc/systemd/journald.conf
systemctl restart systemd-journald
# Verify:
journalctl --header | grep 'File path'
```

#### SelfdefJournalDiskHigh (warning)

**Diagnosis:** same commands as `SelfdefJournalDiskRunaway`.
Sustained > 1 GiB but under 5 GiB ceiling. Retention pressure;
older entries may be rotating out.

**Remediation:**

```bash
# Raise the cap if you have disk to spare:
sed -i 's/^#*SystemMaxUse=.*/SystemMaxUse=8G/' \
  /etc/systemd/journald.conf
systemctl restart systemd-journald

# Or chase the cause (see Runaway runbook above).
```

### Action-surface alert runbook (SDD-070..078 + MFA/token revocations)

The 11 selfdef responder action-surface alert families (`config/prometheus/alerts/selfdef-{apparmor-profile-pivots,bpf-map-element-clears,capability-drops,env-scrubs,kernel-keyring-evictions,mfa-grant-revocations,mount-bindings,netns-isolations,process-tree-freezes,socket-fd-revocations,token-revocations}.rules.yml`) each carry per-alert `runbook_url` anchors into this guide. Every alert below corresponds to one entry; the `test_action_surface_alert_runbook_coverage` lint locks the rules↔runbook anchors in lockstep so a page never lands on a missing section. All four observer-health alerts (TextfileEmitFailed / ObserverSilent / StateDirMissing / PendingRestoreBacklog) share a diagnosis shape across families; the action-specific high-watermark alerts are unique per surface. These are the consumer-side runbooks for selfdef's producer responder surfaces (proper-responsibility boundary: selfdef emits the textfile gauges, sovereign-os owns the alerts + operator runbooks).

#### SelfdefApparmorProfilePivotsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-077 enforcement visibility lost at the MAC policy axis.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_apparmor_profile_pivots gauges is failing.
systemctl status selfdef-apparmor-profile-pivots-textfile.service
journalctl -u selfdef-apparmor-profile-pivots-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-apparmor-profile-pivots-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefApparmorProfilePivotsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-apparmor-profile-pivots observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-apparmor-profile-pivots-textfile.timer' --all
systemctl status selfdef-apparmor-profile-pivots-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-apparmor-profile-pivots.prom
```

**Fix:** `systemctl enable --now selfdef-apparmor-profile-pivots-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-apparmor-profile-pivots-textfile.service` and reset it.


#### SelfdefApparmorProfilePivotsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/apparmor-profile-pivots not present for 10+ minutes. SDD-077 MAC-policy-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/apparmor-profile-pivots
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/apparmor-profile-pivots` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefApparmorProfilePivotsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit apparmor-profile-pivots-queue card needed. NOTE: AppArmor profile pivots are one-way at the kernel level — restore is queue-clear + audit only; operator must restart the process under its original profile via the init system to recover.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-apparmor-profile-pivots surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_apparmor_profile_pivots_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-apparmor-profile-pivots.prom
# ...or query selfdef_apparmor_profile_pivots_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefApparmorProfilePivotsDeniedHigh (warning)

**Meaning:** Multiple pivot requests targeted processes whose current profile forbids change_profile to the requested target. Likely rule misconfiguration or attempt to pivot already-strict processes. Operator review.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_apparmor_profile_pivots_denied_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_apparmor_profile_pivots_denied_count' /var/lib/node_exporter/textfile_collector/selfdef-apparmor-profile-pivots.prom
# ...or query selfdef_apparmor_profile_pivots_denied_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'apparmor.profile.pivots'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefApparmorProfilePivotsQuarantineStrictHigh (warning)

**Meaning:** Per-target-profile breakdown shows many processes pivoted into selfdef-quarantine-strict simultaneously. Could indicate a wide-scope incident response or rule misfire. Investigate correlator events.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_apparmor_profile_pivots_by_target_profile. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_apparmor_profile_pivots_by_target_profile' /var/lib/node_exporter/textfile_collector/selfdef-apparmor-profile-pivots.prom
# ...or query selfdef_apparmor_profile_pivots_by_target_profile in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'apparmor.profile.pivots'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefApparmorProfilePivotsNoTargetHigh (warning)

**Meaning:** Pivot requests reference profiles not loaded in the kernel. Operator should run `apparmor_status` to inventory loaded profiles and either load the missing profiles via `apparmor_parser` or update the rule configuration.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_apparmor_profile_pivots_no_target_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_apparmor_profile_pivots_no_target_count' /var/lib/node_exporter/textfile_collector/selfdef-apparmor-profile-pivots.prom
# ...or query selfdef_apparmor_profile_pivots_no_target_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'apparmor.profile.pivots'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefBpfMapElementClearsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-078 enforcement visibility lost at the eBPF map state axis.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_bpf_map_element_clears gauges is failing.
systemctl status selfdef-bpf-map-element-clears-textfile.service
journalctl -u selfdef-bpf-map-element-clears-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-bpf-map-element-clears-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefBpfMapElementClearsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-bpf-map-element-clears observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-bpf-map-element-clears-textfile.timer' --all
systemctl status selfdef-bpf-map-element-clears-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-bpf-map-element-clears.prom
```

**Fix:** `systemctl enable --now selfdef-bpf-map-element-clears-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-bpf-map-element-clears-textfile.service` and reset it.


#### SelfdefBpfMapElementClearsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/bpf-map-element-clears not present for 10+ minutes. SDD-078 eBPF-map-state-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/bpf-map-element-clears
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/bpf-map-element-clears` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefBpfMapElementClearsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit bpf-map-element-clears-queue card needed. NOTE: BPF map element clears are one-way at the kernel level — selfdef did not snapshot prior values; restore is queue-clear + audit only. The owning BPF program's control plane must re-add elements.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-bpf-map-element-clears surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_bpf_map_element_clears_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-bpf-map-element-clears.prom
# ...or query selfdef_bpf_map_element_clears_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefBpfMapElementClearsAccessDeniedHigh (warning)

**Meaning:** Multiple clear requests denied by the kernel (EPERM/EACCES). Either the target maps set BPF_F_RDONLY or selfdef lacks CAP_BPF/CAP_SYS_ADMIN. Operator action: check map_flags via `bpftool map show id <N>` and verify selfdefd's capabilities.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_bpf_map_element_clears_access_denied_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_bpf_map_element_clears_access_denied_count' /var/lib/node_exporter/textfile_collector/selfdef-bpf-map-element-clears.prom
# ...or query selfdef_bpf_map_element_clears_access_denied_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'bpf.map.element.clears'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefBpfMapElementClearsElementsClearedHigh (warning)

**Meaning:** Large element-cleared count suggests one or more All-scope clears against large maps. Verify the operator intent matches the wipe scope; consider whether the owning BPF program's defaults will safely re-populate.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_bpf_map_element_clears_elements_cleared_total. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_bpf_map_element_clears_elements_cleared_total' /var/lib/node_exporter/textfile_collector/selfdef-bpf-map-element-clears.prom
# ...or query selfdef_bpf_map_element_clears_elements_cleared_total in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'bpf.map.element.clears'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefBpfMapElementClearsAmbiguousNameAny (warning)

**Meaning:** name:<x> resolved to >1 BPF map. Operator action: update the rule to use the pinned path (/sys/fs/bpf/<name>) or id:<u32> for the intended map. AmbiguousName fires on any occurrence because it indicates a rule-config error, not an attack signal.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_bpf_map_element_clears_ambiguous_name_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_bpf_map_element_clears_ambiguous_name_count' /var/lib/node_exporter/textfile_collector/selfdef-bpf-map-element-clears.prom
# ...or query selfdef_bpf_map_element_clears_ambiguous_name_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'bpf.map.element.clears'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefCapabilityDropsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-075 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_capability_drops gauges is failing.
systemctl status selfdef-capability-drops-textfile.service
journalctl -u selfdef-capability-drops-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-capability-drops-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefCapabilityDropsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-capability-drops observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-capability-drops-textfile.timer' --all
systemctl status selfdef-capability-drops-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-capability-drops.prom
```

**Fix:** `systemctl enable --now selfdef-capability-drops-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-capability-drops-textfile.service` and reset it.


#### SelfdefCapabilityDropsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/capability-drops not present for 10+ minutes. SDD-075 per-process-privilege-set-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/capability-drops
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/capability-drops` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefCapabilityDropsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit capability-drops-queue card needed. NOTE: capability drops are irreversible at kernel level — restore is queue-clear + audit only; operator must restart the process to recover the cap.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-capability-drops surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_capability_drops_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-capability-drops.prom
# ...or query selfdef_capability_drops_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefCapabilityDropsRedundantHigh (warning)

**Meaning:** Multiple drop requests targeted processes that didn't hold the named caps — likely rule misconfiguration or stale process model. Operator review.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_capability_drops_redundant_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_capability_drops_redundant_count' /var/lib/node_exporter/textfile_collector/selfdef-capability-drops.prom
# ...or query selfdef_capability_drops_redundant_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'capability.drops'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefCapabilityDropsNetAdminHigh (warning)

**Meaning:** Per-cap breakdown shows multiple processes losing CAP_NET_ADMIN simultaneously. Could indicate a coordinated attack on network-config caps; investigate correlator events.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_capability_drops_by_cap. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_capability_drops_by_cap' /var/lib/node_exporter/textfile_collector/selfdef-capability-drops.prom
# ...or query selfdef_capability_drops_by_cap in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'capability.drops'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefEnvScrubsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-074 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_env_scrubs gauges is failing.
systemctl status selfdef-env-scrubs-textfile.service
journalctl -u selfdef-env-scrubs-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-env-scrubs-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefEnvScrubsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-env-scrubs observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-env-scrubs-textfile.timer' --all
systemctl status selfdef-env-scrubs-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-env-scrubs.prom
```

**Fix:** `systemctl enable --now selfdef-env-scrubs-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-env-scrubs-textfile.service` and reset it.


#### SelfdefEnvScrubsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/env-scrubs not present for 10+ minutes. SDD-074 in-memory secret-residency-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/env-scrubs
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/env-scrubs` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefEnvScrubsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit env-scrubs-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-env-scrubs surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_env_scrubs_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-env-scrubs.prom
# ...or query selfdef_env_scrubs_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefEnvScrubsNoMatchHigh (warning)

**Meaning:** Multiple scrub requests targeted processes without the named vars — likely rule misconfiguration or stale process model. Operator review.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_env_scrubs_no_match_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_env_scrubs_no_match_count' /var/lib/node_exporter/textfile_collector/selfdef-env-scrubs.prom
# ...or query selfdef_env_scrubs_no_match_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'env.scrubs'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefEnvScrubsVarsScrubbedHigh (warning)

**Meaning:** Large-scale credential-rotation propagation. Verify rotation workflow + secret-broker fetch latency.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_env_scrubs_vars_scrubbed_total. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_env_scrubs_vars_scrubbed_total' /var/lib/node_exporter/textfile_collector/selfdef-env-scrubs.prom
# ...or query selfdef_env_scrubs_vars_scrubbed_total in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'env.scrubs'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefKernelKeyringEvictionsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-076 enforcement visibility lost at the kernel-keyring axis.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_kernel_keyring_evictions gauges is failing.
systemctl status selfdef-kernel-keyring-evictions-textfile.service
journalctl -u selfdef-kernel-keyring-evictions-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-kernel-keyring-evictions-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefKernelKeyringEvictionsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-kernel-keyring-evictions observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-kernel-keyring-evictions-textfile.timer' --all
systemctl status selfdef-kernel-keyring-evictions-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-kernel-keyring-evictions.prom
```

**Fix:** `systemctl enable --now selfdef-kernel-keyring-evictions-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-kernel-keyring-evictions-textfile.service` and reset it.


#### SelfdefKernelKeyringEvictionsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/kernel-keyring-evictions not present for 10+ minutes. SDD-076 kernel-keyring-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/kernel-keyring-evictions
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/kernel-keyring-evictions` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefKernelKeyringEvictionsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit kernel-keyring-evictions-queue card needed. NOTE: kernel keyring entries that have been invalidated/unlinked are gone — restore is queue-clear + audit only; operator must re-provision the key material to recover.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-kernel-keyring-evictions surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_kernel_keyring_evictions_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-kernel-keyring-evictions.prom
# ...or query selfdef_kernel_keyring_evictions_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefKernelKeyringEvictionsNotFoundHigh (warning)

**Meaning:** Multiple eviction requests targeted keys that didn't exist in the named keyring — likely rule misconfiguration, stale spec, or attacker pre-clearing keys. Operator review.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_kernel_keyring_evictions_not_found_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_kernel_keyring_evictions_not_found_count' /var/lib/node_exporter/textfile_collector/selfdef-kernel-keyring-evictions.prom
# ...or query selfdef_kernel_keyring_evictions_not_found_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'kernel.keyring.evictions'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefKernelKeyringEvictionsUserKeyHigh (warning)

**Meaning:** Per-type breakdown shows multiple user-type kernel keys evicted simultaneously. User keys typically hold per-session credentials (Kerberos TGT, etc.); coordinated eviction could indicate credential-rotation suppression. Investigate correlator events.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_kernel_keyring_evictions_by_type. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_kernel_keyring_evictions_by_type' /var/lib/node_exporter/textfile_collector/selfdef-kernel-keyring-evictions.prom
# ...or query selfdef_kernel_keyring_evictions_by_type in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'kernel.keyring.evictions'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefMfaGrantRevocationsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-069 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_mfa_grant_revocations gauges is failing.
systemctl status selfdef-mfa-grant-revocations-textfile.service
journalctl -u selfdef-mfa-grant-revocations-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-mfa-grant-revocations-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefMfaGrantRevocationsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-mfa-grant-revocations observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-mfa-grant-revocations-textfile.timer' --all
systemctl status selfdef-mfa-grant-revocations-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-mfa-grant-revocations.prom
```

**Fix:** `systemctl enable --now selfdef-mfa-grant-revocations-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-mfa-grant-revocations-textfile.service` and reset it.


#### SelfdefMfaGrantRevocationsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/mfa-grant-revocations not present for 10+ minutes. SDD-069 MFA-grant revocation cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/mfa-grant-revocations
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/mfa-grant-revocations` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefMfaGrantRevocationsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit mfa-grant-revocations-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-mfa-grant-revocations surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_mfa_grant_revocations_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-mfa-grant-revocations.prom
# ...or query selfdef_mfa_grant_revocations_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefMfaGrantRevocationsActiveHigh (warning)

**Meaning:** Likely incident-response scenario.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_mfa_grant_revocations_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_mfa_grant_revocations_active_count' /var/lib/node_exporter/textfile_collector/selfdef-mfa-grant-revocations.prom
# ...or query selfdef_mfa_grant_revocations_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'mfa.grant.revocations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefMountBindingsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-071 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_mount_bindings gauges is failing.
systemctl status selfdef-mount-bindings-textfile.service
journalctl -u selfdef-mount-bindings-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-mount-bindings-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefMountBindingsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-mount-bindings observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-mount-bindings-textfile.timer' --all
systemctl status selfdef-mount-bindings-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-mount-bindings.prom
```

**Fix:** `systemctl enable --now selfdef-mount-bindings-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-mount-bindings-textfile.service` and reset it.


#### SelfdefMountBindingsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/mount-bindings not present for 10+ minutes. SDD-071 filesystem-binding-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/mount-bindings
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/mount-bindings` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefMountBindingsPendingRebindBacklog (warning)

**Meaning:** Operator engagement with the cockpit mount-bindings-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-mount-bindings surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_mount_bindings_pending_rebinds ' /var/lib/node_exporter/textfile_collector/selfdef-mount-bindings.prom
# ...or query selfdef_mount_bindings_pending_rebinds in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefMountBindingsActiveHigh (warning)

**Meaning:** Likely container-escape investigation scenario; the filesystem-binding axis is the shortest-duration IPS primitive (max 6h even at operator-overridden).

**Diagnosis:**

```bash
# Sustained high reading on selfdef_mount_bindings_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_mount_bindings_active_count' /var/lib/node_exporter/textfile_collector/selfdef-mount-bindings.prom
# ...or query selfdef_mount_bindings_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'mount.bindings'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefNetnsIsolationsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-070 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_netns_isolations gauges is failing.
systemctl status selfdef-netns-isolations-textfile.service
journalctl -u selfdef-netns-isolations-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-netns-isolations-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefNetnsIsolationsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-netns-isolations observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-netns-isolations-textfile.timer' --all
systemctl status selfdef-netns-isolations-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-netns-isolations.prom
```

**Fix:** `systemctl enable --now selfdef-netns-isolations-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-netns-isolations-textfile.service` and reset it.


#### SelfdefNetnsIsolationsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/netns-isolations not present for 10+ minutes. SDD-070 kernel-containment cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/netns-isolations
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/netns-isolations` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefNetnsIsolationsPendingReleaseBacklog (warning)

**Meaning:** Operator engagement with the cockpit netns-isolations-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-netns-isolations surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_netns_isolations_pending_releases ' /var/lib/node_exporter/textfile_collector/selfdef-netns-isolations.prom
# ...or query selfdef_netns_isolations_pending_releases in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefNetnsIsolationsActiveHigh (warning)

**Meaning:** Likely large-scale incident-response scenario; the kernel-containment axis is the shortest-duration IPS primitive.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_netns_isolations_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_netns_isolations_active_count' /var/lib/node_exporter/textfile_collector/selfdef-netns-isolations.prom
# ...or query selfdef_netns_isolations_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'netns.isolations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefProcessTreeFreezesTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-072 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_process_tree_freezes gauges is failing.
systemctl status selfdef-process-tree-freezes-textfile.service
journalctl -u selfdef-process-tree-freezes-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-process-tree-freezes-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefProcessTreeFreezesObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-process-tree-freezes observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-process-tree-freezes-textfile.timer' --all
systemctl status selfdef-process-tree-freezes-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-process-tree-freezes.prom
```

**Fix:** `systemctl enable --now selfdef-process-tree-freezes-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-process-tree-freezes-textfile.service` and reset it.


#### SelfdefProcessTreeFreezesStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/process-tree-freezes not present for 10+ minutes. SDD-072 process-graph-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/process-tree-freezes
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/process-tree-freezes` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefProcessTreeFreezesPendingThawBacklog (warning)

**Meaning:** Operator engagement with the cockpit process-tree-freezes-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-process-tree-freezes surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_process_tree_freezes_pending_thaws ' /var/lib/node_exporter/textfile_collector/selfdef-process-tree-freezes.prom
# ...or query selfdef_process_tree_freezes_pending_thaws in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefProcessTreeFreezesFrozenPidCountHigh (warning)

**Meaning:** Sum of pids frozen across all active SDD-072 handles >100 — likely fork-bomb or large-worker-pool incident. Operator review.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_process_tree_freezes_frozen_pid_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_process_tree_freezes_frozen_pid_count' /var/lib/node_exporter/textfile_collector/selfdef-process-tree-freezes.prom
# ...or query selfdef_process_tree_freezes_frozen_pid_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'process.tree.freezes'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefProcessTreeFreezesActiveHigh (warning)

**Meaning:** Likely multi-incident response scenario. The process-graph axis primitive max-duration is 8h at operator-overridden tier.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_process_tree_freezes_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_process_tree_freezes_active_count' /var/lib/node_exporter/textfile_collector/selfdef-process-tree-freezes.prom
# ...or query selfdef_process_tree_freezes_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'process.tree.freezes'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefSocketFdRevocationsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-073 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_socket_fd_revocations gauges is failing.
systemctl status selfdef-socket-fd-revocations-textfile.service
journalctl -u selfdef-socket-fd-revocations-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-socket-fd-revocations-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefSocketFdRevocationsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes.

**Diagnosis:**

```bash
# The selfdef-socket-fd-revocations observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-socket-fd-revocations-textfile.timer' --all
systemctl status selfdef-socket-fd-revocations-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-socket-fd-revocations.prom
```

**Fix:** `systemctl enable --now selfdef-socket-fd-revocations-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-socket-fd-revocations-textfile.service` and reset it.


#### SelfdefSocketFdRevocationsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/socket-fd-revocations not present for 10+ minutes. SDD-073 per-connection-axis IPS primitive cannot persist state. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/socket-fd-revocations
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/socket-fd-revocations` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefSocketFdRevocationsPendingRestoreBacklog (warning)

**Meaning:** Operator engagement with the cockpit socket-fd-revocations-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-socket-fd-revocations surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_socket_fd_revocations_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-socket-fd-revocations.prom
# ...or query selfdef_socket_fd_revocations_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefSocketFdRevocationsStaleHandleRising (warning)

**Meaning:** Inode-race detection is firing repeatedly — the target process is rapidly closing/reopening fds, or the event detection→action latency is too high. Operator review of correlator timing recommended.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_socket_fd_revocations_stale_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_socket_fd_revocations_stale_count' /var/lib/node_exporter/textfile_collector/selfdef-socket-fd-revocations.prom
# ...or query selfdef_socket_fd_revocations_stale_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'socket.fd.revocations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefSocketFdRevocationsActiveHigh (warning)

**Meaning:** Likely large-scale connection-severance scenario. The per-connection axis primitive max-duration is 4h at operator-overridden tier (shortest of the IPS spine).

**Diagnosis:**

```bash
# Sustained high reading on selfdef_socket_fd_revocations_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_socket_fd_revocations_active_count' /var/lib/node_exporter/textfile_collector/selfdef-socket-fd-revocations.prom
# ...or query selfdef_socket_fd_revocations_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'socket.fd.revocations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefTokenRevocationsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-068 enforcement visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_token_revocations gauges is failing.
systemctl status selfdef-token-revocations-textfile.service
journalctl -u selfdef-token-revocations-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-token-revocations-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefTokenRevocationsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes. SDD-068 state stale.

**Diagnosis:**

```bash
# The selfdef-token-revocations observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-token-revocations-textfile.timer' --all
systemctl status selfdef-token-revocations-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-token-revocations.prom
```

**Fix:** `systemctl enable --now selfdef-token-revocations-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-token-revocations-textfile.service` and reset it.


#### SelfdefTokenRevocationsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/token-revocations not present for 10+ minutes. SDD-068 API/web-token revocation cannot persist state; revoke-tokens calls cannot land. Operator action: systemctl status selfdefd && systemctl restart selfdefd.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/token-revocations
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/token-revocations` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefTokenRevocationsPendingRestoreBacklog (warning)

**Meaning:** More than 5 pending operator-restore decisions sustained 30+ minutes. Operator engagement with the cockpit token-revocations-queue card needed.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-token-revocations surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_token_revocations_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-token-revocations.prom
# ...or query selfdef_token_revocations_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefTokenRevocationsActiveHigh (warning)

**Meaning:** More than 10 active token-revocations sustained 1+ hour. Likely incident-response scenario or correlator misconfig. Investigate.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_token_revocations_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_token_revocations_active_count' /var/lib/node_exporter/textfile_collector/selfdef-token-revocations.prom
# ...or query selfdef_token_revocations_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'token.revocations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


### IPS-quartet action-surface runbook (SDD-065 blockset / SDD-066 quarantine / SDD-067 revocations)

Sibling to the SDD-068+ action-surface runbook above — these three earlier IPS responder families (`selfdef-{blockset,quarantine,revocations}.rules.yml`) had per-family structural contract tests but their `runbook_url` anchors pointed at missing sections. Each alert below now resolves; the generic `test_alert_runbook_anchor_coverage` lint keeps every alert family's anchors honest.

#### SelfdefBlocksetTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-065 enforcement- layer visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_blockset gauges is failing.
systemctl status selfdef-blockset-textfile.service
journalctl -u selfdef-blockset-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-blockset-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefBlocksetObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes. Enforcement-layer state stale.

**Diagnosis:**

```bash
# The selfdef-blockset observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-blockset-textfile.timer' --all
systemctl status selfdef-blockset-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-blockset.prom
```

**Fix:** `systemctl enable --now selfdef-blockset-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-blockset-textfile.service` and reset it.


#### SelfdefBlocksetTableMissing (critical)

**Meaning:** selfdef-blocks nftables table is not present for 10+ minutes. SDD-065 IP-block enforcement cannot operate. Either selfdefd hasn't started, or its bootstrap was denied by CAP_NET_ADMIN policy. Operator action: `systemctl status selfdefd`, check `journalctl -u selfdefd | grep blockset`, then re-bootstrap via `selfdefctl init` (MS3+) or manual `nft -f /usr/share/selfdef/blockset-bootstrap.nft`.

**Diagnosis:**

```bash
# The kernel resource this action surface depends on (nftables set/table or
# cgroup slice) is absent — enforcement cannot land. Honest-offline sentinel.
# Confirm via the published gauge:
grep -E '^selfdef_blockset_present' /var/lib/node_exporter/textfile_collector/selfdef-blockset.prom
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|nft|cgroup|slice'
```

**Fix:** `systemctl restart selfdefd` — the daemon re-creates its nftables set/table (or cgroup slice) at start. If it stays absent, the daemon is failing earlier in boot or the kernel lacks the required subsystem; read the selfdefd journal for the prior fault.


#### SelfdefBlocksetTotalHigh (warning)

**Meaning:** {{ $value }} blocked IPs sustained 1+ hour. Investigate via `selfdefctl block-ip --list` (MS3+) and the paired auth-events / fail2ban dashboards for source ASN concentration.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_blockset_total_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_blockset_total_count' /var/lib/node_exporter/textfile_collector/selfdef-blockset.prom
# ...or query selfdef_blockset_total_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'blockset'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefQuarantineTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-066 enforcement- layer visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_quarantine gauges is failing.
systemctl status selfdef-quarantine-textfile.service
journalctl -u selfdef-quarantine-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-quarantine-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefQuarantineObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes. SDD-066 state stale.

**Diagnosis:**

```bash
# The selfdef-quarantine observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-quarantine-textfile.timer' --all
systemctl status selfdef-quarantine-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-quarantine.prom
```

**Fix:** `systemctl enable --now selfdef-quarantine-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-quarantine-textfile.service` and reset it.


#### SelfdefQuarantineSliceMissing (critical)

**Meaning:** /sys/fs/cgroup/selfdef.slice not present for 10+ minutes. SDD-066 process-quarantine enforcement cannot operate. Either selfdefd hasn't started or its slice was deleted. Operator action: `systemctl status selfdefd`, then `systemctl restart selfdefd`.

**Diagnosis:**

```bash
# The kernel resource this action surface depends on (nftables set/table or
# cgroup slice) is absent — enforcement cannot land. Honest-offline sentinel.
# Confirm via the published gauge:
grep -E '^selfdef_quarantine_slice_present' /var/lib/node_exporter/textfile_collector/selfdef-quarantine.prom
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|nft|cgroup|slice'
```

**Fix:** `systemctl restart selfdefd` — the daemon re-creates its nftables set/table (or cgroup slice) at start. If it stays absent, the daemon is failing earlier in boot or the kernel lacks the required subsystem; read the selfdefd journal for the prior fault.


#### SelfdefQuarantineActiveHigh (warning)

**Meaning:** More than 10 quarantine-*.scope entries sustained 30+ minutes. Operator decision queue probably backlogged. Inspect via the cockpit quarantine-queue card and `selfdefctl release-pid` or `selfdefctl kill-quarantined` per entry.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_quarantine_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_quarantine_active_count' /var/lib/node_exporter/textfile_collector/selfdef-quarantine.prom
# ...or query selfdef_quarantine_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'quarantine'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


#### SelfdefRevocationsTextfileEmitFailed (critical)

**Meaning:** Wrapper failure for 5+ minutes. SDD-067 enforcement- layer visibility lost.

**Diagnosis:**

```bash
# The textfile wrapper that writes selfdef_revocations gauges is failing.
systemctl status selfdef-revocations-textfile.service
journalctl -u selfdef-revocations-textfile.service --since '15 min ago' | tail -40
# Confirm the node_exporter textfile dir is writable by the selfdef uid:
sudo -u selfdef ls -ld /var/lib/node_exporter/textfile_collector
```

**Fix:** clear the underlying wrapper error (most often a permissions or disk-space fault on the textfile dir), then `systemctl restart selfdef-revocations-textfile.timer`. The sentinel clears on the next successful emit.


#### SelfdefRevocationsObserverSilent (critical)

**Meaning:** Timer hasn't fired in 5+ minutes. SDD-067 state stale.

**Diagnosis:**

```bash
# The selfdef-revocations observer timer has not run recently (state is going stale).
systemctl list-timers 'selfdef-revocations-textfile.timer' --all
systemctl status selfdef-revocations-textfile.timer
ls -la /var/lib/node_exporter/textfile_collector/selfdef-revocations.prom
```

**Fix:** `systemctl enable --now selfdef-revocations-textfile.timer`. If the timer is active but not firing, check for a wedged prior run with `systemctl status selfdef-revocations-textfile.service` and reset it.


#### SelfdefRevocationsStateDirMissing (critical)

**Meaning:** /var/lib/selfdef/revocations not present for 10+ minutes. SDD-067 session-revocation enforcement cannot operate; revoke-sessions calls cannot persist state. Operator action: `systemctl status selfdefd`, then `systemctl restart selfdefd`.

**Diagnosis:**

```bash
# The enforcement state directory is absent — the action surface cannot persist state.
ls -ld /var/lib/selfdef/revocations
systemctl status selfdefd
journalctl -u selfdefd --since '15 min ago' | grep -iE 'error|panic|state'
```

**Fix:** `systemctl restart selfdefd` — the daemon recreates its state dirs at start. If `/var/lib/selfdef/revocations` stays absent after restart, the daemon is failing earlier in boot; read its journal for the prior fault.


#### SelfdefRevocationsPendingRestoreBacklog (warning)

**Meaning:** More than 5 pending operator-restore decisions sustained 30+ minutes. Operator engagement with the cockpit revocations-queue card needed. Inspect via `python3 scripts/cockpit/revocations-queue.py`.

**Diagnosis:**

```bash
# Operator-restore decisions are queuing on the selfdef-revocations surface.
# Read the pending count straight from the published gauge:
grep '^selfdef_revocations_pending_restores ' /var/lib/node_exporter/textfile_collector/selfdef-revocations.prom
# ...or query selfdef_revocations_pending_restores in Prometheus/Grafana, or open the cockpit card for this surface.
```

**Fix:** engage the cockpit queue for this surface and resolve (restore or confirm) the pending decisions. The backlog is operator-action-required, not a daemon fault.


#### SelfdefRevocationsActiveHigh (warning)

**Meaning:** More than 10 active session-revocations sustained 1+ hour. Likely incident-response scenario or operator-misconfigured correlator rule. Investigate.

**Diagnosis:**

```bash
# Sustained high reading on selfdef_revocations_active_count. Confirm whether this is an active
# incident-response scenario or a correlator/config drift.
grep -E '^selfdef_revocations_active_count' /var/lib/node_exporter/textfile_collector/selfdef-revocations.prom
# ...or query selfdef_revocations_active_count in Prometheus/Grafana over the alert window.
journalctl -u selfdefd --since '1 hour ago' | grep -iE 'revocations'
```

**Fix:** if this matches a known incident response, no action — the surface is doing its job; acknowledge the page. If unexpected, investigate the driving events in the cockpit and the selfdef journal before relaxing the threshold.


### selfdef hot-store retention runbook (SDD-081)

#### SelfdefStoreRetentionStalled (warning)

**Meaning:** `selfdef_store_retention_enabled == 1` (the operator set
`hot_retention_days > 0`) but `selfdef_store_retention_sweeps_total` has
not advanced in over 13 hours — more than two of the daemon's 6-hour
sweep ticks. The retention loop that prunes events past the horizon is
not running, so the hot SQLite store (`selfdef_store_events`) will grow
unbounded and eventually pressure the disk — the exact F-2026-016
outcome retention exists to prevent. A host that deliberately keeps
events forever (`hot_retention_days = 0`) sets the gauge to 0 and never
fires this alert.

**Diagnosis:**

```bash
# 1. Is selfdefd up and exposing the retention series?
curl -s --unix-socket /run/selfdef.sock http://localhost/metrics \
  | grep selfdef_store_retention
# 2. Is retention actually enabled in config?
grep -E '^hot_retention_days' /etc/selfdef/selfdef.toml
# 3. Did the retention loop announce itself / log a sweep?
journalctl -u selfdefd --since '13 hours ago' | grep -i 'SD-R retention'
```

**Fix:** if `selfdef_store_retention_enabled` is 1 but no sweep line
appears in the journal, the daemon's retention task is wedged or the
daemon is unhealthy — `systemctl restart selfdefd` and confirm a
`SD-R retention: sweep loop running` line plus the sweep counter
advancing within a tick. If retention should be OFF for this host, set
`hot_retention_days = 0` (the alert then stops firing by design).

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
