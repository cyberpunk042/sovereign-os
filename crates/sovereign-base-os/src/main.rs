//! `sovereign-base-os` CLI — the runnable end of E0459 / M00800.
//!
//! The library fixes the base-OS model: the OS base owns **10 responsibilities**
//! (kernel / firmware / NVIDIA drivers / AppArmor / cgroup-v2 / systemd / ZFS /
//! LUKS / networking / VFIO-IOMMU) and runs in one of **5 config modes**
//! (stable / ai-driver-latest / secure / developer / offline), under the E0459
//! principle: "declarative where it protects continuity, imperative where
//! hardware reality demands adaptation." But nothing *ran* it, so "does this
//! provisioning config honour that model?" was unanswerable at the command line.
//! This binary is that runnable end. It never executes an install — it only
//! *emits* the canonical model and *validates* a config against it.
//!
//! Modes:
//!   * default (no args) — print the canonical base-OS provisioning model: the
//!     10 responsibilities, each tagged with the E0459 strategy the principle
//!     assigns it (declarative for continuity, imperative for hardware reality),
//!     and the 5 config modes with their network posture. A reference only —
//!     nothing is executed.
//!   * `--check FILE` — load a `BaseOsConfig` from JSON and `validate()` it:
//!     all 10 responsibilities covered exactly once, each with the strategy the
//!     E0459 principle requires. Reports OK / the `ConfigError`; exits non-zero
//!     on any failure.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::fmt;
use std::process::ExitCode;

use serde::{Deserialize, Serialize};
use sovereign_base_os::{OsConfigMode, OsResponsibility};

/// How the base OS handles a responsibility. The E0459 principle binds this to
/// [`OsResponsibility::is_hardware_reality`]: continuity-protecting parts are
/// **declarative**, hardware-reality parts are **imperative**.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
enum Strategy {
    /// Declared once, rebuilt reproducibly — protects continuity.
    Declarative,
    /// Adapted imperatively to whatever hardware is actually present.
    Imperative,
}

/// The strategy the E0459 principle *requires* for a responsibility: imperative
/// for the three hardware-reality responsibilities, declarative for the rest.
fn required_strategy(r: OsResponsibility) -> Strategy {
    if r.is_hardware_reality() {
        Strategy::Imperative
    } else {
        Strategy::Declarative
    }
}

/// One line of a provisioning config: how a single responsibility is handled.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ResponsibilityPlan {
    /// Which of the 10 base-OS responsibilities this plans for.
    responsibility: OsResponsibility,
    /// The strategy the config declares for it.
    strategy: Strategy,
}

/// A base-OS provisioning config: a chosen config mode plus a strategy for each
/// responsibility. This is the reviewable artefact `--check` validates.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct BaseOsConfig {
    /// One of the 5 config modes (validated to be one of them by serde).
    mode: OsConfigMode,
    /// The per-responsibility plan; must cover all 10 exactly once.
    responsibilities: Vec<ResponsibilityPlan>,
}

/// Why a [`BaseOsConfig`] fails validation.
#[derive(Debug, Clone, PartialEq, Eq)]
enum ConfigError {
    /// A required responsibility is absent (the base OS must own all 10).
    MissingResponsibility(OsResponsibility),
    /// A responsibility is declared more than once.
    DuplicateResponsibility(OsResponsibility),
    /// A responsibility's strategy violates the E0459 principle.
    WrongStrategy {
        /// The offending responsibility.
        responsibility: OsResponsibility,
        /// The strategy the principle requires.
        expected: Strategy,
        /// The strategy the config declared.
        found: Strategy,
    },
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::MissingResponsibility(r) => write!(
                f,
                "missing responsibility '{}' — the base OS must own all 10",
                responsibility_label(*r)
            ),
            ConfigError::DuplicateResponsibility(r) => write!(
                f,
                "responsibility '{}' declared more than once",
                responsibility_label(*r)
            ),
            ConfigError::WrongStrategy {
                responsibility,
                expected,
                found,
            } => write!(
                f,
                "responsibility '{}' must be '{}' per the E0459 principle, but the config declares '{}'",
                responsibility_label(*responsibility),
                strategy_label(*expected),
                strategy_label(*found),
            ),
        }
    }
}

