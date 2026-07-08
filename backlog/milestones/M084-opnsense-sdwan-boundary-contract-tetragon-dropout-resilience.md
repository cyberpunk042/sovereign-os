# M084 — OPNsense/SD-WAN boundary contract + Tetragon-dropout resilience (Zero-Trust dual-NIC perimeter)

**Parent**: sovereign-os infrastructure — network perimeter + security-loop resilience layer (extends M003 hardware topology; pairs with selfdef MS047 perimeter + MS044 guardian)
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 420-424 (expansion item 2 — Network Infrastructure & Perimeter Segregation), 456-475 (§ 8 — dual-NIC Zero-Trust topology, VLAN 100/200), 761-765 (OPNsense WAN/LAN Bridging and Tetragon Interface Dropouts — gotcha + prevention, verbatim)
**Audit provenance**: closes the 2026-06 catalog audit gap #3 — "OPNsense / SD-WAN boundary contract — the VLAN concept is catalogued (M003) but the firewall interface + Tetragon-socket-dropout gotcha isn't."
**Shipped already**: the dropout prevention is implemented in commit `47632d0` (`BindsTo=tetragon.service` on the guardian unit + EOF fall-through exits nonzero instead of silently returning 0).

## Doctrinal anchors

> "Network Infrastructure & Perimeter Segregation (Interfacing the ProArt dual NICs with your OPNsense/SD-WAN firewall topology)." (dump 422)
> "The ProArt X870E-Creator features asymmetric networking ports: a Marvell 10GbE adapter and an Intel 2.5GbE adapter. To align with a Zero-Trust OPNsense / SD-WAN core architecture, network traffic is physically segregated at the hardware boundary." (dump 456)
> "Your network design separates management traffic (Intel 2.5GbE) from data processing paths (Marvell 10GbE). If your OPNsense/SD-WAN firewall dynamically re-shuffles interface addresses or drops a lease connection along the management path, the system loopback hooks used by the Tetragon socket stream can experience buffer disconnects." (dump 762)
> "The Gotcha: If Tetragon drops its connection to the system logging pipeline during a network reconfiguration event, the `guardian-core` script will stall on its read loop, blinding your real-time exploit containment system." (dump 764)
> "The Prevention: The `guardian-core.service` systemd unit file must include explicit service binding controls (`BindsTo=tetragon.service`) and include health checking routines that instantly restart the security loop if the local UNIX socket encounters an end-of-file (EOF) exception." (dump 765)

## Epics (E0808-E0817)

| epic | name | source |
|---|---|---|
| E0808 | Zero-Trust dual-NIC boundary — traffic physically segregated at the hardware boundary | dump 456 |
| E0809 | OPNsense Core Router / SD-WAN Firewall as the perimeter authority | dump 460 |
| E0810 | VLAN 100 — management/telemetry plane on the Intel I226-V 2.5GbE | dump 460-475 |
| E0811 | VLAN 200 — model ingestion/storage plane on the Marvell AQC113C 10GbE | dump 460-475 |
| E0812 | No-outbound-WAN rule for the data plane (container bridge isolated; NAS-only pulls) | dump 460-475 |
| E0813 | Tetragon-dropout gotcha — interface re-shuffle → socket buffer disconnects → guardian blind | dump 762-764 |
| E0814 | Dropout prevention — `BindsTo=tetragon.service` binding control (verbatim-required) | dump 765 |
| E0815 | Dropout prevention — EOF health routine: instantly restart the security loop on stream EOF | dump 765 |
| E0816 | Firewall interface contract — sovereign-os ↔ OPNsense observation surface (read-only) | dump 422 + E11.M8 lineage |
| E0817 | Reconfiguration-event observability — interface re-shuffles must be operator-visible | dump 762 + architecture |

## Modules (M01412-M01428)

| module | name | source |
|---|---|---|
| M01412 | sovereign-boundary-nic-role-map (Intel 2.5GbE ↔ management; Marvell 10GbE ↔ data) | dump 460-475 |
| M01413 | sovereign-boundary-vlan100-contract (host SSH · Tetragon log streams · system updates) | dump 460-475 |
| M01414 | sovereign-boundary-vlan200-contract (isolated container bridge · model weight pulls (NAS) · no outbound WAN) | dump 460-475 |
| M01415 | sovereign-boundary-opnsense-observer (reachability tiers; read-only firewall interface) | E11.M8 / R486 lineage |
| M01416 | sovereign-boundary-nat-chain-lens (two-NAT-hop chain visibility) | E11.M8 network-edge lineage |
| M01417 | sovereign-guardian-bindsto-binding (BindsTo=tetragon.service in the unit) | dump 765 + commit 47632d0 |
| M01418 | sovereign-guardian-eof-sentinel (EOF fall-through → nonzero exit + journal evidence) | dump 765 + commit 47632d0 |
| M01419 | sovereign-guardian-restart-loop (Restart=always + RestartSec=1 recovery cycle) | dump 765 + unit |
| M01420 | sovereign-boundary-reconfig-detector (interface re-shuffle / lease-drop event surfacing) | dump 762 + architecture |
| M01421 | sovereign-boundary-dropout-metrics (guardian restart + stream-loss counters) | architecture + cross-ref M049 |
| M01422 | sovereign-boundary-dashboard-binding (network-edge + guardian panels) | cross-ref M060 |
| M01423 | sovereign-boundary-alert-binding (guardian-silent + perimeter alerts) | cross-ref M055 + alert fleet |
| M01424 | sovereign-boundary-typed-mirror (NIC-role + VLAN contract mirror under MS007) | cross-ref selfdef MS007 |
| M01425 | sovereign-boundary-event-emitter (OCSF via MS026 on reconfig + dropout) | cross-ref selfdef MS026 |
| M01426 | sovereign-boundary-cli-surface (network-edge verbs: detect / opnsense_status / interfaces / nat_chain / watch) | E11.M8 / R486 |
| M01427 | sovereign-boundary-test-harness (dropout simulation: EOF injection + unit-binding assertions) | repo test discipline |
| M01428 | sovereign-boundary-doctrine-preserver (gotcha + prevention quoted verbatim in docs/units) | dump 764-765 |

