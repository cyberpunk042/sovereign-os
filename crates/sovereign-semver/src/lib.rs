//! `sovereign-semver` — semantic-version parsing, ordering, and `^`-compatibility.
//!
//! Every crate in this workspace carries a `SCHEMA_VERSION` string. To gate one
//! component against another — "does the model I loaded satisfy what the runtime
//! requires?" — those strings have to be *compared by meaning*, not by bytes:
//! `1.10.0` is newer than `1.9.0` even though it sorts earlier lexically, and a
//! `1.0.0-alpha` prerelease is *older* than the `1.0.0` it precedes. This crate
//! implements the [SemVer 2.0.0] precedence rules so the schema versions can be
//! ordered and range-checked.
//!
//! A [`Version`] is `MAJOR.MINOR.PATCH` with an optional `-prerelease` and an
//! optional `+build` (parsed and discarded — build metadata does not affect
//! precedence). [`Version::parse`] is strict: each of the three numeric fields
//! must be present and a valid integer, or you get a typed [`SemverError`].
//!
//! Ordering follows SemVer precedence exactly: compare major, then minor, then
//! patch numerically; if all equal, a version *with* a prerelease ranks **below**
//! one without, and two prereleases compare identifier-by-identifier (numeric
//! identifiers numerically, alphanumeric ones lexically, numeric below
//! alphanumeric).
//!
//! Compatibility uses the Cargo/npm caret rule: `^required` admits any version
//! `>= required` that does not change the left-most non-zero component — so for
//! `^1.2.0` any `1.x.y >= 1.2.0` satisfies, for `^0.2.3` any `0.2.y >= 0.2.3`,
//! and for `^0.0.3` only `0.0.3` exactly.
//!
//! [SemVer 2.0.0]: https://semver.org/
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::fmt;
use thiserror::Error;

/// Schema version of the semver surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors from parsing a version string.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum SemverError {
    /// The version did not have the three `MAJOR.MINOR.PATCH` components.
    #[error("expected MAJOR.MINOR.PATCH, got '{0}'")]
    Shape(String),
    /// One of the numeric components was not a valid non-negative integer.
    #[error("invalid {field} number '{value}'")]
    Number {
        /// Which component failed (`major` / `minor` / `patch`).
        field: &'static str,
        /// The offending text.
        value: String,
    },
    /// A prerelease identifier was empty (e.g. `1.0.0-` or `1.0.0-a..b`).
    #[error("empty prerelease identifier in '{0}'")]
    EmptyPrerelease(String),
}

/// A parsed semantic version: `MAJOR.MINOR.PATCH` with optional prerelease.
///
/// Build metadata (`+...`) is accepted by the parser but not stored, because it
/// has no bearing on precedence.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Version {
    /// Major version — incremented for incompatible changes.
    pub major: u64,
    /// Minor version — incremented for backward-compatible additions.
    pub minor: u64,
    /// Patch version — incremented for backward-compatible fixes.
    pub patch: u64,
    /// Dot-separated prerelease identifiers (empty for a normal release).
    pub prerelease: Vec<String>,
}

impl Version {
    /// A release version with no prerelease.
    pub fn new(major: u64, minor: u64, patch: u64) -> Self {
        Self {
            major,
            minor,
            patch,
            prerelease: Vec::new(),
        }
    }

    /// Parse a `MAJOR.MINOR.PATCH[-prerelease][+build]` string.
    pub fn parse(s: &str) -> Result<Self, SemverError> {
        let s = s.trim();
        // Strip build metadata: everything from the first '+' is ignored.
        let without_build = match s.split_once('+') {
            Some((head, _build)) => head,
            None => s,
        };
        // Split off the prerelease at the first '-'.
        let (core, pre) = match without_build.split_once('-') {
            Some((core, pre)) => (core, Some(pre)),
            None => (without_build, None),
        };

        let mut parts = core.split('.');
        let major = parts.next();
        let minor = parts.next();
        let patch = parts.next();
        let (major, minor, patch) = match (major, minor, patch, parts.next()) {
            (Some(a), Some(b), Some(c), None) => (a, b, c),
            _ => return Err(SemverError::Shape(s.to_string())),
        };

        let major = parse_num(major, "major")?;
        let minor = parse_num(minor, "minor")?;
        let patch = parse_num(patch, "patch")?;

        let prerelease = match pre {
            None => Vec::new(),
            Some(pre) => {
                let mut ids = Vec::new();
                for id in pre.split('.') {
                    if id.is_empty() {
                        return Err(SemverError::EmptyPrerelease(s.to_string()));
                    }
                    ids.push(id.to_string());
                }
                ids
            }
        };

        Ok(Self {
            major,
            minor,
            patch,
            prerelease,
        })
    }

