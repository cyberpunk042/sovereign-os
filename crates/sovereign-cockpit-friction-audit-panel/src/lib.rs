//! `sovereign-cockpit-friction-audit-panel` — sovereign-os cockpit
//! panel binding for the selfdef IPS friction-audit boot-time gate.
//!
//! ## Cross-repo discipline (sacrosanct)
//!
//! Per operator standing direction 2026-05-19 *"if I talk about an IPS
//! feature its obviously not in Sovereign-OS. Respect the projects."*
//! this crate **does NOT depend on selfdef crates**. It consumes the
//! selfdef-emitted ring-buffer JSON files at the filesystem boundary
//! (`/var/cache/selfdef/friction-audit/ring/*.json`) and converts them
//! into the sovereign-os cockpit's own UX-tier types.
//!
//! Selfdef owns the gate state. Sovereign-OS only renders it.
//!
//! ## Surface
//!
//! - [`Panel`] — top-level container holding the latest per-gate
//!   verdicts + UX freshness metadata.
//! - [`RenderRow`] — one row per gate as the cockpit renders it
//!   (color tag + label + freshness label + click-target route).
//! - [`Panel::load_from_ring`] — reads the selfdef ring directory and
//!   builds the latest per-gate verdict map.
//! - [`Panel::render`] — produces the [`RenderRow`] vector the M060
//!   main-dashboard layout consumes.
//!
//! ## Reference
//!
//! - Selfdef SDD-027 friction-audit-system specification
//! - Selfdef MS046 catalog R11136–R11142 (cockpit panel binding)
//! - Selfdef ring-entry on-disk schema (Cargo crate
//!   `selfdef-friction-audit-mirror::Verdict`) — sovereign-os reads
//!   ONLY the simpler script-written shape ({gate, status, ts_ms,
//!   hostname}).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;
use thiserror::Error;

/// Schema version. Bump on breaking changes; downstream cockpit
/// renderers MUST refuse to display panels whose schema_version
/// does not match what they were built against.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default ring-buffer directory written by the selfdef friction-audit
/// boot script. Operators on non-default deploys override via env or
/// pass an explicit Path to `Panel::load_from_ring`.
pub const DEFAULT_RING_DIR: &str = "/var/cache/selfdef/friction-audit/ring";

/// Selfdef gate identity. Mirrors the kebab-case shape selfdef emits.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[serde(rename_all = "kebab-case")]
pub enum Gate {
    /// PCIe bifurcation symmetry gate.
    Pcie,
    /// ZFS pool health gate.
    Zfs,
    /// System memory geometry gate.
    Memory,
    /// Script integrity (chattr +i / IMA-appraise) gate.
    Immutability,
    /// MS003 signature verification gate.
    Signature,
    /// Operator-extended timeout-watchdog gate.
    Timeout,
}

impl Gate {
    /// Stable display label as the M060 main-dashboard row title.
    #[must_use]
    pub const fn label(self) -> &'static str {
        match self {
            Self::Pcie => "PCIe Bifurcation",
            Self::Zfs => "ZFS Pool Health",
            Self::Memory => "Memory Geometry",
            Self::Immutability => "Script Immutability",
            Self::Signature => "MS003 Signature",
            Self::Timeout => "Gate Timeout",
        }
    }

    /// Iterate the gates in fixed render order (top-to-bottom).
    #[must_use]
    pub const fn render_order() -> &'static [Self] {
        &[
            Self::Pcie,
            Self::Zfs,
            Self::Memory,
            Self::Immutability,
            Self::Signature,
            Self::Timeout,
        ]
    }
}

/// Selfdef gate verdict status. We mirror the simpler shape selfdef's
/// boot script writes: `pass | fail | skip`. The richer
/// `OverrideActive` variant (from the selfdef-friction-audit-mirror
/// Cargo crate) is represented as a separate `RenderColor::Override`
/// when consumers detect an active override manifest via the future
/// MS003 cross-cutting binding (Deliverable 4 in SDD-027).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Gate passed.
    Pass,
    /// Gate failed.
    Fail,
    /// Gate skipped (operator-extension for hosts without zpool /
    /// dmidecode).
    Skip,
    /// Operator-signed override is honoring a failed gate. The cockpit
    /// surfaces this with a yellow countdown banner.
    Override,
}

/// A single ring-buffer entry as selfdef writes it. Minimal shape so
/// sovereign-os doesn't lock to the richer selfdef Verdict struct.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Selfdef gate identity.
    pub gate: Gate,
    /// Verdict status.
    pub status: Status,
    /// Verdict ts (epoch ms).
    pub ts_ms: u64,
    /// Host where the gate ran.
    pub hostname: String,
}

