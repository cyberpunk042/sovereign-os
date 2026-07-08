# M012 — Storage and replay plane

> Parent: `backlog/milestones/INDEX.md` row M012 (dump 2729–3022).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 2729–3022.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0096–E0105)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0096 | Storage as memory substrate — not "where files live" | 2744–2746 |
| E0097 | OpenZFS as workstation storage substrate — ARC / L2ARC / special vdevs / snapshots / checksums / compression / datasets / replayable state | 2750 |
| E0098 | SPDK userspace NVMe — direct queue pairs + polled completions | 2751 |
| E0099 | Four-class storage model — Immutable Artifacts / Replay Logs / Hot Caches / Workspace State | 2756–2772 |
| E0100 | ZFS Layout Philosophy — correctness/replay/compression/snapshots; per-dataset behavior | 2775–2821 |
| E0101 | Sacred-vs-disposable distinction — replay-log sacred, KV-cache valuable-but-disposable, embeddings rebuildable, models redownloadable, source sacred-if-local | 2823–2835 |
| E0102 | Replay Log as AI Ledger — append-only auditability | 2837–2872 |
| E0103 | Bit-Level Storage Optimizations — binary + columnar internal state, JSON only at boundaries | 2873–2898 |
| E0104 | Memory Index Plane — content-hash + embedding + bitmap-metadata + replay-transition + tool/result + KV-block hash indexes | 2900–2935 |
| E0105 | Six-plane architecture — Inference / Control / Memory / Storage / Tool / Observability | 2980–3020 |

## Modules (M00181–M00197)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00181 | Storage-class 1 — Immutable Artifacts (model files / datasets / source docs / checkpoints) | 2760–2762 | E0099 |
| M00182 | Storage-class 2 — Replay Logs (branch transitions / model outputs / tool intents / accepted commits) | 2763–2765 | E0099 |
| M00183 | Storage-class 3 — Hot Caches (KV tiers / parsed schemas / token masks / embeddings / memory indexes) | 2766–2768 | E0099 |
| M00184 | Storage-class 4 — Workspace State (repos / generated code / documents / experiments) | 2769–2771 | E0099 |
| M00185 | ZFS dataset — `tank/models` (zstd/lz4, readonly-ish, large recordsize) | 2791, 2805 | E0100 |
| M00186 | ZFS dataset — `tank/datasets` (large recordsize, compression by data type) | 2792, 2819–2820 | E0100 |
| M00187 | ZFS dataset — `tank/runtime/replay` (append-heavy, snapshot often, checksum matters) | 2793, 2807–2808 | E0100 |
| M00188 | ZFS dataset — `tank/runtime/cache` (disposable, can be rebuilt, aggressive pruning) | 2794, 2810–2811 | E0100 |
| M00189 | ZFS dataset — `tank/runtime/kv` (large binary blocks, versioned by model/tokenizer hash) | 2795, 2813–2814 | E0100 |
| M00190 | ZFS dataset — `tank/workspaces` (snapshots before agent edits) | 2796, 2816–2817 | E0100 |
| M00191 | ZFS dataset — `tank/checkpoints` | 2797 | E0100 |
| M00192 | ZFS dataset — `tank/snapshots` | 2798 | E0100 |
| M00193 | Replay-log record — branch_id / parent_id / state_before / candidate_ref / policy_mask / grammar_state / model / accepted / tool_intent / timestamp | 2843–2856 | E0102 |
| M00194 | Bit-level columnar runtime state — branch_id[] / score_q16[] / risk_u8[] / control_u64[] / memory_ref_u64[] | 2889–2894 | E0103 |
| M00195 | Memory-index plane — 6 named indexes (content-hash / embedding / bitmap-metadata / replay-transition / tool-result / KV-block-hash) | 2904–2911 | E0104 |
| M00196 | Bitmap-metadata sub-indexes — project_id / file_type / trust_level / freshness_bucket / tool_generated / user_verified | 2916–2922 | E0104 |
| M00197 | Six-plane architecture rollup — Inference / Control / Memory / Storage / Tool / Observability | 2984–3003 | E0105 |

