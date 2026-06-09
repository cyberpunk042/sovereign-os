//! `sovereign-zfs-dataset-layout` — the canonical `tank` ZFS layout.
//!
//! The substrate storage layer is not "one big pool". Each dataset under `tank`
//! has a *purpose* that dictates its ZFS properties, and getting them wrong
//! silently changes storage IO characteristics or durability.
//!
//! # Source of truth: the applied profile, not the backlog catalogue
//!
//! This crate encodes the **operator-verbatim §4.1 storage matrix** as it is
//! actually applied and regression-tested — `profiles/sain-01.yaml`
//! (`hardware.storage.datasets`), pinned by `tests/lint/test_zfs_datasets_
//! verbatim.py` (R396). That authoritative matrix is **three** datasets:
//!
//! | dataset | recordsize | compression | other | purpose |
//! |---------|-----------|-------------|-------|---------|
//! | **tank/models** | 1M | lz4 | `redundant_metadata=most` | 100GB+ weight files; large sequential reads |
//! | **tank/context** | 16k | zstd-9 | `copies=2`, `sync=always` | sovereignty/integrity-critical state fabric |
//! | **tank/agents** | 128k | zstd-3 | — | stateful local agent storage |
//!
//! > Reconciliation note: the M068 *backlog catalogue* proposes a richer
//! > 6-dataset model (`context`/`containers`/`models`/`logs`/`snapshots`/`vault`)
//! > with different properties (e.g. catalogue `models` = zstd-3, catalogue
//! > `context` = 128k/lz4). That catalogue is **aspirational** and DIVERGES from
//! > the applied profile. The applied profile is authoritative for validating
//! > the live system, so this crate follows it; adopting the catalogue's extra
//! > datasets is a future profile change, not an existing fact.
//!
//! Pool-level (E0660): `ashift=12` (4K NVMe alignment), `compression=lz4`
//! default, `atime=off`.
//!
//! [`validate_dataset`] / [`audit_layout`] compare an *observed* layout (parsed
//! from `zfs get`) against this canon and rank drift by danger. Drift on
//! `tank/context`'s `sync=always` or `copies=2` is **integrity-critical** (the
//! state fabric — IDENTITY/SOUL/AGENTS/CLAUDE — must survive single-block
//! corruption and power loss); recordsize / compression drift is performance.
//! It runs no `zfs`; it is the pure policy + validator the installer /
//! health-check binary consumes.

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
/// 16M with `large_blocks`, but the layout tops out at 1M; we cap here so an
/// obviously-wrong value can't validate.
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
/// bytes. Case-insensitive `K`/`M` suffixes (binary, ×1024). Validates power of
/// two within `[RECORDSIZE_MIN, RECORDSIZE_MAX]` — the constraints `zfs set
/// recordsize` itself enforces.
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
    /// No compression.
    Off,
    /// lz4 (pool default; balanced — `tank/models`).
    Lz4,
    /// zstd level 3 (`tank/agents`).
    #[serde(rename = "zstd-3")]
    Zstd3,
    /// zstd level 9 (max ratio for small state files — `tank/context`).
    #[serde(rename = "zstd-9")]
    Zstd9,
}

impl Compression {
    /// Parse a `zfs get compression` value token.
    #[must_use]
    pub fn from_token(token: &str) -> Option<Compression> {
        match token.trim().to_ascii_lowercase().as_str() {
            "off" => Some(Compression::Off),
            "lz4" => Some(Compression::Lz4),
            "zstd-3" | "zstd_3" => Some(Compression::Zstd3),
            "zstd-9" | "zstd_9" => Some(Compression::Zstd9),
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
            Compression::Zstd9 => "zstd-9",
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

/// ZFS `redundant_metadata` setting.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RedundantMetadata {
    /// `all` — the ZFS default (full metadata redundancy).
    All,
    /// `most` — reduced metadata copies (`tank/models`: trades a little
    /// metadata redundancy for throughput on huge sequential weight files).
    Most,
}

impl RedundantMetadata {
    /// Parse a `zfs get redundant_metadata` value token.
    #[must_use]
    pub fn from_token(token: &str) -> Option<RedundantMetadata> {
        match token.trim().to_ascii_lowercase().as_str() {
            "all" => Some(RedundantMetadata::All),
            "most" => Some(RedundantMetadata::Most),
            _ => None,
        }
    }
    /// The ZFS token for this setting.
    #[must_use]
    pub const fn token(self) -> &'static str {
        match self {
            RedundantMetadata::All => "all",
            RedundantMetadata::Most => "most",
        }
    }
}

// ── datasets ────────────────────────────────────────────────────────

/// A dataset in the canonical `tank` hierarchy (profile §4.1).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Dataset {
    /// `tank/models` — LLM weight files.
    Models,
    /// `tank/context` — sovereignty/integrity-critical state fabric.
    Context,
    /// `tank/agents` — stateful local agent storage.
    Agents,
}

