//! `sovereign-cockpit-guardian-panel` — sovereign-os cockpit panel
//! binding for the selfdef IPS Guardian Daemon (sain-01 §10
//! `guardian-core`, physical IPS-side manifestation of the Trinity
//! Genesis Auditor narrative in sovereign-os M066).
//!
//! ## Cross-repo discipline (sacrosanct)
//!
//! Per operator standing direction 2026-05-19 *"if I talk about an IPS
//! feature its obviously not in Sovereign-OS. Respect the projects."*
//! this crate **does NOT depend on selfdef crates**. It consumes the
//! selfdef-emitted Guardian verdict JSON files at the filesystem
//! boundary and converts them into the sovereign-os cockpit's own
//! UX-tier types.
//!
//! Selfdef owns the Guardian authority. Sovereign-OS only renders it.
//! This is also the cockpit-side rendering of the Trinity Genesis
//! Auditor narrative bound to the IPS-side `guardian-core` daemon.
//!
//! ## Surface
//!
//! - [`Panel`] — top-level container holding the most-recent N
//!   verdicts + freshness metadata.
//! - [`RenderRow`] — one row per verdict / aggregate as the cockpit
//!   renders it (color tag + label + badge + click-target route).
//! - [`Panel::load_from_paths`] — reads the selfdef ring dir + OCSF
//!   audit log path and builds the panel state.
//! - [`Panel::render`] — produces the [`RenderRow`] vector the M066
//!   main-dashboard layout consumes.
//!
//! ## Reference
//!
//! - Selfdef SDD-029 guardian-daemon specification
//! - Selfdef MS044 catalog R10486-R10510 (cockpit panel binding)
//! - Sister crates: `sovereign-cockpit-friction-audit-panel` (M060),
//!   `sovereign-cockpit-perimeter-panel` (M061)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use thiserror::Error;

/// Schema version. Bump on breaking changes; downstream cockpit
/// renderers MUST refuse to display panels whose schema_version
/// does not match what they were built against.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default ring-buffer directory written by selfdef-guardian.service.
pub const DEFAULT_RING_DIR: &str = "/var/cache/selfdef/guardian/ring";

/// Default OCSF JSONL path.
pub const DEFAULT_OCSF_PATH: &str = "/var/log/selfdef/guardian.ocsf.jsonl";

/// Default Tetragon UNIX socket path.
pub const DEFAULT_SOCKET_PATH: &str = "/var/run/tetragon/tetragon.events";

/// Tetragon action that triggered Guardian's response (mirror of
/// selfdef-guardian-mirror::Action).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Action {
    /// Tetragon's matchAction was Sigkill.
    Sigkill,
    /// Tetragon emitted a process-related policy event.
    ProcessRelated,
    /// Catch-all for action strings that didn't map cleanly.
    Other,
}

/// One step in the verbatim sain-01 §10 3-step Guardian response.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ResponseStep {
    /// Step 1 — SIGKILL.
    Sigkill,
    /// Step 2 — atomic append to ZFS audit log.
    AuditAppend,
    /// Step 3 — native console alert.
    ConsoleAlert,
}

/// Outcome of a single response step.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "outcome", content = "detail")]
pub enum StepOutcome {
    /// Step executed cleanly.
    Ok,
    /// Step deliberately skipped.
    Skipped(String),
    /// Step failed.
    Failed(String),
}

/// One step + its outcome.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StepResult {
    /// Which step.
    pub step: ResponseStep,
    /// Outcome of that step.
    pub outcome: StepOutcome,
}

/// A single Guardian verdict — minimal shape sovereign-os reads from
/// the selfdef-emitted ring buffer.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Tetragon-emitted event id.
    pub event_id: String,
    /// Originating action.
    pub action: Action,
    /// PID of the target process.
    pub target_pid: u32,
    /// Cgroup path.
    pub target_cgroup: String,
    /// Container id (Podman/runc/containerd).
    pub target_container_id: String,
    /// Binary path the target was trying to / did execute.
    pub target_binary_path: String,
    /// Response steps Guardian took.
    pub response_steps: Vec<StepResult>,
    /// Verdict timestamp (ms epoch).
    pub ts_ms: u64,
    /// Host where Guardian ran.
    pub hostname: String,
}

