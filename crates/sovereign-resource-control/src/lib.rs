//! `sovereign-resource-control` — E0429 / M00756: systemd resource-control
//! profiles for the five operator-named service boundaries.
//!
//! "cgroup v2 controls CPU + memory + IO + PIDs + delegation; systemd exposes
//! CPUWeight + MemoryMax + IOWeight + task limits + slices + scopes … agent
//! workloads can be given real boundaries. This is how 'profiles' become real
//! OS behavior."
//!
//! This crate models the five example boundaries from E0429 and emits the
//! corresponding systemd resource-control drop-in directives — the bridge from
//! a declared profile to actual kernel-enforced cgroup limits:
//!
//! 1. `oracle.service`  — high GPU priority, memory protected, no random shell
//! 2. `scout.slice`     — medium CPU/GPU, can be killed-restarted freely
//! 3. `sandbox.slice`   — strict memory / IO / network / time limits
//! 4. `eval.slice`      — low priority background
//! 5. `gateway.service` — protected, always-on, small trusted surface

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// systemd unit kind a profile applies to. Resource-control directives live in
/// the `[Slice]` section for slices and `[Service]` for services.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum UnitKind {
    /// A `.service` unit.
    Service,
    /// A `.slice` unit (a cgroup grouping of units).
    Slice,
}

impl UnitKind {
    /// The systemd ini section resource-control directives go under.
    #[must_use]
    pub fn section(self) -> &'static str {
        match self {
            UnitKind::Service => "Service",
            UnitKind::Slice => "Slice",
        }
    }
}

/// A resource-control profile: the systemd knobs that turn a named boundary
/// into kernel-enforced cgroup v2 limits.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ResourceProfile {
    /// Unit name, e.g. `"oracle.service"`.
    pub unit: String,
    /// Service or slice.
    pub kind: UnitKind,
    /// `CPUWeight` — relative CPU share, 1..=10000 (100 = default).
    pub cpu_weight: u16,
    /// `IOWeight` — relative block-IO share, 1..=10000 (100 = default).
    pub io_weight: u16,
    /// `MemoryMax` cap in MiB; `None` = `infinity` (no hard cap).
    pub memory_max_mb: Option<u32>,
    /// `MemoryLow` soft guarantee in MiB (protection); `None` = unset.
    pub memory_low_mb: Option<u32>,
    /// `TasksMax` PID limit; `None` = unset.
    pub tasks_max: Option<u32>,
    /// `RuntimeMaxSec` wall-clock cap in seconds; `None` = unbounded.
    pub runtime_max_secs: Option<u32>,
    /// Operator intent: this boundary is always-on (not freely killable).
    pub always_on: bool,
    /// Operator intent: this boundary may be killed and restarted freely.
    pub kill_restartable: bool,
    /// One-line rationale, traceable to E0429.
    pub rationale: String,
}

/// Errors validating a profile.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ResourceError {
    /// A weight fell outside systemd's 1..=10000 range.
    WeightOutOfRange {
        /// `"CPUWeight"` or `"IOWeight"`.
        field: &'static str,
        /// The offending value.
        value: u16,
    },
    /// `always_on` and `kill_restartable` were both set — contradictory.
    KillPolicyContradiction,
    /// `MemoryLow` exceeds `MemoryMax` (a guarantee above the cap).
    MemoryLowAboveMax {
        /// low MiB.
        low: u32,
        /// max MiB.
        max: u32,
    },
    /// The config JSON could not be parsed into a list of profiles.
    Parse(String),
    /// Two profiles in the set claim the same `unit` name.
    DuplicateUnit(String),
}

impl std::fmt::Display for ResourceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ResourceError::WeightOutOfRange { field, value } => {
                write!(f, "{field}={value} outside systemd range 1..=10000")
            }
            ResourceError::KillPolicyContradiction => {
                write!(f, "always_on and kill_restartable are mutually exclusive")
            }
            ResourceError::MemoryLowAboveMax { low, max } => {
                write!(f, "MemoryLow={low}M exceeds MemoryMax={max}M")
            }
            ResourceError::Parse(e) => write!(f, "config parse: {e}"),
            ResourceError::DuplicateUnit(u) => write!(f, "duplicate unit {u:?} in profile set"),
        }
    }
}