impl Dataset {
    /// All three canonical datasets.
    pub const ALL: [Dataset; 3] = [Dataset::Models, Dataset::Context, Dataset::Agents];

    /// The full ZFS dataset path under `tank`.
    #[must_use]
    pub const fn path(self) -> &'static str {
        match self {
            Dataset::Models => "tank/models",
            Dataset::Context => "tank/context",
            Dataset::Agents => "tank/agents",
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
    /// `copies` (ZFS default 1; `tank/context` = 2 for state-fabric durability).
    pub copies: u8,
    /// `redundant_metadata` (`tank/models` = most; others = all/default).
    pub redundant_metadata: RedundantMetadata,
}

/// Pool-level (`tank`) properties (E0660).
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

/// The canonical per-dataset specs, verbatim from `profiles/sain-01.yaml` §4.1.
#[must_use]
pub fn canonical_layout() -> [DatasetSpec; 3] {
    [
        // 100GB+ weight files: 1M record, lz4, reduced metadata for throughput.
        DatasetSpec {
            dataset: Dataset::Models,
            recordsize: 1024 * 1024,
            compression: Compression::Lz4,
            sync: Sync::Standard,
            copies: 1,
            redundant_metadata: RedundantMetadata::Most,
        },
        // State fabric: small record, max compression, 2 copies, synchronous.
        DatasetSpec {
            dataset: Dataset::Context,
            recordsize: 16 * 1024,
            compression: Compression::Zstd9,
            sync: Sync::Always,
            copies: 2,
            redundant_metadata: RedundantMetadata::All,
        },
        // Stateful agent storage: default record, zstd-3.
        DatasetSpec {
            dataset: Dataset::Agents,
            recordsize: 128 * 1024,
            compression: Compression::Zstd3,
            sync: Sync::Standard,
            copies: 1,
            redundant_metadata: RedundantMetadata::All,
        },
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
    /// Performance / efficiency drift (wrong recordsize, wrong compression) —
    /// wastes IO or space but does not risk data loss.
    Performance,
    /// Integrity-critical drift — `tank/context` losing `sync=always` (writes
    /// lost on power cut) or `copies=2` (no second copy to survive single-block
    /// corruption of the state fabric).
    Integrity,
}

/// One property that does not match the canon.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LayoutDrift {
    /// Which dataset.
    pub dataset: Dataset,
    /// Which property drifted.
    pub property: String,
    /// The canonical (expected) value, as a ZFS token.
    pub expected: String,
    /// The observed value, as a ZFS token.
    pub observed: String,
    /// How serious the drift is.
    pub severity: DriftSeverity,
}

/// Compare one observed dataset spec against its canon. Returns every property
/// that drifted (empty = matches the canon). On `tank/context`, a `sync`
/// regression off `always` or a `copies` value below the canonical 2 is
/// `Integrity`; everything else is `Performance`.
#[must_use]
pub fn validate_dataset(observed: &DatasetSpec) -> Vec<LayoutDrift> {
    let canon = canonical_spec(observed.dataset);
    let is_context = observed.dataset == Dataset::Context;
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
        let severity = if canon.sync == Sync::Always && is_context {
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
    if observed.copies != canon.copies {
        // Dropping below the canonical copies on the state fabric is a
        // durability gap (single-block corruption survivability).
        let severity = if is_context && observed.copies < canon.copies {
            DriftSeverity::Integrity
        } else {
            DriftSeverity::Performance
        };
        drift.push(LayoutDrift {
            dataset: observed.dataset,
            property: "copies".into(),
            expected: canon.copies.to_string(),
            observed: observed.copies.to_string(),
            severity,
        });
    }
    if observed.redundant_metadata != canon.redundant_metadata {
        drift.push(LayoutDrift {
            dataset: observed.dataset,
            property: "redundant_metadata".into(),
            expected: canon.redundant_metadata.token().into(),
            observed: observed.redundant_metadata.token().into(),
            severity: DriftSeverity::Performance,
        });
    }
    drift
}

/// Validate a whole observed layout. Returns all drift, integrity drift first.
#[must_use]
pub fn audit_layout(observed: &[DatasetSpec]) -> Vec<LayoutDrift> {
    let mut all: Vec<LayoutDrift> = observed.iter().flat_map(validate_dataset).collect();
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
        assert!(matches!(parse_recordsize("256"), Err(RecordSizeError::OutOfRange(_))));
        assert!(matches!(parse_recordsize("32M"), Err(RecordSizeError::OutOfRange(_))));
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
    fn canon_matches_profile_section_4_1() {
        // The three operator-verbatim datasets, exactly as profiles/sain-01.yaml
        // declares them (and tests/lint/test_zfs_datasets_verbatim.py pins).
        let models = canonical_spec(Dataset::Models);
        assert_eq!(models.recordsize, 1024 * 1024);
        assert_eq!(models.compression, Compression::Lz4);
        assert_eq!(models.redundant_metadata, RedundantMetadata::Most);

        let context = canonical_spec(Dataset::Context);
        assert_eq!(context.recordsize, 16 * 1024);
        assert_eq!(context.compression, Compression::Zstd9);
        assert_eq!(context.copies, 2);
        assert_eq!(context.sync, Sync::Always);

        let agents = canonical_spec(Dataset::Agents);
        assert_eq!(agents.recordsize, 128 * 1024);
        assert_eq!(agents.compression, Compression::Zstd3);
    }

    #[test]
    fn canon_validates_clean() {
        for spec in canonical_layout() {
            assert!(validate_dataset(&spec).is_empty(), "{:?} should match canon", spec.dataset);
        }
        assert!(audit_layout(&canonical_layout()).is_empty());
    }

    #[test]
    fn context_losing_sync_or_copies_is_integrity_critical() {
        let mut bad = canonical_spec(Dataset::Context);
        bad.sync = Sync::Standard;
        bad.copies = 1; // both regressions
        let drift = validate_dataset(&bad);
        assert_eq!(drift.len(), 2);
        for d in &drift {
            assert_eq!(d.severity, DriftSeverity::Integrity, "{}", d.property);
        }
    }

    #[test]
    fn models_compression_drift_is_performance() {
        let mut bad = canonical_spec(Dataset::Models);
        bad.compression = Compression::Zstd3; // the catalogue value — wrong vs profile
        let drift = validate_dataset(&bad);
        assert_eq!(drift.len(), 1);
        assert_eq!(drift[0].property, "compression");
        assert_eq!(drift[0].expected, "lz4");
        assert_eq!(drift[0].observed, "zstd-3");
        assert_eq!(drift[0].severity, DriftSeverity::Performance);
    }

    #[test]
    fn audit_sorts_integrity_before_performance() {
        let observed = vec![
            DatasetSpec {
                dataset: Dataset::Agents,
                recordsize: 16 * 1024, // perf drift
                compression: Compression::Zstd3,
                sync: Sync::Standard,
                copies: 1,
                redundant_metadata: RedundantMetadata::All,
            },
            DatasetSpec {
                dataset: Dataset::Context,
                recordsize: 16 * 1024,
                compression: Compression::Zstd9,
                sync: Sync::Standard, // integrity drift
                copies: 2,
                redundant_metadata: RedundantMetadata::All,
            },
        ];
        let drift = audit_layout(&observed);
        assert_eq!(drift[0].severity, DriftSeverity::Integrity, "worst first");
        assert_eq!(drift[0].dataset, Dataset::Context);
    }

    #[test]
    fn pool_canon() {
        let p = canonical_pool();
        assert_eq!(p.ashift, 12);
        assert_eq!(p.compression, Compression::Lz4);
        assert!(p.atime_off);
    }

    #[test]
    fn serde_kebab_tokens() {
        assert_eq!(serde_json::to_string(&Dataset::Context).unwrap(), "\"context\"");
        assert_eq!(serde_json::to_string(&Compression::Zstd9).unwrap(), "\"zstd-9\"");
        assert_eq!(serde_json::to_string(&RedundantMetadata::Most).unwrap(), "\"most\"");
        assert_eq!(serde_json::to_string(&Sync::Always).unwrap(), "\"always\"");
        assert_eq!(serde_json::to_string(&DriftSeverity::Integrity).unwrap(), "\"integrity\"");
    }
}