/// Rendering color semantics. The cockpit's CSS / TUI palette maps
/// these onto the operator-chosen color scheme (via the whitelabel
/// crate, sovereign-os M081). WCAG 2.1 AA contrast 4.5:1 is the
/// minimum each chosen palette must meet (selfdef MS043 R10175).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    /// All gates passing or operator-extended SKIP.
    Green,
    /// Override active (operator-signed exception with countdown).
    Yellow,
    /// Gate failing (any).
    Red,
    /// No verdict yet recorded (fresh deploy, ring empty).
    Gray,
}

/// One M060 panel row.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RenderRow {
    /// Gate identity (also drives the click-target route).
    pub gate: Gate,
    /// Display label.
    pub label: &'static str,
    /// Status badge text (PASS / FAIL / SKIP / OVRD / —).
    pub badge: &'static str,
    /// Color semantic.
    pub color: Color,
    /// Detailed text rendered under the badge (human-readable freshness
    /// or skip reason).
    pub detail: String,
    /// Click-target route for the M060 main-dashboard handler. Points
    /// at the operator runbook URL in the info-hub second brain.
    pub runbook_route: &'static str,
}

/// Errors produced by the panel surface.
#[derive(Debug, Error)]
pub enum PanelError {
    /// Schema version drift on a deserialized Entry.
    #[error("schema version mismatch: expected {SCHEMA_VERSION}, got {0}")]
    SchemaMismatch(String),
    /// I/O reading the ring directory.
    #[error("ring directory I/O: {0}")]
    Io(String),
    /// JSON deserialization failure on a ring entry.
    #[error("ring entry parse: {0}")]
    Parse(String),
}

/// Panel container — what the cockpit M060 layout consumes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Panel {
    /// Schema version (for forward compatibility).
    pub schema_version: String,
    /// Latest verdict per gate.
    pub entries: BTreeMap<String, Entry>,
    /// Wall-clock "now" the panel was assembled at (for freshness).
    pub now_ms: u64,
}

impl Panel {
    /// Construct an empty panel at a given wall-clock.
    #[must_use]
    pub fn new(now_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            entries: BTreeMap::new(),
            now_ms,
        }
    }

    /// Read the selfdef ring directory and build the latest per-gate
    /// verdict map. Missing dir is not an error — surfaces as empty
    /// panel (Gray render).
    ///
    /// # Errors
    /// Returns `PanelError` on read failure (other than missing dir)
    /// or unrecoverable JSON parse failure.
    pub fn load_from_ring(ring: &Path, now_ms: u64) -> Result<Self, PanelError> {
        let mut panel = Self::new(now_ms);
        if !ring.exists() {
            return Ok(panel);
        }
        let read = fs::read_dir(ring).map_err(|e| PanelError::Io(e.to_string()))?;
        for dirent in read {
            let dirent = dirent.map_err(|e| PanelError::Io(e.to_string()))?;
            let path = dirent.path();
            if path.extension().is_none_or(|e| e != "json") {
                continue;
            }
            let bytes = match fs::read(&path) {
                Ok(b) => b,
                Err(_) => continue, // race with eviction; ignore
            };
            let entry: Entry = match serde_json::from_slice(&bytes) {
                Ok(e) => e,
                Err(_) => continue, // malformed entry; ignore (don't fail the panel)
            };
            // Latest-per-gate: only insert if newer.
            let key = serde_json::to_string(&entry.gate).unwrap_or_default();
            panel
                .entries
                .entry(key)
                .and_modify(|existing| {
                    if entry.ts_ms > existing.ts_ms {
                        *existing = entry.clone();
                    }
                })
                .or_insert(entry);
        }
        Ok(panel)
    }

    /// Whether the panel has any verdict at all.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Whether any gate is currently FAIL (no override honoring).
    #[must_use]
    pub fn any_failing(&self) -> bool {
        self.entries.values().any(|e| e.status == Status::Fail)
    }

    /// Top-row color aggregate (worst-of-all rule).
    #[must_use]
    pub fn aggregate_color(&self) -> Color {
        if self.is_empty() {
            return Color::Gray;
        }
        if self.any_failing() {
            return Color::Red;
        }
        // Override-active is yellow only if anything is overridden.
        if self.entries.values().any(|e| e.status == Status::Override) {
            return Color::Yellow;
        }
        Color::Green
    }

    /// Build the row sequence the M060 dashboard renders. Gates appear
    /// in fixed render order; a gate with no recorded verdict appears
    /// as Gray with badge "—".
    #[must_use]
    pub fn render(&self) -> Vec<RenderRow> {
        Gate::render_order()
            .iter()
            .map(|&g| self.render_one(g))
            .collect()
    }

    fn render_one(&self, gate: Gate) -> RenderRow {
        let key = serde_json::to_string(&gate).unwrap_or_default();
        let entry = self.entries.get(&key);
        let (badge, color, detail) = match entry {
            None => ("—", Color::Gray, "no verdict yet recorded".to_string()),
            Some(e) => match e.status {
                Status::Pass => ("PASS", Color::Green, freshness(self.now_ms, e.ts_ms)),
                Status::Fail => ("FAIL", Color::Red, freshness(self.now_ms, e.ts_ms)),
                Status::Skip => (
                    "SKIP",
                    Color::Green,
                    format!(
                        "operator-extended skip · {}",
                        freshness(self.now_ms, e.ts_ms)
                    ),
                ),
                Status::Override => ("OVRD", Color::Yellow, freshness(self.now_ms, e.ts_ms)),
            },
        };
        RenderRow {
            gate,
            label: gate.label(),
            badge,
            color,
            detail,
            runbook_route: runbook_route(gate),
        }
    }
}