## Features (F00936–F01020)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00936 | Toggle storage backend (ZFS native / ext4 fallback / btrfs alt) | 2750, 2753 | E0097 | mode | true |
| F00937 | Profile knob — `storage_backend = zfs \| ext4 \| btrfs` | 2750, 2753 | E0097 | profile | true |
| F00938 | Env var `SOVEREIGN_STORAGE_BACKEND` | 2750 | E0097 | env_var | true |
| F00939 | CLI `--storage-backend <name>` | 2750 | E0097 | cli_verb | true |
| F00940 | Toggle storage-class-1 immutable-artifact mount — `tank/models` | 2791 | M00185 | mode | true |
| F00941 | Toggle storage-class-1 immutable-artifact mount — `tank/datasets` | 2792 | M00186 | mode | true |
| F00942 | Toggle storage-class-2 replay-log mount — `tank/runtime/replay` | 2793 | M00187 | mode | true |
| F00943 | Toggle storage-class-3 hot-cache mount — `tank/runtime/cache` | 2794 | M00188 | mode | true |
| F00944 | Toggle storage-class-3 hot-cache mount — `tank/runtime/kv` | 2795 | M00189 | mode | true |
| F00945 | Toggle storage-class-4 workspace mount — `tank/workspaces` | 2796 | M00190 | mode | true |
| F00946 | Toggle storage-class-4 workspace mount — `tank/checkpoints` | 2797 | M00191 | mode | true |
| F00947 | Toggle storage-class-4 workspace mount — `tank/snapshots` | 2798 | M00192 | mode | true |
| F00948 | Profile knob — per-dataset compression (zstd / lz4 / off) | 2805 | M00185 | profile | true |
| F00949 | Profile knob — per-dataset recordsize | 2805, 2819 | M00185 | profile | true |
| F00950 | Profile knob — per-dataset readonly toggle | 2805 | M00185 | profile | true |
| F00951 | Profile knob — replay snapshot cadence | 2807 | M00187 | profile | true |
| F00952 | Profile knob — checksum algorithm (fletcher4 / sha256 / blake3) | 2808 | M00187 | profile | true |
| F00953 | Profile knob — cache aggressive-pruning policy | 2811 | M00188 | profile | true |
| F00954 | Profile knob — kv-version-by `{model_id, tokenizer_id}` hash | 2814 | M00189 | profile | true |
| F00955 | Profile knob — workspace snapshot-before-agent-edit policy | 2817 | M00190 | profile | true |
| F00956 | Env var `SOVEREIGN_ZFS_POOL` (override default `tank`) | 2791–2798 | E0100 | env_var | true |
| F00957 | Env var `SOVEREIGN_REPLAY_SNAPSHOT_CADENCE` | 2807 | M00187 | env_var | true |
| F00958 | Env var `SOVEREIGN_KV_VERSION_HASH_SCOPE` | 2814 | M00189 | env_var | true |
| F00959 | CLI `--zfs-pool <name>` | 2791 | E0100 | cli_verb | true |
| F00960 | CLI `sovereign-osctl storage dataset list` | 2791–2798 | E0100 | cli_verb | true |
| F00961 | CLI `sovereign-osctl storage dataset show <name>` | 2791–2798 | E0100 | cli_verb | true |
| F00962 | CLI `sovereign-osctl storage snapshot create --dataset <name>` | 2798 | M00192 | cli_verb | true |
| F00963 | CLI `sovereign-osctl storage snapshot list` | 2798 | M00192 | cli_verb | true |
| F00964 | CLI `sovereign-osctl storage snapshot rollback <name>@<snap>` (triple-gated) | 2798 | M00192 | cli_verb | true |
| F00965 | Dashboard surface — ZFS pool health (ONLINE/DEGRADED/FAULTED) | 2750 | E0097 | dashboard | true |
| F00966 | Dashboard surface — per-dataset usage + compression-ratio + dedup-ratio | 2780–2821 | E0100 | dashboard | true |
| F00967 | Dashboard surface — replay-log ingest rate + size growth | 2837 | M00193 | dashboard | true |
| F00968 | Dashboard surface — sacred-vs-disposable category map | 2823–2835 | E0101 | dashboard | true |
| F00969 | API `GET /v1/storage/datasets` | 2791–2798 | E0100 | api_endpoint | true |
| F00970 | API `GET /v1/storage/dataset/{name}` | 2791–2798 | E0100 | api_endpoint | true |
| F00971 | API `POST /v1/storage/snapshot` | 2798 | M00192 | api_endpoint | true |
| F00972 | API `POST /v1/storage/rollback` (triple-gated) | 2798 | M00192 | api_endpoint | true |
| F00973 | API `GET /v1/replay/transition?branch_id=<n>` | 2843–2856 | M00193 | api_endpoint | true |
| F00974 | API `GET /v1/replay/search?q=<query>` | 2862–2868 | M00193 | api_endpoint | true |
| F00975 | Metric `sovereign_storage_dataset_bytes{dataset}` | 2791–2798 | E0100 | observability_metric | true |
| F00976 | Metric `sovereign_storage_compress_ratio{dataset}` | 2805 | M00185 | observability_metric | true |
| F00977 | Metric `sovereign_replay_log_records_total` | 2841 | M00193 | observability_metric | true |
| F00978 | Metric `sovereign_replay_log_bytes_total` | 2841 | M00193 | observability_metric | true |
| F00979 | Metric `sovereign_zfs_arc_hit_ratio` | 2782 | E0097 | observability_metric | true |
| F00980 | Metric `sovereign_zfs_arc_size_bytes` | 2782 | E0097 | observability_metric | true |
| F00981 | Replay-log record field — `branch_id` | 2845 | M00193 | data_model | false |
| F00982 | Replay-log record field — `parent_id` | 2846 | M00193 | data_model | false |
| F00983 | Replay-log record field — `state_before` | 2847 | M00193 | data_model | false |
| F00984 | Replay-log record field — `candidate_ref` | 2848 | M00193 | data_model | false |
| F00985 | Replay-log record field — `policy_mask` | 2849 | M00193 | data_model | false |
| F00986 | Replay-log record field — `grammar_state` | 2850 | M00193 | data_model | false |
| F00987 | Replay-log record field — `model` | 2851 | M00193 | data_model | false |
| F00988 | Replay-log record field — `accepted` | 2852 | M00193 | data_model | false |
| F00989 | Replay-log record field — `tool_intent` | 2853 | M00193 | data_model | false |
| F00990 | Replay-log record field — `timestamp` | 2854 | M00193 | data_model | false |
| F00991 | Forensic query — "Why did it call that tool?" | 2863 | M00193 | composite | true |
| F00992 | Forensic query — "Which branch produced this file edit?" | 2864 | M00193 | composite | true |
| F00993 | Forensic query — "Which memory was admitted?" | 2865 | M00193 | composite | true |
| F00994 | Forensic query — "Which model output was rejected?" | 2866 | M00193 | composite | true |
| F00995 | Forensic query — "Which policy bit stopped a dangerous action?" | 2867 | M00193 | composite | true |
| F00996 | Forensic query — "Where did latency go?" | 2868 | M00193 | composite | true |
| F00997 | Columnar runtime row — `branch_id[]` | 2889 | M00194 | data_model | false |
| F00998 | Columnar runtime row — `score_q16[]` | 2890 | M00194 | data_model | false |
| F00999 | Columnar runtime row — `risk_u8[]` | 2891 | M00194 | data_model | false |
| F01000 | Columnar runtime row — `control_u64[]` | 2892 | M00194 | data_model | false |
| F01001 | Columnar runtime row — `memory_ref_u64[]` | 2893 | M00194 | data_model | false |
| F01002 | Internal-binary / boundary-JSON serialization rule | 2898 | M00194 | mode | false |
| F01003 | Memory-index — content-hash index | 2905 | M00195 | composite | false |
| F01004 | Memory-index — embedding index | 2906 | M00195 | composite | false |
| F01005 | Memory-index — bitmap metadata index | 2907 | M00195 | composite | false |
| F01006 | Memory-index — replay transition index | 2908 | M00195 | composite | false |
| F01007 | Memory-index — tool/result index | 2909 | M00195 | composite | false |
| F01008 | Memory-index — KV-block hash index | 2910 | M00195 | composite | false |
| F01009 | Bitmap-metadata sub-index — `project_id` bitmap | 2916 | M00196 | composite | false |
| F01010 | Bitmap-metadata sub-index — `file_type` bitmap | 2917 | M00196 | composite | false |
| F01011 | Bitmap-metadata sub-index — `trust_level` bitmap | 2918 | M00196 | composite | false |
| F01012 | Bitmap-metadata sub-index — `freshness_bucket` bitmap | 2919 | M00196 | composite | false |
| F01013 | Bitmap-metadata sub-index — `tool_generated` bitmap | 2920 | M00196 | composite | false |
| F01014 | Bitmap-metadata sub-index — `user_verified` bitmap | 2921 | M00196 | composite | false |
| F01015 | Bitmap query composer — `project_python & recent & trusted & not_obsolete & relevant_topic` | 2927–2933 | M00196 | composite | true |
| F01016 | Special-vdev mirror-required guard (refuse to add unmirrored special vdev) | 2944 | E0097 | composite | false |
| F01017 | L2ARC opt-in toggle | 2946 | E0097 | mode | true |
| F01018 | SLOG opt-in toggle for sync-write-latency-critical datasets | 2947 | E0097 | mode | true |
| F01019 | SPDK opt-in toggle (Phase 4 — profile-gated) | 2965–2975 | E0098 | mode | true |
| F01020 | Composite — Storage Plane completes the six-plane architecture | 2984–3003 | E0105 | composite | false |

