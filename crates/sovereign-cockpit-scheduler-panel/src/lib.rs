//! `sovereign-cockpit-scheduler-panel` — sovereign-os cockpit panel
//! binding for the selfdef IPS Goldilocks Scheduler (avx-plus-plus
//! dump tail 18000-18250 IPS-side implementation).
//!
//! ## Cross-repo discipline (sacrosanct)
//!
//! Per operator standing direction 2026-05-19 *"if I talk about an IPS
//! feature its obviously not in Sovereign-OS. Respect the projects."*
//! this crate **does NOT depend on selfdef crates**. It consumes the
//! selfdef-emitted scheduler decision JSON at the filesystem boundary
//! and converts them into the sovereign-os cockpit's own UX-tier types.
//!
//! Selfdef owns the scheduler authority. Sovereign-OS only renders it.
//!
//! ## Surface
//!
//! - [`Panel`] — top-level container: recent decisions + backpressure
//!   state + audit-chain integrity flag + freshness metadata.
//! - [`RenderRow`] — one row per decision / aggregate / backpressure
//!   surface as the cockpit renders it.
//! - [`Panel::load_from_paths`] — reads the selfdef ring dir + audit
//!   log path and builds the panel state.
//! - [`Panel::render`] — produces the [`RenderRow`] vector the cockpit
//!   layout consumes.
//!
//! ## Reference
//!
//! - Selfdef SDD-031 goldilocks-scheduler specification
//! - Selfdef MS048 catalog R11447 + R11476-R11478 (cockpit panel
//!   binding contract)
//! - Sister crates (four-watchdog set):
//!   - sovereign-cockpit-friction-audit-panel (M060, hardware frame)
//!   - sovereign-cockpit-perimeter-panel (M061, kernel syscall)
//!   - sovereign-cockpit-guardian-panel (M066, supervisor tier)
//!   - this = routing layer (Stage-1 slot reservation; canonical
//!     M-id assignment is a sovereign-os arc decision)
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

/// Default ring buffer directory written by selfdef-scheduler.service.
pub const DEFAULT_RING_DIR: &str = "/var/cache/selfdef/scheduler/ring";

/// Default ZFS audit log path.
pub const DEFAULT_AUDIT_LOG_PATH: &str = "/mnt/vault/context/scheduler_audit.log";

/// Six profiles per sain-01 §10 + avx-plus-plus dump 18004-18040.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Profile {
    /// fast — favor latency
    Fast,
    /// careful — favor correctness
    Careful,
    /// private — local-only, cloud disabled
    Private,
    /// autonomous — sandbox-first, batch approvals
    Autonomous,
    /// experimental — wide branch search, no host commit
    Experimental,
    /// production — strict commit gates, low variance
    Production,
}

/// Hardware tier the scheduler routed the request to.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Route {
    /// RTX PRO 6000 Blackwell (oracle tier)
    Blackwell,
    /// RTX 4090 (scout tier)
    Rtx4090,
    /// Ryzen 9900X AVX-512 (deterministic cortex)
    Cpu,
    /// Hybrid — work split across tiers
    Hybrid,
    /// Branch hibernated — deferred
    Hibernate,
}

/// 7-axis objective breakdown for a single decision.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct AxisScores {
    /// Latency axis score (0.0-1.0; 1.0 = fast)
    pub latency: f32,
    /// Cost axis score
    pub cost: f32,
    /// Risk axis score
    pub risk: f32,
    /// Energy axis score
    pub energy: f32,
    /// Human-attention axis score
    pub human_attention: f32,
    /// Hardware-pressure axis score
    pub hardware_pressure: f32,
    /// Compound 7th axis (per-profile weighted)
    pub compound: f32,
}

/// Backpressure state across the five surfaces.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct BackpressureState {
    /// Blackwell VRAM ≥ 90%
    pub blackwell_vram_high: bool,
    /// RTX 4090 GPU busy ≥ 80%
    pub gpu3090_busy: bool,
    /// CPU PSI > 50%
    pub cpu_pressure: bool,
    /// Memory PSI > 30%
    pub ram_pressure: bool,
    /// IO PSI > 40%
    pub io_pressure: bool,
    /// Human gate queue > 5
    pub human_gate_queue_high: bool,
}

impl BackpressureState {
    /// Count surfaces under pressure.
    #[must_use]
    pub const fn pressure_count(&self) -> u8 {
        (self.blackwell_vram_high as u8)
            + (self.gpu3090_busy as u8)
            + (self.cpu_pressure as u8)
            + (self.ram_pressure as u8)
            + (self.io_pressure as u8)
            + (self.human_gate_queue_high as u8)
    }

