//! `sovereign-zfs-dataset-layout` — M068: the canonical `tank` ZFS layout.
//!
//! The substrate storage layer is not "one big pool". Each dataset under `tank`
//! has a *purpose* that dictates its ZFS properties, and getting them wrong has
//! real consequences:
//!
//! - **tank/context** (sovereignty/integrity-critical state) — `sync=always`
//!   so the ZIL commits before a write is acknowledged (F05709/F05722). Losing
//!   this silently turns durable state into lose-on-power-cut state.
//! - **tank/containers** (Podman graph driver) — `recordsize=16k` +
//!   `compression=off`, matching Podman's allocation blocks (F05711/F05712).
//!   A compressed or mis-sized dataset here causes write amplification.
//! - **tank/models** (LLM weights) — `recordsize=1M` + `compression=zstd-3`
//!   for large sequential weight files (F05713/F05714).
//! - **tank/logs** — `recordsize=128k` + `compression=lz4` (F05715/F05716).
//! - **tank/snapshots** — `recordsize=128k`, retained for M041 rollbacks
//!   (F05717/F05718).
//! - **tank/vault** — security audit logs (F05719).
//!
//! Pool-level (E0660): `ashift=12` (4K NVMe alignment), `compression=lz4`
//! default, `atime=off` (F05702-F05705).
//!
//! This crate fixes those canonical values and provides [`validate_dataset`] /
//! [`audit_layout`]: compare an *observed* layout (parsed from `zfs get
//! recordsize,compression,sync <dataset>`) against the canon and surface the
//! drift, ranked by how dangerous it is. It does NOT run `zfs` — it is the
//! pure policy + validator the installer / health-check binary consumes.
//!
//! All property values are extracted verbatim from M068's doctrinal anchors +
//! F-rows (F05702-F05730); none are invented.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

// ── recordsize ──────────────────────────────────────────────────────

/// Smallest legal ZFS recordsize (bytes).
pub const RECORDSIZE_MIN: u32 = 512;
/// Largest recordsize this layout uses / accepts (bytes). ZFS supports up to
/// 16M with `large_blocks`, but the catalogued layout tops out at 1M; we cap
/// here to keep an obviously-wrong value (e.g. a parse slip into the hundreds
/// of MB) from validating.
pub const RECORDSIZE_MAX: u32 = 16 * 1024 * 1024;

/// Why a recordsize is not a legal ZFS value.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum RecordSizeError {
    /// The token could not be parsed (bad suffix, non-numeric, empty).
    #[error("{0:?} is not a recordsize (expected e.g. 512, 16K, 128K, 1M)")]
    Unparseable(String),
    /// Parsed, but not a power of two.
    #[error("recordsize {0} bytes is not a power of two")]
    NotPowerOfTwo(u32),
    /// Parsed, but outside the legal [512, 16M] range.
    #[error("recordsize {0} bytes is outside the legal range [512, 16777216]")]
    OutOfRange(u32),
}

/// Parse a ZFS recordsize token (`512`, `16K`, `128K`, `1M`, `1048576`) into
/// bytes. Case-insensitive `K`/`M` suffixes (binary, ×1024). Validates that the
/// result is a power of two within `[RECORDSIZE_MIN, RECORDSIZE_MAX]` — exactly
/// the constraints `zfs set recordsize` itself enforces.
pub fn parse_recordsize(token: &str) -> Result<u32, RecordSizeError> {
    let t = token.trim();
    if t.is_empty() {
        return Err(RecordSizeError::Unparseable(token.to_string()));
    }
    let (num, mult): (&str, u64) = match t.chars().last().unwrap() {
        'k' | 'K' => (&t[..t.len() - 1], 1024),
        'm' | 'M' => (&t[..t.len() - 1], 1024 * 1024),
        '0'..='9' => (t, 1),
        _ => return Err(RecordSizeError::Unparseable(token.to_string())),
    };
    let base: u64 = num
        .trim()
        .parse()
        .map_err(|_| RecordSizeError::Unparseable(token.to_string()))?;
    let bytes = base
        .checked_mul(mult)
        .filter(|b| *b <= u64::from(u32::MAX))
        .ok_or(RecordSizeError::OutOfRange(u32::MAX))?;
    let bytes = bytes as u32;
    if !(RECORDSIZE_MIN..=RECORDSIZE_MAX).contains(&bytes) {
        return Err(RecordSizeError::OutOfRange(bytes));
    }
    if !bytes.is_power_of_two() {
        return Err(RecordSizeError::NotPowerOfTwo(bytes));
    }
    Ok(bytes)
}

