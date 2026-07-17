//! `sovereign-cortex` — the first runnable assembly of the real engines.
//!
//! The runtime crates each do their own job well, but until now nothing
//! composed them: there was no binary, and the engines barely referenced
//! each other. This crate is the composition layer — one
//! [`Cortex::tick`] runs a request through the whole local intelligence
//! path and returns a single auditable decision; [`Cortex::act`] then
//! ratifies it through the Trinity gate, and [`Cortex::learn`] folds a
//! committed outcome back into memory. All eight engines compose here:
//!
//! ```text
//! CortexRequest
//!   │
//!   ├─▶ router-7axis    route(axes)          → SRP role + reason
//!   ├─▶ srp-scheduler   place(workload, …)   → hardware target (capability-aware)
//!   ├─▶ memory-os       retrieve(query)      → recalled evidence ──┐
//!   │                                          (boosts the branch) │
//!   ├─▶ value-plane     critic.assess(branch) → commit/expand/prune ◀┘
//!   ├─▶ lora-foundry    decide_serving(…)    → which adapter path
//!   ├─▶ hrm-runtime     run_with_halt(…)     → deeper reasoning (if uncertain)
//!   └─▶ bitlinear+nvfp4 ComputeProfile       → real per-device kernel + footprint
//!   ▼
//! CortexDecision
//!   │
//!   ├─▶ trinity         Pulse→Weaver→Auditor → ratified commit   (act)
//!   └─▶ memory-os       admit(committed)     → learned for next  (learn, M016)
//! ```
//!
//! The wiring is real, not nominal: recalled memory modulates the reward
//! vector the PRM critic judges (more relevant memory → more confident
//! verdict); the compute step actually runs the bitlinear/nvfp4 kernels;
//! the Auditor ratifies only a value-plane Commit; and committed decisions
//! are learned so later similar requests decide better — adaptation without
//! retraining.
//!
//! Modes: [`Cortex::tick`] (single pass), [`Cortex::deliberate`] (best-of-N),
//! [`Cortex::search`] (iterative, budget-bounded), [`Cortex::act`] /
//! [`Cortex::act_and_learn`] (decide → ratify → learn).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod compute;
pub mod verify;

pub use compute::ComputeProfile;
pub use verify::{decision_facts, session_trace, verify_session};
// Re-exported for consumers building safety properties over a cortex session.
pub use sovereign_symbolic_plan::{SafetyProperty, facts};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use sovereign_branch_tree::{BranchTree, ROOT};
use sovereign_control_word::{
    ControlWord, FLAG_AUDIT, FLAG_COMMIT_GATE, FLAG_SANDBOX, FLAG_SPECULATIVE, PrecisionCode,
    m00013,
};
use sovereign_hrm_runtime::{HrmConfig, HrmRun, HrmStepper, RecurrentState};
use sovereign_lora_foundry::{AdapterSlot, RuntimeDecision, ServeRequest, decide_serving};
use sovereign_memory_os::{
    FLAG_READABLE, GroundTruth, Hit, HotMeta, MemoryStore, MemoryType, Query,
};
use sovereign_replay_ledger::ReplayLedger;
use sovereign_router_7axis::{RouteDecision, RouterError, Safety, SrpRole, TaskAxes, route};
use sovereign_srp_scheduler::{
    Placement, PlacementError, RolePressure, ScheduleRequest, Workload, place,
};
use sovereign_trinity::TrinityCycle;
use sovereign_value_plane::{
    BranchAssessment, BranchCritic, BranchState, IntelligenceTier, NextAction, RewardVector,
};
use sovereign_world_model::WorldModel;

/// Schema version of the cortex request/decision surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// How many memory items the recall stage returns at most.
pub const RECALL_TOP_K: usize = 5;

/// Per-recalled-item boost applied to the branch's evidence axis before
/// the critic judges it. Recall feeds the value plane.
pub const RECALL_EVIDENCE_BOOST: f32 = 0.05;

/// Additional evidence boost scaled by the best recalled embedding's cosine
/// similarity to the query embedding — semantically closer recall yields
/// more confidence (the embedding-rerank stage feeding the value plane).
pub const SEMANTIC_EVIDENCE_BOOST: f32 = 0.1;

/// Hard safety cap on iterative-search rounds, independent of tier budget.
pub const MAX_SEARCH_ROUNDS: u32 = 64;

/// Base id for memories learned from committed decisions (kept clear of
/// any externally-seeded ids).
pub const LEARNED_ID_BASE: u64 = 1_000_000;

/// Minimum World-Model prior confidence for a disagreement to count as a
/// "surprise" worth extra scrutiny (M030 → deeper reasoning).
pub const WORLD_MODEL_SURPRISE_CONFIDENCE: f32 = 0.75;

/// Minimum past observations behind the prior before a disagreement is trusted
/// enough to act on (don't engage compute on one-off history).
pub const WORLD_MODEL_SURPRISE_MIN_OBS: u64 = 3;

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
    /// Eval-passed LoRA adapters that match this task (may be empty).
    pub available_adapters: Vec<AdapterSlot>,
    /// Whether the runtime can stack-merge multiple adapters.
    pub stacking_supported: bool,
    /// Optional query embedding; when non-empty, recall adds the embedding
    /// rerank stage and a semantic-similarity evidence boost.
    pub query_embedding: Vec<f32>,
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
    /// LoRA serving decision — which adapter path to take (M046).
    pub serving: RuntimeDecision,
    /// Deeper-reasoning engagement (M080): `Some` recurrent run when the
    /// verdict needed more compute, `None` when the branch was decisive.
    pub reasoning: Option<HrmRun>,
    /// Per-device compute profile for the placement (footprint + precision).
    pub compute: ComputeProfile,
    /// Per-branch control word (M002): the injected microcode encoding this
    /// decision's precision lane + flags (commit-gate / sandbox / audit /
    /// speculative) + opcode + recall count.
    pub control_word: ControlWord,
    /// The SAME decision, encoded in the M00013 field layout (M002): mode ←
    /// next-action, event ← role, intensity ← step-score, cooldown ← reasoning
    /// steps, neighborhood ← risk-score, paramA ← recall count, paramB ← flags.
    /// Emitted alongside `control_word`; the `avx-mode` switch (custom/hybrid)
    /// selects this layout downstream via [`CortexDecision::control_word_bits`].
    pub control_word_m00013: m00013::Fields,
    /// Learned-dynamics prior for this `(topic, role)` (M030). `Some` once the
    /// pair has resolved before; `None` for a cold pair.
    pub prediction: Option<WorldModelPrediction>,
    /// One-line human-readable trace of the whole path.
    pub summary: String,
}

