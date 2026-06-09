//! `sovereign-gatewayd` — the first persistent runnable service: it promotes
//! the one-shot `sovereign-cortex` engine into a long-lived **daemon** behind
//! the M048 Module 4 [`sovereign_gateway`] contract.
//!
//! Doctrine verbatim (from [`sovereign_gateway`]):
//!
//! > "Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router"
//!
//! What makes this a *service* rather than a CLI:
//!
//! * **Stateful memory that learns across requests.** The daemon owns one
//!   [`Cortex`] for the whole process. Every committed decision is admitted
//!   back into Memory-OS via [`Cortex::act_and_learn`] (M016 learning without
//!   retraining), so later requests on the same topic recall it and the value
//!   plane judges them more confidently. A fresh CLI invocation cannot do this.
//! * **Long-running hygiene.** [`GatewayServer::maintain`] ages out stale
//!   memory (M028 decay) the way a CLI never needs to.
//! * **A live cost/route ledger** (gateway surface 6) accumulated over the
//!   process lifetime, and the **never-cloud-spill** safety invariant tracked
//!   as a process-level tripwire.
//!
//! The wire protocol is newline-delimited JSON (NDJSON): each line is one
//! [`GatewayRequest`]; the reply is one line of [`GatewayResponse`]. This is
//! transport-agnostic — the `main` binary speaks it over TCP, over stdio, or
//! against the built-in demo session.
//!
//! Standing rule (from the gateway crate): we do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod http;

use std::collections::BTreeMap;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

use sovereign_cortex::{Cortex, CortexRequest, Deliberation, seed_memory};
use sovereign_gateway::{GatewayManifest, GatewaySurface, SCHEMA_VERSION, SurfaceState};
use sovereign_router_7axis::{Complexity, TaskAxes};
use sovereign_srp_scheduler::{Precision, RolePressure, Workload, WorkloadClass};
use sovereign_value_plane::{IntelligenceTier, NextAction, RewardVector};

/// A simplified client request: the client supplies the task descriptor (the
/// 7-axis `axes`) and an explicit quality intent, and the gateway fills the
/// runtime-state and engine-internal fields a `CortexRequest` needs. The full
/// [`CortexRequest`] path remains for clients that want full control — this is
/// an additive convenience so a simple client need not know the engine internals.
///
/// The fill-in defaults are deliberately conservative and **operator-tunable**:
/// runtime pressures default to idle (the daemon has no live telemetry, so it
/// assumes capacity), the cloud is never allowed (sovereign default), and the
/// workload/precision are derived mechanically from the task's complexity. The
/// reward is derived from the client's own `expected_quality` dial — the gateway
/// invents no hidden quality policy.
#[derive(Debug, Clone, Deserialize)]
pub struct SimpleRequest {
    /// The 7-axis task descriptor (the task's nature) — the client's domain.
    pub axes: TaskAxes,
    /// Topic bitset for memory recall (default 0 = no topic).
    #[serde(default)]
    pub query_topic: u64,
    /// Value-plane critic profile (`fast`/`careful`/…); defaults to `careful`.
    #[serde(default)]
    pub profile: Option<String>,
    /// Expected/desired answer quality, 0.0..=1.0 (default 0.7). The client's
    /// quality dial — mapped transparently onto the reward vector.
    #[serde(default)]
    pub expected_quality: Option<f32>,
}

