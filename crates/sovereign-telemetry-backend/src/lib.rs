//! `sovereign-telemetry-backend` — operator-overrideable telemetry sink.
//!
//! Where the runtime ships metrics/traces, and how the operator overrides it.
//!
//! # Source of truth: the profile schema, not the backlog catalogue
//!
//! The authoritative vocabulary is the **profile field**
//! `observability.telemetry_sink`, defined by SDD-004 (Q-013) and bound by
//! SDD-016, declared by every profile in `profiles/*.yaml` and exercised by
//! `tests/unit/test_profile_merger.py` + `tests/lint/test_build_lib_contract.py`.
//! Its three values are:
//!
//! - **`prometheus-local`** (default) — Prometheus textfile collector at
//!   `/var/lib/node_exporter/textfile_collector/sovereign-os.prom` (SDD-016
//!   Layer B). Local-default, no phone-home.
//! - **`otel`** — OpenTelemetry (remote sink; requires operator action).
//! - **`none`** — telemetry disabled (structured logs, SDD-016 Layer A, stay on).
//!
//! > Reconciliation note: the M013 *backlog catalogue* (F01024/F01025) proposed
//! > a different field (`telemetry_backend`) and value set (`otel` / `prom` /
//! > `dual`). That catalogue is aspirational and DIVERGES from the applied
//! > profile schema — there is no `dual` sink operationally, and the disabled
//! > state is `none`. This crate follows the profile schema (operational truth);
//! > a `dual` sink would be a future schema change, not an existing fact.
//!
//! This crate fixes the sink taxonomy and the *operator override* contract: a
//! single token parsed from the `observability.telemetry_sink` profile field,
//! the `SOVEREIGN_TELEMETRY_SINK` env var, or the `--telemetry-sink` CLI flag,
//! resolved by a fixed precedence. It is consumable substrate the runtime reads
//! at startup; it does NOT stand up a collector.
//!
//! ```
//! use sovereign_telemetry_backend::{TelemetrySink, ResolvedFrom, resolve};
//!
//! // CLI beats env beats profile beats the default.
//! let r = resolve(Some("otel"), Some("none"), Some("prometheus-local")).unwrap();
//! assert_eq!(r.sink, TelemetrySink::Otel);
//! assert_eq!(r.source, ResolvedFrom::Cli);
//!
//! // Nothing set anywhere → the documented default (prometheus-local).
//! let r = resolve(None, None, None).unwrap();
//! assert_eq!(r.sink, TelemetrySink::default());
//! assert_eq!(r.source, ResolvedFrom::Default);
//! ```

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The env var that overrides the telemetry sink.
pub const ENV_VAR: &str = "SOVEREIGN_TELEMETRY_SINK";

/// The CLI flag that overrides the telemetry sink.
pub const CLI_FLAG: &str = "--telemetry-sink";

/// Where the runtime ships telemetry (`observability.telemetry_sink`, SDD-004).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TelemetrySink {
    /// Prometheus textfile collector — local-default, no phone-home.
    #[serde(rename = "prometheus-local")]
    PrometheusLocal,
    /// OpenTelemetry (remote sink; operator action required).
    Otel,
    /// Telemetry disabled (structured logs stay on).
    None,
}

impl TelemetrySink {
    /// All three sinks, in canonical order.
    pub const ALL: [TelemetrySink; 3] = [
        TelemetrySink::PrometheusLocal,
        TelemetrySink::Otel,
        TelemetrySink::None,
    ];

