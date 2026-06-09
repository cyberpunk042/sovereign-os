//! `sovereign-worker-fleet` — fleet health summary over worker status words.
//!
//! The [`WorkerStatusWord`] (M00212) encodes one worker's live state into a
//! `u64`. A scheduler or cockpit watching many workers needs the *fleet*
//! picture: the worst pressure on each axis, how many workers are erroring,
//! and a single fleet verdict. This is a pure, read-only aggregation over a
//! slice of status words — the workers produce the words; this summarises them.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_worker_status_word::WorkerStatusWord;

/// Fleet-wide pressure verdict, by the worst per-axis pressure across workers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FleetVerdict {
    /// No workers (an empty fleet).
    Empty,
    /// All measured pressures below the elevated threshold.
    Healthy,
    /// Some axis crossed the elevated threshold (busy but coping).
    Elevated,
    /// Some axis crossed the saturated threshold, or a worker is erroring.
    Saturated,
}

/// Thresholds (on the 0..=255 status-word byte scale) for the verdict.
#[derive(Debug, Clone, Copy)]
pub struct FleetThresholds {
    /// A pressure byte at or above this is "elevated". Default 160 (~63%).
    pub elevated: u8,
    /// A pressure byte at or above this is "saturated". Default 224 (~88%).
    pub saturated: u8,
}

impl Default for FleetThresholds {
    fn default() -> Self {
        Self {
            elevated: 160,
            saturated: 224,
        }
    }
}

/// Aggregated fleet health over a set of worker status words.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FleetSummary {
    /// Number of workers in the fleet.
    pub worker_count: usize,
    /// Worst (max) load bucket across the fleet.
    pub max_load: u8,
    /// Worst (max) memory pressure across the fleet.
    pub max_memory_pressure: u8,
    /// Worst (max) thermal pressure across the fleet.
    pub max_thermal_pressure: u8,
    /// Worst (max) queue depth across the fleet.
    pub max_queue_depth: u8,
    /// Count of workers reporting a non-zero error state.
    pub workers_in_error: usize,
    /// Count of workers with any flag bit set.
    pub workers_flagged: usize,
    /// The fleet pressure verdict.
    pub verdict: FleetVerdict,
}