impl SimpleRequest {
    /// Map to a full [`CortexRequest`], filling runtime-state defaults (idle,
    /// local-only) and deriving the workload + reward from the task + quality.
    pub fn into_cortex(self) -> CortexRequest {
        let quality = self.expected_quality.unwrap_or(0.7).clamp(0.0, 1.0);
        // Workload class + precision follow the task's complexity (the same
        // split the 7-axis router uses): simple → CPU-side, complex → GPU-side.
        let (class, precision) = match self.axes.complexity {
            Complexity::Simple => (WorkloadClass::IntentEval, Precision::Ternary),
            Complexity::Complex => (WorkloadClass::DeepReason, Precision::Fp16),
        };
        CortexRequest {
            axes: self.axes,
            workload: Workload {
                class,
                precision,
                context_tokens: 4096,
                // No hard VRAM floor — don't over-constrain placement; the role
                // (from the axes) drives where the work lands.
                min_vram_gb: 0,
            },
            // No live telemetry → assume capacity is free on every role.
            conductor: RolePressure::free(),
            logic: RolePressure::free(),
            oracle: RolePressure::free(),
            allow_cloud: false,
            query_topic: self.query_topic,
            query_entity: 0,
            now: 0,
            half_life: 64,
            reward: reward_from_quality(quality),
            profile: self.profile.unwrap_or_else(|| "careful".into()),
            // Footprint estimate only; a mid-size default.
            model_params: 7_000_000_000,
            available_adapters: Vec::new(),
            stacking_supported: false,
            query_embedding: Vec::new(),
        }
    }
}

/// Map a single quality intent (0.0..=1.0) onto the value-plane reward axes:
/// the quality/competence axes track it; the inverted axes (risk/latency/cost)
/// default low. Transparent and operator-tunable — no hidden quality policy.
fn reward_from_quality(q: f32) -> RewardVector {
    RewardVector {
        correctness: q,
        evidence: q,
        schema_validity: 1.0,
        tool_success: q,
        test_success: q,
        risk: 0.1,
        latency: 0.2,
        cost: 0.2,
        novelty: 0.5,
        user_preference: q,
        cache_reuse: 0.5,
        confidence_calibration: q,
    }
}

/// One request on the wire. Tagged by `op`, so a client sends e.g.
/// `{"op":"infer","request":{…}}` or `{"op":"health"}`.
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "op", rename_all = "kebab-case")]
pub enum GatewayRequest {
    /// Run one request through the cortex engine (gateway surface 1/3/4 —
    /// Anthropic Messages / MCP bridge / Claude Code all land here).
    Infer {
        /// The end-to-end cortex request. Boxed because it is large.
        request: Box<CortexRequest>,
    },
    /// Run a simplified request: the client supplies only the task axes + a
    /// quality intent; the gateway fills the engine-internal fields (see
    /// [`SimpleRequest`]) and runs it like [`Self::Infer`].
    SimpleInfer {
        /// The simplified request.
        request: SimpleRequest,
    },
    /// Dry-run a request and return the plain-language rationale (M015
    /// human-gate) — read-only: the engine decides but does not learn or
    /// account, so an auditor can ask "what would you do, and why" safely.
    Explain {
        /// The end-to-end cortex request. Boxed because it is large.
        request: Box<CortexRequest>,
    },
    /// Best-of-N deliberation (read-only): the client supplies candidate reward
    /// vectors and a compute tier; the engine forks one branch per candidate
    /// and returns the winner + every assessment. The premium decision path.
    Deliberate {
        /// The shared end-to-end request. Boxed because it is large.
        request: Box<CortexRequest>,
        /// One candidate branch per reward vector (the N of best-of-N).
        candidates: Vec<RewardVector>,
        /// How much compute to spend (fanout budget): `reflex` … `experimental`.
        tier: IntelligenceTier,
    },
    /// Return the 6-surface gateway manifest.
    Manifest,
    /// Return liveness + the never-cloud-spill invariant state.
    Health,
    /// Return the accumulated cost/route ledger (gateway surface 6).
    Ledger,
}