    /// Whether this is a prerelease (`true`) or a normal release (`false`).
    pub fn is_prerelease(&self) -> bool {
        !self.prerelease.is_empty()
    }

    /// Whether `self` satisfies the caret requirement `^required`.
    ///
    /// `self` must be `>= required` and must not change `required`'s left-most
    /// non-zero component. This is the default compatibility rule used by Cargo.
    pub fn satisfies_caret(&self, required: &Version) -> bool {
        if self < required {
            return false;
        }
        if required.major > 0 {
            self.major == required.major
        } else if required.minor > 0 {
            self.major == 0 && self.minor == required.minor
        } else {
            self.major == 0 && self.minor == 0 && self.patch == required.patch
        }
    }
}

fn parse_num(s: &str, field: &'static str) -> Result<u64, SemverError> {
    // Reject leading '+' / whitespace / signs that u64::from_str would or
    // wouldn't accept inconsistently; SemVer numerics are plain digits.
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return Err(SemverError::Number {
            field,
            value: s.to_string(),
        });
    }
    s.parse::<u64>().map_err(|_| SemverError::Number {
        field,
        value: s.to_string(),
    })
}

impl fmt::Display for Version {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)?;
        if !self.prerelease.is_empty() {
            write!(f, "-{}", self.prerelease.join("."))?;
        }
        Ok(())
    }
}