/// A learned-dynamics prior (M030): what the world model expects for this
/// `(task-topic, routing-role)` pair from history. Carried on a decision only
/// when the pair has been seen before — `None` for a cold pair, no fabrication.
#[derive(Debug, Clone, Serialize)]
pub struct WorldModelPrediction {
    /// The modal historical verdict for this `(topic, role)`.
    pub expected_action: NextAction,
    /// Probability the model assigns that verdict (0.0..=1.0).
    pub confidence: f32,
    /// How many past transitions back this prediction.
    pub observations: u64,
    /// Whether the live value-plane verdict matches the learned prior. A
    /// mismatch is a signal: this task is resolving differently than history.
    pub agrees_with_verdict: bool,
}

/// Encode an SRP role as a world-model action id (M030 action space).
fn role_action_id(role: SrpRole) -> u64 {
    match role {
        SrpRole::Conductor => 0,
        SrpRole::Logic => 1,
        SrpRole::Oracle => 2,
        SrpRole::Cloud => 3,
    }
}

/// Encode a value-plane verdict as a world-model outcome-state id.
fn outcome_state_id(action: NextAction) -> u64 {
    match action {
        NextAction::Commit => 1,
        NextAction::Expand => 2,
        NextAction::NeedMoreCompute => 3,
        NextAction::Prune => 4,
    }
}

/// Decode a world-model outcome-state id back to a verdict.
fn outcome_from_state_id(id: u64) -> Option<NextAction> {
    match id {
        1 => Some(NextAction::Commit),
        2 => Some(NextAction::Expand),
        3 => Some(NextAction::NeedMoreCompute),
        4 => Some(NextAction::Prune),
        _ => None,
    }
}

/// Map a placed SRP role to the control word's precision lane.
fn precision_for_role(role: SrpRole) -> PrecisionCode {
    match role {
        SrpRole::Conductor => PrecisionCode::Ternary,
        SrpRole::Logic => PrecisionCode::Quantized,
        SrpRole::Oracle => PrecisionCode::Fp16,
        SrpRole::Cloud => PrecisionCode::Fp16, // remote; treated as full precision
    }
}

/// Which control-word layout the runtime emits (F00092 / R00269 — the
/// `control_word_layout_version` knob, driven by the `avx-mode` switch).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ControlWordLayout {
    /// The opcode / precision / flags / operand word (M002 crate default).
    #[default]
    Legacy,
    /// The M00013 field layout (mode / event / intensity / … / paramA / paramB).
    M00013,
}

/// Map the `avx-mode` switch (`custom` / `builtin` / `hybrid` / `off`) to the
/// control-word layout: the bit-machine modes (`custom` / `hybrid`) emit the
/// M00013 word; the math / scalar modes keep the legacy word. This is the
/// switch the operator flips — `sovereign-osctl avx-mode set custom`.
pub fn control_word_layout_for_avx_mode(avx_mode: &str) -> ControlWordLayout {
    match avx_mode.trim() {
        "custom" | "hybrid" => ControlWordLayout::M00013,
        _ => ControlWordLayout::Legacy,
    }
}

impl CortexDecision {
    /// The control word this decision emits under `layout` — the legacy packed
    /// u64, or the M00013 word. This is where the `avx-mode` switch takes effect:
    /// `custom` / `hybrid` → M00013, else legacy. Both are always computed from
    /// the same decision; the layout only selects which one is authoritative.
    pub fn control_word_bits(&self, layout: ControlWordLayout) -> u64 {
        match layout {
            ControlWordLayout::Legacy => self.control_word.raw(),
            // pack() only errors on field overflow; the fields are constructed
            // in-range from the decision, so this never fails in practice.
            ControlWordLayout::M00013 => self.control_word_m00013.pack().unwrap_or(0),
        }
    }

    /// A plain-language operator rationale (M015 human-gate: "plain-language
    /// reasons" + a cost/rollback preview), distinct from the terse
    /// machine `summary`. This is what a human approver reads.
    pub fn explain(&self) -> String {
        let mut lines = vec![
            format!("Routed to {:?}: {}", self.route.role, self.route.reason),
            format!(
                "Runs on {} ({}, ~{} MB at {:.1} bits/param)",
                self.placement.device,
                self.compute.path,
                self.compute.est_model_bytes / 1_000_000,
                self.compute.bits_per_param,
            ),
            format!("Adapter path: {:?}", self.serving),
            format!(
                "Verdict: {:?} (score {:.3}, risk {:.3}, uncertainty {:.3})",
                self.assessment.suggested_next_action,
                self.assessment.step_score,
                self.assessment.risk_score,
                self.assessment.uncertainty,
            ),
        ];
        if !self.recalled.is_empty() {
            lines.push(format!(
                "Supported by {} recalled memory item(s).",
                self.recalled.len()
            ));
        }
        if let Some(r) = self.reasoning {
            lines.push(format!(
                "Engaged deeper reasoning ({} recurrent steps).",
                r.steps
            ));
        }
        if self.placement.spilled_to_cloud {
            lines.push("NOTE: spilled to the cloud expert plane (off-node).".to_string());
        } else if self.placement.fell_back {
            lines.push("NOTE: fell back from the canonical role.".to_string());
        }
        let footprint = if self.compute.est_model_bytes == 0 {
            "remote (no local footprint)".to_string()
        } else {
            format!("~{} MB local", self.compute.est_model_bytes / 1_000_000)
        };
        lines.push(format!(
            "Cost/rollback: {footprint}; rollback = discard this branch (no host commit until ratified by the Auditor)."
        ));
        lines.join("\n")
    }
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
    /// The branch tree (M007): one forked branch per candidate, the winner
    /// committed and the rest pruned.
    pub branches: BranchTree,
    /// One-line human-readable trace.
    pub summary: String,
}

/// Aggregate result of a [`Cortex::run_session`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct SessionReport {
    /// Requests submitted.
    pub total: usize,
    /// How many committed.
    pub committed: usize,
    /// How many were learned into memory.
    pub learned: usize,
    /// How many were refused by an engine (router/scheduler).
    pub refused: usize,
}

/// Produces the next round of candidate branches given the current best.
///
/// The cortex owns the *search loop and the budget control*; generating
/// the actual next candidates (the "expand" step — sampling, refining,
/// re-prompting) is the model's job and is injected here. Return an empty
/// vector to signal "no further expansion possible", which stops the loop.
pub trait BranchExpander {
    /// Candidates for the next round, given the current `best` and the
    /// zero-based `round` number just completed.
    fn expand(&self, best: &BranchAssessment, round: u32) -> Vec<RewardVector>;
}