impl std::error::Error for ResourceError {}

impl ResourceProfile {
    /// Validate the systemd-enforced invariants.
    pub fn validate(&self) -> Result<(), ResourceError> {
        if !(1..=10000).contains(&self.cpu_weight) {
            return Err(ResourceError::WeightOutOfRange {
                field: "CPUWeight",
                value: self.cpu_weight,
            });
        }
        if !(1..=10000).contains(&self.io_weight) {
            return Err(ResourceError::WeightOutOfRange {
                field: "IOWeight",
                value: self.io_weight,
            });
        }
        if self.always_on && self.kill_restartable {
            return Err(ResourceError::KillPolicyContradiction);
        }
        if let (Some(low), Some(max)) = (self.memory_low_mb, self.memory_max_mb)
            && low > max
        {
            return Err(ResourceError::MemoryLowAboveMax { low, max });
        }
        Ok(())
    }

    /// Render the systemd resource-control drop-in for this profile.
    ///
    /// The output is a complete drop-in body (`# rationale` + the
    /// `[Slice]`/`[Service]` section + the set directives) suitable for
    /// `/etc/systemd/system/<unit>.d/50-sovereign-resource.conf`.
    #[must_use]
    pub fn to_systemd_dropin(&self) -> String {
        let mut s = format!("# {}\n[{}]\n", self.rationale, self.kind.section());
        s.push_str(&format!("CPUWeight={}\n", self.cpu_weight));
        s.push_str(&format!("IOWeight={}\n", self.io_weight));
        match self.memory_max_mb {
            Some(m) => s.push_str(&format!("MemoryMax={m}M\n")),
            None => s.push_str("MemoryMax=infinity\n"),
        }
        if let Some(low) = self.memory_low_mb {
            s.push_str(&format!("MemoryLow={low}M\n"));
        }
        if let Some(t) = self.tasks_max {
            s.push_str(&format!("TasksMax={t}\n"));
        }
        if let Some(r) = self.runtime_max_secs {
            s.push_str(&format!("RuntimeMaxSec={r}\n"));
        }
        s
    }
}

/// The five canonical E0429 service boundaries, in order.
///
/// Weights follow the operator's high/medium/low intent (high≈1000,
/// medium≈100, low≈10 on systemd's 1..=10000 `CPUWeight` scale; 100 is the
/// unit default). The memory/task/time caps are conservative starting points
/// an operator tunes per host — the *shape* of each boundary is what E0429
/// fixes.
#[must_use]
pub fn canonical_profiles() -> Vec<ResourceProfile> {
    vec![
        // 1. oracle.service — high GPU priority, memory protected, no shell.
        ResourceProfile {
            unit: "oracle.service".into(),
            kind: UnitKind::Service,
            cpu_weight: 1000,
            io_weight: 500,
            memory_max_mb: None, // generous — the oracle is protected, not capped
            memory_low_mb: Some(8192), // protected: 8 GiB soft guarantee
            tasks_max: Some(64), // bounded: no random shell fan-out
            runtime_max_secs: None, // always available
            always_on: true,
            kill_restartable: false,
            rationale:
                "E0429 oracle.service: high GPU priority, memory protected, no random shell access"
                    .into(),
        },
        // 2. scout.slice — medium CPU/GPU, freely killable.
        ResourceProfile {
            unit: "scout.slice".into(),
            kind: UnitKind::Slice,
            cpu_weight: 100,
            io_weight: 100,
            memory_max_mb: Some(16384),
            memory_low_mb: None,
            tasks_max: Some(256),
            runtime_max_secs: None,
            always_on: false,
            kill_restartable: true,
            rationale: "E0429 scout.slice: medium CPU-GPU, can be killed-restarted freely".into(),
        },
        // 3. sandbox.slice — strict memory / IO / time limits.
        ResourceProfile {
            unit: "sandbox.slice".into(),
            kind: UnitKind::Slice,
            cpu_weight: 50,
            io_weight: 20,
            memory_max_mb: Some(2048), // strict
            memory_low_mb: None,
            tasks_max: Some(64),
            runtime_max_secs: Some(900), // 15-minute wall-clock cap
            always_on: false,
            kill_restartable: true,
            rationale: "E0429 sandbox.slice: strict memory / IO / network / time limits".into(),
        },
        // 4. eval.slice — low priority background.
        ResourceProfile {
            unit: "eval.slice".into(),
            kind: UnitKind::Slice,
            cpu_weight: 10,
            io_weight: 10,
            memory_max_mb: Some(8192),
            memory_low_mb: None,
            tasks_max: Some(128),
            runtime_max_secs: None,
            always_on: false,
            kill_restartable: true,
            rationale: "E0429 eval.slice: low priority background".into(),
        },
        // 5. gateway.service — protected, always-on, small trusted surface.
        ResourceProfile {
            unit: "gateway.service".into(),
            kind: UnitKind::Service,
            cpu_weight: 200,
            io_weight: 200,
            memory_max_mb: Some(1024), // small trusted surface
            memory_low_mb: Some(256),  // protected baseline
            tasks_max: Some(32),       // small
            runtime_max_secs: None,
            always_on: true,
            kill_restartable: false,
            rationale: "E0429 gateway.service: protected always-on, small trusted surface".into(),
        },
    ]
}

