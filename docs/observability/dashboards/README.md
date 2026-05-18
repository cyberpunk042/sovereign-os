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
| `sovereign-os-thermals.json` | sovereign-os thermal observability (R176) | last-tick age · breach_total · hottest sensor · critical count · per-sensor time series · current-status table · breach-count rolling chart · selfdef-daemon hardware probe panel (when SD-R22 [hardware_probe].enabled) |
| `sovereign-os-auth-tier.json` | sovereign-os auth-tier (R484, E11.M7+) | per-tier query counters across the 6-tier §1g ladder (no-auth / basic / advanced / social / enterprise / network-level) · query rate per tier + per verb · result distribution · current-state tier × dashboard table · §1g verbatim text panel with ladder definition |
| `sovereign-os-edge-firewall.json` | sovereign-os edge-firewall (R485, E11.M9+) | per-candidate query counters across the 4-class §1g ladder (nftables-baseline / fail2ban / crowdsec / suricata) · install-failures stat · query rate per candidate + per verb · result distribution · verb × candidate × result histogram · §1g verbatim text panel quoting the 'pay the performance price' rationale |
| `sovereign-os-network-edge.json` | sovereign-os network-edge (R486, E11.M8+) | per-verb query counters (detect / opnsense_status / opnsense_capabilities / interfaces / nat_chain / watch) · OPNsense reachability tier time series (unavailable / reachable / authenticated / full-api) · result distribution · verb × result histogram · §1g verbatim text panel with two-NAT-hop chain + OPNsense capability-unlock ladder |
| `sovereign-os-global-history.json` | sovereign-os global-history (R487, E11.M5+) | per-verb query counters (recent / summary / sources / delta / tail) · per-source attention time series (apt / dpkg / shell / osctl / events / modules) · cumulative source distribution · verb × source × result histogram · §1g verbatim text panel with 6-source ladder + 'delta / differentials' rationale + disambiguation from `history` / `events` / `journal` |
| `sovereign-os-compliance.json` | sovereign-os compliance (R489, R458+) | per-verb query counters (status / module / worst / history / snapshot) · per-instrument attention time series (surface-map / doc-coverage / anti-minimization-audit / ux-design-audit / all) · result distribution · verb × instrument × result histogram · §1g/§1h verbatim text panel with the 4-instrument suite + 'we do not minimize anything' standing rule |
| `sovereign-os-anti-minimization-audit.json` | sovereign-os anti-minimization-audit (R490, R456+) | per-verb query counters (patterns / scan / module / report / waivers) · per-pattern attention time series across the 8-pattern suite (todo-no-anchor / empty-stub / skipped-no-followup / surface-gap / doc-gap / mandate-todo / minimize-phrase / partial-status) · result distribution · verb × pattern × result histogram · §1g verbatim text panel with the 8-pattern catalog + R474/R476/R478 precision filters + 'we do not minimize anything' standing rule |
| `sovereign-os-doc-coverage.json` | sovereign-os doc-coverage (R491, R454+) | per-verb query counters (kinds / modules / scan / coverage / gaps) · per-kind attention time series across the 6-kind ladder (readme / sdd / helptext / metric-inventory / mandate-row / man-page) · result distribution · verb × kind × result histogram · §1g verbatim text panel with the 6-kind doc ladder + 'we do not minimize anything' standing rule |
| `sovereign-os-ux-design-audit.json` | sovereign-os ux-design-audit (R492, R457+) | per-verb query counters (dimensions / modules / audit / score / report) · per-dimension attention time series across the 6-dimension UX ladder (action-budget / discoverable / recoverable / next-step / operator-named / readable-30s) · result distribution · verb × dimension × result histogram · §1g verbatim text panel with the 6-dimension UX ladder + 'we do not minimize anything' standing rule |
| `sovereign-os-surface-map.json` | sovereign-os surface-map (R493, R453+) | per-verb query counters (surfaces / modules / coverage / gaps / waivers) · per-surface attention time series across the 8-surface §1g ladder (core / cli / tui / api / mcp / dashboard / webapp / service) · result distribution · verb × surface × result histogram · §1g verbatim text panel with the 8-surface delivery ladder + R478 structural-vs-FUTURE waiver distinction + 'we do not minimize anything' standing rule. Closes the 4-instrument meta-coverage loop: surface-map now appears in its own MODULE_COVERAGE. |
| `sovereign-os-trinity.json` | sovereign-os trinity (R494, R290-R299+ E5) | per-tier route counters (pulse / logic-engine / oracle-core) · last-route freshness stat · per-tier route rate (5m) · per-task-type route rate · backend start success/skip/fail barchart · live backend PID table · router class distribution time series · §1g verbatim text panel with the 3-tier Trinity ladder + operator-named-port-binding + lifecycle CLI + 'we do not minimize anything' standing rule |
| `sovereign-os-weaver.json` | sovereign-os weaver (R496, master spec § 21) | total / success atomic-write counters · distinct-state-files stat · freshest-commit-age stat across the 4-file fabric (IDENTITY / SOUL / AGENTS / CLAUDE) · per-file × per-result write rate (5m) · cumulative writes per file × result barchart · per-file payload bytes time series · per-file last-commit age table · §21 verbatim text panel with the Atomic State Transition Protocol (O_DIRECT / O_SYNC / O_TRUNC / 4K-aligned / atomic rename) + ZFS prerequisites + 4-file ladder + 'we do not minimize anything' standing rule |
| `sovereign-os-router.json` | sovereign-os router (R495, SDD-011+ R161 R215) | total-routes + last-route freshness + distinct-task-types + distinct-model-classes stats · per-tier route rate (5m) · per-task-type route rate across the 4-class R161 taxonomy (code / math / conversational / creative) · per-model-class route rate across the 13-class R215 taxonomy (llm / slm / rlm / ternary-lm / lora-adapter / embed / vision / multimodal / code / mixture / speculative / reranker / (unspecified)) · cumulative routes per tier barchart · tier × task-type decision matrix · §1g verbatim text panel with R161 task-type + R215 model-class taxonomies + 6-surface signal-flow + 'we do not minimize anything' standing rule |

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
- `sovereign_os_notify_events_emitted_total` — R229: count of NEW probe-transition events emitted by the hourly notify-dispatch hook (R228 dedup applied — only transitions, never spam).
- `sovereign_os_notify_deliveries_ok_total` — R229: count of per-channel deliveries (file / webhook / ntfy) that returned ok on the last tick.
- `sovereign_os_notify_deliveries_fail_total` — R229: count of per-channel deliveries that failed (unresolved env-var, network error, etc). Operators alert when this is non-zero.
- `sovereign_os_notify_last_run_timestamp` — R229: timestamp of the most recent notify-dispatch tick (operators alert on staleness vs the hourly timer).
- `sovereign_os_power_shutdown_guard_last_run_timestamp` — R253: timestamp of the most recent UPS-battery shutdown-guard tick (operators alert on staleness vs the per-minute timer when on UPS power).
- `sovereign_os_power_shutdown_guard_advisory_rc` — R253: rc from the R252 `power-status advisories` call (0=ok/no-ups, 1=critical, 2=usage-error).
- `sovereign_os_power_shutdown_guard_verdict` — R253: encoded verdict (0=ok, 1=attention, 2=critical, 3=no-ups, 9=error). Operators alert when this transitions to 2.
- `sovereign_os_power_estimated_load_watts` — R258: live aggregate of R219 GPU draw + declared CPU TDP + overhead, sampled every minute.
- `sovereign_os_power_headroom_watts` — R258: PSU sustained budget minus estimated load — operators alert when this goes negative.
- `sovereign_os_power_utilization_pct` — R258: estimated load as percent of PSU sustained budget — operators alert at ≥85% sustained.
- `sovereign_os_power_sample_last_run_timestamp` — R258: timestamp of the most recent wattage sample (operators alert on staleness vs the per-minute timer).
- `sovereign_os_thermal_celsius{sensor}` — per-sensor temperature in °C (R172). Sources: `/sys/class/hwmon/<dev>/temp<N>_input` + `nvidia-smi` GPU temps. Updated every 5 min by `sovereign-thermal-watch.timer`.
- `sovereign_os_thermal_severity{sensor,level}` — 1 if `<sensor>` is currently at `<level>` ∈ {ok, warn, critical}, 0 otherwise. Thresholds are profile-aware (sain-01: warn≥85 crit≥95; headless: warn≥75 crit≥85; GPU sensors: warn≥85 crit≥95 regardless of profile).
- `sovereign_os_thermal_breach_total` — count of sensors at WARN+CRITICAL on the last tick. Operator-facing "is anything overheating right now?" gauge.
- `sovereign_os_thermal_last_run_unix` — timestamp of the most recent thermal-watch tick (operators alert on staleness).

