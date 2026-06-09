//! `sovereign-zfs-provisioning-plan` — M068 M01141/M01142: emit the ordered
//! `zpool create` + `zfs create/set` plan for the canonical `tank` layout.
//!
//! This composes [`sovereign_zfs_dataset_layout`]'s canon into the actual shell
//! command sequence the installer runs. The one piece of real logic beyond
//! string-joining is **emitting only what differs from the inherited default**,
//! so the provisioning script stays minimal and an operator reading it sees
//! intent, not noise:
//!
//! - `recordsize` is set only when it differs from ZFS's 128K default
//!   (⇒ only `tank/containers` 16K and `tank/models` 1M get an explicit set),
//! - `compression` is set only when it differs from the pool-inherited `lz4`
//!   (⇒ only `tank/containers` off and `tank/models` zstd-3),
//! - `sync` is set only when it differs from the `standard` default
//!   (⇒ only `tank/context` and `tank/vault` get `sync=always`).
//!
//! The target device is validated against a conservative block-device pattern
//! before it is interpolated, so a malformed device string can't smuggle shell
//! metacharacters into the emitted `zpool create` line. This crate builds the
//! commands; it does not execute them.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::Serialize;
use sovereign_zfs_dataset_layout::{
    RedundantMetadata, Sync, canonical_layout, canonical_pool, format_recordsize,
};

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// ZFS's default `recordsize` (128K). Datasets at this value inherit it and
/// need no explicit `zfs set recordsize`.
pub const ZFS_DEFAULT_RECORDSIZE: u32 = 128 * 1024;

/// ZFS's default `copies` (1). Datasets at this value need no explicit set.
pub const ZFS_DEFAULT_COPIES: u8 = 1;

/// Why a target device string was rejected.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum DeviceError {
    /// The device path is empty.
    #[error("device path is empty")]
    Empty,
    /// The device path is not an absolute `/dev/...` path.
    #[error("device {0:?} is not an absolute /dev path")]
    NotDevPath(String),
    /// The device path contains a character outside the safe block-device set
    /// (`[A-Za-z0-9_/.-]`) — refused to avoid shell-metacharacter injection.
    #[error("device {0:?} contains an unsafe character")]
    UnsafeChar(String),
    /// The device path contains a `..` component — refused so a `/dev/…` prefix
    /// can't be escaped by traversal (e.g. `/dev/../etc/passwd`).
    #[error("device {0:?} contains a '..' path-traversal component")]
    Traversal(String),
}

/// Validate a target block-device path. Accepts absolute `/dev/...` paths made
/// of `[A-Za-z0-9_/.-]` (covers `/dev/nvme0n1`, `/dev/disk/by-id/…`, `/dev/sda`);
/// rejects anything that could carry shell metacharacters OR escape `/dev` via a
/// `..` component (so the `/dev/` prefix is a real guarantee, not just a
/// textual one).
pub fn validate_device(device: &str) -> Result<(), DeviceError> {
    let d = device.trim();
    if d.is_empty() {
        return Err(DeviceError::Empty);
    }
    if !d.starts_with("/dev/") {
        return Err(DeviceError::NotDevPath(device.to_string()));
    }
    if !d
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '/' | '.' | '-'))
    {
        return Err(DeviceError::UnsafeChar(device.to_string()));
    }
    // The char allow-list permits `.`, so `..` would otherwise slip through and
    // let `/dev/../etc/passwd` escape the /dev tree. Reject any `..` component.
    if d.split('/').any(|seg| seg == "..") {
        return Err(DeviceError::Traversal(device.to_string()));
    }
    Ok(())
}

/// One emitted provisioning command, structured for inspection + a flat render.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ProvisioningCommand {
    /// What the command does (e.g. `"create pool"`, `"create dataset tank/context"`).
    pub purpose: String,
    /// The argv, ready to exec (no shell needed).
    pub argv: Vec<String>,
}

impl ProvisioningCommand {
    /// The command as a single shell-style line (argv joined by spaces). Safe
    /// because every token was validated / drawn from the fixed canon.
    #[must_use]
    pub fn command_line(&self) -> String {
        self.argv.join(" ")
    }
}