/// Render a recordsize in bytes as ZFS's human token (`16K`, `1M`, `512`).
#[must_use]
pub fn format_recordsize(bytes: u32) -> String {
    if bytes >= 1024 * 1024 && bytes.is_multiple_of(1024 * 1024) {
        format!("{}M", bytes / (1024 * 1024))
    } else if bytes >= 1024 && bytes.is_multiple_of(1024) {
        format!("{}K", bytes / 1024)
    } else {
        bytes.to_string()
    }
}

// ── properties ──────────────────────────────────────────────────────

/// ZFS compression setting used in the canonical layout.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Compression {
    /// No compression (Podman graph driver alignment — tank/containers).
    Off,
    /// lz4 (pool default; balanced).
    Lz4,
    /// zstd level 3 (better ratio for LLM weights — tank/models). Renamed so
    /// the serde wire form matches the actual ZFS token `zstd-3` (serde's
    /// kebab-case would otherwise yield `zstd3`, which ZFS does not accept).
    #[serde(rename = "zstd-3")]
    Zstd3,
}

impl Compression {
    /// Parse a `zfs get compression` value token.
    #[must_use]
    pub fn from_token(token: &str) -> Option<Compression> {
        match token.trim().to_ascii_lowercase().as_str() {
            "off" => Some(Compression::Off),
            "lz4" => Some(Compression::Lz4),
            "zstd-3" | "zstd_3" => Some(Compression::Zstd3),
            _ => None,
        }
    }
    /// The ZFS token for this setting.
    #[must_use]
    pub const fn token(self) -> &'static str {
        match self {
            Compression::Off => "off",
            Compression::Lz4 => "lz4",
            Compression::Zstd3 => "zstd-3",
        }
    }
}

/// ZFS `sync` policy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Sync {
    /// `standard` — honor application sync requests (the ZFS default).
    Standard,
    /// `always` — every write is synchronous (sovereignty/integrity-critical).
    Always,
    /// `disabled` — ignore sync requests (never used in the canon).
    Disabled,
}

impl Sync {
    /// Parse a `zfs get sync` value token.
    #[must_use]
    pub fn from_token(token: &str) -> Option<Sync> {
        match token.trim().to_ascii_lowercase().as_str() {
            "standard" => Some(Sync::Standard),
            "always" => Some(Sync::Always),
            "disabled" => Some(Sync::Disabled),
            _ => None,
        }
    }
    /// The ZFS token for this setting.
    #[must_use]
    pub const fn token(self) -> &'static str {
        match self {
            Sync::Standard => "standard",
            Sync::Always => "always",
            Sync::Disabled => "disabled",
        }
    }
}

// ── datasets ────────────────────────────────────────────────────────

/// A dataset in the canonical `tank` hierarchy (E0661).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Dataset {
    /// `tank/context` — sovereignty/integrity-critical state.
    Context,
    /// `tank/containers` — Podman graph driver storage.
    Containers,
    /// `tank/models` — LLM weight files.
    Models,
    /// `tank/logs` — runtime logs.
    Logs,
    /// `tank/snapshots` — M041 rollback retention.
    Snapshots,
    /// `tank/vault` — security audit logs.
    Vault,
}

impl Dataset {
    /// All six canonical datasets.
    pub const ALL: [Dataset; 6] = [
        Dataset::Context,
        Dataset::Containers,
        Dataset::Models,
        Dataset::Logs,
        Dataset::Snapshots,
        Dataset::Vault,
    ];

    /// The full ZFS dataset path under `tank`.
    #[must_use]
    pub const fn path(self) -> &'static str {
        match self {
            Dataset::Context => "tank/context",
            Dataset::Containers => "tank/containers",
            Dataset::Models => "tank/models",
            Dataset::Logs => "tank/logs",
            Dataset::Snapshots => "tank/snapshots",
            Dataset::Vault => "tank/vault",
        }
    }
}

/// The canonical ZFS properties for one dataset.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct DatasetSpec {
    /// Which dataset.
    pub dataset: Dataset,
    /// `recordsize` in bytes.
    pub recordsize: u32,
    /// `compression`.
    pub compression: Compression,
    /// `sync`.
    pub sync: Sync,
}

/// Pool-level (`tank`) properties (E0660 / F05702-F05705).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct PoolSpec {
    /// `ashift` — 12 for 4K-physical NVMe alignment.
    pub ashift: u8,
    /// Pool-default `compression`.
    pub compression: Compression,
    /// Whether `atime` is off.
    pub atime_off: bool,
}

