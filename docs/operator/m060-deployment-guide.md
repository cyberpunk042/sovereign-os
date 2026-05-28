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

## Troubleshooting

| symptom | cause | fix |
|---|---|---|
| All 8 mirrors stay red | `selfdef_mirror_dir` not set or daemon not running | check `journalctl -u selfdefd` for the "M060: mirror export enabled" line |
| D-16 stays red while D-13/14/15 are green | audit chain has zero entries (no decisions/events yet) — honest offline | run `selfdefctl audit verify --tail 256`; the chain populates as the daemon decides/observes |
| D-02 only stays red | flex-profile path mismatch | check `selfdef_flex_profile::DEFAULT_STATE_PATH` (`/var/lib/selfdef/flex-profile.json`) |
| D-13/D-14/D-15 stay red after `selfdefctl issue` | API daemon not running, or `SELFDEF_<DOMAIN>_PATH` mismatch between writer (API) + reader (export) | check both honor the same path |
| Mirror flips green then back to red | export loop crashed | check `journalctl -u selfdefd` for "mirror export: ... write failed" |
| Dashboard shows `mirror_status=online` but old data | snapshot stale | the export refreshes every 30s; check `captured_at` timestamp in the banner |

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