/// Summarise a fleet from its workers' status words.
#[must_use]
pub fn summarise(workers: &[WorkerStatusWord], th: FleetThresholds) -> FleetSummary {
    if workers.is_empty() {
        return FleetSummary {
            worker_count: 0,
            max_load: 0,
            max_memory_pressure: 0,
            max_thermal_pressure: 0,
            max_queue_depth: 0,
            workers_in_error: 0,
            workers_flagged: 0,
            verdict: FleetVerdict::Empty,
        };
    }

    let max_load = workers.iter().map(|w| w.load_bucket).max().unwrap_or(0);
    let max_memory_pressure = workers.iter().map(|w| w.memory_pressure).max().unwrap_or(0);
    let max_thermal_pressure = workers.iter().map(|w| w.thermal_pressure).max().unwrap_or(0);
    let max_queue_depth = workers.iter().map(|w| w.queue_depth).max().unwrap_or(0);
    let workers_in_error = workers.iter().filter(|w| w.error_state != 0).count();
    let workers_flagged = workers.iter().filter(|w| w.flags != 0).count();

    let worst_pressure = max_load
        .max(max_memory_pressure)
        .max(max_thermal_pressure)
        .max(max_queue_depth);
    let verdict = if workers_in_error > 0 || worst_pressure >= th.saturated {
        FleetVerdict::Saturated
    } else if worst_pressure >= th.elevated {
        FleetVerdict::Elevated
    } else {
        FleetVerdict::Healthy
    };

    FleetSummary {
        worker_count: workers.len(),
        max_load,
        max_memory_pressure,
        max_thermal_pressure,
        max_queue_depth,
        workers_in_error,
        workers_flagged,
        verdict,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn worker(load: u8, mem: u8, thermal: u8, queue: u8, error: u8, flags: u8) -> WorkerStatusWord {
        WorkerStatusWord {
            load_bucket: load,
            memory_pressure: mem,
            thermal_pressure: thermal,
            queue_depth: queue,
            error_state: error,
            health: 0,
            policy_mode: 0,
            flags,
        }
    }

    #[test]
    fn empty_fleet_is_empty_verdict() {
        let s = summarise(&[], FleetThresholds::default());
        assert_eq!(s.verdict, FleetVerdict::Empty);
        assert_eq!(s.worker_count, 0);
    }

    #[test]
    fn healthy_fleet_below_elevated() {
        let s = summarise(
            &[worker(10, 20, 30, 5, 0, 0), worker(50, 40, 10, 8, 0, 0)],
            FleetThresholds::default(),
        );
        assert_eq!(s.verdict, FleetVerdict::Healthy);
        assert_eq!(s.worker_count, 2);
        assert_eq!(s.max_load, 50);
        assert_eq!(s.max_memory_pressure, 40);
    }

    #[test]
    fn elevated_when_an_axis_crosses_elevated() {
        // one worker's thermal hits 200 (>= elevated 160, < saturated 224)
        let s = summarise(
            &[worker(10, 10, 200, 10, 0, 0)],
            FleetThresholds::default(),
        );
        assert_eq!(s.verdict, FleetVerdict::Elevated);
        assert_eq!(s.max_thermal_pressure, 200);
    }

    #[test]
    fn saturated_when_an_axis_crosses_saturated() {
        let s = summarise(&[worker(240, 10, 10, 10, 0, 0)], FleetThresholds::default());
        assert_eq!(s.verdict, FleetVerdict::Saturated);
    }

    #[test]
    fn saturated_when_any_worker_errors_regardless_of_pressure() {
        // low pressure everywhere, but one worker has an error → Saturated.
        let s = summarise(
            &[worker(5, 5, 5, 5, 0, 0), worker(5, 5, 5, 5, 7, 0)],
            FleetThresholds::default(),
        );
        assert_eq!(s.verdict, FleetVerdict::Saturated);
        assert_eq!(s.workers_in_error, 1);
    }

    #[test]
    fn aggregates_maxes_and_counts() {
        let s = summarise(
            &[
                worker(10, 90, 30, 5, 0, 0b0001),
                worker(70, 40, 80, 60, 0, 0),
                worker(20, 20, 20, 20, 3, 0b1000),
            ],
            FleetThresholds::default(),
        );
        assert_eq!(s.max_load, 70);
        assert_eq!(s.max_memory_pressure, 90);
        assert_eq!(s.max_thermal_pressure, 80);
        assert_eq!(s.max_queue_depth, 60);
        assert_eq!(s.workers_in_error, 1);
        assert_eq!(s.workers_flagged, 2);
    }

    #[test]
    fn verdict_serializes_kebab() {
        let s = summarise(&[worker(240, 0, 0, 0, 0, 0)], FleetThresholds::default());
        let j = serde_json::to_value(&s).unwrap();
        assert_eq!(j["verdict"], "saturated");
    }

    #[test]
    fn summary_roundtrips_from_packed_words() {
        // Build workers via the status-word pack/unpack to prove the fleet
        // view composes with the M00212 wire format.
        let packed: Vec<u64> = vec![
            worker(100, 100, 100, 10, 0, 0).pack(),
            worker(200, 50, 50, 50, 0, 0).pack(),
        ];
        let workers: Vec<WorkerStatusWord> =
            packed.into_iter().map(WorkerStatusWord::unpack).collect();
        let s = summarise(&workers, FleetThresholds::default());
        assert_eq!(s.max_load, 200);
        assert_eq!(s.verdict, FleetVerdict::Elevated); // 200 >= 160, < 224
    }
}