## Features (F07041-F07125)

| feature | name | source |
|---|---|---|
| F07041 | Doctrinal — expansion item 2: Network Infrastructure & Perimeter Segregation | dump 422 |
| F07042 | Doctrinal — asymmetric ports: Marvell 10GbE + Intel 2.5GbE | dump 456 |
| F07043 | Doctrinal — "Zero-Trust OPNsense / SD-WAN core architecture" verbatim | dump 456 |
| F07044 | Doctrinal — "network traffic is physically segregated at the hardware boundary" verbatim | dump 456 |
| F07045 | Topology — OPNsense Core Router / SD-WAN Firewall at the root | dump 460 |
| F07046 | Topology — VLAN 100 = Management/Telemetry | dump 460-475 |
| F07047 | Topology — VLAN 200 = Model Ingestion/Storage | dump 460-475 |
| F07048 | Topology — Intel I226-V 2.5GbE carries VLAN 100 | dump 460-475 |
| F07049 | Topology — Marvell AQC113C 10GbE carries VLAN 200 | dump 460-475 |
| F07050 | VLAN 100 role — host SSH | dump 460-475 |
| F07051 | VLAN 100 role — Tetragon log streams | dump 460-475 |
| F07052 | VLAN 100 role — system updates | dump 460-475 |
| F07053 | VLAN 200 role — isolated container bridge | dump 460-475 |
| F07054 | VLAN 200 role — model weight pulls (NAS) | dump 460-475 |
| F07055 | VLAN 200 role — NO outbound WAN access | dump 460-475 |
| F07056 | Gotcha — interface re-shuffle / lease drop on the management path | dump 762 |
| F07057 | Gotcha — Tetragon socket stream buffer disconnects | dump 762 |
| F07058 | Gotcha — guardian-core stalls on its read loop | dump 764 |
| F07059 | Gotcha — "blinding your real-time exploit containment system" verbatim | dump 764 |
| F07060 | Prevention — BindsTo=tetragon.service explicit service binding control | dump 765 |
| F07061 | Prevention — health routine restarts the security loop on UNIX-socket EOF | dump 765 |
| F07062 | Shipped — unit carries BindsTo=tetragon.service (commit 47632d0) | commit 47632d0 |
| F07063 | Shipped — EOF fall-through logs [EOF] + exits nonzero (commit 47632d0) | commit 47632d0 |
| F07064 | Shipped — Restart=always + RestartSec=1 completes the instant-restart loop | unit + dump 765 |
| F07065 | Unit — After=tetragon.service ordering preserved | unit + master spec § 10.2 |
| F07066 | Unit — Requires=tetragon.service preserved alongside BindsTo | unit + master spec § 10.2 |
| F07067 | Unit — R171 defense-in-depth posture unchanged by the binding additions | unit + R171 gate |
| F07068 | EOF sentinel — exit 0 on EOF is forbidden (hides the blinding) | dump 764 + commit 47632d0 |
| F07069 | EOF sentinel — journal carries "[EOF] tetragon event stream ... closed — perimeter blind" | commit 47632d0 |
| F07070 | EOF sentinel — failure-restart recorded by systemd (not a clean-exit restart) | commit 47632d0 |
| F07071 | Firewall interface — OPNsense observed read-only (no mutation from sovereign-os) | E11.M8 lineage + R10212 doctrine |
| F07072 | Firewall interface — reachability ladder: unavailable / reachable / authenticated / full-api | E11.M8 / R486 |
| F07073 | Firewall interface — detect / opnsense_status / opnsense_capabilities verbs | E11.M8 / R486 |
| F07074 | Firewall interface — interfaces / nat_chain / watch verbs | E11.M8 / R486 |
| F07075 | Firewall interface — two-NAT-hop chain documented + visible | E11.M8 network-edge |
| F07076 | Reconfig observability — interface re-shuffle events surfaced to the operator | dump 762 + architecture |
| F07077 | Reconfig observability — lease-drop events on the management path surfaced | dump 762 + architecture |
| F07078 | Reconfig observability — guardian restart correlated with reconfig window | architecture |
| F07079 | Metrics — guardian failure-restart count trackable over time | architecture + cross-ref M049 |
| F07080 | Metrics — stream-EOF occurrences trackable over time | architecture + cross-ref M049 |
| F07081 | Metrics — perimeter-blind window duration measurable (restart latency) | architecture |
| F07082 | Alerts — guardian-silent condition pages (observer-silent pattern) | alert fleet pattern |
| F07083 | Alerts — repeated EOF-restart churn pages (flap detection) | architecture + alert fleet |
| F07084 | Dashboard — network-edge panel shows OPNsense reachability tier over time | cross-ref M060 + E11.M8 |
| F07085 | Dashboard — guardian panel shows restart/EOF history | cross-ref M060 |
| F07086 | Typed mirror — NIC-role map mirrored under MS007 scheme | cross-ref selfdef MS007 |
| F07087 | Typed mirror — NicRole enum {ManagementTelemetry, ModelIngestionStorage} | dump 460-475 + MS007 |
| F07088 | Typed mirror — VlanContract struct {vlan_id, nic, roles, outbound_wan} | dump 460-475 + MS007 |
| F07089 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F07090 | Event — OCSF Network Activity on detected reconfiguration events | cross-ref selfdef MS026 |
| F07091 | Event — OCSF System Activity on guardian EOF-restart | cross-ref selfdef MS026 |
| F07092 | Event — M049 trace spans for dropout-recovery cycles | cross-ref M049 |
| F07093 | CLI — network-edge verbs reachable via sovereign-osctl | E11.M8 / R486 |
| F07094 | CLI — guardian status surfaces last-restart reason (EOF vs clean) | architecture |
| F07095 | Composition — extends M003 hardware topology (VLAN concept → full boundary contract) | cross-ref M003 + audit gap #3 |
| F07096 | Composition — composes with M013 observability-as-control-input | cross-ref M013 |
| F07097 | Composition — composes with M045 Linux-as-intelligence-governor (PSI/systemd) | cross-ref M045 |
| F07098 | Composition — composes with M049 trace pipeline | cross-ref M049 |
| F07099 | Composition — composes with M055 failure modes (dropout = catalogued failure mode) | cross-ref M055 |
| F07100 | Composition — composes with M060 cockpit visibility | cross-ref M060 |
| F07101 | Composition — composes with selfdef MS044 guardian daemon (the protected loop) | cross-ref selfdef MS044 |
| F07102 | Composition — composes with selfdef MS047 perimeter engine (kernel fence) | cross-ref selfdef MS047 |
| F07103 | Composition — composes with selfdef MS038 network boundary | cross-ref selfdef MS038 |
| F07104 | Composition — composes with selfdef MS012 perimeter coexistence | cross-ref selfdef MS012 |
| F07105 | Boundary — sovereign-os observes the firewall; OPNsense enforces the perimeter | dump 456 + R10212 doctrine |
| F07106 | Boundary — sovereign-os never mutates firewall state | R10212 read-only doctrine |
| F07107 | Boundary — info-hub indexes the topology as read-only second-brain entries | operator standing direction "second-brain" |
| F07108 | Doctrinal preservation — "physically segregated at the hardware boundary" never paraphrased | dump 456 |
| F07109 | Doctrinal preservation — gotcha sentence preserved verbatim wherever cited | dump 764 |
| F07110 | Doctrinal preservation — prevention sentence preserved verbatim wherever cited | dump 765 |
| F07111 | Doctrinal preservation — unit comments cite the dump prevention verbatim | commit 47632d0 |
| F07112 | Operational — guardian binding behavior testable without hardware (unit-text lint) | repo test discipline |
| F07113 | Operational — EOF path testable via stream-close simulation | repo test discipline |
| F07114 | Operational — dropout recovery target: perimeter-blind window ≤ 2s (RestartSec=1 + bind) | unit + architecture |
| F07115 | Operational — reconfig events never crash the observer surfaces (graceful degradation) | E11.M8 lineage + architecture |
| F07116 | Operator UX — "is the firewall reachable?" one-verb answer | E11.M8 / R486 |
| F07117 | Operator UX — "did the guardian go blind, when, for how long?" answerable from journal+metrics | architecture |
| F07118 | Operator UX — VLAN contract readable as one table (NIC → VLAN → roles → WAN rule) | dump 460-475 |
| F07119 | Reproducibility — dropout-recovery cycles recorded for replay audit | cross-ref selfdef MS009 |
| F07120 | Reproducibility — unit changes to the binding controls require the bidir gate to pass | repo gate discipline |
| F07121 | Audit lineage — 2026-06 catalog audit gap #3 closed by this milestone | audit verbatim |
| F07122 | Audit lineage — M003 VLAN concept extended to the full firewall-interface contract | audit verbatim + cross-ref M003 |
| F07123 | Closing — covers dump 420-424 + 456-475 + 761-765 verbatim scope | dump ranges |
| F07124 | Closing — prevention shipped (47632d0); boundary observation surfaces from E11.M8 linked | commit 47632d0 + E11.M8 |
| F07125 | Closing — reconfig-detector + dropout-metrics + flap alert remain explicitly pending | architecture + operator standing constraint |

