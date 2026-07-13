//! `sovereign-data-plane` CLI — the runnable end of M010's deterministic data plane.
//!
//! The library is a Roaring-style compressed bitmap over `u32` keys: the exact,
//! deterministic set substrate behind fast metadata filtering. But nothing *ran*
//! it, so "what is the intersection of these two id sets?" was unanswerable at the
//! command line. This binary is that runnable end — a set-algebra tool over JSON
//! arrays of `u32`.
//!
//! Each input FILE is a JSON array of `u32` (e.g. `[1, 2, 3, 100000]`) — think a
//! set of object / metadata ids. Values are treated as a set: duplicates collapse,
//! and results are emitted in ascending order.
//!
//! Modes:
//!   * default (no args) — print a short reference (what the tool computes).
//!   * `--union A B`        — union of two sets, as a sorted JSON array.
//!   * `--intersect A B`    — intersection of two sets, as a sorted JSON array.
//!   * `--cardinality A`    — the number of distinct values in A.
//!   * `--contains A VALUE` — membership test; prints `true`/`false` and exits 0
//!     when present, 1 when absent (grep-style).
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_data_plane::{RoaringBitmap, SCHEMA_VERSION};

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-data-plane — set algebra over compressed u32 bitmaps (M010)\n\n\
     Each FILE is a JSON array of u32, e.g. [1, 2, 3, 100000]. Values form a set:\n\
     duplicates collapse. Set results are emitted as a sorted JSON array of u32.\n\n\
     USAGE:\n\
     \x20   sovereign-data-plane                      print a short reference and exit\n\
     \x20   sovereign-data-plane --union A B          union of sets A and B\n\
     \x20   sovereign-data-plane --intersect A B      intersection of sets A and B\n\
     \x20   sovereign-data-plane --cardinality A      count of distinct values in A\n\
     \x20   sovereign-data-plane --contains A VALUE   membership test (exit 0 hit, 1 miss)\n\
     \x20   sovereign-data-plane --help               print this help and exit\n\n\
     Exit status is non-zero on any read or parse error; --contains additionally\n\
     exits 1 when VALUE is absent (grep-style).\n"
        .to_string()
}

/// The default (no-args) reference: what the tool computes, and how.
fn reference_text() -> String {
    format!(
        "sovereign-data-plane (schema {SCHEMA_VERSION}) — M010 deterministic data plane.\n\n\
         A Roaring-style compressed bitmap over u32 keys: the exact, deterministic set\n\
         substrate behind fast metadata filtering. This CLI runs exact set algebra over\n\
         JSON arrays of u32 (sets of ids):\n\n\
         \x20   --union A B         union of two sets           -> sorted JSON array\n\
         \x20   --intersect A B     intersection of two sets    -> sorted JSON array\n\
         \x20   --cardinality A     count of distinct values    -> integer\n\
         \x20   --contains A VALUE  membership test             -> true / false\n\n\
         Run with --help for full usage.\n"
    )
}

/// Parse a JSON array of `u32` into a [`RoaringBitmap`] (duplicates collapse).
fn parse_set(json: &str) -> Result<RoaringBitmap, serde_json::Error> {
    let values: Vec<u32> = serde_json::from_str(json)?;
    Ok(RoaringBitmap::from_values(values))
}

/// Read FILE and parse it as a set, mapping every failure to a message.
fn load_set(path: &str) -> Result<RoaringBitmap, String> {
    let json = std::fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))?;
    parse_set(&json).map_err(|e| format!("{path} is not a JSON array of u32: {e}"))
}

/// Serialize a bitmap's ascending values as a compact JSON array (pipeable).
fn format_set(bitmap: &RoaringBitmap) -> String {
    // A `Vec<u32>` always serializes to a JSON array; this cannot fail.
    serde_json::to_string(&bitmap.to_vec()).expect("Vec<u32> serializes to a JSON array")
}

/// `--union` / `--intersect`: load two sets, combine them with `op`, and print
/// the result as a sorted JSON array. Non-zero exit on any read/parse error.
fn run_binary(
    args: &[String],
    op: impl Fn(&RoaringBitmap, &RoaringBitmap) -> RoaringBitmap,
) -> ExitCode {
    let [_, path_a, path_b] = args else {
        let flag = args.first().map(String::as_str).unwrap_or("<op>");
        eprintln!("error: {flag} requires exactly two FILE arguments\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    };
    let a = match load_set(path_a) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::FAILURE;
        }
    };
    let b = match load_set(path_b) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::FAILURE;
        }
    };
    println!("{}", format_set(&op(&a, &b)));
    ExitCode::SUCCESS
}

