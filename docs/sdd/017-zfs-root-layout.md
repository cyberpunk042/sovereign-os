# SDD-017 — ZFS root layout (Q-005 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-005 (ZFS root layout details)
> Derived from: `profiles/sain-01.yaml` § hardware.storage,
> `schemas/profile.schema.yaml` § storage,
> SDD-005 (initial profiles), SDD-014 (decommission),
> `scripts/hooks/during-install/zfs-pool-create.sh`,
> `scripts/hooks/during-install/zfs-datasets-create.sh`,
> SAIN-01 milestone (info-hub
> `wiki/backlog/milestones/sain-01-sovereign-node.md`).

## Problem

Q-005 ("ZFS root layout details") has been open since PR 1. The
sain-01 profile already declares a tiered ZFS layout (pool name, root
device topology, three first-class datasets with explicit recordsize
/ compression / sync / copies / purpose). But no SDD locks the contract
or explains why this layout vs alternatives. This SDD closes that gap.

## Decision: `tank` single pool with three tiered datasets, raid0
across dual NVMe-PCIe-5

```
tank/                            # zpool, raid0 across nvme0n1 + nvme1n1
├── models/                      # recordsize=1M, compression=lz4
├── context/                     # recordsize=16k, compression=zstd-9,
│                                  copies=2, sync=always
└── agents/                      # recordsize=128k, compression=zstd-3
```

**Mount points**: `/mnt/vault/{models,context,agents}` (set via
`SOVEREIGN_OS_MOUNT_BASE`, default `/mnt/vault`).

**Rootfs**: a separate small partition on the boot device (mkosi-built
image), NOT on ZFS — boot path stays simple, no zfsutils-linux
required at GRUB/initramfs stage.

## Why each dataset has its parameters

### `tank/models` — large weight files
- **recordsize=1M**: aligned with typical model-weight read patterns
  (sequential, large chunks). Larger records reduce FS-metadata
  overhead substantially for 100GB+ files (Ling-2.6-flash, Nemotron-3-
  Nano-Omni, BitNet variants, etc.).
- **compression=lz4**: fast, low-CPU; weight files are already
  pre-compressed at the format level (safetensors, GGUF) so we
  intentionally pick a cheap codec to avoid wasted cycles.
- **redundant_metadata=most**: keep enough metadata redundancy for
  recovery; don't go full=all for weight files (recoverable from HF).

### `tank/context` — state-fabric
- **recordsize=16k**: tiny records align with state-fabric access
  patterns (Weaver writes small structured records; Pulse + Auditor
  read them race-free).
- **compression=zstd-9**: high compression ratio — context payloads
  are textual / structured / repetitive (good entropy).
- **copies=2**: doubles on-disk durability of state-fabric data. The
  raid0 topology has zero redundancy at the device level; copies=2
  on this dataset is the load-bearing durability guarantee.
- **sync=always**: every write is fsync'd. State-fabric correctness
  requires durability before the next agent observes the write.
  ~15-30% throughput hit accepted; tradeoff is intentional.

### `tank/agents` — runtime cache + scratch
- **recordsize=128k**: middle ground — agents read+write a mix of
  small and large objects.
- **compression=zstd-3**: balanced compression — better than lz4 for
  text-heavy scratch but lower CPU than zstd-9.

## Why raid0 (zero redundancy) on the dual NVMe

**Operator-acknowledged tradeoff** (already in `sain-01.yaml`
hardware.storage.devices[0]): raid0 across the dual PCIe-5 NVMe
maximizes throughput + capacity for model storage. **No device-level
redundancy.**

Durability strategy instead:
1. **`tank/context` carries `copies=2`** — irreplaceable state-fabric
   data has logical redundancy even on a raid0 pool.
2. **`tank/models` is reconstructible** — model weights are pullable
   from HuggingFace (model-catalog-sync.sh handles re-pull).
3. **`tank/agents` is scratch** — loss is operator-acceptable.
4. **Snapshot-replicate strategy** (future SDD): periodic `zfs send`
   of `tank/context` to external storage. Not implemented in
   foundation phase; specified here as the binding plan.

Future option: re-declare topology=raidz1 if operator adds a third
NVMe — schema already supports it (raidz enum value).

## Pool naming

- Pool name: `tank` (`SOVEREIGN_OS_POOL_NAME` overridable). Stable
  across all sovereign-os profiles that use zfs-tiered layout.
