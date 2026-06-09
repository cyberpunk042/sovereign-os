//! `sovereign-sandbox-profile` — E0461 / M00804: the sandbox-fabric profiles.
//!
//! Agent containers run under systemd (Podman Quadlet) with GPU access through
//! CDI when allowed, rootless where possible, and cgroup-v2 limits. The fabric
//! offers eight named profiles, each constraining one dimension of what a
//! sandbox may do. This crate fixes those eight and the dimension each governs.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The dimension a sandbox profile primarily constrains.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SandboxDimension {
    /// Filesystem access.
    Filesystem,
    /// Network access.
    Network,
    /// GPU access.
    Gpu,
    /// Isolation strength (VM / VFIO).
    Isolation,
}

/// The 8 container/sandbox-fabric profiles (E0461).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SandboxProfile {
    /// Read-only repo mount.
    ReadOnlyRepo,
    /// Writable workspace.
    WriteWorkspace,
    /// No network.
    NetworkDenied,
    /// Network limited to documentation.
    NetworkDocsOnly,
    /// 3090 scout GPU access.
    GpuScout,
    /// No GPU.
    NoGpu,
    /// VM-isolated.
    VmIsolated,
    /// VFIO-passthrough of the 3090.
    Vfio3090,
}

impl SandboxProfile {
    /// All 8 profiles.
    pub const ALL: [SandboxProfile; 8] = [
        SandboxProfile::ReadOnlyRepo,
        SandboxProfile::WriteWorkspace,
        SandboxProfile::NetworkDenied,
        SandboxProfile::NetworkDocsOnly,
        SandboxProfile::GpuScout,
        SandboxProfile::NoGpu,
        SandboxProfile::VmIsolated,
        SandboxProfile::Vfio3090,
    ];

    /// The dimension this profile constrains.
    #[must_use]
    pub fn dimension(self) -> SandboxDimension {
        match self {
            SandboxProfile::ReadOnlyRepo | SandboxProfile::WriteWorkspace => {
                SandboxDimension::Filesystem
            }
            SandboxProfile::NetworkDenied | SandboxProfile::NetworkDocsOnly => {
                SandboxDimension::Network
            }
            SandboxProfile::GpuScout | SandboxProfile::NoGpu => SandboxDimension::Gpu,
            SandboxProfile::VmIsolated | SandboxProfile::Vfio3090 => SandboxDimension::Isolation,
        }
    }

    /// Whether this profile grants the sandbox any GPU. Only the two GPU
    /// profiles that explicitly expose a device do (`gpu-scout`, `vfio-3090`).
    #[must_use]
    pub fn grants_gpu(self) -> bool {
        matches!(self, SandboxProfile::GpuScout | SandboxProfile::Vfio3090)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eight_profiles_two_per_dimension() {
        assert_eq!(SandboxProfile::ALL.len(), 8);
        for dim in [
            SandboxDimension::Filesystem,
            SandboxDimension::Network,
            SandboxDimension::Gpu,
            SandboxDimension::Isolation,
        ] {
            let n = SandboxProfile::ALL.iter().filter(|p| p.dimension() == dim).count();
            assert_eq!(n, 2, "{dim:?}");
        }
    }

    #[test]
    fn only_explicit_gpu_profiles_grant_gpu() {
        assert!(SandboxProfile::GpuScout.grants_gpu());
        assert!(SandboxProfile::Vfio3090.grants_gpu());
        for p in SandboxProfile::ALL
            .into_iter()
            .filter(|p| !matches!(p, SandboxProfile::GpuScout | SandboxProfile::Vfio3090))
        {
            assert!(!p.grants_gpu(), "{p:?}");
        }
    }

    #[test]
    fn filesystem_and_isolation_profiles_classed_right() {
        assert_eq!(SandboxProfile::ReadOnlyRepo.dimension(), SandboxDimension::Filesystem);
        assert_eq!(SandboxProfile::Vfio3090.dimension(), SandboxDimension::Isolation);
        assert_eq!(SandboxProfile::NetworkDocsOnly.dimension(), SandboxDimension::Network);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(serde_json::to_string(&SandboxProfile::Vfio3090).unwrap(), "\"vfio3090\"");
        assert_eq!(serde_json::to_string(&SandboxProfile::ReadOnlyRepo).unwrap(), "\"read-only-repo\"");
        assert_eq!(serde_json::to_string(&SandboxDimension::Gpu).unwrap(), "\"gpu\"");
    }
}
