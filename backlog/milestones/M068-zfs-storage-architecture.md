# M068 — ZFS storage architecture (tank/context + sync=always + ashift=12 + lz4 + recordsize)

**Parent**: sovereign-os runtime — substrate storage layer
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md`
- Phase III: Storage Layer + DKMS (lines 680-695)
- Phase IV: Container Storage Divergence (lines 705-707)
- Layer Allocation Scheme + KV cache compression (lines 913-925)
**Project boundary**: M068 catalogs ZFS pool architecture for sovereign-os; selfdef MS037 (existing) handles IPS-side filesystem boundary enforcement; cross-repo binding via MS007 mirrors only.

## Doctrinal anchors

> "zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank /dev/nvme0n1" (dump 693)
> "zfs create tank/context" (dump 694)
> "zfs set sync=always tank/context" (dump 695)
> "Map Podman's internal graph driver storage to write directly into an uncompressed ZFS data dataset (`tank/containers`) optimized with matching allocation block sizes (`recordsize=16k`)." (dump 706)

## Epics (E0658-E0667)

| epic | name | source |
|---|---|---|
| E0658 | ZFS DKMS initialization — install dkms + zfs-dkms + zfsutils-linux | dump 682-684 |
| E0659 | Module binding validation — dkms status verification | dump 686-688 |
| E0660 | Pool hardening — `zpool create` with ashift=12 / lz4 / atime=off | dump 691-693 |
| E0661 | tank dataset hierarchy — tank / tank/context / tank/containers / tank/models / tank/logs | dump 693-706 + architecture |
| E0662 | sync=always for tank/context — synchronous writes for sovereignty/integrity-critical state | dump 695 |
| E0663 | recordsize=16k for tank/containers — Podman graph driver alignment | dump 706 |
| E0664 | recordsize tuning per dataset — matrix-weights / KV-cache / logs differ in optimal block size | architecture + dump 691 |
| E0665 | Layer allocation scheme — layer maps + KV cache fp8 compression for inference engines | dump 911-925 |
| E0666 | ZFS dataset → SFIF phase mapping — each phase has dataset-allocation requirements | architecture + cross-ref M063 |
| E0667 | ZFS snapshot policy — every high-risk commit (M041) creates pre-commit snapshot retained 365 days | cross-ref selfdef MS037 + MS041 |

## Modules (M01139-M01155)

| module | name | source |
|---|---|---|
| M01139 | sovereign-zfs-dkms-installer | dump 682-684 |
| M01140 | sovereign-zfs-module-validator | dump 686-688 |
| M01141 | sovereign-zfs-pool-creator | dump 691-693 |
| M01142 | sovereign-zfs-dataset-hierarchy-builder | dump 693-706 |
| M01143 | sovereign-zfs-sync-always-enforcer | dump 695 |
| M01144 | sovereign-zfs-recordsize-tuner | dump 706 |
| M01145 | sovereign-zfs-compression-policy (lz4 / off) | dump 691 + 706 |
| M01146 | sovereign-zfs-atime-disabler | dump 691 |
| M01147 | sovereign-zfs-ashift-12-validator | dump 691 |
| M01148 | sovereign-zfs-snapshot-policy-engine | cross-ref selfdef MS037 + MS041 |
| M01149 | sovereign-zfs-rollback-engine | cross-ref selfdef MS041 |
| M01150 | sovereign-zfs-replay-validator | cross-ref selfdef MS009 |
| M01151 | sovereign-zfs-layer-allocation-mapper | dump 911-925 |
| M01152 | sovereign-zfs-kv-cache-fp8-coordinator | dump 924-925 |
| M01153 | sovereign-zfs-typed-mirror | cross-ref selfdef MS007 |
| M01154 | sovereign-zfs-event-emitter | cross-ref M049 + selfdef MS026 |
| M01155 | sovereign-zfs-dashboard-binding (D-09 hardware pressure + D-08 rollback points + D-04 costs) | cross-ref M060 |

## Features (F05696-F05780)

| feature | name | source |
|---|---|---|
| F05696 | DKMS — install dkms package | dump 683 |
| F05697 | DKMS — install zfs-dkms package | dump 683 |
| F05698 | DKMS — install zfsutils-linux package | dump 683 |
| F05699 | DKMS — manual compilation verification of out-of-tree ZFS module against tailored kernel | dump 686 |
| F05700 | DKMS — verify `dkms status` shows zfs module loaded for 6.12-znver5 kernel | dump 687-688 |
| F05701 | DKMS — DKMS errors halt installation (no structural errors allowed) | dump 686 |
| F05702 | Pool creation — `zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank /dev/nvme0n1` | dump 693 |
| F05703 | Pool — ashift=12 (4KB physical block alignment for modern NVMe) | dump 691-693 |
| F05704 | Pool — compression=lz4 (default; balanced compression + speed) | dump 691-693 |
| F05705 | Pool — atime=off (eliminates access-time writes) | dump 691-693 |
| F05706 | Pool — target NVMe array (PCIe 5 dual-NVMe per SAIN-01 hardware) | architecture + dump 691 |
| F05707 | Pool — RAID 0 stripe across dual NVMe for max throughput | architecture + M044 |
| F05708 | Dataset — `zfs create tank/context` (sovereignty-critical state) | dump 694 |
| F05709 | Dataset — tank/context: sync=always (synchronous writes) | dump 695 |
| F05710 | Dataset — tank/context: optimized for matrix-weights operations | dump 691 |
| F05711 | Dataset — tank/containers: uncompressed for Podman graph driver | dump 706 |
| F05712 | Dataset — tank/containers: recordsize=16k | dump 706 |
| F05713 | Dataset — tank/models: recordsize=1M (large model file blocks) | architecture |
| F05714 | Dataset — tank/models: compression=zstd-3 (better for LLM weights) | architecture |
| F05715 | Dataset — tank/logs: recordsize=128k | architecture |
| F05716 | Dataset — tank/logs: compression=lz4 | architecture |
| F05717 | Dataset — tank/snapshots: recordsize=128k | architecture |
| F05718 | Dataset — tank/snapshots: retained for M041 high-risk commit rollbacks | cross-ref selfdef MS041 |
| F05719 | Dataset — tank/vault: tank/vault/context security audit logs | dump 981 + architecture |
| F05720 | Dataset hierarchy — operator-customizable via /etc/sovereign-os/zfs-layout.toml | architecture |
| F05721 | Dataset hierarchy — TOML signed via MS003 | cross-ref selfdef MS003 |
| F05722 | sync=always — applies to tank/context for sovereignty/integrity-critical state | dump 695 |
| F05723 | sync=always — optional for non-critical datasets | architecture |
| F05724 | sync=always — guarantees ZIL commit before write acknowledgment | architecture |
| F05725 | sync=always — composes with ZFS SLOG device for performance (if present) | architecture |
| F05726 | recordsize — 16k for containers (Podman alignment) | dump 706 |
| F05727 | recordsize — 1M for tank/models (large weights) | architecture |
| F05728 | recordsize — 128k for tank/logs (mixed-size logs) | architecture |
| F05729 | recordsize — 4k for tank/db (if databases used) | architecture |
| F05730 | recordsize — tunable per dataset, signed change | cross-ref selfdef MS003 |
| F05731 | Snapshot policy — every M041 high-risk commit produces pre-commit snapshot | cross-ref selfdef MS041 |
| F05732 | Snapshot policy — snapshot name format `selfdef-pre-commit-<commit-id>` | cross-ref selfdef MS041 + MS037 |
| F05733 | Snapshot policy — snapshots retained 365 days minimum | cross-ref selfdef MS037 |
| F05734 | Snapshot policy — daily auto-snapshots of tank/context (zfs-auto-snapshot) | architecture |
| F05735 | Snapshot policy — daily snapshots retained 30 days | architecture |
| F05736 | Snapshot policy — weekly snapshots retained 90 days | architecture |
| F05737 | Snapshot policy — monthly snapshots retained 365 days | architecture |
| F05738 | Snapshot policy — operator can disable per dataset | operator standing direction "everything can be turned on and off" |
| F05739 | Rollback engine — `zfs rollback <snapshot>` reverts to pre-commit state | cross-ref selfdef MS041 |
| F05740 | Rollback engine — operator confirmation required for rollback | cross-ref selfdef MS041 + MS003 |
| F05741 | Rollback engine — emits OCSF Audit Activity class 1003 on revert | cross-ref selfdef MS026 |
| F05742 | Rollback engine — emits M049 trace on revert | cross-ref M049 |
| F05743 | Rollback engine — atomic (entire dataset reverted at once) | architecture |
| F05744 | Replay validator — verifies snapshot chain integrity | cross-ref selfdef MS009 |
| F05745 | Replay validator — detects unauthorized snapshot deletion | cross-ref selfdef MS009 + MS003 |
| F05746 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F05747 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 |
| F05748 | Layer allocation — Layer 0-30 pinned to high-throughput GPU 0 (RTX 4090) | dump 916-917 |
| F05749 | Layer allocation — Layer 31-80 pinned to massive VRAM GPU 1 (Blackwell 96GB) | dump 916-917 |
| F05750 | Layer allocation — KV Cache compressed to 4-bit width | dump 918 |
| F05751 | Layer allocation — fp8 KV-cache dtype option (--kv-cache-dtype fp8) | dump 924 |
| F05752 | Layer allocation — tensor-parallel-size 2 (dual GPU) | dump 922 |
| F05753 | Layer allocation — pipeline-parallel-size 1 | dump 923 |
| F05754 | Layer allocation — gpu-memory-utilization 0.95 | dump 924 |
| F05755 | Layer allocation — uses vllm/vllm-openai:latest container | dump 921 |
| F05756 | Layer allocation — models mounted from /mnt/vault/models:/models:ro | dump 921 |
| F05757 | Layer allocation — composes with M058 hardware-aware scheduler | cross-ref M058 |
| F05758 | Layer allocation — composes with M076 three load-balancing profiles (pending) | cross-ref M076 (pending) |
| F05759 | ZFS dataset → SFIF phase — Scaffold needs tank/context only | cross-ref M063 |
| F05760 | ZFS dataset → SFIF phase — Foundation needs tank/context + tank/snapshots | cross-ref M063 |
| F05761 | ZFS dataset → SFIF phase — Infrastructure begin needs tank/containers added | cross-ref M063 |
| F05762 | ZFS dataset → SFIF phase — Infrastructure continue needs tank/models added | cross-ref M063 |
| F05763 | ZFS dataset → SFIF phase — Features phase needs tank/logs + tank/vault added | cross-ref M063 |
| F05764 | Typed mirror — sovereign-zfs-layout-mirror crate under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F05765 | Typed mirror — ZfsLayout struct {pool_name, datasets[], compression, ashift, sync_mode, retention_policy} | cross-ref selfdef MS007 |
| F05766 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F05767 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F05768 | Event emitter — every dataset creation emits M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + selfdef MS026 |
| F05769 | Event emitter — every snapshot emits M049 trace + OCSF File System Activity class 1001 | cross-ref M049 + selfdef MS026 |
| F05770 | Event emitter — every rollback emits M049 trace + OCSF Audit Activity class 1003 | cross-ref M049 + selfdef MS026 |
| F05771 | Dashboard — D-09 hardware pressure shows zpool IOPS / latency / fill | cross-ref M060 |
| F05772 | Dashboard — D-08 rollback points lists snapshots with retention info | cross-ref M060 |
| F05773 | Dashboard — D-04 costs shows storage consumption per dataset | cross-ref M060 |
| F05774 | CLI — `sovereign zfs layout show` returns current layout | architecture |
| F05775 | CLI — `sovereign zfs snapshot <dataset> --name <name>` creates snapshot | cross-ref selfdef MS003 |
| F05776 | CLI — `sovereign zfs rollback <snapshot>` rolls back (operator-signed) | cross-ref selfdef MS003 + MS041 |
| F05777 | CLI — `sovereign zfs status` returns pool health | architecture |
| F05778 | Boundary — IPS (selfdef MS037) enforces fanotify policy on ZFS-mounted paths | cross-ref selfdef MS037 |
| F05779 | Boundary — ZFS layout NEVER mutated from selfdef IPS (sovereign-os runtime controls) | operator standing direction | 
| F05780 | Closing — M068 covers dump 680-706 + 913-925 verbatim; M069→MS044 Guardian Daemon next | dump 680-706 + 913-925 + operator standing direction |

## Requirements (R11391-R11560)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R11391 | Doctrinal — pool create: ashift=12 / compression=lz4 / atime=off | dump 693 | F05702 | non-negotiable | false | 10 |
| R11392 | Doctrinal — `zfs create tank/context` | dump 694 | F05708 | non-negotiable | false | 10 |
| R11393 | Doctrinal — `zfs set sync=always tank/context` | dump 695 | F05709 | non-negotiable | false | 10 |
| R11394 | Doctrinal — tank/containers recordsize=16k for Podman graph driver alignment | dump 706 | F05712 | non-negotiable | false | 10 |
| R11395 | Doctrinal — tank/containers uncompressed for Podman | dump 706 | F05711 | non-negotiable | false | 10 |
| R11396 | DKMS — install dkms package | dump 683 | F05696 | non-negotiable | false | 10 |
| R11397 | DKMS — install zfs-dkms package | dump 683 | F05697 | non-negotiable | false | 10 |
| R11398 | DKMS — install zfsutils-linux package | dump 683 | F05698 | non-negotiable | false | 10 |
| R11399 | DKMS — manual compilation verification of out-of-tree ZFS module against tailored kernel | dump 686 | F05699 | non-negotiable | false | 10 |
| R11400 | DKMS — `dkms status` verifies zfs module loaded for 6.12-znver5 kernel | dump 687-688 | F05700 | non-negotiable | false | 10 |
| R11401 | DKMS — DKMS errors halt installation (no structural errors allowed) | dump 686 | F05701 | non-negotiable | false | 10 |
| R11402 | DKMS — DKMS errors emit OCSF Detection 2004 | cross-ref selfdef MS026 | F05701 | non-negotiable | false | 10 |
| R11403 | DKMS — DKMS rebuild on every kernel update | architecture + cross-ref M067 | F05699 | non-negotiable | false | 10 |
| R11404 | DKMS — DKMS rebuild signed via MS003 | cross-ref selfdef MS003 | F05699 | non-negotiable | false | 10 |
| R11405 | DKMS — DKMS rebuild emits M049 trace | cross-ref M049 | F05699 | non-negotiable | false | 10 |
| R11406 | Pool — `zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank /dev/nvme0n1` | dump 693 | F05702 | non-negotiable | false | 10 |
| R11407 | Pool — ashift=12 (4KB physical block alignment) | dump 691-693 | F05703 | non-negotiable | false | 10 |
| R11408 | Pool — compression=lz4 (balanced compression + speed) | dump 691-693 | F05704 | non-negotiable | false | 10 |
| R11409 | Pool — atime=off (eliminates access-time writes) | dump 691-693 | F05705 | non-negotiable | false | 10 |
| R11410 | Pool — target NVMe array (PCIe 5 dual-NVMe per SAIN-01) | architecture + cross-ref M044 | F05706 | non-negotiable | false | 10 |
| R11411 | Pool — RAID 0 stripe across dual NVMe for max throughput | architecture + M044 | F05707 | non-negotiable | false | 10 |
| R11412 | Pool — pool name `tank` (verbatim from dump 693) | dump 693 | F05702 | non-negotiable | false | 10 |
| R11413 | Pool — pool integrity verified via `zpool status` post-create | architecture | F05702 | non-negotiable | false | 10 |
| R11414 | Pool — creation emits M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + selfdef MS026 | F05768 | non-negotiable | false | 10 |
| R11415 | Pool — creation signed via MS003 | cross-ref selfdef MS003 | F05702 | non-negotiable | false | 10 |
| R11416 | Dataset — tank/context (verbatim from dump 694) | dump 694 | F05708 | non-negotiable | false | 10 |
| R11417 | Dataset — tank/context sync=always | dump 695 | F05709 | non-negotiable | false | 10 |
| R11418 | Dataset — tank/context optimized for matrix-weights | dump 691 | F05710 | non-negotiable | false | 10 |
| R11419 | Dataset — tank/containers uncompressed | dump 706 | F05711 | non-negotiable | false | 10 |
| R11420 | Dataset — tank/containers recordsize=16k | dump 706 | F05712 | non-negotiable | false | 10 |
| R11421 | Dataset — tank/models recordsize=1M | architecture | F05713 | non-negotiable | false | 10 |
| R11422 | Dataset — tank/models compression=zstd-3 | architecture | F05714 | non-negotiable | false | 10 |
| R11423 | Dataset — tank/logs recordsize=128k | architecture | F05715 | non-negotiable | false | 10 |
| R11424 | Dataset — tank/logs compression=lz4 | architecture | F05716 | non-negotiable | false | 10 |
| R11425 | Dataset — tank/snapshots recordsize=128k | architecture | F05717 | non-negotiable | false | 10 |
| R11426 | Dataset — tank/snapshots retained for MS041 high-risk commit rollbacks | cross-ref selfdef MS041 | F05718 | non-negotiable | false | 10 |
| R11427 | Dataset — tank/vault for security audit logs (per dump 981 path tank/context/security_audit.log) | dump 981 | F05719 | non-negotiable | false | 10 |
| R11428 | Dataset hierarchy — operator-customizable via /etc/sovereign-os/zfs-layout.toml | architecture | F05720 | non-negotiable | false | 10 |
| R11429 | Dataset hierarchy — TOML signed via MS003 | cross-ref selfdef MS003 | F05721 | non-negotiable | false | 10 |
| R11430 | Dataset hierarchy — TOML changes emit OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05768 | non-negotiable | false | 10 |
| R11431 | Dataset hierarchy — TOML changes emit M049 trace | cross-ref M049 | F05768 | non-negotiable | false | 10 |
| R11432 | sync=always — applies to tank/context for sovereignty/integrity-critical state | dump 695 | F05722 | non-negotiable | false | 10 |
| R11433 | sync=always — optional for non-critical datasets | architecture | F05723 | non-negotiable | false | 10 |
| R11434 | sync=always — guarantees ZIL commit before write acknowledgment | architecture | F05724 | non-negotiable | false | 10 |
| R11435 | sync=always — composes with ZFS SLOG device for performance | architecture | F05725 | non-negotiable | false | 10 |
| R11436 | recordsize — 16k for tank/containers | dump 706 | F05726 | non-negotiable | false | 10 |
| R11437 | recordsize — 1M for tank/models | architecture | F05727 | non-negotiable | false | 10 |
| R11438 | recordsize — 128k for tank/logs | architecture | F05728 | non-negotiable | false | 10 |
| R11439 | recordsize — 4k for tank/db (databases) | architecture | F05729 | non-negotiable | false | 10 |
| R11440 | recordsize — tunable per dataset, signed change | cross-ref selfdef MS003 | F05730 | non-negotiable | false | 10 |
| R11441 | Snapshot — every M041 high-risk commit produces pre-commit snapshot | cross-ref selfdef MS041 | F05731 | non-negotiable | false | 10 |
| R11442 | Snapshot — name format `selfdef-pre-commit-<commit-id>` | cross-ref selfdef MS041 + MS037 | F05732 | non-negotiable | false | 10 |
| R11443 | Snapshot — retained 365 days minimum | cross-ref selfdef MS037 | F05733 | non-negotiable | false | 10 |
| R11444 | Snapshot — daily auto-snapshot of tank/context | architecture | F05734 | non-negotiable | false | 10 |
| R11445 | Snapshot — daily snapshots retained 30 days | architecture | F05735 | non-negotiable | false | 10 |
| R11446 | Snapshot — weekly snapshots retained 90 days | architecture | F05736 | non-negotiable | false | 10 |
| R11447 | Snapshot — monthly snapshots retained 365 days | architecture | F05737 | non-negotiable | false | 10 |
| R11448 | Snapshot — operator can disable per dataset | operator standing direction "everything can be turned on and off" | F05738 | non-negotiable | false | 10 |
| R11449 | Snapshot — every snapshot emits M049 trace | cross-ref M049 | F05769 | non-negotiable | false | 10 |
| R11450 | Snapshot — every snapshot emits OCSF File System Activity class 1001 | cross-ref selfdef MS026 | F05769 | non-negotiable | false | 10 |
| R11451 | Rollback — `zfs rollback <snapshot>` reverts to pre-commit state | cross-ref selfdef MS041 | F05739 | non-negotiable | false | 10 |
| R11452 | Rollback — operator confirmation required | cross-ref selfdef MS041 + MS003 | F05740 | non-negotiable | false | 10 |
| R11453 | Rollback — emits OCSF Audit Activity class 1003 | cross-ref selfdef MS026 | F05741 | non-negotiable | false | 10 |
| R11454 | Rollback — emits M049 trace | cross-ref M049 | F05742 | non-negotiable | false | 10 |
| R11455 | Rollback — atomic (entire dataset reverted at once) | architecture | F05743 | non-negotiable | false | 10 |
| R11456 | Rollback — never silently drops state | cross-ref selfdef MS041 | F05743 | non-negotiable | false | 10 |
| R11457 | Replay validator — verifies snapshot chain integrity | cross-ref selfdef MS009 | F05744 | non-negotiable | false | 10 |
| R11458 | Replay validator — detects unauthorized snapshot deletion | cross-ref selfdef MS009 + MS003 | F05745 | non-negotiable | false | 10 |
| R11459 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F05746 | non-negotiable | false | 10 |
| R11460 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 | F05747 | non-negotiable | false | 10 |
| R11461 | Replay validator — failures halt new high-risk commits | architecture | F05744 | non-negotiable | false | 10 |
| R11462 | Layer allocation — Layer 0-30 pinned to high-throughput GPU 0 (4090) | dump 916-917 | F05748 | non-negotiable | false | 10 |
| R11463 | Layer allocation — Layer 31-80 pinned to massive VRAM GPU 1 (Blackwell 96GB) | dump 916-917 | F05749 | non-negotiable | false | 10 |
| R11464 | Layer allocation — KV cache compressed to 4-bit width to maximize active token context length | dump 918 | F05750 | non-negotiable | false | 10 |
| R11465 | Layer allocation — fp8 KV-cache dtype option | dump 924 | F05751 | non-negotiable | false | 10 |
| R11466 | Layer allocation — tensor-parallel-size 2 (dual GPU) | dump 922 | F05752 | non-negotiable | false | 10 |
| R11467 | Layer allocation — pipeline-parallel-size 1 | dump 923 | F05753 | non-negotiable | false | 10 |
| R11468 | Layer allocation — gpu-memory-utilization 0.95 | dump 924 | F05754 | non-negotiable | false | 10 |
| R11469 | Layer allocation — uses vllm/vllm-openai:latest container | dump 921 | F05755 | non-negotiable | false | 10 |
| R11470 | Layer allocation — models mounted from /mnt/vault/models:/models:ro (read-only) | dump 921 | F05756 | non-negotiable | false | 10 |
| R11471 | Layer allocation — composes with M058 hardware-aware scheduler | cross-ref M058 | F05757 | non-negotiable | false | 10 |
| R11472 | Layer allocation — composes with M076 three load-balancing profiles (pending) | cross-ref M076 (pending) | F05758 | non-negotiable | false | 10 |
| R11473 | SFIF phase — Scaffold needs tank/context only | cross-ref M063 | F05759 | non-negotiable | false | 10 |
| R11474 | SFIF phase — Foundation needs tank/context + tank/snapshots | cross-ref M063 | F05760 | non-negotiable | false | 10 |
| R11475 | SFIF phase — Infrastructure begin needs tank/containers added | cross-ref M063 | F05761 | non-negotiable | false | 10 |
| R11476 | SFIF phase — Infrastructure continue needs tank/models added | cross-ref M063 | F05762 | non-negotiable | false | 10 |
| R11477 | SFIF phase — Features phase needs tank/logs + tank/vault added | cross-ref M063 | F05763 | non-negotiable | false | 10 |
| R11478 | SFIF phase — dataset additions signed via MS003 | cross-ref selfdef MS003 | F05759 | non-negotiable | false | 10 |
| R11479 | Typed mirror — sovereign-zfs-layout-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F05764 | non-negotiable | false | 10 |
| R11480 | Typed mirror — ZfsLayout struct fields | cross-ref selfdef MS007 | F05765 | non-negotiable | false | 10 |
| R11481 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F05766 | non-negotiable | false | 10 |
| R11482 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F05767 | non-negotiable | false | 10 |
| R11483 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F05764 | non-negotiable | false | 10 |
| R11484 | Typed mirror — no_std friendly | architecture | F05764 | non-negotiable | false | 10 |
| R11485 | Typed mirror — serde + bincode derives present | architecture | F05764 | non-negotiable | false | 10 |
| R11486 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F05766 | non-negotiable | false | 10 |
| R11487 | Event emitter — every dataset creation emits M049 + OCSF Configuration Change 5001 | cross-ref M049 + selfdef MS026 | F05768 | non-negotiable | false | 10 |
| R11488 | Event emitter — every snapshot emits M049 + OCSF File System Activity 1001 | cross-ref M049 + selfdef MS026 | F05769 | non-negotiable | false | 10 |
| R11489 | Event emitter — every rollback emits M049 + OCSF Audit Activity 1003 | cross-ref M049 + selfdef MS026 | F05770 | non-negotiable | false | 10 |
| R11490 | Event emitter — every IO error emits OCSF Detection Finding 2004 | cross-ref selfdef MS026 + M055 | F05744 | non-negotiable | false | 10 |
| R11491 | Dashboard — D-09 hardware pressure shows zpool IOPS | cross-ref M060 | F05771 | non-negotiable | false | 10 |
| R11492 | Dashboard — D-09 hardware pressure shows zpool latency | cross-ref M060 | F05771 | non-negotiable | false | 10 |
| R11493 | Dashboard — D-09 hardware pressure shows zpool fill | cross-ref M060 | F05771 | non-negotiable | false | 10 |
| R11494 | Dashboard — D-08 rollback points lists snapshots | cross-ref M060 | F05772 | non-negotiable | false | 10 |
| R11495 | Dashboard — D-08 rollback points shows retention info per snapshot | cross-ref M060 | F05772 | non-negotiable | false | 10 |
| R11496 | Dashboard — D-04 costs shows storage consumption per dataset | cross-ref M060 | F05773 | non-negotiable | false | 10 |
| R11497 | CLI — `sovereign zfs layout show` returns current layout | architecture | F05774 | non-negotiable | false | 10 |
| R11498 | CLI — `sovereign zfs snapshot <dataset> --name <name>` creates snapshot | cross-ref selfdef MS003 | F05775 | non-negotiable | false | 10 |
| R11499 | CLI — `sovereign zfs rollback <snapshot>` rolls back (operator-signed) | cross-ref selfdef MS003 + MS041 | F05776 | non-negotiable | false | 10 |
| R11500 | CLI — `sovereign zfs status` returns pool health | architecture | F05777 | non-negotiable | false | 10 |
| R11501 | CLI — all zfs subcommands emit M049 trace | cross-ref M049 | F05768 | non-negotiable | false | 10 |
| R11502 | CLI — `sovereign zfs scrub <pool>` runs zpool scrub | architecture | F05777 | non-negotiable | false | 10 |
| R11503 | CLI — `sovereign zfs send/receive` for backup operations | architecture | F05777 | non-negotiable | false | 10 |
| R11504 | Boundary — IPS selfdef MS037 enforces fanotify policy on ZFS-mounted paths | cross-ref selfdef MS037 | F05778 | non-negotiable | false | 10 |
| R11505 | Boundary — ZFS layout NEVER mutated from selfdef (sovereign-os runtime controls) | operator standing direction | F05779 | non-negotiable | false | 10 |
| R11506 | Boundary — selfdef MS037 publishes filesystem-grant mirror; sovereign-os runtime publishes zfs-layout mirror | cross-ref selfdef MS007 + MS037 | F05764 | non-negotiable | false | 10 |
| R11507 | Composition — ZFS storage composes with M058 hardware-aware scheduler (NVMe pressure feedback) | cross-ref M058 | F05771 | non-negotiable | false | 10 |
| R11508 | Composition — ZFS storage composes with M063 SFIF phases (datasets added per phase) | cross-ref M063 | F05759 | non-negotiable | false | 10 |
| R11509 | Composition — ZFS storage composes with M064 Debian-as-Ark customization | cross-ref M064 | F05702 | non-negotiable | false | 10 |
| R11510 | Composition — ZFS storage composes with M066 Trinity (Weaver storage manifestation) | cross-ref M066 | F05708 | non-negotiable | false | 10 |
| R11511 | Composition — ZFS storage composes with M067 kernel build (ZFS DKMS depends on kernel) | cross-ref M067 | F05699 | non-negotiable | false | 10 |
| R11512 | Composition — ZFS storage composes forward with M070 Dual-CCD topology (pending) | cross-ref M070 (pending) | F05755 | non-negotiable | false | 10 |
| R11513 | Composition — ZFS storage composes forward with M076 3 load-balancing profiles (pending) | cross-ref M076 (pending) | F05758 | non-negotiable | false | 10 |
| R11514 | Composition — ZFS storage composes forward with selfdef MS044 Guardian Daemon (audit log writes) | cross-ref selfdef MS044 (pending) | F05719 | non-negotiable | false | 10 |
| R11515 | Performance — zpool IOPS sustained `>=` 100K on dual NVMe PCIe 5 (target) | architecture | F05771 | non-negotiable | false | 10 |
| R11516 | Performance — zpool latency p95 `<` 1ms for tank/context sync writes | architecture | F05724 | non-negotiable | false | 10 |
| R11517 | Performance — zfs send/receive throughput `>=` 5GB/s for tank/models | architecture | F05503 | non-negotiable | false | 10 |
| R11518 | Performance — `sovereign zfs status` runtime `<` 100ms p95 | architecture | F05777 | non-negotiable | false | 10 |
| R11519 | Performance — `sovereign zfs layout show` runtime `<` 50ms p95 | architecture | F05774 | non-negotiable | false | 10 |
| R11520 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05764 | non-negotiable | false | 10 |
| R11521 | Telemetry — zpool IOPS / latency / fill emitted via M049 | cross-ref M049 | F05771 | non-negotiable | false | 10 |
| R11522 | Telemetry — snapshot count per dataset emitted via M049 | cross-ref M049 | F05769 | non-negotiable | false | 10 |
| R11523 | Telemetry — rollback count emitted via M049 (high-priority alert) | cross-ref M049 | F05770 | non-negotiable | false | 10 |
| R11524 | Telemetry — replay validator pass-rate emitted via M049 | cross-ref M049 | F05744 | non-negotiable | false | 10 |
| R11525 | Telemetry — IO error count emitted via M049 | cross-ref M049 + M055 | F05744 | non-negotiable | false | 10 |
| R11526 | Doctrinal preservation — `zpool create` command verbatim | dump 693 | F05702 | non-negotiable | false | 10 |
| R11527 | Doctrinal preservation — `zfs create tank/context` verbatim | dump 694 | F05708 | non-negotiable | false | 10 |
| R11528 | Doctrinal preservation — `zfs set sync=always tank/context` verbatim | dump 695 | F05709 | non-negotiable | false | 10 |
| R11529 | Doctrinal preservation — recordsize=16k for tank/containers verbatim | dump 706 | F05712 | non-negotiable | false | 10 |
| R11530 | Doctrinal preservation — `--kv-cache-dtype fp8` verbatim | dump 924 | F05751 | non-negotiable | false | 10 |
| R11531 | Doctrinal preservation — layer allocation 0-30 / 31-80 verbatim | dump 916-917 | F05748 | non-negotiable | false | 10 |
| R11532 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05780 | non-negotiable | false | 10 |
| R11533 | Doctrinal preservation — info-hub indexes ZFS architecture as second-brain entry | operator standing direction "second-brain" | F05780 | non-negotiable | false | 10 |
| R11534 | Operational — ZFS pool manager runs as systemd unit sovereign-zfs-layout.service | architecture | F05702 | non-negotiable | false | 10 |
| R11535 | Operational — ZFS pool manager honors SIGHUP for layout reload | architecture | F05702 | non-negotiable | false | 10 |
| R11536 | Operational — ZFS pool manager refuses to start with chain-break detected | cross-ref selfdef MS009 | F05744 | non-negotiable | false | 10 |
| R11537 | Operational — ZFS pool manager refuses to mutate without operator MS003 signature | cross-ref selfdef MS003 | F05779 | non-negotiable | false | 10 |
| R11538 | Operational — ZFS pool manager graceful drain on shutdown | architecture | F05702 | non-negotiable | false | 10 |
| R11539 | Operational — zfs-auto-snapshot installed + systemd timer enabled per policy | architecture | F05734 | non-negotiable | false | 10 |
| R11540 | Operational — zpool scrub scheduled monthly via systemd timer | architecture | F05777 | non-negotiable | false | 10 |
| R11541 | Operational — zpool scrub emits M049 trace + OCSF System Activity 1001 | cross-ref M049 + selfdef MS026 | F05768 | non-negotiable | false | 10 |
| R11542 | Operational — pool degradation emits OCSF Detection 2004 + halts new high-risk commits | cross-ref selfdef MS026 + M055 | F05744 | non-negotiable | false | 10 |
| R11543 | Operational — pool restore via `zpool import` emits operator-confirmation requirement | cross-ref selfdef MS003 + MS041 | F05776 | non-negotiable | false | 10 |
| R11544 | Operational — pool encryption optional (operator-toggled per dataset) | architecture + operator standing direction | F05722 | non-negotiable | false | 10 |
| R11545 | Operational — pool encryption uses native ZFS encryption with operator key | architecture + cross-ref selfdef MS003 | F05722 | non-negotiable | false | 10 |
| R11546 | Operational — pool integrates with LUKS at-rest encryption (cross-ref M059 substrate) | cross-ref M059 + M044 | F05707 | non-negotiable | false | 10 |
| R11547 | Operational — pool exposed via D-Bus property for runtime introspection | architecture + cross-ref selfdef MS007 | F05764 | non-negotiable | false | 10 |
| R11548 | Operational — pool name `tank` is operator-customizable (default `tank` per dump 693) | dump 693 | F05702 | non-negotiable | false | 10 |
| R11549 | Operational — pool customization signed via MS003 | cross-ref selfdef MS003 | F05721 | non-negotiable | false | 10 |
| R11550 | Operational — pool customization emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05768 | non-negotiable | false | 10 |
| R11551 | Closing — M068 covers dump 680-695 (Phase III ZFS) verbatim | dump 680-695 | F05780 | non-negotiable | false | 10 |
| R11552 | Closing — M068 covers dump 706 (Podman graph driver) verbatim | dump 706 | F05712 | non-negotiable | false | 10 |
| R11553 | Closing — M068 covers dump 913-925 (layer allocation + fp8 KV) verbatim | dump 913-925 | F05748 | non-negotiable | false | 10 |
| R11554 | Closing — sovereign-os catalog at 68/68 milestones | architecture | F05780 | non-negotiable | false | 10 |
| R11555 | Closing — combined ecosystem 111 milestones | architecture | F05780 | non-negotiable | false | 10 |
| R11556 | Closing — combined R-rows ~21880 | architecture | F05780 | non-negotiable | false | 10 |
| R11557 | Closing — combined enforced sub-reqs ~218800 | architecture | F05780 | non-negotiable | false | 10 |
| R11558 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05696 | non-negotiable | false | 10 |
| R11559 | Closing — sovereignty preserved (peace machine axiom across ZFS) | cross-ref M059 + operator standing direction | F05780 | non-negotiable | false | 10 |
| R11560 | Closing — M068 covers ZFS dump scope verbatim; selfdef MS044 Guardian Daemon next (cross-repo) | dump 680-925 + operator standing direction | F05780 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M068.

## Cross-references

- **M044** — sovereign-os substrate (PCIe 5 dual-NVMe)
- **M047** — continuity (CRIU + ZFS warm sandboxes)
- **M048** — modules map (Base OS + Memory OS depend on ZFS)
- **M049** — observability + trace pipeline
- **M055** — failure modes (IO errors / pool degradation taxonomy)
- **M058** — hardware-aware scheduler (NVMe pressure feedback)
- **M059** — peace machine close (LUKS at-rest encryption composes with ZFS)
- **M060** — cockpit + dashboards (D-04 / D-08 / D-09 surface ZFS state)
- **M063** — SFIF phases (dataset additions per phase)
- **M064** — Debian-as-Ark (ZFS DKMS is customization per working hypothesis)
- **M066** — Trinity Genesis (Weaver storage manifestation)
- **M067** — Custom Kernel Build (DKMS depends on kernel; rebuild per kernel update)
- **M070** — Dual-CCD topology (pending; CCD-aware IO routing)
- **M076** — 3 load-balancing profiles (pending; layer allocation per profile)
- **selfdef MS003** — selfdef-signing (signs every layout change + snapshot + rollback)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-zfs-layout-mirror)
- **selfdef MS009** — replay validator (verifies snapshot chain)
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS037** — filesystem boundary (IPS enforces fanotify on ZFS paths)
- **selfdef MS041** — commit authority (high-risk commits get pre-commit snapshot)
- **selfdef MS044** — Guardian Daemon (pending; writes audit logs to tank/vault)

## Schema

```
schema_version: "1.0.0"
milestone_id: M068
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines:
  - 680-695 (Phase III: Storage Layer + DKMS)
  - 706 (Phase IV: Podman graph driver mapping)
  - 913-925 (Layer allocation + KV cache fp8)
pool_creation: "zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank /dev/nvme0n1"
canonical_datasets:
  tank/context: { sync: always, optimized_for: matrix-weights }
  tank/containers: { recordsize: 16k, compression: off, podman_graph_driver: true }
  tank/models: { recordsize: 1M, compression: zstd-3 }
  tank/logs: { recordsize: 128k, compression: lz4 }
  tank/snapshots: { recordsize: 128k, retention: per-MS041 }
  tank/vault: { security_audit_logs: true, ref_dump_line: 981 }
typed_mirror_crate: sovereign-zfs-layout-mirror
catalog_status:
  sovereign_os: 68/68 milestones
  selfdef: 43/43 milestones
  combined: 111 milestones
```
