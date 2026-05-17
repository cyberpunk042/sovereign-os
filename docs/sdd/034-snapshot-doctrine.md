# SDD-034 — Snapshot doctrine (E9.M15 / R336)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: E9.M15 (mandate decomposition)
> Derived from: lived practice of R322 + R324 + R332 + R333 + R334
> + R335 — the 6-script snapshot family

## Mission

Snapshots are the operator's audit + backup + drift-detection
primitive. The 6 snapshot scripts shipped in this round set
(R322 / R324 / R332 / R333 / R334 / R335) form a family that must
interoperate forever — producer-side rounds (R322 / R332) emit
JSON that consumer-side rounds (R324 / R333 / R334 / R335) ingest.
Changing a producer's schema without coordinating consumers breaks
the family. SDD-034 codifies the contracts so this can't happen
silently.

## The snapshot family — 6 scripts

| Round | Script | Producer or Consumer | Snapshot Round-ID |
|-------|--------|----------------------|--------------------|
| R322 (E2.M18) | `scripts/diagnostics/state-snapshot.py` | producer | **R322** |
| R324 (E2.M20) | `scripts/fleet/snapshot-aggregator.py` | consumer of R322 | (aggregates) |
| R332 (E2.M23) | `scripts/diagnostics/config-snapshot.py` | producer | **R332** |
| R333 (E2.M24) | `scripts/diagnostics/config-restore.py` | consumer of R332 | (verifies + writes) |
| R334 (E2.M25) | `scripts/diagnostics/snapshot-diff.py` | consumer of R322 × 2 | (diffs) |
| R335 (E2.M26) | `scripts/diagnostics/config-snapshot-diff.py` | consumer of R332 × 2 | (diffs) |

## Schema invariants

Every snapshot JSON document MUST carry:

```json
{
  "schema_version": "1.0.0",
  "round": "R322" | "R332",
  "sdd_vector": "E2.M18" | "E2.M23",
  // ...payload...
}
```

These three fields are operator-stable contract — consumers reject
documents whose `round` doesn't match the expected producer round
(R333/R334 demand R322; R335 demands R332). The L1 lint pins this.

## Producer-consumer contract

### R322 → R324 / R334

R322 emits:
```json
{
  "round": "R322",
  "snapshot_at": "<ISO-8601 UTC>",
  "snapshot_at_epoch": <float>,
  "probes": [
    {"name": "<probe-name>", "axis": "<axis>", "rc": <int>,
     "duration_ms": <int>, "available": <bool>,
     "output": <probe-JSON> | {"raw_stdout": ..., "raw_stderr": ...}},
    ...
  ],
  ...
}
```

R324 (fleet aggregator) consumes one R322 per host + emits
cross-host rollup.
R334 (state snapshot-diff) consumes two R322 + emits per-probe
delta.

### R332 → R333 / R335

R332 emits:
```json
{
  "round": "R332",
  "captured_at": "<ISO-8601 UTC>",
  "host": "<hostname>",
  "overlays": [
    {"overlay_file": "<name.toml>", "overlay_path": "<full path>",
     "size_bytes": <int>, "sha256": "<64-hex>",
     "body_b64": "<base64-of-file-bytes>"},
    ...
  ],
  "helper_library": {"modules": [...]},
  ...
}
```

R333 (config-restore) consumes one R332 + replays overlays.
R335 (config-snapshot-diff) consumes two R332 + emits per-overlay
delta.

## NEVER-raise contract (inherited from SDD-032 helper library)

All 6 snapshot scripts inherit the NEVER-raise discipline:

| Script | Failure mode | Recovery |
|--------|--------------|----------|
| R322 | one probe times out / crashes | `available=false` + skips; other probes complete |
| R324 | snapshot file unreadable | skips that file; aggregates remaining |
| R332 | overlay file unreadable | skips that overlay; rest captured |
| R333 | sha256 mismatch | refuses to write that overlay; `rc=1`; others proceed |
| R334 | round mismatch | `rc=2` + structured error JSON |
| R335 | round mismatch | `rc=2` + structured error JSON |

## Round-mismatch enforcement

Consumers verify `round == "R322"` (for R333/R334) or `round ==
"R332"` (for R335) before processing. Mismatch → `rc=2` +
structured error JSON. Operator can't accidentally feed a config
snapshot to a state-snapshot consumer or vice-versa.

## Schema-version evolution

`schema_version` follows semver. Backward-compatible field additions
bump the patch (`1.0.0` → `1.0.1`). Schema changes that break
existing consumers bump the major (`1.0.0` → `2.0.0`) — consumers
ALSO bump the version they accept + the L1 lint pins the mapping.

The current version is locked at `1.0.0` across all 6 scripts. A
future round that needs `2.0.0` must:
- Update the producer's emitted `schema_version`
- Update every consumer to accept `2.0.0`
- Document the schema delta in this SDD
- Update the L1 lint mapping
- Run R331 self-test to catch any consumer that wasn't updated

## L1 lint enforcement

`tests/lint/test_snapshot_doctrine.py` pins:
- The 6 snapshot scripts exist at expected paths
- Each script declares `SCHEMA_VERSION = "1.0.0"`, `ROUND = "R<N>"`,
  `SDD_VECTOR = "E<n>.M<m>"` constants matching the table above
- Producer rounds (R322 / R332) declare those exact round IDs
- Consumer rounds carry round-mismatch handling
- This SDD-034 carries required sections (R326 pattern)

## What this SDD does NOT do

- It does NOT lock in PROBE schemas — R322 probes evolve as new
  advisors land; the snapshot-level envelope is the contract.
- It does NOT freeze the catalog — R322 can add new probes; R324
  / R334 handle missing/new probes via their diff categories.
- It does NOT prevent a 7th snapshot script from joining the
  family — adoption requires a new SDD section + new L1 pin.

## Future snapshot-family evolution

If a future round adds, e.g.:
- `R336 snapshot-merge` (combine multiple R322 → unified view)
- `R337 snapshot-replay` (re-execute the probes that were captured)
- `R338 snapshot-sign` (gpg-sign snapshots for tamper detection)

…the new round extends this SDD: new table row + new L1 pin +
producer/consumer arrow + adoption note in next R285 quarterly
review.