impl BaseOsConfig {
    /// Validate the config against the base-OS model: every one of the 10
    /// responsibilities is covered exactly once, and each carries the strategy
    /// the E0459 principle requires. Errors are reported in canonical
    /// [`OsResponsibility::ALL`] order.
    fn validate(&self) -> Result<(), ConfigError> {
        for r in OsResponsibility::ALL {
            let count = self
                .responsibilities
                .iter()
                .filter(|p| p.responsibility == r)
                .count();
            if count == 0 {
                return Err(ConfigError::MissingResponsibility(r));
            }
            if count > 1 {
                return Err(ConfigError::DuplicateResponsibility(r));
            }
        }
        for r in OsResponsibility::ALL {
            if let Some(plan) = self.responsibilities.iter().find(|p| p.responsibility == r) {
                let expected = required_strategy(r);
                if plan.strategy != expected {
                    return Err(ConfigError::WrongStrategy {
                        responsibility: r,
                        expected,
                        found: plan.strategy,
                    });
                }
            }
        }
        Ok(())
    }
}

/// The stable kebab-case label for a responsibility — identical to how
/// [`OsResponsibility`] serializes to JSON (kept honest by the
/// `labels_match_serde` test).
fn responsibility_label(r: OsResponsibility) -> &'static str {
    match r {
        OsResponsibility::Kernel => "kernel",
        OsResponsibility::Firmware => "firmware",
        OsResponsibility::NvidiaDrivers => "nvidia-drivers",
        OsResponsibility::AppArmor => "app-armor",
        OsResponsibility::CgroupV2 => "cgroup-v2",
        OsResponsibility::Systemd => "systemd",
        OsResponsibility::Zfs => "zfs",
        OsResponsibility::Luks => "luks",
        OsResponsibility::Networking => "networking",
        OsResponsibility::VfioIommu => "vfio-iommu",
    }
}

/// The stable kebab-case label for a config mode — matches serde.
fn mode_label(m: OsConfigMode) -> &'static str {
    match m {
        OsConfigMode::Stable => "stable",
        OsConfigMode::AiDriverLatest => "ai-driver-latest",
        OsConfigMode::Secure => "secure",
        OsConfigMode::Developer => "developer",
        OsConfigMode::Offline => "offline",
    }
}

/// The stable kebab-case label for a strategy — matches serde.
fn strategy_label(s: Strategy) -> &'static str {
    match s {
        Strategy::Declarative => "declarative",
        Strategy::Imperative => "imperative",
    }
}

/// The human-readable reference: the canonical base-OS provisioning model.
fn reference_text() -> String {
    let mut s = String::from(
        "Sovereign Base OS — E0459 / M00800 (reference model; nothing is executed).\n\n\
         The base OS owns 10 responsibilities. Per the E0459 principle — \"declarative\n\
         where it protects continuity, imperative where hardware reality demands\n\
         adaptation\" — each is handled one way:\n\n",
    );
    for (i, r) in OsResponsibility::ALL.into_iter().enumerate() {
        let strategy = required_strategy(r);
        let why = if r.is_hardware_reality() {
            "hardware reality"
        } else {
            "continuity"
        };
        s.push_str(&format!(
            "  {:>2}. {:<15} {:<12} ({why})\n",
            i + 1,
            responsibility_label(r),
            strategy_label(strategy),
        ));
    }
    s.push_str("\nThe 5 config modes:\n\n");
    for m in OsConfigMode::ALL {
        let net = if m.network_enabled() {
            "network: enabled"
        } else {
            "network: disabled"
        };
        s.push_str(&format!("  * {:<16} {net}\n", mode_label(m)));
    }
    s.push_str("\nValidate a provisioning config with:  sovereign-base-os --check FILE\n");
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-base-os — the base-OS provisioning model (E0459 / M00800)\n\n\
     The base OS owns 10 responsibilities and runs in one of 5 config modes,\n\
     under the E0459 principle: declarative where it protects continuity,\n\
     imperative where hardware reality demands adaptation.\n\n\
     USAGE:\n\
     \x20   sovereign-base-os                 print the canonical base-OS model (reference)\n\
     \x20   sovereign-base-os --check FILE     validate a BaseOsConfig from JSON\n\
     \x20   sovereign-base-os --help           print this help and exit\n\n\
     --check FILE loads a BaseOsConfig { mode, responsibilities: [{ responsibility,\n\
     strategy }] }, verifies all 10 responsibilities are covered exactly once and\n\
     each carries the strategy the E0459 principle requires, and exits non-zero on\n\
     any failure. It never runs an install — it only reviews the config.\n"
        .to_string()
}

/// Parse a `BaseOsConfig` from JSON text.
fn parse_config(json: &str) -> Result<BaseOsConfig, serde_json::Error> {
    serde_json::from_str(json)
}

