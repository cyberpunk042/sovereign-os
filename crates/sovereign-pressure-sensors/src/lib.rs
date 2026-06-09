//! `sovereign-pressure-sensors` — M045 Pressure-As-Sensation 6-axis model.
//!
//! Per M045 + E0430 + M00759 + dump 13636-13660:
//!
//! Doctrine surface verbatim:
//!
//! > "PSI gives system pressure. DCGM gives GPU pressure. The runtime gives cost and attention pressure."
//!
//! 6 axes per E0430:
//!   1. CPU pressure (PSI cpu)
//!   2. Memory pressure (PSI memory)
//!   3. IO pressure (PSI io)
//!   4. GPU pressure (DCGM)
//!   5. Human-attention pressure (runtime)
//!   6. Cost pressure (runtime / cost ledger)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine verbatim per F03773 dump 13636 + dump 13658-13660.
pub const DOCTRINE_PRESSURE_AS_SENSATION: &str = "PSI gives system pressure. DCGM gives GPU pressure. The runtime gives cost and attention pressure.";

/// 6 pressure axes per E0430.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PressureAxis {
    /// CPU (PSI cpu).
    Cpu,
    /// Memory (PSI memory).
    Memory,
    /// IO (PSI io).
    Io,
    /// GPU (DCGM).
    Gpu,
    /// Human-attention (runtime queue depth + operator availability).
    HumanAttention,
    /// Cost (runtime + cost ledger).
    Cost,
}

impl PressureAxis {
    /// Canonical 1..6 position.
    pub fn position(self) -> u8 {
        match self {
            PressureAxis::Cpu => 1,
            PressureAxis::Memory => 2,
            PressureAxis::Io => 3,
            PressureAxis::Gpu => 4,
            PressureAxis::HumanAttention => 5,
            PressureAxis::Cost => 6,
        }
    }
    /// Source identifier (PSI / DCGM / runtime).
    pub fn source(self) -> &'static str {
        match self {
            PressureAxis::Cpu | PressureAxis::Memory | PressureAxis::Io => "psi",
            PressureAxis::Gpu => "dcgm",
            PressureAxis::HumanAttention | PressureAxis::Cost => "runtime",
        }
    }
}

/// One axis reading in normalised 0.0..=1.0 form.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct AxisReading {
    /// Axis.
    pub axis: PressureAxis,
    /// Normalised pressure 0.0..=1.0 (0=free, 1=overloaded).
    pub value: f32,
}

impl AxisReading {
    /// Construct one normalised axis reading.
    ///
    /// `value` is the normalised pressure 0.0..=1.0 a sensor reports for this
    /// axis (e.g. the Memory axis is fed by the host's PSI / `memory-pressure`
    /// probe). Out-of-range or non-finite values are caught by
    /// [`PressureSnapshot::validate`] / [`PressureSnapshot::update_axis`] at the
    /// boundary rather than here, so a bad reading surfaces as a typed error
    /// instead of being silently clamped.
    pub fn new(axis: PressureAxis, value: f32) -> Self {
        Self { axis, value }
    }
}

/// Full 6-axis snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PressureSnapshot {
    /// Schema version.
    pub schema_version: String,
    /// ISO-8601 UTC capture time.
    pub captured_at: String,
    /// 6 readings (MUST be exactly 6).
    pub readings: Vec<AxisReading>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PressureError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Reading value out of range.
    #[error("axis {axis:?} value {value} outside 0.0..=1.0")]
    ValueOutOfRange {
        /// Axis.
        axis: PressureAxis,
        /// Value.
        value: f32,
    },
    /// Wrong number of readings.
    #[error("readings count {0} != 6 canonical axes")]
    ReadingCountInvalid(usize),
    /// One axis missing from readings.
    #[error("required axis missing: {0:?}")]
    AxisMissing(PressureAxis),
    /// Duplicate axis.
    #[error("duplicate axis: {0:?}")]
    DuplicateAxis(PressureAxis),
    /// Doctrine tampered.
    #[error("doctrine tampered")]
    DoctrineTampered,
}

