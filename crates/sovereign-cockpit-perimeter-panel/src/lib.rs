//! `sovereign-cockpit-perimeter-panel` — sovereign-os cockpit panel
//! binding for the selfdef IPS real-time security perimeter (Tetragon
//! `sovereign-kernel-fence`).
//!
//! ## Cross-repo discipline (sacrosanct)
//!
//! Per operator standing direction 2026-05-19 *"if I talk about an IPS
//! feature its obviously not in Sovereign-OS. Respect the projects."*
//! this crate **does NOT depend on selfdef crates**. It consumes the
//! selfdef-emitted OCSF jsonl + extension-manifest JSON files at the
//! filesystem boundary and converts them into the sovereign-os
//! cockpit's own UX-tier types.
//!
//! Selfdef owns the perimeter authority. Sovereign-OS only renders it.
//!
//! ## Surface
//!
//! - [`Panel`] — top-level container holding the most-recent N
//!   verdicts + currently-active extension manifests + freshness metadata.
//! - [`RenderRow`] — one row per verdict / extension as the cockpit
//!   renders it (color tag + label + badge + click-target route).
//! - [`Panel::load_from_paths`] — reads the selfdef ring dir + extension
//!   dir + policy YAML path and builds the panel state.
//! - [`Panel::render`] — produces the [`RenderRow`] vector the M061
//!   main-dashboard layout consumes.
//!
//! ## Reference
//!
//! - Selfdef SDD-028 perimeter-engine specification
//! - Selfdef MS047 catalog R11136-R11142 (cockpit panel binding)
//! - Sister crate: `sovereign-cockpit-friction-audit-panel` (M060)
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

/// Default ring-buffer directory written by selfdefd (Tetragon event
/// fan-out). Operators on non-default deploys override via env or pass
/// an explicit Path to `Panel::load_from_paths`.
pub const DEFAULT_RING_DIR: &str = "/var/cache/selfdef/perimeter/ring";

/// Default extension manifest dir.
pub const DEFAULT_EXTENSION_DIR: &str = "/etc/selfdef/perimeter-extensions";

/// Default TracingPolicy YAML path.
pub const DEFAULT_POLICY_PATH: &str =
    "/etc/tetragon/tracing-policies/sovereign-perimeter.yaml";

/// Verbatim sain-01 §6 default allowlist (mirror — sovereign-os keeps
/// its own copy of the spec-locked set for display + drift detection).
pub const DEFAULT_ALLOWLIST: &[&str] = &[
    "/usr/bin/python3",
    "/usr/bin/nvidia-smi",
    "/usr/local/bin/vllm",
    "/usr/bin/podman",
];

/// Outcome of a single sys_execve evaluation. Mirrors the kebab-case
/// shape selfdef emits in its OCSF / ring-buffer JSON.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "outcome", content = "detail")]
pub enum Outcome {
    /// In-kernel SIGKILL fired (binary not in allowlist; no extension).
    Sigkill,
    /// Binary in verbatim sain-01 §6 default allowlist.
    Allowlisted,
    /// Binary covered by an operator-signed extension manifest.
    ExtensionAllowed {
        /// SHA-256 of the extension manifest (hex).
        manifest_sha256: String,
        /// Expiry timestamp (ms epoch).
        expires_at_ms: u64,
    },
}

/// A single ring-buffer entry — the minimal shape sovereign-os reads.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Entry {
    /// Outcome of the evaluation.
    pub outcome: Outcome,
    /// Path the attempting process passed to sys_execve.
    pub attempted_binary_path: String,
    /// PID of the attempting process.
    pub attempting_pid: u32,
    /// Process cmdline (already-exec'd).
    pub process_cmdline: String,
    /// Verdict timestamp (ms epoch).
    pub ts_ms: u64,
    /// Host where the perimeter ran.
    pub hostname: String,
}

/// A summary of a currently-loaded extension manifest. Sovereign-os
/// reads selfdef's MS003-signed manifest JSON at the filesystem
/// boundary; this is the minimal shape it needs for rendering.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExtensionSummary {
    /// Stable extension id.
    pub extension_id: String,
    /// Binary paths this extension allowlists.
    pub binary_paths: Vec<String>,
    /// Expiry timestamp (ms epoch).
    pub expires_at_ms: u64,
    /// Primary signer kid (MS003).
    pub signer_kid: String,
    /// Auditor co-signer kid (MS003).
    pub auditor_kid: String,
}

