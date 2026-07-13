//! `sovereign-zfs-provisioning-plan` CLI — the runnable end of M068 M01141/M01142.
//!
//! The library composes the canonical `tank` layout
//! ([`sovereign_zfs_dataset_layout`]) into the ordered `zpool create` +
//! `zfs create` / `zfs set` command sequence the installer runs, emitting only
//! the properties that differ from the inherited ZFS/pool defaults so the plan
//! stays minimal and an operator reading it sees intent, not noise. Nothing
//! *ran* it, so "what commands would provisioning issue, and is a saved plan
//! still safe to apply?" was unanswerable at the command line. This binary is
//! that runnable end — and, exactly like `sovereign-resource-control` emits
//! drop-ins for review, it **emits** the provisioning commands for inspection;
//! it does **not** execute them. No `zpool`/`zfs` is invoked and no disk is
//! touched.
//!
//! Modes:
//!   * default (no args) — emit the provisioning plan for the placeholder target
//!     device as a clearly-marked REVIEW-ONLY script.
//!   * `--device DEV` — emit the plan for target block device `DEV` (validated
//!     against the block-device safety contract before it is interpolated).
//!   * `--check FILE` — load a previously-emitted plan (a JSON array of
//!     `{purpose, argv}`), verify every command is a known ZFS verb carrying only
//!     shell-safe tokens, that it begins with `zpool create`, and re-validate the
//!     target device; report OK or the failure and exit non-zero on any problem.
//!   * `--help` — usage.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::Deserialize;
use sovereign_zfs_provisioning_plan::{DeviceError, provisioning_plan, validate_device};

/// The placeholder target device used when `--device` is not supplied. The
/// emitted script is REVIEW-ONLY, so this stands in for "your real disk"; the
/// `profiles/sain-01.yaml` storage tier is a 2×NVMe raid0, so there is no single
/// canonical path — the operator substitutes their own (e.g. a stable
/// `/dev/disk/by-id/...`).
const DEFAULT_DEVICE: &str = "/dev/nvme0n1";

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-zfs-provisioning-plan — emit / check the canonical tank ZFS provisioning plan\n\n\
     Composes the canonical tank layout into the ordered `zpool create` + `zfs\n\
     create`/`zfs set` command sequence, setting only the properties that differ\n\
     from the inherited ZFS/pool defaults. This binary EMITS those commands for an\n\
     operator to review; it NEVER executes them and touches no disk.\n\n\
     USAGE:\n\
     \x20   sovereign-zfs-provisioning-plan                 emit the plan for the default device (REVIEW ONLY)\n\
     \x20   sovereign-zfs-provisioning-plan --device DEV    emit the plan for target block device DEV\n\
     \x20   sovereign-zfs-provisioning-plan --check FILE    validate a plan JSON (array of {purpose, argv})\n\
     \x20   sovereign-zfs-provisioning-plan --help          print this help and exit\n\n\
     --check FILE loads a previously-emitted plan, verifies every command is a\n\
     known zpool/zfs verb carrying only shell-safe tokens, that the plan begins\n\
     with `zpool create`, and re-validates the target device through the\n\
     block-device safety contract; it prints OK or the failure and exits non-zero\n\
     on any problem. Nothing is executed.\n"
        .to_string()
}

/// Render the provisioning plan for `device` as a REVIEW-ONLY script: a banner
/// that states it is not executed, followed by each command preceded by a
/// comment naming its purpose.
fn emit_plan(device: &str) -> Result<String, DeviceError> {
    let plan = provisioning_plan(device)?;
    let mut out = String::new();
    out.push_str("# --- sovereign-os ZFS provisioning plan (REVIEW ONLY) ---\n");
    out.push_str("# This tool EMITS the zpool/zfs command sequence for an operator to review.\n");
    out.push_str("# It does NOT execute anything; nothing here touches a disk.\n");
    out.push_str(&format!("# target device : {device}\n"));
    out.push_str("# override with  : --device /dev/disk/by-id/nvme-...\n");
    out.push_str("#\n");
    for cmd in plan {
        out.push_str(&format!("# {}\n", cmd.purpose));
        out.push_str(&cmd.command_line());
        out.push('\n');
    }
    Ok(out)
}