- Dataset naming: `tank/<purpose>` — short, three-deep max.

## Build-time vs install-time vs runtime

| Phase | Who creates | How |
|---|---|---|
| **build** | nothing | mkosi.repart only reserves the ESP + a small ext4 fallback; the ZFS partition is declared with `Format=none` (per `tests/nspawn/test_mkosi_adapter.sh`'s assertion) |
| **install** (operator boots from image) | `zfs-pool-create.sh` + `zfs-datasets-create.sh` | reads `SOVEREIGN_OS_POOL_DEVICES` env (operator-supplied list of /dev/nvme*); reads `profile.hardware.storage.datasets` for the dataset spec |
| **runtime** | `zfs-arc-clamp.sh` (post-install) | bounds the ARC to a profile-declared max (otherwise ZFS eats all RAM) |
| **recurrent** | `zfs-scrub.sh` weekly | scrub + emit pool-health + scrub-timestamp metrics (SDD-016 Layer B) |
| **decommission** | `zfs-pool-destroy.sh` | destroys pool; requires SOVEREIGN_OS_CONFIRM_DESTROY=YES (SDD-014) |

## ARC sizing (operator-tunable)

`scripts/hooks/post-install/zfs-arc-clamp.sh` writes to
`/etc/modprobe.d/zfs.conf`:
```
options zfs zfs_arc_max=<bytes>
options zfs zfs_arc_min=<bytes>
```

Default for sain-01 (256GB DDR5): cap ARC at 64GB
(`zfs_arc_max=68719476736`), giving ~192GB to the inference stack.

Operator overrides (both honored by the `zfs-arc-clamp` post-install hook;
`_BYTES` takes precedence when both are set):

- `SOVEREIGN_OS_ZFS_ARC_MAX_BYTES` — byte-precise (matches `zfs_arc_max`'s
  native unit), e.g. `68719476736` for 64 GiB.
- `SOVEREIGN_OS_ARC_MAX_GB` — convenience form in whole GiB (e.g. `64`);
  the hook's default is `128`.

## Profile-conditioned variations

Only sain-01 uses zfs-tiered. old-workstation + minimal use ext4
(profile.hardware.storage.layout=ext4 — `rootfs-format-ext4.sh`
handles those; the zfs-* hooks SKIP cleanly per
`test_during_install_gates.sh`).

## Goals

1. **Layout-as-code** — every parameter is in `profiles/sain-01.yaml`
   and consumed by the install-time scripts; no hidden defaults.
2. **State-fabric durability** — copies=2 + sync=always on
   `tank/context` is the irreducible guarantee.
3. **Operator-tunable** — pool name, devices, dataset parameters,
   ARC bounds all env-overridable.
4. **Composable** — profiles that don't need ZFS (old-workstation,
   minimal) simply pick `layout: ext4` and the zfs hooks SKIP.
5. **Decommissionable** — SDD-014 gates the destruction path.

## Non-goals (this SDD)

- Does NOT decide ZFS native encryption (separate future SDD; affects
  secure-boot binding from SDD-015 Q15-B).
- Does NOT decide L2ARC / SLOG device addition (operator can add via
  `zpool add` post-install; sovereign-os doesn't pre-configure).
- Does NOT lock the snapshot-replicate cadence (future SDD when
  Q-014 destructive-loop QEMU test lands and the replication target
  is specified).
- Does NOT prescribe alternative layouts (raidz1, mirror, etc.) — the
  schema supports them; operator can author a variant profile.

## Cross-references

- `profiles/sain-01.yaml` § hardware.storage
- `schemas/profile.schema.yaml` § storage.layout + datasets
- `scripts/hooks/during-install/zfs-pool-create.sh`
- `scripts/hooks/during-install/zfs-datasets-create.sh`
- `scripts/hooks/post-install/zfs-arc-clamp.sh`
- `scripts/hooks/recurrent/zfs-scrub.sh`
- `scripts/hooks/decommission/zfs-pool-destroy.sh`
- `tests/nspawn/test_during_install_gates.sh` (zfs hooks gate coverage)
- `tests/nspawn/test_mkosi_adapter.sh` (asserts ZFS partition has Format=none)
- SDD-014 (decommission)
- SDD-015 (secure-boot — Q15-B notes the disk-encryption binding deferred)
- SDD-016 (observability — zfs-scrub emits Layer B metrics)
