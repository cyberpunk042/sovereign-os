//! `sovereign-config-resolver` — E0476 / M00827: Configuration Continuity.
//!
//! "Configuration is not just settings. It is the continuity of choice." Seven
//! layered config types stack, and the runtime resolves them per action so
//! "flexibility does not become chaos." This crate fixes the layer set and the
//! precedence by which a key resolves, encoding the catalogued 5
//! conflict-resolution rules:
//!
//! 1. hard policy beats profile                  → `Policy` outranks `Runtime`/`User`
//! 2. project policy beats generic profile       → `Project` outranks `User`
//! 3. user approval can elevate only within hard limits → [`LayeredConfig::resolve_capped`]
//! 4. offline mode beats cloud route             → [`offline_beats_cloud`]
//! 5. sandbox requirement beats host convenience → `Os`(sandbox) outranks host convenience
//!
//! Rules 1, 2, 5 are encoded directly in [`ConfigLayer::precedence`]; rules 3
//! and 4 are value-semantic and provided as explicit helpers.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// The 7 layered config types (E0476).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ConfigLayer {
    /// Hardware config (GPUs / PCIe / MIG / VFIO / drivers) — physical facts.
    Hardware,
    /// OS config (AppArmor / cgroups / ZFS / networking / LUKS), incl. sandbox.
    Os,
    /// Runtime config (models / providers / profiles / routes).
    Runtime,
    /// Policy config (permissions / gates / cloud / secrets / memory exposure).
    Policy,
    /// Workflow config (MAP / SPEC / TDD / EVAL rules).
    Workflow,
    /// User config (preferences / cost limits / communication style).
    User,
    /// Project config (repo rules / tests / allowed tools / memory scope).
    Project,
}

impl ConfigLayer {
    /// Resolution precedence — higher wins when two layers define a key.
    ///
    /// Encodes conflict-resolution rules 1, 2, and 5: hard `Policy` is supreme
    /// (rule 1), `Project` outranks the generic `User` profile (rule 2), and
    /// `Os` (which carries the sandbox requirement) outranks host-convenience
    /// `Runtime`/`User` (rule 5). `Hardware` sits just under `Policy` because
    /// physical facts can't be wished away by a profile.
    #[must_use]
    pub fn precedence(self) -> u8 {
        match self {
            ConfigLayer::Policy => 7,
            ConfigLayer::Hardware => 6,
            ConfigLayer::Os => 5,
            ConfigLayer::Project => 4,
            ConfigLayer::Runtime => 3,
            ConfigLayer::Workflow => 2,
            ConfigLayer::User => 1,
        }
    }
}

/// A stack of per-layer key→value config, resolved by precedence per action.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LayeredConfig {
    layers: HashMap<ConfigLayer, HashMap<String, String>>,
}

impl LayeredConfig {
    /// Empty config.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Set a key in one layer.
    pub fn set(&mut self, layer: ConfigLayer, key: impl Into<String>, value: impl Into<String>) {
        self.layers
            .entry(layer)
            .or_default()
            .insert(key.into(), value.into());
    }

    /// Resolve a key to the value from the highest-precedence layer that
    /// defines it, returning that layer too (so the caller can see *why*).
    #[must_use]
    pub fn resolve(&self, key: &str) -> Option<(ConfigLayer, &str)> {
        self.layers
            .iter()
            .filter_map(|(layer, kv)| kv.get(key).map(|v| (*layer, v.as_str())))
            .max_by_key(|(layer, _)| layer.precedence())
    }