### GPU power policy (R219 / SDD-026 Z-5 — scripts/hardware/gpu-watch.py)

- `sovereign_os_gpu_power_limit_watts{gpu,idx}` — live nvidia-smi `power.limit` reading per GPU. Gauge; sampled by `gpu-watch.py --emit-metrics` (manual / timer).
- `sovereign_os_gpu_power_draw_watts{gpu,idx}` — live `power.draw` per GPU. Operator dashboards plot the trend for sustained-inference workloads.
- `sovereign_os_gpu_power_limit_deviance_watts{gpu,idx}` — `abs(actual_limit - operator_safe_limit)` for GPUs matched by `/etc/sovereign-os/gpu-policy.toml`. 0 = operator's safe limit honored; >tolerance = nvidia-smi-fix needed.
- `sovereign_os_gpu_sustained_draw_warning{gpu,idx}` — 1 when current `power_draw_watts` exceeds the operator's `max_sustained_draw_watts` band. Informational; sustained loads are normal during inference.

### Inference router (scripts/inference)

- `sovereign_os_inference_route_total{tier}`
- `sovereign_os_inference_router_task_type_total{task_type}` — per-task-type classification (R161, closes R157 follow-up). Also surfaced as `X-Sovereign-Task-Type` HTTP response header per request.
- `sovereign_os_inference_router_class_total{class}` — per-model-class classification (R215, composes with R212 catalog taxonomy: llm/slm/rlm/ternary-lm/lora-adapter/embed/vision/multimodal/code/mixture/speculative/reranker/(unspecified)). Operators supply the explicit class via the operator-asserted request-body field; the router otherwise infers from the model id. Also surfaced as `X-Sovereign-Model-Class` HTTP response header.
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

