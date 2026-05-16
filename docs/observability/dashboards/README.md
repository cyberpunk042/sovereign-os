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

### Inference router (scripts/inference)

- `sovereign_os_inference_route_total{tier}`
- `sovereign_os_inference_router_last_route_timestamp`
- `sovereign_os_inference_backend_start_total{tier,backend,result}`
- `sovereign_os_inference_backend_pid{tier}`

### Perimeter

- `sovereign_os_perimeter_status`
- `sovereign_os_perimeter_verify_last_run_timestamp`

When a new hook adds metrics: add a row to the section above + a panel
to the relevant dashboard JSON + bump the dashboard `version`.
Operators re-import to pick up. The `test_metric_inventory_lockstep.py`
lint guards against forgetting the README row.

## Layer 3 coverage

`tests/lint/test_dashboard_json_valid.py` parses every dashboard JSON
and verifies it has the minimum shape Grafana requires (title, uid,
panels[], schemaVersion).
