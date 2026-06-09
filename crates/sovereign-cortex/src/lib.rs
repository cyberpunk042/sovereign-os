//! `sovereign-cortex` — the first runnable assembly of the real engines.
//!
//! The runtime crates each do their own job well, but until now nothing
//! composed them: there was no binary, and the engines barely referenced
//! each other. This crate is the composition layer — one
//! [`Cortex::tick`] runs a request through the whole local intelligence
//! path and returns a single auditable decision:
//!
//! ```text
//! CortexRequest
//!   │
//!   ├─▶ router-7axis   route(axes)            → SRP role + reason
//!   ├─▶ srp-scheduler  place(workload, …)     → hardware target (capability-aware)
//!   ├─▶ memory-os      retrieve(query)        → recalled evidence
//!   │        └─ recall boosts the branch's evidence/calibration
//!   └─▶ value-plane    critic.assess(branch)  → commit / expand / prune
//!   ▼
//! CortexDecision  (role, device, recalled, assessment, summary)
//! ```
//!
//! The wiring is real, not nominal: the memory the cortex recalls
//! actually modulates the reward vector the PRM critic then judges
//! ([`Cortex::tick`] raises `evidence`/`confidence_calibration` per
//! supporting memory found), so "more relevant memory" yields a more
//! confident verdict — exactly what the Memory-OS doctrine ("memory is
//! intelligence") asks of the value plane.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod compute;

pub use compute::ComputeProfile;

use serde::{Deserialize, Serialize};
use thiserror::Error;

use sovereign_memory_os::{
    FLAG_READABLE, GroundTruth, Hit, HotMeta, MemoryStore, MemoryType, Query,
};
use sovereign_router_7axis::{RouteDecision, RouterError, TaskAxes, route};
use sovereign_srp_scheduler::{
    Placement, PlacementError, RolePressure, ScheduleRequest, Workload, place,
};
use sovereign_value_plane::{
    BranchAssessment, BranchCritic, BranchState, IntelligenceTier, RewardVector,
};

/// Schema version of the cortex request/decision surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// How many memory items the recall stage returns at most.
pub const RECALL_TOP_K: usize = 5;

/// Per-recalled-item boost applied to the branch's evidence axis before
/// the critic judges it. Recall feeds the value plane.
pub const RECALL_EVIDENCE_BOOST: f32 = 0.05;

/// One end-to-end request to the cortex. Every field is a real input to
/// one of the composed engines.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CortexRequest {
    /// 7-axis task descriptor for the router.
    pub axes: TaskAxes,
    /// Workload + hardware requirements for the scheduler.
    pub workload: Workload,
    /// Live pressure on the Conductor (CPU) role.
    pub conductor: RolePressure,
    /// Live pressure on the Logic (GPU 0) role.
    pub logic: RolePressure,
    /// Live pressure on the Oracle (GPU 1) role.
    pub oracle: RolePressure,
    /// Whether the scheduler may spill to the cloud expert plane.
    pub allow_cloud: bool,
    /// Topic bitset for the memory recall query.
    pub query_topic: u64,
    /// Entity bitset for the memory recall query.
    pub query_entity: u64,
    /// Current epoch tick (drives memory freshness decay).
    pub now: u64,
    /// Freshness half-life for the recall query.
    pub half_life: u64,
    /// Measured reward signals for the candidate branch.
    pub reward: RewardVector,
    /// Profile weighting the critic should apply (`fast`/`careful`/…).
    pub profile: String,
    /// Model size (parameters) used to estimate the on-device footprint.
    pub model_params: u64,
}

/// The cortex's single auditable decision for a request. Output-only —
/// serializes to JSON but is not deserialized (it embeds `&'static`
/// device labels from the scheduler), so it derives `Serialize` only.
#[derive(Debug, Clone, Serialize)]
pub struct CortexDecision {
    /// Router output — SRP role + reason.
    pub route: RouteDecision,
    /// Scheduler output — the hardware target the work landed on.
    pub placement: Placement,
    /// Memory recalled to support the branch (may be empty).
    pub recalled: Vec<Hit>,
    /// Value-plane critic verdict on the (recall-boosted) branch.
    pub assessment: BranchAssessment,
    /// Per-device compute profile for the placement (footprint + precision).
    pub compute: ComputeProfile,
    /// One-line human-readable trace of the whole path.
    pub summary: String,
}