## Requirements (R14081-R14250)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R14081 | Doctrinal — expansion item 2 catalogued as a first-class boundary contract | dump 422 | F07041 | non-negotiable | false | 10 |
| R14082 | Doctrinal — asymmetric ports (Marvell 10GbE + Intel 2.5GbE) recorded | dump 456 | F07042 | non-negotiable | false | 10 |
| R14083 | Doctrinal — "Zero-Trust OPNsense / SD-WAN core architecture" preserved verbatim | dump 456 | F07043 | non-negotiable | false | 10 |
| R14084 | Doctrinal — "physically segregated at the hardware boundary" preserved verbatim | dump 456 | F07044 | non-negotiable | false | 10 |
| R14085 | Topology — OPNsense Core Router / SD-WAN Firewall is the perimeter root | dump 460 | F07045 | non-negotiable | false | 10 |
| R14086 | Topology — VLAN 100 designated Management/Telemetry | dump 460-475 | F07046 | non-negotiable | false | 10 |
| R14087 | Topology — VLAN 200 designated Model Ingestion/Storage | dump 460-475 | F07047 | non-negotiable | false | 10 |
| R14088 | Topology — Intel I226-V 2.5GbE bound to VLAN 100 | dump 460-475 | F07048 | non-negotiable | false | 10 |
| R14089 | Topology — Marvell AQC113C 10GbE bound to VLAN 200 | dump 460-475 | F07049 | non-negotiable | false | 10 |
| R14090 | VLAN 100 — carries host SSH | dump 460-475 | F07050 | non-negotiable | false | 10 |
| R14091 | VLAN 100 — carries Tetragon log streams | dump 460-475 | F07051 | non-negotiable | false | 10 |
| R14092 | VLAN 100 — carries system updates | dump 460-475 | F07052 | non-negotiable | false | 10 |
| R14093 | VLAN 200 — carries the isolated container bridge | dump 460-475 | F07053 | non-negotiable | false | 10 |
| R14094 | VLAN 200 — carries model weight pulls (NAS) | dump 460-475 | F07054 | non-negotiable | false | 10 |
| R14095 | VLAN 200 — NO outbound WAN access (hard rule) | dump 460-475 | F07055 | non-negotiable | false | 10 |
| R14096 | VLAN 200 — WAN-access violations are a paging-severity event | dump 460-475 + architecture | F07055 | non-negotiable | false | 10 |
| R14097 | Gotcha — interface re-shuffle / lease drop on management path catalogued as failure mode | dump 762 | F07056 | non-negotiable | false | 10 |
| R14098 | Gotcha — Tetragon socket buffer-disconnect mechanism documented | dump 762 | F07057 | non-negotiable | false | 10 |
| R14099 | Gotcha — guardian read-loop stall documented | dump 764 | F07058 | non-negotiable | false | 10 |
| R14100 | Gotcha — "blinding your real-time exploit containment system" preserved verbatim | dump 764 | F07059 | non-negotiable | false | 10 |
| R14101 | Prevention — BindsTo=tetragon.service present in the guardian unit | dump 765 | F07060 | non-negotiable | false | 10 |
| R14102 | Prevention — EOF health routine restarts the security loop | dump 765 | F07061 | non-negotiable | false | 10 |
| R14103 | Prevention — both prevention halves implemented before this milestone closes | dump 765 + SHIPPED discipline | F07062 | non-negotiable | false | 10 |
| R14104 | Shipped — BindsTo landed in commit 47632d0 | commit 47632d0 | F07062 | non-negotiable | false | 10 |
| R14105 | Shipped — EOF nonzero-exit landed in commit 47632d0 | commit 47632d0 | F07063 | non-negotiable | false | 10 |
| R14106 | Shipped — Restart=always + RestartSec=1 complete the instant-restart loop | unit + dump 765 | F07064 | non-negotiable | false | 10 |
| R14107 | Unit — After=tetragon.service preserved | unit + master spec § 10.2 | F07065 | non-negotiable | false | 10 |
| R14108 | Unit — Requires=tetragon.service preserved alongside BindsTo | unit + master spec § 10.2 | F07066 | non-negotiable | false | 10 |
| R14109 | Unit — R171 defense-in-depth posture unchanged | unit + R171 gate | F07067 | non-negotiable | false | 10 |
| R14110 | Unit — binding controls locked by the guardian bidir gate | repo gate discipline | F07120 | non-negotiable | false | 10 |
| R14111 | EOF sentinel — exit 0 on stream EOF forbidden | dump 764 + commit 47632d0 | F07068 | non-negotiable | false | 10 |
| R14112 | EOF sentinel — journal line names the socket path + "perimeter blind" | commit 47632d0 | F07069 | non-negotiable | false | 10 |
| R14113 | EOF sentinel — systemd records a failure-restart (not clean-exit) | commit 47632d0 | F07070 | non-negotiable | false | 10 |
| R14114 | EOF sentinel — KeyboardInterrupt shutdown remains a clean exit 0 | guardian script | F07068 | non-negotiable | false | 10 |
| R14115 | Firewall interface — observed read-only; no mutation verbs exist | E11.M8 + R10212 | F07071 | non-negotiable | false | 10 |
| R14116 | Firewall interface — reachability ladder unavailable/reachable/authenticated/full-api | E11.M8 / R486 | F07072 | non-negotiable | false | 10 |
| R14117 | Firewall interface — detect verb reachable | E11.M8 / R486 | F07073 | non-negotiable | false | 10 |
| R14118 | Firewall interface — opnsense_status verb reachable | E11.M8 / R486 | F07073 | non-negotiable | false | 10 |
| R14119 | Firewall interface — opnsense_capabilities verb reachable | E11.M8 / R486 | F07073 | non-negotiable | false | 10 |
| R14120 | Firewall interface — interfaces verb reachable | E11.M8 / R486 | F07074 | non-negotiable | false | 10 |
| R14121 | Firewall interface — nat_chain verb reachable | E11.M8 / R486 | F07074 | non-negotiable | false | 10 |
| R14122 | Firewall interface — watch verb reachable | E11.M8 / R486 | F07074 | non-negotiable | false | 10 |
| R14123 | Firewall interface — two-NAT-hop chain documented + visible | E11.M8 | F07075 | non-negotiable | false | 10 |
| R14124 | Reconfig — interface re-shuffle events surfaced to operator (pending detector) | dump 762 + architecture | F07076 | non-negotiable | false | 10 |
| R14125 | Reconfig — lease-drop events on management path surfaced (pending detector) | dump 762 + architecture | F07077 | non-negotiable | false | 10 |
| R14126 | Reconfig — guardian restarts correlatable with reconfig windows | architecture | F07078 | non-negotiable | false | 10 |
| R14127 | Metrics — guardian failure-restart count trackable | architecture + cross-ref M049 | F07079 | non-negotiable | false | 10 |
| R14128 | Metrics — stream-EOF occurrences trackable | architecture + cross-ref M049 | F07080 | non-negotiable | false | 10 |
| R14129 | Metrics — perimeter-blind window duration measurable | architecture | F07081 | non-negotiable | false | 10 |
| R14130 | Metrics — new series inventoried per the metric-inventory lockstep gate | repo gate discipline | F07079 | non-negotiable | false | 10 |
| R14131 | Alerts — guardian-silent condition pages | alert fleet pattern | F07082 | non-negotiable | false | 10 |
| R14132 | Alerts — EOF-restart churn (flap) pages | architecture | F07083 | non-negotiable | false | 10 |
| R14133 | Alerts — every alert carries a resolving runbook anchor | repo gate discipline | F07082 | non-negotiable | false | 10 |
| R14134 | Dashboard — OPNsense reachability tier over time | cross-ref M060 + E11.M8 | F07084 | non-negotiable | false | 10 |
| R14135 | Dashboard — guardian restart/EOF history panel | cross-ref M060 | F07085 | non-negotiable | false | 10 |
| R14136 | Typed mirror — NIC-role map under MS007 scheme | cross-ref selfdef MS007 | F07086 | non-negotiable | false | 10 |
| R14137 | Typed mirror — NicRole enum {ManagementTelemetry, ModelIngestionStorage} | dump 460-475 + MS007 | F07087 | non-negotiable | false | 10 |
| R14138 | Typed mirror — VlanContract struct {vlan_id, nic, roles, outbound_wan} | dump 460-475 + MS007 | F07088 | non-negotiable | false | 10 |
| R14139 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F07089 | non-negotiable | false | 10 |
| R14140 | Typed mirror — schema-breaking changes require version bump | cross-ref selfdef MS007 | F07089 | non-negotiable | false | 10 |
| R14141 | Event — OCSF Network Activity on reconfiguration events | cross-ref selfdef MS026 | F07090 | non-negotiable | false | 10 |
| R14142 | Event — OCSF System Activity on guardian EOF-restart | cross-ref selfdef MS026 | F07091 | non-negotiable | false | 10 |
| R14143 | Event — M049 trace spans for dropout-recovery cycles | cross-ref M049 | F07092 | non-negotiable | false | 10 |
| R14144 | Event — spans deterministic for MS009 replay | cross-ref selfdef MS009 | F07119 | non-negotiable | false | 10 |
| R14145 | CLI — network-edge verbs reachable via sovereign-osctl | E11.M8 / R486 | F07093 | non-negotiable | false | 10 |
| R14146 | CLI — guardian status surfaces last-restart reason | architecture | F07094 | non-negotiable | false | 10 |
| R14147 | CLI — unknown subverbs exit 2 (dispatch-surface discipline) | repo CLI discipline | F07093 | non-negotiable | false | 10 |
| R14148 | Composition — extends M003 (VLAN concept → full boundary contract) | cross-ref M003 + audit | F07095 | non-negotiable | false | 10 |
| R14149 | Composition — composes with M013 observability-as-control-input | cross-ref M013 | F07096 | non-negotiable | false | 10 |
| R14150 | Composition — composes with M045 Linux-as-intelligence-governor | cross-ref M045 | F07097 | non-negotiable | false | 10 |
| R14151 | Composition — composes with M049 trace pipeline | cross-ref M049 | F07098 | non-negotiable | false | 10 |
| R14152 | Composition — dropout catalogued in M055 failure modes | cross-ref M055 | F07099 | non-negotiable | false | 10 |
| R14153 | Composition — composes with M060 cockpit | cross-ref M060 | F07100 | non-negotiable | false | 10 |
| R14154 | Composition — composes with selfdef MS044 guardian daemon | cross-ref selfdef MS044 | F07101 | non-negotiable | false | 10 |
| R14155 | Composition — composes with selfdef MS047 perimeter engine | cross-ref selfdef MS047 | F07102 | non-negotiable | false | 10 |
| R14156 | Composition — composes with selfdef MS038 network boundary | cross-ref selfdef MS038 | F07103 | non-negotiable | false | 10 |
| R14157 | Composition — composes with selfdef MS012 perimeter coexistence | cross-ref selfdef MS012 | F07104 | non-negotiable | false | 10 |
| R14158 | Boundary — sovereign-os observes; OPNsense enforces | dump 456 + R10212 | F07105 | non-negotiable | false | 10 |
| R14159 | Boundary — sovereign-os never mutates firewall state | R10212 | F07106 | non-negotiable | false | 10 |
| R14160 | Boundary — info-hub indexes the topology read-only | operator standing direction | F07107 | non-negotiable | false | 10 |
| R14161 | Doctrine — "physically segregated at the hardware boundary" never paraphrased | dump 456 | F07108 | non-negotiable | false | 10 |
| R14162 | Doctrine — gotcha sentence preserved verbatim wherever cited | dump 764 | F07109 | non-negotiable | false | 10 |
| R14163 | Doctrine — prevention sentence preserved verbatim wherever cited | dump 765 | F07110 | non-negotiable | false | 10 |
| R14164 | Doctrine — unit comments cite the dump prevention | commit 47632d0 | F07111 | non-negotiable | false | 10 |
| R14165 | Doctrine — verbatim quotes never paraphrased | operator standing direction | F07109 | non-negotiable | false | 10 |
| R14166 | Tests — unit-text lint asserts BindsTo presence (hardware-free) | repo test discipline | F07112 | non-negotiable | false | 10 |
| R14167 | Tests — EOF path covered via stream-close simulation | repo test discipline | F07113 | non-negotiable | false | 10 |
| R14168 | Tests — bidir gate keeps ExecStart ↔ script ↔ socket path consistent | repo gate discipline | F07120 | non-negotiable | false | 10 |
| R14169 | Performance — perimeter-blind window ≤ 2s under dropout (RestartSec=1 + bind) | unit + architecture | F07114 | non-negotiable | false | 10 |
| R14170 | Performance — reconfig events never crash observer surfaces | E11.M8 + architecture | F07115 | non-negotiable | false | 10 |
| R14171 | Operator UX — "is the firewall reachable?" answered by one verb | E11.M8 / R486 | F07116 | non-negotiable | false | 10 |
| R14172 | Operator UX — blind-window question answerable from journal + metrics | architecture | F07117 | non-negotiable | false | 10 |
| R14173 | Operator UX — VLAN contract readable as one table | dump 460-475 | F07118 | non-negotiable | false | 10 |
| R14174 | Reproducibility — dropout-recovery cycles recorded for replay | cross-ref selfdef MS009 | F07119 | non-negotiable | false | 10 |
| R14175 | Audit lineage — 2026-06 audit gap #3 closed by this milestone | audit verbatim | F07121 | non-negotiable | false | 10 |
| R14176 | Audit lineage — M003 VLAN concept extended to the firewall-interface contract | audit verbatim + cross-ref M003 | F07122 | non-negotiable | false | 10 |
| R14177 | Closing — covers dump 420-424 verbatim scope | dump 420-424 | F07123 | non-negotiable | false | 10 |
| R14178 | Closing — covers dump 456-475 verbatim scope | dump 456-475 | F07123 | non-negotiable | false | 10 |
| R14179 | Closing — covers dump 761-765 verbatim scope | dump 761-765 | F07123 | non-negotiable | false | 10 |
| R14180 | Closing — prevention shipped; boundary observation linked to E11.M8 | commit 47632d0 + E11.M8 | F07124 | non-negotiable | false | 10 |
| R14181 | Closing — reconfig-detector explicitly pending (no false "done") | architecture + operator standing constraint | F07125 | non-negotiable | false | 10 |
| R14182 | Closing — dropout-metrics explicitly pending | architecture | F07125 | non-negotiable | false | 10 |
| R14183 | Closing — flap alert explicitly pending | architecture | F07125 | non-negotiable | false | 10 |
| R14184 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F07041 | non-negotiable | false | 10 |
| R14185 | Closing — sovereignty preserved (perimeter local; no cloud dependency) | operator standing direction | F07105 | non-negotiable | false | 10 |
| R14186 | Closing — boundary respected (sovereign-os observes; selfdef + OPNsense enforce) | operator standing direction | F07105 | non-negotiable | false | 10 |
| R14187 | Closing — cross-repo binding only through MS007 typed mirrors | cross-ref selfdef MS007 | F07086 | non-negotiable | false | 10 |
| R14188 | Closing — "Do not minimize" upheld (full boundary catalog with 170 R-rows) | operator standing direction | F07041 | non-negotiable | false | 10 |
| R14189 | Closing — M084 closes audit gap #3; sovereign-os catalog at 82 milestones | audit verbatim + architecture | F07121 | non-negotiable | false | 10 |
| R14190 | Drill — dropout simulation drill documented (stop tetragon; observe bind-stop + restart) | architecture + dump 765 | F07113 | non-negotiable | false | 10 |
| R14191 | Drill — drill verifies the journal carries the [EOF] evidence when stream dies first | commit 47632d0 | F07069 | non-negotiable | false | 10 |
| R14192 | Drill — drill verifies no stale guardian process survives a tetragon stop | dump 765 + unit | F07060 | non-negotiable | false | 10 |
| R14193 | Drill — drill repeatable without hardware (nspawn-style) | repo test discipline | F07112 | non-negotiable | false | 10 |
| R14194 | Contract — VLAN 100 ↔ VLAN 200 isolation never bridged by sovereign-os config | dump 460-475 | F07044 | non-negotiable | false | 10 |
| R14195 | Contract — Tetragon log streams stay on the management plane (VLAN 100) | dump 460-475 | F07051 | non-negotiable | false | 10 |
| R14196 | Contract — model pulls stay on the data plane (VLAN 200, NAS-only) | dump 460-475 | F07054 | non-negotiable | false | 10 |
| R14197 | Contract — container bridge remains isolated from the management plane | dump 460-475 | F07053 | non-negotiable | false | 10 |
| R14198 | Contract — any cross-plane flow is an explicit operator decision, never a default | dump 456 + architecture | F07044 | non-negotiable | false | 10 |
| R14199 | Doc — deployment guide documents the dual-NIC + VLAN contract when boundary ships | repo doc discipline | F07118 | non-negotiable | false | 10 |
| R14200 | Doc — runbook documents the dropout drill + expected journal evidence | repo doc discipline | F07113 | non-negotiable | false | 10 |
| R14201 | Resilience — guardian survives OPNsense reboot cycles (bind-restart per cycle) | dump 762-765 | F07064 | non-negotiable | false | 10 |
| R14202 | Resilience — repeated lease drops degrade to paging, never to silent blindness | dump 764 + architecture | F07083 | non-negotiable | false | 10 |
| R14203 | Resilience — socket re-appearance is picked up by the restarted loop without manual action | dump 765 + unit | F07064 | non-negotiable | false | 10 |
| R14204 | Resilience — guardian start refuses cleanly when socket absent (structural-friction message) | guardian script | F07068 | non-negotiable | false | 10 |
| R14205 | Observability — restart reason distinguishable in journal: EOF vs OSError vs operator stop | commit 47632d0 + script | F07094 | non-negotiable | false | 10 |
| R14206 | Observability — blind-window metrics consumable by the four-watchdog rollup | cross-ref MS027 four-watchdog | F07081 | non-negotiable | false | 10 |
| R14207 | Observability — network-edge watch verb streams reconfig-relevant state | E11.M8 / R486 | F07076 | non-negotiable | false | 10 |
| R14208 | Security — dropout window cannot be exploited silently (restart + journal + page) | dump 764 + architecture | F07082 | non-negotiable | false | 10 |
| R14209 | Security — guardian hardening (R171 posture) not weakened by resilience additions | unit + R171 gate | F07067 | non-negotiable | false | 10 |
| R14210 | Security — no new privileges introduced by the binding controls | unit | F07067 | non-negotiable | false | 10 |
| R14211 | Scheduler — M058 may consult perimeter state before placing network-touching jobs | cross-ref M058 + architecture | F07096 | non-negotiable | false | 10 |
| R14212 | Portfolio — model pulls honor the VLAN 200 NAS-only rule regardless of model source | dump 460-475 + cross-ref M017 | F07054 | non-negotiable | false | 10 |
| R14213 | Gateway — sovereign-gatewayd binds loopback by default; boundary exposure is an explicit override | gatewayd README + dump 456 | F07105 | non-negotiable | false | 10 |
| R14214 | Gateway — never-cloud-spill invariant complements the no-outbound-WAN data-plane rule | gatewayd + dump 460-475 | F07055 | non-negotiable | false | 10 |
| R14215 | Docs — master-spec § 8 topology diagram preserved verbatim in the spec | dump 460-475 + master spec | F07118 | non-negotiable | false | 10 |
| R14216 | Docs — SDD authored before any reconfig-detector implementation (SDD-first discipline) | repo SDD discipline | F07125 | non-negotiable | false | 10 |
| R14217 | Tests — VLAN-contract lint asserts the role table stays in lockstep with the spec | repo gate discipline | F07118 | non-negotiable | false | 10 |
| R14218 | Tests — alert-runbook anchors for new boundary alerts resolve (anchor-coverage gate) | repo gate discipline | F07082 | non-negotiable | false | 10 |
| R14219 | Tests — dashboard panels for boundary metrics pass the json-valid gate | repo gate discipline | F07084 | non-negotiable | false | 10 |
| R14220 | Tests — typed-mirror schema covered by MS007 saturation tests | cross-ref selfdef MS007 | F07086 | non-negotiable | false | 10 |
| R14221 | Rollout — boundary contract activates per-profile (sain-01 first) | profiles discipline | F07118 | non-negotiable | false | 10 |
| R14222 | Rollout — non-sain-01 profiles degrade gracefully (single-NIC hosts skip the contract) | profiles discipline + architecture | F07115 | non-negotiable | false | 10 |
| R14223 | Rollout — profile validation rejects contradictory NIC-role declarations | profiles discipline | F07087 | non-negotiable | false | 10 |
| R14224 | Telemetry — reachability-tier transitions emitted as events | E11.M8 + cross-ref M049 | F07072 | non-negotiable | false | 10 |
| R14225 | Telemetry — tier-transition history retained for trend analysis | architecture | F07084 | non-negotiable | false | 10 |
| R14226 | Telemetry — EOF/restart counters exposed via the existing auditor metric family | script metrics + architecture | F07080 | non-negotiable | false | 10 |
| R14227 | Quality — no fabricated OPNsense API claims; capabilities verb reports observed truth | E11.M8 + operator standing direction | F07073 | non-negotiable | false | 10 |
| R14228 | Quality — unreachable firewall reported as unavailable, never assumed | E11.M8 | F07072 | non-negotiable | false | 10 |
| R14229 | Quality — boundary docs distinguish OBSERVED (live) vs DECLARED (spec) state | P4 discipline | F07118 | non-negotiable | false | 10 |
| R14230 | Closing — gotcha + prevention pair is the template for future infra-interface gotchas | dump 761-765 + architecture | F07109 | non-negotiable | false | 10 |
| R14231 | Closing — every future boundary change re-runs the dropout drill | architecture | F07113 | non-negotiable | false | 10 |
| R14232 | Closing — boundary contract reviewed when OPNsense major versions change | architecture | F07071 | non-negotiable | false | 10 |
| R14233 | Closing — SD-WAN path changes (new ISP, new tunnel) re-validate the lease-drop behavior | dump 762 + architecture | F07077 | non-negotiable | false | 10 |
| R14234 | Closing — NIC replacement re-validates the role map (typed mirror bump) | architecture + MS007 | F07086 | non-negotiable | false | 10 |
| R14235 | Closing — the guardian loop is the canonical consumer; new socket consumers inherit the EOF rule | dump 765 + architecture | F07068 | non-negotiable | false | 10 |
| R14236 | Closing — telemetry probes (sovereign-telemetry) remain management-plane citizens | dump 460-475 + cross-ref M045 | F07051 | non-negotiable | false | 10 |
| R14237 | Closing — gatewayd remains loopback/management-plane; data-plane exposure forbidden by default | gatewayd + dump 460-475 | F07105 | non-negotiable | false | 10 |
| R14238 | Closing — info-hub second-brain entry links paper-trail: dump → milestone → commit | operator standing direction | F07107 | non-negotiable | false | 10 |
| R14239 | Closing — audit gaps #1 (wiki-side) noted as out-of-repo; #2 (M083) + #3 (M084) closed here | audit verbatim | F07121 | non-negotiable | false | 10 |
| R14240 | Closing — catalog lockstep updated (INDEX, MASTER-PLAN, SHIPPED, gate literal) | repo gate discipline | F07121 | non-negotiable | false | 10 |
| R14241 | Closing — milestone internally consistent (contiguous IDs, no dangling feature refs) | repo discipline | F07123 | non-negotiable | false | 10 |
| R14242 | Closing — verbatim anchors quoted, never summarized | operator standing direction | F07109 | non-negotiable | false | 10 |
| R14243 | Closing — implementation preceded cataloguing for the prevention (build-first evidence) | commit 47632d0 | F07124 | non-negotiable | false | 10 |
| R14244 | Closing — remaining pendings carry explicit owners-by-default (operator decides order) | operator standing direction | F07125 | non-negotiable | false | 10 |
| R14245 | Closing — no scope minimization: full dual-NIC + firewall + dropout scope catalogued | operator standing direction | F07041 | non-negotiable | false | 10 |
| R14246 | Closing — boundary contract composable with future OPNsense API automation (read-only) | E11.M8 + architecture | F07073 | non-negotiable | false | 10 |
| R14247 | Closing — drill + contract docs land in the deployment guide on implementation | repo doc discipline | F07118 | non-negotiable | false | 10 |
| R14248 | Closing — perimeter-blind metrics join the four-watchdog rollup on implementation | cross-ref MS027 | F07081 | non-negotiable | false | 10 |
| R14249 | Closing — this milestone is the infra-interface sibling of M083 (both audit closures) | audit verbatim | F07121 | non-negotiable | false | 10 |
| R14250 | Closing — sovereign-os catalog at 82 milestones / 14,080 R-rows after M084 | architecture | F07121 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M084.

