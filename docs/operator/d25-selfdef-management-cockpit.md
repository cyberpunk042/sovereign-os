# D-25 — Self-Defense Management (cockpit panel)

> Read-only **consumer** cockpit panel. Operator §1g (sacrosanct): **We do not minimize anything.**

## What it is
The operator's unified view of the **selfdef intrusion-prevention system**: live
**on/off enablement**, the **M060 mirror-chain health** (how many of the 10 mirror
artifacts are fresh + the aggregate chain state), and pointers to the six
per-domain security panels (**D-13..D-18**). It consolidates "is selfdef running,
and is its mirror chain healthy" into one surface, with the on/off control right
there as a clipboard-copied signed CLI verb.

## Boundary (R10212 — load-bearing)
sovereign-os is the **CONSUMER**; selfdef is the **PRODUCER**. This panel is
**strictly READ-ONLY**: it derives selfdef state through the sanctioned M060
consumer proxy (`scripts/operator/m060-health.py` `probe()`) and **never** mutates
selfdef. The on/off control is the SDD-045 control-surface's `selfdef` control
(`change_cli: sovereign-osctl selfdef {on|off}`, already in
`config/control-systems.yaml`) — a **clipboard copy**, never an HTTP mutation. The
daemon rejects every POST/PUT/DELETE with `405`. When the selfdef producer is
unreachable (the CI/dev case), the panel renders a graceful `unreachable`
envelope rather than failing.

## Surfaces
- api: `scripts/operator/selfdef-management-api.py` — `GET /api/selfdef-management/{state,stream}`, `GET /control-systems`
- webapp: `webapp/d-25-selfdef-management/index.html` (`/webapp/`)
- service: `systemd/system/sovereign-selfdef-management-api.service` (R171 hardened, loopback :8125)
- core: reused `scripts/operator/m060-health.py` `probe()` (READ-ONLY M060 consumer proxy)

Registered in surface-map (`selfdef-management`, 4/8 ceiling) + nav (D-25) +
dashboard-catalog (`selfdef-management` → api `sovereign-selfdef-management-api`).
SDD-040 palette + SDD-045 control-surface compliant.

## Run
```sh
python3 scripts/operator/selfdef-management-api.py   # http://127.0.0.1:8125/webapp/
```
`--self-check` prints the derived state (selfdef enablement + M060 chain +
mirror panels), exit 0.

## Related
D-13..D-18 selfdef-domain panels (mirror consumers) · M060 mirror-chain · selfdef
producer (`sovereign-osctl selfdef …`). Producer/consumer split per R10212.
