# M060 deployment-guide addendum — D-12 rules + D-16 audit-chain coverage closure

> **Status**: corrective addendum to
> [`m060-deployment-guide.md`](m060-deployment-guide.md). Once the
> main guide is updated in-line (pending MCP transaction split / local
> Bash recovery), this addendum can be retired. Until then, treat the
> content below as the authoritative correction for the alert-runbook
> sections it touches.

## The bug, in one paragraph

The `selfdefctl m060-doctor` verb walks the M060 cross-repo mirror
chain to surface wedged or absent mirrors for the operator. It
**originally** covered 6 of the 8 wire-contract domains
(`D-02 active-profile` / `D-13 grants` / `D-14 capability-tokens` /
`D-15 sandboxes` / `D-17 quarantine` / `D-18 trust-scores`) but
silently skipped `D-12 rules` and `D-16 audit-chain` even though:

- The selfdef daemon's `mirror_export_loop` publishes both
  `rules.json` and `audit.json` (see `crates/selfdef-daemon/src/
  mirror_export_loop.rs` `RULES_FILE` + `AUDIT_FILE` consts).
- The selfdef-api `/v1/m060/health` endpoint reports both in its
  10-artifact set.
- The sovereign-os consumer reads both via `/api/d-12` + `/api/d-16`
  endpoints.
- The cross-repo lint
  `tests/lint/test_m060_cross_repo_chain_contract.py` asserts both
  producer-consumer contracts.

Only the operator filesystem-side triage verb was blind to D-12 +
D-16. Closed in selfdef commit `82014d6` (branch
`claude/recover-projects-b0oT6`).

## Corrections to apply to the main deployment guide

### Alert section: M060MirrorDomainChainDegraded (warning)

**Where it lives**: search the main `m060-deployment-guide.md` for
the heading `#### M060MirrorDomainChainDegraded (warning)`.

**Old wording (incorrect)**:

> **Meaning:** the selfdef-side `selfdefctl m060-doctor` reports at
> least one of the 6 mirror domains (D-02/D-13/D-14/D-15/D-17/D-18)
> in WARN state. `selfdef_m060_doctor_worst_severity == 1`.

**New wording (correct)**:

> **Meaning:** the selfdef-side `selfdefctl m060-doctor` reports at
> least one of the 8 mirror domains (D-02/D-12/D-13/D-14/D-15/D-16/
> D-17/D-18) in WARN state. `selfdef_m060_doctor_worst_severity == 1`.

Apply the same 6→8 correction to:

- `#### M060MirrorDomainChainBroken (critical)` if its description
  also lists the 6-domain set.
- `#### M060MirrorDomainObserverSilent (critical)` if its description
  references the per-domain set.

### Per-domain reference table

If the deployment guide carries a per-domain table listing the
mirrors it covers, it should now read:

| Domain | Label | Resident store | Published file |
|---|---|---|---|
| D-02 | active-profile | `/var/lib/selfdef/flex-profile.json` | `active-profile.json` |
| **D-12** | **rules** | **`/var/lib/selfdef/rules.json`** | **`rules.json`** |
| D-13 | grants | `/var/lib/selfdef/grants.json` | `grants.json` |
| D-14 | capability-tokens | `/var/lib/selfdef/capability-tokens.json` | `capability-tokens.json` |
| D-15 | sandboxes | `/var/lib/selfdef/sandboxes.json` | `sandboxes.json` |
| **D-16** | **audit-chain** | **`/var/lib/selfdef/audit.json`** | **`audit.json`** |
| D-17 | quarantine | `/var/lib/selfdef/quarantine.json` | `quarantine.json` |
| D-18 | trust-scores | `/var/lib/selfdef/trust-scores.json` | `trust-scores.json` |

**Bold rows are the previously-skipped pair.**

## Why this matters (operability angle)

Without this correction:

1. **Operator reading the runbook** during a 3 AM M060 incident sees
   "6 mirror domains" and assumes the chain only ships 6 — would
   miss that the wedged mirror might be D-12 (network rules — Ring
   0..4 RuleEntry projection from `nft list ruleset --json`) or
   D-16 (audit chain — every IPS authority decision / OCSF event).
2. **Dashboard panels and CLI verbs** would have looked aligned with
   the doc's claim (6 visible domains) when they're now actually 8.
3. **The post-fix state** is consistent end-to-end: code (commit
   `82014d6`), systemd unit comment (`ddfe907`), debian postinst
   comment (`0f2a664`), SHIPPED.md tracker (`99dcca4`), Grafana
   dashboard (sovereign-os `234a1e0`), alert YAML comments
   (sovereign-os `5c25ded`), lint contracts (sovereign-os `4134317`
   + dashboard regression guard `5f175df`). This addendum closes
   the last operator-facing surface that referenced the old set.

## Operator commands to verify the closure

```sh
# 1. The doctor now lists 8 rows (one per domain).
selfdefctl m060-doctor

# 2. JSON output enumerates all 8 domains explicitly.
selfdefctl m060-doctor --json | jq '.domains[].id'

# Expected output (one per line):
#   "D-02"
#   "D-12"
#   "D-13"
#   "D-14"
#   "D-15"
#   "D-16"
#   "D-17"
#   "D-18"

# 3. The textfile collector emits 8 severity gauges per timer fire.
cat /var/lib/node_exporter/textfile_collector/selfdef-m060-doctor.prom \
  | grep selfdef_m060_doctor_severity \
  | wc -l
# Expected: 8

# 4. The regression-guard test pins the full set:
#    crates/selfdef-cli/src/m060_doctor.rs::tests::
#      domains_cover_full_m060_wire_contract
```

## Cross-references

- selfdef commit closing the bug: [`82014d6`](https://github.com/cyberpunk042/selfdef/commit/82014d64b5022f8b544424530dd322cda18145c1)
- Main deployment guide:
  [`m060-deployment-guide.md`](m060-deployment-guide.md)
- Producer guide (selfdef side):
  [`m060-cockpit-mirror-producers.md`](https://github.com/cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md)
- Cross-repo wire contract test:
  [`tests/lint/test_m060_cross_repo_chain_contract.py`](../../tests/lint/test_m060_cross_repo_chain_contract.py)
- Dashboard regression guard:
  [`tests/lint/test_m060_mirror_domains_dashboard_contract.py`](../../tests/lint/test_m060_mirror_domains_dashboard_contract.py)
