# MS022 — SSE subscriber quota cockpit guide

Sovereign-os surfaces the selfdef-side MS022 SSE subscriber quota
state across 4 operator-visible layers: a Prometheus alert set, a
Grafana dashboard, the master-dashboard D-00 banner, and a proxy API
daemon. This document covers the **sovereign-os consumer side**; the
selfdef producer side (cap enforcement + the 6
`selfdef_sse_subscribers_*` Prometheus gauges) is documented at
[`cyberpunk042/selfdef` → `docs/operator/ms022-sse-subscriber-quota.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/ms022-sse-subscriber-quota.md).

Per the operator's standing rule (2026-05-19):

> *"if I talk about an IPS feature it's obviously not in Sovereign-OS"*

The cap enforcement + metric emission are selfdef IPS surfaces. Every
piece described in this doc reads those surfaces READ-ONLY (R10212);
no sovereign-os component mutates IPS state.

---

## TL;DR — what an operator sees

1. **Master dashboard banner** (D-00, top of the page): live SSE
   quota state shown alongside the existing M060 chain-health banner.
   Color-coded: green = ok, yellow = approaching, red = saturated,
   gray = unreachable.
2. **Prometheus alerts** (subsystem `ms022-sse-quota`): fire when
   saturation crosses 0.85 (warning) or 1.0 (critical) and when any
   token is saturated.
3. **Grafana dashboard** (`/d/sovereign-os-ms022-sse-quota`): 10
   panels with saturation trend + per-token table + companion M060
   view.
4. **Proxy daemon** (`sovereign-ms022-sse-quota-api.service`,
   loopback `:7711`): parses the selfdef daemon's `/metrics` and
   serves the compact JSON envelope the master-dashboard banner
   consumes.

---

## The 4 consumer-side surfaces

### 1. Master-dashboard banner

Wired into `webapp/master-dashboard/index.html` next to the existing
M060 chain-health banner. The `renderMS022SseQuotaBanner()` function
polls `/api/ms022/sse-quota` on the same 30s tick as the M060 banner
and updates four DOM elements:

| DOM id | Content |
|---|---|
| `ms022-sse-quota-banner` | container element with state class (`ok` / `approaching` / `saturated` / `unknown`) driving the color palette |
| `ms022-sse-label` | text: "SSE quota: ok/approaching/saturated/unknown" |
| `ms022-sse-detail` | context line carrying saturation % + the relevant alert name when degraded |
| `ms022-sse-active` | "N / M subscribers" count |

The footer carries a Grafana deep-link to
`/d/sovereign-os-ms022-sse-quota`. Operators clicking through land
directly on the dedicated dashboard.

### 2. Prometheus alerts

Three alerts ship in
[`config/prometheus/alerts/ms022-sse-quota.rules.yml`](../../config/prometheus/alerts/ms022-sse-quota.rules.yml):

| Alert | Severity | Expression | `for:` |
|---|---|---|---|
| `MS022SseGlobalQuotaApproaching` | warning | `selfdef_sse_subscribers_global_saturation > 0.85` | 5m |
| `MS022SseGlobalQuotaSaturated` | critical | `selfdef_sse_subscribers_global_saturation >= 1.0` | 2m |
| `MS022SsePerTokenQuotaSaturated` | warning | `selfdef_sse_subscribers_per_token_saturated > 0` | 5m |

Each carries `subsystem=ms022-sse-quota` for filter discipline +
`runbook_url` pointing at the matching `#### <AlertName>` section
in `m060-deployment-guide.md`. Alert thresholds are locked at
0.85 + 1.0 in the contract test
[`tests/lint/test_ms022_sse_quota_alerts_contract.py`](../../tests/lint/test_ms022_sse_quota_alerts_contract.py)
— drift would silently misalign the dashboard's threshold rendering
against the alert trigger.

### 3. Grafana dashboard

[`docs/observability/dashboards/sovereign-os-ms022-sse-quota.json`](../observability/dashboards/sovereign-os-ms022-sse-quota.json),
uid `sovereign-os-ms022-sse-quota`. 10 panels:

| Row | Panels |
|---|---|
| Top stat | saturation % (red threshold = 0.85 matching the alert), active count, cap, tokens-saturated count |
| Time-series | saturation trend with alert threshold lines visualized at 0.85 + 1.0, active-vs-cap gap |
| Triage table | topk(20) per-token subscribers with `Value` → `subscribers` column rename, sorted descending so the heaviest token surfaces on top |
| Time-series | per-token-saturated count over time, per-token cap step-change |
| Companion | M060 chain-health rate cross-context view so operators correlate SSE saturation with chain-wide events |

Imported via Grafana Settings → JSON Model. Tagged
`sovereign-os` / `ms022` / `sse-quota` / `observability`.

### 4. Proxy daemon (`sovereign-ms022-sse-quota-api`)

[`scripts/operator/ms022-sse-quota-api.py`](../../scripts/operator/ms022-sse-quota-api.py)
+ [`systemd/system/sovereign-ms022-sse-quota-api.service`](../../systemd/system/sovereign-ms022-sse-quota-api.service).

The daemon parses the selfdef daemon's `/metrics` exposition body
(UNIX socket first via `/run/selfdef.sock`; TCP fallback via
`$SELFDEF_API_URL` + `$SELFDEF_API_TOKEN`) and emits a compact JSON
envelope on `/api/ms022/sse-quota`. The classifier is locked to the
same thresholds the alert rules use (0.85 + 1.0), so the banner
state and alert firing stay in lockstep.

State enumeration:

| State | Trigger | Banner color |
|---|---|---|
| `ok` | saturation ≤ 0.85 AND `per_token_saturated == 0` | green |
| `approaching` | saturation > 0.85 OR `per_token_saturated > 0` (but below 1.0) | yellow |
| `saturated` | saturation ≥ 1.0 | red |
| `unreachable` | selfdef daemon unreachable / metric absent | gray |

Bind defaults to `127.0.0.1:7711`. Port chosen above the
`m060-health-api` 8160 band so the two daemons coexist without
collision — locked by a contract test that fails CI if either port
drifts.

#### Enable on boot

```bash
sudo systemctl enable --now sovereign-ms022-sse-quota-api.service
sudo systemctl status sovereign-ms022-sse-quota-api.service
```

#### Expose beyond loopback

Drop a `/etc/systemd/system/sovereign-ms022-sse-quota-api.service.d/bind.conf`:

```ini
[Service]
Environment=MS022_SSE_QUOTA_API_BIND=0.0.0.0
```

Then `systemctl daemon-reload && systemctl restart sovereign-ms022-sse-quota-api`.

#### TCP-fallback selfdef

When selfdefd runs on a different host (or the UNIX socket isn't
accessible), drop a `tcp.conf` matching the
`sovereign-m060-health-api.service` convention:

```ini
[Service]
Environment=SELFDEF_API_URL=https://selfdef-host:8443
Environment=SELFDEF_API_TOKEN=<token>
```

---

## Verification recipes

```bash
# 1. The proxy daemon answers.
curl -s http://localhost:7711/healthz
curl -s http://localhost:7711/version

# 2. Live SSE quota state through the proxy.
curl -s http://localhost:7711/api/ms022/sse-quota | jq '.'

# 3. Bare state for incident-response scripting.
curl -s http://localhost:7711/api/ms022/state

# 4. Smoke the proxy without running the daemon (one-shot probe).
python3 /usr/local/lib/sovereign-os/scripts/operator/ms022-sse-quota-api.py \
  --self-check

# 5. Confirm Prometheus loaded the alert rules.
curl -s http://localhost:9090/api/v1/rules \
  | jq '.data.groups[] | select(.name == "ms022-sse-quota")'
```

---

## Failure-mode → first-action crib sheet

| Symptom | First action | Where the fix lives |
|---|---|---|
| Banner says `unreachable` | Verify selfdefd is running: `ssh <selfdef-host> sudo systemctl status selfdefd` | selfdef-host |
| Banner says `unreachable` but selfdefd is up | Verify `/run/selfdef.sock` exists + the sovereign-os user can read it | selfdef-host filesystem perms |
| `MS022SseGlobalQuotaApproaching` firing | Drill into the Grafana per-token table; identify the heaviest token; rotate or raise the cap per the selfdef-side decision tree | selfdef-host config (R10212 — sovereign-os cannot mutate) |
| `MS022SseGlobalQuotaSaturated` firing | Restart selfdefd to clear leaked subscribers; investigate the leak source via the Grafana per-token table | selfdef-host: `systemctl restart selfdefd` |
| `MS022SsePerTokenQuotaSaturated` firing for a specific `token_fp` | Cross-reference the 8-hex prefix with the daemon's tracing output to identify the operator; rotate that operator's token | selfdef-host journal: `journalctl -u selfdefd \| grep <fp-prefix>` |
| `MS022SseGlobalQuotaApproaching` firing on a healthy chain (no leak, no monopoly) | Raise `[api].max_sse_subscribers` in `/etc/selfdef/selfdef.toml` + restart selfdefd | selfdef-host config |
| Grafana panel renders but the time-series is flat | Confirm Prometheus is scraping selfdefd's `/metrics`: `curl -s http://prometheus:9090/api/v1/targets \| jq '.data.activeTargets[]'` | Prometheus host config |
| Master-dashboard banner stays "unknown" indefinitely | `systemctl status sovereign-ms022-sse-quota-api.service` — the proxy daemon may not be running | this-host systemd |

---

## Project boundary (R10212 — sacrosanct)

Every fix in the crib sheet above is an operator action on the
**selfdef host** (config edit, daemon restart, token rotation,
journal grep). The sovereign-os surface only renders the state —
it does not POST to selfdef, does not raise caps, does not rotate
tokens. When the operator clicks any action surface from the
master-dashboard banner OR the Grafana dashboard, what they get is
a clipboard-copy of the right `ssh <selfdef-host> sudo ...` command,
never an HTTP mutation.

The 4 consumer-side surfaces are locked by 50 contract tests across
both repos:

- selfdef-side: 9 `sse_quota_metrics.rs` unit tests
- sovereign-os-side:
  - 12 alert contract tests (`test_ms022_sse_quota_alerts_contract.py`)
  - 10 dashboard contract tests (`test_ms022_sse_quota_dashboard_contract.py`)
  - 15 API + master-dashboard wire-shape tests (`test_ms022_sse_quota_api_contract.py`)
  - 13 systemd unit contract tests (`test_ms022_sse_quota_api_systemd_contract.py`)

Drift on either side fails contract tests on **both** sides.

---

## Operator runbook references

- **Producer side**: [`cyberpunk042/selfdef` → `docs/operator/ms022-sse-subscriber-quota.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/ms022-sse-subscriber-quota.md)
  for cap enforcement semantics + config knob explanation + the
  raise-vs-leak decision tree.
- **Alert runbook**: see the `MS022Sse*` sections of
  [`m060-deployment-guide.md`](m060-deployment-guide.md) for the
  per-alert diagnosis + fix commands.
- **CLI** (this side): the smoke script
  [`scripts/diagnostics/m060-smoke.py`](../../scripts/diagnostics/m060-smoke.py)
  verifies the M060 chain; SSE quota is checked via the proxy
  daemon's `/api/ms022/state` endpoint (curl one-liner above).
  Future enhancement: extend `sovereign-osctl` with an `ms022-doctor`
  verb wrapping the curl probe — additive, not a regression on
  the current state.
