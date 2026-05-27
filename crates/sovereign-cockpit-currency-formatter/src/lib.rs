//! `sovereign-cockpit-currency-formatter` — currency amount display.
//!
//! Spec{symbol, position SymbolPosition, decimals, group, sep}.
//! format(amount_minor) renders an i64 amount (in minor units;
//! e.g. cents) per the spec. Negative amounts get a leading "-".
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Symbol position.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum SymbolPosition {
    /// "$ 12.34"
    Prefix,
    /// "12.34 €"
    Suffix,
}

/// Spec.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CurrencySpec {
    /// Symbol (e.g. "$", "€").
    pub symbol: String,
    /// Position.
    pub position: SymbolPosition,
    /// Decimal places (0..=8).
    pub decimals: u8,
    /// Thousands group separator character.
    pub group: char,
    /// Decimal separator character.
    pub sep: char,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CurError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("symbol empty")]
    EmptySymbol,
    /// Bad decimals.
    #[error("decimals must be in 0..=8")]
    BadDecimals,
}

impl CurrencySpec {
    /// New.
    pub fn new(
        symbol: &str,
        position: SymbolPosition,
        decimals: u8,
        group: char,
        sep: char,
    ) -> Result<Self, CurError> {
        if symbol.is_empty() {
            return Err(CurError::EmptySymbol);
        }
        if decimals > 8 {
            return Err(CurError::BadDecimals);
        }
        Ok(Self {
            symbol: symbol.into(),
            position,
            decimals,
            group,
            sep,
        })
    }

    /// Format an amount in minor units.
    pub fn format(&self, amount_minor: i64) -> String {
        let negative = amount_minor < 0;
        let mut abs = (amount_minor.unsigned_abs()).to_string();
        // Pad to at least decimals+1 length (so leading zeros for tiny amounts).
        while abs.len() <= self.decimals as usize {
            abs.insert(0, '0');
        }
        let split_at = abs.len() - self.decimals as usize;
        let int_part = &abs[..split_at];
        let frac_part = &abs[split_at..];
        // Group the integer part from the right in groups of 3.
        let grouped = group_thousands(int_part, self.group);
        let mut body = grouped;
        if self.decimals > 0 {
            body.push(self.sep);
            body.push_str(frac_part);
        }
        let mut out = String::new();
        if negative {
            out.push('-');
        }
        match self.position {
            SymbolPosition::Prefix => {
                out.push_str(&self.symbol);
                out.push_str(&body);
            }
            SymbolPosition::Suffix => {
                out.push_str(&body);
                out.push(' ');
                out.push_str(&self.symbol);
            }
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CurError> {
        if self.symbol.is_empty() {
            return Err(CurError::EmptySymbol);
        }
        if self.decimals > 8 {
            return Err(CurError::BadDecimals);
        }
        Ok(())
    }
}

fn group_thousands(int: &str, sep: char) -> String {
    let bytes = int.as_bytes();
    let mut out = String::with_capacity(int.len() + int.len() / 3);
    let mut counter = 0;
    for i in (0..bytes.len()).rev() {
        if counter == 3 {
            out.push(sep);
            counter = 0;
        }
        out.push(bytes[i] as char);
        counter += 1;
    }
    out.chars().rev().collect()
}

/// Validate.
pub fn validate_schema_version(s: &str) -> Result<(), CurError> {
    if s != SCHEMA_VERSION {
        return Err(CurError::SchemaMismatch);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn usd_prefix_format() {
        let s = CurrencySpec::new("$", SymbolPosition::Prefix, 2, ',', '.').unwrap();
        assert_eq!(s.format(123456), "$1,234.56");
    }

    #[test]
    fn euro_suffix_format() {
        let s = CurrencySpec::new("€", SymbolPosition::Suffix, 2, '.', ',').unwrap();
        assert_eq!(s.format(1234567), "12.345,67 €");
    }

    #[test]
    fn jpy_no_decimals() {
        let s = CurrencySpec::new("¥", SymbolPosition::Prefix, 0, ',', '.').unwrap();
        assert_eq!(s.format(12345678), "¥12,345,678");
    }

    #[test]
    fn negative_amount() {
        let s = CurrencySpec::new("$", SymbolPosition::Prefix, 2, ',', '.').unwrap();
        assert_eq!(s.format(-12345), "-$123.45");
    }

    #[test]
    fn small_amount_pads_decimals() {
        let s = CurrencySpec::new("$", SymbolPosition::Prefix, 2, ',', '.').unwrap();
        assert_eq!(s.format(5), "$0.05");
    }

    #[test]
    fn empty_symbol_rejected() {
        assert!(matches!(
            CurrencySpec::new("", SymbolPosition::Prefix, 2, ',', '.').unwrap_err(),
            CurError::EmptySymbol
        ));
    }

    #[test]
    fn bad_decimals_rejected() {
        assert!(matches!(
            CurrencySpec::new("$", SymbolPosition::Prefix, 9, ',', '.').unwrap_err(),
            CurError::BadDecimals
        ));
    }

    #[test]
    fn schema_check() {
        assert!(validate_schema_version("1.0.0").is_ok());
        assert!(matches!(
            validate_schema_version("9.9.9").unwrap_err(),
            CurError::SchemaMismatch
        ));
    }

    #[test]
    fn currency_serde_roundtrip() {
        let s = CurrencySpec::new("$", SymbolPosition::Prefix, 2, ',', '.').unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: CurrencySpec = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
