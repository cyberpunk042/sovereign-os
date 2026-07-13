//! `sovereign-dashboard-layout` CLI — the runnable end of the widget-grid model.
//!
//! The library models a per-dashboard 12-column widget grid: each dashboard slot
//! (D-NN) declares an ordered list of widgets (x / y / w / h / kind / binding) and
//! a `validate()` that rejects zero-dimension, out-of-bounds, empty-binding, and
//! overlapping widgets. But nothing *ran* it, so "is this layout JSON sound?" was
//! unanswerable at the command line. This binary is that runnable end.
//!
//! Modes:
//!   * default (no args) — print the 12-column grid model and the 8 canonical
//!     widget kinds (name + description) as a human-readable reference.
//!   * `--check FILE` — load a `DashboardLayout` object OR a `LayoutManifest`
//!     envelope from JSON, run `validate()` (a manifest is validated against the
//!     canonical dashboard-coverage slots), report OK / the `LayoutError`, and
//!     exit non-zero on read/parse error or any validation failure.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_dashboard_coverage::CoverageManifest;
use sovereign_dashboard_layout::{DashboardLayout, GRID_COLS, LayoutManifest, WidgetKind};

/// Every widget kind, in canonical order. Exhaustive by construction: adding a
/// variant to `WidgetKind` without listing it here breaks the `kind_label`
/// match below, so this array can never silently fall out of date.
const ALL_KINDS: [WidgetKind; 8] = [
    WidgetKind::LineChart,
    WidgetKind::KpiTile,
    WidgetKind::Status,
    WidgetKind::LogFeed,
    WidgetKind::Table,
    WidgetKind::Text,
    WidgetKind::ActionRow,
    WidgetKind::Heatmap,
];

/// The stable kebab-case label for a widget kind — identical to how `WidgetKind`
/// serializes to JSON (kept honest by the `kind_label_matches_serde` test).
fn kind_label(kind: WidgetKind) -> &'static str {
    match kind {
        WidgetKind::LineChart => "line-chart",
        WidgetKind::KpiTile => "kpi-tile",
        WidgetKind::Status => "status",
        WidgetKind::LogFeed => "log-feed",
        WidgetKind::Table => "table",
        WidgetKind::Text => "text",
        WidgetKind::ActionRow => "action-row",
        WidgetKind::Heatmap => "heatmap",
    }
}

/// A one-line human description of what each widget kind renders.
fn kind_description(kind: WidgetKind) -> &'static str {
    match kind {
        WidgetKind::LineChart => "time-series line chart",
        WidgetKind::KpiTile => "numeric KPI tile",
        WidgetKind::Status => "status indicator (color-coded)",
        WidgetKind::LogFeed => "log feed (auto-scrolling)",
        WidgetKind::Table => "table with rows",
        WidgetKind::Text => "free-form text panel",
        WidgetKind::ActionRow => "action button row",
        WidgetKind::Heatmap => "2D heatmap",
    }
}

