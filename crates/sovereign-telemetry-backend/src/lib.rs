//! `sovereign-telemetry-backend` — M013 E0107: which telemetry backend the
//! runtime ships metrics/traces through, and how the operator overrides it.
//!
//! The observability plane (M00198/M00199 — DCGM-to-Prometheus + OpenTelemetry)
//! can emit through three backends:
//!
//! - **prom** — Prometheus-direct (a `/metrics` exposition endpoint + the
//!   node_exporter textfile-collector path). Lowest overhead; matches the
//!   exposition surface the rest of the stack already scrapes.
//! - **otel** — OpenTelemetry (traces / metrics / logs through an
//!   otel-collector, with context propagation).
//! - **dual** — both at once (Prometheus for cheap scrape-time gauges,
//!   OpenTelemetry for the trace_id/span_id/branch_id correlation of M00215).
//!
//! This crate fixes the backend taxonomy and the *operator override* contract
//! (R02194/R02197/R02199): a single token (`otel` / `prom` / `dual`) parsed
//! from the `SOVEREIGN_TELEMETRY_BACKEND` env var, the `--telemetry-backend`
//! CLI flag, or a profile knob, resolved by a fixed precedence. It is the
//! consumable substrate the runtime binary reads at startup; it does NOT itself
//! stand up a collector (that is the runtime's job).
//!
//! ```
//! use sovereign_telemetry_backend::{TelemetryBackend, ResolvedFrom, resolve};
//!
//! // CLI beats env beats profile beats the default.
//! let r = resolve(Some("dual"), Some("otel"), Some("prom")).unwrap();
//! assert_eq!(r.backend, TelemetryBackend::Dual);
//! assert_eq!(r.source, ResolvedFrom::Cli);
//!
//! // Nothing set anywhere → the documented default (prom).
//! let r = resolve(None, None, None).unwrap();
//! assert_eq!(r.backend, TelemetryBackend::default());
//! assert_eq!(r.source, ResolvedFrom::Default);
//! ```

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The env var that overrides the telemetry backend (R02197).
pub const ENV_VAR: &str = "SOVEREIGN_TELEMETRY_BACKEND";

/// The CLI flag that overrides the telemetry backend (R02199).
pub const CLI_FLAG: &str = "--telemetry-backend";

/// Which telemetry backend the runtime emits through (R02194).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TelemetryBackend {
    /// Prometheus-direct (`/metrics` exposition + textfile collector).
    Prom,
    /// OpenTelemetry (otel-collector; traces / metrics / logs).
    Otel,
    /// Both Prometheus and OpenTelemetry simultaneously.
    Dual,
}

impl TelemetryBackend {
    /// All three backends, in canonical order.
    pub const ALL: [TelemetryBackend; 3] = [
        TelemetryBackend::Prom,
        TelemetryBackend::Otel,
        TelemetryBackend::Dual,
    ];

    /// The canonical lower-case token (`prom` / `otel` / `dual`) — the form
    /// written in the env var, the CLI flag value, and a profile knob.
    #[must_use]
    pub const fn token(self) -> &'static str {
        match self {
            TelemetryBackend::Prom => "prom",
            TelemetryBackend::Otel => "otel",
            TelemetryBackend::Dual => "dual",
        }
    }

    /// Whether this backend emits a Prometheus exposition surface.
    #[must_use]
    pub const fn emits_prometheus(self) -> bool {
        matches!(self, TelemetryBackend::Prom | TelemetryBackend::Dual)
    }

    /// Whether this backend emits through OpenTelemetry.
    #[must_use]
    pub const fn emits_otel(self) -> bool {
        matches!(self, TelemetryBackend::Otel | TelemetryBackend::Dual)
    }

    /// Parse an operator-supplied token. Case-insensitive and whitespace-
    /// tolerant; accepts common aliases (`prometheus` → `prom`, `otlp`/
    /// `opentelemetry` → `otel`, `both` → `dual`). Returns `None` for an
    /// unrecognized token so callers can surface a precise error.
    #[must_use]
    pub fn from_token(token: &str) -> Option<TelemetryBackend> {
        match token.trim().to_ascii_lowercase().as_str() {
            "prom" | "prometheus" | "prom-direct" => Some(TelemetryBackend::Prom),
            "otel" | "otlp" | "opentelemetry" | "open-telemetry" => Some(TelemetryBackend::Otel),
            "dual" | "both" => Some(TelemetryBackend::Dual),
            _ => None,
        }
    }
}