/// One reply on the wire. Tagged by `kind`. Output-only: it embeds the
/// `Serialize`-only [`sovereign_cortex::CortexDecision`], so it is never
/// deserialized back.
#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum GatewayResponse {
    /// A cortex decision plus whether it was learned back into memory.
    Decision {
        /// The auditable decision.
        decision: Box<sovereign_cortex::CortexDecision>,
        /// Whether the committed decision was admitted into Memory-OS.
        learned: bool,
    },
    /// The plain-language rationale for a dry-run request (read-only).
    Explanation {
        /// The M015 human-gate rationale (route → device → verdict → cost).
        explanation: String,
    },
    /// A best-of-N deliberation result (read-only). Output-only: it embeds the
    /// `Serialize`-only `Deliberation`, so it is never deserialized back.
    Deliberation {
        /// The winner + every candidate assessment + the branch tree.
        deliberation: Box<Deliberation>,
    },
    /// The gateway manifest.
    Manifest {
        /// The 6-surface manifest.
        manifest: GatewayManifest,
    },
    /// Daemon health.
    Health {
        /// The health snapshot.
        health: Health,
    },
    /// The cost/route ledger.
    Ledger {
        /// The ledger snapshot.
        ledger: Ledger,
    },
    /// A request that could not be parsed or that the engine refused.
    Error {
        /// Human-readable reason.
        message: String,
    },
}

/// Accumulated cost/route ledger — gateway responsibility 1 (Cost) + 7
/// (Tracing), surfaced as surface 6 (CostRouteLedger).
#[derive(Debug, Clone, Default, Serialize)]
pub struct Ledger {
    /// Total inference requests handled.
    pub total_requests: u64,
    /// Decisions whose verdict was Commit.
    pub committed: u64,
    /// Requests the engine refused (route/placement/profile error).
    pub refused: u64,
    /// Decisions that were learned back into memory.
    pub learned: u64,
    /// Route distribution, keyed by SRP role (`conductor`/`logic`/`oracle`/`cloud`).
    pub by_role: BTreeMap<String, u64>,
    /// Decisions that spilled to the cloud expert plane. MUST stay 0 while
    /// `force_local` is set — it is the never-cloud-spill tripwire.
    pub cloud_spills: u64,
    /// Decisions that carried a World-Model prior (M030) — i.e. the
    /// `(topic, role)` pair had resolved before. Cold pairs don't count.
    pub predictions: u64,
    /// Of those, how many had the learned prior agree with the live verdict.
    /// The ratio is how well the engine is learning its own dynamics.
    pub prediction_agreements: u64,
    /// Read-only ops handled (`explain` + `deliberate`). Counted for request-mix
    /// observability; the decision-ledger fields above and the engine's learned
    /// state are untouched by these ops — the auditor guarantee still holds.
    pub dry_runs: u64,
}

/// Daemon health snapshot.
#[derive(Debug, Clone, Serialize)]
pub struct Health {
    /// Gateway contract schema version.
    pub schema_version: &'static str,
    /// Number of surfaces currently `Live`.
    pub live_surfaces: usize,
    /// Whether the daemon forces every request local (Privacy/Routing policy).
    pub force_local: bool,
    /// Total inference requests handled so far.
    pub total_requests: u64,
    /// Cloud spills observed (see [`Ledger::cloud_spills`]).
    pub cloud_spills: u64,
    /// The headline safety invariant: `cloud_spills == 0`.
    pub never_cloud_spill_holds: bool,
}

/// The persistent gateway service. Owns one [`Cortex`] (the engine) and one
/// [`Ledger`] (the cost/route surface) for the whole process, behind the
/// [`sovereign_gateway`] manifest contract.
pub struct GatewayServer {
    cortex: Mutex<Cortex>,
    ledger: Mutex<Ledger>,
    manifest: GatewayManifest,
    /// When set, every request is forced local (`allow_cloud = false`) before
    /// it reaches the router — the gateway owning Privacy + Routing on the
    /// client's behalf (the doctrine: the client never holds provider keys).
    force_local: bool,
}

impl GatewayServer {
    /// A sovereign-by-default daemon: memory seeded for recall, every request
    /// forced local. The inference surfaces (Anthropic Messages / MCP bridge /
    /// Claude Code) and the ledger surface are marked `Live`.
    pub fn new() -> Self {
        Self::with_force_local(true)
    }