/// Rendering color semantics. The cockpit's CSS / TUI palette maps
/// these onto the operator-chosen color scheme via the whitelabel
/// crate (sovereign-os M081). WCAG 2.1 AA contrast 4.5:1 is the
/// minimum each chosen palette must meet (selfdef MS043 R10175).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    /// All verdicts clean.
    Green,
    /// Active extension(s) in effect (yellow countdown banner).
    Yellow,
    /// At least one Sigkill verdict in the recent window.
    Red,
    /// No verdicts and no extensions (fresh deploy).
    Gray,
}

/// Render-row kind discriminator. One panel renders many rows of
/// different kinds (aggregate, verdict, extension).
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum RowKind {
    /// Top-row aggregate.
    Aggregate,
    /// One Sigkill / Allowlisted / ExtensionAllowed verdict.
    Verdict,
    /// One active extension manifest.
    Extension,
}

/// One M061 panel row. The cockpit layout decides whether to render
/// it as a button, list-item, or banner based on `kind`.
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
    /// Detail text (under the badge — freshness, cmdline excerpt, etc.).
    pub detail: String,
    /// Click-target route for the M061 main-dashboard handler. Empty
    /// when no specific runbook applies (aggregate row, generic rows).
    pub runbook_route: String,
}

/// Errors produced by the panel surface.
#[derive(Debug, Error)]
pub enum PanelError {
    /// Schema version drift on a deserialized entry/manifest.
    #[error("schema version mismatch: expected {SCHEMA_VERSION}, got {0}")]
    SchemaMismatch(String),
    /// I/O reading a directory.
    #[error("directory I/O: {0}")]
    Io(String),
    /// JSON deserialization failure on a ring or extension entry.
    #[error("entry parse: {0}")]
    Parse(String),
}

/// Panel container — what the M061 cockpit layout consumes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Panel {
    /// Schema version (for forward compatibility).
    pub schema_version: String,
    /// Most recent N verdicts (newest-first, capped at 16).
    pub recent_verdicts: Vec<Entry>,
    /// Currently-active extension manifests.
    pub active_extensions: Vec<ExtensionSummary>,
    /// Whether the TracingPolicy YAML is present on disk.
    pub policy_present: bool,
    /// Wall-clock "now" the panel was assembled at (for freshness).
    pub now_ms: u64,
}