/// The human-readable reference: the grid model plus the 8 widget kinds.
fn reference_text() -> String {
    let mut s = String::new();
    s.push_str("The dashboard widget-grid model (sovereign-dashboard-layout)\n\n");
    s.push_str(&format!(
        "Each dashboard slot (D-NN) declares an ordered list of widgets. The grid width is\n\
         fixed at {GRID_COLS} columns; rows are unbounded. Every widget has an origin (x, y),\n\
         a size (w, h) in cells, a kind, and a non-empty binding.\n\n"
    ));
    s.push_str(&format!(
        "validate() rejects a layout when a widget has a zero dimension (w == 0 or h == 0),\n\
         runs off the right edge (x + w > {GRID_COLS}), carries an empty binding, or overlaps\n\
         another widget.\n\n"
    ));
    s.push_str(&format!("The {} widget kinds:\n", ALL_KINDS.len()));
    for (i, kind) in ALL_KINDS.into_iter().enumerate() {
        s.push_str(&format!(
            "  {}. {:<12} {}\n",
            i + 1,
            kind_label(kind),
            kind_description(kind),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-dashboard-layout — per-dashboard 12-column widget-grid layouts\n\n\
     Each dashboard slot (D-NN) declares widgets (x/y/w/h/kind/binding) on a\n\
     12-column grid; validate() detects zero dimensions, out-of-bounds widgets,\n\
     empty bindings, and overlaps.\n\n\
     USAGE:\n\
     \x20   sovereign-dashboard-layout                print the grid model + 8 widget kinds\n\
     \x20   sovereign-dashboard-layout --check FILE   validate a layout/manifest from JSON\n\
     \x20   sovereign-dashboard-layout --help         print this help and exit\n\n\
     --check FILE loads either a single DashboardLayout object or a LayoutManifest\n\
     envelope. A manifest is validated against the canonical dashboard-coverage\n\
     slots (schema, unknown/duplicate slots, and every layout's grid); a bare\n\
     layout is checked for its grid invariants only. Exits non-zero on failure.\n"
        .to_string()
}

/// Which shape `--check` found in the file.
enum Input {
    /// A bare `DashboardLayout` object.
    Layout(DashboardLayout),
    /// A `LayoutManifest` envelope (schema_version + layouts).
    Manifest(LayoutManifest),
}

/// Accept either a single `DashboardLayout` or a `LayoutManifest`. The two shapes
/// are disjoint by required fields (`slot`/`widgets` vs `schema_version`/`layouts`);
/// we discriminate on the envelope keys so a malformed input reports against the
/// shape it most resembles rather than a misleading fallback error.
fn parse_input(json: &str) -> Result<Input, serde_json::Error> {
    let value: serde_json::Value = serde_json::from_str(json)?;
    if value.get("layouts").is_some() || value.get("schema_version").is_some() {
        serde_json::from_str::<LayoutManifest>(json).map(Input::Manifest)
    } else {
        serde_json::from_str::<DashboardLayout>(json).map(Input::Layout)
    }
}

/// Validate a single dashboard layout's grid invariants and print a report.
fn check_layout(layout: &DashboardLayout) -> ExitCode {
    println!(
        "DashboardLayout {} — {} widget(s), {} cell(s) used",
        layout.slot,
        layout.widgets.len(),
        layout.cells_used(),
    );
    match layout.validate() {
        Ok(()) => {
            println!("OK   layout {} valid (grid invariants)", layout.slot);
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL layout {} — {err}", layout.slot);
            ExitCode::FAILURE
        }
    }
}

/// Validate a full manifest against the canonical dashboard-coverage slots and
/// print a per-slot report.
fn check_manifest(manifest: &LayoutManifest) -> ExitCode {
    let coverage = CoverageManifest::canonical();
    let widgets: usize = manifest.layouts.iter().map(|l| l.widgets.len()).sum();
    let cells: u32 = manifest
        .layouts
        .iter()
        .map(DashboardLayout::cells_used)
        .sum();
    println!(
        "LayoutManifest (schema {}) — {} layout(s), {} widget(s), {} cell(s) used",
        manifest.schema_version,
        manifest.layouts.len(),
        widgets,
        cells,
    );
    for l in &manifest.layouts {
        println!(
            "  {:<6} {} widget(s)  {} cell(s)",
            l.slot,
            l.widgets.len(),
            l.cells_used(),
        );
    }
    match manifest.validate(&coverage) {
        Ok(()) => {
            println!(
                "OK   manifest valid against canonical coverage ({} slots)",
                coverage.entries.len()
            );
            ExitCode::SUCCESS
        }
        Err(err) => {
            println!("FAIL manifest — {err}");
            ExitCode::FAILURE
        }
    }
}

/// `--check FILE`: read the file, discriminate the JSON shape, validate, print a
/// report, and return a process exit code (non-zero on read/parse/validation
/// error).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    match parse_input(&json) {
        Ok(Input::Layout(layout)) => check_layout(&layout),
        Ok(Input::Manifest(manifest)) => check_manifest(&manifest),
        Err(e) => {
            eprintln!("error: {path} is not a DashboardLayout or LayoutManifest: {e}");
            ExitCode::FAILURE
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_dashboard_layout::LayoutError;

    const VALID_LAYOUT: &str = r#"{"slot":"D-00","widgets":[
        {"x":0,"y":0,"w":6,"h":4,"kind":"line-chart","binding":"cpu.load"},
        {"x":6,"y":0,"w":6,"h":4,"kind":"heatmap","binding":"gpu.util"}
    ]}"#;

    #[test]
    fn reference_lists_all_eight_kinds() {
        let t = reference_text();
        for k in ALL_KINDS {
            assert!(t.contains(kind_label(k)), "reference missing {k:?}:\n{t}");
            assert!(
                t.contains(kind_description(k)),
                "reference missing description for {k:?}:\n{t}"
            );
        }
        // Exactly eight numbered "  N. " entries — one per widget kind, no more.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(numbered, ALL_KINDS.len(), "expected 8 widget-kind lines");
    }

    #[test]
    fn kind_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for k in ALL_KINDS {
            let json = serde_json::to_string(&k).unwrap();
            assert_eq!(json, format!("\"{}\"", kind_label(k)));
        }
    }

    #[test]
    fn check_accepts_valid_layout() {
        let Input::Layout(l) = parse_input(VALID_LAYOUT).unwrap() else {
            panic!("expected a bare DashboardLayout");
        };
        assert_eq!(l.slot, "D-00");
        assert_eq!(l.widgets.len(), 2);
        assert_eq!(l.cells_used(), 48);
        l.validate().unwrap();
    }

    #[test]
    fn check_rejects_out_of_bounds_layout() {
        // x=8, w=6 → x+w=14 > 12.
        let json = r#"{"slot":"D-00","widgets":[
            {"x":8,"y":0,"w":6,"h":4,"kind":"table","binding":"t"}
        ]}"#;
        let Input::Layout(l) = parse_input(json).unwrap() else {
            panic!("expected a bare DashboardLayout");
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::OutOfBounds { x_plus_w: 14, .. }
        ));
    }

    #[test]
    fn check_rejects_overlapping_layout() {
        let json = r#"{"slot":"D-00","widgets":[
            {"x":0,"y":0,"w":6,"h":4,"kind":"line-chart","binding":"a"},
            {"x":4,"y":2,"w":6,"h":4,"kind":"heatmap","binding":"b"}
        ]}"#;
        let Input::Layout(l) = parse_input(json).unwrap() else {
            panic!("expected a bare DashboardLayout");
        };
        assert!(matches!(
            l.validate().unwrap_err(),
            LayoutError::Overlap { a: 0, b: 1, .. }
        ));
    }

    #[test]
    fn check_accepts_valid_manifest_against_canonical_coverage() {
        let json = r#"{"schema_version":"1.0.0","layouts":[
            {"slot":"D-00","widgets":[{"x":0,"y":0,"w":12,"h":6,"kind":"table","binding":"t"}]}
        ]}"#;
        let Input::Manifest(m) = parse_input(json).unwrap() else {
            panic!("expected a LayoutManifest");
        };
        m.validate(&CoverageManifest::canonical()).unwrap();
    }

    #[test]
    fn check_rejects_manifest_with_unknown_slot() {
        // D-99 is not one of the canonical D-00..D-20 slots.
        let json = r#"{"schema_version":"1.0.0","layouts":[
            {"slot":"D-99","widgets":[{"x":0,"y":0,"w":4,"h":4,"kind":"kpi-tile","binding":"k"}]}
        ]}"#;
        let Input::Manifest(m) = parse_input(json).unwrap() else {
            panic!("expected a LayoutManifest");
        };
        assert!(matches!(
            m.validate(&CoverageManifest::canonical()).unwrap_err(),
            LayoutError::UnknownSlot(_)
        ));
    }

    #[test]
    fn parse_input_rejects_invalid_json() {
        assert!(parse_input("not json").is_err());
    }
}