    /// Build with an explicit local-only policy. `force_local = false` lets a
    /// request opt into cloud spill via its own `allow_cloud` flag — only for
    /// non-sovereign deployments.
    pub fn with_force_local(force_local: bool) -> Self {
        let cortex = Cortex::with_memory(seed_memory());
        let mut manifest = GatewayManifest::empty_canonical();
        for record in &mut manifest.surfaces {
            // The surfaces this daemon actually answers route into the engine
            // (or expose the ledger); the rest stay Disabled until built.
            record.state = match record.surface {
                GatewaySurface::AnthropicMessages
                | GatewaySurface::McpBridge
                | GatewaySurface::ClaudeCode
                | GatewaySurface::CostRouteLedger => SurfaceState::Live,
                _ => SurfaceState::Disabled,
            };
        }
        Self {
            cortex: Mutex::new(cortex),
            ledger: Mutex::new(Ledger::default()),
            manifest,
            force_local,
        }
    }

    /// Handle one NDJSON line and return one NDJSON line of response. Never
    /// panics and never returns invalid JSON — a parse failure becomes an
    /// `Error` response.
    pub fn handle_line(&self, line: &str) -> String {
        let response = match serde_json::from_str::<GatewayRequest>(line.trim()) {
            Ok(req) => self.handle(req),
            Err(e) => GatewayResponse::Error {
                message: format!("malformed request: {e}"),
            },
        };
        serde_json::to_string(&response).unwrap_or_else(|e| {
            format!("{{\"kind\":\"error\",\"message\":\"response serialize failed: {e}\"}}")
        })
    }

    /// Dispatch one typed request to a typed response. Transport-agnostic: the
    /// NDJSON line protocol ([`Self::handle_line`]) and the HTTP surface
    /// ([`crate::http`]) both route through here, so they can never diverge.
    pub fn handle(&self, req: GatewayRequest) -> GatewayResponse {
        match req {
            GatewayRequest::Infer { request } => self.infer(*request),
            GatewayRequest::SimpleInfer { request } => self.infer(request.into_cortex()),
            GatewayRequest::Explain { request } => self.explain(*request),
            GatewayRequest::Deliberate {
                request,
                candidates,
                tier,
            } => self.deliberate(*request, candidates, tier),
            GatewayRequest::Manifest => GatewayResponse::Manifest {
                manifest: self.manifest.clone(),
            },
            GatewayRequest::Health => GatewayResponse::Health {
                health: self.health(),
            },
            GatewayRequest::Ledger => GatewayResponse::Ledger {
                ledger: self.ledger.lock().expect("ledger poisoned").clone(),
            },
        }
    }

    /// Dry-run a request: decide and explain, but do **not** learn or touch the
    /// ledger. `tick` is read-only, so this is a side-effect-free "what would
    /// you do, and why" for an auditor. The same Privacy policy applies.
    fn explain(&self, mut request: CortexRequest) -> GatewayResponse {
        if self.force_local {
            request.allow_cloud = false;
        }
        let result = {
            let cortex = self.cortex.lock().expect("cortex poisoned");
            cortex.tick(&request)
        };
        self.ledger.lock().expect("ledger poisoned").dry_runs += 1;
        match result {
            Ok(decision) => GatewayResponse::Explanation {
                explanation: decision.explain(),
            },
            Err(e) => GatewayResponse::Error {
                message: e.to_string(),
            },
        }
    }

    /// Best-of-N deliberation (read-only): fork one branch per candidate at the
    /// requested compute tier and return the winner + all assessments. Like
    /// `explain`, it decides without learning or touching the ledger. The same
    /// Privacy policy applies.
    fn deliberate(
        &self,
        mut request: CortexRequest,
        candidates: Vec<RewardVector>,
        tier: IntelligenceTier,
    ) -> GatewayResponse {
        if self.force_local {
            request.allow_cloud = false;
        }
        let result = {
            let cortex = self.cortex.lock().expect("cortex poisoned");
            cortex.deliberate(&request, &candidates, tier)
        };
        self.ledger.lock().expect("ledger poisoned").dry_runs += 1;
        match result {
            Ok(deliberation) => GatewayResponse::Deliberation {
                deliberation: Box::new(deliberation),
            },
            Err(e) => GatewayResponse::Error {
                message: e.to_string(),
            },
        }
    }

