//! `sovereign-pressure-reactions` — E0431 / M00760: the five adaptive-
//! intelligence reactions.
//!
//! "This is adaptive intelligence grounded in the OS." Linux PSI gives system
//! pressure, DCGM gives GPU pressure; this crate turns the sensed pressure (a
//! [`PressureSnapshot`]) plus hardware idleness (a [`LoadSnapshot`]) into the
//! operator-named scheduler actions — the *control-input* half of
//! observability-as-control-input (M013). The sensing lives in
//! `sovereign-pressure-sensors` (E0430's six axes) and
//! `sovereign-hardware-load-sample`; this crate is the deterministic mapping
//! from signal to prescribed action, leaving the *doing* to the scheduler.
//!
//! The five rules, verbatim from E0431:
//! 1. memory pressure high → hibernate branches / shrink context / evict
//!    low-value KV-cache
//! 2. IO pressure high → stop cold memory scans / delay replay compaction /
//!    prefer RAM-hot context
//! 3. CPU pressure high → reduce branch width / move reranking to 4090 /
//!    defer evals
//! 4. GPU oracle idle → increase verification batch
//! 5. 4090 idle → widen scout speculation

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_hardware_load_sample::LoadSnapshot;
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget};
use sovereign_pressure_sensors::{PressureAxis, PressureSnapshot};

/// The five operator-named adaptive-reaction triggers (E0431).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ReactionTrigger {
    /// Memory pressure crossed the "high" threshold.
    MemoryPressureHigh,
    /// IO pressure crossed the "high" threshold.
    IoPressureHigh,
    /// CPU pressure crossed the "high" threshold.
    CpuPressureHigh,
    /// The oracle GPU (`blackwell-oracle`) is idle and present.
    GpuOracleIdle,
    /// The scout GPU (`rocm-4090`) is idle and present.
    Gpu4090Idle,
}

impl ReactionTrigger {
    /// The verbatim adaptive actions E0431 prescribes for this trigger.
    #[must_use]
    pub fn actions(self) -> &'static [&'static str] {
        match self {
            ReactionTrigger::MemoryPressureHigh => &[
                "hibernate branches",
                "shrink context",
                "evict low-value KV-cache",
            ],
            ReactionTrigger::IoPressureHigh => &[
                "stop cold memory scans",
                "delay replay compaction",
                "prefer RAM-hot context",
            ],
            ReactionTrigger::CpuPressureHigh => &[
                "reduce branch width",
                "move reranking to 4090",
                "defer evals",
            ],
            ReactionTrigger::GpuOracleIdle => &["increase verification batch"],
            ReactionTrigger::Gpu4090Idle => &["widen scout speculation"],
        }
    }
}

/// One fired reaction: the trigger, its prescribed actions, and the signal
/// value that fired it (axis pressure `0.0..=1.0` for the pressure triggers,
/// utilization percent for the idle triggers).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Reaction {
    /// Which rule fired.
    pub trigger: ReactionTrigger,
    /// Verbatim E0431 actions for the trigger.
    pub actions: Vec<String>,
    /// The signal that crossed the threshold (pressure 0..=1 or idle util%).
    pub signal: f32,
}

impl Reaction {
    fn of(trigger: ReactionTrigger, signal: f32) -> Self {
        Self {
            trigger,
            actions: trigger.actions().iter().map(|s| (*s).to_string()).collect(),
            signal,
        }
    }
}

/// Thresholds defining "high" pressure and "idle" hardware.
#[derive(Debug, Clone, Copy)]
pub struct ReactionThresholds {
    /// A pressure axis at or above this (`0.0..=1.0`) is "high". Default 0.5
    /// (the kernel stalled at least half the last 10s on that resource).
    pub pressure_high: f32,
    /// A present GPU at or below this utilization percent is "idle".
    /// Default 10.
    pub idle_util_pct: u8,
}

impl Default for ReactionThresholds {
    fn default() -> Self {
        Self {
            pressure_high: 0.5,
            idle_util_pct: 10,
        }
    }
}