impl Panel {
    /// Construct an empty panel at a given wall-clock.
    #[must_use]
    pub fn new(now_ms: u64) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            recent_verdicts: Vec::new(),
            active_extensions: Vec::new(),
            policy_present: false,
            now_ms,
        }
    }

    /// Load the panel state from the canonical selfdef-emitted paths.
    /// Missing dirs/files are not errors — they surface as the empty
    /// state (Gray render).
    ///
    /// # Errors
    /// Returns `PanelError::Io` on read failure for an existing dir.
    pub fn load_from_paths(
        ring_dir: &Path,
        extension_dir: &Path,
        policy_path: &Path,
        now_ms: u64,
    ) -> Result<Self, PanelError> {
        let mut panel = Self::new(now_ms);

        // Ring buffer — recent verdicts (newest-first).
        if ring_dir.exists() {
            let read = fs::read_dir(ring_dir).map_err(|e| PanelError::Io(e.to_string()))?;
            for dirent in read {
                let dirent = dirent.map_err(|e| PanelError::Io(e.to_string()))?;
                let path = dirent.path();
                if path.extension().map_or(true, |e| e != "json") {
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

        // Extension manifests — currently-active only.
        if extension_dir.exists() {
            let read =
                fs::read_dir(extension_dir).map_err(|e| PanelError::Io(e.to_string()))?;
            for dirent in read {
                let dirent = dirent.map_err(|e| PanelError::Io(e.to_string()))?;
                let path = dirent.path();
                if path.extension().map_or(true, |e| e != "json") {
                    continue;
                }
                let bytes = match fs::read(&path) {
                    Ok(b) => b,
                    Err(_) => continue,
                };
                if let Ok(summary) = serde_json::from_slice::<ExtensionSummary>(&bytes) {
                    if summary.expires_at_ms > now_ms {
                        panel.active_extensions.push(summary);
                    }
                }
            }
            panel
                .active_extensions
                .sort_by(|a, b| a.extension_id.cmp(&b.extension_id));
        }

        panel.policy_present = policy_path.exists();
        Ok(panel)
    }

    /// Whether the panel has any data at all.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.recent_verdicts.is_empty() && self.active_extensions.is_empty()
    }

    /// Whether any verdict in the recent window is a SIGKILL.
    #[must_use]
    pub fn any_sigkill(&self) -> bool {
        self.recent_verdicts
            .iter()
            .any(|v| matches!(v.outcome, Outcome::Sigkill))
    }

    /// Top-row color aggregate.
    #[must_use]
    pub fn aggregate_color(&self) -> Color {
        if self.any_sigkill() {
            return Color::Red;
        }
        if !self.active_extensions.is_empty() {
            return Color::Yellow;
        }
        if self.is_empty() {
            return Color::Gray;
        }
        Color::Green
    }

    /// Aggregate badge text.
    #[must_use]
    pub fn aggregate_badge(&self) -> &'static str {
        match self.aggregate_color() {
            Color::Red => "ALERT",
            Color::Yellow => "EXTENDED",
            Color::Green => "OK",
            Color::Gray => "—",
        }
    }

    /// Build the row sequence the M061 dashboard renders.
    /// Order: aggregate row first, then active extensions, then recent verdicts.
    #[must_use]
    pub fn render(&self) -> Vec<RenderRow> {
        let mut rows = Vec::new();
        rows.push(self.render_aggregate());
        for ext in &self.active_extensions {
            rows.push(self.render_extension(ext));
        }
        for v in &self.recent_verdicts {
            rows.push(self.render_verdict(v));
        }
        rows
    }

    fn render_aggregate(&self) -> RenderRow {
        let color = self.aggregate_color();
        let badge = self.aggregate_badge().to_string();
        let detail = if self.policy_present {
            format!(
                "sovereign-kernel-fence active · {} verdict(s) · {} extension(s)",
                self.recent_verdicts.len(),
                self.active_extensions.len()
            )
        } else {
            "TracingPolicy NOT present — kernel-fence is OFF".to_string()
        };
        RenderRow {
            kind: RowKind::Aggregate,
            label: "Perimeter".to_string(),
            badge,
            color,
            detail,
            runbook_route: "/wiki/runbooks/perimeter-sigkill-investigation".to_string(),
        }
    }

    fn render_extension(&self, ext: &ExtensionSummary) -> RenderRow {
        let countdown = freshness_until(ext.expires_at_ms, self.now_ms);
        RenderRow {
            kind: RowKind::Extension,
            label: format!("ext: {}", ext.extension_id),
            badge: "EXTEND".to_string(),
            color: Color::Yellow,
            detail: format!(
                "{} path(s) · expires {} · signer={} auditor={}",
                ext.binary_paths.len(),
                countdown,
                ext.signer_kid,
                ext.auditor_kid
            ),
            runbook_route: "/wiki/runbooks/perimeter-extension-create".to_string(),
        }
    }

    fn render_verdict(&self, v: &Entry) -> RenderRow {
        let (badge, color, runbook) = match &v.outcome {
            Outcome::Sigkill => (
                "SIGKILL".to_string(),
                Color::Red,
                "/wiki/runbooks/perimeter-sigkill-investigation".to_string(),
            ),
            Outcome::Allowlisted => (
                "ALLOWED".to_string(),
                Color::Green,
                String::new(),
            ),
            Outcome::ExtensionAllowed { manifest_sha256, .. } => {
                let stub = manifest_sha256
                    .get(..8.min(manifest_sha256.len()))
                    .unwrap_or("");
                (
                    format!("EXTEND[{stub}]"),
                    Color::Yellow,
                    "/wiki/runbooks/perimeter-extension-create".to_string(),
                )
            }
        };
        RenderRow {
            kind: RowKind::Verdict,
            label: v.attempted_binary_path.clone(),
            badge,
            color,
            detail: format!(
                "pid={} · {} · cmdline={:?}",
                v.attempting_pid,
                freshness_since(self.now_ms, v.ts_ms),
                v.process_cmdline
            ),
            runbook_route: runbook,
        }
    }
}

/// Format a "ms ago" freshness string. Caps at 30 days; older shows
/// as "stale".
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

