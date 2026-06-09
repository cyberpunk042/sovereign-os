//! `sovereign-cpu-topology` — M070: dual-CCD cache topology + core pinning.
//!
//! The operator's CPU is two CCDs, each with an isolated 32 MB L3; crossing the
//! Infinity Fabric between them costs a cache-miss + cross-die latency penalty
//! (E0668). The SRP-Trinity therefore pins its roles along CCD boundaries so a
//! role never straddles the fabric. This crate fixes that topology and the
//! three core allocations, validates they partition the 24 threads exactly, and
//! emits the cgroup-v2 cpuset for CCD-aware scheduling (taskset / cpuset
//! enforcement, E0675).
//!
//! - CCD 0 — cores 0–5,  threads 0–11,  local 32 MB L3 → **Pulse** (mask `0xfff`)
//! - CCD 1 — cores 6–11, threads 12–23, 32 MB L3 → **Weaver+Auditor** (cores 6–9,
//!   threads 12–19, mask `0xff000`) + **System/Host** (cores 10–11, threads
//!   20–23, mask `0xf00000`)

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// One Core-Complex Die.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct CcdInfo {
    /// CCD index (0 or 1).
    pub ccd: u8,
    /// Inclusive physical core range.
    pub cores: (u8, u8),
    /// Inclusive SMT thread range.
    pub threads: (u8, u8),
    /// Isolated L3 cache size in MiB.
    pub l3_mb: u16,
}

/// The two CCDs (E0669 / E0670).
#[must_use]
pub fn ccds() -> [CcdInfo; 2] {
    [
        CcdInfo {
            ccd: 0,
            cores: (0, 5),
            threads: (0, 11),
            l3_mb: 32,
        },
        CcdInfo {
            ccd: 1,
            cores: (6, 11),
            threads: (12, 23),
            l3_mb: 32,
        },
    ]
}

/// An SRP-Trinity role pinned to a contiguous core block.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TrinityRole {
    /// Pulse — the deterministic CPU cortex (CCD 0).
    Pulse,
    /// Weaver + Auditor (CCD 1, cores 6–9).
    WeaverAuditor,
    /// System / OS base (CCD 1, cores 10–11).
    SystemHost,
}

/// A core allocation: a role, its core block, SMT thread mask, and the cgroup
/// cpuset string that pins it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoreAllocation {
    /// Which role.
    pub role: TrinityRole,
    /// The CCD this allocation lives on.
    pub ccd: u8,
    /// Inclusive physical core range.
    pub cores: (u8, u8),
    /// SMT thread affinity mask (1 bit per logical thread).
    pub thread_mask: u32,
    /// cgroup-v2 `cpuset.cpus` value (the threads, e.g. `"0-11"`).
    pub cpuset: String,
}

/// The three Trinity core allocations (E0672 / E0673 / E0674).
#[must_use]
pub fn allocations() -> [CoreAllocation; 3] {
    [
        CoreAllocation {
            role: TrinityRole::Pulse,
            ccd: 0,
            cores: (0, 5),
            thread_mask: 0x0000_0fff, // threads 0–11
            cpuset: "0-11".into(),
        },
        CoreAllocation {
            role: TrinityRole::WeaverAuditor,
            ccd: 1,
            cores: (6, 9),
            thread_mask: 0x000f_f000, // threads 12–19
            cpuset: "12-19".into(),
        },
        CoreAllocation {
            role: TrinityRole::SystemHost,
            ccd: 1,
            cores: (10, 11),
            thread_mask: 0x00f0_0000, // threads 20–23
            cpuset: "20-23".into(),
        },
    ]
}

/// Errors validating the partition.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TopologyError {
    /// Two allocations claim overlapping threads.
    Overlap(TrinityRole, TrinityRole),
    /// The allocations don't cover exactly the 24 threads.
    IncompleteCover {
        /// The OR of all masks (should be `0x00ff_ffff`).
        covered: u32,
    },
    /// An allocation's cpuset string disagrees with its thread mask.
    CpusetMismatch(TrinityRole),
}

