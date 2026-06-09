//! `sovereign-zfs-snapshot-policy` — M068 E0667: ZFS snapshot retention.
//!
//! Snapshots are the rollback floor for the substrate. The catalogue fixes four
//! retention classes (F05731-F05737):
//!
//! | class | source | retention |
//! |-------|--------|-----------|
//! | **pre-commit** | every M041 high-risk commit, named `selfdef-pre-commit-<id>` | 365 days minimum |
//! | **daily** | `zfs-auto-snapshot` daily of tank/context | 30 days |
//! | **weekly** | weekly auto-snapshot | 90 days |
//! | **monthly** | monthly auto-snapshot | 365 days |
//!
//! This crate classifies a snapshot by its name and decides — purely, from a
//! caller-supplied `now` — which snapshots are past their window and may be
//! pruned. Two safety rules are load-bearing:
//!
//! 1. **An unclassifiable snapshot is never pruned** (returns
//!    [`SnapshotClass::Unknown`], which has no retention window). Operators or
//!    other tooling may have created it; the replay validator (F05745) treats
//!    unauthorized deletion as an incident, so the planner must not delete what
//!    it does not understand.
//! 2. **"365 days minimum"** for pre-commit/monthly means a snapshot is prunable
//!    only once it is *strictly older* than its window — never on the boundary.
//!
//! It does NOT run `zfs destroy`; it produces a [`PrunePlan`] the rollback /
//! retention binary executes (so the decision is testable without a pool).
//!
//! Retention windows are verbatim from F05733/F05735/F05736/F05737; none are
//! invented.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Seconds in a day.
const DAY_SECS: i64 = 86_400;

/// A snapshot's retention class (F05731-F05737).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SnapshotClass {
    /// Pre-commit snapshot from an M041 high-risk commit
    /// (`selfdef-pre-commit-<commit-id>`).
    PreCommit,
    /// Daily auto-snapshot.
    Daily,
    /// Weekly auto-snapshot.
    Weekly,
    /// Monthly auto-snapshot.
    Monthly,
    /// Not a recognized policy snapshot — never auto-pruned.
    Unknown,
}

impl SnapshotClass {
    /// The retention window in days, or `None` for [`SnapshotClass::Unknown`]
    /// (no window ⇒ never auto-pruned).
    #[must_use]
    pub const fn retention_days(self) -> Option<u32> {
        match self {
            SnapshotClass::PreCommit => Some(365), // F05733 — 365-day minimum
            SnapshotClass::Daily => Some(30),      // F05735
            SnapshotClass::Weekly => Some(90),     // F05736
            SnapshotClass::Monthly => Some(365),   // F05737
            SnapshotClass::Unknown => None,
        }
    }

    /// Classify a snapshot from its name (the part after `@`, or the whole
    /// string). Case-insensitive substring match against the catalogued naming
    /// conventions; pre-commit is checked first because it is the most specific.
    #[must_use]
    pub fn classify(name: &str) -> SnapshotClass {
        // Use only the snapshot component if a full `dataset@snap` was passed.
        let snap = name.rsplit('@').next().unwrap_or(name).to_ascii_lowercase();
        if snap.contains("pre-commit") {
            SnapshotClass::PreCommit
        } else if snap.contains("monthly") {
            SnapshotClass::Monthly
        } else if snap.contains("weekly") {
            SnapshotClass::Weekly
        } else if snap.contains("daily") {
            SnapshotClass::Daily
        } else {
            SnapshotClass::Unknown
        }
    }
}

/// One snapshot's identity + creation time (unix epoch seconds).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SnapshotMeta {
    /// Full ZFS snapshot name, e.g. `tank/context@selfdef-pre-commit-abc123`.
    pub name: String,
    /// Creation time, unix epoch seconds (from `zfs get -p creation`).
    pub created_epoch: i64,
}

/// The decision for one snapshot.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SnapshotDecision {
    /// The snapshot name.
    pub name: String,
    /// Its classification.
    pub class: SnapshotClass,
    /// Age in whole days at `now`.
    pub age_days: i64,
    /// Whether it is past its retention window and may be pruned.
    pub prune: bool,
}

/// Age of a snapshot in whole days at `now`. Negative (a `created_epoch` in the
/// future, e.g. clock skew) clamps to 0 — a future-dated snapshot is treated as
/// brand new, never prunable.
#[must_use]
pub fn age_days(created_epoch: i64, now_epoch: i64) -> i64 {
    let delta = now_epoch - created_epoch;
    if delta <= 0 { 0 } else { delta / DAY_SECS }
}

/// Decide whether a single snapshot of `class` at `age_days` is prunable.
/// Prunable iff the class has a window AND the snapshot is *strictly older*
/// than it (the "minimum" retention is inclusive of the boundary day).
#[must_use]
pub fn is_prunable(class: SnapshotClass, age_days: i64) -> bool {
    match class.retention_days() {
        Some(window) => age_days > i64::from(window),
        None => false,
    }
}

/// A full prune plan: every snapshot's decision, partitioned for the caller.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PrunePlan {
    /// Per-snapshot decisions, in input order.
    pub decisions: Vec<SnapshotDecision>,
}

impl PrunePlan {
    /// Names of snapshots safe to `zfs destroy`.
    #[must_use]
    pub fn to_prune(&self) -> Vec<&str> {
        self.decisions
            .iter()
            .filter(|d| d.prune)
            .map(|d| d.name.as_str())
            .collect()
    }

