//! `sovereign-zfs-snapshot-policy` CLI — the runnable end of M068 / E0667.
//!
//! The library fixes the ZFS snapshot retention policy (four retention classes
//! with catalogued windows, F05731-F05737) and a pure prune planner that keeps
//! anything younger than its window and never prunes an unclassifiable snapshot.
//! But nothing *ran* it, so the policy could neither be turned into deployable
//! systemd units nor exercised against a real snapshot inventory at the command
//! line. This binary is that runnable end — a config tool that needs no live ZFS
//! host: it emits the canonical snapshot units and, given an inventory, computes
//! the `zfs destroy` plan the retention binary would execute.
//!
//! Modes:
//!   * default (no args) — **emit** the canonical snapshot systemd units: a
//!     `.timer` + `.service` pair per cadence class (daily / weekly / monthly)
//!     that creates snapshots named so the library's `classify()` recognises
//!     them, each preceded by the `/etc/systemd/system/…` path it belongs at
//!     (mirroring `sovereign-cpu-pinning`), under a retention-window reference.
//!   * `--check FILE` — load a snapshot inventory (a JSON array of `SnapshotMeta`,
//!     or `{ "now_epoch": …, "snapshots": [ … ] }` for a deterministic what-if),
//!     run the pure `plan_pruning()`, print the keep/prune report and the concrete
//!     `zfs destroy` commands, and exit non-zero on read/parse error, a duplicate
//!     snapshot name (ZFS names are unique per pool), or any violation of the
//!     never-prune-the-unclassifiable safety rule.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_zfs_snapshot_policy::{
    PrunePlan, SCHEMA_VERSION, SnapshotClass, SnapshotMeta, plan_pruning,
};

/// The dataset the policy snapshots — `tank/context`, per the library's catalogue
/// note ("`zfs-auto-snapshot` daily of tank/context"). The substrate rollback
/// floor lives here.
const DATASET: &str = "tank/context";

/// Every retention class, in catalogue order (mirrors the [`SnapshotClass`] enum;
/// the enum exposes no `ALL`, so it is enumerated here and kept honest by the
/// `every_class_is_listed_in_the_reference` test).
const ALL_CLASSES: [SnapshotClass; 5] = [
    SnapshotClass::PreCommit,
    SnapshotClass::Daily,
    SnapshotClass::Weekly,
    SnapshotClass::Monthly,
    SnapshotClass::Unknown,
];

/// The cadence-driven classes — the ones a `.timer` creates on a schedule.
/// Pre-commit is event-driven (per M041 commit) and Unknown is operator-made, so
/// neither gets a timer.
const CADENCE_CLASSES: [SnapshotClass; 3] = [
    SnapshotClass::Daily,
    SnapshotClass::Weekly,
    SnapshotClass::Monthly,
];

/// The stable kebab-case label for a class — identical to how [`SnapshotClass`]
/// serialises to JSON (kept honest by the `class_label_matches_serde` test).
fn class_label(class: SnapshotClass) -> &'static str {
    match class {
        SnapshotClass::PreCommit => "pre-commit",
        SnapshotClass::Daily => "daily",
        SnapshotClass::Weekly => "weekly",
        SnapshotClass::Monthly => "monthly",
        SnapshotClass::Unknown => "unknown",
    }
}

/// The catalogue feature id that fixes a class (from the library's module doc).
fn class_feature(class: SnapshotClass) -> &'static str {
    match class {
        SnapshotClass::PreCommit => "F05733",
        SnapshotClass::Daily => "F05735",
        SnapshotClass::Weekly => "F05736",
        SnapshotClass::Monthly => "F05737",
        // The safety rule protecting unclassifiable snapshots (replay validator).
        SnapshotClass::Unknown => "F05745",
    }
}

/// A one-line description of where a class's snapshots come from.
fn class_source(class: SnapshotClass) -> &'static str {
    match class {
        SnapshotClass::PreCommit => "every M041 high-risk commit (selfdef-pre-commit-<id>)",
        SnapshotClass::Daily => "zfs-auto-snapshot daily",
        SnapshotClass::Weekly => "zfs-auto-snapshot weekly",
        SnapshotClass::Monthly => "zfs-auto-snapshot monthly",
        SnapshotClass::Unknown => "operator / other tooling — never auto-pruned",
    }
}