/// The canonical pool spec: `ashift=12`, `compression=lz4`, `atime=off`.
#[must_use]
pub fn canonical_pool() -> PoolSpec {
    PoolSpec { ashift: 12, compression: Compression::Lz4, atime_off: true }
}

/// The canonical per-dataset specs, verbatim from M068 F05709-F05717.
#[must_use]
pub fn canonical_layout() -> [DatasetSpec; 6] {
    [
        // sovereignty-critical: sync=always; inherits lz4; default 128k record.
        DatasetSpec { dataset: Dataset::Context, recordsize: 128 * 1024, compression: Compression::Lz4, sync: Sync::Always },
        // Podman alignment: 16k, uncompressed.
        DatasetSpec { dataset: Dataset::Containers, recordsize: 16 * 1024, compression: Compression::Off, sync: Sync::Standard },
        // Large weight files: 1M, zstd-3.
        DatasetSpec { dataset: Dataset::Models, recordsize: 1024 * 1024, compression: Compression::Zstd3, sync: Sync::Standard },
        DatasetSpec { dataset: Dataset::Logs, recordsize: 128 * 1024, compression: Compression::Lz4, sync: Sync::Standard },
        DatasetSpec { dataset: Dataset::Snapshots, recordsize: 128 * 1024, compression: Compression::Lz4, sync: Sync::Standard },
        DatasetSpec { dataset: Dataset::Vault, recordsize: 128 * 1024, compression: Compression::Lz4, sync: Sync::Always },
    ]
}

/// The canonical spec for one dataset.
#[must_use]
pub fn canonical_spec(dataset: Dataset) -> DatasetSpec {
    canonical_layout()
        .into_iter()
        .find(|s| s.dataset == dataset)
        .expect("every Dataset has a canonical spec")
}

// ── drift validation ────────────────────────────────────────────────

/// How serious a layout drift is.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DriftSeverity {
    /// Performance / efficiency drift (e.g. wrong recordsize, wrong
    /// compression) — wastes IO or space but does not risk data loss.
    Performance,
    /// Integrity-critical drift — `tank/context` (or `tank/vault`) without
    /// `sync=always` means acknowledged writes can be lost on power loss.
    Integrity,
}

/// One property that does not match the canon.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LayoutDrift {
    /// Which dataset.
    pub dataset: Dataset,
    /// Which property drifted (`recordsize` / `compression` / `sync`).
    pub property: String,
    /// The canonical (expected) value, as a ZFS token.
    pub expected: String,
    /// The observed value, as a ZFS token.
    pub observed: String,
    /// How serious the drift is.
    pub severity: DriftSeverity,
}

/// Compare one observed dataset spec against its canon. Returns every property
/// that drifted (empty = matches the canon). A `sync` regression on an
/// integrity-critical dataset (context / vault) is flagged `Integrity`; all
/// other drift is `Performance`.
#[must_use]
pub fn validate_dataset(observed: &DatasetSpec) -> Vec<LayoutDrift> {
    let canon = canonical_spec(observed.dataset);
    let integrity_critical = matches!(observed.dataset, Dataset::Context | Dataset::Vault);
    let mut drift = Vec::new();
    if observed.recordsize != canon.recordsize {
        drift.push(LayoutDrift {
            dataset: observed.dataset,
            property: "recordsize".into(),
            expected: format_recordsize(canon.recordsize),
            observed: format_recordsize(observed.recordsize),
            severity: DriftSeverity::Performance,
        });
    }
    if observed.compression != canon.compression {
        drift.push(LayoutDrift {
            dataset: observed.dataset,
            property: "compression".into(),
            expected: canon.compression.token().into(),
            observed: observed.compression.token().into(),
            severity: DriftSeverity::Performance,
        });
    }
    if observed.sync != canon.sync {
        // Losing sync=always where the canon requires it is integrity-critical;
        // gaining sync (stricter than canon) is merely a performance choice.
        let severity = if canon.sync == Sync::Always && integrity_critical {
            DriftSeverity::Integrity
        } else {
            DriftSeverity::Performance
        };
        drift.push(LayoutDrift {
            dataset: observed.dataset,
            property: "sync".into(),
            expected: canon.sync.token().into(),
            observed: observed.sync.token().into(),
            severity,
        });
    }
    drift
}

