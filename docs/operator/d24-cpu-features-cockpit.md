# D-24 — CPU Features (cockpit panel)

> Read-only cockpit panel. Operator §1g (sacrosanct): **We do not minimize anything.**

## What it is
The deep **AVX-512 capability** view: the raw extension map, the per-AI-workload
fit verdict, and the actionable advisory. Flips the dashboard-catalog
`cpu-features` planned surface to live. **Reuses** `scripts/hardware/avx512-advisor.py`
(`probe`/`workloads`/`advisory` --json) — no drift. Distinct from D-21's
Features-CPU *summary* (this is the full drill-down).

## Surfaces
- api: `scripts/operator/cpu-features-api.py` — `GET /api/cpu-features/{probe,workloads,advisory,stream}`
- webapp: `webapp/d-24-cpu-features/index.html` (`/webapp/`)
- service: `systemd/system/sovereign-cpu-features-api.service` (loopback :8124)
- core: reused `scripts/hardware/avx512-advisor.py`

Registered in surface-map (`cpu-features`, 4/8 ceiling) + nav (D-24) +
dashboard-catalog. SDD-040/045 compliant. Read-only (405 on writes — pure
capability observation, nothing to mutate).

## Run
```sh
python3 scripts/operator/cpu-features-api.py   # http://127.0.0.1:8124/webapp/
```
`--self-check` prints one probe/workloads/advisory view, exit 0.

## Related
D-21 LM Orchestration (Features-CPU summary) · M008 bit-level-cheats · M074 AVX-512-VNNI.