    /// The core: force policy, run the engine, learn, account, answer.
    fn infer(&self, mut request: CortexRequest) -> GatewayResponse {
        // Gateway owns Privacy + Routing: a sovereign daemon never lets a
        // request reach across to the cloud, whatever the client asked.
        if self.force_local {
            request.allow_cloud = false;
        }

        let result = {
            let mut cortex = self.cortex.lock().expect("cortex poisoned");
            cortex.act_and_learn(&request)
        };

        match result {
            Ok((decision, _cycle, learned)) => {
                let mut ledger = self.ledger.lock().expect("ledger poisoned");
                ledger.total_requests += 1;
                let role_key = role_key(&decision.route.role);
                *ledger.by_role.entry(role_key).or_insert(0) += 1;
                if decision.assessment.suggested_next_action == NextAction::Commit {
                    ledger.committed += 1;
                }
                if learned {
                    ledger.learned += 1;
                }
                if decision.placement.spilled_to_cloud {
                    // Tripwire: under force_local this must be unreachable.
                    ledger.cloud_spills += 1;
                }
                if let Some(prediction) = &decision.prediction {
                    // The engine carried a learned World-Model prior (M030).
                    ledger.predictions += 1;
                    if prediction.agrees_with_verdict {
                        ledger.prediction_agreements += 1;
                    }
                }
                GatewayResponse::Decision {
                    decision: Box::new(decision),
                    learned,
                }
            }
            Err(e) => {
                let mut ledger = self.ledger.lock().expect("ledger poisoned");
                ledger.total_requests += 1;
                ledger.refused += 1;
                GatewayResponse::Error {
                    message: e.to_string(),
                }
            }
        }
    }

    /// Long-running memory hygiene (M028 decay): age out memories older than
    /// `ttl` ticks relative to `now`. Returns how many were aged. A daemon
    /// calls this periodically; a CLI never needs to.
    pub fn maintain(&self, now: u64, ttl: u64) -> usize {
        let mut cortex = self.cortex.lock().expect("cortex poisoned");
        cortex.maintain(now, ttl)
    }

    /// Current health snapshot, including the never-cloud-spill invariant.
    pub fn health(&self) -> Health {
        let ledger = self.ledger.lock().expect("ledger poisoned");
        Health {
            schema_version: SCHEMA_VERSION,
            live_surfaces: self.manifest.live_count(),
            force_local: self.force_local,
            total_requests: ledger.total_requests,
            cloud_spills: ledger.cloud_spills,
            never_cloud_spill_holds: ledger.cloud_spills == 0,
        }
    }

    /// The gateway manifest this daemon serves.
    pub fn manifest(&self) -> &GatewayManifest {
        &self.manifest
    }

