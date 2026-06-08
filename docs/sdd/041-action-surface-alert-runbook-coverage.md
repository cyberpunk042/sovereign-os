# SDD-041 — Action-surface alert runbook coverage (close 64 dead runbook links)

**Status**: ACTIVE
**Owner**: @cyberpunk042 (Architect)
**Created**: 2026-06-08
**Source milestone**: `backlog/milestones/M013-observability-as-control-input.md` (consumer-side alerting + operability) + the selfdef SDD-070..078 responder action surfaces this repo consumes
**Implementation surface**: `config/prometheus/alerts/selfdef-*.rules.yml` (11 action-surface families) + `docs/operator/m060-deployment-guide.md` (operator runbook) + `tests/lint/test_action_surface_alert_runbook_coverage.py` (lockstep gate)

> Closes findings: 64 dead `runbook_url` anchors across the 11 selfdef responder action-surface alert families — every alert pointed at a deployment-guide section that did not exist.

## Mission

The 11 selfdef responder action-surface alert families —
`selfdef-{apparmor-profile-pivots, bpf-map-element-clears,
capability-drops, env-scrubs, kernel-keyring-evictions,
mfa-grant-revocations, mount-bindings, netns-isolations,
process-tree-freezes, socket-fd-revocations, token-revocations}` — ship
**64 Prometheus alerts**, each carrying a `runbook_url` annotation that
deep-links into `docs/operator/m060-deployment-guide.md`.

**Every one of those 64 anchors was dead.** An operator paged by a
critical alert such as `SelfdefTokenRevocationsStateDirMissing`
("SDD-068 enforcement OFFLINE") clicked the runbook link and landed on a
non-existent anchor — no diagnosis, no fix, mid-incident. This is the
worst class of operability failure: the alert fires correctly, but the
path from page → action is broken precisely when it is needed.

The existing `test_m060_alert_runbook_coverage` lint already enforces
this invariant for the `m060-chain-health` family. The action-surface
families had no equivalent gate, so the runbook drift went unnoticed.

## What ships

1. **64 runbook sections** authored into the deployment guide under a new
   `### Action-surface alert runbook (SDD-070..078 + MFA/token
   revocations)` subsection. Each section is **grounded in the real
   alert definition** — Meaning derived from the alert's own
   `description`, Diagnosis referencing the actual published gauge
   metric + the `selfdef-<surface>-textfile.{service,timer}` units +
   the `/var/lib/node_exporter/textfile_collector/<surface>.prom` file,
   Fix specific to the alert category. The four observer-health alerts
   (TextfileEmitFailed / ObserverSilent / StateDirMissing /
   PendingRestoreBacklog) share a diagnosis shape across families; the
   action-specific high-watermark alerts are unique per surface.

2. **A lockstep gate**:
   `tests/lint/test_action_surface_alert_runbook_coverage.py` asserts —
   for all 11 families — that every alert's `runbook_url` anchor
   resolves to a heading in the guide (via GitHub's heading-slug rules),
   AND that each resolved section carries the Meaning/Fix scaffold (a
   heading alone is not a runbook). Drift on either the rules files or
   the guide now fails CI.

## Responsibility boundary

Proper producer↔consumer split preserved: **selfdef** emits the textfile
gauges these alerts fire on (the `selfdef-<surface>-textfile` wrappers);
**sovereign-os** owns the alert rules *and* the operator runbook that
turns a page into an action. This SDD closes the consumer-side operability
half — it does not touch the selfdef producer surface.

## Verification

```
$ pytest -xq tests/lint/test_action_surface_alert_runbook_coverage.py
# 3 passed — 64/64 anchors resolve; every section has Meaning + Fix
```

Before: 64/64 anchors missing. After: 0 missing.

## Non-goals

- Not re-authoring the m060-chain-health runbook (already covered).
- Not changing alert thresholds or expressions — this is operability
  documentation + a coverage gate, not an alerting-policy change.
- Not adding new alert families — the family list is explicit in the
  test so adding one is a deliberate act that forces its runbook coverage.

## Open questions

- **D-1**: Should the per-surface high-watermark thresholds (e.g.
  `*ActiveHigh > 10 for 1h`) be operator-tunable per deployment?
  **Recommendation**: track separately — this SDD closes the runbook
  gap; threshold tuning is an alerting-policy concern for M013's
  follow-up, not a documentation gate.