    /// Names of snapshots to keep.
    #[must_use]
    pub fn to_keep(&self) -> Vec<&str> {
        self.decisions
            .iter()
            .filter(|d| !d.prune)
            .map(|d| d.name.as_str())
            .collect()
    }

    /// How many snapshots the plan would prune.
    #[must_use]
    pub fn prune_count(&self) -> usize {
        self.decisions.iter().filter(|d| d.prune).count()
    }
}

/// Build a prune plan for a set of snapshots, evaluated at `now_epoch`.
#[must_use]
pub fn plan_pruning(snapshots: &[SnapshotMeta], now_epoch: i64) -> PrunePlan {
    let decisions = snapshots
        .iter()
        .map(|s| {
            let class = SnapshotClass::classify(&s.name);
            let age = age_days(s.created_epoch, now_epoch);
            SnapshotDecision {
                name: s.name.clone(),
                class,
                age_days: age,
                prune: is_prunable(class, age),
            }
        })
        .collect();
    PrunePlan { decisions }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn days(n: i64) -> i64 {
        n * DAY_SECS
    }

    #[test]
    fn classify_matches_naming_conventions() {
        assert_eq!(
            SnapshotClass::classify("tank/context@selfdef-pre-commit-abc123"),
            SnapshotClass::PreCommit
        );
        assert_eq!(
            SnapshotClass::classify("tank/context@zfs-auto-snap_daily-2026-06-09-0000"),
            SnapshotClass::Daily
        );
        assert_eq!(
            SnapshotClass::classify("tank/context@zfs-auto-snap_weekly-2026-06-07"),
            SnapshotClass::Weekly
        );
        assert_eq!(
            SnapshotClass::classify("tank/context@zfs-auto-snap_monthly-2026-06-01"),
            SnapshotClass::Monthly
        );
        assert_eq!(
            SnapshotClass::classify("tank/models@operator-adhoc-thing"),
            SnapshotClass::Unknown
        );
    }

    #[test]
    fn retention_windows_are_the_catalogued_values() {
        assert_eq!(SnapshotClass::PreCommit.retention_days(), Some(365));
        assert_eq!(SnapshotClass::Daily.retention_days(), Some(30));
        assert_eq!(SnapshotClass::Weekly.retention_days(), Some(90));
        assert_eq!(SnapshotClass::Monthly.retention_days(), Some(365));
        assert_eq!(SnapshotClass::Unknown.retention_days(), None);
    }

    #[test]
    fn age_clamps_future_dated_to_zero() {
        assert_eq!(age_days(1000, 1000 + days(5)), 5);
        assert_eq!(age_days(1000, 1000), 0);
        assert_eq!(age_days(1000 + days(3), 1000), 0); // future-dated → 0
    }

    #[test]
    fn boundary_is_inclusive_minimum() {
        // Daily window is 30 days: at exactly 30 days, keep; at 31, prune.
        assert!(!is_prunable(SnapshotClass::Daily, 30));
        assert!(is_prunable(SnapshotClass::Daily, 31));
        // Pre-commit 365-day minimum: 365 keep, 366 prune.
        assert!(!is_prunable(SnapshotClass::PreCommit, 365));
        assert!(is_prunable(SnapshotClass::PreCommit, 366));
    }

    #[test]
    fn unknown_is_never_prunable_even_when_ancient() {
        assert!(!is_prunable(SnapshotClass::Unknown, 100_000));
    }

    #[test]
    fn plan_partitions_keep_and_prune() {
        let now = 1_000_000_000;
        let snaps = vec![
            // daily, 40 days old → prune (window 30)
            SnapshotMeta {
                name: "tank/context@zfs-auto-snap_daily-x".into(),
                created_epoch: now - days(40),
            },
            // daily, 10 days old → keep
            SnapshotMeta {
                name: "tank/context@zfs-auto-snap_daily-y".into(),
                created_epoch: now - days(10),
            },
            // pre-commit, 400 days old → prune (window 365)
            SnapshotMeta {
                name: "tank/context@selfdef-pre-commit-old".into(),
                created_epoch: now - days(400),
            },
            // pre-commit, 100 days old → keep
            SnapshotMeta {
                name: "tank/context@selfdef-pre-commit-new".into(),
                created_epoch: now - days(100),
            },
            // unknown, ancient → keep (never pruned)
            SnapshotMeta {
                name: "tank/models@adhoc".into(),
                created_epoch: now - days(9999),
            },
        ];
        let plan = plan_pruning(&snaps, now);
        assert_eq!(plan.prune_count(), 2);
        assert_eq!(
            plan.to_prune(),
            vec![
                "tank/context@zfs-auto-snap_daily-x",
                "tank/context@selfdef-pre-commit-old"
            ]
        );
        assert!(plan.to_keep().contains(&"tank/models@adhoc"));
        assert!(
            plan.to_keep()
                .contains(&"tank/context@selfdef-pre-commit-new")
        );
    }

    #[test]
    fn serde_kebab_class() {
        assert_eq!(
            serde_json::to_string(&SnapshotClass::PreCommit).unwrap(),
            "\"pre-commit\""
        );
        assert_eq!(
            serde_json::to_string(&SnapshotClass::Unknown).unwrap(),
            "\"unknown\""
        );
    }
}