/// `--cardinality`: load one set and print its number of distinct values.
fn run_cardinality(args: &[String]) -> ExitCode {
    let [_, path] = args else {
        eprintln!("error: --cardinality requires exactly one FILE argument\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    };
    match load_set(path) {
        Ok(set) => {
            println!("{}", set.cardinality());
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}

/// `--contains`: load one set and test membership of VALUE. Prints `true`/`false`
/// and exits 0 when present, 1 when absent (grep-style); other errors are failures.
fn run_contains(args: &[String]) -> ExitCode {
    let [_, path, value] = args else {
        eprintln!("error: --contains requires a FILE and a VALUE argument\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    };
    let needle: u32 = match value.parse() {
        Ok(n) => n,
        Err(e) => {
            eprintln!("error: VALUE '{value}' is not a u32: {e}");
            return ExitCode::FAILURE;
        }
    };
    let set = match load_set(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::FAILURE;
        }
    };
    let present = set.contains(needle);
    println!("{present}");
    if present {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    match args.first().map(String::as_str) {
        Some("--union") => run_binary(&args, |a, b| a.union(b)),
        Some("--intersect") => run_binary(&args, |a, b| a.intersection(b)),
        Some("--cardinality") => run_cardinality(&args),
        Some("--contains") => run_contains(&args),
        Some(unknown) => {
            eprintln!("error: unknown argument '{unknown}'\n");
            eprint!("{}", help_text());
            ExitCode::FAILURE
        }
        None => {
            print!("{}", reference_text());
            ExitCode::SUCCESS
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_set_reads_json_array() {
        let set = parse_set("[1, 2, 3, 100000]").unwrap();
        assert_eq!(set.cardinality(), 4);
        assert!(set.contains(100_000));
        assert!(!set.contains(4));
    }

    #[test]
    fn parse_set_collapses_duplicates() {
        // A JSON array is a multiset on the wire but a set once loaded.
        let set = parse_set("[7, 7, 7, 42]").unwrap();
        assert_eq!(set.cardinality(), 2);
    }

    #[test]
    fn parse_set_accepts_empty_array() {
        let set = parse_set("[]").unwrap();
        assert_eq!(set.cardinality(), 0);
        assert_eq!(format_set(&set), "[]");
    }

    #[test]
    fn parse_set_rejects_bad_input() {
        assert!(parse_set("not json").is_err());
        assert!(parse_set("{\"a\": 1}").is_err()); // object, not array
        assert!(parse_set("[1, -2]").is_err()); // -2 is out of u32 range
    }

    #[test]
    fn format_set_is_sorted_compact_json() {
        let set = parse_set("[500000, 1, 70000, 2]").unwrap();
        assert_eq!(format_set(&set), "[1,2,70000,500000]");
    }

    #[test]
    fn union_then_format_matches_reference() {
        let a = parse_set("[1, 2, 3, 100000]").unwrap();
        let b = parse_set("[3, 4, 100000, 200000]").unwrap();
        assert_eq!(format_set(&a.union(&b)), "[1,2,3,4,100000,200000]");
    }

    #[test]
    fn intersect_then_format_matches_reference() {
        let a = parse_set("[1, 2, 3, 100000, 200000]").unwrap();
        let b = parse_set("[3, 4, 100000]").unwrap();
        assert_eq!(format_set(&a.intersection(&b)), "[3,100000]");
    }

    #[test]
    fn load_set_reports_missing_file() {
        let err = load_set("/no/such/sovereign-data-plane/file.json").unwrap_err();
        assert!(err.contains("cannot read"), "unexpected message: {err}");
    }

    #[test]
    fn load_set_reads_a_real_file() {
        let mut path = std::env::temp_dir();
        path.push(format!(
            "sovereign-data-plane-cli-{}.json",
            std::process::id()
        ));
        std::fs::write(&path, "[10, 20, 30, 20]").unwrap();
        let set = load_set(path.to_str().unwrap()).unwrap();
        assert_eq!(set.cardinality(), 3);
        assert!(set.contains(20));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn help_and_reference_mention_all_ops() {
        let h = help_text();
        let r = reference_text();
        for op in ["--union", "--intersect", "--cardinality", "--contains"] {
            assert!(h.contains(op), "help missing {op}");
            assert!(r.contains(op), "reference missing {op}");
        }
    }
}