impl PartialOrd for Version {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Version {
    fn cmp(&self, other: &Self) -> Ordering {
        self.major
            .cmp(&other.major)
            .then(self.minor.cmp(&other.minor))
            .then(self.patch.cmp(&other.patch))
            .then_with(|| cmp_prerelease(&self.prerelease, &other.prerelease))
    }
}

/// Compare prerelease identifier lists per SemVer §11.
///
/// A version with no prerelease ranks *above* one with a prerelease. Otherwise
/// compare identifier by identifier: numeric identifiers compare numerically and
/// rank below alphanumeric ones; a shorter run of identifiers ranks below a
/// longer one when all preceding are equal.
fn cmp_prerelease(a: &[String], b: &[String]) -> Ordering {
    match (a.is_empty(), b.is_empty()) {
        (true, true) => return Ordering::Equal,
        (true, false) => return Ordering::Greater, // release > prerelease
        (false, true) => return Ordering::Less,
        (false, false) => {}
    }
    for (x, y) in a.iter().zip(b.iter()) {
        let ord = cmp_identifier(x, y);
        if ord != Ordering::Equal {
            return ord;
        }
    }
    a.len().cmp(&b.len())
}

fn cmp_identifier(x: &str, y: &str) -> Ordering {
    let xn = x.bytes().all(|b| b.is_ascii_digit());
    let yn = y.bytes().all(|b| b.is_ascii_digit());
    match (xn, yn) {
        (true, true) => {
            // Both numeric: compare as numbers (identifiers can be large, but
            // SemVer forbids leading zeros; parse defensively as u128).
            let xv = x.parse::<u128>().unwrap_or(0);
            let yv = y.parse::<u128>().unwrap_or(0);
            xv.cmp(&yv)
        }
        (true, false) => Ordering::Less,    // numeric < alphanumeric
        (false, true) => Ordering::Greater, // alphanumeric > numeric
        (false, false) => x.cmp(y),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_plain_release() {
        let v = Version::parse("1.2.3").unwrap();
        assert_eq!(v, Version::new(1, 2, 3));
        assert!(!v.is_prerelease());
    }

    #[test]
    fn parses_prerelease_and_ignores_build() {
        let v = Version::parse("1.0.0-alpha.1+build.99").unwrap();
        assert_eq!(v.major, 1);
        assert_eq!(v.prerelease, vec!["alpha".to_string(), "1".to_string()]);
        assert!(v.is_prerelease());
        // build metadata is discarded, not part of equality
        assert_eq!(v, Version::parse("1.0.0-alpha.1+other").unwrap());
    }

    #[test]
    fn rejects_malformed_versions() {
        assert!(matches!(Version::parse("1.2"), Err(SemverError::Shape(_))));
        assert!(matches!(
            Version::parse("1.2.3.4"),
            Err(SemverError::Shape(_))
        ));
        assert!(matches!(
            Version::parse("1.x.0"),
            Err(SemverError::Number { field: "minor", .. })
        ));
        assert!(matches!(
            Version::parse("1.0.0-"),
            Err(SemverError::EmptyPrerelease(_))
        ));
    }

    #[test]
    fn orders_by_numeric_precedence_not_lexically() {
        // 1.9.0 < 1.10.0 even though "1.10" sorts before "1.9" as text
        assert!(Version::parse("1.9.0").unwrap() < Version::parse("1.10.0").unwrap());
        assert!(Version::parse("1.2.3").unwrap() < Version::parse("1.3.0").unwrap());
        assert!(Version::parse("1.3.0").unwrap() < Version::parse("2.0.0").unwrap());
    }

    #[test]
    fn prerelease_ranks_below_its_release() {
        assert!(Version::parse("1.0.0-alpha").unwrap() < Version::parse("1.0.0").unwrap());
        // SemVer §11 example chain
        let chain = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ];
        for w in chain.windows(2) {
            let lo = Version::parse(w[0]).unwrap();
            let hi = Version::parse(w[1]).unwrap();
            assert!(lo < hi, "{} should be < {}", w[0], w[1]);
        }
    }

    #[test]
    fn numeric_prerelease_id_below_alphanumeric() {
        // 1.0.0-1 < 1.0.0-alpha (numeric identifiers have lower precedence)
        assert!(Version::parse("1.0.0-1").unwrap() < Version::parse("1.0.0-alpha").unwrap());
        // and 1.0.0-alpha.1 < 1.0.0-alpha.2 numerically
        assert!(
            Version::parse("1.0.0-alpha.1").unwrap() < Version::parse("1.0.0-alpha.2").unwrap()
        );
    }

    #[test]
    fn caret_for_major_at_least_one() {
        let req = Version::parse("1.2.0").unwrap();
        assert!(Version::parse("1.2.0").unwrap().satisfies_caret(&req));
        assert!(Version::parse("1.5.7").unwrap().satisfies_caret(&req));
        assert!(!Version::parse("1.1.9").unwrap().satisfies_caret(&req)); // below
        assert!(!Version::parse("2.0.0").unwrap().satisfies_caret(&req)); // major bump
    }

    #[test]
    fn caret_for_zero_major() {
        // ^0.2.3 admits 0.2.y >= 0.2.3 but not 0.3.0
        let req = Version::parse("0.2.3").unwrap();
        assert!(Version::parse("0.2.3").unwrap().satisfies_caret(&req));
        assert!(Version::parse("0.2.9").unwrap().satisfies_caret(&req));
        assert!(!Version::parse("0.2.2").unwrap().satisfies_caret(&req));
        assert!(!Version::parse("0.3.0").unwrap().satisfies_caret(&req));
    }

    #[test]
    fn caret_for_zero_minor() {
        // ^0.0.3 is exact
        let req = Version::parse("0.0.3").unwrap();
        assert!(Version::parse("0.0.3").unwrap().satisfies_caret(&req));
        assert!(!Version::parse("0.0.4").unwrap().satisfies_caret(&req));
        assert!(!Version::parse("0.1.0").unwrap().satisfies_caret(&req));
    }

    #[test]
    fn display_round_trips_through_parse() {
        for s in ["0.0.0", "1.2.3", "10.20.30", "1.0.0-rc.1"] {
            let v = Version::parse(s).unwrap();
            assert_eq!(v.to_string(), s);
            assert_eq!(Version::parse(&v.to_string()).unwrap(), v);
        }
    }

    #[test]
    fn serde_round_trip() {
        let v = Version::parse("3.4.5-beta.2").unwrap();
        let j = serde_json::to_string(&v).unwrap();
        let back: Version = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }

    #[test]
    fn schema_version_is_parseable() {
        // dogfooding: our own SCHEMA_VERSION must be a valid semver
        assert_eq!(
            Version::parse(SCHEMA_VERSION).unwrap(),
            Version::new(1, 0, 0)
        );
    }
}
