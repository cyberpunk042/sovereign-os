//! `sovereign-cockpit-route-history` — UI back/forward navigation.
//!
//! Bounded back stack (LIFO of past routes) + forward stack (built up
//! when going back). Navigating to a new route clears forward.
//! Capacity 50.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max history depth.
pub const MAX_DEPTH: usize = 50;

/// Route history.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RouteHistory {
    /// Schema version.
    pub schema_version: String,
    /// Current route.
    pub current: String,
    /// Back stack (most-recent last).
    pub back: Vec<String>,
    /// Forward stack (most-recent last).
    pub forward: Vec<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RouteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty route.
    #[error("route empty")]
    EmptyRoute,
    /// Nothing to go back to.
    #[error("back stack empty")]
    NothingBack,
    /// Nothing to go forward to.
    #[error("forward stack empty")]
    NothingForward,
}

impl RouteHistory {
    /// New with an initial route.
    pub fn new(initial: &str) -> Result<Self, RouteError> {
        if initial.is_empty() {
            return Err(RouteError::EmptyRoute);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            current: initial.into(),
            back: Vec::new(),
            forward: Vec::new(),
        })
    }

    /// Navigate to a new route (clears forward).
    pub fn navigate(&mut self, route: &str) -> Result<(), RouteError> {
        if route.is_empty() {
            return Err(RouteError::EmptyRoute);
        }
        if route == self.current {
            return Ok(());
        }
        let prev = std::mem::replace(&mut self.current, route.into());
        self.back.push(prev);
        while self.back.len() > MAX_DEPTH {
            self.back.remove(0);
        }
        self.forward.clear();
        Ok(())
    }

    /// Step back.
    pub fn back(&mut self) -> Result<&str, RouteError> {
        let prev = self.back.pop().ok_or(RouteError::NothingBack)?;
        let cur = std::mem::replace(&mut self.current, prev);
        self.forward.push(cur);
        Ok(&self.current)
    }

    /// Step forward.
    pub fn forward(&mut self) -> Result<&str, RouteError> {
        let next = self.forward.pop().ok_or(RouteError::NothingForward)?;
        let cur = std::mem::replace(&mut self.current, next);
        self.back.push(cur);
        Ok(&self.current)
    }

    /// True if back is available.
    pub fn can_go_back(&self) -> bool {
        !self.back.is_empty()
    }

    /// True if forward is available.
    pub fn can_go_forward(&self) -> bool {
        !self.forward.is_empty()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RouteError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RouteError::SchemaMismatch);
        }
        if self.current.is_empty() {
            return Err(RouteError::EmptyRoute);
        }
        for r in self.back.iter().chain(self.forward.iter()) {
            if r.is_empty() {
                return Err(RouteError::EmptyRoute);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_initial_rejected() {
        assert!(matches!(
            RouteHistory::new("").unwrap_err(),
            RouteError::EmptyRoute
        ));
    }

    #[test]
    fn navigate_back_forward_cycle() {
        let mut h = RouteHistory::new("/home").unwrap();
        h.navigate("/dashboards").unwrap();
        h.navigate("/dashboards/d-13").unwrap();
        assert_eq!(h.current, "/dashboards/d-13");
        assert!(h.can_go_back());
        assert_eq!(h.back().unwrap(), "/dashboards");
        assert_eq!(h.back().unwrap(), "/home");
        assert!(!h.can_go_back());
        assert_eq!(h.forward().unwrap(), "/dashboards");
        assert_eq!(h.forward().unwrap(), "/dashboards/d-13");
    }

    #[test]
    fn navigate_clears_forward() {
        let mut h = RouteHistory::new("/a").unwrap();
        h.navigate("/b").unwrap();
        h.back().unwrap();
        assert!(h.can_go_forward());
        h.navigate("/c").unwrap();
        assert!(!h.can_go_forward());
    }

    #[test]
    fn navigate_same_route_no_op() {
        let mut h = RouteHistory::new("/a").unwrap();
        h.navigate("/a").unwrap();
        assert!(!h.can_go_back());
    }

    #[test]
    fn back_on_empty_rejected() {
        let mut h = RouteHistory::new("/a").unwrap();
        assert!(matches!(h.back().unwrap_err(), RouteError::NothingBack));
    }

    #[test]
    fn forward_on_empty_rejected() {
        let mut h = RouteHistory::new("/a").unwrap();
        assert!(matches!(
            h.forward().unwrap_err(),
            RouteError::NothingForward
        ));
    }

    #[test]
    fn back_stack_capped() {
        let mut h = RouteHistory::new("/start").unwrap();
        for i in 0..MAX_DEPTH + 10 {
            h.navigate(&format!("/route-{i}")).unwrap();
        }
        assert_eq!(h.back.len(), MAX_DEPTH);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut h = RouteHistory::new("/a").unwrap();
        h.schema_version = "9.9.9".into();
        assert!(matches!(
            h.validate().unwrap_err(),
            RouteError::SchemaMismatch
        ));
    }

    #[test]
    fn history_serde_roundtrip() {
        let mut h = RouteHistory::new("/a").unwrap();
        h.navigate("/b").unwrap();
        let j = serde_json::to_string(&h).unwrap();
        let back: RouteHistory = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
    }
}