    /// The canonical token, exactly as written in `telemetry_sink`.
    #[must_use]
    pub const fn token(self) -> &'static str {
        match self {
            TelemetrySink::PrometheusLocal => "prometheus-local",
            TelemetrySink::Otel => "otel",
            TelemetrySink::None => "none",
        }
    }

    /// Whether this sink emits a Prometheus exposition / textfile surface.
    #[must_use]
    pub const fn emits_prometheus(self) -> bool {
        matches!(self, TelemetrySink::PrometheusLocal)
    }

    /// Whether this sink emits through OpenTelemetry.
    #[must_use]
    pub const fn emits_otel(self) -> bool {
        matches!(self, TelemetrySink::Otel)
    }

    /// Whether telemetry is enabled at all (structured logs are independent).
    #[must_use]
    pub const fn is_enabled(self) -> bool {
        !matches!(self, TelemetrySink::None)
    }

    /// Parse an operator-supplied token. Case-insensitive and whitespace-
    /// tolerant; accepts the canonical `prometheus-local` / `otel` / `none`
    /// plus convenience aliases (`prom` / `prometheus` → `prometheus-local`,
    /// `otlp` / `opentelemetry` → `otel`, `off` / `disabled` → `none`). Returns
    /// `None` for an unrecognized token so callers can surface a precise error.
    #[must_use]
    pub fn from_token(token: &str) -> Option<TelemetrySink> {
        match token.trim().to_ascii_lowercase().as_str() {
            "prometheus-local" | "prometheus_local" | "prom" | "prometheus" | "prom-direct" => {
                Some(TelemetrySink::PrometheusLocal)
            }
            "otel" | "otlp" | "opentelemetry" | "open-telemetry" => Some(TelemetrySink::Otel),
            "none" | "off" | "disabled" => Some(TelemetrySink::None),
            _ => None,
        }
    }
}

impl Default for TelemetrySink {
    /// The profile-schema default: `prometheus-local` (SDD-016 Layer B,
    /// local-default, no phone-home).
    fn default() -> Self {
        TelemetrySink::PrometheusLocal
    }
}

impl std::fmt::Display for TelemetrySink {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.token())
    }
}

/// Where a resolved sink value came from — the winning precedence rung.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ResolvedFrom {
    /// The `--telemetry-sink` CLI flag (highest precedence).
    Cli,
    /// The `SOVEREIGN_TELEMETRY_SINK` env var.
    Env,
    /// The `observability.telemetry_sink` profile field.
    Profile,
    /// No override anywhere; the built-in default.
    Default,
}

/// A resolved sink plus the rung it was resolved from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Resolution {
    /// The selected sink.
    pub sink: TelemetrySink,
    /// Which precedence rung supplied it.
    pub source: ResolvedFrom,
}

/// Why a sink could not be resolved.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum TelemetrySinkError {
    /// A supplied override token was not a recognized sink.
    #[error(
        "{rung} value {token:?} is not a telemetry sink (expected one of: prometheus-local, otel, none)"
    )]
    BadToken {
        /// Which rung carried the bad token.
        rung: ResolvedFrom,
        /// The offending token.
        token: String,
    },
}

impl std::fmt::Display for ResolvedFrom {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            ResolvedFrom::Cli => "--telemetry-sink",
            ResolvedFrom::Env => "SOVEREIGN_TELEMETRY_SINK",
            ResolvedFrom::Profile => "profile telemetry_sink",
            ResolvedFrom::Default => "default",
        })
    }
}