### Operator-tooling (R447-R448 — scripts/operator)

E11.M6 (operator §1g — bashrc integration + autocompletes + aliases + menus):
- `sovereign_os_operator_bashrc_install_total{action,result}` — outcomes of `scripts/operator/bashrc-install.sh` (action=install/uninstall/status/dump; result=success/dry-run/absent/installed/skip-no-file/skip-no-block)

E11.M5 (operator §1g — global history surface, delta/differential across 6 sources):
- `sovereign_os_operator_global_history_query_total{verb,source,result}` — `sovereign-osctl global-history <verb>` queries (verb=recent/summary/sources/delta; source=apt|dpkg|shell|osctl|events|modules|all|comma-joined; result=ok)

E11.M8 (operator §1g — network topology + OPNsense detection):
- `sovereign_os_operator_network_topology_query_total{verb,result}` — `sovereign-osctl network-topology <verb>` queries (verb=detect/opnsense_status/opnsense_capabilities/interfaces/nat_chain; result=ok|tier-name|unavailable)

E11.M7 (operator §1g — 6-tier auth ladder per-dashboard):
- `sovereign_os_operator_auth_tier_query_total{verb,tier,result}` — `sovereign-osctl auth-tier <verb>` queries (verb=list-tiers/registry/show/matrix/set; tier=no-auth|basic|advanced|social|enterprise|network-level|all|unknown; result=ok|preview|applied|dry-run|unknown-tier|unknown-dashboard|blocked-skip-tiers|mkdir-failed|write-failed)