impl PressureSnapshot {
    /// Construct a free (all-zero) canonical snapshot.
    pub fn free_canonical() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: "2026-05-19T00:00:00Z".into(),
            readings: [
                PressureAxis::Cpu,
                PressureAxis::Memory,
                PressureAxis::Io,
                PressureAxis::Gpu,
                PressureAxis::HumanAttention,
                PressureAxis::Cost,
            ]
            .into_iter()
            .map(|a| AxisReading {
                axis: a,
                value: 0.0,
            })
            .collect(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PressureError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PressureError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.readings.len() != 6 {
            return Err(PressureError::ReadingCountInvalid(self.readings.len()));
        }
        for r in &self.readings {
            if !r.value.is_finite() || !(0.0..=1.0).contains(&r.value) {
                return Err(PressureError::ValueOutOfRange {
                    axis: r.axis,
                    value: r.value,
                });
            }
        }
        let required = [
            PressureAxis::Cpu,
            PressureAxis::Memory,
            PressureAxis::Io,
            PressureAxis::Gpu,
            PressureAxis::HumanAttention,
            PressureAxis::Cost,
        ];
        for a in required {
            if !self.readings.iter().any(|r| r.axis == a) {
                return Err(PressureError::AxisMissing(a));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<PressureAxis> = HashSet::new();
        for r in &self.readings {
            if !seen.insert(r.axis) {
                return Err(PressureError::DuplicateAxis(r.axis));
            }
        }
        Ok(())
    }

    /// Lookup reading by axis.
    pub fn reading_of(&self, axis: PressureAxis) -> Option<f32> {
        self.readings
            .iter()
            .find(|r| r.axis == axis)
            .map(|r| r.value)
    }

    /// Mean pressure across all 6 axes.
    pub fn mean(&self) -> f32 {
        if self.readings.is_empty() {
            return 0.0;
        }
        let total: f32 = self.readings.iter().map(|r| r.value).sum();
        total / self.readings.len() as f32
    }

    /// Max pressure across all 6 axes (worst signal).
    pub fn max(&self) -> Option<(PressureAxis, f32)> {
        let mut best: Option<(PressureAxis, f32)> = None;
        for r in &self.readings {
            best = Some(match best {
                None => (r.axis, r.value),
                Some((_a, v)) if r.value > v => (r.axis, r.value),
                Some(b) => b,
            });
        }
        best
    }

    /// Whether any axis is overloaded (≥ 0.9).
    pub fn any_overloaded(&self) -> bool {
        self.readings.iter().any(|r| r.value >= 0.9)
    }

    /// Assemble a snapshot from live sensor readings, enforcing the canonical
    /// invariants before returning.
    ///
    /// The live counterpart to [`Self::free_canonical`]: callers pass the
    /// capture time plus the six real axis readings sampled from the running
    /// system. Construction fails (rather than yielding a malformed snapshot)
    /// if the readings aren't exactly the six canonical axes, in range, with
    /// no duplicates — the same gate `validate()` enforces, applied at the
    /// boundary so an invalid snapshot can never reach a consumer.
    pub fn from_readings(
        captured_at: impl Into<String>,
        readings: Vec<AxisReading>,
    ) -> Result<Self, PressureError> {
        let snap = Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: captured_at.into(),
            readings,
        };
        snap.validate()?;
        Ok(snap)
    }

    /// Update one axis's live value in place, validating it first.
    ///
    /// Returns [`PressureError::ValueOutOfRange`] for a non-finite or
    /// out-of-`0.0..=1.0` value, or [`PressureError::AxisMissing`] if the axis
    /// is absent (impossible on a snapshot that has passed `validate()`).
    /// Because it only mutates an existing reading — never adds or removes one
    /// — the six-axis invariant is preserved across an unbounded sample stream.
    pub fn update_axis(&mut self, axis: PressureAxis, value: f32) -> Result<(), PressureError> {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(PressureError::ValueOutOfRange { axis, value });
        }
        let rec = self
            .readings
            .iter_mut()
            .find(|r| r.axis == axis)
            .ok_or(PressureError::AxisMissing(axis))?;
        rec.value = value;
        Ok(())
    }
}