/// The outcome of an iterative [`Cortex::search`]. Output-only (`Serialize`).
#[derive(Debug, Clone, Serialize)]
pub struct SearchOutcome {
    /// Router output (shared across the search).
    pub route: RouteDecision,
    /// Placement (shared across the search).
    pub placement: Placement,
    /// Number of memory items recalled for the shared context.
    pub recalled: usize,
    /// Number of expansion rounds performed (0 = the seed round only).
    pub rounds: u32,
    /// Whether the search ended on a committable branch.
    pub committed: bool,
    /// The final winning branch, if any survived pruning.
    pub final_best: Option<BranchAssessment>,
    /// The winning branch of each round, in order.
    pub history: Vec<BranchAssessment>,
    /// Compute profile for the shared placement.
    pub compute: ComputeProfile,
    /// One-line human-readable trace.
    pub summary: String,
}

/// FNV-1a over `text`'s alphanumeric tokens → a 64-bit sketch (one set bit per
/// token). The keying kernel behind [`Cortex::recall_text`] — different text
/// probes different memory. Case-insensitive.
fn text_sketch(text: &str) -> u64 {
    let mut bits = 0u64;
    for tok in text
        .split(|c: char| !c.is_alphanumeric())
        .filter(|t| !t.is_empty())
    {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for b in tok.as_bytes() {
            h ^= b.to_ascii_lowercase() as u64;
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        bits |= 1u64 << (h % 64);
    }
    bits
}

/// The cortex. Owns the memory store; stateless engines are called
/// functionally per tick.
#[derive(Debug, Default)]
pub struct Cortex {
    /// The live memory the recall stage queries.
    pub memory: MemoryStore,
    /// Tamper-evident audit trail of decisions (M012 replay plane).
    pub ledger: ReplayLedger,
    /// Learned task→routing→outcome dynamics (M030 World Model plane). Grows
    /// as the cortex observes how `(task-topic, routing-role)` pairs resolve,
    /// supplying a learned prior alongside the value plane's per-branch critique.
    pub world_model: WorldModel,
}

impl Cortex {
    /// A cortex with empty memory.
    pub fn new() -> Self {
        Self::default()
    }

    /// A cortex wrapping a pre-populated memory store.
    pub fn with_memory(memory: MemoryStore) -> Self {
        Self {
            memory,
            ..Self::default()
        }
    }

    /// A cortex whose learned memory is bounded to `capacity` items — past
    /// the bound, the lowest-value memory is evicted, so an endlessly-running
    /// learning cortex keeps its best memories without unbounded growth.
    pub fn bounded(capacity: usize) -> Self {
        Self {
            memory: MemoryStore::with_capacity(capacity),
            ..Self::default()
        }
    }

    /// Append a decision to the tamper-evident audit ledger; returns its
    /// sequence number. Every decision is recorded so the trail is replayable
    /// and verifiable (the Trinity Auditor's record).
    pub fn audit(&mut self, decision: &CortexDecision) -> u64 {
        self.ledger.append(decision.summary.clone())
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

        // World-model prior (M030): what history expects for this
        // (task-topic, routing-role), learned across prior transitions.
        let prediction = self.predict_outcome(
            req.query_topic,
            route.role,
            assessment.suggested_next_action,
        );

        // Serve — which LoRA adapter path (M046). High-stakes (risky) tasks
        // route to oracle verification regardless of available adapters.
        let serve_req = ServeRequest {
            matching_adapters: req.available_adapters.clone(),
            stacking_supported: req.stacking_supported,
            high_stakes: req.axes.safety == Safety::Risky,
            base_allowed: true,
        };
        let serving = decide_serving(&serve_req);

        // Engage deeper reasoning (M080) when the verdict is uncertain OR when
        // the World-Model prior (M030) strongly disagrees with it. A confident,
        // well-observed prior that contradicts the verdict is a "surprise" — the
        // task is resolving against history — and warrants extra scrutiny before
        // the Auditor sees it. This never changes the verdict (so it can't cause
        // a wrong commit); it only adds a bounded recurrent pass.
        let surprising = prediction.as_ref().is_some_and(|p| {
            !p.agrees_with_verdict
                && p.confidence >= WORLD_MODEL_SURPRISE_CONFIDENCE
                && p.observations >= WORLD_MODEL_SURPRISE_MIN_OBS
        });
        let reasoning =
            if assessment.suggested_next_action == NextAction::NeedMoreCompute || surprising {
                Some(engage_reasoning())
            } else {
                None
            };

        // Compute profile — what the placed precision actually costs,
        // computed by the bitlinear / nvfp4 engines themselves.
        let compute = ComputeProfile::for_role(placement.role, req.model_params);

        // Control word (M002): the per-branch injected logic for this decision.
        let opcode = match assessment.suggested_next_action {
            NextAction::Commit => 1,
            NextAction::Expand => 2,
            NextAction::NeedMoreCompute => 3,
            NextAction::Prune => 4,
        };
        let mut cw_flags = FLAG_AUDIT; // the cortex always routes through the Auditor
        if assessment.suggested_next_action == NextAction::Commit {
            cw_flags |= FLAG_COMMIT_GATE;
        }
        if req.axes.safety == Safety::Risky {
            cw_flags |= FLAG_SANDBOX;
        }
        if reasoning.is_some() {
            cw_flags |= FLAG_SPECULATIVE;
        }
        let control_word = ControlWord::new(
            opcode,
            precision_for_role(placement.role),
            cw_flags,
            recalled.len() as u32,
        );
        // The M00013 view of the same decision — real fields, not placeholders.
        let control_word_m00013 = m00013::Fields {
            mode: opcode as u16,                              // next-action
            event: role_action_id(route.role).min(15) as u16, // role
            intensity: (assessment.step_score.clamp(0.0, 1.0) * 255.0).round() as u16,
            cooldown: reasoning.as_ref().map(|r| r.steps).unwrap_or(0).min(255) as u16,
            neighborhood: (assessment.risk_score.clamp(0.0, 1.0) * 255.0).round() as u16,
            param_a: (recalled.len() as u64).min(u16::MAX as u64) as u16, // recall count
            param_b: cw_flags as u16, // commit/sandbox/audit/spec
        };

        let summary = format!(
            "route={:?} → device='{}'{} | recalled={} | action={:?} (score={:.3}, uncertainty={:.3}) | serve={:?} | reasoning={} | compute={} ({:.1} bits/param, {} MB)",
            route.role,
            placement.device,
            placement_tag(&placement),
            recalled.len(),
            assessment.suggested_next_action,
            assessment.step_score,
            assessment.uncertainty,
            serving,
            reasoning.map(|r| r.steps).unwrap_or(0),
            compute.path,
            compute.bits_per_param,
            compute.est_model_bytes / 1_000_000,
        );

        Ok(CortexDecision {
            route,
            placement,
            recalled,
            assessment,
            serving,
            reasoning,
            compute,
            control_word,
            control_word_m00013,
            prediction,
            summary,
        })
    }

    /// The M030 world-model prior for a `(topic, role)` pair, or `None` when the
    /// pair is cold. Read-only — learning happens in [`Cortex::learn`].
    fn predict_outcome(
        &self,
        topic: u64,
        role: SrpRole,
        verdict: NextAction,
    ) -> Option<WorldModelPrediction> {
        let action = role_action_id(role);
        let predicted_id = self.world_model.predict(topic, action)?;
        let expected_action = outcome_from_state_id(predicted_id)?;
        Some(WorldModelPrediction {
            expected_action,
            confidence: self.world_model.probability(topic, action, predicted_id) as f32,
            observations: self.world_model.pair_observations(topic, action),
            agrees_with_verdict: expected_action == verdict,
        })
    }

    /// Execute a decision through the Trinity gate (M066): the local
    /// Pulse → Weaver → Auditor cycle that turns a *decision* into a
    /// ratified *commit*.
    ///
    /// - **Pulse** runs only if the work stayed on local iron — cloud-spilled
    ///   work is executed remotely, not by the local Trinity.
    /// - **Weaver** orchestrates unless the branch is a hard failure.
    /// - **Auditor** — the immutable gate — passes only when the value
    ///   plane's verdict is [`NextAction::Commit`]. The cortex *decides*;
    ///   the Auditor *ratifies*.
    pub fn execute(&self, decision: &CortexDecision) -> TrinityCycle {
        let pulse_ok = !decision.placement.spilled_to_cloud;
        let weave_ok = !decision.assessment.failure_mode.is_hard();
        let audit_ok = decision.assessment.suggested_next_action == NextAction::Commit;
        TrinityCycle::run(
            (pulse_ok, decision.placement.device),
            (weave_ok, "weaver: orchestration + state transition"),
            (audit_ok, "auditor: value-plane commit verdict"),
        )
    }

    /// One-shot: decide ([`Cortex::tick`]) then ratify through the Trinity
    /// gate ([`Cortex::execute`]). Returns the decision and the cycle.
    pub fn act(&self, req: &CortexRequest) -> Result<(CortexDecision, TrinityCycle), CortexError> {
        let decision = self.tick(req)?;
        let cycle = self.execute(&decision);
        Ok((decision, cycle))
    }

    /// Learning without retraining (M016): admit a *committed* decision back
    /// into Memory-OS so later requests on the same topic recall it and the
    /// value plane judges them more confidently. Non-committed decisions are
    /// not learned (we only remember outcomes we stood behind). Returns
    /// whether anything was learned.
    pub fn learn(&mut self, req: &CortexRequest, decision: &CortexDecision) -> bool {
        // Learn the dynamics (M030) from EVERY outcome — the world model needs
        // to see prunes and expansions, not just commits, to predict them. This
        // is separate from the commit-gated memory admission below.
        self.world_model.observe(
            req.query_topic,
            role_action_id(decision.route.role),
            outcome_state_id(decision.assessment.suggested_next_action),
        );
        if decision.assessment.suggested_next_action != NextAction::Commit {
            return false;
        }
        let id = LEARNED_ID_BASE + self.memory.len() as u64;
        let trust = (decision.assessment.step_score.clamp(0.0, 1.0) * 1000.0) as u64;
        let meta = HotMeta::new(
            id,
            MemoryType::Episodic,
            0,
            req.now,
            trust,
            req.now,
            req.query_topic,
            req.query_entity,
            trust,
            FLAG_READABLE,
        );
        let truth = GroundTruth {
            raw_episode: decision.summary.clone(),
            derived_facts: vec![format!("{:?}", decision.route.role)],
            summary: format!(
                "committed decision (score {:.3})",
                decision.assessment.step_score
            ),
            graph_edges: vec![],
            embedding: vec![],
            trust: trust.min(1000) as u16,
            freshness: req.now,
            summary_suspect: false,
        };
        self.memory.admit(meta, truth);
        true
    }

    /// Decide, ratify, and learn: [`Cortex::act`] then [`Cortex::learn`].
    /// Returns the decision, the Trinity cycle, and whether it was learned.
    pub fn act_and_learn(
        &mut self,
        req: &CortexRequest,
    ) -> Result<(CortexDecision, TrinityCycle, bool), CortexError> {
        let (decision, cycle) = self.act(req)?;
        let learned = self.learn(req, &decision);
        Ok((decision, cycle, learned))
    }

    /// Memory hygiene for long-running operation (M028 decay stage): age out
    /// memories older than `ttl` ticks relative to `now` by marking their
    /// summary suspect (recover-to-truth) — the raw episode is never touched.
    /// Pairs with the capacity bound ([`Cortex::bounded`]) so an endlessly
    /// running cortex keeps memory both small and fresh. Returns how many
    /// memories were aged.
    pub fn maintain(&mut self, now: u64, ttl: u64) -> usize {
        self.memory.decay(now, ttl)
    }

    /// Run a sequence of requests as one session, learning across them: each
    /// request is decided and (if committed) learned, so later requests in
    /// the session can recall earlier outcomes. Router/scheduler refusals
    /// are counted, not fatal. Returns the decisions plus a [`SessionReport`].
    pub fn run_session(&mut self, reqs: &[CortexRequest]) -> (Vec<CortexDecision>, SessionReport) {
        let mut decisions = Vec::with_capacity(reqs.len());
        let mut report = SessionReport {
            total: reqs.len(),
            committed: 0,
            learned: 0,
            refused: 0,
        };
        for req in reqs {
            match self.tick(req) {
                Ok(decision) => {
                    if decision.assessment.suggested_next_action == NextAction::Commit {
                        report.committed += 1;
                    }
                    if self.learn(req, &decision) {
                        report.learned += 1;
                    }
                    self.audit(&decision); // tamper-evident decision trail
                    decisions.push(decision);
                }
                Err(_) => report.refused += 1,
            }
        }
        (decisions, report)
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
        let branch_states: Vec<BranchState> = candidates
            .iter()
            .enumerate()
            .map(|(i, r)| BranchState::from_reward(i as u64, boost_reward(r.clone(), boost)))
            .collect();

        let best = critic.select_best_of_n(&branch_states);
        let all: Vec<BranchAssessment> = branch_states.iter().map(|b| critic.assess(b)).collect();
        let more_compute_justified = best
            .as_ref()
            .map(|b| critic.compute_justified(b, tier, 0))
            .unwrap_or(false);
        let compute = ComputeProfile::for_role(placement.role, req.model_params);

        // Branch tree (M007): fork one branch per candidate, then commit the
        // winner and prune the rest — best-of-N as fork-and-prune.
        let mut branches = BranchTree::new();
        let branch_ids: Vec<u64> = candidates
            .iter()
            .map(|_| branches.fork(ROOT).expect("root is active"))
            .collect();
        if let Some(b) = &best {
            let winner = b.branch_id as usize;
            for (i, &bid) in branch_ids.iter().enumerate() {
                if i == winner {
                    let _ = branches.commit(bid);
                } else {
                    let _ = branches.prune(bid);
                }
            }
        } else {
            // all candidates failed → prune every branch
            for &bid in &branch_ids {
                let _ = branches.prune(bid);
            }
        }

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
            branches,
            summary,
        })
    }

    /// Associative recall for the CoAT reasoning engine (`sovereign-coat`): the
    /// Memory-OS staged scan, exposed as `(id, relevance)` pairs so callers need
    /// not depend on the `sovereign-memory-os` `Hit` type. This is the same
    /// `retrieve` that feeds `deliberate`'s evidence boost — surfaced so an
    /// external MCTS can pull associative memory at every expansion (CoAT's
    /// defining mechanism). Read-only.
    pub fn recall(
        &self,
        topic: u64,
        entity: u64,
        now: u64,
        half_life: u64,
        k: usize,
    ) -> Vec<(u64, f64)> {
        self.memory
            .retrieve(&Query::new(topic, entity, now, half_life), k)
            .into_iter()
            .map(|hit| (hit.id, hit.relevance))
            .collect()
    }

    /// Text-keyed recall — the string-query counterpart to [`Cortex::recall`],
    /// so a caller with a plain query (e.g. a `recall` agent tool, SDD-713) can
    /// pull relevant memory back as **text** without hand-computing sketches.
    /// Sketches `query` (topic = the sketch, entity = a rotated copy — the same
    /// keying the CoAT steering path uses), retrieves the top-`k` hits, and maps
    /// each surviving id to its ground-truth text ([`GroundTruth::best_available`]).
    /// `now`/`half_life` drive freshness decay (pass the store's own clock).
    /// Read-only.
    pub fn recall_text(&self, query: &str, now: u64, half_life: u64, k: usize) -> Vec<String> {
        let bits = text_sketch(query);
        self.recall(bits, bits.rotate_left(29), now, half_life, k)
            .into_iter()
            .filter_map(|(id, _rel)| {
                self.memory
                    .ground_truth(id)
                    .map(|g| g.best_available().to_string())
            })
            .collect()
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
        let mut boost = recalled.len() as f32 * RECALL_EVIDENCE_BOOST;
        // Embedding rerank stage: when a query embedding is supplied, add a
        // boost proportional to the best recalled item's cosine similarity.
        if !req.query_embedding.is_empty()
            && let Some(top) = self
                .memory
                .retrieve_reranked(&query, &req.query_embedding, 1)
                .first()
        {
            boost += top.cosine.max(0.0) * SEMANTIC_EVIDENCE_BOOST;
        }
        Ok(Prepared {
            route,
            placement,
            recalled,
            boost,
        })
    }

    /// Iterative inference-time search (M035): deliberate over the seed
    /// candidates, then keep expanding the best branch — via the injected
    /// [`BranchExpander`] — until it is committable, no more compute is
    /// justified for the tier, the expander yields nothing, or the safety
    /// cap is hit. The cortex owns the loop + budget; the expander owns
    /// candidate generation. Route/place/recall happen once, up front.
    pub fn search(
        &self,
        req: &CortexRequest,
        seed: &[RewardVector],
        tier: IntelligenceTier,
        expander: &dyn BranchExpander,
    ) -> Result<SearchOutcome, CortexError> {
        if seed.is_empty() {
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

        let mut current: Vec<RewardVector> = seed.to_vec();
        let mut history: Vec<BranchAssessment> = Vec::new();
        let mut round: u32 = 0;
        let mut best: Option<BranchAssessment>;

        loop {
            let branches: Vec<BranchState> = current
                .iter()
                .enumerate()
                .map(|(i, r)| BranchState::from_reward(i as u64, boost_reward(r.clone(), boost)))
                .collect();
            best = critic.select_best_of_n(&branches);

            let Some(b) = best else { break }; // all pruned this round
            history.push(b);

            if b.suggested_next_action == NextAction::Commit {
                break; // good enough + certain enough
            }
            if !critic.compute_justified(&b, tier, round) {
                break; // tier fanout budget spent
            }
            if round + 1 >= MAX_SEARCH_ROUNDS {
                break; // hard safety cap
            }

            let next = expander.expand(&b, round);
            if next.is_empty() {
                break; // nothing left to try
            }
            current = next;
            round += 1;
        }

        let committed = best
            .map(|b| b.suggested_next_action == NextAction::Commit)
            .unwrap_or(false);
        let compute = ComputeProfile::for_role(placement.role, req.model_params);
        let summary = format!(
            "route={:?} → device='{}'{} | recalled={} | rounds={} | committed={} | final={}",
            route.role,
            placement.device,
            placement_tag(&placement),
            recalled.len(),
            round,
            committed,
            match &best {
                Some(b) => format!(
                    "branch#{} {:?} ({:.3})",
                    b.branch_id, b.suggested_next_action, b.step_score
                ),
                None => "none (all pruned)".to_string(),
            },
        );

        Ok(SearchOutcome {
            route,
            placement,
            recalled: recalled.len(),
            rounds: round,
            committed,
            final_best: best,
            history,
            compute,
            summary,
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

/// Engage a bounded HRM recurrent pass (M080) representing "think deeper".
/// Halts after the first two outer steps so it is fast + bounded regardless
/// of config; the per-step math is the model's job (the crate's design).
fn engage_reasoning() -> HrmRun {
    let cfg = HrmConfig::canonical();
    // canonical() is a valid config, so the stepper construction succeeds.
    let stepper = HrmStepper::new(&cfg).expect("canonical HRM config is valid");
    let mut state = RecurrentState::zeros(&cfg);
    stepper.run_with_halt(&mut state, |s| s.outer_step >= 2)
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
        embedding: vec![],
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
            available_adapters: vec![AdapterSlot::CodingStyle],
            stacking_supported: false,
            query_embedding: vec![],
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
            available_adapters: vec![],
            stacking_supported: false,
            query_embedding: vec![],
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

    #[test]
    fn decision_emits_control_word() {
        use sovereign_control_word::{FLAG_COMMIT_GATE, PrecisionCode};
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        // simple/local → Conductor → ternary lane; committed → commit-gate flag
        assert_eq!(d.control_word.precision(), PrecisionCode::Ternary);
        assert!(d.control_word.has_flag(FLAG_COMMIT_GATE));
        assert_eq!(d.control_word.operand(), d.recalled.len() as u32);
    }

    #[test]
    fn decision_emits_m00013_word_and_avx_switch_selects_it() {
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        let f = d.control_word_m00013;
        // committed decision → mode = opcode Commit (1); paramA = recall count;
        // paramB carries the flags (the Auditor bit is always set).
        assert_eq!(f.mode, 1, "committed → mode == Commit opcode");
        assert_eq!(f.param_a, d.recalled.len() as u16, "paramA == recall count");
        assert!(
            f.param_b & (sovereign_control_word::FLAG_AUDIT as u16) != 0,
            "paramB must carry the audit flag"
        );
        // the avx-mode switch drives the layout choice…
        assert_eq!(
            control_word_layout_for_avx_mode("custom"),
            ControlWordLayout::M00013
        );
        assert_eq!(
            control_word_layout_for_avx_mode("builtin"),
            ControlWordLayout::Legacy
        );
        // …and selecting a layout yields the matching word, from ONE decision.
        assert_eq!(
            d.control_word_bits(ControlWordLayout::Legacy),
            d.control_word.raw()
        );
        assert_eq!(
            d.control_word_bits(ControlWordLayout::M00013),
            f.pack().unwrap()
        );
    }

    #[test]
    fn explain_is_human_readable_rationale() {
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        let text = d.explain();
        assert!(text.contains("Routed to Conductor"));
        assert!(text.contains("Verdict:"));
        assert!(text.contains("Adapter path:"));
        assert!(text.contains("Cost/rollback:"));
        // multi-line operator rationale
        assert!(text.lines().count() >= 4);
    }

    // --- LoRA serving decision wiring ---

    #[test]
    fn safe_task_with_one_adapter_uses_it() {
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        assert_eq!(d.serving, RuntimeDecision::UseAdapter);
    }

    #[test]
    fn risky_task_routes_serving_to_oracle() {
        let d = Cortex::with_memory(seed_memory())
            .tick(&demo_requests().remove(1))
            .unwrap();
        assert_eq!(d.serving, RuntimeDecision::AskOracle);
    }

    #[test]
    fn safe_task_no_adapter_uses_base() {
        let mut r = req();
        r.available_adapters.clear();
        let d = Cortex::new().tick(&r).unwrap();
        assert_eq!(d.serving, RuntimeDecision::UseBase);
    }

    // --- HRM deeper-reasoning engagement ---

    #[test]
    fn uncertain_verdict_engages_recurrent_reasoning() {
        let mut r = req();
        r.reward.confidence_calibration = 0.2; // high uncertainty → NeedMoreCompute
        let d = Cortex::new().tick(&r).unwrap();
        assert_eq!(
            d.assessment.suggested_next_action,
            NextAction::NeedMoreCompute
        );
        let run = d.reasoning.expect("uncertain verdict should engage HRM");
        assert!(run.steps > 0);
    }

    #[test]
    fn decisive_verdict_skips_recurrent_reasoning() {
        // strong local request → Commit → no deeper reasoning needed
        let d = Cortex::with_memory(seed_memory()).tick(&req()).unwrap();
        assert_eq!(d.assessment.suggested_next_action, NextAction::Commit);
        assert!(d.reasoning.is_none());
    }

    // --- learning without retraining (M016) ---

    #[test]
    fn committed_decision_is_learned_into_memory() {
        let mut cortex = Cortex::new();
        let before = cortex.memory.len();
        let (_d, _c, learned) = cortex.act_and_learn(&req()).unwrap();
        assert!(learned);
        assert_eq!(cortex.memory.len(), before + 1);
    }

    #[test]
    fn uncommitted_decision_is_not_learned() {
        let mut cortex = Cortex::new();
        let mut r = req();
        r.reward.confidence_calibration = 0.2; // → NeedMoreCompute, not Commit
        let (_d, _c, learned) = cortex.act_and_learn(&r).unwrap();
        assert!(!learned);
        assert_eq!(cortex.memory.len(), 0);
    }

    #[test]
    fn world_model_learns_the_routing_outcome_prior() {
        // A cold cortex carries no learned prior; after observing the same
        // (task-topic, routing-role) resolve once, the next tick carries an
        // M030 prediction that agrees with the verdict.
        let mut cortex = Cortex::new();
        let r = req();

        let cold = cortex.tick(&r).unwrap();
        assert!(
            cold.prediction.is_none(),
            "a cold (topic, role) pair has no learned prior"
        );

        // Resolve it once — learn() observes the (topic, role) → outcome.
        cortex.learn(&r, &cold);

        let warm = cortex.tick(&r).unwrap();
        let p = warm
            .prediction
            .expect("after one observation the pair is known");
        assert_eq!(p.expected_action, warm.assessment.suggested_next_action);
        assert!(p.agrees_with_verdict);
        assert!(
            (p.confidence - 1.0).abs() < 1e-6,
            "a single consistent outcome implies probability 1.0, got {}",
            p.confidence
        );
        assert_eq!(p.observations, 1);
    }

    #[test]
    fn prediction_flags_disagreement_with_history() {
        // Seed a conflicting prior: history says this (topic, role) pruned, but
        // the live request commits — the prediction must flag the mismatch.
        let mut cortex = Cortex::new();
        let r = req();

        let cold = cortex.tick(&r).unwrap();
        assert!(cold.prediction.is_none());
        let role = cold.route.role;

        // History: this (topic, role) resolved to Prune before.
        cortex.world_model.observe(
            r.query_topic,
            role_action_id(role),
            outcome_state_id(NextAction::Prune),
        );

        let warm = cortex.tick(&r).unwrap();
        let p = warm.prediction.expect("the pair is now known");
        assert_eq!(p.expected_action, NextAction::Prune);
        assert_ne!(
            warm.assessment.suggested_next_action,
            NextAction::Prune,
            "the live request commits, so it must not prune"
        );
        assert!(
            !p.agrees_with_verdict,
            "a Prune prior must disagree with a non-Prune verdict"
        );
    }

    #[test]
    fn a_surprising_prior_engages_reasoning_without_changing_the_verdict() {
        // A confident, well-observed prior that contradicts the verdict is a
        // surprise: it must engage deeper reasoning (extra scrutiny) but leave
        // the verdict itself untouched — it can never cause a wrong commit.
        let mut cortex = Cortex::new();
        let r = req();

        let cold = cortex.tick(&r).unwrap();
        let role = cold.route.role;
        assert_eq!(cold.assessment.suggested_next_action, NextAction::Commit);
        assert!(
            cold.reasoning.is_none(),
            "a committing request engages no extra compute by default"
        );

        // Build a confident Prune history for this (topic, role).
        for _ in 0..=WORLD_MODEL_SURPRISE_MIN_OBS {
            cortex.world_model.observe(
                r.query_topic,
                role_action_id(role),
                outcome_state_id(NextAction::Prune),
            );
        }

        let warm = cortex.tick(&r).unwrap();
        let p = warm.prediction.expect("the pair is now known");
        assert!(!p.agrees_with_verdict);
        assert!(p.confidence >= WORLD_MODEL_SURPRISE_CONFIDENCE);
        assert!(p.observations >= WORLD_MODEL_SURPRISE_MIN_OBS);
        // The surprise engaged deeper reasoning …
        assert!(
            warm.reasoning.is_some(),
            "a confident contradicting prior should engage reasoning"
        );
        // … but the verdict is unchanged — still a commit.
        assert_eq!(warm.assessment.suggested_next_action, NextAction::Commit);
    }

    #[test]
    fn learning_raises_confidence_on_the_next_similar_request() {
        // A weakened request the cortex commits on (strong base reward),
        // then a second identical request should recall the learned memory
        // and score higher than a cold cortex would.
        let mut cortex = Cortex::new();
        let r = req();

        let cold = Cortex::new().tick(&r).unwrap();
        let first = cortex.tick(&r).unwrap();
        assert!(cortex.learn(&r, &first)); // learn from the committed decision
        let warm = cortex.tick(&r).unwrap();

        assert!(
            warm.assessment.step_score >= cold.assessment.step_score,
            "after learning, the warm score {} should be >= cold {}",
            warm.assessment.step_score,
            cold.assessment.step_score
        );
        assert!(
            !warm.recalled.is_empty(),
            "should recall the learned memory"
        );
    }

    // --- session runner ---

    #[test]
    fn session_decides_and_learns_each_request() {
        let mut cortex = Cortex::new();
        let (decisions, report) = cortex.run_session(&demo_requests());
        assert_eq!(report.total, 2);
        assert_eq!(decisions.len(), 2);
        // both demo scenarios commit → both learned
        assert_eq!(report.committed, 2);
        assert_eq!(report.learned, 2);
        assert_eq!(report.refused, 0);
        assert_eq!(cortex.memory.len(), 2);
    }

    #[test]
    fn session_records_a_verifiable_audit_trail() {
        let mut cortex = Cortex::with_memory(seed_memory());
        let (decisions, _) = cortex.run_session(&demo_requests());
        // one ledger entry per decided request, and the chain verifies
        assert_eq!(cortex.ledger.len(), decisions.len());
        assert!(cortex.ledger.verify().is_ok());
        // the trail records the decision summaries in order
        assert_eq!(cortex.ledger.get(0).unwrap().payload, decisions[0].summary);
    }

    #[test]
    fn session_counts_refusals_without_aborting() {
        // first request is refused (private + cloud), second is fine.
        let mut bad = req();
        bad.axes.privacy = Privacy::Private;
        bad.axes.locality = Locality::Cloud;
        let good = req();
        let mut cortex = Cortex::new();
        let (decisions, report) = cortex.run_session(&[bad, good]);
        assert_eq!(report.refused, 1);
        assert_eq!(decisions.len(), 1); // the good one still decided
        assert_eq!(report.committed, 1);
    }

    #[test]
    fn bounded_cortex_caps_learned_memory() {
        let mut cortex = Cortex::bounded(2);
        let reqs: Vec<CortexRequest> = std::iter::repeat_with(req).take(5).collect();
        let (_decisions, report) = cortex.run_session(&reqs);
        assert_eq!(report.committed, 5);
        assert_eq!(report.learned, 5);
        // despite learning 5, the bound holds
        assert!(
            cortex.memory.len() <= 2,
            "bounded to 2, got {}",
            cortex.memory.len()
        );
    }

    #[test]
    fn maintain_ages_stale_learned_memory() {
        let mut cortex = Cortex::new();
        let r = req(); // freshness of learned memory = req.now (100)
        let d = cortex.tick(&r).unwrap();
        assert!(cortex.learn(&r, &d));
        // far in the future relative to ttl → the memory ages out
        let aged = cortex.maintain(10_000, 100);
        assert_eq!(aged, 1);
        // idempotent: already-suspect memory is not re-aged
        assert_eq!(cortex.maintain(10_000, 100), 0);
    }

    // --- embedding-rerank semantic boost ---

    #[test]
    fn query_embedding_adds_semantic_boost() {
        // A readable memory carrying an embedding, matching the recall topic.
        let mut store = MemoryStore::new();
        store.admit(
            HotMeta::new(
                1,
                MemoryType::Semantic,
                0,
                0,
                800,
                100,
                0b1111,
                0b0001,
                700,
                FLAG_READABLE,
            ),
            GroundTruth {
                raw_episode: "e".into(),
                derived_facts: vec![],
                summary: "s".into(),
                graph_edges: vec![],
                embedding: vec![1.0, 0.0],
                trust: 800,
                freshness: 100,
                summary_suspect: false,
            },
        );
        let cortex = Cortex::with_memory(store);

        let mut base = req();
        base.reward.evidence = 0.4;
        base.reward.confidence_calibration = 0.5;
        let mut with_emb = base.clone();
        with_emb.query_embedding = vec![1.0, 0.0]; // aligned with the memory

        let plain = cortex.tick(&base).unwrap();
        let semantic = cortex.tick(&with_emb).unwrap();
        assert!(
            semantic.assessment.step_score > plain.assessment.step_score,
            "semantic match should boost the verdict: {} vs {}",
            semantic.assessment.step_score,
            plain.assessment.step_score
        );
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

        // M007 branch tree: root + 3 candidates; winner committed, rest pruned.
        use sovereign_branch_tree::BranchState as BState;
        assert_eq!(d.branches.len(), 4);
        assert_eq!(
            d.branches.get(best.branch_id + 1).unwrap().state,
            BState::Committed
        );
        let pruned = (1..=3u64)
            .filter(|&bid| d.branches.get(bid).unwrap().state == BState::Pruned)
            .count();
        assert_eq!(pruned, 2, "the two non-winners should be pruned");
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

    // --- iterative search loop ---

    fn perfect_reward() -> RewardVector {
        RewardVector {
            correctness: 1.0,
            evidence: 1.0,
            schema_validity: 1.0,
            tool_success: 1.0,
            test_success: 1.0,
            risk: 0.0,
            latency: 0.0,
            cost: 0.0,
            novelty: 1.0,
            user_preference: 1.0,
            cache_reuse: 1.0,
            confidence_calibration: 0.99,
        }
    }

    /// Expander that returns one fully-strong candidate — convergence.
    struct Improver;
    impl BranchExpander for Improver {
        fn expand(&self, _best: &BranchAssessment, _round: u32) -> Vec<RewardVector> {
            vec![perfect_reward()]
        }
    }

    /// Expander that never improves — always an uncertain candidate.
    struct Stuck;
    impl BranchExpander for Stuck {
        fn expand(&self, _best: &BranchAssessment, _round: u32) -> Vec<RewardVector> {
            vec![graded_reward(0.7, 0.2)]
        }
    }

    /// Expander with nothing left to try.
    struct Exhausted;
    impl BranchExpander for Exhausted {
        fn expand(&self, _best: &BranchAssessment, _round: u32) -> Vec<RewardVector> {
            vec![]
        }
    }

    #[test]
    fn search_converges_to_commit() {
        let cortex = Cortex::new();
        let seed = vec![graded_reward(0.7, 0.2)]; // uncertain start
        let out = cortex
            .search(&req(), &seed, IntelligenceTier::Deliberate, &Improver)
            .unwrap();
        assert!(out.committed, "should converge: {}", out.summary);
        assert!(out.rounds >= 1, "should take at least one expansion round");
        assert!(out.final_best.is_some());
        // history records a winner per round
        assert_eq!(out.history.len() as u32, out.rounds + 1);
    }

    #[test]
    fn search_respects_tier_fanout_budget() {
        let cortex = Cortex::new();
        let seed = vec![graded_reward(0.7, 0.2)];
        // Normal tier fanout = 4 → stops once round reaches the budget.
        let out = cortex
            .search(&req(), &seed, IntelligenceTier::Normal, &Stuck)
            .unwrap();
        assert!(!out.committed);
        assert_eq!(out.rounds, IntelligenceTier::Normal.fanout());
    }

    #[test]
    fn search_stops_when_expander_exhausted() {
        let cortex = Cortex::new();
        let seed = vec![graded_reward(0.7, 0.2)];
        let out = cortex
            .search(&req(), &seed, IntelligenceTier::Deliberate, &Exhausted)
            .unwrap();
        assert_eq!(out.rounds, 0); // never got a second round
        assert!(!out.committed);
        assert!(out.final_best.is_some()); // the seed branch survived
    }

    #[test]
    fn search_empty_seed_is_error() {
        let err = Cortex::new()
            .search(&req(), &[], IntelligenceTier::Normal, &Improver)
            .unwrap_err();
        assert!(matches!(err, CortexError::NoCandidates));
    }

    #[test]
    fn search_commits_immediately_on_strong_seed() {
        let cortex = Cortex::new();
        let out = cortex
            .search(
                &req(),
                &[perfect_reward()],
                IntelligenceTier::Deliberate,
                &Exhausted,
            )
            .unwrap();
        assert!(out.committed);
        assert_eq!(out.rounds, 0); // committed on the seed, no expansion
    }

    // --- Trinity gate execution ---

    #[test]
    fn act_commits_through_trinity_when_value_plane_commits() {
        let cortex = Cortex::with_memory(seed_memory());
        let (decision, cycle) = cortex.act(&req()).unwrap();
        // strong local request → value plane Commit → Auditor ratifies
        assert_eq!(
            decision.assessment.suggested_next_action,
            NextAction::Commit
        );
        assert!(
            cycle.committed(),
            "trinity should commit: {:?}",
            cycle.stage
        );
        assert_eq!(cycle.reports.len(), 3);
    }

    #[test]
    fn execute_rejects_when_value_plane_does_not_commit() {
        let cortex = Cortex::new();
        // weak/uncertain → Expand or NeedMoreCompute, not Commit
        let mut r = req();
        r.reward.confidence_calibration = 0.2; // high uncertainty
        let decision = cortex.tick(&r).unwrap();
        assert_ne!(
            decision.assessment.suggested_next_action,
            NextAction::Commit
        );
        let cycle = cortex.execute(&decision);
        assert!(!cycle.committed()); // Auditor refuses to ratify
    }

    #[test]
    fn execute_rejects_cloud_spilled_work_at_pulse() {
        let cortex = Cortex::new();
        // FP16 deep job, Oracle overloaded, cloud allowed → spills to cloud
        let mut r = demo_requests().remove(1);
        r.oracle = RolePressure::overloaded();
        r.allow_cloud = true;
        let decision = cortex.tick(&r).unwrap();
        assert!(decision.placement.spilled_to_cloud);
        let cycle = cortex.execute(&decision);
        // local Trinity Pulse can't run remote work → rejected, only 1 report
        assert!(!cycle.committed());
        assert_eq!(cycle.reports.len(), 1);
    }

    #[test]
    fn recall_text_returns_ground_truth_for_a_matching_query() {
        // Admit one memory keyed on the sketch of a known phrase, then recall it
        // by that phrase — proving the string→sketch→retrieve→ground-truth path.
        let mut store = MemoryStore::new();
        let bits = text_sketch("blackwell gpu bringup");
        store.admit(
            HotMeta::new(
                42,
                MemoryType::Semantic,
                0,
                0,
                900,
                100,
                bits,
                bits.rotate_left(29),
                800,
                FLAG_READABLE,
            ),
            GroundTruth {
                raw_episode: "the RTX PRO 6000 Blackwell bringup notes".into(),
                derived_facts: vec![],
                summary: "gpu bringup summary".into(),
                graph_edges: vec![],
                embedding: vec![],
                trust: 900,
                freshness: 100,
                summary_suspect: false,
            },
        );
        let cortex = Cortex {
            memory: store,
            ..Default::default()
        };
        let hits = cortex.recall_text("blackwell gpu bringup", 100, 1000, 3);
        assert!(
            hits.iter().any(|h| h.contains("gpu bringup")),
            "expected the seeded memory back, got {hits:?}"
        );
    }

    #[test]
    fn recall_text_is_empty_on_an_empty_store() {
        let cortex = Cortex::default();
        assert!(cortex.recall_text("anything", 100, 1000, 3).is_empty());
    }
}