E11.M9 (operator §1g — workstation-side edge-firewall alternative):
- `sovereign_os_operator_edge_firewall_query_total{verb,candidate,result}` — `sovereign-osctl edge-firewall <verb>` queries (verb=state/candidates/recommend/install-plan/install; candidate=nftables-baseline|fail2ban|crowdsec|suricata|all|unknown; result=ok|preview|applied|dry-run|already-installed|unknown-candidate|needs-root|step-failed|step-error)

E11.M2 (operator §1g — master-dashboard / reverse-proxy aggregator):
- `sovereign_os_operator_master_dashboard_query_total{verb,backend,result}` — `sovereign-osctl master-dashboard <verb>` queries (verb=list/routes/collisions/render/health; backend=nginx|caddy|traefik|any|unknown; result=ok|preview|applied|dry-run|clean|collisions|blocked-collisions|unknown-backend|unknown-mode|write-failed)

E11.M3 (operator §1g — multi-surface delivery contract):
- `sovereign_os_operator_surface_map_query_total{verb,surface,result}` — `sovereign-osctl surface-map <verb>` queries (verb=surfaces/modules/coverage/gaps/waivers; surface=core|cli|tui|api|mcp|dashboard|webapp|service|all|any|unknown; result=ok|below-threshold|unknown-module|unknown-surface)

E11.M1 (operator §1g — documentation through-and-through):
- `sovereign_os_operator_doc_coverage_query_total{verb,kind,result}` — `sovereign-osctl doc-coverage <verb>` queries (verb=kinds/modules/scan/coverage/gaps; kind=readme|sdd|helptext|metric-inventory|mandate-row|man-page|all|any|unknown; result=ok|below-threshold|unknown-module)

E11.M11 (operator §1g — anti-minimization audit standing rule):
- `sovereign_os_operator_anti_minimization_audit_query_total{verb,pattern,result}` — `sovereign-osctl anti-minimization-audit <verb>` queries (verb=patterns/scan/module/cross-module/report/waivers/selfdef; pattern=todo-no-anchor|empty-stub|skipped-no-followup|surface-gap|doc-gap|mandate-todo|minimize-phrase|partial-status|all|any|unknown; result=ok|unknown-pattern|unknown-module). R474 added the `waivers` verb (operator-explicit `# anti-min-waiver:` annotation listing).

E11.M10 (operator §1g — thorough UX design stage):
- `sovereign_os_operator_ux_design_audit_query_total{verb,dimension,result}` — `sovereign-osctl ux-design-audit <verb>` queries (verb=dimensions/modules/audit/score/report; dimension=action-budget|discoverable|recoverable|next-step|operator-named|readable-30s|all|any|unknown; result=ok|below-threshold|unknown-module)

R458 (operator §1g/§1h — compliance dashboard aggregator):
- `sovereign_os_operator_compliance_query_total{verb,instrument,result}` — `sovereign-osctl compliance <verb>` queries (verb=status/module/worst/history/snapshot; instrument=surface-map|doc-coverage|anti-minimization-audit|ux-design-audit|all|any; result=ok|preview|applied|dry-run|write-failed)

When a new hook adds metrics: add a row to the section above + a panel
to the relevant dashboard JSON + bump the dashboard `version`.
Operators re-import to pick up. The `test_metric_inventory_lockstep.py`
lint guards against forgetting the README row.

## Layer 3 coverage

`tests/lint/test_dashboard_json_valid.py` parses every dashboard JSON
and verifies it has the minimum shape Grafana requires (title, uid,
panels[], schemaVersion).