/// Map each gate to its operator-runbook URL in the info-hub second
/// brain. The cockpit click handler dereferences this on row tap.
const fn runbook_route(gate: Gate) -> &'static str {
    match gate {
        Gate::Pcie => "/wiki/runbooks/friction-audit-pcie",
        Gate::Zfs => "/wiki/runbooks/friction-audit-zfs",
        Gate::Memory => "/wiki/runbooks/friction-audit-memory",
        Gate::Immutability => "/wiki/runbooks/friction-audit-immutability",
        Gate::Signature => "/wiki/runbooks/friction-audit-signature",
        // Timeout has no dedicated runbook yet — route to the PCIe
        // runbook as the closest cause (PCIe probe is the most likely
        // to wedge and trigger the 2000ms cap). When a dedicated
        // timeout runbook is authored, update this match.
        Gate::Timeout => "/wiki/runbooks/friction-audit-pcie",
    }
}

/// Format a "ms ago" freshness string. Caps at 30 days; older shows
/// as "stale". Per selfdef MS046 R10910 the panel marks stale at 24h.
fn freshness(now_ms: u64, ts_ms: u64) -> String {
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
        if days >= 1 {
            format!("{days}d ago · stale")
        } else {
            "1d ago".to_string()
        }
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
            "panel-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        std::fs::create_dir_all(&p).unwrap();
        p
    }

    fn write_entry(dir: &Path, ts: u64, gate: &str, status: &str, host: &str) {
        let path = dir.join(format!("{ts}-{gate}.json"));
        let body =
            format!(r#"{{"gate":"{gate}","status":"{status}","ts_ms":{ts},"hostname":"{host}"}}"#);
        let mut f = fs::File::create(&path).unwrap();
        f.write_all(body.as_bytes()).unwrap();
    }

    #[test]
    fn empty_panel_renders_six_gray_rows() {
        let p = Panel::new(1_700_000_000_000);
        let rows = p.render();
        assert_eq!(rows.len(), 6);
        for r in &rows {
            assert_eq!(r.color, Color::Gray);
            assert_eq!(r.badge, "—");
        }
        assert_eq!(p.aggregate_color(), Color::Gray);
    }

    #[test]
    fn load_from_missing_dir_returns_empty() {
        let p = Panel::load_from_ring(Path::new("/nonexistent/path"), 1_700_000_000_000).unwrap();
        assert!(p.is_empty());
    }

    #[test]
    fn load_from_ring_picks_latest_per_gate() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "host-A");
        write_entry(&dir, 200, "pcie", "fail", "host-A");
        write_entry(&dir, 150, "zfs", "pass", "host-A");
        let p = Panel::load_from_ring(&dir, 300).unwrap();
        assert_eq!(p.entries.len(), 2);
        // PCIe latest is the fail (ts=200)
        let pcie_key = serde_json::to_string(&Gate::Pcie).unwrap();
        let pcie = p.entries.get(&pcie_key).unwrap();
        assert_eq!(pcie.status, Status::Fail);
        assert_eq!(pcie.ts_ms, 200);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn aggregate_color_red_when_any_fail() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "h");
        write_entry(&dir, 200, "zfs", "fail", "h");
        let p = Panel::load_from_ring(&dir, 300).unwrap();
        assert_eq!(p.aggregate_color(), Color::Red);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn aggregate_color_yellow_on_override_no_fail() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "override", "h");
        write_entry(&dir, 200, "zfs", "pass", "h");
        let p = Panel::load_from_ring(&dir, 300).unwrap();
        assert_eq!(p.aggregate_color(), Color::Yellow);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn aggregate_color_green_when_all_pass_or_skip() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "h");
        write_entry(&dir, 200, "zfs", "skip", "h");
        write_entry(&dir, 300, "memory", "pass", "h");
        let p = Panel::load_from_ring(&dir, 400).unwrap();
        assert_eq!(p.aggregate_color(), Color::Green);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn render_row_uses_stable_labels() {
        let p = Panel::new(1);
        let rows = p.render();
        assert_eq!(rows[0].label, "PCIe Bifurcation");
        assert_eq!(rows[1].label, "ZFS Pool Health");
        assert_eq!(rows[2].label, "Memory Geometry");
        assert_eq!(rows[3].label, "Script Immutability");
        assert_eq!(rows[4].label, "MS003 Signature");
        assert_eq!(rows[5].label, "Gate Timeout");
    }

    #[test]
    fn render_row_carries_runbook_route() {
        let p = Panel::new(1);
        let rows = p.render();
        assert_eq!(rows[0].runbook_route, "/wiki/runbooks/friction-audit-pcie");
        assert_eq!(rows[1].runbook_route, "/wiki/runbooks/friction-audit-zfs");
        assert_eq!(
            rows[2].runbook_route,
            "/wiki/runbooks/friction-audit-memory"
        );
        assert_eq!(
            rows[3].runbook_route,
            "/wiki/runbooks/friction-audit-immutability"
        );
        assert_eq!(
            rows[4].runbook_route,
            "/wiki/runbooks/friction-audit-signature"
        );
    }

    #[test]
    fn freshness_buckets() {
        assert_eq!(freshness(10_000, 10_000), "just now");
        assert_eq!(freshness(10_000, 7_000), "just now"); // <5s
        assert_eq!(freshness(70_000, 10_000), "1m ago");
        assert_eq!(freshness(3_600_000 + 100, 100), "1h ago");
        assert_eq!(freshness(86_400_000 + 100, 100), "1d ago · stale");
        assert_eq!(freshness(86_400_000 * 31 + 100, 100), "stale (>30d)");
    }

    #[test]
    fn skip_renders_green_with_skip_badge() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "zfs", "skip", "container-X");
        let p = Panel::load_from_ring(&dir, 200).unwrap();
        let rows = p.render();
        let zfs = rows.iter().find(|r| r.gate == Gate::Zfs).unwrap();
        assert_eq!(zfs.badge, "SKIP");
        assert_eq!(zfs.color, Color::Green);
        assert!(zfs.detail.contains("operator-extended skip"));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn override_renders_yellow_ovrd() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "override", "h");
        let p = Panel::load_from_ring(&dir, 200).unwrap();
        let rows = p.render();
        let pcie = rows.iter().find(|r| r.gate == Gate::Pcie).unwrap();
        assert_eq!(pcie.badge, "OVRD");
        assert_eq!(pcie.color, Color::Yellow);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn malformed_entry_silently_skipped() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "h");
        // Write a non-JSON file:
        std::fs::write(dir.join("garbage.json"), "{not-json").unwrap();
        let p = Panel::load_from_ring(&dir, 200).unwrap();
        // The valid entry still loaded.
        assert_eq!(p.entries.len(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn non_json_file_in_ring_ignored() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "h");
        std::fs::write(dir.join("README.txt"), "not a ring entry").unwrap();
        let p = Panel::load_from_ring(&dir, 200).unwrap();
        assert_eq!(p.entries.len(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn serde_roundtrip_panel() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "pcie", "pass", "host-A");
        let p = Panel::load_from_ring(&dir, 200).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Panel = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn gates_render_in_fixed_order() {
        let dir = tmp_dir();
        write_entry(&dir, 100, "signature", "pass", "h");
        write_entry(&dir, 200, "pcie", "pass", "h");
        write_entry(&dir, 300, "memory", "pass", "h");
        let p = Panel::load_from_ring(&dir, 400).unwrap();
        let rows = p.render();
        // Order is always pcie, zfs, memory, immutability, signature, timeout
        assert_eq!(rows[0].gate, Gate::Pcie);
        assert_eq!(rows[1].gate, Gate::Zfs);
        assert_eq!(rows[2].gate, Gate::Memory);
        assert_eq!(rows[3].gate, Gate::Immutability);
        assert_eq!(rows[4].gate, Gate::Signature);
        assert_eq!(rows[5].gate, Gate::Timeout);
        std::fs::remove_dir_all(&dir).ok();
    }
}
