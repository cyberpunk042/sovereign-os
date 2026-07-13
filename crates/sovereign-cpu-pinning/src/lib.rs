//! `sovereign-cpu-pinning` — turn the `sovereign-cpu-topology` CCD partition into
//! deployable systemd `AllowedCPUs=` drop-ins that pin the Trinity CPU agents to
//! their cores.
//!
//! This is the CPU-affinity counterpart to `sovereign-resource-control` (which emits
//! `CPUWeight` / `MemoryMax` drop-ins): same "how a model becomes real OS behavior"
//! pattern, different systemd knob. Crucially the core ranges are read from
//! `sovereign-cpu-topology::allocations()` — the SINGLE SOURCE OF TRUTH for the
//! partition (E0672-E0674) — rather than hardcoded, so the ranges can never drift
//! from the topology model the way a duplicated table would.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use sovereign_cpu_topology::{CoreAllocation, TopologyError, TrinityRole, allocations, validate_partition};

/// A systemd unit and the resource-control drop-in body that pins it to its cores.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnitDropin {
    /// The systemd unit the drop-in applies to (`sovereign-pulse.service`, …).
    pub unit: String,
    /// The complete drop-in body (`# rationale` + `[Slice]`/`[Service]` +
    /// `AllowedCPUs=`), suitable for the file at [`dropin_path`].
    pub body: String,
}

/// The systemd unit(s) each Trinity role pins. These are the real service units
/// (plus the OS `system.slice` for the host reserve). The drop-ins are emitted for
/// review / placement whether or not a unit is currently running — the same
/// contract as `sovereign-resource-control`.
#[must_use]
pub fn units_for(role: TrinityRole) -> &'static [&'static str] {
    match role {
        TrinityRole::Pulse => &["sovereign-pulse.service"],
        TrinityRole::WeaverAuditor => {
            &["sovereign-weaver-api.service", "sovereign-auditor-api.service"]
        }
        TrinityRole::SystemHost => &["system.slice"],
    }
}

/// The drop-in path a unit's pinning file belongs at.
#[must_use]
pub fn dropin_path(unit: &str) -> String {
    format!("/etc/systemd/system/{unit}.d/50-sovereign-cpu-pinning.conf")
}

/// The `[Section]` a directive lives in for `unit`: `[Slice]` for a `.slice`,
/// `[Service]` otherwise. `AllowedCPUs=` is valid in both.
fn section_for(unit: &str) -> &'static str {
    if unit.ends_with(".slice") {
        "Slice"
    } else {
        "Service"
    }
}

/// Render one allocation's drop-in body for `unit`.
fn dropin_body(unit: &str, a: &CoreAllocation) -> String {
    format!(
        "# Trinity {:?} — CCD {} cores {}-{} → CPUs {} (from sovereign-cpu-topology)\n\
         [{}]\nAllowedCPUs={}\n",
        a.role,
        a.ccd,
        a.cores.0,
        a.cores.1,
        a.cpuset,
        section_for(unit),
        a.cpuset,
    )
}

/// The full set of pinning drop-ins for the canonical Trinity partition — one per
/// (role, unit). Validates the partition first (no overlap, full cover, cpusets
/// consistent with masks), so a malformed topology never emits a bad pinning.
///
/// # Errors
/// Returns the [`TopologyError`] if `sovereign-cpu-topology`'s partition is invalid.
pub fn pinning_dropins() -> Result<Vec<UnitDropin>, TopologyError> {
    let allocs = allocations();
    validate_partition(&allocs)?;
    let mut out = Vec::new();
    for a in &allocs {
        for unit in units_for(a.role) {
            out.push(UnitDropin {
                unit: (*unit).to_string(),
                body: dropin_body(unit, a),
            });
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn emits_a_dropin_per_unit_with_the_topology_cpuset() {
        let d = pinning_dropins().expect("the canonical partition is valid");
        // Pulse (1 unit) + Weaver+Auditor (2 units) + System-Host (1 unit) = 4.
        assert_eq!(d.len(), 4, "one drop-in per (role, unit)");
        // Pulse pins its service to the topology's cpuset, in the [Service] section.
        let pulse = d.iter().find(|x| x.unit == "sovereign-pulse.service").unwrap();
        assert!(pulse.body.contains("AllowedCPUs=0-11"), "body: {}", pulse.body);
        assert!(pulse.body.contains("[Service]"));
        // The OS host reserve is a slice → [Slice].
        let sys = d.iter().find(|x| x.unit == "system.slice").unwrap();
        assert!(sys.body.contains("[Slice]"), "body: {}", sys.body);
        // Every cpuset comes FROM sovereign-cpu-topology, not a local hardcode.
        for a in allocations() {
            assert!(
                d.iter().any(|x| x.body.contains(&format!("AllowedCPUs={}", a.cpuset))),
                "no drop-in carries the topology cpuset {:?}",
                a.cpuset
            );
        }
    }

    #[test]
    fn dropin_path_follows_the_systemd_convention() {
        assert_eq!(
            dropin_path("sovereign-pulse.service"),
            "/etc/systemd/system/sovereign-pulse.service.d/50-sovereign-cpu-pinning.conf"
        );
    }

    #[test]
    fn section_is_slice_for_slices_service_otherwise() {
        assert_eq!(section_for("system.slice"), "Slice");
        assert_eq!(section_for("sovereign-pulse.service"), "Service");
    }
}
