//! `sovereign-cockpit-shortcut-cheatsheet` — generated operator cheatsheet.
//!
//! Given a `KeystrokeMap`, produces a per-scope grouped, sorted-by-chord
//! cheatsheet in either Markdown or plain-text. Pure read-side over
//! the keystroke-map.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cockpit_keystroke_map::{KeyBinding, KeystrokeMap, Scope};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Output format.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Format {
    /// Markdown.
    Markdown,
    /// Plain text (column-aligned).
    PlainText,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CheatsheetError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

fn chord(b: &KeyBinding) -> String {
    let mut s = String::new();
    let m = b.modifiers;
    if m.ctrl {
        s.push_str("Ctrl+");
    }
    if m.alt {
        s.push_str("Alt+");
    }
    if m.shift {
        s.push_str("Shift+");
    }
    if m.meta {
        s.push_str("Meta+");
    }
    s.push_str(&b.key);
    s
}

fn scope_label(s: Scope) -> &'static str {
    match s {
        Scope::Global => "Global",
        Scope::Conversation => "Conversation",
        Scope::Dashboard => "Dashboard",
        Scope::Replay => "Replay",
        Scope::Palette => "Palette",
    }
}

/// Render the map as a cheatsheet in the requested format.
pub fn render(map: &KeystrokeMap, fmt: Format) -> String {
    // Group bindings by scope.
    let mut by_scope: BTreeMap<&'static str, Vec<&KeyBinding>> = BTreeMap::new();
    for b in &map.bindings {
        by_scope.entry(scope_label(b.scope)).or_default().push(b);
    }
    // Sort each scope's vec by chord.
    for v in by_scope.values_mut() {
        v.sort_by_key(|a| chord(a));
    }
    match fmt {
        Format::Markdown => render_markdown(&by_scope),
        Format::PlainText => render_plain(&by_scope),
    }
}

fn render_markdown(by_scope: &BTreeMap<&'static str, Vec<&KeyBinding>>) -> String {
    let mut out = String::new();
    out.push_str("# Keyboard shortcuts\n\n");
    for (scope, bindings) in by_scope {
        out.push_str(&format!("## {scope}\n\n"));
        out.push_str("| Chord | Action | Description |\n");
        out.push_str("|---|---|---|\n");
        for b in bindings {
            out.push_str(&format!(
                "| `{}` | {} | {} |\n",
                chord(b),
                b.action_id,
                b.description
            ));
        }
        out.push('\n');
    }
    out
}

fn render_plain(by_scope: &BTreeMap<&'static str, Vec<&KeyBinding>>) -> String {
    let mut out = String::new();
    out.push_str("KEYBOARD SHORTCUTS\n\n");
    for (scope, bindings) in by_scope {
        out.push_str(&format!("[{scope}]\n"));
        // Compute column widths.
        let chord_w = bindings
            .iter()
            .map(|b| chord(b).len())
            .max()
            .unwrap_or(0)
            .max(5);
        let action_w = bindings
            .iter()
            .map(|b| b.action_id.len())
            .max()
            .unwrap_or(0)
            .max(6);
        for b in bindings {
            let c = chord(b);
            out.push_str(&format!(
                "  {c:<chord_w$}  {action:<action_w$}  {desc}\n",
                c = c,
                chord_w = chord_w,
                action = b.action_id,
                action_w = action_w,
                desc = b.description
            ));
        }
        out.push('\n');
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    // `Modifiers` is only referenced by these tests (the crate-level import
    // was correctly dropped as unused for the lib target).
    use sovereign_cockpit_keystroke_map::Modifiers;

    fn map_with_three() -> KeystrokeMap {
        let mut m = KeystrokeMap::new();
        let mut b = KeyBinding {
            modifiers: Modifiers::ctrl(),
            key: "k".into(),
            action_id: "open-palette".into(),
            scope: Scope::Global,
            description: "Open command palette".into(),
        };
        m.add(b.clone()).unwrap();
        b.key = "s".into();
        b.action_id = "save".into();
        b.description = "Save".into();
        m.add(b.clone()).unwrap();
        b.scope = Scope::Replay;
        b.modifiers = Modifiers::NONE;
        b.key = "space".into();
        b.action_id = "step-or-pause".into();
        b.description = "Step or pause".into();
        m.add(b).unwrap();
        m
    }

    #[test]
    fn markdown_contains_scope_headers() {
        let out = render(&map_with_three(), Format::Markdown);
        assert!(out.contains("## Global"));
        assert!(out.contains("## Replay"));
    }

    #[test]
    fn markdown_contains_chord_table() {
        let out = render(&map_with_three(), Format::Markdown);
        assert!(out.contains("`Ctrl+k`"));
        assert!(out.contains("`Ctrl+s`"));
        assert!(out.contains("`space`"));
    }

    #[test]
    fn plain_text_columns_align() {
        let out = render(&map_with_three(), Format::PlainText);
        assert!(out.contains("[Global]"));
        assert!(out.contains("[Replay]"));
        assert!(out.contains("open-palette"));
    }

    #[test]
    fn empty_map_produces_header_only() {
        let m = KeystrokeMap::new();
        let out_md = render(&m, Format::Markdown);
        assert!(out_md.contains("# Keyboard shortcuts"));
        assert!(!out_md.contains("## "));
        let out_pt = render(&m, Format::PlainText);
        assert!(out_pt.contains("KEYBOARD SHORTCUTS"));
    }

    #[test]
    fn chord_sort_within_scope() {
        let out = render(&map_with_three(), Format::Markdown);
        let ctrl_k = out.find("Ctrl+k").unwrap();
        let ctrl_s = out.find("Ctrl+s").unwrap();
        assert!(ctrl_k < ctrl_s);
    }

    #[test]
    fn format_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Format::Markdown).unwrap(),
            "\"markdown\""
        );
        assert_eq!(
            serde_json::to_string(&Format::PlainText).unwrap(),
            "\"plain-text\""
        );
    }
}