/// `--check FILE`: read the file, parse & validate the config, print a report,
/// and return a process exit code (non-zero on read/parse error or failure).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let config = match parse_config(&json) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {path} is not a BaseOsConfig: {e}");
            return ExitCode::FAILURE;
        }
    };

    let net = if config.mode.network_enabled() {
        "enabled"
    } else {
        "disabled"
    };
    println!("config mode: {} (network: {net})", mode_label(config.mode));

    match config.validate() {
        Ok(()) => {
            println!("OK — all 10 base-OS responsibilities covered; E0459 strategy conforms");
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL — {err}");
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

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A config declaring all 10 responsibilities with the E0459-required strategy.
    fn canonical_config() -> BaseOsConfig {
        BaseOsConfig {
            mode: OsConfigMode::Stable,
            responsibilities: OsResponsibility::ALL
                .into_iter()
                .map(|r| ResponsibilityPlan {
                    responsibility: r,
                    strategy: required_strategy(r),
                })
                .collect(),
        }
    }

    #[test]
    fn reference_lists_all_ten_responsibilities_and_five_modes() {
        let t = reference_text();
        for r in OsResponsibility::ALL {
            assert!(
                t.contains(responsibility_label(r)),
                "reference missing {r:?}:\n{t}"
            );
        }
        for m in OsConfigMode::ALL {
            assert!(t.contains(mode_label(m)), "reference missing {m:?}:\n{t}");
        }
        // Exactly ten numbered responsibility lines.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, OsResponsibility::ALL.len());
    }

    #[test]
    fn labels_match_serde() {
        // The CLI's kebab labels must not drift from the enums' JSON forms.
        for r in OsResponsibility::ALL {
            let json = serde_json::to_string(&r).unwrap();
            assert_eq!(json, format!("\"{}\"", responsibility_label(r)));
        }
        for m in OsConfigMode::ALL {
            let json = serde_json::to_string(&m).unwrap();
            assert_eq!(json, format!("\"{}\"", mode_label(m)));
        }
        for s in [Strategy::Declarative, Strategy::Imperative] {
            let json = serde_json::to_string(&s).unwrap();
            assert_eq!(json, format!("\"{}\"", strategy_label(s)));
        }
    }

    #[test]
    fn canonical_config_validates_and_round_trips() {
        let cfg = canonical_config();
        assert!(cfg.validate().is_ok());
        // It must survive a JSON round-trip (the --check path).
        let json = serde_json::to_string(&cfg).unwrap();
        let parsed = parse_config(&json).unwrap();
        assert!(parsed.validate().is_ok());
    }

    #[test]
    fn missing_responsibility_rejected() {
        let mut cfg = canonical_config();
        // Drop the last-declared responsibility; the first missing one in
        // canonical order is Kernel only if we drop it — drop VfioIommu instead.
        cfg.responsibilities
            .retain(|p| p.responsibility != OsResponsibility::VfioIommu);
        assert_eq!(
            cfg.validate(),
            Err(ConfigError::MissingResponsibility(
                OsResponsibility::VfioIommu
            ))
        );
    }

    #[test]
    fn duplicate_responsibility_rejected() {
        let mut cfg = canonical_config();
        cfg.responsibilities.push(ResponsibilityPlan {
            responsibility: OsResponsibility::Kernel,
            strategy: Strategy::Declarative,
        });
        assert_eq!(
            cfg.validate(),
            Err(ConfigError::DuplicateResponsibility(
                OsResponsibility::Kernel
            ))
        );
    }

    #[test]
    fn wrong_strategy_rejected() {
        let mut cfg = canonical_config();
        // NVIDIA drivers are hardware reality → must be imperative. Force the
        // wrong (declarative) strategy and expect the E0459 violation.
        for p in &mut cfg.responsibilities {
            if p.responsibility == OsResponsibility::NvidiaDrivers {
                p.strategy = Strategy::Declarative;
            }
        }
        assert_eq!(
            cfg.validate(),
            Err(ConfigError::WrongStrategy {
                responsibility: OsResponsibility::NvidiaDrivers,
                expected: Strategy::Imperative,
                found: Strategy::Declarative,
            })
        );
    }

    #[test]
    fn required_strategy_follows_hardware_reality() {
        for r in OsResponsibility::ALL {
            let expected = if r.is_hardware_reality() {
                Strategy::Imperative
            } else {
                Strategy::Declarative
            };
            assert_eq!(required_strategy(r), expected, "{r:?}");
        }
    }

    #[test]
    fn parse_reports_invalid_json_as_error() {
        assert!(parse_config("not json").is_err());
        // An unknown config mode must also be rejected by serde.
        assert!(parse_config(r#"{"mode":"nope","responsibilities":[]}"#).is_err());
    }
}
