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

/// The environment variable an operator sets to a JSON [`RouteProfileMap`] to
/// override the built-in doctrine per role (SDD-518). Unset/empty ⇒ the doctrine.
/// Mirrors the token-law engine's other env config (`SOVEREIGN_TOKEN_LAW_MASK_LAYERS`).
pub const ROUTE_PROFILES_ENV: &str = "SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES";

/// The environment variable naming a JSON **file** that holds the operator
/// [`RouteProfileMap`] (SDD-521) — the config-file surface, for a multi-role map
/// too unwieldy to inline in [`ROUTE_PROFILES_ENV`]. The file's contents are the
/// same shape [`from_json`](RouteProfileMap::from_json) parses. The inline env
/// JSON takes precedence over the file; an unset/empty/unreadable/invalid file
/// falls back to the doctrine (the same forgiving impure boundary as the env).
pub const ROUTE_PROFILES_FILE_ENV: &str = "SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES_FILE";

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

    /// Parse an operator override map from JSON (SDD-518). A role omitted from the
    /// JSON keeps the doctrine; a role present with a [`RouteProfile`] overrides it.
    /// An empty object `{}` is the all-doctrine map (identical to
    /// [`default`](Self::default)).
    pub fn from_json(json: &str) -> Result<Self, String> {
        serde_json::from_str(json).map_err(|e| e.to_string())
    }

    /// Parse the operator override map from a JSON **file** (SDD-521). Reads
    /// `path` and parses its contents via [`from_json`](Self::from_json). An
    /// unreadable file or invalid JSON is an `Err`; the forgiving fallback to the
    /// doctrine lives in [`from_env_or_default`](Self::from_env_or_default).
    pub fn from_file(path: &str) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))?;
        Self::from_json(&text)
    }

    /// The effective map from the operator's two config surfaces, resolved with a
    /// fixed precedence: the **inline** [`ROUTE_PROFILES_ENV`] JSON wins (the most
    /// explicit, per-run override), then the [`ROUTE_PROFILES_FILE_ENV`] JSON
    /// **file** (SDD-521, the persistent config), then the all-doctrine
    /// [`default`](Self::default). Unset / empty / unreadable / parse-error at any
    /// surface falls through to the next — the impure boundary, like the token-law
    /// engine's `MaskLayerSet::from_env_or_all`. The pure core
    /// ([`resolve`](Self::resolve)) takes an already-resolved map.
    pub fn from_env_or_default() -> Self {
        Self::resolve_env(
            std::env::var(ROUTE_PROFILES_ENV).ok().as_deref(),
            std::env::var(ROUTE_PROFILES_FILE_ENV).ok().as_deref(),
        )
    }

    /// Pure precedence resolution over the two env values (inline JSON, file
    /// path) — split out so the ordering is unit-testable without mutating the
    /// process environment. Inline non-empty JSON wins; else a non-empty file
    /// path is read; else the doctrine. Any parse/read failure falls to the
    /// doctrine (via `unwrap_or_default`), matching SDD-518's forgiving boundary.
    fn resolve_env(inline: Option<&str>, file: Option<&str>) -> Self {
        if let Some(v) = inline {
            if !v.trim().is_empty() {
                return Self::from_json(v).unwrap_or_default();
            }
        }
        if let Some(p) = file {
            let p = p.trim();
            if !p.is_empty() {
                return Self::from_file(p).unwrap_or_default();
            }
        }
        Self::default()
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
    fn from_json_parses_a_per_role_override() {
        // Operator: a Cloud task forces nothing (accepts the risk); other roles
        // omitted → keep the doctrine.
        let map = RouteProfileMap::from_json(
            r#"{"cloud":{"force_pii":false,"force_entropy":false,"force_safety_denylist":false}}"#,
        )
        .expect("valid json");
        assert!(
            map.resolve(SrpRole::Cloud, Privacy::Public, Safety::Risky)
                .is_noop()
        );
        // A non-overridden role still follows the doctrine.
        assert!(
            map.resolve(SrpRole::Conductor, Privacy::Public, Safety::Safe)
                .force_pii
        );
    }

    #[test]
    fn from_json_empty_object_is_the_all_doctrine_map() {
        let map = RouteProfileMap::from_json("{}").expect("valid json");
        assert_eq!(map, RouteProfileMap::default());
        assert!(
            map.resolve(SrpRole::Cloud, Privacy::Private, Safety::Safe)
                .force_pii
        );
    }

    #[test]
    fn from_json_rejects_malformed_input() {
        assert!(RouteProfileMap::from_json("{not json").is_err());
    }

    // ── SDD-521: the config-FILE surface ────────────────────────────────────

    /// A per-test unique temp path (no external deps; the process id keeps
    /// concurrent test binaries from colliding).
    fn temp_json_path(tag: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("sovereign-route-{}-{tag}.json", std::process::id()))
    }

    #[test]
    fn from_file_parses_a_json_file() {
        let path = temp_json_path("parse");
        std::fs::write(
            &path,
            r#"{"cloud":{"force_pii":false,"force_entropy":false,"force_safety_denylist":false}}"#,
        )
        .unwrap();
        let map = RouteProfileMap::from_file(path.to_str().unwrap()).expect("valid file");
        // the file's per-role override applies …
        assert!(
            map.resolve(SrpRole::Cloud, Privacy::Public, Safety::Risky)
                .is_noop()
        );
        // … while an omitted role still follows the doctrine.
        assert!(
            map.resolve(SrpRole::Conductor, Privacy::Public, Safety::Safe)
                .force_pii
        );
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn from_file_errors_on_a_missing_or_malformed_file() {
        // a path that does not exist is an Err (read failure)
        assert!(RouteProfileMap::from_file("/no/such/route-profiles.json").is_err());
        // a file with invalid JSON is an Err (parse failure)
        let path = temp_json_path("malformed");
        std::fs::write(&path, "{not json").unwrap();
        assert!(RouteProfileMap::from_file(path.to_str().unwrap()).is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn resolve_env_precedence_inline_over_file_over_doctrine() {
        let cloud_noop =
            r#"{"cloud":{"force_pii":false,"force_entropy":false,"force_safety_denylist":false}}"#;
        // write a DIFFERENT map to a file (conductor overridden to a no-op) so we
        // can tell which surface won.
        let path = temp_json_path("precedence");
        std::fs::write(
            &path,
            r#"{"conductor":{"force_pii":false,"force_entropy":false,"force_safety_denylist":false}}"#,
        )
        .unwrap();
        let file = path.to_str().unwrap();

        // 1. inline JSON wins over the file: the cloud override applies, and the
        //    file's conductor override does NOT (conductor keeps the doctrine).
        let m = RouteProfileMap::resolve_env(Some(cloud_noop), Some(file));
        assert!(
            m.resolve(SrpRole::Cloud, Privacy::Public, Safety::Risky)
                .is_noop()
        );
        assert!(
            m.resolve(SrpRole::Conductor, Privacy::Public, Safety::Safe)
                .force_pii
        );

        // 2. no inline (None / empty / whitespace) ⇒ the file is used: the
        //    conductor override makes a Public task a no-op, which the doctrine
        //    would have forced PII on — so this only holds if the file applied.
        for inline in [None, Some(""), Some("   ")] {
            let m = RouteProfileMap::resolve_env(inline, Some(file));
            assert!(
                m.resolve(SrpRole::Conductor, Privacy::Public, Safety::Safe)
                    .is_noop(),
                "the file's conductor override must apply when inline is empty/absent"
            );
        }

        // 3. neither surface set ⇒ the doctrine (cloud forces PII on).
        let m = RouteProfileMap::resolve_env(None, None);
        assert_eq!(m, RouteProfileMap::default());
        assert!(
            m.resolve(SrpRole::Cloud, Privacy::Private, Safety::Safe)
                .force_pii
        );

        // 4. an unreadable file path falls through to the doctrine.
        let m = RouteProfileMap::resolve_env(None, Some("/no/such/file.json"));
        assert_eq!(m, RouteProfileMap::default());

        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