impl Default for TelemetryBackend {
    /// The documented default when the operator overrides nothing: `prom`.
    /// Prometheus-direct is the lowest-overhead backend and matches the
    /// exposition surface the rest of the stack already scrapes. Chosen
    /// default (the catalogue states the override set, not a default).
    fn default() -> Self {
        TelemetryBackend::Prom
    }
}

impl std::fmt::Display for TelemetryBackend {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.token())
    }
}

/// Where a resolved backend value came from — the winning precedence rung.
/// Returned alongside the backend so the runtime can log *why* a backend is
/// active (operability: distinguishes "operator forced otel via CLI" from
/// "fell through to the default").
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ResolvedFrom {
    /// The `--telemetry-backend` CLI flag (highest precedence).
    Cli,
    /// The `SOVEREIGN_TELEMETRY_BACKEND` env var.
    Env,
    /// A profile knob (`telemetry_backend = ...`).
    Profile,
    /// No override anywhere; the built-in default.
    Default,
}

/// A resolved backend plus the rung it was resolved from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Resolution {
    /// The selected backend.
    pub backend: TelemetryBackend,
    /// Which precedence rung supplied it.
    pub source: ResolvedFrom,
}

/// Why a backend could not be resolved.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum TelemetryBackendError {
    /// A supplied override token was not a recognized backend.
    #[error("{rung} value {token:?} is not a telemetry backend (expected one of: prom, otel, dual)")]
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
            ResolvedFrom::Cli => "--telemetry-backend",
            ResolvedFrom::Env => "SOVEREIGN_TELEMETRY_BACKEND",
            ResolvedFrom::Profile => "profile telemetry_backend",
            ResolvedFrom::Default => "default",
        })
    }
}

