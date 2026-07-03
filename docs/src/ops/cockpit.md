# The cockpit — dashboards + control surface

> Operator guide to the sovereign-os dashboard cockpit: the ~43 dashboards,
> the control surface on every one of them, the modes/profiles/toggles you can
> drive, and the guarantee that nothing is invisible. Built by SDD-045.

The whole cockpit is **read-only from the browser**. Every control shows you
the exact `sovereign-osctl …` command and copies it to your clipboard — the
web never mutates privileged state (operator §1g / hardening lint). You paste
the command in a terminal (`⚡ YOU RUN`). That boundary is the point: the
dashboards observe and *compose commands*; you execute.

## Start it

```bash
make panel        # or: scripts/operator/panel.sh — no sudo, nothing installed
```

Then open **`http://127.0.0.1:8100/master-dashboard/`** — the front door.

## The front door (master-dashboard)

The master-dashboard is the operator's index. On it:

- **Coverage — everything is reachable.** A live summary (dashboards · control
  systems · verb families mapped · cli-only · **0 invisible**) computed from
  the catalog + control-systems + feature-coverage ledgers. This is the
  answer to "where is everything": every one of the ~176 `sovereign-osctl`
  verb families reaches a dashboard or is an explicit cli-only waiver, and CI
  (`test_feature_coverage.py`) fails if that ever regresses.
- **Controls — profiles, modes & feature toggles.** The 11 control systems
  rendered as cards (see below).
- **All dashboards — described.** Every surface with a real description,
  grouped by category, honestly badged `live` / `snapshot`.
- **⌘K / Ctrl-K palette.** Search *every* dashboard by label, description or
  category and jump to it.
- **Routes + health + selfdef mirror producers** for the reverse-proxy
  aggregator path.

`http://127.0.0.1:8100/panels` is the same described catalog as a standalone
global view.

## The control surface (on every dashboard)

Every panel carries a **controls — profiles, modes & feature toggles**
section. It renders the controls that are *global* (appear everywhere) plus
the ones that *govern that specific panel*:

- **Global controls (every panel):** the OS-profile picker, per-dashboard
  on/off toggle, and the per-surface auth tier.
- **Scoped controls:** e.g. Runtime-Modes shows the runtime mode, cpu-mode,
  gpu-mode, flex deltas and workload knobs; the Trinity panel shows the
  inference tiers; the security panels show selfdef + perimeter.

Each card lists the control's options and a **copy-command** button. Click it,
paste the command, done.

## The 11 control systems ("everything on/off + tons of modes and profiles")

The single source of truth is `config/control-systems.yaml`. The systems:

| System | What it does | CLI |
|--------|--------------|-----|
| OS profile | hardware/role archetype | `profiles switch <id>` |
| Runtime mode (§18) | how the 3 Trinity tiers are allocated | `trinity profile switch <id>` |
| Flex deltas | reversible per-allocation overrides | `profiles flex set <k> <v>` |
| CPU mode | frequency governor | `cpu-mode set <mode>` |
| GPU mode | per-GPU power mode | `gpu-mode set <mode>` |
| Dashboard on/off | turn any dashboard on/off | `dashboards {enable\|disable} <slug>` |
| Auth tier | per-surface auth ladder | `auth-tier set <dash> <tier> …` |
| selfdef (IPS) | the intrusion-prevention system | `selfdef {on\|off}` |
| Perimeter | Tetragon eBPF perimeter | `perimeter reload` |
| Inference tiers | start/stop each Trinity tier | `inference {start\|stop} <tier>` |
| Workload knobs | MPS / hugepages / THP / IRQ / isolation | `workload-knobs set <knob> <v>` |

## The dashboards

~43 dashboards across five categories (Trinity & orchestration · Models &
compute · Hardware & operations · Security & selfdef · Governance & meta). The
described catalog on the front door is the live index. Notable net-new ones
(SDD-045 §5) that fill the "where are the Models / AVX / orchestration" gaps:

- **models-catalog** — browse all 68 models; filter by tier/class/quant/
  purpose/status/max-VRAM.
- **cpu-features** — live AVX-512 probe of *this* CPU + per-workload fit matrix.
- **orchestration** — the 7-axis routing rules + live routing metrics.
- **profile-generation** — the runtime strategies + the allocations they
  resolve to, with the generate command.
- **selfdef-management** — the IPS on/off state + the 6 mirror dashboards
  (D-13..D-18) + perimeter.

## Your rules survive a reflash

The AI's operator-interaction rules are versioned in `assets/operator-memory/`
and re-applied on `make provision`, so a fresh flash restores them. Manage
them with `sovereign-osctl operator-rules {status,apply,capture,compat}`. See
[Managing THIS OS](./run-on-host.md).