    /// Render the live ledger + health as Prometheus text-exposition, so the
    /// existing cockpit (node_exporter scrape → Grafana) can chart the daemon
    /// without a new pipeline. Mirrors the metric style of `sovereign-telemetry`.
    pub fn metrics_prometheus(&self) -> String {
        let ledger = self.ledger.lock().expect("ledger poisoned").clone();
        let mut s = String::new();

        s.push_str(
            "# HELP sovereign_gateway_requests_total Inference requests handled by the gateway.\n",
        );
        s.push_str("# TYPE sovereign_gateway_requests_total counter\n");
        s.push_str(&format!(
            "sovereign_gateway_requests_total {}\n",
            ledger.total_requests
        ));

        s.push_str("# HELP sovereign_gateway_decisions_total Decisions by terminal disposition.\n");
        s.push_str("# TYPE sovereign_gateway_decisions_total counter\n");
        for (disposition, value) in [
            ("committed", ledger.committed),
            ("refused", ledger.refused),
            ("learned", ledger.learned),
        ] {
            s.push_str(&format!(
                "sovereign_gateway_decisions_total{{disposition=\"{disposition}\"}} {value}\n"
            ));
        }

        s.push_str("# HELP sovereign_gateway_route_total Decisions routed to each SRP role.\n");
        s.push_str("# TYPE sovereign_gateway_route_total counter\n");
        for (role, value) in &ledger.by_role {
            s.push_str(&format!(
                "sovereign_gateway_route_total{{role=\"{role}\"}} {value}\n"
            ));
        }

        s.push_str(
            "# HELP sovereign_gateway_cloud_spills_total Decisions that spilled to the cloud plane (must stay 0 under force-local).\n",
        );
        s.push_str("# TYPE sovereign_gateway_cloud_spills_total counter\n");
        s.push_str(&format!(
            "sovereign_gateway_cloud_spills_total {}\n",
            ledger.cloud_spills
        ));

        s.push_str("# HELP sovereign_gateway_never_cloud_spill_holds 1 while the never-cloud-spill invariant holds.\n");
        s.push_str("# TYPE sovereign_gateway_never_cloud_spill_holds gauge\n");
        s.push_str(&format!(
            "sovereign_gateway_never_cloud_spill_holds {}\n",
            u8::from(ledger.cloud_spills == 0)
        ));

        s.push_str("# HELP sovereign_gateway_live_surfaces Gateway surfaces currently Live.\n");
        s.push_str("# TYPE sovereign_gateway_live_surfaces gauge\n");
        s.push_str(&format!(
            "sovereign_gateway_live_surfaces {}\n",
            self.manifest.live_count()
        ));

        s.push_str(
            "# HELP sovereign_gateway_dry_runs_total Read-only ops (explain + deliberate) handled.\n",
        );
        s.push_str("# TYPE sovereign_gateway_dry_runs_total counter\n");
        s.push_str(&format!(
            "sovereign_gateway_dry_runs_total {}\n",
            ledger.dry_runs
        ));

        s.push_str(
            "# HELP sovereign_gateway_prediction_total Decisions that carried a World-Model prior (M030).\n",
        );
        s.push_str("# TYPE sovereign_gateway_prediction_total counter\n");
        s.push_str(&format!(
            "sovereign_gateway_prediction_total {}\n",
            ledger.predictions
        ));
        s.push_str(
            "# HELP sovereign_gateway_prediction_agreements_total Priors that agreed with the live verdict.\n",
        );
        s.push_str("# TYPE sovereign_gateway_prediction_agreements_total counter\n");
        s.push_str(&format!(
            "sovereign_gateway_prediction_agreements_total {}\n",
            ledger.prediction_agreements
        ));

        s
    }
}