impl std::fmt::Display for TopologyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TopologyError::Overlap(a, b) => write!(f, "{a:?} and {b:?} overlap"),
            TopologyError::IncompleteCover { covered } => {
                write!(f, "allocations cover {covered:#08x}, not the 24 threads 0x00ffffff")
            }
            TopologyError::CpusetMismatch(r) => write!(f, "{r:?} cpuset disagrees with its mask"),
        }
    }
}

impl std::error::Error for TopologyError {}

/// Convert a `cpuset.cpus` range string (`"a-b"` or `"n"`) to a thread mask.
fn cpuset_to_mask(cpuset: &str) -> u32 {
    let mut mask = 0u32;
    for part in cpuset.split(',') {
        let part = part.trim();
        if let Some((a, b)) = part.split_once('-') {
            if let (Ok(a), Ok(b)) = (a.parse::<u32>(), b.parse::<u32>()) {
                for bit in a..=b {
                    mask |= 1 << bit;
                }
            }
        } else if let Ok(n) = part.parse::<u32>() {
            mask |= 1 << n;
        }
    }
    mask
}

/// Validate the three allocations partition the 24 threads exactly: pairwise
/// disjoint, union == `0x00ff_ffff`, and each cpuset string matches its mask.
pub fn validate_partition(allocs: &[CoreAllocation]) -> Result<(), TopologyError> {
    let mut union = 0u32;
    for a in allocs {
        if cpuset_to_mask(&a.cpuset) != a.thread_mask {
            return Err(TopologyError::CpusetMismatch(a.role));
        }
        for b in allocs {
            if a.role != b.role && (a.thread_mask & b.thread_mask) != 0 {
                return Err(TopologyError::Overlap(a.role, b.role));
            }
        }
        union |= a.thread_mask;
    }
    if union != 0x00ff_ffff {
        return Err(TopologyError::IncompleteCover { covered: union });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_ccds_each_32mb_l3() {
        let c = ccds();
        assert_eq!(c[0].cores, (0, 5));
        assert_eq!(c[0].threads, (0, 11));
        assert_eq!(c[1].cores, (6, 11));
        assert_eq!(c[1].threads, (12, 23));
        assert!(c.iter().all(|x| x.l3_mb == 32));
    }

    #[test]
    fn thread_masks_match_catalogue() {
        let a = allocations();
        assert_eq!(a[0].thread_mask, 0xfff); // Pulse, threads 0–11
        assert_eq!(a[1].thread_mask, 0xff000); // Weaver+Auditor, threads 12–19
        assert_eq!(a[2].thread_mask, 0xf00000); // System/Host, threads 20–23
    }

    #[test]
    fn allocations_partition_the_24_threads_exactly() {
        validate_partition(&allocations()).unwrap();
        // union is exactly 24 threads.
        let union = allocations().iter().fold(0u32, |m, a| m | a.thread_mask);
        assert_eq!(union, 0x00ff_ffff);
        assert_eq!(union.count_ones(), 24);
    }

    #[test]
    fn overlap_is_rejected() {
        let mut a = allocations().to_vec();
        a[1].thread_mask |= 1 << 0; // now collides with Pulse's thread 0
        a[1].cpuset = "0,12-19".into(); // keep cpuset consistent with the mask
        assert!(matches!(
            validate_partition(&a),
            Err(TopologyError::Overlap(..))
        ));
    }

    #[test]
    fn incomplete_cover_is_rejected() {
        let mut a = allocations().to_vec();
        a.pop(); // drop System/Host → threads 20–23 uncovered
        assert!(matches!(
            validate_partition(&a),
            Err(TopologyError::IncompleteCover { .. })
        ));
    }

    #[test]
    fn cpuset_mismatch_is_rejected() {
        let mut a = allocations().to_vec();
        a[0].cpuset = "0-5".into(); // says 6 threads but mask is 12 (0xfff)
        assert_eq!(
            validate_partition(&a),
            Err(TopologyError::CpusetMismatch(TrinityRole::Pulse))
        );
    }

    #[test]
    fn role_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&TrinityRole::WeaverAuditor).unwrap(),
            "\"weaver-auditor\""
        );
    }
}