/// Build the ordered provisioning plan for `device`: the pool creation command
/// followed by, for each canonical dataset, a `zfs create` and (only if it has
/// non-default properties) a single `zfs set` carrying just those properties.
pub fn provisioning_plan(device: &str) -> Result<Vec<ProvisioningCommand>, DeviceError> {
    validate_device(device)?;
    let device = device.trim();
    let pool = canonical_pool();

    let mut plan = Vec::new();

    // zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank <device>
    let mut create_argv = vec![
        "zpool".into(),
        "create".into(),
        "-f".into(),
        "-o".into(),
        format!("ashift={}", pool.ashift),
        "-O".into(),
        format!("compression={}", pool.compression.token()),
    ];
    if pool.atime_off {
        create_argv.push("-O".into());
        create_argv.push("atime=off".into());
    }
    create_argv.push("tank".into());
    create_argv.push(device.to_string());
    plan.push(ProvisioningCommand { purpose: "create pool".into(), argv: create_argv });

    for spec in canonical_layout() {
        let path = spec.dataset.path();
        plan.push(ProvisioningCommand {
            purpose: format!("create dataset {path}"),
            argv: vec!["zfs".into(), "create".into(), path.to_string()],
        });

        // Only the properties that differ from the inherited default.
        let mut props: Vec<String> = Vec::new();
        if spec.recordsize != ZFS_DEFAULT_RECORDSIZE {
            props.push(format!("recordsize={}", format_recordsize(spec.recordsize)));
        }
        if spec.compression != pool.compression {
            props.push(format!("compression={}", spec.compression.token()));
        }
        if spec.sync != Sync::Standard {
            props.push(format!("sync={}", spec.sync.token()));
        }
        if spec.copies != ZFS_DEFAULT_COPIES {
            props.push(format!("copies={}", spec.copies));
        }
        if spec.redundant_metadata != RedundantMetadata::All {
            props.push(format!("redundant_metadata={}", spec.redundant_metadata.token()));
        }
        if !props.is_empty() {
            let mut set_argv = vec!["zfs".into(), "set".into()];
            set_argv.extend(props);
            set_argv.push(path.to_string());
            plan.push(ProvisioningCommand {
                purpose: format!("tune dataset {path}"),
                argv: set_argv,
            });
        }
    }

    Ok(plan)
}

/// The plan rendered as shell-style lines (one per command).
pub fn provisioning_script(device: &str) -> Result<Vec<String>, DeviceError> {
    Ok(provisioning_plan(device)?
        .iter()
        .map(ProvisioningCommand::command_line)
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_unsafe_devices() {
        assert_eq!(validate_device(""), Err(DeviceError::Empty));
        assert!(matches!(validate_device("nvme0n1"), Err(DeviceError::NotDevPath(_))));
        assert!(matches!(
            validate_device("/dev/nvme0n1; rm -rf /"),
            Err(DeviceError::UnsafeChar(_))
        ));
        assert!(matches!(
            validate_device("/dev/$(whoami)"),
            Err(DeviceError::UnsafeChar(_))
        ));
        // Path traversal: only safe chars, /dev/ prefix — must still be refused.
        assert!(matches!(
            validate_device("/dev/../etc/passwd"),
            Err(DeviceError::Traversal(_))
        ));
        assert!(matches!(
            validate_device("/dev/disk/../../root"),
            Err(DeviceError::Traversal(_))
        ));
        validate_device("/dev/nvme0n1").unwrap();
        validate_device("/dev/disk/by-id/nvme-Samsung_990").unwrap();
        // A literal `..` inside a name segment (not its own component) is fine.
        validate_device("/dev/my..disk").unwrap();
    }

    #[test]
    fn pool_command_carries_the_canonical_options() {
        let plan = provisioning_plan("/dev/nvme0n1").unwrap();
        let pool = &plan[0];
        assert_eq!(pool.purpose, "create pool");
        let line = pool.command_line();
        assert!(line.starts_with("zpool create -f -o ashift=12 -O compression=lz4 -O atime=off tank /dev/nvme0n1"), "{line}");
    }

    #[test]
    fn only_non_default_properties_are_set() {
        let script = provisioning_script("/dev/nvme0n1").unwrap();
        let joined = script.join("\n");

        // models: 1M (!=128k) + redundant_metadata=most; compression lz4 is the
        // inherited pool default, so it is NOT re-set.
        assert!(
            joined.contains("zfs set recordsize=1M redundant_metadata=most tank/models"),
            "{joined}"
        );
        // context: recordsize=16k + compression=zstd-9 + sync=always + copies=2.
        assert!(
            joined.contains("zfs set recordsize=16K compression=zstd-9 sync=always copies=2 tank/context"),
            "{joined}"
        );
        // agents: only compression=zstd-3 (recordsize 128k = default, copies 1,
        // redundant_metadata all, sync standard — all inherited).
        assert!(joined.contains("zfs set compression=zstd-3 tank/agents"), "{joined}");
        // agents must NOT carry a recordsize set (it's the 128k default).
        let agents_set: Vec<&String> =
            script.iter().filter(|l| l.starts_with("zfs set") && l.ends_with("tank/agents")).collect();
        assert_eq!(agents_set.len(), 1, "agents has exactly one set line: {agents_set:?}");
        assert!(!agents_set[0].contains("recordsize"), "agents 128k is default: {agents_set:?}");
    }

    #[test]
    fn every_dataset_gets_a_create_line_in_order() {
        let script = provisioning_script("/dev/nvme0n1").unwrap();
        for path in ["tank/models", "tank/context", "tank/agents"] {
            assert!(
                script.iter().any(|l| l == &format!("zfs create {path}")),
                "missing create for {path}"
            );
        }
        // Pool create comes first.
        assert!(script[0].starts_with("zpool create"));
    }

    #[test]
    fn context_set_serializes() {
        let plan = provisioning_plan("/dev/nvme0n1").unwrap();
        // Round-trips through serde (structured form is inspectable).
        let json = serde_json::to_string(&plan).unwrap();
        assert!(json.contains("create pool"));
        assert!(json.contains("tune dataset tank/context"));
    }
}
