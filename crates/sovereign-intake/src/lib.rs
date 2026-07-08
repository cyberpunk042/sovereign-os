//! `sovereign-intake` — E0549: Step 1 Intake.
//!
//! The first step of the task lifecycle. A task can arrive from any of ten
//! sources, and the gateway stamps every request with six fields so the rest
//! of the lifecycle has a stable, typed handle from the very start. `trace_id`
//! is the [`sovereign_trace_context`] id, so a task is locatable in its
//! reconstructable trace (E0112) from intake onward.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_trace_context::TraceId;

/// The ten task sources a request can arrive from (E0549).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TaskSource {
    /// Claude Code.
    ClaudeCode,
    /// Cline.
    Cline,
    /// OpenCode.
    OpenCode,
    /// The local cockpit dashboard.
    LocalDashboard,
    /// The CLI.
    Cli,
    /// An MCP client.
    Mcp,
    /// The HTTP API.
    Api,
    /// Scheduled automation (timer/cron).
    ScheduledAutomation,
    /// A file watcher.
    FileWatcher,
    /// Human voice/text (later).
    HumanVoiceText,
}

impl TaskSource {
    /// All ten sources.
    pub const ALL: [TaskSource; 10] = [
        TaskSource::ClaudeCode,
        TaskSource::Cline,
        TaskSource::OpenCode,
        TaskSource::LocalDashboard,
        TaskSource::Cli,
        TaskSource::Mcp,
        TaskSource::Api,
        TaskSource::ScheduledAutomation,
        TaskSource::FileWatcher,
        TaskSource::HumanVoiceText,
    ];
}

/// Privacy context the request arrives under — a coarse handle the policy
/// fabric (E0473) refines.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PrivacyContext {
    /// No special handling.
    Public,
    /// Keep local; cloud allowed with care.
    Private,
    /// Never leaves the host.
    LocalOnly,
}

/// The six fields the gateway stamps on every intake (E0549).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IntakeRequest {
    /// Which of the ten sources this came from.
    pub source: TaskSource,
    /// 1. request_id — unique per request.
    pub request_id: String,
    /// 2. trace_id — the E0112 trace this request opens.
    pub trace_id: TraceId,
    /// 3. client_id — the originating client.
    pub client_id: String,
    /// 4. profile_hint — a suggested operating profile (resolved later).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile_hint: Option<String>,
    /// 5. privacy_context.
    pub privacy_context: PrivacyContext,
    /// 6. budget_hint — a suggested spend ceiling in USD.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub budget_hint: Option<f64>,
}

impl IntakeRequest {
    /// Stamp a new intake request with the required identity fields. Optional
    /// hints (profile, budget) default to `None`.
    #[must_use]
    pub fn new(
        source: TaskSource,
        request_id: impl Into<String>,
        trace_id: TraceId,
        client_id: impl Into<String>,
        privacy_context: PrivacyContext,
    ) -> Self {
        Self {
            source,
            request_id: request_id.into(),
            trace_id,
            client_id: client_id.into(),
            profile_hint: None,
            privacy_context,
            budget_hint: None,
        }
    }

    /// Whether the required identity is present (non-empty request_id +
    /// client_id) — a malformed intake the gateway should reject.
    #[must_use]
    pub fn has_identity(&self) -> bool {
        !self.request_id.trim().is_empty() && !self.client_id.trim().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ten_distinct_sources() {
        use std::collections::HashSet;
        assert_eq!(TaskSource::ALL.len(), 10);
        assert_eq!(TaskSource::ALL.iter().collect::<HashSet<_>>().len(), 10);
    }

    #[test]
    fn intake_carries_trace_id_from_e0112() {
        let r = IntakeRequest::new(
            TaskSource::ClaudeCode,
            "req-1",
            TraceId(0xfeed),
            "client-a",
            PrivacyContext::Private,
        );
        assert_eq!(r.trace_id, TraceId(0xfeed));
        assert!(r.has_identity());
        assert!(r.profile_hint.is_none());
    }

    #[test]
    fn missing_identity_is_detected() {
        let r = IntakeRequest::new(
            TaskSource::Api,
            "  ",
            TraceId(1),
            "client",
            PrivacyContext::Public,
        );
        assert!(!r.has_identity());
    }

    #[test]
    fn roundtrips_and_omits_empty_hints() {
        let r = IntakeRequest::new(
            TaskSource::FileWatcher,
            "req-2",
            TraceId(2),
            "watcher",
            PrivacyContext::LocalOnly,
        );
        let v: serde_json::Value = serde_json::to_value(&r).unwrap();
        assert_eq!(v["source"], "file-watcher");
        assert_eq!(v["privacy_context"], "local-only");
        assert!(v.get("profile_hint").is_none()); // omitted when None
        let back: IntakeRequest = serde_json::from_value(v).unwrap();
        assert_eq!(r, back);
    }

    #[test]
    fn hints_present_when_set() {
        let mut r = IntakeRequest::new(
            TaskSource::Cli,
            "req-3",
            TraceId(3),
            "cli",
            PrivacyContext::Public,
        );
        r.profile_hint = Some("careful".into());
        r.budget_hint = Some(2.50);
        let v: serde_json::Value = serde_json::to_value(&r).unwrap();
        assert_eq!(v["profile_hint"], "careful");
        assert!((v["budget_hint"].as_f64().unwrap() - 2.50).abs() < 1e-9);
    }
}