/// Validate a whole observed layout. Returns all drift across all supplied
/// datasets, integrity drift first (so the worst problems read at the top).
#[must_use]
pub fn audit_layout(observed: &[DatasetSpec]) -> Vec<LayoutDrift> {
    let mut all: Vec<LayoutDrift> = observed.iter().flat_map(validate_dataset).collect();
    // Integrity > Performance; stable within a severity for predictable output.
    all.sort_by(|a, b| b.severity.cmp(&a.severity));
    all
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recordsize_parses_human_and_numeric() {
        assert_eq!(parse_recordsize("16K").unwrap(), 16 * 1024);
        assert_eq!(parse_recordsize("128k").unwrap(), 128 * 1024);
        assert_eq!(parse_recordsize("1M").unwrap(), 1024 * 1024);
        assert_eq!(parse_recordsize("512").unwrap(), 512);
        assert_eq!(parse_recordsize(" 1048576 ").unwrap(), 1024 * 1024);
    }

    #[test]
    fn recordsize_rejects_illegal_values() {
        assert!(matches!(parse_recordsize("100K"), Err(RecordSizeError::NotPowerOfTwo(_))));
        assert!(matches!(parse_recordsize("256"), Err(RecordSizeError::OutOfRange(_)))); // < 512
        assert!(matches!(parse_recordsize("32M"), Err(RecordSizeError::OutOfRange(_)))); // > 16M
        assert!(matches!(parse_recordsize("abc"), Err(RecordSizeError::Unparseable(_))));
        assert!(matches!(parse_recordsize(""), Err(RecordSizeError::Unparseable(_))));
    }

    #[test]
    fn recordsize_round_trips_format() {
        for token in ["512", "16K", "128K", "1M"] {
            let bytes = parse_recordsize(token).unwrap();
            assert_eq!(format_recordsize(bytes), token);
        }
    }

    #[test]
    fn every_dataset_has_a_canonical_spec() {
        for d in Dataset::ALL {
            let spec = canonical_spec(d);
            assert_eq!(spec.dataset, d);
            assert!(spec.recordsize.is_power_of_two());
        }
        assert_eq!(canonical_layout().len(), 6);
    }

    #[test]
    fn canon_validates_clean() {
        for spec in canonical_layout() {
            assert!(validate_dataset(&spec).is_empty(), "{:?} should match canon", spec.dataset);
        }
        assert!(audit_layout(&canonical_layout()).is_empty());
    }

    #[test]
    fn context_losing_sync_always_is_integrity_critical() {
        let mut bad = canonical_spec(Dataset::Context);
        bad.sync = Sync::Standard; // the dangerous regression
        let drift = validate_dataset(&bad);
        assert_eq!(drift.len(), 1);
        assert_eq!(drift[0].property, "sync");
        assert_eq!(drift[0].severity, DriftSeverity::Integrity);
        assert_eq!(drift[0].expected, "always");
        assert_eq!(drift[0].observed, "standard");
    }

    #[test]
    fn containers_compression_drift_is_performance() {
        let mut bad = canonical_spec(Dataset::Containers);
        bad.compression = Compression::Lz4; // should be off for Podman
        let drift = validate_dataset(&bad);
        assert_eq!(drift.len(), 1);
        assert_eq!(drift[0].property, "compression");
        assert_eq!(drift[0].severity, DriftSeverity::Performance);
    }

    #[test]
    fn audit_sorts_integrity_before_performance() {
        let observed = vec![
            DatasetSpec { dataset: Dataset::Containers, recordsize: 16 * 1024, compression: Compression::Lz4, sync: Sync::Standard }, // perf drift
            DatasetSpec { dataset: Dataset::Context, recordsize: 128 * 1024, compression: Compression::Lz4, sync: Sync::Standard }, // integrity drift
        ];
        let drift = audit_layout(&observed);
        assert_eq!(drift.len(), 2);
        assert_eq!(drift[0].severity, DriftSeverity::Integrity, "worst drift first");
        assert_eq!(drift[0].dataset, Dataset::Context);
    }

    #[test]
    fn pool_canon_matches_doctrine() {
        let p = canonical_pool();
        assert_eq!(p.ashift, 12);
        assert_eq!(p.compression, Compression::Lz4);
        assert!(p.atime_off);
    }

    #[test]
    fn serde_kebab_tokens() {
        assert_eq!(serde_json::to_string(&Dataset::Context).unwrap(), "\"context\"");
        assert_eq!(serde_json::to_string(&Compression::Zstd3).unwrap(), "\"zstd-3\"");
        assert_eq!(serde_json::to_string(&Sync::Always).unwrap(), "\"always\"");
        assert_eq!(serde_json::to_string(&DriftSeverity::Integrity).unwrap(), "\"integrity\"");
    }
}