impl Entry {
    /// Whether all three response steps completed (Ok or Skipped — not Failed).
    #[must_use]
    pub fn all_steps_ok(&self) -> bool {
        let mut have_sigkill = false;
        let mut have_audit = false;
        let mut have_console = false;
        for s in &self.response_steps {
            if let StepOutcome::Failed(_) = s.outcome {
                return false;
            }
            match s.step {
                ResponseStep::Sigkill => have_sigkill = true,
                ResponseStep::AuditAppend => have_audit = true,
                ResponseStep::ConsoleAlert => have_console = true,
            }
        }
        have_sigkill && have_audit && have_console
    }
}

/// Rendering color semantics.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    /// Guardian healthy, all responses clean.
    Green,
    /// Tetragon socket missing — Guardian can't ingest.
    Yellow,
    /// At least one verdict had a failed step.
    Red,
    /// No verdicts and Tetragon socket present.
    Gray,
}

/// Render-row kind discriminator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum RowKind {
    /// Top-row aggregate.
    Aggregate,
    /// One Guardian verdict.
    Verdict,
}

/// One M066 panel row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RenderRow {
    /// Row kind discriminator.
    pub kind: RowKind,
    /// Display label (left side).
    pub label: String,
    /// Badge text (right side).
    pub badge: String,
    /// Color semantic.
    pub color: Color,
    /// Detail text under the badge.
    pub detail: String,
    /// Click-target route for the M066 main-dashboard handler.
    pub runbook_route: String,
}

/// Errors produced by the panel surface.
#[derive(Debug, Error)]
pub enum PanelError {
    /// Schema version drift on a deserialized entry.
    #[error("schema version mismatch: expected {SCHEMA_VERSION}, got {0}")]
    SchemaMismatch(String),
    /// I/O reading a directory or file.
    #[error("I/O: {0}")]
    Io(String),
    /// JSON deserialization failure on a ring entry.
    #[error("entry parse: {0}")]
    Parse(String),
}

/// Panel container — what the M066 cockpit layout consumes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Panel {
    /// Schema version.
    pub schema_version: String,
    /// Most recent N verdicts (newest-first, capped at 16).
    pub recent_verdicts: Vec<Entry>,
    /// Whether the Tetragon UNIX socket is present.
    pub socket_present: bool,
    /// Wall-clock "now" the panel was assembled at (for freshness).
    pub now_ms: u64,
}

impl Panel {
    /// Construct an empty panel.
    #[must_use]
    pub fn new(now_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            recent_verdicts: Vec::new(),
            socket_present: false,
            now_ms,
        }
    }

    /// Load panel state from canonical selfdef paths. Missing paths
    /// surface as empty (Gray) — never an error.
    ///
    /// # Errors
    /// Returns `PanelError::Io` on read failure for an existing dir.
    pub fn load_from_paths(
        ring_dir: &Path,
        socket_path: &Path,
        now_ms: u64,
    ) -> Result<Self, PanelError> {
        let mut panel = Self::new(now_ms);

        if ring_dir.exists() {
            let read = fs::read_dir(ring_dir).map_err(|e| PanelError::Io(e.to_string()))?;
            for dirent in read {
                let dirent = dirent.map_err(|e| PanelError::Io(e.to_string()))?;
                let path = dirent.path();
                if path.extension().is_none_or(|e| e != "json") {
                    continue;
                }
                let bytes = match fs::read(&path) {
                    Ok(b) => b,
                    Err(_) => continue,
                };
                if let Ok(entry) = serde_json::from_slice::<Entry>(&bytes) {
                    panel.recent_verdicts.push(entry);
                }
            }
            panel
                .recent_verdicts
                .sort_by_key(|e| std::cmp::Reverse(e.ts_ms));
            panel.recent_verdicts.truncate(16);
        }

        panel.socket_present = socket_path.exists();
        Ok(panel)
    }

    /// Whether any verdict had a failed step.
    #[must_use]
    pub fn any_failed(&self) -> bool {
        self.recent_verdicts.iter().any(|v| !v.all_steps_ok())
    }

    /// Top-row color aggregate.
    #[must_use]
    pub fn aggregate_color(&self) -> Color {
        if self.any_failed() {
            return Color::Red;
        }
        if !self.socket_present {
            return Color::Yellow;
        }
        if self.recent_verdicts.is_empty() {
            return Color::Gray;
        }
        Color::Green
    }

    /// Aggregate badge text.
    #[must_use]
    pub fn aggregate_badge(&self) -> &'static str {
        match self.aggregate_color() {
            Color::Red => "ALERT",
            Color::Yellow => "DEGRADED",
            Color::Green => "OK",
            Color::Gray => "—",
        }
    }

    /// Build the row sequence the M066 dashboard renders.
    /// Order: aggregate row first, then recent verdicts.
    #[must_use]
    pub fn render(&self) -> Vec<RenderRow> {
        let mut rows = Vec::new();
        rows.push(self.render_aggregate());
        for v in &self.recent_verdicts {
            rows.push(self.render_verdict(v));
        }
        rows
    }

    fn render_aggregate(&self) -> RenderRow {
        let color = self.aggregate_color();
        let badge = self.aggregate_badge().to_string();
        let detail = if self.socket_present {
            format!(
                "Tetragon socket present · {} verdict(s) tracked",
                self.recent_verdicts.len()
            )
        } else {
            "Tetragon UNIX socket missing — Guardian cannot ingest events".to_string()
        };
        RenderRow {
            kind: RowKind::Aggregate,
            label: "Guardian".to_string(),
            badge,
            color,
            detail,
            runbook_route: "/wiki/runbooks/guardian-not-running".to_string(),
        }
    }

    fn render_verdict(&self, v: &Entry) -> RenderRow {
        let all_ok = v.all_steps_ok();
        let (badge, color, runbook) = if all_ok {
            ("OK".to_string(), Color::Green, String::new())
        } else {
            (
                "ALERT".to_string(),
                Color::Red,
                "/wiki/runbooks/guardian-console-alert-investigation".to_string(),
            )
        };
        RenderRow {
            kind: RowKind::Verdict,
            label: v.target_binary_path.clone(),
            badge,
            color,
            detail: format!(
                "event={} pid={} · {} · host={}",
                v.event_id,
                v.target_pid,
                freshness_since(self.now_ms, v.ts_ms),
                v.hostname
            ),
            runbook_route: runbook,
        }
    }
}