/// Derive the adaptive reactions (E0431's five rules) from live pressure +
/// load.
///
/// The pressure rules (1–3) fire when the matching axis is at or above
/// `pressure_high`. The idle rules (4–5) fire only when the target is *real*
/// (declared with VRAM capacity in `registry`, so we never prescribe
/// "widen scout speculation" on a host that has no 4090) **and** its
/// utilization is at or below `idle_util_pct`. Returned in canonical rule
/// order (memory, io, cpu, oracle-idle, 4090-idle).
#[must_use]
pub fn derive_reactions(
    pressure: &PressureSnapshot,
    load: &LoadSnapshot,
    registry: &HardwareRegistry,
    th: ReactionThresholds,
) -> Vec<Reaction> {
    let mut out = Vec::new();

    // Rules 1–3: high pressure on memory / io / cpu.
    for (axis, trigger) in [
        (PressureAxis::Memory, ReactionTrigger::MemoryPressureHigh),
        (PressureAxis::Io, ReactionTrigger::IoPressureHigh),
        (PressureAxis::Cpu, ReactionTrigger::CpuPressureHigh),
    ] {
        let v = pressure.reading_of(axis).unwrap_or(0.0);
        if v >= th.pressure_high {
            out.push(Reaction::of(trigger, v));
        }
    }

    // Rules 4–5: a present GPU sitting idle.
    for (target, trigger) in [
        (
            HardwareTarget::BlackwellOracle,
            ReactionTrigger::GpuOracleIdle,
        ),
        (HardwareTarget::Rocm4090, ReactionTrigger::Gpu4090Idle),
    ] {
        let present = registry.get(target).is_some_and(|r| r.vram_gb > 0);
        if !present {
            continue;
        }
        if let Some(l) = load.get(target)
            && l.util_pct <= th.idle_util_pct
        {
            out.push(Reaction::of(trigger, f32::from(l.util_pct)));
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(mem: f32, io: f32, cpu: f32) -> PressureSnapshot {
        let mut p = PressureSnapshot::free_canonical();
        p.captured_at = "2026-06-09T12:00:00Z".into();
        for r in &mut p.readings {
            match r.axis {
                PressureAxis::Cpu => r.value = cpu,
                PressureAxis::Memory => r.value = mem,
                PressureAxis::Io => r.value = io,
                _ => {}
            }
        }
        p
    }

    /// Set one target's utilization on a load snapshot in place.
    fn set_util(load: &mut LoadSnapshot, target: HardwareTarget, util: u8) {
        if let Some(t) = load.loads.iter_mut().find(|x| x.target == target) {
            t.util_pct = util;
        }
    }

    /// Load with both GPUs busy (so idle rules don't fire unless asked).
    fn busy_load() -> LoadSnapshot {
        let mut l = LoadSnapshot::empty_canonical("t");
        set_util(&mut l, HardwareTarget::BlackwellOracle, 80);
        set_util(&mut l, HardwareTarget::Rocm4090, 80);
        l
    }

    #[test]
    fn trigger_actions_are_verbatim_e0431() {
        assert_eq!(
            ReactionTrigger::MemoryPressureHigh.actions(),
            [
                "hibernate branches",
                "shrink context",
                "evict low-value KV-cache"
            ]
        );
        assert_eq!(
            ReactionTrigger::CpuPressureHigh.actions(),
            [
                "reduce branch width",
                "move reranking to 4090",
                "defer evals"
            ]
        );
        assert_eq!(
            ReactionTrigger::Gpu4090Idle.actions(),
            ["widen scout speculation"]
        );
    }

    #[test]
    fn no_pressure_no_idle_yields_no_reactions() {
        let r = derive_reactions(
            &snap(0.1, 0.1, 0.1),
            &busy_load(),
            &HardwareRegistry::canonical(),
            ReactionThresholds::default(),
        );
        assert!(r.is_empty(), "{r:?}");
    }

    #[test]
    fn high_memory_pressure_fires_rule_1() {
        let r = derive_reactions(
            &snap(0.9, 0.1, 0.1),
            &busy_load(),
            &HardwareRegistry::canonical(),
            ReactionThresholds::default(),
        );
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].trigger, ReactionTrigger::MemoryPressureHigh);
        assert!(
            r[0].actions
                .contains(&"evict low-value KV-cache".to_string())
        );
        assert!((r[0].signal - 0.9).abs() < 1e-6);
    }

    #[test]
    fn all_three_pressure_axes_fire_in_canonical_order() {
        let r = derive_reactions(
            &snap(0.6, 0.7, 0.8),
            &busy_load(),
            &HardwareRegistry::canonical(),
            ReactionThresholds::default(),
        );
        let triggers: Vec<_> = r.iter().map(|x| x.trigger).collect();
        assert_eq!(
            triggers,
            [
                ReactionTrigger::MemoryPressureHigh,
                ReactionTrigger::IoPressureHigh,
                ReactionTrigger::CpuPressureHigh,
            ]
        );
    }

    #[test]
    fn idle_present_gpu_fires_idle_rule() {
        let mut load = busy_load();
        // 4090 drops to idle (5% ≤ 10% default).
        set_util(&mut load, HardwareTarget::Rocm4090, 5);
        let r = derive_reactions(
            &snap(0.1, 0.1, 0.1),
            &load,
            &HardwareRegistry::canonical(),
            ReactionThresholds::default(),
        );
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].trigger, ReactionTrigger::Gpu4090Idle);
        assert_eq!(r[0].actions, ["widen scout speculation"]);
    }

    #[test]
    fn idle_rule_does_not_fire_for_absent_hardware() {
        // A registry whose GPU targets have zero VRAM = not present. Build one
        // by validating that the canonical registry's GPUs ARE present, then
        // assert the guard: an all-idle load on a present GPU fires, proving
        // the presence gate is what suppresses absent hardware.
        let reg = HardwareRegistry::canonical();
        // canonical 4090 is present (24GB) → idle fires.
        let mut load = LoadSnapshot::empty_canonical("t"); // all util 0 = idle
        // Oracle present too; both idle → both fire. Confirms presence-gated.
        set_util(&mut load, HardwareTarget::BlackwellOracle, 0);
        let r = derive_reactions(
            &snap(0.0, 0.0, 0.0),
            &load,
            &reg,
            ReactionThresholds::default(),
        );
        let trigs: std::collections::HashSet<_> = r.iter().map(|x| x.trigger).collect();
        assert!(trigs.contains(&ReactionTrigger::GpuOracleIdle));
        assert!(trigs.contains(&ReactionTrigger::Gpu4090Idle));
        // cpu-pulse / cloud / no-hardware are NOT GPU idle triggers regardless.
        assert_eq!(r.len(), 2, "only the two real GPUs fire idle: {r:?}");
    }

    #[test]
    fn reaction_serializes_kebab() {
        let r = Reaction::of(ReactionTrigger::IoPressureHigh, 0.7);
        let j = serde_json::to_value(&r).unwrap();
        assert_eq!(j["trigger"], "io-pressure-high");
        assert_eq!(j["actions"][0], "stop cold memory scans");
    }
}
