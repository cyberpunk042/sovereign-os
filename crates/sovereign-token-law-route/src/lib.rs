//! `sovereign-token-law-route` — the **route** token-law source (SDD-517).
//!
//! The M00117 milestone always named a *route* plane alongside grammar / regex /
//! safety / policy, but it stayed unbuilt for an honest reason: the 7-axis router
//! ([`sovereign_router_7axis`]) outputs an [`SrpRole`] — a **compute tier**
//! (Conductor = CPU, Logic = RTX 5090, Oracle = Blackwell, Cloud), *not* a
//! vocabulary subset. There is no honest `SrpRole → allow-bitset` table: which
//! GPU runs a task says nothing about which *tokens* are allowed.
//!
//! What the routing decision *does* carry that is token-law-relevant is its
//! **axes** — `privacy` (Public ⇒ cloud egress is acceptable) and `safety` — plus
//! whether the chosen role sends data off the device (`Cloud`). So the route is a
//! source not by mapping a role to tokens, but by **binding a routing decision to
//! a token-law profile**: when a task's placement means personal data or secrets
//! could leave the device, the engine **forces the intrinsic egress guards on** —
//! the PII-completion plane (SDD-516) and the entropy plane (SDD-513) — no matter
//! what the request asked for.
//!
//! This crate is deliberately **dependency-light**: it carries only the decision
//! logic and a [`RouteProfile`] of **flags** (`force_pii` / `force_entropy` /
//! `force_safety_denylist`), depending on `sovereign-router-7axis` for the axis
//! types and `serde` for the operator config. The serving boundary
//! (`sovereign-gatewayd`) applies the flags using the constraint types it already
//! holds, so this crate never depends on the plane crates.
//!
//! It **complements, never replaces**, an explicit per-request `token_law`: a
//! request may still add planes; the route only ever forces the egress guards
//! **on**, never off — so a stricter request stays strict, and a lax one is
//! tightened when its routing demands it.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_router_7axis::{Privacy, Safety, SrpRole};

/// Schema version of the token-law-route surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The token-law profile a routing decision selects: which planes the engine
/// **forces on** for this route, on top of whatever the request already carries.
/// All-false is a no-op — the route contributes nothing (a local, private, safe
/// task is unconstrained by routing).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RouteProfile {
    /// Force the PII-completion plane on (SDD-516) — an intrinsic egress guard.
    #[serde(default)]
    pub force_pii: bool,
    /// Force the entropy plane on (SDD-513) — an intrinsic egress guard.
    #[serde(default)]
    pub force_entropy: bool,
    /// Keep the safety denylist (`denylist` + `regex_denylist`) selected for this
    /// route. Only bites if the request carries denylist / regex-denylist sources
    /// (this flag never invents deny strings — it forbids their deselection).
    #[serde(default)]
    pub force_safety_denylist: bool,
}

impl RouteProfile {
    /// Whether this profile forces nothing — the route makes no contribution.
    pub fn is_noop(&self) -> bool {
        !self.force_pii && !self.force_entropy && !self.force_safety_denylist
    }
}

/// A routing decision reduced to the axes that bind a token-law profile: the
/// assigned compute [`SrpRole`], the [`Privacy`] envelope, and the [`Safety`]
/// class. This is the wire shape a serving request carries (a `token_law.route`
/// object) — the caller supplies it from the router's `RouteDecision` + the
/// task's axes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct RouteDirective {
    /// The compute tier the 7-axis router assigned.
    pub role: SrpRole,
    /// The privacy envelope (Public ⇒ cloud egress acceptable).
    pub privacy: Privacy,
    /// The safety class.
    pub safety: Safety,
}

/// An operator-configured map from a routing decision to a [`RouteProfile`]. An
/// absent per-role override falls back to the **built-in doctrine**
/// ([`RouteProfileMap::doctrine`]); a present override **replaces** the doctrine
/// for that role (the operator takes full control of that role's profile).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RouteProfileMap {
    /// Override for `Conductor` (CPU) — absent ⇒ doctrine.
    #[serde(default)]
    pub conductor: Option<RouteProfile>,
    /// Override for `Logic` (mid GPU) — absent ⇒ doctrine.
    #[serde(default)]
    pub logic: Option<RouteProfile>,
    /// Override for `Oracle` (top GPU) — absent ⇒ doctrine.
    #[serde(default)]
    pub oracle: Option<RouteProfile>,
    /// Override for `Cloud` — absent ⇒ doctrine.
    #[serde(default)]
    pub cloud: Option<RouteProfile>,
}

