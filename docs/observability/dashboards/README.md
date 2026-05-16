# sovereign-os Grafana dashboards (templates)

Per SDD-016 Layer C: operator-imported JSON dashboard templates. NOT
auto-installed — operator imports them if they run Grafana.

Sovereignty: sovereign-os ships **dashboard templates**, not a Grafana
deployment. Operator picks their scraper + their viz layer; the metrics
contract (Prometheus textfile collector at
`/var/lib/node_exporter/textfile_collector/sovereign-os-*.prom`) is
the load-bearing piece — dashboards are convenience.

## Dashboards in this directory

| File | Title | Coverage |
|---|---|---|
| `sovereign-os-overview.json` | sovereign-os overview | Pipeline last-run · per-tier inference counters · ZFS health · perimeter status · build step duration · log rotation · snapshots · pending security updates — at-a-glance health |
| `sovereign-os-inference.json` | sovereign-os inference | Per-tier route rate + cumulative · last decision age · backend start success/fail/skip counts |
| `sovereign-os-install.json` | sovereign-os install lifecycle | during-install + post-install audit: rootfs-format · pool-create · datasets-create · MOK enroll · friction-audit failures/warnings · VFIO bind · NVIDIA bind · ARC max bytes · Tetragon policy · network VLAN · shell setup · image-sign per posture · friction-audit last-run age |

## Import (one-time, per dashboard)

1. In Grafana: Dashboards → New → Import → Upload JSON file →
   select `sovereign-os-overview.json` (or the other).
2. Pick the Prometheus datasource that scrapes
   `/var/lib/node_exporter/textfile_collector/`.
3. Save.

Operators who want the dashboards auto-provisioned can drop the JSONs
under `/etc/grafana/provisioning/dashboards/` and add a
`dashboards.yaml` provider config. Out of scope for sovereign-os —
the JSON templates work either path.

## Metric inventory consumed by these dashboards

All emitted from `scripts/build/lib/observability.sh` via
`emit_metric` / `emit_metric_set` helpers. Names are stable contracts —
panel queries lock to them.

### Build pipeline (scripts/build/01..09)

- `sovereign_os_build_step_duration_seconds{step,profile,result}`
- `sovereign_os_build_pipeline_duration_seconds{profile,result}`
- `sovereign_os_build_pipeline_steps_total{profile,result}`
- `sovereign_os_build_pipeline_last_run_timestamp{profile}`
- `sovereign_os_build_step_bootstrap_forge_total{profile,result}`
- `sovereign_os_build_step_kernel_fetch_total{profile,result}`
- `sovereign_os_build_step_kernel_config_total{profile,result}`
- `sovereign_os_build_step_kernel_compile_total{profile,result}`
- `sovereign_os_build_step_substrate_total{profile,substrate,result}`
- `sovereign_os_build_step_render_total{profile,result}`
- `sovereign_os_build_step_image_build_total{profile,substrate,result}`
- `sovereign_os_build_step_sign_total{profile,posture,result}`
- `sovereign_os_build_step_image_verify_total{profile,result}`

### Pre-install lifecycle hooks (scripts/hooks/pre-install)

- `sovereign_os_pre_install_preflight_total{hook,result}` — pass/fail counters for preflight-network / preflight-storage / preflight-tpm
- `sovereign_os_pre_install_friction_audit_spec_total{profile,result}`
- `sovereign_os_pre_install_friction_audit_spec_failures{profile}` — count of structural issues found in the profile YAML

### During-install lifecycle hooks (scripts/hooks/during-install)

- `sovereign_os_during_install_rootfs_format_total{profile,fs,result}`
- `sovereign_os_during_install_pool_create_total{profile,pool,result}`
- `sovereign_os_during_install_datasets_create_total{profile,result}`
- `sovereign_os_during_install_mok_enroll_total{profile,result}`

### Post-install lifecycle hooks (scripts/hooks/post-install)

- `sovereign_os_post_install_nvidia_bind_total{profile,result}`
- `sovereign_os_post_install_vfio_bind_total{profile,result}`
- `sovereign_os_post_install_arc_clamp_total{profile,result}`
- `sovereign_os_post_install_arc_max_bytes{profile}` — applied ZFS ARC ceiling
- `sovereign_os_post_install_network_vlan_total{profile,result}`
- `sovereign_os_post_install_shell_setup_total{profile,result}`
- `sovereign_os_post_install_tetragon_policy_load_total{profile,result}`
- `sovereign_os_post_install_first_login_assistant_total{profile,result}`
- `sovereign_os_post_install_first_login_assistant_choices{profile}` — number of opt-in choices the operator made
- `sovereign_os_post_install_server_hardening_total{profile,result}` — apply-server-hardening hook (role-server profiles): success / dry-run / skipped / fail
- `sovereign_os_post_install_server_hardening_applied{profile}` — count of drop-in files actually applied on the last run
- `sovereign_os_post_install_workstation_hardening_total{profile,result}` — apply-workstation-hardening hook (role-workstation profiles): success / dry-run / skipped / fail
- `sovereign_os_post_install_workstation_hardening_applied{profile}` — count of drop-in files applied (workstation = 4 vs server = 5)
- `sovereign_os_friction_audit_failures{profile}` — runtime friction-audit fails (lspci / IOMMU mismatch)
- `sovereign_os_friction_audit_warnings{profile}`
- `sovereign_os_friction_audit_last_run_timestamp{profile}`

