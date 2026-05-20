//! `sovereign-cockpit-key-binding-display` — render a chord as a string.
//!
//! Renders `Chord { ctrl, alt, shift, meta, key }` with platform-
//! appropriate glyphs:
//!
//!   * Mac: `⌃ ⌥ ⇧ ⌘ key`
//!   * Linux/Windows: `Ctrl+Alt+Shift+Super+key`
//!
//! Special keys map to their conventional glyphs/strings:
//! Enter → `↩` / `Enter`, Backspace → `⌫` / `Backspace`, Escape →
//! `⎋` / `Esc`, Tab → `⇥` / `Tab`, ArrowLeft/Up/Right/Down →
//! arrows on both platforms.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Platform.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Platform {
    /// macOS.
    Mac,
    /// Linux.
    Linux,
    /// Windows.
    Windows,
}

/// Special key alias.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SpecialKey {
    /// Enter.
    Enter,
    /// Backspace.
    Backspace,
    /// Escape.
    Escape,
    /// Tab.
    Tab,
    /// Space.
    Space,
    /// Arrow up.
    ArrowUp,
    /// Arrow down.
    ArrowDown,
    /// Arrow left.
    ArrowLeft,
    /// Arrow right.
    ArrowRight,
}

/// Key payload — either a single non-modifier char or a special key.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Key {
    /// Character key (uppercase shown).
    Char {
        /// The char.
        ch: char,
    },
    /// Named special key.
    Special {
        /// Which one.
        which: SpecialKey,
    },
}

/// Chord (modifiers + key).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Chord {
    /// Ctrl.
    pub ctrl: bool,
    /// Alt / Option.
    pub alt: bool,
    /// Shift.
    pub shift: bool,
    /// Meta (Super on linux, Cmd on mac, Win on windows).
    pub meta: bool,
    /// Key payload.
    pub key: Key,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyBindingDisplay {
    /// Schema version.
    pub schema_version: String,
    /// Target platform.
    pub platform: Platform,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DisplayError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl KeyBindingDisplay {
    /// New.
    pub fn new(platform: Platform) -> Self {
        Self { schema_version: SCHEMA_VERSION.into(), platform }
    }

    /// Render.
    pub fn render(&self, c: &Chord) -> String {
        let sep = if self.platform == Platform::Mac { "" } else { "+" };
        let mut parts: Vec<String> = Vec::new();
        match self.platform {
            Platform::Mac => {
                // Mac convention order: Ctrl ⌃, Alt ⌥, Shift ⇧, Cmd ⌘.
                if c.ctrl { parts.push("⌃".into()); }
                if c.alt { parts.push("⌥".into()); }
                if c.shift { parts.push("⇧".into()); }
                if c.meta { parts.push("⌘".into()); }
            }
            _ => {
                if c.ctrl { parts.push("Ctrl".into()); }
                if c.alt { parts.push("Alt".into()); }
                if c.shift { parts.push("Shift".into()); }
                if c.meta { parts.push(if self.platform == Platform::Windows { "Win".into() } else { "Super".into() }); }
            }
        }
        parts.push(self.render_key(&c.key));
        parts.join(sep)
    }

    fn render_key(&self, k: &Key) -> String {
        match k {
            Key::Char { ch } => ch.to_ascii_uppercase().to_string(),
            Key::Special { which } => self.render_special(*which),
        }
    }

    fn render_special(&self, s: SpecialKey) -> String {
        match (self.platform, s) {
            (Platform::Mac, SpecialKey::Enter)      => "↩".into(),
            (Platform::Mac, SpecialKey::Backspace)  => "⌫".into(),
            (Platform::Mac, SpecialKey::Escape)     => "⎋".into(),
            (Platform::Mac, SpecialKey::Tab)        => "⇥".into(),
            (Platform::Mac, SpecialKey::Space)      => "␣".into(),
            (_, SpecialKey::Enter)      => "Enter".into(),
            (_, SpecialKey::Backspace)  => "Backspace".into(),
            (_, SpecialKey::Escape)     => "Esc".into(),
            (_, SpecialKey::Tab)        => "Tab".into(),
            (_, SpecialKey::Space)      => "Space".into(),
            (_, SpecialKey::ArrowUp)    => "↑".into(),
            (_, SpecialKey::ArrowDown)  => "↓".into(),
            (_, SpecialKey::ArrowLeft)  => "←".into(),
            (_, SpecialKey::ArrowRight) => "→".into(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DisplayError> {
        if self.schema_version != SCHEMA_VERSION { return Err(DisplayError::SchemaMismatch); }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn char_key(ch: char) -> Key { Key::Char { ch } }
    fn special(s: SpecialKey) -> Key { Key::Special { which: s } }

    #[test]
    fn mac_cmd_shift_p() {
        let d = KeyBindingDisplay::new(Platform::Mac);
        let c = Chord { ctrl: false, alt: false, shift: true, meta: true, key: char_key('p') };
        assert_eq!(d.render(&c), "⇧⌘P");
    }

    #[test]
    fn linux_ctrl_shift_p() {
        let d = KeyBindingDisplay::new(Platform::Linux);
        let c = Chord { ctrl: true, alt: false, shift: true, meta: false, key: char_key('p') };
        assert_eq!(d.render(&c), "Ctrl+Shift+P");
    }

    #[test]
    fn windows_super_renders_win() {
        let d = KeyBindingDisplay::new(Platform::Windows);
        let c = Chord { ctrl: false, alt: false, shift: false, meta: true, key: char_key('r') };
        assert_eq!(d.render(&c), "Win+R");
    }

    #[test]
    fn mac_enter_glyph() {
        let d = KeyBindingDisplay::new(Platform::Mac);
        let c = Chord { ctrl: false, alt: false, shift: false, meta: true, key: special(SpecialKey::Enter) };
        assert_eq!(d.render(&c), "⌘↩");
    }

    #[test]
    fn linux_arrows() {
        let d = KeyBindingDisplay::new(Platform::Linux);
        let c = Chord { ctrl: false, alt: true, shift: false, meta: false, key: special(SpecialKey::ArrowLeft) };
        assert_eq!(d.render(&c), "Alt+←");
    }

    #[test]
    fn mac_modifier_order_ctrl_alt_shift_cmd() {
        let d = KeyBindingDisplay::new(Platform::Mac);
        let c = Chord { ctrl: true, alt: true, shift: true, meta: true, key: char_key('k') };
        assert_eq!(d.render(&c), "⌃⌥⇧⌘K");
    }

    #[test]
    fn schema_drift_rejected() {
        let mut d = KeyBindingDisplay::new(Platform::Mac);
        d.schema_version = "9.9.9".into();
        assert!(matches!(d.validate().unwrap_err(), DisplayError::SchemaMismatch));
    }

    #[test]
    fn display_serde_roundtrip() {
        let d = KeyBindingDisplay::new(Platform::Linux);
        let j = serde_json::to_string(&d).unwrap();
        let back: KeyBindingDisplay = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
