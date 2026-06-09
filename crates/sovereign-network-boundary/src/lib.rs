//! `sovereign-network-boundary` — E0124 / M00232: the Network Boundary.
//!
//! Network access is not binary. A branch declares the *narrowest* network
//! scope it needs as a [`ToolIntent`], and the runtime grants it only if that
//! scope sits within the profile the operator/policy allows. The profiles form
//! a ladder of increasing reach; nothing escalates past its allowance.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 5-rung network-profile ladder (M00232), ascending reach.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum NetworkProfile {
    /// No network at all.
    Offline,
    /// Package registries only (crates.io / PyPI / npm …).
    PackageRegistries,
    /// Read-only documentation web.
    DocsWeb,
    /// Arbitrary web (any http(s) host).
    ArbitraryWeb,
    /// An authenticated browser profile (logged-in sessions).
    AuthenticatedBrowserProfile,
}

impl NetworkProfile {
    /// All 5 profiles, narrowest first.
    pub const ALL: [NetworkProfile; 5] = [
        NetworkProfile::Offline,
        NetworkProfile::PackageRegistries,
        NetworkProfile::DocsWeb,
        NetworkProfile::ArbitraryWeb,
        NetworkProfile::AuthenticatedBrowserProfile,
    ];

    /// Reach rank — higher grants strictly more network access.
    #[must_use]
    pub fn rank(self) -> u8 {
        match self {
            NetworkProfile::Offline => 0,
            NetworkProfile::PackageRegistries => 1,
            NetworkProfile::DocsWeb => 2,
            NetworkProfile::ArbitraryWeb => 3,
            NetworkProfile::AuthenticatedBrowserProfile => 4,
        }
    }
}

/// A per-branch network intent (M00232 / F01182 + F01183): the narrowest scope
/// a unit of work needs, plus the reason it needs it (for the audit trail).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolIntent {
    /// The narrowest network profile this work requires.
    pub network_scope: NetworkProfile,
    /// Why the work needs it.
    pub reason: String,
}

impl ToolIntent {
    /// Declare an intent.
    #[must_use]
    pub fn new(network_scope: NetworkProfile, reason: impl Into<String>) -> Self {
        Self {
            network_scope,
            reason: reason.into(),
        }
    }
}

/// Whether `intent` is permitted under the `allowed` profile: the requested
/// scope must sit at or below the allowance. A docs-web intent is fine under
/// arbitrary-web, but an arbitrary-web intent is denied under offline.
#[must_use]
pub fn is_within_allowance(intent: &ToolIntent, allowed: NetworkProfile) -> bool {
    intent.network_scope.rank() <= allowed.rank()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_profiles_strictly_ranked() {
        assert_eq!(NetworkProfile::ALL.len(), 5);
        assert!(NetworkProfile::Offline.rank() < NetworkProfile::PackageRegistries.rank());
        assert!(
            NetworkProfile::ArbitraryWeb.rank()
                < NetworkProfile::AuthenticatedBrowserProfile.rank()
        );
    }

    #[test]
    fn narrower_intent_is_allowed_under_broader_profile() {
        let docs = ToolIntent::new(NetworkProfile::DocsWeb, "read rust docs");
        assert!(is_within_allowance(&docs, NetworkProfile::ArbitraryWeb));
        assert!(is_within_allowance(
            &docs,
            NetworkProfile::AuthenticatedBrowserProfile
        ));
        // exactly at the allowance is fine.
        assert!(is_within_allowance(&docs, NetworkProfile::DocsWeb));
    }

    #[test]
    fn broader_intent_is_denied_under_narrower_profile() {
        let web = ToolIntent::new(NetworkProfile::ArbitraryWeb, "fetch a blog");
        assert!(!is_within_allowance(&web, NetworkProfile::Offline));
        assert!(!is_within_allowance(
            &web,
            NetworkProfile::PackageRegistries
        ));
        assert!(!is_within_allowance(&web, NetworkProfile::DocsWeb));
    }

    #[test]
    fn offline_allows_only_offline_intents() {
        let offline = ToolIntent::new(NetworkProfile::Offline, "pure compute");
        assert!(is_within_allowance(&offline, NetworkProfile::Offline));
        for p in NetworkProfile::ALL
            .into_iter()
            .filter(|p| *p != NetworkProfile::Offline)
        {
            let intent = ToolIntent::new(p, "needs net");
            assert!(
                !is_within_allowance(&intent, NetworkProfile::Offline),
                "{p:?}"
            );
        }
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&NetworkProfile::PackageRegistries).unwrap(),
            "\"package-registries\""
        );
        let i = ToolIntent::new(NetworkProfile::DocsWeb, "docs");
        let v: serde_json::Value = serde_json::to_value(&i).unwrap();
        assert_eq!(v["network_scope"], "docs-web");
        assert_eq!(v["reason"], "docs");
    }
}