/// Resolve the active telemetry sink by precedence:
///
/// 1. `cli` — the `--telemetry-sink` flag,
/// 2. `env` — the `SOVEREIGN_TELEMETRY_SINK` env var,
/// 3. `profile` — the `observability.telemetry_sink` field,
/// 4. the built-in [`TelemetrySink::default`] (`prometheus-local`).
///
/// Each rung is consulted only if the higher one is absent (`None`). A present
/// but unparseable token is a hard error (not silently skipped to a lower rung).
/// Empty / whitespace-only strings count as absent so a blank env var doesn't
/// mask a profile field.
pub fn resolve(
    cli: Option<&str>,
    env: Option<&str>,
    profile: Option<&str>,
) -> Result<Resolution, TelemetrySinkError> {
    for (rung, value) in [
        (ResolvedFrom::Cli, cli),
        (ResolvedFrom::Env, env),
        (ResolvedFrom::Profile, profile),
    ] {
        let Some(raw) = value else { continue };
        if raw.trim().is_empty() {
            continue;
        }
        let sink = TelemetrySink::from_token(raw).ok_or_else(|| TelemetrySinkError::BadToken {
            rung,
            token: raw.trim().to_string(),
        })?;
        return Ok(Resolution { sink, source: rung });
    }
    Ok(Resolution {
        sink: TelemetrySink::default(),
        source: ResolvedFrom::Default,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_sinks_round_trip_their_tokens() {
        assert_eq!(TelemetrySink::ALL.len(), 3);
        for s in TelemetrySink::ALL {
            assert_eq!(TelemetrySink::from_token(s.token()), Some(s));
        }
    }

    #[test]
    fn profile_vocabulary_parses() {
        // The exact tokens every profiles/*.yaml uses + the SDD-004 set.
        assert_eq!(
            TelemetrySink::from_token("prometheus-local"),
            Some(TelemetrySink::PrometheusLocal)
        );
        assert_eq!(TelemetrySink::from_token("otel"), Some(TelemetrySink::Otel));
        assert_eq!(TelemetrySink::from_token("none"), Some(TelemetrySink::None));
    }

    #[test]
    fn aliases_and_case_insensitivity() {
        assert_eq!(
            TelemetrySink::from_token("PROM"),
            Some(TelemetrySink::PrometheusLocal)
        );
        assert_eq!(
            TelemetrySink::from_token("  prometheus "),
            Some(TelemetrySink::PrometheusLocal)
        );
        assert_eq!(TelemetrySink::from_token("OTLP"), Some(TelemetrySink::Otel));
        assert_eq!(TelemetrySink::from_token("off"), Some(TelemetrySink::None));
        assert_eq!(
            TelemetrySink::from_token("dual"),
            None,
            "no dual sink operationally"
        );
        assert_eq!(TelemetrySink::from_token(""), None);
    }

    #[test]
    fn emission_and_enabled_predicates() {
        assert!(TelemetrySink::PrometheusLocal.emits_prometheus());
        assert!(!TelemetrySink::PrometheusLocal.emits_otel());
        assert!(TelemetrySink::Otel.emits_otel());
        assert!(!TelemetrySink::Otel.emits_prometheus());
        assert!(TelemetrySink::PrometheusLocal.is_enabled());
        assert!(TelemetrySink::Otel.is_enabled());
        assert!(!TelemetrySink::None.is_enabled());
    }

    #[test]
    fn default_is_prometheus_local() {
        assert_eq!(TelemetrySink::default(), TelemetrySink::PrometheusLocal);
    }

    #[test]
    fn cli_beats_env_beats_profile_beats_default() {
        assert_eq!(
            resolve(Some("otel"), Some("none"), Some("prometheus-local")).unwrap(),
            Resolution {
                sink: TelemetrySink::Otel,
                source: ResolvedFrom::Cli
            }
        );
        assert_eq!(
            resolve(None, Some("none"), Some("prometheus-local")).unwrap(),
            Resolution {
                sink: TelemetrySink::None,
                source: ResolvedFrom::Env
            }
        );
        assert_eq!(
            resolve(None, None, Some("otel")).unwrap(),
            Resolution {
                sink: TelemetrySink::Otel,
                source: ResolvedFrom::Profile
            }
        );
        assert_eq!(
            resolve(None, None, None).unwrap(),
            Resolution {
                sink: TelemetrySink::PrometheusLocal,
                source: ResolvedFrom::Default
            }
        );
    }

    #[test]
    fn blank_rungs_fall_through() {
        assert_eq!(
            resolve(None, Some("   "), Some("otel")).unwrap(),
            Resolution {
                sink: TelemetrySink::Otel,
                source: ResolvedFrom::Profile
            }
        );
        assert_eq!(
            resolve(Some(""), Some(" "), Some("")).unwrap().source,
            ResolvedFrom::Default
        );
    }

    #[test]
    fn present_but_bad_token_errors_naming_the_rung() {
        let err = resolve(Some("dual"), Some("otel"), None).unwrap_err();
        assert_eq!(
            err,
            TelemetrySinkError::BadToken {
                rung: ResolvedFrom::Cli,
                token: "dual".to_string()
            }
        );
        assert!(err.to_string().contains("--telemetry-sink"));
    }

    #[test]
    fn serde_matches_profile_field_form() {
        // Serde wire form must equal the token written in profiles/*.yaml.
        assert_eq!(
            serde_json::to_string(&TelemetrySink::PrometheusLocal).unwrap(),
            "\"prometheus-local\""
        );
        assert_eq!(
            serde_json::to_string(&TelemetrySink::Otel).unwrap(),
            "\"otel\""
        );
        assert_eq!(
            serde_json::to_string(&TelemetrySink::None).unwrap(),
            "\"none\""
        );
        assert_eq!(
            serde_json::to_string(&ResolvedFrom::Cli).unwrap(),
            "\"cli\""
        );
    }
}