/// Resolve the active telemetry backend by precedence (R02194):
///
/// 1. `cli` — the `--telemetry-backend` flag (operator's most explicit intent),
/// 2. `env` — the `SOVEREIGN_TELEMETRY_BACKEND` env var,
/// 3. `profile` — a profile knob,
/// 4. the built-in [`TelemetryBackend::default`].
///
/// Each rung is consulted only if the higher one is absent (`None`). A *present
/// but unparseable* token is a hard error (it is not silently skipped to a
/// lower rung — an operator who typed `--telemetry-backend otlel` wants to know
/// they fat-fingered it, not to silently get the default). Empty / whitespace-
/// only strings count as absent so a blank env var doesn't mask a profile knob.
pub fn resolve(
    cli: Option<&str>,
    env: Option<&str>,
    profile: Option<&str>,
) -> Result<Resolution, TelemetryBackendError> {
    for (rung, value) in [
        (ResolvedFrom::Cli, cli),
        (ResolvedFrom::Env, env),
        (ResolvedFrom::Profile, profile),
    ] {
        let Some(raw) = value else { continue };
        if raw.trim().is_empty() {
            continue;
        }
        let backend = TelemetryBackend::from_token(raw).ok_or_else(|| {
            TelemetryBackendError::BadToken {
                rung,
                token: raw.trim().to_string(),
            }
        })?;
        return Ok(Resolution { backend, source: rung });
    }
    Ok(Resolution {
        backend: TelemetryBackend::default(),
        source: ResolvedFrom::Default,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_backends_round_trip_their_tokens() {
        assert_eq!(TelemetryBackend::ALL.len(), 3);
        for b in TelemetryBackend::ALL {
            assert_eq!(TelemetryBackend::from_token(b.token()), Some(b));
        }
    }

    #[test]
    fn from_token_is_case_insensitive_and_aliased() {
        assert_eq!(TelemetryBackend::from_token("PROM"), Some(TelemetryBackend::Prom));
        assert_eq!(TelemetryBackend::from_token("  prometheus "), Some(TelemetryBackend::Prom));
        assert_eq!(TelemetryBackend::from_token("OTLP"), Some(TelemetryBackend::Otel));
        assert_eq!(TelemetryBackend::from_token("OpenTelemetry"), Some(TelemetryBackend::Otel));
        assert_eq!(TelemetryBackend::from_token("both"), Some(TelemetryBackend::Dual));
        assert_eq!(TelemetryBackend::from_token("otlel"), None);
        assert_eq!(TelemetryBackend::from_token(""), None);
    }

    #[test]
    fn emission_predicates() {
        assert!(TelemetryBackend::Prom.emits_prometheus());
        assert!(!TelemetryBackend::Prom.emits_otel());
        assert!(TelemetryBackend::Otel.emits_otel());
        assert!(!TelemetryBackend::Otel.emits_prometheus());
        assert!(TelemetryBackend::Dual.emits_prometheus());
        assert!(TelemetryBackend::Dual.emits_otel());
    }

    #[test]
    fn default_is_prom() {
        assert_eq!(TelemetryBackend::default(), TelemetryBackend::Prom);
    }

    #[test]
    fn cli_beats_env_beats_profile_beats_default() {
        assert_eq!(
            resolve(Some("dual"), Some("otel"), Some("prom")).unwrap(),
            Resolution { backend: TelemetryBackend::Dual, source: ResolvedFrom::Cli }
        );
        assert_eq!(
            resolve(None, Some("otel"), Some("prom")).unwrap(),
            Resolution { backend: TelemetryBackend::Otel, source: ResolvedFrom::Env }
        );
        assert_eq!(
            resolve(None, None, Some("dual")).unwrap(),
            Resolution { backend: TelemetryBackend::Dual, source: ResolvedFrom::Profile }
        );
        assert_eq!(
            resolve(None, None, None).unwrap(),
            Resolution { backend: TelemetryBackend::Prom, source: ResolvedFrom::Default }
        );
    }

    #[test]
    fn blank_rungs_fall_through_to_the_next() {
        // A blank env var must not mask a real profile knob.
        assert_eq!(
            resolve(None, Some("   "), Some("otel")).unwrap(),
            Resolution { backend: TelemetryBackend::Otel, source: ResolvedFrom::Profile }
        );
        // Blank everywhere → default.
        assert_eq!(
            resolve(Some(""), Some(" "), Some("")).unwrap().source,
            ResolvedFrom::Default
        );
    }

    #[test]
    fn present_but_bad_token_is_an_error_not_a_fallthrough() {
        // A fat-fingered CLI value must error, NOT silently use env/default.
        let err = resolve(Some("otlel"), Some("prom"), None).unwrap_err();
        assert_eq!(
            err,
            TelemetryBackendError::BadToken {
                rung: ResolvedFrom::Cli,
                token: "otlel".to_string()
            }
        );
        // The error names the rung so the operator knows where to look.
        assert!(err.to_string().contains("--telemetry-backend"));
    }

    #[test]
    fn serde_kebab_tokens() {
        assert_eq!(serde_json::to_string(&TelemetryBackend::Prom).unwrap(), "\"prom\"");
        assert_eq!(serde_json::to_string(&TelemetryBackend::Otel).unwrap(), "\"otel\"");
        assert_eq!(serde_json::to_string(&TelemetryBackend::Dual).unwrap(), "\"dual\"");
        assert_eq!(serde_json::to_string(&ResolvedFrom::Cli).unwrap(), "\"cli\"");
    }
}