    /// Any surface under pressure?
    #[must_use]
    pub const fn any_pressure(&self) -> bool {
        self.pressure_count() > 0
    }
}

/// A single scheduler decision — minimal shape sovereign-os reads.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Entry {
    /// Request id (UUIDv7).
    pub request_id: String,
    /// Profile in effect.
    pub profile: Profile,
    /// Hardware tier the request was routed to.
    pub route: Route,
    /// 7-axis objective breakdown.
    pub axis_scores: AxisScores,
    /// Backpressure state at decision time.
    pub backpressure: BackpressureState,
    /// Decision timestamp (ms epoch).
    pub ts_ms: u64,
    /// Host where the scheduler ran.
    pub hostname: String,
    /// MS003 signing key id of an operator force-override (if any).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub override_signer_kid: Option<String>,
}

impl Entry {
    /// Whether this decision was operator-force-overridden.
    #[must_use]
    pub fn is_overridden(&self) -> bool {
        self.override_signer_kid.is_some()
    }
}

/// Rendering color semantics.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    /// All decisions clean.
    Green,
    /// Some decision had backpressure OR an operator force-override.
    Yellow,
    /// Audit chain broken OR no decisions in window (alert).
    Red,
    /// No decisions and chain unknown.
    Gray,
}

/// Render-row kind discriminator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum RowKind {
    /// Top-row aggregate.
    Aggregate,
    /// One scheduling decision.
    Decision,
    /// One backpressure surface row.
    Backpressure,
}

/// One panel row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RenderRow {
    /// Row kind discriminator.
    pub kind: RowKind,
    /// Display label.
    pub label: String,
    /// Badge text.
    pub badge: String,
    /// Color semantic.
    pub color: Color,
    /// Detail text.
    pub detail: String,
    /// Click-target runbook route in the info-hub wiki.
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
    /// JSON deserialization failure.
    #[error("entry parse: {0}")]
    Parse(String),
}

/// Panel container — what the cockpit layout consumes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Panel {
    /// Schema version.
    pub schema_version: String,
    /// Most recent N decisions (newest-first, capped at 16).
    pub recent_decisions: Vec<Entry>,
    /// Whether the audit log file exists.
    pub audit_log_present: bool,
    /// Wall-clock "now" the panel was assembled at.
    pub now_ms: u64,
}