/// One command loaded from a plan JSON file. Mirrors the serialized shape of the
/// library's `ProvisioningCommand` (`{purpose, argv}`) so an emitted plan
/// round-trips straight back into `--check` without the library needing to grow
/// a `Deserialize` impl.
#[derive(Debug, Deserialize)]
struct PlanCommand {
    /// Human-readable description of what the command does.
    #[allow(dead_code)]
    purpose: String,
    /// The argv, ready to exec (no shell needed).
    argv: Vec<String>,
}

/// The successful result of checking a plan.
#[derive(Debug, PartialEq, Eq)]
struct CheckReport {
    /// How many commands the plan contains.
    commands: usize,
    /// The target block device named in the `zpool create` command.
    device: String,
}

/// Why a plan JSON failed validation.
#[derive(Debug, thiserror::Error)]
enum CheckError {
    /// The file did not parse as a plan (JSON array of `{purpose, argv}`).
    #[error("not a provisioning plan (expected a JSON array of {{purpose, argv}}): {0}")]
    Parse(String),
    /// The plan contains no commands.
    #[error("plan is empty — no commands to provision")]
    Empty,
    /// A command has an empty argv.
    #[error("command #{index} has an empty argv")]
    EmptyArgv {
        /// Zero-based index of the offending command.
        index: usize,
    },
    /// A command's verb is not `zpool` or `zfs`.
    #[error("command #{index} verb {verb:?} is not a zpool/zfs command")]
    BadVerb {
        /// Zero-based index of the offending command.
        index: usize,
        /// The rejected verb.
        verb: String,
    },
    /// A token carries a character outside the shell-safe set — refused so a
    /// hand-edited plan can't smuggle shell metacharacters into a command.
    #[error("command #{index} token {token:?} carries an unsafe character")]
    UnsafeToken {
        /// Zero-based index of the offending command.
        index: usize,
        /// The rejected token.
        token: String,
    },
    /// The plan does not begin with a `zpool create` command.
    #[error("plan does not begin with a `zpool create` command")]
    NoPoolCreate,
    /// The `zpool create` command names no target device after `tank`.
    #[error("`zpool create` command names no target device after `tank`")]
    NoDevice,
    /// The named target device is not a safe block-device path.
    #[error("target device rejected: {0}")]
    Device(#[from] DeviceError),
}

/// Whether every character of `token` is in the shell-safe set drawn from the
/// canonical plan vocabulary (`recordsize=1M`, `zstd-9`, `tank/models`, device
/// paths). Rejects whitespace and shell metacharacters (`;`, `$`, `|`, `&`,
/// backticks, `<`, `>`, `(`, `)`, `*`, …).
fn token_is_safe(token: &str) -> bool {
    !token.is_empty()
        && token.chars().all(|c| {
            c.is_ascii_alphanumeric() || matches!(c, '_' | '/' | '.' | '-' | '=' | ':' | ',')
        })
}

/// Validate a plan JSON string: it must parse as a non-empty array of
/// `{purpose, argv}` commands, every command must be a known ZFS verb carrying
/// only shell-safe tokens, the plan must begin with `zpool create`, and the
/// target device (the token after `tank`) must pass the block-device contract.
fn check_plan(json: &str) -> Result<CheckReport, CheckError> {
    let plan: Vec<PlanCommand> =
        serde_json::from_str(json).map_err(|e| CheckError::Parse(e.to_string()))?;
    if plan.is_empty() {
        return Err(CheckError::Empty);
    }

    for (index, cmd) in plan.iter().enumerate() {
        let verb = cmd.argv.first().ok_or(CheckError::EmptyArgv { index })?;
        if verb != "zpool" && verb != "zfs" {
            return Err(CheckError::BadVerb {
                index,
                verb: verb.clone(),
            });
        }
        if let Some(bad) = cmd.argv.iter().find(|t| !token_is_safe(t)) {
            return Err(CheckError::UnsafeToken {
                index,
                token: bad.clone(),
            });
        }
    }

    let head = &plan[0].argv;
    if head.first().map(String::as_str) != Some("zpool")
        || head.get(1).map(String::as_str) != Some("create")
    {
        return Err(CheckError::NoPoolCreate);
    }

    // The target device is the token immediately after `tank`; re-validate it
    // through the library's block-device safety contract.
    let device = head
        .iter()
        .position(|t| t == "tank")
        .and_then(|p| head.get(p + 1))
        .ok_or(CheckError::NoDevice)?;
    validate_device(device)?;

    Ok(CheckReport {
        commands: plan.len(),
        device: device.clone(),
    })
}

/// `--check FILE`: read the file, validate the plan, print a report, and return
/// a process exit code (non-zero on read/parse error or an invalid plan).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("sovereign-zfs-provisioning-plan: --check {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    match check_plan(&json) {
        Ok(report) => {
            println!(
                "OK   plan valid: {} command(s), target device {}",
                report.commands, report.device
            );
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("FAIL {e}");
            ExitCode::FAILURE
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    // Reject unknown flags so a typo doesn't silently emit the default plan.
    // (`--device`'s value is a /dev path, not a flag, so it is not caught here.)
    if let Some(unknown) = args
        .iter()
        .find(|a| a.starts_with('-') && a.as_str() != "--device")
    {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    let device = args
        .iter()
        .position(|a| a == "--device")
        .and_then(|i| args.get(i + 1))
        .map_or(DEFAULT_DEVICE, String::as_str);

    match emit_plan(device) {
        Ok(script) => {
            print!("{script}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("error: invalid --device {device:?}: {e}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Serialize the canonical plan the library emits into the JSON shape that
    /// `--check` consumes — proving emit → check round-trips.
    fn canonical_plan_json(device: &str) -> String {
        serde_json::to_string(&provisioning_plan(device).unwrap()).unwrap()
    }

    #[test]
    fn emit_is_review_only_and_lists_every_dataset() {
        let script = emit_plan(DEFAULT_DEVICE).unwrap();
        assert!(script.contains("REVIEW ONLY"), "{script}");
        assert!(script.contains("does NOT execute"), "{script}");
        assert!(script.contains("zpool create"), "{script}");
        for path in ["tank/models", "tank/context", "tank/agents"] {
            assert!(
                script.contains(&format!("zfs create {path}")),
                "missing create for {path}:\n{script}"
            );
        }
    }

    #[test]
    fn emit_rejects_an_unsafe_device() {
        assert!(matches!(
            emit_plan("/dev/nvme0n1; rm -rf /"),
            Err(DeviceError::UnsafeChar(_))
        ));
    }

    #[test]
    fn check_accepts_the_canonical_emitted_plan() {
        let json = canonical_plan_json("/dev/nvme0n1");
        let report = check_plan(&json).unwrap();
        assert_eq!(report.device, "/dev/nvme0n1");
        // pool create + one create per dataset + the tuned datasets' set lines.
        assert!(report.commands >= 4, "{report:?}");
    }

    #[test]
    fn check_rejects_a_non_dev_target_device() {
        // A plan hand-edited to point the pool at a non-/dev path.
        let json = canonical_plan_json("/dev/nvme0n1").replace("/dev/nvme0n1", "/etc/passwd");
        assert!(matches!(
            check_plan(&json),
            Err(CheckError::Device(DeviceError::NotDevPath(_)))
        ));
    }

    #[test]
    fn check_rejects_an_injected_metacharacter() {
        // A device token carrying a `;` must be refused as an unsafe token
        // before it can ever reach a shell.
        let json = canonical_plan_json("/dev/nvme0n1").replace("/dev/nvme0n1", "/dev/nvme0n1;rm");
        assert!(matches!(
            check_plan(&json),
            Err(CheckError::UnsafeToken { .. })
        ));
    }

    #[test]
    fn check_rejects_empty_garbage_and_headless_plans() {
        assert!(matches!(check_plan("[]"), Err(CheckError::Empty)));
        assert!(matches!(check_plan("not json"), Err(CheckError::Parse(_))));
        // A well-formed command that isn't a `zpool create` at the head.
        let headless = r#"[{"purpose":"x","argv":["zfs","create","tank/models"]}]"#;
        assert!(matches!(
            check_plan(headless),
            Err(CheckError::NoPoolCreate)
        ));
    }
}