### Recurrent maintenance (scripts/hooks/recurrent + systemd timers)

- `sovereign_os_log_rotation_files_rotated`
- `sovereign_os_log_rotation_files_purged`
- `sovereign_os_log_rotation_last_run_timestamp`
- `sovereign_os_zfs_pool_health{pool}`
- `sovereign_os_zfs_scrub_last_run_timestamp{pool}`
- `sovereign_os_snapshot_count{dataset}`
- `sovereign_os_snapshot_last_created_timestamp{dataset}`
- `sovereign_os_snapshot_pruned_total{dataset}`
- `sovereign_os_snapshot_created_total{dataset}`
- `sovereign_os_security_updates_available`
- `sovereign_os_security_update_check_last_run_timestamp`
- `sovereign_os_models_catalog_total{result}` — verified / missing-manifest / corrupt counters from the last catalog-sync
- `sovereign_os_models_catalog_total_bytes`
- `sovereign_os_models_catalog_resident_count`
- `sovereign_os_models_catalog_last_run_timestamp`
- `sovereign_os_meta_alert_count{level}` — count of derived alerts by level (ALERT/WARN) from the hourly alerts-check
- `sovereign_os_meta_alert_by_metric{metric,level}` — per-(metric,level) histogram of derived alerts; lets operators graph which underlying metric is the noisiest
- `sovereign_os_meta_alerts_check_last_run_timestamp`

### Inference router (scripts/inference)

- `sovereign_os_inference_route_total{tier}`
- `sovereign_os_inference_router_task_type_total{task_type}` — per-task-type classification (R161, closes R157 follow-up). Also surfaced as `X-Sovereign-Task-Type` HTTP response header per request.
- `sovereign_os_inference_router_last_route_timestamp`
- `sovereign_os_inference_backend_start_total{tier,backend,result}`
- `sovereign_os_inference_backend_pid{tier}`

### Perimeter

- `sovereign_os_perimeter_status`
- `sovereign_os_perimeter_verify_last_run_timestamp`

### Trinity execution machinery (R152-R155 — master spec §§ 10, 17, 20, 21)

Pulse (CPU ternary inference; bitnet.cpp + Wasm AOT):
- `sovereign_os_pulse_build_total{result}` — bitnet.cpp build outcomes per run of `scripts/pulse/build-bitnet.sh`
- `sovereign_os_pulse_build_last_run_timestamp` — last Pulse-runtime build attempt
- `sovereign_os_pulse_wasm_aot_total{result}` — Wasm-to-AVX-512 AOT invocations from `scripts/pulse/wasm-aot.sh` (success/skip/fail)
- `sovereign_os_pulse_wasm_aot_last_run_timestamp` — last AOT compile

Weaver (atomic state transitions; master spec § 21):
- `sovereign_os_weaver_atomic_write_total{file,result}` — per-state-file atomic commit outcomes (IDENTITY/SOUL/AGENTS/CLAUDE)
- `sovereign_os_weaver_atomic_write_bytes{file}` — bytes committed per atomic write
- `sovereign_os_weaver_atomic_write_last_timestamp{file}` — last successful atomic commit per file

Auditor (Tetragon eBPF event-loop guardian; master spec § 10):
- `sovereign_os_auditor_neutralization_total{result}` — `podman kill` outcomes per perimeter violation (success/kill-failed/no-container-id/dry-run)
- `sovereign_os_auditor_event_parse_total{outcome}` — Tetragon event parse classification (trigger/benign/bad-json)
- `sovereign_os_auditor_last_neutralization_timestamp` — last neutralization event

### Inference fabric extensions (R156-R157)

Model catalog (R156 — master spec § 17/18):
- `sovereign_os_models_pull_total{model,result}` — outcomes of `scripts/models/pull.sh` per declared model (success/fail/skip-aspirational/missing-tool/dry-run)
- `sovereign_os_models_pull_last_timestamp{model}` — last successful pull per model

DFlash speculative decoding (R157 — master spec Block 7):
- `sovereign_os_dflash_decision_total{task_type,decision}` — per-task-type gating decisions from `scripts/inference/dflash-wrap.sh` (enabled/disabled/disabled-no-install)
- `sovereign_os_dflash_last_invocation_timestamp{task_type}` — last DFlash decision per task type

### Substrate fabric (R158-R159 — master spec §§ 8, 22)

Asymmetric Zero-Trust network rendering (R158 — master spec § 8):
- `sovereign_os_network_asymmetric_render_total{profile,result}` — outcomes of `scripts/network/render-asymmetric.sh` (success/dry-run/legacy-rendered/skip-empty/skip-no-address)
- `sovereign_os_network_asymmetric_render_last_timestamp{profile}` — last successful render per profile

Master bootstrap verification (R159 — master spec § 22):
- `sovereign_os_bootstrap_check_total{check,result}` — per-check outcome (PASS/FAIL/SKIP) for the 6 master spec § 22 checks
- `sovereign_os_bootstrap_verify_last_run_timestamp` — last verify run (any subset)

When a new hook adds metrics: add a row to the section above + a panel
to the relevant dashboard JSON + bump the dashboard `version`.
Operators re-import to pick up. The `test_metric_inventory_lockstep.py`
lint guards against forgetting the README row.

## Layer 3 coverage

`tests/lint/test_dashboard_json_valid.py` parses every dashboard JSON
and verifies it has the minimum shape Grafana requires (title, uid,
panels[], schemaVersion).