## Requirements (R01871–R02040)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R01871 | Storage is the system's memory substrate, not "where files live" | 2744–2746 | E0096 | non-negotiable | false | 10 |
| R01872 | OpenZFS provides ARC | 2750 | E0097 | non-negotiable | false | 10 |
| R01873 | OpenZFS provides L2ARC | 2750 | E0097 | non-negotiable | false | 10 |
| R01874 | OpenZFS provides special allocation classes | 2750 | E0097 | non-negotiable | false | 10 |
| R01875 | OpenZFS provides snapshots | 2750 | E0097 | non-negotiable | false | 10 |
| R01876 | OpenZFS provides checksums | 2750 | E0097 | non-negotiable | false | 10 |
| R01877 | OpenZFS provides compression | 2750 | E0097 | non-negotiable | false | 10 |
| R01878 | OpenZFS provides datasets | 2750 | E0097 | non-negotiable | false | 10 |
| R01879 | OpenZFS provides replayable state | 2750 | E0097 | non-negotiable | false | 10 |
| R01880 | OpenZFS special vdevs can store metadata, indirect blocks, dedup tables, optionally small blocks via `special_small_blocks` | 2750 | E0097 | non-negotiable | true | 10 |
| R01881 | SPDK maps NVMe control into userspace and submits async I/O through queue pairs | 2751 | E0098 | non-negotiable | true | 10 |
| R01882 | SPDK polls completions directly instead of kernel path | 2751 | E0098 | non-negotiable | true | 10 |
| R01883 | Default — start with ZFS, not SPDK | 2753 | E0097 | non-negotiable | true | 10 |
| R01884 | Storage class 1 — Immutable Artifacts (model files / datasets / source docs / checkpoints) | 2760–2762 | M00181 | non-negotiable | false | 10 |
| R01885 | Storage class 2 — Replay Logs (branch transitions / model outputs / tool intents / accepted commits) | 2763–2765 | M00182 | non-negotiable | false | 10 |
| R01886 | Storage class 3 — Hot Caches (KV tiers / parsed schemas / token masks / embeddings / memory indexes) | 2766–2768 | M00183 | non-negotiable | false | 10 |
| R01887 | Storage class 4 — Workspace State (repos / generated code / documents / experiments) | 2769–2771 | M00184 | non-negotiable | false | 10 |
| R01888 | Four storage classes are not treated the same | 2773 | E0099 | non-negotiable | false | 10 |
| R01889 | ZFS is for correctness, replay, compression, snapshots | 2780 | E0100 | non-negotiable | false | 10 |
| R01890 | RAM ARC is for hot metadata and files | 2781 | E0100 | non-negotiable | false | 10 |
| R01891 | NVMe bandwidth is for cold-to-warm promotion | 2782 | E0100 | non-negotiable | false | 10 |
| R01892 | GPU VRAM is not storage; it is active compute memory | 2783 | E0100 | non-negotiable | false | 10 |
| R01893 | Use datasets, not one giant undifferentiated pool | 2786 | E0100 | non-negotiable | false | 10 |
| R01894 | ZFS dataset `tank/models` exists | 2791 | M00185 | non-negotiable | false | 10 |
| R01895 | ZFS dataset `tank/datasets` exists | 2792 | M00186 | non-negotiable | false | 10 |
| R01896 | ZFS dataset `tank/runtime/replay` exists | 2793 | M00187 | non-negotiable | false | 10 |
| R01897 | ZFS dataset `tank/runtime/cache` exists | 2794 | M00188 | non-negotiable | false | 10 |
| R01898 | ZFS dataset `tank/runtime/kv` exists | 2795 | M00189 | non-negotiable | false | 10 |
| R01899 | ZFS dataset `tank/workspaces` exists | 2796 | M00190 | non-negotiable | false | 10 |
| R01900 | ZFS dataset `tank/checkpoints` exists | 2797 | M00191 | non-negotiable | false | 10 |
| R01901 | ZFS dataset `tank/snapshots` exists | 2798 | M00192 | non-negotiable | false | 10 |
| R01902 | `tank/models` — compression maybe zstd/lz4, readonly-ish, large recordsize | 2805 | M00185 | non-negotiable | true | 10 |
| R01903 | `tank/runtime/replay` — append-heavy, snapshot often, checksum matters | 2807–2808 | M00187 | non-negotiable | false | 10 |
| R01904 | `tank/runtime/cache` — disposable, can be rebuilt, aggressive pruning | 2810–2811 | M00188 | non-negotiable | true | 10 |
| R01905 | `tank/runtime/kv` — large binary blocks, versioned by model/tokenizer hash | 2813–2814 | M00189 | non-negotiable | false | 10 |
| R01906 | `tank/workspaces` — snapshots before agent edits | 2816–2817 | M00190 | non-negotiable | false | 10 |
| R01907 | `tank/datasets` — large recordsize, compression based on data type | 2819–2820 | M00186 | non-negotiable | true | 10 |
| R01908 | Do not put irreplaceable truth and disposable cache in the same operational category | 2825 | E0101 | non-negotiable | false | 10 |
| R01909 | Replay log is sacred | 2828 | E0101 | non-negotiable | false | 10 |
| R01910 | KV cache is valuable but disposable | 2829 | E0101 | non-negotiable | false | 10 |
| R01911 | Embeddings are rebuildable | 2830 | E0101 | non-negotiable | false | 10 |
| R01912 | Models are redownloadable but expensive | 2831 | E0101 | non-negotiable | false | 10 |
| R01913 | Source is sacred if local-only | 2832 | E0101 | non-negotiable | false | 10 |
| R01914 | Sacred-vs-disposable distinction affects snapshots | 2835 | E0101 | non-negotiable | false | 10 |
| R01915 | Sacred-vs-disposable distinction affects replication | 2835 | E0101 | non-negotiable | false | 10 |
| R01916 | Sacred-vs-disposable distinction affects backup | 2835 | E0101 | non-negotiable | false | 10 |
| R01917 | Sacred-vs-disposable distinction affects eviction | 2835 | E0101 | non-negotiable | false | 10 |
| R01918 | Replay log is one of the most important pieces | 2839 | E0102 | non-negotiable | false | 10 |
| R01919 | Every committed transition is append-only | 2841 | E0102 | non-negotiable | false | 10 |
| R01920 | Replay record carries `branch_id` | 2845 | M00193 | non-negotiable | false | 10 |
| R01921 | Replay record carries `parent_id` | 2846 | M00193 | non-negotiable | false | 10 |
| R01922 | Replay record carries `state_before` | 2847 | M00193 | non-negotiable | false | 10 |
| R01923 | Replay record carries `candidate_ref` | 2848 | M00193 | non-negotiable | false | 10 |
| R01924 | Replay record carries `policy_mask` | 2849 | M00193 | non-negotiable | false | 10 |
| R01925 | Replay record carries `grammar_state` | 2850 | M00193 | non-negotiable | false | 10 |
| R01926 | Replay record carries `model` identifier | 2851 | M00193 | non-negotiable | false | 10 |
| R01927 | Replay record carries `accepted` bool | 2852 | M00193 | non-negotiable | false | 10 |
| R01928 | Replay record carries `tool_intent` | 2853 | M00193 | non-negotiable | false | 10 |
| R01929 | Replay record carries `timestamp` | 2854 | M00193 | non-negotiable | false | 10 |
| R01930 | Deterministic AI infrastructure needs auditability | 2858 | E0102 | non-negotiable | false | 10 |
| R01931 | Forensic query — "Why did it call that tool?" answerable from replay log | 2863 | M00193 | non-negotiable | false | 10 |
| R01932 | Forensic query — "Which branch produced this file edit?" answerable | 2864 | M00193 | non-negotiable | false | 10 |
| R01933 | Forensic query — "Which memory was admitted?" answerable | 2865 | M00193 | non-negotiable | false | 10 |
| R01934 | Forensic query — "Which model output was rejected?" answerable | 2866 | M00193 | non-negotiable | false | 10 |
| R01935 | Forensic query — "Which policy bit stopped a dangerous action?" answerable | 2867 | M00193 | non-negotiable | false | 10 |
| R01936 | Forensic query — "Where did latency go?" answerable | 2868 | M00193 | non-negotiable | false | 10 |
| R01937 | Replay log enables the workstation to be better than a cloud black box | 2871 | E0102 | non-negotiable | false | 10 |
| R01938 | Runtime state is binary and columnar on the hot path | 2875 | E0103 | non-negotiable | false | 10 |
| R01939 | Columnar runtime row — `branch_id[]` | 2889 | M00194 | non-negotiable | false | 10 |
| R01940 | Columnar runtime row — `score_q16[]` | 2890 | M00194 | non-negotiable | false | 10 |
| R01941 | Columnar runtime row — `risk_u8[]` | 2891 | M00194 | non-negotiable | false | 10 |
| R01942 | Columnar runtime row — `control_u64[]` | 2892 | M00194 | non-negotiable | false | 10 |
| R01943 | Columnar runtime row — `memory_ref_u64[]` | 2893 | M00194 | non-negotiable | false | 10 |
| R01944 | Hot-path serializes chunks to replay/ZFS in batches | 2896 | M00194 | non-negotiable | false | 10 |
| R01945 | Text JSON only at boundaries and inspection layers | 2898 | M00194 | non-negotiable | false | 10 |
| R01946 | Internally — compact binary records plus a manifest | 2898 | M00194 | non-negotiable | false | 10 |
| R01947 | Memory index — content-hash index | 2905 | M00195 | non-negotiable | false | 10 |
| R01948 | Memory index — embedding index | 2906 | M00195 | non-negotiable | false | 10 |
| R01949 | Memory index — bitmap metadata index | 2907 | M00195 | non-negotiable | false | 10 |
| R01950 | Memory index — replay transition index | 2908 | M00195 | non-negotiable | false | 10 |
| R01951 | Memory index — tool/result index | 2909 | M00195 | non-negotiable | false | 10 |
| R01952 | Memory index — KV-block hash index | 2910 | M00195 | non-negotiable | false | 10 |
| R01953 | Bitmap-metadata index is where AVX-512 shines | 2913 | M00196 | non-negotiable | false | 10 |
| R01954 | Bitmap sub-index — `project_id` bitmap | 2916 | M00196 | non-negotiable | false | 10 |
| R01955 | Bitmap sub-index — `file_type` bitmap | 2917 | M00196 | non-negotiable | false | 10 |
| R01956 | Bitmap sub-index — `trust_level` bitmap | 2918 | M00196 | non-negotiable | false | 10 |
| R01957 | Bitmap sub-index — `freshness_bucket` bitmap | 2919 | M00196 | non-negotiable | false | 10 |
| R01958 | Bitmap sub-index — `tool_generated` bitmap | 2920 | M00196 | non-negotiable | false | 10 |
| R01959 | Bitmap sub-index — `user_verified` bitmap | 2921 | M00196 | non-negotiable | false | 10 |
| R01960 | Bitmap query composer composes `project_python & recent & trusted & not_obsolete & relevant_topic` | 2927–2933 | M00196 | non-negotiable | false | 10 |
| R01961 | Embeddings/rerank only see the bitmap-query survivors | 2935 | M00196 | non-negotiable | false | 10 |
| R01962 | OpenZFS special class holds metadata by default | 2939 | E0097 | non-negotiable | true | 10 |
| R01963 | OpenZFS special class can opt into small file blocks with `special_small_blocks` | 2939 | E0097 | non-negotiable | true | 10 |
| R01964 | Special vdevs are not "cache" — they are allocation destinations | 2941 | E0097 | non-negotiable | false | 10 |
| R01965 | Special vdev without redundancy puts the pool in danger | 2941 | E0097 | non-negotiable | false | 10 |
| R01966 | Special vdev only if mirrored | 2944 | E0097 | non-negotiable | false | 10 |
| R01967 | L2ARC is cache | 2946 | E0097 | non-negotiable | false | 10 |
| R01968 | SLOG is for sync-write latency, not general speed | 2947 | E0097 | non-negotiable | false | 10 |
| R01969 | ARC/RAM first | 2948 | E0097 | non-negotiable | false | 10 |
| R01970 | Initial two-NVMe RAID-0 — ZFS stripe for scratch/performance | 2953 | E0097 | non-negotiable | true | 10 |
| R01971 | Initial two-NVMe RAID-0 — fast but not trusted alone | 2954 | E0097 | non-negotiable | true | 10 |
| R01972 | External replication / backup for anything sacred | 2956 | E0101 | non-negotiable | true | 10 |
| R01973 | Snapshots before agent edits and experiments | 2959 | M00190 | non-negotiable | false | 10 |
| R01974 | SPDK only if you build a custom cache engine bypassing filesystem semantics | 2965 | E0098 | non-negotiable | true | 10 |
| R01975 | SPDK gives direct userspace NVMe queues and polling | 2965 | E0098 | non-negotiable | true | 10 |
| R01976 | SPDK costs complexity | 2967 | E0098 | non-negotiable | true | 10 |
| R01977 | Storage roadmap Phase 1 — ZFS datasets + mmap/io_uring where useful | 2972 | E0097 | non-negotiable | true | 10 |
| R01978 | Storage roadmap Phase 2 — binary columnar cache files | 2973 | M00194 | non-negotiable | true | 10 |
| R01979 | Storage roadmap Phase 3 — custom KV block store | 2974 | E0098 | preferable | true | 10 |
| R01980 | Storage roadmap Phase 4 — SPDK only if profiling proves kernel/filesystem overhead dominates | 2975 | E0098 | preferable | true | 10 |
| R01981 | Do not start with the dragon — earn it | 2978 | E0098 | non-negotiable | false | 10 |
| R01982 | Full machine has Inference Plane (Blackwell oracle + 4090 scout/specialists) | 2985–2987 | E0105 | non-negotiable | false | 10 |
| R01983 | Full machine has Control Plane (AVX-512 branch/policy/grammar engine) | 2989–2990 | E0105 | non-negotiable | false | 10 |
| R01984 | Full machine has Memory Plane (semantic memory, embeddings, bitmaps, KV refs) | 2992–2993 | E0105 | non-negotiable | false | 10 |
| R01985 | Full machine has Storage Plane (ZFS datasets, replay ledger, snapshots, cache tiers) | 2995–2996 | E0105 | non-negotiable | false | 10 |
| R01986 | Full machine has Tool Plane (shell/browser/code/doc sandboxes) | 2998–2999 | E0105 | non-negotiable | false | 10 |
| R01987 | Full machine has Observability Plane (latency, branch death reasons, cache hit rates, oracle utilization) | 3001–3002 | E0105 | non-negotiable | false | 10 |
| R01988 | Storage plane makes the whole thing persistent and evolutionary | 3005 | E0105 | non-negotiable | false | 10 |
| R01989 | Without storage plane, the system is smart but forgetful | 3007 | E0105 | non-negotiable | false | 10 |
| R01990 | With storage plane, the system is replayable | 3012 | E0105 | non-negotiable | false | 10 |
| R01991 | With storage plane, the system is auditable | 3013 | E0105 | non-negotiable | false | 10 |
| R01992 | With storage plane, the system is self-measuring | 3014 | E0105 | non-negotiable | false | 10 |
| R01993 | With storage plane, the system is cache-aware | 3015 | E0105 | non-negotiable | false | 10 |
| R01994 | With storage plane, the system is rollback-safe | 3016 | E0105 | non-negotiable | false | 10 |
| R01995 | With storage plane, the system is capable of learning from its own failures | 3017 | E0105 | non-negotiable | false | 10 |
| R01996 | High-standard version is "a deterministic local AI operating environment with memory, law, replay, and compute hierarchy" | 3020 | E0105 | non-negotiable | false | 10 |
| R01997 | Storage backend operator-overrideable (zfs / ext4 / btrfs) | 2750 | F00936 | non-negotiable | true | 10 |
| R01998 | Per-dataset compression operator-tunable (zstd / lz4 / off) | 2805 | F00948 | non-negotiable | true | 10 |
| R01999 | Per-dataset recordsize operator-tunable | 2805, 2819 | F00949 | non-negotiable | true | 10 |
| R02000 | Per-dataset readonly-toggle operator-tunable | 2805 | F00950 | non-negotiable | true | 10 |
| R02001 | Replay snapshot cadence operator-tunable | 2807 | F00951 | non-negotiable | true | 10 |
| R02002 | Checksum algorithm operator-overrideable (fletcher4 / sha256 / blake3) | 2808 | F00952 | non-negotiable | true | 10 |
| R02003 | Cache aggressive-pruning policy operator-tunable | 2811 | F00953 | non-negotiable | true | 10 |
| R02004 | KV-version-hash scope operator-tunable | 2814 | F00954 | non-negotiable | true | 10 |
| R02005 | Workspace snapshot-before-agent-edit policy operator-tunable | 2817 | F00955 | non-negotiable | true | 10 |
| R02006 | Env var `SOVEREIGN_STORAGE_BACKEND` | 2750 | F00938 | non-negotiable | true | 10 |
| R02007 | Env var `SOVEREIGN_ZFS_POOL` | 2791–2798 | F00956 | non-negotiable | true | 10 |
| R02008 | Env var `SOVEREIGN_REPLAY_SNAPSHOT_CADENCE` | 2807 | F00957 | non-negotiable | true | 10 |
| R02009 | Env var `SOVEREIGN_KV_VERSION_HASH_SCOPE` | 2814 | F00958 | non-negotiable | true | 10 |
| R02010 | CLI `sovereign-osctl storage dataset list` | 2791–2798 | F00960 | non-negotiable | true | 10 |
| R02011 | CLI `sovereign-osctl storage dataset show <name>` | 2791–2798 | F00961 | non-negotiable | true | 10 |
| R02012 | CLI `sovereign-osctl storage snapshot create --dataset <name>` | 2798 | F00962 | non-negotiable | true | 10 |
| R02013 | CLI `sovereign-osctl storage snapshot list` | 2798 | F00963 | non-negotiable | true | 10 |
| R02014 | CLI `sovereign-osctl storage snapshot rollback <name>@<snap>` triple-gated | 2798 | F00964 | non-negotiable | true | 10 |
| R02015 | Dashboard — ZFS pool health (ONLINE/DEGRADED/FAULTED) | 2750 | F00965 | non-negotiable | true | 10 |
| R02016 | Dashboard — per-dataset usage + compression-ratio + dedup-ratio | 2780–2821 | F00966 | non-negotiable | true | 10 |
| R02017 | Dashboard — replay-log ingest rate + size growth | 2837 | F00967 | non-negotiable | true | 10 |
| R02018 | Dashboard — sacred-vs-disposable category map | 2823–2835 | F00968 | non-negotiable | true | 10 |
| R02019 | API `GET /v1/storage/datasets` | 2791–2798 | F00969 | non-negotiable | true | 10 |
| R02020 | API `GET /v1/storage/dataset/{name}` | 2791–2798 | F00970 | non-negotiable | true | 10 |
| R02021 | API `POST /v1/storage/snapshot` | 2798 | F00971 | non-negotiable | true | 10 |
| R02022 | API `POST /v1/storage/rollback` triple-gated | 2798 | F00972 | non-negotiable | true | 10 |
| R02023 | API `GET /v1/replay/transition?branch_id=<n>` | 2843–2856 | F00973 | non-negotiable | true | 10 |
| R02024 | API `GET /v1/replay/search?q=<query>` | 2862–2868 | F00974 | non-negotiable | true | 10 |
| R02025 | Metric `sovereign_storage_dataset_bytes{dataset}` | 2791–2798 | F00975 | non-negotiable | true | 10 |
| R02026 | Metric `sovereign_storage_compress_ratio{dataset}` | 2805 | F00976 | non-negotiable | true | 10 |
| R02027 | Metric `sovereign_replay_log_records_total` | 2841 | F00977 | non-negotiable | true | 10 |
| R02028 | Metric `sovereign_replay_log_bytes_total` | 2841 | F00978 | non-negotiable | true | 10 |
| R02029 | Metric `sovereign_zfs_arc_hit_ratio` | 2782 | F00979 | non-negotiable | true | 10 |
| R02030 | Metric `sovereign_zfs_arc_size_bytes` | 2782 | F00980 | non-negotiable | true | 10 |
| R02031 | Test — replay-log record round-trip preserves all 10 fields | 2843–2856 | M00193 | non-negotiable | false | 10 |
| R02032 | Test — replay-log append-only invariant (no in-place mutation) | 2841 | M00193 | non-negotiable | false | 10 |
| R02033 | Test — each forensic query returns expected answer on a recorded session | 2862–2868 | M00193 | non-negotiable | false | 10 |
| R02034 | Test — columnar runtime SoA layout matches expected struct of arrays | 2889–2894 | M00194 | non-negotiable | false | 10 |
| R02035 | Test — bitmap query composer composes 5-axis intersection correctly | 2927–2933 | M00196 | non-negotiable | false | 10 |
| R02036 | Test — ZFS pool refuses unmirrored special vdev addition | 2944 | F01016 | non-negotiable | false | 10 |
| R02037 | Test — snapshot rollback triple-gate enforced | 2798 | F00964 | non-negotiable | false | 10 |
| R02038 | Test — six-plane architecture rollup enumerates all six planes | 2984–3003 | M00197 | non-negotiable | false | 10 |
| R02039 | Composite F01020 — Storage Plane completes the six-plane architecture | 2984–3003 | F01020 | non-negotiable | false | 10 |
| R02040 | Composite — High-standard version of the workstation is "a deterministic local AI operating environment with memory, law, replay, and compute hierarchy" | 3020 | E0105 | non-negotiable | false | 10 |

— End of M012 milestone file.