    /// Rule 3 — *user approval can elevate only within hard limits*: take the
    /// `User` value for `key` if present, but never above the `Policy` hard
    /// limit for the same key. Returns the effective value: the user's choice
    /// when it's within (or no) hard limit, otherwise the hard limit. Values
    /// are compared numerically; a non-numeric hard limit is treated as an
    /// exact allow-list (user must match it).
    #[must_use]
    pub fn resolve_capped(&self, key: &str) -> Option<String> {
        let user = self
            .layers
            .get(&ConfigLayer::User)
            .and_then(|kv| kv.get(key));
        let hard = self
            .layers
            .get(&ConfigLayer::Policy)
            .and_then(|kv| kv.get(key));
        match (user, hard) {
            (Some(u), Some(h)) => match (u.parse::<f64>(), h.parse::<f64>()) {
                (Ok(uv), Ok(hv)) => Some(if uv <= hv { u.clone() } else { h.clone() }),
                // Non-numeric hard limit = exact allow: user must match it.
                _ => Some(if u == h { u.clone() } else { h.clone() }),
            },
            (Some(u), None) => Some(u.clone()),
            (None, Some(h)) => Some(h.clone()),
            (None, None) => None,
        }
    }
}

/// Rule 4 — *offline mode beats cloud route*: if `offline` is set, a route that
/// would go to the cloud is overridden to the local fallback.
#[must_use]
pub fn offline_beats_cloud(offline: bool, requested_route: &str, local_fallback: &str) -> String {
    if offline && requested_route.eq_ignore_ascii_case("cloud") {
        local_fallback.to_string()
    } else {
        requested_route.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seven_layers_have_distinct_precedence() {
        use std::collections::HashSet;
        let layers = [
            ConfigLayer::Hardware,
            ConfigLayer::Os,
            ConfigLayer::Runtime,
            ConfigLayer::Policy,
            ConfigLayer::Workflow,
            ConfigLayer::User,
            ConfigLayer::Project,
        ];
        let ranks: HashSet<u8> = layers.iter().map(|l| l.precedence()).collect();
        assert_eq!(ranks.len(), 7, "all 7 precedences distinct");
        assert_eq!(ConfigLayer::Policy.precedence(), 7, "policy is supreme");
    }

    #[test]
    fn rule1_hard_policy_beats_profile() {
        let mut c = LayeredConfig::new();
        c.set(ConfigLayer::Runtime, "cloud_allowed", "true"); // profile says yes
        c.set(ConfigLayer::Policy, "cloud_allowed", "false"); // hard policy says no
        assert_eq!(
            c.resolve("cloud_allowed"),
            Some((ConfigLayer::Policy, "false"))
        );
    }

    #[test]
    fn rule2_project_beats_generic_user_profile() {
        let mut c = LayeredConfig::new();
        c.set(ConfigLayer::User, "max_branches", "16"); // generic profile
        c.set(ConfigLayer::Project, "max_branches", "4"); // project rule
        assert_eq!(c.resolve("max_branches"), Some((ConfigLayer::Project, "4")));
    }

    #[test]
    fn rule5_os_sandbox_beats_host_convenience() {
        let mut c = LayeredConfig::new();
        c.set(ConfigLayer::Runtime, "network", "host"); // host convenience
        c.set(ConfigLayer::Os, "network", "none"); // sandbox requirement
        assert_eq!(c.resolve("network"), Some((ConfigLayer::Os, "none")));
    }

    #[test]
    fn rule3_user_elevation_capped_by_hard_limit() {
        let mut c = LayeredConfig::new();
        c.set(ConfigLayer::Policy, "cost_limit_usd", "10"); // hard limit
        c.set(ConfigLayer::User, "cost_limit_usd", "100"); // user wants more
        assert_eq!(c.resolve_capped("cost_limit_usd").as_deref(), Some("10"));
        // within the limit, the user value stands.
        c.set(ConfigLayer::User, "cost_limit_usd", "5");
        assert_eq!(c.resolve_capped("cost_limit_usd").as_deref(), Some("5"));
    }

    #[test]
    fn rule4_offline_overrides_cloud_route() {
        assert_eq!(
            offline_beats_cloud(true, "cloud", "local-3090"),
            "local-3090"
        );
        assert_eq!(offline_beats_cloud(false, "cloud", "local-3090"), "cloud");
        assert_eq!(offline_beats_cloud(true, "local", "local-3090"), "local");
    }

    #[test]
    fn resolve_missing_key_is_none() {
        let c = LayeredConfig::new();
        assert!(c.resolve("nope").is_none());
        assert!(c.resolve_capped("nope").is_none());
    }
}