/// The systemd `OnCalendar=` expression for a cadence class (its name IS the
/// systemd shortcut: `daily` / `weekly` / `monthly`).
fn on_calendar(class: SnapshotClass) -> &'static str {
    match class {
        SnapshotClass::Daily => "daily",
        SnapshotClass::Weekly => "weekly",
        SnapshotClass::Monthly => "monthly",
        // Non-cadence classes have no schedule.
        SnapshotClass::PreCommit | SnapshotClass::Unknown => "",
    }
}

/// The snapshot-name prefix a cadence class's service stamps — chosen so the
/// resulting `dataset@<prefix>-<timestamp>` classifies back to this exact class
/// (the drift guard is the `emitted_names_classify_back_to_their_class` test).
fn snap_prefix(class: SnapshotClass) -> &'static str {
    match class {
        SnapshotClass::Daily => "zfs-auto-snap_daily",
        SnapshotClass::Weekly => "zfs-auto-snap_weekly",
        SnapshotClass::Monthly => "zfs-auto-snap_monthly",
        SnapshotClass::PreCommit => "selfdef-pre-commit",
        SnapshotClass::Unknown => "",
    }
}

/// A retention window rendered for humans: `365d`, or `never` for a class with
/// no window (Unknown).
fn window_text(days: Option<u32>) -> String {
    match days {
        Some(d) => format!("{d}d"),
        None => "never".to_string(),
    }
}

/// One emitted systemd unit: the file it belongs at plus its complete body.
struct EmittedUnit {
    /// The install path (`/etc/systemd/system/…`).
    path: String,
    /// The full unit body.
    body: String,
}

/// The canonical snapshot units: a `.timer` + `.service` per cadence class. The
/// service creates a recursive snapshot whose name carries the class's prefix, so
/// the very snapshots these units create are the ones `classify()` recognises.
fn snapshot_units() -> Vec<EmittedUnit> {
    let mut out = Vec::new();
    for class in CADENCE_CLASSES {
        let label = class_label(class);
        let feature = class_feature(class);
        let cal = on_calendar(class);
        let prefix = snap_prefix(class);
        // Cadence classes always have a window; render it for the description.
        let window = window_text(class.retention_days());
        let base = format!("sovereign-zfs-snapshot-{label}");

        out.push(EmittedUnit {
            path: format!("/etc/systemd/system/{base}.timer"),
            body: format!(
                "[Unit]\n\
                 Description=Sovereign ZFS {label} snapshot of {DATASET} (retention {window}, {feature})\n\n\
                 [Timer]\n\
                 OnCalendar={cal}\n\
                 Persistent=true\n\
                 Unit={base}.service\n\n\
                 [Install]\n\
                 WantedBy=timers.target\n"
            ),
        });
        out.push(EmittedUnit {
            path: format!("/etc/systemd/system/{base}.service"),
            body: format!(
                "[Unit]\n\
                 Description=Sovereign ZFS {label} snapshot of {DATASET}\n\n\
                 [Service]\n\
                 Type=oneshot\n\
                 ExecStart=/bin/sh -c '/usr/sbin/zfs snapshot -r {DATASET}@{prefix}-$(date -u +%%Y-%%m-%%d-%%H%%M)'\n"
            ),
        });
    }
    out
}

