//! `sovereign-cockpit-online-status` — connection-status indicator.
//!
//! 4 states (Online/Reconnecting/Offline/Unknown). heartbeat(now)
//! resets to Online. tick(now) degrades Online → Reconnecting after
//! `reconnect_after_ms`, then → Offline after `offline_after_ms`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Online.
    Online,
    /// Reconnecting.
    Reconnecting,
    /// Offline.
    Offline,
    /// Unknown (initial / never had heartbeat).
    Unknown,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OnlineStatus {
    /// Schema version.
    pub schema_version: String,
    /// Status.
    pub status: Status,
    /// Last heartbeat wall-clock ms.
    pub last_heartbeat_ms: u64,
    /// ms after which Online → Reconnecting (no heartbeat).
    pub reconnect_after_ms: u32,
    /// ms after which Reconnecting → Offline.
    pub offline_after_ms: u32,
    /// Reason text (operator-facing).
    pub reason: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum OnlineError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// reconnect_after_ms zero.
    #[error("reconnect_after_ms zero")]
    ReconnectZero,
    /// offline_after_ms <= reconnect.
    #[error("offline_after_ms {off} <= reconnect_after_ms {rec}")]
    BadOfflineThreshold {
        /// off.
        off: u32,
        /// rec.
        rec: u32,
    },
}

impl OnlineStatus {
    /// New initially Unknown.
    pub fn new(reconnect_after_ms: u32, offline_after_ms: u32) -> Result<Self, OnlineError> {
        if reconnect_after_ms == 0 {
            return Err(OnlineError::ReconnectZero);
        }
        if offline_after_ms <= reconnect_after_ms {
            return Err(OnlineError::BadOfflineThreshold {
                off: offline_after_ms,
                rec: reconnect_after_ms,
            });
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            status: Status::Unknown,
            last_heartbeat_ms: 0,
            reconnect_after_ms,
            offline_after_ms,
            reason: String::new(),
        })
    }

    /// Heartbeat — sets Online, records timestamp.
    pub fn heartbeat(&mut self, now_ms: u64) {
        self.status = Status::Online;
        self.last_heartbeat_ms = now_ms;
        self.reason.clear();
    }

    /// Tick — degrades status based on time since last heartbeat.
    pub fn tick(&mut self, now_ms: u64) {
        if self.last_heartbeat_ms == 0 {
            return;
        }
        let elapsed = now_ms.saturating_sub(self.last_heartbeat_ms);
        if elapsed >= self.offline_after_ms as u64 {
            self.status = Status::Offline;
            self.reason = format!("no heartbeat for {elapsed}ms");
        } else if elapsed >= self.reconnect_after_ms as u64 {
            self.status = Status::Reconnecting;
            self.reason = format!("reconnecting ({elapsed}ms since last heartbeat)");
        } else {
            self.status = Status::Online;
            self.reason.clear();
        }
    }

    /// Mark offline manually with reason.
    pub fn mark_offline(&mut self, reason: &str) {
        self.status = Status::Offline;
        self.reason = reason.into();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), OnlineError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(OnlineError::SchemaMismatch);
        }
        if self.reconnect_after_ms == 0 {
            return Err(OnlineError::ReconnectZero);
        }
        if self.offline_after_ms <= self.reconnect_after_ms {
            return Err(OnlineError::BadOfflineThreshold {
                off: self.offline_after_ms,
                rec: self.reconnect_after_ms,
            });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s() -> OnlineStatus {
        OnlineStatus::new(2_000, 10_000).unwrap()
    }

    #[test]
    fn zero_reconnect_rejected() {
        assert!(matches!(
            OnlineStatus::new(0, 1).unwrap_err(),
            OnlineError::ReconnectZero
        ));
    }

    #[test]
    fn offline_le_reconnect_rejected() {
        assert!(matches!(
            OnlineStatus::new(2_000, 1_000).unwrap_err(),
            OnlineError::BadOfflineThreshold { .. }
        ));
    }

    #[test]
    fn initial_unknown() {
        assert_eq!(s().status, Status::Unknown);
    }

    #[test]
    fn heartbeat_makes_online() {
        let mut s = s();
        s.heartbeat(100);
        assert_eq!(s.status, Status::Online);
    }

    #[test]
    fn tick_degrades_to_reconnecting() {
        let mut s = s();
        s.heartbeat(100);
        s.tick(3_000);
        assert_eq!(s.status, Status::Reconnecting);
        assert!(!s.reason.is_empty());
    }

    #[test]
    fn tick_degrades_to_offline() {
        let mut s = s();
        s.heartbeat(100);
        s.tick(20_000);
        assert_eq!(s.status, Status::Offline);
    }

    #[test]
    fn tick_returns_online_after_heartbeat() {
        let mut s = s();
        s.heartbeat(100);
        s.tick(3_000);
        s.heartbeat(3_500);
        s.tick(4_000);
        assert_eq!(s.status, Status::Online);
        assert!(s.reason.is_empty());
    }

    #[test]
    fn tick_unknown_when_never_heartbeat() {
        let mut s = s();
        s.tick(10_000);
        assert_eq!(s.status, Status::Unknown);
    }

    #[test]
    fn mark_offline_manual() {
        let mut s = s();
        s.mark_offline("kernel panic");
        assert_eq!(s.status, Status::Offline);
        assert_eq!(s.reason, "kernel panic");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = s();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            OnlineError::SchemaMismatch
        ));
    }

    #[test]
    fn status_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Status::Reconnecting).unwrap(),
            "\"reconnecting\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let mut s = s();
        s.heartbeat(100);
        let j = serde_json::to_string(&s).unwrap();
        let back: OnlineStatus = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