/// Validate the doctrine constant.
pub fn assert_doctrine_intact(observed: &str) -> Result<(), PressureError> {
    if observed != DOCTRINE_PRESSURE_AS_SENSATION {
        return Err(PressureError::DoctrineTampered);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn free_canonical_validates() {
        PressureSnapshot::free_canonical().validate().unwrap();
    }

    #[test]
    fn six_axes_positioned_correctly() {
        for (a, p) in [
            (PressureAxis::Cpu, 1),
            (PressureAxis::Memory, 2),
            (PressureAxis::Io, 3),
            (PressureAxis::Gpu, 4),
            (PressureAxis::HumanAttention, 5),
            (PressureAxis::Cost, 6),
        ] {
            assert_eq!(a.position(), p);
        }
    }

    #[test]
    fn sources_match_doctrine() {
        assert_eq!(PressureAxis::Cpu.source(), "psi");
        assert_eq!(PressureAxis::Memory.source(), "psi");
        assert_eq!(PressureAxis::Io.source(), "psi");
        assert_eq!(PressureAxis::Gpu.source(), "dcgm");
        assert_eq!(PressureAxis::HumanAttention.source(), "runtime");
        assert_eq!(PressureAxis::Cost.source(), "runtime");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = PressureSnapshot::free_canonical();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            PressureError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn out_of_range_value_rejected() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings[0].value = 1.5;
        assert!(matches!(
            s.validate().unwrap_err(),
            PressureError::ValueOutOfRange { .. }
        ));
        s.readings[0].value = -0.1;
        assert!(matches!(
            s.validate().unwrap_err(),
            PressureError::ValueOutOfRange { .. }
        ));
        s.readings[0].value = f32::NAN;
        assert!(matches!(
            s.validate().unwrap_err(),
            PressureError::ValueOutOfRange { .. }
        ));
    }

    #[test]
    fn reading_count_invalid_rejected() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings.pop();
        assert!(matches!(
            s.validate().unwrap_err(),
            PressureError::ReadingCountInvalid(5)
        ));
    }

    #[test]
    fn missing_axis_caught_when_replaced() {
        let mut s = PressureSnapshot::free_canonical();
        // Replace CPU with duplicate Memory — count stays 6 but Cpu missing.
        s.readings[0] = AxisReading {
            axis: PressureAxis::Memory,
            value: 0.5,
        };
        let err = s.validate().unwrap_err();
        assert!(matches!(
            err,
            PressureError::AxisMissing(PressureAxis::Cpu)
                | PressureError::DuplicateAxis(PressureAxis::Memory)
        ));
    }

    #[test]
    fn reading_of_returns_value() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings[3].value = 0.85; // GPU
        assert_eq!(s.reading_of(PressureAxis::Gpu), Some(0.85));
        assert_eq!(s.reading_of(PressureAxis::Cpu), Some(0.0));
    }

    #[test]
    fn mean_across_axes() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings[0].value = 0.6;
        s.readings[1].value = 0.6;
        s.readings[2].value = 0.0;
        s.readings[3].value = 0.0;
        s.readings[4].value = 0.0;
        s.readings[5].value = 0.0;
        assert!((s.mean() - 0.2).abs() < 1e-6);
    }

    #[test]
    fn max_returns_worst_axis() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings[3].value = 0.95; // GPU spike
        s.readings[0].value = 0.5;
        let (axis, value) = s.max().unwrap();
        assert_eq!(axis, PressureAxis::Gpu);
        assert!((value - 0.95).abs() < 1e-6);
    }

    #[test]
    fn any_overloaded_detects_90() {
        let mut s = PressureSnapshot::free_canonical();
        s.readings[2].value = 0.91;
        assert!(s.any_overloaded());
        s.readings[2].value = 0.50;
        assert!(!s.any_overloaded());
    }

    #[test]
    fn doctrine_verbatim() {
        assert_doctrine_intact(DOCTRINE_PRESSURE_AS_SENSATION).unwrap();
        assert!(matches!(
            assert_doctrine_intact("WRONG").unwrap_err(),
            PressureError::DoctrineTampered
        ));
    }

    #[test]
    fn pressure_axis_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&PressureAxis::HumanAttention).unwrap(),
            "\"human-attention\""
        );
        assert_eq!(serde_json::to_string(&PressureAxis::Io).unwrap(), "\"io\"");
    }

    #[test]
    fn snapshot_serde_roundtrip() {
        let s = PressureSnapshot::free_canonical();
        let j = serde_json::to_string(&s).unwrap();
        let back: PressureSnapshot = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }

    // ---- live population / update API ----

    fn six_readings(v: f32) -> Vec<AxisReading> {
        [
            PressureAxis::Cpu,
            PressureAxis::Memory,
            PressureAxis::Io,
            PressureAxis::Gpu,
            PressureAxis::HumanAttention,
            PressureAxis::Cost,
        ]
        .into_iter()
        .map(|a| AxisReading::new(a, v))
        .collect()
    }

    #[test]
    fn from_readings_builds_validated_snapshot() {
        let s = PressureSnapshot::from_readings("2026-06-09T12:00:00Z", six_readings(0.5)).unwrap();
        assert_eq!(s.captured_at, "2026-06-09T12:00:00Z");
        assert!((s.mean() - 0.5).abs() < 1e-6);
        assert!(!s.any_overloaded());
    }

    #[test]
    fn from_readings_rejects_out_of_range() {
        let mut r = six_readings(0.1);
        r[1] = AxisReading::new(PressureAxis::Memory, 1.5); // PSI > 1.0
        assert!(matches!(
            PressureSnapshot::from_readings("t", r).unwrap_err(),
            PressureError::ValueOutOfRange {
                axis: PressureAxis::Memory,
                ..
            }
        ));
    }

    #[test]
    fn from_readings_rejects_wrong_count() {
        let mut r = six_readings(0.1);
        r.pop();
        assert!(matches!(
            PressureSnapshot::from_readings("t", r).unwrap_err(),
            PressureError::ReadingCountInvalid(5)
        ));
    }

    #[test]
    fn update_axis_validates_and_preserves_invariant() {
        let mut s = PressureSnapshot::free_canonical();
        // A live memory-pressure sample lands on the Memory axis.
        s.update_axis(PressureAxis::Memory, 0.95).unwrap();
        assert_eq!(s.reading_of(PressureAxis::Memory), Some(0.95));
        assert!(s.any_overloaded());
        assert_eq!(s.max(), Some((PressureAxis::Memory, 0.95)));
        // Invariant survives the live update.
        s.validate().unwrap();
        // Out-of-range and non-finite are rejected, leaving state untouched.
        assert!(s.update_axis(PressureAxis::Cpu, 2.0).is_err());
        assert!(s.update_axis(PressureAxis::Cpu, f32::NAN).is_err());
        assert_eq!(s.reading_of(PressureAxis::Cpu), Some(0.0));
    }
}