## Cross-references

- **M003** — hardware topology + PCIe lane discipline (the VLAN concept this contract extends)
- **M013** — observability as control input
- **M045** — Linux as intelligence governor (systemd/PSI machinery)
- **M049** — observability + trace pipeline
- **M055** — failure modes (dropout catalogued)
- **M058** — Goldilocks scheduler (perimeter-state consultation)
- **M060** — cockpit + dashboards (network-edge + guardian panels)
- **E11.M8 / R486** — network-edge module (detect / opnsense_status / opnsense_capabilities / interfaces / nat_chain / watch; reachability ladder)
- **selfdef MS007** — typed-mirror crate scheme
- **selfdef MS009** — replay validator
- **selfdef MS012** — perimeter coexistence
- **selfdef MS026** — observability + OCSF
- **selfdef MS038** — network boundary
- **selfdef MS044** — Guardian Daemon (the protected loop)
- **selfdef MS047** — Real-Time Security Perimeter Engine
- **commit 47632d0** — the shipped dropout prevention (BindsTo + EOF nonzero exit)

## Schema

```
schema_version: "1.0.0"
milestone_id: M084
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump: 2026-05-15-sain-01-master-spec-other-conversation-transposition.md
source_dump_lines: 420-424 + 456-475 + 761-765
nic_roles:
  intel_i226v_2_5gbe: {vlan: 100, plane: management-telemetry, carries: [host-ssh, tetragon-log-streams, system-updates]}
  marvell_aqc113c_10gbe: {vlan: 200, plane: model-ingestion-storage, carries: [isolated-container-bridge, model-weight-pulls-nas], outbound_wan: forbidden}
gotcha: "OPNsense WAN/LAN Bridging and Tetragon Interface Dropouts (dump 761-765)"
prevention:
  binds_to: tetragon.service        # shipped 47632d0
  eof_restart: nonzero-exit + Restart=always   # shipped 47632d0
catalog_status:
  sovereign_os: 82 milestones
  selfdef: 48 milestones
  combined: 130 milestones
```