impl Default for GatewayServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Stable ledger key for an SRP role (`conductor`/`logic`/`oracle`/`cloud`),
/// reusing the role's own kebab-case serde form so the ledger and the decision
/// JSON agree on spelling.
fn role_key(role: &sovereign_router_7axis::SrpRole) -> String {
    serde_json::to_value(role)
        .ok()
        .and_then(|v| v.as_str().map(str::to_owned))
        .unwrap_or_else(|| format!("{role:?}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_cortex::demo_requests;

    fn infer_line(req: &CortexRequest) -> String {
        serde_json::json!({ "op": "infer", "request": req }).to_string()
    }

    #[test]
    fn malformed_line_returns_error_not_panic() {
        let s = GatewayServer::new();
        let out = s.handle_line("not json at all");
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "error");
        assert!(v["message"].as_str().unwrap().contains("malformed"));
    }

    #[test]
    fn unknown_op_is_an_error() {
        let s = GatewayServer::new();
        let out = s.handle_line(r#"{"op":"teleport"}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "error");
    }

    #[test]
    fn explain_op_is_read_only_and_returns_the_rationale() {
        let s = GatewayServer::new();
        let req = demo_requests()[0].clone();
        let line = serde_json::json!({ "op": "explain", "request": req }).to_string();
        let out = s.handle_line(&line);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "explanation");
        assert!(v["explanation"].as_str().unwrap().contains("Routed to"));
        // A dry-run must not move the decision ledger (no infer/learn happened),
        // but it is counted for request-mix observability.
        let ledger = s.ledger.lock().unwrap();
        assert_eq!(ledger.total_requests, 0);
        assert_eq!(ledger.dry_runs, 1);
    }

    #[test]
    fn simple_request_fills_conservative_defaults() {
        let demo = demo_requests()[0].clone();
        let req = SimpleRequest {
            axes: demo.axes,
            query_topic: 0,
            profile: None,
            expected_quality: None,
        }
        .into_cortex();
        assert!(!req.allow_cloud, "sovereign default: cloud disallowed");
        assert_eq!(req.profile, "careful");
        assert_eq!(req.conductor.util_percent, 0, "pressures default to idle");
        assert_eq!(req.oracle.util_percent, 0);
    }

    #[test]
    fn simple_request_maps_complexity_to_workload() {
        let demo = demo_requests()[0].clone();
        // Simple complexity → CPU-side workload (ternary).
        let mut axes = demo.axes.clone();
        axes.complexity = Complexity::Simple;
        let simple = SimpleRequest {
            axes,
            query_topic: 0,
            profile: None,
            expected_quality: Some(0.9),
        }
        .into_cortex();
        assert!(matches!(simple.workload.class, WorkloadClass::IntentEval));
        assert!(matches!(simple.workload.precision, Precision::Ternary));

        // Complex complexity → GPU-side workload (fp16).
        let mut axes = demo.axes.clone();
        axes.complexity = Complexity::Complex;
        let complex = SimpleRequest {
            axes,
            query_topic: 0,
            profile: None,
            expected_quality: Some(0.9),
        }
        .into_cortex();
        assert!(matches!(complex.workload.class, WorkloadClass::DeepReason));
        assert!(matches!(complex.workload.precision, Precision::Fp16));
    }

    #[test]
    fn simple_infer_op_maps_and_runs_the_engine() {
        let s = GatewayServer::new();
        let demo = demo_requests()[0].clone();
        let line = serde_json::json!({
            "op": "simple-infer",
            "request": { "axes": demo.axes, "expected_quality": 0.9 },
        })
        .to_string();
        let out = s.handle_line(&line);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "decision");
        assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);
        // It ran the engine (not read-only): the ledger advanced.
        assert_eq!(s.ledger.lock().unwrap().total_requests, 1);
    }

    #[test]
    fn deliberate_op_is_best_of_n_and_read_only() {
        let s = GatewayServer::new();
        let req = demo_requests()[0].clone();
        let candidates = vec![req.reward.clone(), req.reward.clone(), req.reward.clone()];
        let line = serde_json::json!({
            "op": "deliberate",
            "request": req,
            "candidates": candidates,
            "tier": "normal",
        })
        .to_string();
        let out = s.handle_line(&line);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "deliberation");
        assert_eq!(v["deliberation"]["candidates_considered"], 3);
        // Read-only: best-of-N decides but does not learn or account.
        assert_eq!(s.ledger.lock().unwrap().total_requests, 0);
    }

    #[test]
    fn manifest_op_returns_six_surfaces() {
        let s = GatewayServer::new();
        let out = s.handle_line(r#"{"op":"manifest"}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "manifest");
        assert_eq!(v["manifest"]["surfaces"].as_array().unwrap().len(), 6);
        // The doctrine must survive the round trip verbatim.
        assert!(
            v["manifest"]["doctrine"]
                .as_str()
                .unwrap()
                .contains("client → Sovereign Gateway → local/cloud/model router")
        );
    }

    #[test]
    fn infer_produces_a_decision_and_updates_the_ledger() {
        let s = GatewayServer::new();
        let req = &demo_requests()[0];
        let out = s.handle_line(&infer_line(req));
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "decision");
        // Real engine output is present and structured.
        assert!(v["decision"]["route"]["role"].is_string());
        assert!(v["decision"]["summary"].is_string());

        let ledger = s.ledger.lock().unwrap();
        assert_eq!(ledger.total_requests, 1);
        assert_eq!(ledger.cloud_spills, 0);
        assert_eq!(ledger.by_role.values().sum::<u64>(), 1);
    }

    #[test]
    fn force_local_keeps_the_never_cloud_spill_invariant() {
        // Run the whole demo session; under force_local nothing may spill.
        let s = GatewayServer::new();
        for req in demo_requests() {
            let out = s.handle_line(&infer_line(&req));
            let v: serde_json::Value = serde_json::from_str(&out).unwrap();
            assert_eq!(v["kind"], "decision");
            assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);
        }
        let h = s.health();
        assert!(h.never_cloud_spill_holds);
        assert_eq!(h.cloud_spills, 0);
    }

    #[test]
    fn force_local_overrides_a_client_that_asks_for_cloud() {
        let s = GatewayServer::new();
        let mut req = demo_requests()[0].clone();
        req.allow_cloud = true; // client tries to opt into cloud …
        let out = s.handle_line(&infer_line(&req));
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        // … the gateway forced it local, so no spill.
        assert_eq!(v["decision"]["placement"]["spilled_to_cloud"], false);
        assert_eq!(s.ledger.lock().unwrap().cloud_spills, 0);
    }

    #[test]
    fn memory_learns_across_requests() {
        // The daemon's reason to exist: a committed decision admitted on the
        // first request is recalled as evidence on a later identical one.
        let s = GatewayServer::new();
        let req = demo_requests()[0].clone();

        let first: serde_json::Value =
            serde_json::from_str(&s.handle_line(&infer_line(&req))).unwrap();
        let recalled_first = first["decision"]["recalled"].as_array().unwrap().len();

        // Replay the same request a few times; learned memory accumulates.
        for _ in 0..3 {
            let _ = s.handle_line(&infer_line(&req));
        }
        let later: serde_json::Value =
            serde_json::from_str(&s.handle_line(&infer_line(&req))).unwrap();
        let recalled_later = later["decision"]["recalled"].as_array().unwrap().len();

        assert!(
            recalled_later >= recalled_first,
            "recall should not shrink as committed memory accumulates ({recalled_first} → {recalled_later})"
        );
        assert!(s.ledger.lock().unwrap().learned >= 1);
    }

    #[test]
    fn ledger_op_reflects_handled_requests() {
        let s = GatewayServer::new();
        let req = demo_requests()[0].clone();
        let _ = s.handle_line(&infer_line(&req));
        let out = s.handle_line(r#"{"op":"ledger"}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "ledger");
        assert_eq!(v["ledger"]["total_requests"], 1);
    }

    #[test]
    fn ledger_tracks_world_model_prediction_agreement() {
        // The first request to a (topic, role) is cold (no prior); replays warm
        // the engine's World-Model (M030) so later decisions carry a prior.
        let s = GatewayServer::new();
        let req = demo_requests()[0].clone();
        for _ in 0..4 {
            let _ = s.handle_line(&infer_line(&req));
        }
        let ledger = s.ledger.lock().unwrap();
        assert!(
            ledger.predictions >= 1,
            "later requests should carry a learned prior, got {}",
            ledger.predictions
        );
        // A stable repeated request resolves the same way every time, so the
        // learned prior agrees with every verdict it was present for.
        assert_eq!(ledger.prediction_agreements, ledger.predictions);
    }

    #[test]
    fn health_op_reports_live_surfaces_and_invariant() {
        let s = GatewayServer::new();
        let out = s.handle_line(r#"{"op":"health"}"#);
        let v: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(v["kind"], "health");
        assert_eq!(v["health"]["never_cloud_spill_holds"], true);
        // 4 surfaces are wired Live (Anthropic / MCP / Claude Code / Ledger).
        assert_eq!(v["health"]["live_surfaces"], 4);
    }

    #[test]
    fn maintain_is_callable_for_long_running_hygiene() {
        let s = GatewayServer::new();
        // Learn something, then age everything out far in the future.
        let _ = s.handle_line(&infer_line(&demo_requests()[0]));
        let aged = s.maintain(u64::MAX / 2, 1);
        // It returns a count without panicking; the exact number is engine-owned.
        let _ = aged;
    }
}