/// Format a "ms ago" freshness string.
fn freshness_since(now_ms: u64, ts_ms: u64) -> String {
    let delta = now_ms.saturating_sub(ts_ms);
    let secs = delta / 1000;
    if secs < 5 {
        "just now".to_string()
    } else if secs < 60 {
        format!("{secs}s ago")
    } else if secs < 3600 {
        format!("{}m ago", secs / 60)
    } else if secs < 86_400 {
        format!("{}h ago", secs / 3600)
    } else if secs < 86_400 * 30 {
        let days = secs / 86_400;
        format!("{days}d ago · stale")
    } else {
        "stale (>30d)".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::path::PathBuf;

    fn tmp_dir() -> PathBuf {
        let p = std::env::temp_dir().join(format!(
            "guardian-panel-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&p).unwrap();
        p
    }

    fn three_step_ok() -> Vec<StepResult> {
        vec![
            StepResult {
                step: ResponseStep::Sigkill,
                outcome: StepOutcome::Ok,
            },
            StepResult {
                step: ResponseStep::AuditAppend,
                outcome: StepOutcome::Ok,
            },
            StepResult {
                step: ResponseStep::ConsoleAlert,
                outcome: StepOutcome::Ok,
            },
        ]
    }

    fn sample_ok(ts: u64) -> Entry {
        Entry {
            event_id: format!("evt-{ts}"),
            action: Action::Sigkill,
            target_pid: 4242,
            target_cgroup: "/system.slice/sshd.service".into(),
            target_container_id: String::new(),
            target_binary_path: "/usr/bin/curl".into(),
            response_steps: three_step_ok(),
            ts_ms: ts,
            hostname: "host-A".into(),
        }
    }

    fn sample_failed(ts: u64) -> Entry {
        let mut e = sample_ok(ts);
        e.response_steps[0].outcome = StepOutcome::Failed("podman down".into());
        e
    }

    fn write_entry(dir: &Path, name: &str, e: &Entry) {
        let mut f = fs::File::create(dir.join(name)).unwrap();
        f.write_all(&serde_json::to_vec(e).unwrap()).unwrap();
    }

    #[test]
    fn all_steps_ok_true_on_clean_three_step() {
        assert!(sample_ok(1).all_steps_ok());
    }

    #[test]
    fn all_steps_ok_false_on_failed_step() {
        assert!(!sample_failed(1).all_steps_ok());
    }

    #[test]
    fn all_steps_ok_treats_skipped_as_ok() {
        let mut e = sample_ok(1);
        e.response_steps[2].outcome = StepOutcome::Skipped("/dev/console unavailable".into());
        assert!(e.all_steps_ok());
    }

    #[test]
    fn empty_panel_aggregates_gray_with_socket() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        assert_eq!(p.aggregate_color(), Color::Gray);
        assert_eq!(p.aggregate_badge(), "—");
    }

    #[test]
    fn empty_panel_aggregates_yellow_without_socket() {
        let p = Panel::new(1_700_000_000_000);
        assert_eq!(p.aggregate_color(), Color::Yellow);
        assert_eq!(p.aggregate_badge(), "DEGRADED");
    }

    #[test]
    fn panel_clean_verdicts_aggregate_green() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        p.recent_verdicts.push(sample_ok(1_700_000_000_000));
        assert_eq!(p.aggregate_color(), Color::Green);
        assert_eq!(p.aggregate_badge(), "OK");
    }

    #[test]
    fn panel_with_failed_step_aggregates_red() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        p.recent_verdicts.push(sample_failed(1_700_000_000_000));
        assert_eq!(p.aggregate_color(), Color::Red);
        assert_eq!(p.aggregate_badge(), "ALERT");
    }

    #[test]
    fn failed_step_overrides_missing_socket() {
        let mut p = Panel::new(1_700_000_000_000);
        // socket_present = false
        p.recent_verdicts.push(sample_failed(1_700_000_000_000));
        assert_eq!(p.aggregate_color(), Color::Red);
    }

    #[test]
    fn render_emits_aggregate_first() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        p.recent_verdicts.push(sample_ok(1_700_000_000_000));
        let rows = p.render();
        assert!(matches!(rows[0].kind, RowKind::Aggregate));
    }

    #[test]
    fn render_clean_verdict_has_no_runbook() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        p.recent_verdicts.push(sample_ok(1_700_000_000_000));
        let rows = p.render();
        let verdict = rows.iter().find(|r| r.kind == RowKind::Verdict).unwrap();
        assert_eq!(verdict.runbook_route, "");
        assert_eq!(verdict.badge, "OK");
    }

    #[test]
    fn render_failed_verdict_has_alert_runbook() {
        let mut p = Panel::new(1_700_000_000_000);
        p.socket_present = true;
        p.recent_verdicts.push(sample_failed(1_700_000_000_000));
        let rows = p.render();
        let verdict = rows.iter().find(|r| r.kind == RowKind::Verdict).unwrap();
        assert_eq!(
            verdict.runbook_route,
            "/wiki/runbooks/guardian-console-alert-investigation"
        );
        assert_eq!(verdict.badge, "ALERT");
    }

    #[test]
    fn load_from_paths_missing_dirs_returns_empty() {
        let dir = tmp_dir();
        let p = Panel::load_from_paths(&dir.join("ring"), &dir.join("socket"), 1_700_000_000_000)
            .unwrap();
        assert!(p.recent_verdicts.is_empty());
        assert!(!p.socket_present);
    }

    #[test]
    fn load_from_paths_reads_ring_entries_newest_first() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        write_entry(&ring, "a.json", &sample_ok(1_700_000_000_000));
        write_entry(&ring, "b.json", &sample_ok(1_700_000_001_000));
        let p = Panel::load_from_paths(&ring, &dir.join("nope"), 1_700_000_001_500).unwrap();
        assert_eq!(p.recent_verdicts.len(), 2);
        assert_eq!(p.recent_verdicts[0].ts_ms, 1_700_000_001_000);
    }

    #[test]
    fn load_from_paths_caps_at_16() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        for i in 0..30u32 {
            write_entry(
                &ring,
                &format!("v{i:02}.json"),
                &sample_ok(1_700_000_000_000 + u64::from(i)),
            );
        }
        let p = Panel::load_from_paths(&ring, &dir.join("nope"), 1_700_000_000_500).unwrap();
        assert_eq!(p.recent_verdicts.len(), 16);
    }

    #[test]
    fn load_from_paths_skips_malformed() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        fs::write(ring.join("bad.json"), b"not json").unwrap();
        write_entry(&ring, "good.json", &sample_ok(1_700_000_000_000));
        let p = Panel::load_from_paths(&ring, &dir.join("nope"), 1_700_000_000_000).unwrap();
        assert_eq!(p.recent_verdicts.len(), 1);
    }

    #[test]
    fn load_from_paths_detects_socket_presence() {
        let dir = tmp_dir();
        let sock = dir.join("socket");
        fs::write(&sock, b"placeholder").unwrap();
        let p = Panel::load_from_paths(&dir.join("ring"), &sock, 1_700_000_000_000).unwrap();
        assert!(p.socket_present);
    }
}
