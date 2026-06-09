//! `sovereign-cockpit-views` — E0496 §10: the cockpit's required views.
//!
//! "Fullstack here is not marketing UI. It is cockpit design." A sovereign
//! station's cockpit must answer seven operational questions at all times. This
//! crate fixes those seven required views and a coverage gate, so a cockpit
//! that silently drops one (say, what can be rolled back) is caught.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

/// The 7 views every cockpit must surface (E0496 §10).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CockpitView {
    /// What is running.
    WhatIsRunning,
    /// What it costs.
    WhatItCosts,
    /// What it can touch (capabilities / scopes).
    WhatItCanTouch,
    /// What it changed.
    WhatItChanged,
    /// What is waiting for approval.
    WhatIsWaitingForApproval,
    /// What can be resumed.
    WhatCanBeResumed,
    /// What can be rolled back.
    WhatCanBeRolledBack,
}

impl CockpitView {
    /// All 7 required views.
    pub const ALL: [CockpitView; 7] = [
        CockpitView::WhatIsRunning,
        CockpitView::WhatItCosts,
        CockpitView::WhatItCanTouch,
        CockpitView::WhatItChanged,
        CockpitView::WhatIsWaitingForApproval,
        CockpitView::WhatCanBeResumed,
        CockpitView::WhatCanBeRolledBack,
    ];
}

/// The set of views a cockpit actually surfaces, checked against the required 7.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct CockpitCoverage {
    surfaced: BTreeSet<CockpitView>,
}

impl CockpitCoverage {
    /// A new, empty coverage.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Record that a view is surfaced.
    pub fn surface(&mut self, view: CockpitView) {
        self.surfaced.insert(view);
    }

    /// The required views the cockpit is NOT surfacing.
    #[must_use]
    pub fn missing_views(&self) -> Vec<CockpitView> {
        CockpitView::ALL
            .into_iter()
            .filter(|v| !self.surfaced.contains(v))
            .collect()
    }

    /// Whether the cockpit surfaces all 7 required views.
    #[must_use]
    pub fn is_complete(&self) -> bool {
        self.missing_views().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seven_required_views() {
        assert_eq!(CockpitView::ALL.len(), 7);
    }

    #[test]
    fn empty_cockpit_misses_all_seven() {
        let c = CockpitCoverage::new();
        assert!(!c.is_complete());
        assert_eq!(c.missing_views().len(), 7);
    }

    #[test]
    fn full_cockpit_is_complete() {
        let mut c = CockpitCoverage::new();
        for v in CockpitView::ALL {
            c.surface(v);
        }
        assert!(c.is_complete());
        assert!(c.missing_views().is_empty());
    }

    #[test]
    fn dropping_rollback_view_is_caught() {
        // The reversibility view is load-bearing for a sovereign station.
        let mut c = CockpitCoverage::new();
        for v in CockpitView::ALL.into_iter().filter(|v| *v != CockpitView::WhatCanBeRolledBack) {
            c.surface(v);
        }
        assert!(!c.is_complete());
        assert_eq!(c.missing_views(), vec![CockpitView::WhatCanBeRolledBack]);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&CockpitView::WhatIsWaitingForApproval).unwrap(),
            "\"what-is-waiting-for-approval\""
        );
    }
}