/// The retention-window reference header (commented), built from the library's
/// `retention_days()` — no window number is hardcoded here.
fn reference_text() -> String {
    let mut s = format!(
        "# sovereign-zfs-snapshot-policy — retention reference (M068 E0667, schema {SCHEMA_VERSION})\n\
         # class        window   source\n"
    );
    for class in ALL_CLASSES {
        s.push_str(&format!(
            "#   {:<10} {:<8} {}\n",
            class_label(class),
            window_text(class.retention_days()),
            class_source(class),
        ));
    }
    s.push_str(
        "#\n\
         # The .timer/.service units below CREATE the daily/weekly/monthly snapshots\n\
         # on cadence. Pruning is age-based: run `--check FILE` to print the zfs\n\
         # destroy plan for a snapshot inventory. Pre-commit snapshots are event-\n\
         # driven (no timer); unclassifiable snapshots are never auto-pruned.\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-zfs-snapshot-policy — ZFS snapshot retention policy (M068 / E0667)\n\n\
     Four retention classes with catalogued windows: pre-commit 365d, daily 30d,\n\
     weekly 90d, monthly 365d. Unclassifiable snapshots are never auto-pruned.\n\n\
     USAGE:\n\
     \x20   sovereign-zfs-snapshot-policy                emit the canonical snapshot .timer/.service units\n\
     \x20   sovereign-zfs-snapshot-policy --check FILE   validate a snapshot inventory & print the prune plan\n\
     \x20   sovereign-zfs-snapshot-policy --help         print this help and exit\n\n\
     Default emits, for each cadence class (daily/weekly/monthly), a systemd timer\n\
     and a oneshot service that runs `zfs snapshot` with a name classify() knows,\n\
     each preceded by its /etc/systemd/system/ install path.\n\n\
     --check FILE loads a JSON array of SnapshotMeta { name, created_epoch }, or an\n\
     object { \"now_epoch\": <secs>, \"snapshots\": [ … ] } for a deterministic run,\n\
     computes plan_pruning(), prints KEEP/PRUNE per snapshot and the concrete\n\
     `zfs destroy` commands, and exits non-zero on a read/parse error, a duplicate\n\
     snapshot name, or any violation of the never-prune-the-unclassifiable rule.\n"
        .to_string()
}

/// A snapshot inventory to check: a bare array of snapshots, or an object that
/// carries an explicit evaluation clock for deterministic what-if runs.
#[derive(Deserialize)]
#[serde(untagged)]
enum Inventory {
    /// `{ "now_epoch": <secs>, "snapshots": [ … ] }`.
    Clocked {
        /// The instant to evaluate retention at (unix epoch seconds).
        now_epoch: i64,
        /// The snapshots to plan.
        snapshots: Vec<SnapshotMeta>,
    },
    /// A bare `[ SnapshotMeta, … ]`, evaluated at the current system time.
    Bare(Vec<SnapshotMeta>),
}

/// The result of checking one inventory: the plan plus the two policy-integrity
/// findings (`--check` exits non-zero if either is non-empty).
struct CheckReport {
    /// The instant retention was evaluated at.
    now: i64,
    /// Number of snapshots in the inventory.
    total: usize,
    /// The pure prune plan.
    plan: PrunePlan,
    /// Snapshot names that appear more than once (ZFS names are unique per pool).
    duplicates: Vec<String>,
    /// Names the plan would prune despite having no retention window — a
    /// violation of the load-bearing safety rule (should always be empty; this is
    /// a regression guard on `plan_pruning()`'s promise).
    invariant_violations: Vec<String>,
}

impl CheckReport {
    /// Whether the inventory is policy-clean (nothing to fail on).
    fn ok(&self) -> bool {
        self.duplicates.is_empty() && self.invariant_violations.is_empty()
    }
}

/// Parse an inventory from JSON and evaluate it against the retention policy.
/// `fallback_now` is used only for the bare-array form.
fn evaluate(json: &str, fallback_now: i64) -> Result<CheckReport, serde_json::Error> {
    let (now, snapshots) = match serde_json::from_str::<Inventory>(json)? {
        Inventory::Clocked {
            now_epoch,
            snapshots,
        } => (now_epoch, snapshots),
        Inventory::Bare(snapshots) => (fallback_now, snapshots),
    };

    let plan = plan_pruning(&snapshots, now);

    // Duplicate names: an inventory with two of the same snapshot is malformed.
    let mut seen = std::collections::BTreeSet::new();
    let mut duplicates = Vec::new();
    for s in &snapshots {
        if !seen.insert(s.name.as_str()) {
            duplicates.push(s.name.clone());
        }
    }

    // Safety rule: nothing without a retention window may ever be pruned.
    let invariant_violations = plan
        .decisions
        .iter()
        .filter(|d| d.prune && d.class.retention_days().is_none())
        .map(|d| d.name.clone())
        .collect();

    Ok(CheckReport {
        now,
        total: snapshots.len(),
        plan,
        duplicates,
        invariant_violations,
    })
}

/// Render a check report as the operator-facing KEEP/PRUNE listing plus the
/// `zfs destroy` plan.
fn render_report(r: &CheckReport) -> String {
    let mut s = format!(
        "# sovereign-zfs-snapshot-policy --check (schema {SCHEMA_VERSION})\n\
         # evaluated at epoch {}, {} snapshot(s)\n\n",
        r.now, r.total,
    );
    for d in &r.plan.decisions {
        let verb = if d.prune { "PRUNE" } else { "KEEP " };
        s.push_str(&format!(
            "{verb} {name}  [{class}]  age {age}d  (window {window})\n",
            name = d.name,
            class = class_label(d.class),
            age = d.age_days,
            window = window_text(d.class.retention_days()),
        ));
    }

    let to_prune = r.plan.to_prune();
    s.push('\n');
    if to_prune.is_empty() {
        s.push_str("# nothing prunable at this time\n");
    } else {
        s.push_str(&format!(
            "# {} prunable — zfs destroy plan:\n",
            to_prune.len()
        ));
        for name in to_prune {
            s.push_str(&format!("zfs destroy '{name}'\n"));
        }
    }
    s
}

/// The current wall-clock time as unix epoch seconds (fallback for the bare
/// array form of `--check`).
fn now_epoch() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// `--check FILE`: read the file, evaluate the inventory, print the report, and
/// return a process exit code (non-zero on read/parse error or a policy finding).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let report = match evaluate(&json, now_epoch()) {
        Ok(r) => r,
        Err(e) => {
            eprintln!(
                "error: {path} is not a snapshot inventory (array or {{now_epoch,snapshots}}): {e}"
            );
            return ExitCode::FAILURE;
        }
    };

    print!("{}", render_report(&report));

    if !report.duplicates.is_empty() {
        eprintln!(
            "error: {} duplicate snapshot name(s) — ZFS names are unique per pool: {}",
            report.duplicates.len(),
            report.duplicates.join(", "),
        );
    }
    if !report.invariant_violations.is_empty() {
        eprintln!(
            "error: {} snapshot(s) would be pruned with no retention window (safety-rule violation): {}",
            report.invariant_violations.len(),
            report.invariant_violations.join(", "),
        );
    }

    if report.ok() {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

/// Emit the reference header followed by every canonical unit, each preceded by
/// its install path (the cpu-pinning convention).
fn run_emit() {
    print!("{}", reference_text());
    for u in snapshot_units() {
        println!("\n# --- {} ---", u.path);
        print!("{}", u.body);
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    run_emit();
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    const DAY: i64 = 86_400;

    #[test]
    fn class_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for class in ALL_CLASSES {
            let json = serde_json::to_string(&class).unwrap();
            assert_eq!(json, format!("\"{}\"", class_label(class)));
        }
    }

    #[test]
    fn every_class_is_listed_in_the_reference() {
        let t = reference_text();
        for class in ALL_CLASSES {
            assert!(
                t.contains(class_label(class)),
                "reference missing {class:?}"
            );
            // Window text is derived from retention_days(), never hardcoded.
            assert!(
                t.contains(&window_text(class.retention_days())),
                "reference missing window for {class:?}"
            );
        }
    }

    #[test]
    fn emits_a_timer_and_service_per_cadence_class() {
        let units = snapshot_units();
        // 3 cadence classes × (timer + service) = 6 units.
        assert_eq!(units.len(), CADENCE_CLASSES.len() * 2);
        for class in CADENCE_CLASSES {
            let label = class_label(class);
            let base = format!("sovereign-zfs-snapshot-{label}");
            assert!(
                units
                    .iter()
                    .any(|u| u.path == format!("/etc/systemd/system/{base}.timer")),
                "no timer for {label}"
            );
            assert!(
                units
                    .iter()
                    .any(|u| u.path == format!("/etc/systemd/system/{base}.service")),
                "no service for {label}"
            );
        }
    }

    #[test]
    fn timer_carries_the_classes_oncalendar_and_window() {
        let units = snapshot_units();
        for class in CADENCE_CLASSES {
            let base = format!("sovereign-zfs-snapshot-{}", class_label(class));
            let timer = units
                .iter()
                .find(|u| u.path == format!("/etc/systemd/system/{base}.timer"))
                .unwrap();
            assert!(
                timer
                    .body
                    .contains(&format!("OnCalendar={}", on_calendar(class))),
                "timer body: {}",
                timer.body
            );
            // The window in the description comes from retention_days().
            assert!(
                timer.body.contains(&window_text(class.retention_days())),
                "timer body: {}",
                timer.body
            );
        }
    }

    #[test]
    fn emitted_names_classify_back_to_their_class() {
        // The load-bearing link: a snapshot the emitted service creates must be
        // classified by the library as the very class that emitted it — otherwise
        // the units and the pruner would disagree.
        for class in CADENCE_CLASSES {
            let example = format!("{DATASET}@{}-2026-06-10-0000", snap_prefix(class));
            assert_eq!(
                SnapshotClass::classify(&example),
                class,
                "emitted name {example} does not classify as {class:?}"
            );
        }
    }

    #[test]
    fn check_plans_prune_and_keep_with_zfs_destroy() {
        let now = 1_000_000_000;
        let json = serde_json::json!({
            "now_epoch": now,
            "snapshots": [
                // daily, 40 days old → prune (window 30)
                { "name": "tank/context@zfs-auto-snap_daily-old", "created_epoch": now - 40 * DAY },
                // daily, 5 days old → keep
                { "name": "tank/context@zfs-auto-snap_daily-new", "created_epoch": now - 5 * DAY },
                // unknown, ancient → keep (never pruned)
                { "name": "tank/models@operator-adhoc", "created_epoch": now - 9999 * DAY },
            ]
        })
        .to_string();

        let report = evaluate(&json, 0).unwrap();
        assert_eq!(report.now, now);
        assert_eq!(report.total, 3);
        assert_eq!(report.plan.prune_count(), 1);
        assert!(report.ok());

        let rendered = render_report(&report);
        assert!(rendered.contains("zfs destroy 'tank/context@zfs-auto-snap_daily-old'"));
        assert!(!rendered.contains("zfs destroy 'tank/context@zfs-auto-snap_daily-new'"));
        // The unclassifiable snapshot is never in the destroy plan.
        assert!(!rendered.contains("zfs destroy 'tank/models@operator-adhoc'"));
    }

    #[test]
    fn check_flags_duplicate_snapshot_names() {
        let json = serde_json::json!([
            { "name": "tank/context@zfs-auto-snap_daily-x", "created_epoch": 1 },
            { "name": "tank/context@zfs-auto-snap_daily-x", "created_epoch": 2 },
        ])
        .to_string();
        let report = evaluate(&json, 2_000_000_000).unwrap();
        assert_eq!(report.duplicates.len(), 1);
        assert!(!report.ok(), "duplicate names must fail the check");
    }

    #[test]
    fn check_bare_array_uses_fallback_clock() {
        let json = r#"[{ "name": "tank/context@selfdef-pre-commit-abc", "created_epoch": 0 }]"#;
        let report = evaluate(json, 12_345).unwrap();
        assert_eq!(report.now, 12_345);
        assert_eq!(report.total, 1);
    }

    #[test]
    fn check_rejects_invalid_json() {
        assert!(evaluate("not json", 0).is_err());
    }

    #[test]
    fn help_and_reference_are_non_empty() {
        assert!(help_text().contains("--check"));
        assert!(reference_text().contains("E0667"));
    }
}