impl RouteProfileMap {
    /// The built-in doctrine (no operator override): **data leaves the device**
    /// when the role is `Cloud` OR the privacy envelope is `Public` — force the
    /// two intrinsic egress guards (PII + entropy) on; and when safety is `Risky`,
    /// keep the safety denylist selected. A local, private, safe task gets a no-op
    /// profile (routing forces nothing).
    pub fn doctrine(role: SrpRole, privacy: Privacy, safety: Safety) -> RouteProfile {
        let data_leaves_device =
            matches!(role, SrpRole::Cloud) || matches!(privacy, Privacy::Public);
        RouteProfile {
            force_pii: data_leaves_device,
            force_entropy: data_leaves_device,
            force_safety_denylist: matches!(safety, Safety::Risky),
        }
    }

    /// Resolve the profile for a routing decision: the operator's per-role override
    /// if present, else the [`doctrine`](Self::doctrine).
    pub fn resolve(&self, role: SrpRole, privacy: Privacy, safety: Safety) -> RouteProfile {
        match self.override_for(role) {
            Some(p) => p,
            None => Self::doctrine(role, privacy, safety),
        }
    }

    /// Resolve directly from a [`RouteDirective`].
    pub fn resolve_directive(&self, d: &RouteDirective) -> RouteProfile {
        self.resolve(d.role, d.privacy, d.safety)
    }

    fn override_for(&self, role: SrpRole) -> Option<RouteProfile> {
        match role {
            SrpRole::Conductor => self.conductor,
            SrpRole::Logic => self.logic,
            SrpRole::Oracle => self.oracle,
            SrpRole::Cloud => self.cloud,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cloud_role_forces_the_egress_guards_on() {
        let p = RouteProfileMap::doctrine(SrpRole::Cloud, Privacy::Private, Safety::Safe);
        assert!(
            p.force_pii && p.force_entropy,
            "cloud egress forces PII + entropy"
        );
    }

    #[test]
    fn public_privacy_forces_the_egress_guards_even_on_a_local_role() {
        let p = RouteProfileMap::doctrine(SrpRole::Conductor, Privacy::Public, Safety::Safe);
        assert!(
            p.force_pii && p.force_entropy,
            "public egress forces the guards"
        );
    }

    #[test]
    fn local_private_safe_is_a_noop() {
        let p = RouteProfileMap::doctrine(SrpRole::Logic, Privacy::Private, Safety::Safe);
        assert!(
            p.is_noop(),
            "a local private safe task is unconstrained by routing"
        );
    }

    #[test]
    fn risky_safety_keeps_the_denylist_selected() {
        let p = RouteProfileMap::doctrine(SrpRole::Oracle, Privacy::Private, Safety::Risky);
        assert!(p.force_safety_denylist);
        assert!(
            !p.force_pii,
            "safety alone does not force the egress guards"
        );
    }

    #[test]
    fn an_operator_override_replaces_the_doctrine_for_that_role() {
        // Operator says: even a Cloud task forces nothing (they accept the risk).
        let map = RouteProfileMap {
            cloud: Some(RouteProfile::default()),
            ..Default::default()
        };
        let p = map.resolve(SrpRole::Cloud, Privacy::Public, Safety::Risky);
        assert!(p.is_noop(), "the override replaces the doctrine for Cloud");
        // A non-overridden role still gets the doctrine.
        let q = map.resolve(SrpRole::Conductor, Privacy::Public, Safety::Safe);
        assert!(
            q.force_pii,
            "a non-overridden role still follows the doctrine"
        );
    }

    #[test]
    fn resolve_directive_matches_resolve() {
        let map = RouteProfileMap::default();
        let d = RouteDirective {
            role: SrpRole::Cloud,
            privacy: Privacy::Private,
            safety: Safety::Safe,
        };
        assert_eq!(
            map.resolve_directive(&d),
            map.resolve(d.role, d.privacy, d.safety)
        );
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
