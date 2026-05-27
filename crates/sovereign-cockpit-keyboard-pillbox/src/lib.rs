//! `sovereign-cockpit-keyboard-pillbox` — chord parser + pill renderer.
//!
//! Parses chord strings into ordered Pill tokens with OS-specific
//! display symbols. Order: Ctrl, Alt/Option, Shift, Cmd/Meta, key.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Target OS for symbol resolution.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum OsTarget {
    /// macOS.
    Mac,
    /// Linux.
    Linux,
    /// Windows.
    Windows,
}

/// Pill (one rendered chip).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pill {
    /// Display label (already OS-resolved).
    pub label: String,
    /// Is this the leaf key (vs a modifier)?
    pub is_key: bool,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PillboxError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty chord.
    #[error("chord empty")]
    EmptyChord,
    /// Missing leaf key.
    #[error("chord {0:?} has no leaf key")]
    NoKey(String),
}

/// Result envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pillbox {
    /// Schema version.
    pub schema_version: String,
    /// Pills in render order.
    pub pills: Vec<Pill>,
}

/// Parser.
#[derive(Debug, Clone, Default)]
pub struct KeyboardPillbox;

impl KeyboardPillbox {
    /// Parse chord (case-insensitive, separator '+' or '-').
    pub fn parse(chord: &str, os: OsTarget) -> Result<Pillbox, PillboxError> {
        let raw = chord.trim();
        if raw.is_empty() {
            return Err(PillboxError::EmptyChord);
        }
        let parts: Vec<&str> = raw
            .split(['+', '-'])
            .map(|s| s.trim())
            .filter(|s| !s.is_empty())
            .collect();
        let mut ctrl = false;
        let mut alt = false;
        let mut shift = false;
        let mut meta = false;
        let mut key: Option<String> = None;
        for p in &parts {
            let lower = p.to_ascii_lowercase();
            match lower.as_str() {
                "ctrl" | "control" => ctrl = true,
                "alt" | "option" | "opt" => alt = true,
                "shift" => shift = true,
                "cmd" | "command" | "meta" | "win" | "super" => meta = true,
                _ => {
                    // Leaf key (only one allowed; last wins).
                    key = Some((*p).to_string());
                }
            }
        }
        let key = key.ok_or_else(|| PillboxError::NoKey(chord.into()))?;
        let mut pills: Vec<Pill> = Vec::new();
        if ctrl {
            pills.push(Pill {
                label: match os {
                    OsTarget::Mac => "⌃".into(),
                    _ => "Ctrl".into(),
                },
                is_key: false,
            });
        }
        if alt {
            pills.push(Pill {
                label: match os {
                    OsTarget::Mac => "⌥".into(),
                    _ => "Alt".into(),
                },
                is_key: false,
            });
        }
        if shift {
            pills.push(Pill {
                label: match os {
                    OsTarget::Mac => "⇧".into(),
                    _ => "Shift".into(),
                },
                is_key: false,
            });
        }
        if meta {
            pills.push(Pill {
                label: match os {
                    OsTarget::Mac => "⌘".into(),
                    OsTarget::Linux => "Super".into(),
                    OsTarget::Windows => "Win".into(),
                },
                is_key: false,
            });
        }
        let key_lc = key.to_ascii_lowercase();
        let key_display = match key_lc.as_str() {
            "escape" | "esc" => "Esc".to_string(),
            "enter" | "return" => "Enter".to_string(),
            "tab" => "Tab".to_string(),
            "backspace" | "bs" => "Backspace".to_string(),
            "space" | "spc" => "Space".to_string(),
            "delete" | "del" => "Del".to_string(),
            "up" | "down" | "left" | "right" => {
                let arrows = match key_lc.as_str() {
                    "up" => "↑",
                    "down" => "↓",
                    "left" => "←",
                    "right" => "→",
                    _ => unreachable!(),
                };
                arrows.to_string()
            }
            _ => {
                if key.chars().count() == 1 {
                    key.to_uppercase()
                } else {
                    let mut s = key.clone();
                    if let Some(first) = s.get_mut(0..1) {
                        first.make_ascii_uppercase();
                    }
                    s
                }
            }
        };
        pills.push(Pill {
            label: key_display,
            is_key: true,
        });
        Ok(Pillbox {
            schema_version: SCHEMA_VERSION.into(),
            pills,
        })
    }
}

impl Pillbox {
    /// Validate.
    pub fn validate(&self) -> Result<(), PillboxError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PillboxError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_chord_rejected() {
        assert!(matches!(
            KeyboardPillbox::parse("", OsTarget::Linux).unwrap_err(),
            PillboxError::EmptyChord
        ));
    }

    #[test]
    fn no_leaf_key_rejected() {
        assert!(matches!(
            KeyboardPillbox::parse("Ctrl+Shift", OsTarget::Linux).unwrap_err(),
            PillboxError::NoKey(_)
        ));
    }

    #[test]
    fn linux_uses_spelled_modifiers() {
        let p = KeyboardPillbox::parse("Ctrl+Shift+K", OsTarget::Linux).unwrap();
        let labels: Vec<&str> = p.pills.iter().map(|p| p.label.as_str()).collect();
        assert_eq!(labels, vec!["Ctrl", "Shift", "K"]);
    }

    #[test]
    fn mac_uses_symbols() {
        let p = KeyboardPillbox::parse("Cmd+Shift+K", OsTarget::Mac).unwrap();
        let labels: Vec<&str> = p.pills.iter().map(|p| p.label.as_str()).collect();
        assert_eq!(labels, vec!["⇧", "⌘", "K"]);
    }

    #[test]
    fn meta_windows_label() {
        let p = KeyboardPillbox::parse("Super+L", OsTarget::Windows).unwrap();
        assert_eq!(p.pills[0].label, "Win");
    }

    #[test]
    fn esc_normalized() {
        let p = KeyboardPillbox::parse("esc", OsTarget::Linux).unwrap();
        assert_eq!(p.pills[0].label, "Esc");
    }

    #[test]
    fn arrow_keys_glyph() {
        let p = KeyboardPillbox::parse("up", OsTarget::Linux).unwrap();
        assert_eq!(p.pills[0].label, "↑");
    }

    #[test]
    fn modifier_order_stable() {
        // Even if input order differs, output is Ctrl, Alt, Shift, Meta, key.
        let p = KeyboardPillbox::parse("Cmd+Ctrl+Alt+Shift+K", OsTarget::Mac).unwrap();
        let labels: Vec<&str> = p.pills.iter().map(|p| p.label.as_str()).collect();
        assert_eq!(labels, vec!["⌃", "⌥", "⇧", "⌘", "K"]);
    }

    #[test]
    fn slash_separator_also_works() {
        // Even with weird chars, Cmd+/ should yield 2 pills.
        let p = KeyboardPillbox::parse("Cmd+/", OsTarget::Mac).unwrap();
        assert_eq!(p.pills.len(), 2);
        assert_eq!(p.pills[1].label, "/");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = KeyboardPillbox::parse("K", OsTarget::Linux).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PillboxError::SchemaMismatch
        ));
    }

    #[test]
    fn pillbox_serde_roundtrip() {
        let p = KeyboardPillbox::parse("Ctrl+K", OsTarget::Linux).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Pillbox = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