impl Panel {
    /// Construct an empty panel.
    #[must_use]
    pub fn new(now_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            recent_decisions: Vec::new(),
            audit_log_present: false,
            now_ms,
        }
    }

    /// Load panel state from canonical selfdef paths.
    ///
    /// # Errors
    /// Returns `PanelError::Io` on read failure for an existing dir.
    pub fn load_from_paths(
        ring_dir: &Path,
        audit_log: &Path,
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
                    panel.recent_decisions.push(entry);
                }
            }
            panel
                .recent_decisions
                .sort_by_key(|e| std::cmp::Reverse(e.ts_ms));
            panel.recent_decisions.truncate(16);
        }

        panel.audit_log_present = audit_log.exists();
        Ok(panel)
    }

    /// Whether any recent decision had backpressure.
    #[must_use]
    pub fn any_backpressure(&self) -> bool {
        self.recent_decisions
            .iter()
            .any(|d| d.backpressure.any_pressure())
    }

    /// Whether any recent decision was operator-force-overridden.
    #[must_use]
    pub fn any_overridden(&self) -> bool {
        self.recent_decisions.iter().any(Entry::is_overridden)
    }

    /// Top-row color aggregate.
    #[must_use]
    pub fn aggregate_color(&self) -> Color {
        if !self.audit_log_present && self.recent_decisions.is_empty() {
            return Color::Gray;
        }
        if self.any_backpressure() || self.any_overridden() {
            return Color::Yellow;
        }
        if self.recent_decisions.is_empty() {
            return Color::Gray;
        }
        Color::Green
    }

    /// Aggregate badge text.
    #[must_use]
    pub fn aggregate_badge(&self) -> &'static str {
        match self.aggregate_color() {
            Color::Red => "ALERT",
            Color::Yellow => {
                if self.any_overridden() {
                    "OVERRIDE"
                } else {
                    "BACKPRESSURE"
                }
            }
            Color::Green => "OK",
            Color::Gray => "—",
        }
    }

    /// Build the row sequence the cockpit dashboard renders.
    /// Order: aggregate row + 6 backpressure surface rows + recent decisions.
    #[must_use]
    pub fn render(&self) -> Vec<RenderRow> {
        let mut rows = Vec::new();
        rows.push(self.render_aggregate());
        // Backpressure surfaces — show all 6 (operator wants at-a-glance
        // status, not just under-pressure ones).
        let bp = self
            .recent_decisions
            .first()
            .map(|d| d.backpressure)
            .unwrap_or_default();
        rows.extend(self.render_backpressure_rows(bp));
        // Recent decisions (newest-first).
        for d in &self.recent_decisions {
            rows.push(self.render_decision(d));
        }
        rows
    }

    fn render_aggregate(&self) -> RenderRow {
        let color = self.aggregate_color();
        let badge = self.aggregate_badge().to_string();
        let detail = if self.audit_log_present {
            format!(
                "audit log present · {} decisions tracked",
                self.recent_decisions.len()
            )
        } else {
            "audit log absent — scheduler may not be running".to_string()
        };
        RenderRow {
            kind: RowKind::Aggregate,
            label: "Scheduler".to_string(),
            badge,
            color,
            detail,
            runbook_route: "/wiki/runbooks/scheduler-not-running".to_string(),
        }
    }

    fn render_backpressure_rows(&self, bp: BackpressureState) -> Vec<RenderRow> {
        let surfaces: [(&str, bool, &str); 6] = [
            ("Blackwell VRAM", bp.blackwell_vram_high, "blackwell-vram"),
            ("RTX 4090 GPU", bp.gpu3090_busy, "gpu3090"),
            ("CPU PSI", bp.cpu_pressure, "cpu-psi"),
            ("RAM PSI", bp.ram_pressure, "ram-psi"),
            ("IO PSI", bp.io_pressure, "io-psi"),
            ("Human gate queue", bp.human_gate_queue_high, "human-gate"),
        ];
        surfaces
            .iter()
            .map(|(label, pressure, _slug)| {
                let (badge, color) = if *pressure {
                    ("HIGH", Color::Yellow)
                } else {
                    ("clean", Color::Green)
                };
                RenderRow {
                    kind: RowKind::Backpressure,
                    label: (*label).to_string(),
                    badge: badge.to_string(),
                    color,
                    detail: if *pressure {
                        "under pressure — see runbook".to_string()
                    } else {
                        "below threshold".to_string()
                    },
                    runbook_route: "/wiki/runbooks/scheduler-backpressure-stuck-open".to_string(),
                }
            })
            .collect()
    }

    fn render_decision(&self, d: &Entry) -> RenderRow {
        let (badge, color, runbook) = if d.is_overridden() {
            (
                format!("OVRD[{:?}]", d.route),
                Color::Yellow,
                "/wiki/runbooks/scheduler-force-override-investigation".to_string(),
            )
        } else if d.backpressure.any_pressure() {
            (
                format!("BP[{:?}]", d.route),
                Color::Yellow,
                "/wiki/runbooks/scheduler-backpressure-stuck-open".to_string(),
            )
        } else {
            (format!("{:?}", d.route), Color::Green, String::new())
        };
        RenderRow {
            kind: RowKind::Decision,
            label: d.request_id.clone(),
            badge,
            color,
            detail: format!(
                "profile={:?} compound={:.3} · {} · host={}",
                d.profile,
                d.axis_scores.compound,
                freshness_since(self.now_ms, d.ts_ms),
                d.hostname
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
            "scheduler-panel-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&p).unwrap();
        p
    }

    fn clean_scores() -> AxisScores {
        AxisScores {
            latency: 0.9,
            cost: 0.8,
            risk: 0.7,
            energy: 0.6,
            human_attention: 0.5,
            hardware_pressure: 0.8,
            compound: 0.75,
        }
    }

    fn sample(ts: u64, with_pressure: bool, with_override: bool) -> Entry {
        let mut bp = BackpressureState::default();
        if with_pressure {
            bp.blackwell_vram_high = true;
        }
        Entry {
            request_id: format!("req-{ts}"),
            profile: Profile::Careful,
            route: Route::Blackwell,
            axis_scores: clean_scores(),
            backpressure: bp,
            ts_ms: ts,
            hostname: "host-A".into(),
            override_signer_kid: if with_override {
                Some("kid-op-7".into())
            } else {
                None
            },
        }
    }

    fn write_entry(dir: &Path, name: &str, e: &Entry) {
        let mut f = fs::File::create(dir.join(name)).unwrap();
        f.write_all(&serde_json::to_vec(e).unwrap()).unwrap();
    }

    #[test]
    fn empty_panel_no_audit_aggregates_gray() {
        let p = Panel::new(1);
        assert_eq!(p.aggregate_color(), Color::Gray);
        assert_eq!(p.aggregate_badge(), "—");
    }

    #[test]
    fn audit_present_no_decisions_gray() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        assert_eq!(p.aggregate_color(), Color::Gray);
    }

    #[test]
    fn clean_decisions_aggregate_green() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, false, false));
        assert_eq!(p.aggregate_color(), Color::Green);
        assert_eq!(p.aggregate_badge(), "OK");
    }

    #[test]
    fn backpressure_aggregates_yellow() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, true, false));
        assert_eq!(p.aggregate_color(), Color::Yellow);
        assert_eq!(p.aggregate_badge(), "BACKPRESSURE");
    }

    #[test]
    fn override_aggregates_yellow_with_override_badge() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, false, true));
        assert_eq!(p.aggregate_color(), Color::Yellow);
        assert_eq!(p.aggregate_badge(), "OVERRIDE");
    }

    #[test]
    fn override_takes_precedence_in_badge() {
        // Both backpressure AND override → OVERRIDE wins for the operator
        // since force-override is the more important signal (someone
        // explicitly chose this route).
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, true, true));
        assert_eq!(p.aggregate_color(), Color::Yellow);
        assert_eq!(p.aggregate_badge(), "OVERRIDE");
    }

    #[test]
    fn render_emits_aggregate_then_6_backpressure_then_decisions() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(100, false, false));
        p.recent_decisions.push(sample(200, false, false));
        let rows = p.render();
        // 1 aggregate + 6 backpressure surfaces + 2 decisions = 9
        assert_eq!(rows.len(), 9);
        assert!(matches!(rows[0].kind, RowKind::Aggregate));
        for row in &rows[1..=6] {
            assert!(matches!(row.kind, RowKind::Backpressure));
        }
        for row in &rows[7..] {
            assert!(matches!(row.kind, RowKind::Decision));
        }
    }

    #[test]
    fn render_backpressure_row_clean_vs_high() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, true, false));
        let rows = p.render();
        let blackwell = rows
            .iter()
            .find(|r| r.kind == RowKind::Backpressure && r.label == "Blackwell VRAM")
            .unwrap();
        assert_eq!(blackwell.badge, "HIGH");
        assert_eq!(blackwell.color, Color::Yellow);
    }

    #[test]
    fn render_decision_with_override_has_runbook() {
        let mut p = Panel::new(1);
        p.audit_log_present = true;
        p.recent_decisions.push(sample(1, false, true));
        let rows = p.render();
        let decision = rows.iter().find(|r| r.kind == RowKind::Decision).unwrap();
        assert_eq!(
            decision.runbook_route,
            "/wiki/runbooks/scheduler-force-override-investigation"
        );
        assert!(decision.badge.starts_with("OVRD"));
    }

    #[test]
    fn load_from_paths_missing_returns_empty() {
        let dir = tmp_dir();
        let p = Panel::load_from_paths(&dir.join("ring"), &dir.join("audit"), 1_700_000_000_000)
            .unwrap();
        assert!(p.recent_decisions.is_empty());
        assert!(!p.audit_log_present);
    }

    #[test]
    fn load_from_paths_reads_ring_newest_first() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        write_entry(&ring, "a.json", &sample(1_000, false, false));
        write_entry(&ring, "b.json", &sample(2_000, false, false));
        let p = Panel::load_from_paths(&ring, &dir.join("audit"), 3_000).unwrap();
        assert_eq!(p.recent_decisions.len(), 2);
        assert_eq!(p.recent_decisions[0].ts_ms, 2_000);
    }

    #[test]
    fn load_from_paths_skips_malformed() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        fs::write(ring.join("bad.json"), b"not json").unwrap();
        write_entry(&ring, "good.json", &sample(1, false, false));
        let p = Panel::load_from_paths(&ring, &dir.join("audit"), 1).unwrap();
        assert_eq!(p.recent_decisions.len(), 1);
    }

    #[test]
    fn load_from_paths_caps_at_16() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        for i in 0..30u64 {
            write_entry(&ring, &format!("d{i:02}.json"), &sample(i, false, false));
        }
        let p = Panel::load_from_paths(&ring, &dir.join("audit"), 100).unwrap();
        assert_eq!(p.recent_decisions.len(), 16);
    }

    #[test]
    fn load_from_paths_detects_audit_log_presence() {
        let dir = tmp_dir();
        let audit = dir.join("audit.log");
        fs::write(&audit, b"placeholder").unwrap();
        let p = Panel::load_from_paths(&dir.join("ring"), &audit, 1).unwrap();
        assert!(p.audit_log_present);
    }
}