/// Failures along the cortex pipeline.
#[derive(Debug, Error)]
pub enum CortexError {
    /// The router refused the request (e.g. private + cloud contradiction).
    #[error("router refused the request: {0}")]
    Route(#[from] RouterError),
    /// The scheduler could not place the workload.
    #[error("scheduler could not place the workload: {0}")]
    Placement(#[from] PlacementError),
    /// The requested critic profile is unknown.
    #[error("unknown value-plane profile: {0}")]
    UnknownProfile(String),
    /// `deliberate` was called with no candidate branches.
    #[error("deliberation requires at least one candidate branch")]
    NoCandidates,
}

/// The result of a best-of-N deliberation over several candidate branches.
/// Output-only (embeds `&'static` device labels), so `Serialize` only.
#[derive(Debug, Clone, Serialize)]
pub struct Deliberation {
    /// Router output shared by all candidates.
    pub route: RouteDecision,
    /// Placement shared by all candidates.
    pub placement: Placement,
    /// Memory recalled once for the shared context.
    pub recalled: Vec<Hit>,
    /// How many candidate branches were considered.
    pub candidates_considered: usize,
    /// The winning (highest-value, non-pruned) branch, if any survived.
    pub best: Option<BranchAssessment>,
    /// Every candidate's assessment, in input order.
    pub all: Vec<BranchAssessment>,
    /// Whether the tier's fanout budget justifies more compute on the winner.
    pub more_compute_justified: bool,
    /// Compute profile for the shared placement.
    pub compute: ComputeProfile,
    /// One-line human-readable trace.
    pub summary: String,
}

/// The cortex. Owns the memory store; stateless engines are called
/// functionally per tick.
#[derive(Debug, Default)]
pub struct Cortex {
    /// The live memory the recall stage queries.
    pub memory: MemoryStore,
}

impl Cortex {
    /// A cortex with empty memory.
    pub fn new() -> Self {
        Self::default()
    }

    /// A cortex wrapping a pre-populated memory store.
    pub fn with_memory(memory: MemoryStore) -> Self {
        Self { memory }
    }

    /// Run one request through the full pipeline.
    ///
    /// Order matters: the router decides *who* should handle it, the
    /// scheduler decides *on what hardware*, memory supplies *evidence*,
    /// and the critic — judging the evidence-boosted branch — decides
    /// *what to do*. Any engine refusing the request short-circuits into
    /// a [`CortexError`].
    pub fn tick(&self, req: &CortexRequest) -> Result<CortexDecision, CortexError> {
        // Shared steps: route → place → recall (with evidence boost).
        let Prepared {
            route,
            placement,
            recalled,
            boost,
        } = self.prepare(req)?;

        // Memory-boosted single branch, judged by the critic.
        let critic = BranchCritic::for_profile(&req.profile)
            .ok_or_else(|| CortexError::UnknownProfile(req.profile.clone()))?;
        let reward = boost_reward(req.reward.clone(), boost);
        let assessment = critic.assess(&BranchState::from_reward(1, reward));

        // Compute profile — what the placed precision actually costs,
        // computed by the bitlinear / nvfp4 engines themselves.
        let compute = ComputeProfile::for_role(placement.role, req.model_params);

        let summary = format!(
            "route={:?} → device='{}'{} | recalled={} | action={:?} (score={:.3}, uncertainty={:.3}) | compute={} ({:.1} bits/param, {} MB)",
            route.role,
            placement.device,
            placement_tag(&placement),
            recalled.len(),
            assessment.suggested_next_action,
            assessment.step_score,
            assessment.uncertainty,
            compute.path,
            compute.bits_per_param,
            compute.est_model_bytes / 1_000_000,
        );

        Ok(CortexDecision {
            route,
            placement,
            recalled,
            assessment,
            compute,
            summary,
        })
    }

    /// Best-of-N deliberation (M00444 + F02218 + F02228): evaluate several
    /// candidate branches against the *same* routed/placed/recalled context
    /// and pick the highest-value, non-pruned one — then report whether the
    /// [`IntelligenceTier`]'s fanout budget justifies spending more compute
    /// on the winner. This is the cortex doing real search, not a single
    /// forward pass.
    pub fn deliberate(
        &self,
        req: &CortexRequest,
        candidates: &[RewardVector],
        tier: IntelligenceTier,
    ) -> Result<Deliberation, CortexError> {
        if candidates.is_empty() {
            return Err(CortexError::NoCandidates);
        }
        let Prepared {
            route,
            placement,
            recalled,
            boost,
        } = self.prepare(req)?;

        let critic = BranchCritic::for_profile(&req.profile)
            .ok_or_else(|| CortexError::UnknownProfile(req.profile.clone()))?;

        // Every candidate shares the recalled evidence boost.
        let branches: Vec<BranchState> = candidates
            .iter()
            .enumerate()
            .map(|(i, r)| BranchState::from_reward(i as u64, boost_reward(r.clone(), boost)))
            .collect();

        let best = critic.select_best_of_n(&branches);
        let all: Vec<BranchAssessment> = branches.iter().map(|b| critic.assess(b)).collect();
        let more_compute_justified = best
            .as_ref()
            .map(|b| critic.compute_justified(b, tier, 0))
            .unwrap_or(false);
        let compute = ComputeProfile::for_role(placement.role, req.model_params);

        let summary = match &best {
            Some(b) => format!(
                "route={:?} → device='{}'{} | recalled={} | best=branch#{} action={:?} (score={:.3}) of {} candidates | more_compute={}",
                route.role,
                placement.device,
                placement_tag(&placement),
                recalled.len(),
                b.branch_id,
                b.suggested_next_action,
                b.step_score,
                candidates.len(),
                more_compute_justified,
            ),
            None => format!(
                "route={:?} → device='{}' | recalled={} | all {} candidates pruned",
                route.role,
                placement.device,
                recalled.len(),
                candidates.len(),
            ),
        };

        Ok(Deliberation {
            route,
            placement,
            recalled,
            candidates_considered: candidates.len(),
            best,
            all,
            more_compute_justified,
            compute,
            summary,
        })
    }

    /// Shared front of the pipeline: route → place → recall + evidence boost.
    fn prepare(&self, req: &CortexRequest) -> Result<Prepared, CortexError> {
        let route = route(&req.axes)?;
        let sched_req = ScheduleRequest {
            class: req.workload.class,
            conductor: req.conductor,
            logic: req.logic,
            oracle: req.oracle,
        };
        let placement = place(&req.workload, &sched_req, req.allow_cloud)?;
        let query = Query::new(req.query_topic, req.query_entity, req.now, req.half_life);
        let recalled = self.memory.retrieve(&query, RECALL_TOP_K);
        let boost = recalled.len() as f32 * RECALL_EVIDENCE_BOOST;
        Ok(Prepared {
            route,
            placement,
            recalled,
            boost,
        })
    }
}

/// Shared front-of-pipeline result (route + placement + recall + boost).
struct Prepared {
    route: RouteDecision,
    placement: Placement,
    recalled: Vec<Hit>,
    boost: f32,
}

/// Apply the recall evidence boost to a reward vector: more supporting
/// memory raises both the evidence axis and confidence calibration.
fn boost_reward(mut reward: RewardVector, boost: f32) -> RewardVector {
    reward.evidence = (reward.evidence + boost).min(1.0);
    reward.confidence_calibration = (reward.confidence_calibration + boost * 0.5).min(1.0);
    reward
}

/// Short placement annotation for summary lines.
fn placement_tag(p: &Placement) -> &'static str {
    if p.spilled_to_cloud {
        " [cloud spill]"
    } else if p.fell_back {
        " [fell back]"
    } else {
        ""
    }
}

/// Seed a memory store with a few readable items whose topic sketch is
/// `0b1111` — so the demo recall query (topic `0b1111`) returns evidence.
/// Useful for the binary and for tests.
pub fn seed_memory() -> MemoryStore {
    let mut store = MemoryStore::new();
    let gt = |raw: &str| GroundTruth {
        raw_episode: raw.into(),
        derived_facts: vec![],
        summary: format!("summary: {raw}"),
        graph_edges: vec![],
        trust: 850,
        freshness: 100,
        summary_suspect: false,
    };
    store.admit(
        HotMeta::new(
            1,
            MemoryType::Semantic,
            0,
            0,
            850,
            100,
            0b1111,
            0b0001,
            700,
            FLAG_READABLE,
        ),
        gt("prior successful run of this task class"),
    );
    store.admit(
        HotMeta::new(
            2,
            MemoryType::Episodic,
            0,
            0,
            700,
            100,
            0b0110,
            0b0010,
            500,
            FLAG_READABLE,
        ),
        gt("a partially-related episode"),
    );
    store
}

/// A small set of representative requests exercising distinct paths
/// through the cortex (used by the binary's demo mode and by tests).
pub fn demo_requests() -> Vec<CortexRequest> {
    use sovereign_router_7axis::{Complexity, Domain, Latency, Locality, Privacy, Quality, Safety};
    use sovereign_srp_scheduler::WorkloadClass;
    use sovereign_srp_scheduler::{Precision, Workload};

    let strong_reward = RewardVector {
        correctness: 0.9,
        evidence: 0.7,
        schema_validity: 1.0,
        tool_success: 1.0,
        test_success: 1.0,
        risk: 0.1,
        latency: 0.2,
        cost: 0.2,
        novelty: 0.4,
        user_preference: 0.7,
        cache_reuse: 0.6,
        confidence_calibration: 0.85,
    };

    vec![
        // Simple, cheap, fast, local → Conductor / CPU ternary.
        CortexRequest {
            axes: TaskAxes {
                complexity: Complexity::Simple,
                privacy: Privacy::Private,
                safety: Safety::Safe,
                domain: Domain::Coding,
                locality: Locality::Local,
                latency: Latency::Fast,
                quality: Quality::Cheap,
            },
            workload: Workload {
                class: WorkloadClass::IntentEval,
                precision: Precision::Ternary,
                context_tokens: 2_048,
                min_vram_gb: 0,
            },
            conductor: RolePressure::free(),
            logic: RolePressure::free(),
            oracle: RolePressure::free(),
            allow_cloud: false,
            query_topic: 0b1111,
            query_entity: 0b0001,
            now: 100,
            half_life: 1_000,
            reward: strong_reward.clone(),
            profile: "fast".into(),
            model_params: 2_000_000_000,
        },
        // Private, risky, complex, deep → Oracle / GPU 1, never cloud.
        CortexRequest {
            axes: TaskAxes {
                complexity: Complexity::Complex,
                privacy: Privacy::Private,
                safety: Safety::Risky,
                domain: Domain::Research,
                locality: Locality::Local,
                latency: Latency::Careful,
                quality: Quality::Oracle,
            },
            workload: Workload {
                class: WorkloadClass::DeepReason,
                precision: Precision::Fp16,
                context_tokens: 120_000,
                min_vram_gb: 80,
            },
            conductor: RolePressure::free(),
            logic: RolePressure::free(),
            oracle: RolePressure::free(),
            allow_cloud: false,
            query_topic: 0b1111,
            query_entity: 0b0001,
            now: 100,
            half_life: 1_000,
            reward: strong_reward,
            profile: "careful".into(),
            model_params: 70_000_000_000,
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_router_7axis::{Complexity, Domain, Latency, Locality, Privacy, Quality, Safety};
    use sovereign_srp_scheduler::Precision;
    use sovereign_srp_scheduler::WorkloadClass;
    use sovereign_value_plane::NextAction;

    fn req() -> CortexRequest {
        demo_requests().remove(0) // the simple/local one
    }

    #[test]
    fn simple_local_request_routes_to_conductor_and_commits() {
        let cortex = Cortex::with_memory(seed_memory());
        let d = cortex.tick(&req()).unwrap();
        assert_eq!(format!("{:?}", d.route.role), "Conductor");
        assert_eq!(format!("{:?}", d.placement.role), "Conductor");
        assert!(!d.recalled.is_empty(), "seeded memory should be recalled");
        // strong reward + recall boost → commit
        assert_eq!(d.assessment.suggested_next_action, NextAction::Commit);
    }

    #[test]
    fn deep_private_request_lands_on_oracle_never_cloud() {
        let cortex = Cortex::with_memory(seed_memory());
        let d = cortex.tick(&demo_requests().remove(1)).unwrap();
        assert_eq!(format!("{:?}", d.placement.role), "Oracle");
        assert!(!d.placement.spilled_to_cloud);
    }

    #[test]
    fn memory_recall_actually_strengthens_the_verdict() {
        // Same request, two cortexes: one with supporting memory, one empty.
        // The recalled evidence must raise the critic's confidence.
        let mut weak = req();
        // start less confident so the boost matters
        weak.reward.evidence = 0.4;
        weak.reward.confidence_calibration = 0.5;

        let with_mem = Cortex::with_memory(seed_memory()).tick(&weak).unwrap();
        let without_mem = Cortex::new().tick(&weak).unwrap();

        assert!(with_mem.recalled.len() > without_mem.recalled.len());
        assert!(
            with_mem.assessment.step_score > without_mem.assessment.step_score,
            "recalled evidence should raise the score: {} vs {}",
            with_mem.assessment.step_score,
            without_mem.assessment.step_score
        );
    }

    #[test]
    fn privacy_cloud_contradiction_is_refused() {
        let mut r = req();
        r.axes.privacy = Privacy::Private;
        r.axes.locality = Locality::Cloud;
        let err = Cortex::new().tick(&r).unwrap_err();
        assert!(matches!(err, CortexError::Route(_)));
    }

    #[test]
    fn unknown_profile_is_rejected() {
        let mut r = req();
        r.profile = "nonsense".into();
        let err = Cortex::with_memory(seed_memory()).tick(&r).unwrap_err();
        assert!(matches!(err, CortexError::UnknownProfile(_)));
    }

    #[test]
    fn fp16_job_with_oracle_overloaded_and_no_cloud_fails_placement() {
        let mut r = demo_requests().remove(1); // the FP16 deep job
        r.oracle = RolePressure::overloaded();
        // allow_cloud is false → only Oracle is capable, and it's overloaded
        let err = Cortex::new().tick(&r).unwrap_err();
        assert!(matches!(err, CortexError::Placement(_)));
    }

    #[test]
    fn decision_serializes_to_json() {
        let cortex = Cortex::with_memory(seed_memory());
        let d = cortex.tick(&req()).unwrap();
        let json = serde_json::to_string(&d).unwrap();
        assert!(json.contains("\"summary\""));
        assert!(json.contains("\"route\""));
        assert!(json.contains("\"placement\""));
    }

    #[test]
    fn request_round_trips_through_json() {
        let r = req();
        let json = serde_json::to_string(&r).unwrap();
        let back: CortexRequest = serde_json::from_str(&json).unwrap();
        assert_eq!(r, back);
    }

    #[test]
    fn gui_request_routes_to_logic() {
        let mut r = req();
        r.axes.domain = Domain::Gui;
        let d = Cortex::new().tick(&r).unwrap();
        assert_eq!(format!("{:?}", d.route.role), "Logic");
    }

    #[test]
    fn quantized_midscale_places_on_logic() {
        let mut r = req();
        r.axes.complexity = Complexity::Complex;
        r.axes.latency = Latency::Careful;
        r.axes.quality = Quality::Cheap;
        r.axes.safety = Safety::Safe;
        r.workload = Workload {
            class: WorkloadClass::TokenStream,
            precision: Precision::Quantized,
            context_tokens: 16_000,
            min_vram_gb: 18,
        };
        let d = Cortex::new().tick(&r).unwrap();
        assert_eq!(format!("{:?}", d.placement.role), "Logic");
    }

    // --- decision carries a real compute profile ---

    #[test]
    fn decision_carries_compute_profile() {
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        // simple/local → Conductor → ternary, multiplication-free
        assert!(d.compute.multiplication_free);
        assert!((d.compute.bits_per_param - 1.6).abs() < 1e-6);
    }

    // --- best-of-N deliberation ---

    fn graded_reward(correctness: f32, calibration: f32) -> RewardVector {
        RewardVector {
            correctness,
            evidence: 0.6,
            schema_validity: 1.0,
            tool_success: 1.0,
            test_success: 1.0,
            risk: 0.1,
            latency: 0.2,
            cost: 0.2,
            novelty: 0.4,
            user_preference: 0.6,
            cache_reuse: 0.5,
            confidence_calibration: calibration,
        }
    }

    #[test]
    fn deliberate_picks_the_strongest_candidate() {
        let cortex = Cortex::with_memory(seed_memory());
        let candidates = vec![
            graded_reward(0.55, 0.9), // branch 0 — weak
            graded_reward(0.95, 0.9), // branch 1 — strong
            graded_reward(0.70, 0.9), // branch 2 — mid
        ];
        let d = cortex
            .deliberate(&req(), &candidates, IntelligenceTier::Deliberate)
            .unwrap();
        assert_eq!(d.candidates_considered, 3);
        assert_eq!(d.all.len(), 3);
        let best = d.best.expect("a winner");
        assert_eq!(best.branch_id, 1, "strongest branch should win");
    }

    #[test]
    fn deliberate_empty_candidates_is_error() {
        let err = Cortex::new()
            .deliberate(&req(), &[], IntelligenceTier::Normal)
            .unwrap_err();
        assert!(matches!(err, CortexError::NoCandidates));
    }

    #[test]
    fn deliberate_all_pruned_yields_no_winner() {
        let cortex = Cortex::new();
        // schema_validity 0 → every candidate is a hard failure → pruned
        let mut bad = graded_reward(0.9, 0.9);
        bad.schema_validity = 0.0;
        let d = cortex
            .deliberate(&req(), &[bad.clone(), bad], IntelligenceTier::Normal)
            .unwrap();
        assert!(d.best.is_none());
        assert!(d.summary.contains("pruned"));
    }

    #[test]
    fn deliberate_flags_more_compute_when_uncertain() {
        let cortex = Cortex::new(); // no memory → no calibration boost
        // low calibration → high uncertainty → more compute justified
        let uncertain = graded_reward(0.7, 0.2);
        let d = cortex
            .deliberate(&req(), &[uncertain], IntelligenceTier::Deliberate)
            .unwrap();
        assert!(d.more_compute_justified);
    }
}