/// Format a "in N ms" countdown string (for extension expiry).
fn freshness_until(expires_at_ms: u64, now_ms: u64) -> String {
    if expires_at_ms <= now_ms {
        return "expired".to_string();
    }
    let delta = expires_at_ms - now_ms;
    let secs = delta / 1000;
    if secs < 60 {
        format!("in {secs}s")
    } else if secs < 3600 {
        format!("in {}m", secs / 60)
    } else if secs < 86_400 {
        format!("in {}h", secs / 3600)
    } else {
        format!("in {}d", secs / 86_400)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::path::PathBuf;

    fn tmp_dir() -> PathBuf {
        let p = std::env::temp_dir().join(format!(
            "perimeter-panel-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&p).unwrap();
        p
    }

    fn write_entry(dir: &Path, name: &str, e: &Entry) {
        let mut f = fs::File::create(dir.join(name)).unwrap();
        f.write_all(&serde_json::to_vec(e).unwrap()).unwrap();
    }

    fn sample_sigkill(ts: u64) -> Entry {
        Entry {
            outcome: Outcome::Sigkill,
            attempted_binary_path: "/usr/bin/curl".into(),
            attempting_pid: 4242,
            process_cmdline: "sshd: operator@pts/0".into(),
            ts_ms: ts,
            hostname: "host-A".into(),
        }
    }

    fn sample_allowlisted(ts: u64) -> Entry {
        Entry {
            outcome: Outcome::Allowlisted,
            attempted_binary_path: "/usr/bin/python3".into(),
            attempting_pid: 5555,
            process_cmdline: "selfdefd".into(),
            ts_ms: ts,
            hostname: "host-A".into(),
        }
    }

    fn sample_extension() -> ExtensionSummary {
        ExtensionSummary {
            extension_id: "rollout-2026q2".into(),
            binary_paths: vec!["/usr/local/bin/foo".into(), "/opt/llm/bar".into()],
            expires_at_ms: 2_000_000_000_000,
            signer_kid: "kid-op-A".into(),
            auditor_kid: "kid-aud-B".into(),
        }
    }

    #[test]
    fn empty_panel_aggregates_gray() {
        let p = Panel::new(1_700_000_000_000);
        assert_eq!(p.aggregate_color(), Color::Gray);
        assert_eq!(p.aggregate_badge(), "—");
    }

    #[test]
    fn panel_with_sigkill_aggregates_red() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_sigkill(1_700_000_000_000));
        assert_eq!(p.aggregate_color(), Color::Red);
        assert_eq!(p.aggregate_badge(), "ALERT");
    }

    #[test]
    fn panel_with_extension_only_aggregates_yellow() {
        let mut p = Panel::new(1_700_000_000_000);
        p.active_extensions.push(sample_extension());
        assert_eq!(p.aggregate_color(), Color::Yellow);
        assert_eq!(p.aggregate_badge(), "EXTENDED");
    }

    #[test]
    fn panel_clean_verdicts_aggregate_green() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_allowlisted(1_700_000_000_000));
        assert_eq!(p.aggregate_color(), Color::Green);
        assert_eq!(p.aggregate_badge(), "OK");
    }

    #[test]
    fn sigkill_overrides_extensions() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_sigkill(1_700_000_000_000));
        p.active_extensions.push(sample_extension());
        assert_eq!(p.aggregate_color(), Color::Red);
    }

    #[test]
    fn render_emits_aggregate_first() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_sigkill(1_700_000_000_000));
        let rows = p.render();
        assert!(matches!(rows[0].kind, RowKind::Aggregate));
        assert_eq!(rows[0].color, Color::Red);
    }

    #[test]
    fn render_order_aggregate_extensions_verdicts() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_sigkill(1_700_000_000_000));
        p.active_extensions.push(sample_extension());
        let rows = p.render();
        assert_eq!(rows.len(), 3);
        assert!(matches!(rows[0].kind, RowKind::Aggregate));
        assert!(matches!(rows[1].kind, RowKind::Extension));
        assert!(matches!(rows[2].kind, RowKind::Verdict));
    }

    #[test]
    fn render_sigkill_row_has_runbook_route() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_sigkill(1_700_000_000_000));
        let rows = p.render();
        let verdict_row = rows.iter().find(|r| r.kind == RowKind::Verdict).unwrap();
        assert_eq!(
            verdict_row.runbook_route,
            "/wiki/runbooks/perimeter-sigkill-investigation"
        );
        assert_eq!(verdict_row.badge, "SIGKILL");
    }

    #[test]
    fn render_allowlisted_row_has_no_runbook() {
        let mut p = Panel::new(1_700_000_000_000);
        p.recent_verdicts.push(sample_allowlisted(1_700_000_000_000));
        let rows = p.render();
        let verdict_row = rows.iter().find(|r| r.kind == RowKind::Verdict).unwrap();
        assert_eq!(verdict_row.runbook_route, "");
        assert_eq!(verdict_row.badge, "ALLOWED");
    }

    #[test]
    fn load_from_paths_missing_dirs_returns_empty() {
        let dir = tmp_dir();
        let p = Panel::load_from_paths(
            &dir.join("ring"),
            &dir.join("ext"),
            &dir.join("p.yaml"),
            1_700_000_000_000,
        )
        .unwrap();
        assert!(p.is_empty());
        assert!(!p.policy_present);
    }

    #[test]
    fn load_from_paths_reads_ring_entries() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        write_entry(&ring, "a.json", &sample_sigkill(1_700_000_000_000));
        write_entry(&ring, "b.json", &sample_allowlisted(1_700_000_001_000));
        let p = Panel::load_from_paths(
            &ring,
            &dir.join("ext"),
            &dir.join("p.yaml"),
            1_700_000_001_500,
        )
        .unwrap();
        assert_eq!(p.recent_verdicts.len(), 2);
        // Newest-first ordering:
        assert_eq!(p.recent_verdicts[0].ts_ms, 1_700_000_001_000);
        assert!(p.any_sigkill());
    }

    #[test]
    fn load_from_paths_skips_malformed_files() {
        let dir = tmp_dir();
        let ring = dir.join("ring");
        fs::create_dir_all(&ring).unwrap();
        fs::write(ring.join("bad.json"), b"{not json").unwrap();
        write_entry(&ring, "good.json", &sample_sigkill(1_700_000_000_000));
        let p = Panel::load_from_paths(
            &ring,
            &dir.join("ext"),
            &dir.join("p.yaml"),
            1_700_000_000_000,
        )
        .unwrap();
        assert_eq!(p.recent_verdicts.len(), 1);
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
                &sample_sigkill(1_700_000_000_000 + u64::from(i)),
            );
        }
        let p = Panel::load_from_paths(
            &ring,
            &dir.join("ext"),
            &dir.join("p.yaml"),
            1_700_000_000_500,
        )
        .unwrap();
        assert_eq!(p.recent_verdicts.len(), 16);
    }

    #[test]
    fn load_from_paths_filters_expired_extensions() {
        let dir = tmp_dir();
        let ext = dir.join("ext");
        fs::create_dir_all(&ext).unwrap();
        let mut summary = sample_extension();
        summary.expires_at_ms = 1_500_000_000_000; // already expired
        fs::write(
            ext.join("expired.json"),
            serde_json::to_vec(&summary).unwrap(),
        )
        .unwrap();
        let mut active = sample_extension();
        active.extension_id = "active".into();
        active.expires_at_ms = 2_000_000_000_000;
        fs::write(
            ext.join("active.json"),
            serde_json::to_vec(&active).unwrap(),
        )
        .unwrap();
        let p = Panel::load_from_paths(
            &dir.join("ring"),
            &ext,
            &dir.join("p.yaml"),
            1_700_000_000_000,
        )
        .unwrap();
        assert_eq!(p.active_extensions.len(), 1);
        assert_eq!(p.active_extensions[0].extension_id, "active");
    }

    #[test]
    fn load_from_paths_detects_policy_presence() {
        let dir = tmp_dir();
        let policy = dir.join("p.yaml");
        fs::write(&policy, b"placeholder").unwrap();
        let p = Panel::load_from_paths(
            &dir.join("ring"),
            &dir.join("ext"),
            &policy,
            1_700_000_000_000,
        )
        .unwrap();
        assert!(p.policy_present);
    }

    #[test]
    fn freshness_since_just_now() {
        assert_eq!(freshness_since(1_000_000, 1_000_000), "just now");
        assert_eq!(freshness_since(1_000_004_999, 1_000_000_000), "just now");
    }

    #[test]
    fn freshness_since_seconds_and_minutes() {
        assert_eq!(freshness_since(60_000, 0), "1m ago");
        assert_eq!(freshness_since(10_000, 0), "10s ago");
    }

    #[test]
    fn freshness_until_expired() {
        assert_eq!(freshness_until(0, 1_000_000), "expired");
    }

    #[test]
    fn freshness_until_format() {
        assert_eq!(freshness_until(1_000_000_000 + 60_000, 1_000_000_000), "in 1m");
        assert_eq!(
            freshness_until(1_000_000_000 + 3_600_000, 1_000_000_000),
            "in 1h"
        );
    }

    #[test]
    fn default_allowlist_matches_sain01_section_6_verbatim() {
        assert_eq!(
            DEFAULT_ALLOWLIST,
            &[
                "/usr/bin/python3",
                "/usr/bin/nvidia-smi",
                "/usr/local/bin/vllm",
                "/usr/bin/podman",
            ]
        );
    }
}