/// Validate a profile set — each profile valid AND unit names unique (two
/// profiles for the same unit would write conflicting drop-ins to the same
/// `/etc/systemd/system/<unit>.d/` file).
pub fn validate_profiles(profiles: &[ResourceProfile]) -> Result<(), ResourceError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for p in profiles {
        p.validate()?;
        if !seen.insert(p.unit.as_str()) {
            return Err(ResourceError::DuplicateUnit(p.unit.clone()));
        }
    }
    Ok(())
}

/// Load operator-defined profiles from a JSON array, validating the set.
///
/// Lets an operator override or extend the [`canonical_profiles`] with their
/// own boundaries (a JSON array of [`ResourceProfile`] objects). Each profile
/// is validated and the set is checked for unique unit names, so a malformed
/// or conflicting config is rejected before any drop-in is emitted.
pub fn from_json(content: &str) -> Result<Vec<ResourceProfile>, ResourceError> {
    let profiles: Vec<ResourceProfile> =
        serde_json::from_str(content).map_err(|e| ResourceError::Parse(e.to_string()))?;
    validate_profiles(&profiles)?;
    Ok(profiles)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_canonical_boundaries_in_order() {
        let p = canonical_profiles();
        let units: Vec<_> = p.iter().map(|x| x.unit.as_str()).collect();
        assert_eq!(
            units,
            [
                "oracle.service",
                "scout.slice",
                "sandbox.slice",
                "eval.slice",
                "gateway.service",
            ]
        );
    }

    #[test]
    fn all_canonical_profiles_validate() {
        validate_profiles(&canonical_profiles()).expect("canonical set valid");
    }

    #[test]
    fn priority_ordering_matches_operator_intent() {
        let p = canonical_profiles();
        let w = |u: &str| p.iter().find(|x| x.unit == u).unwrap().cpu_weight;
        // oracle (high) > gateway > scout (medium) > sandbox > eval (low).
        assert!(w("oracle.service") > w("scout.slice"));
        assert!(w("scout.slice") > w("eval.slice"));
        assert_eq!(w("eval.slice"), 10, "low priority background");
    }

    #[test]
    fn kill_policy_is_consistent() {
        let p = canonical_profiles();
        // always-on units are never freely killable, and vice versa.
        for prof in &p {
            assert!(!(prof.always_on && prof.kill_restartable), "{}", prof.unit);
        }
        let scout = p.iter().find(|x| x.unit == "scout.slice").unwrap();
        assert!(scout.kill_restartable && !scout.always_on);
        let gw = p.iter().find(|x| x.unit == "gateway.service").unwrap();
        assert!(gw.always_on && !gw.kill_restartable);
    }

    #[test]
    fn sandbox_is_strictest() {
        let p = canonical_profiles();
        let sandbox = p.iter().find(|x| x.unit == "sandbox.slice").unwrap();
        assert_eq!(sandbox.memory_max_mb, Some(2048));
        assert!(
            sandbox.runtime_max_secs.is_some(),
            "sandbox has a time limit"
        );
    }

    #[test]
    fn systemd_dropin_renders_directives() {
        let p = canonical_profiles();
        let oracle = p.iter().find(|x| x.unit == "oracle.service").unwrap();
        let d = oracle.to_systemd_dropin();
        assert!(d.contains("[Service]"));
        assert!(d.contains("CPUWeight=1000"));
        assert!(d.contains("IOWeight=500"));
        assert!(d.contains("MemoryMax=infinity")); // protected, not capped
        assert!(d.contains("MemoryLow=8192M")); // protection
        assert!(d.contains("TasksMax=64"));
        assert!(d.starts_with("# E0429 oracle.service"));

        let sandbox = p.iter().find(|x| x.unit == "sandbox.slice").unwrap();
        let ds = sandbox.to_systemd_dropin();
        assert!(ds.contains("[Slice]"));
        assert!(ds.contains("MemoryMax=2048M"));
        assert!(ds.contains("RuntimeMaxSec=900"));
    }

    #[test]
    fn validate_rejects_bad_weight_and_contradictions() {
        let mut bad = canonical_profiles()[0].clone();
        bad.cpu_weight = 0;
        assert!(matches!(
            bad.validate(),
            Err(ResourceError::WeightOutOfRange {
                field: "CPUWeight",
                value: 0
            })
        ));
        let mut contradiction = canonical_profiles()[1].clone();
        contradiction.always_on = true; // scout is kill_restartable
        assert!(matches!(
            contradiction.validate(),
            Err(ResourceError::KillPolicyContradiction)
        ));
        let mut membad = canonical_profiles()[2].clone();
        membad.memory_low_mb = Some(9999); // above the 2048 max
        assert!(matches!(
            membad.validate(),
            Err(ResourceError::MemoryLowAboveMax {
                low: 9999,
                max: 2048
            })
        ));
    }

    #[test]
    fn profile_serializes_kebab() {
        let p = &canonical_profiles()[1];
        let j = serde_json::to_value(p).unwrap();
        assert_eq!(j["kind"], "slice");
        assert_eq!(j["unit"], "scout.slice");
    }

    // ---- operator JSON config ----

    #[test]
    fn from_json_roundtrips_canonical() {
        let json = serde_json::to_string(&canonical_profiles()).unwrap();
        assert_eq!(from_json(&json).unwrap(), canonical_profiles());
    }

    #[test]
    fn from_json_rejects_malformed() {
        assert!(matches!(
            from_json("not json"),
            Err(ResourceError::Parse(_))
        ));
    }

    #[test]
    fn from_json_rejects_duplicate_unit() {
        let mut p = canonical_profiles();
        p[1].unit = "oracle.service".into(); // collides with p[0]
        let json = serde_json::to_string(&p).unwrap();
        assert!(matches!(
            from_json(&json),
            Err(ResourceError::DuplicateUnit(u)) if u == "oracle.service"
        ));
    }

    #[test]
    fn from_json_enforces_per_profile_rules() {
        let mut p = vec![canonical_profiles()[0].clone()];
        p[0].cpu_weight = 0; // invalid
        let json = serde_json::to_string(&p).unwrap();
        assert!(matches!(
            from_json(&json),
            Err(ResourceError::WeightOutOfRange {
                field: "CPUWeight",
                value: 0
            })
        ));
    }

    #[test]
    fn validate_profiles_rejects_duplicate_unit() {
        let mut p = canonical_profiles();
        p[2].unit = p[0].unit.clone();
        assert!(matches!(
            validate_profiles(&p),
            Err(ResourceError::DuplicateUnit(_))
        ));
    }
}
