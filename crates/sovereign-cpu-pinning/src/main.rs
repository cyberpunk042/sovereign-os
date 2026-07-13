//! `sovereign-cpu-pinning` — emit the systemd `AllowedCPUs=` drop-ins that pin the
//! Trinity CPU agents to their CCD cores, from the `sovereign-cpu-topology` model.
//!
//! Default: print every unit's drop-in, each preceded by the
//! `/etc/systemd/system/<unit>.d/50-sovereign-cpu-pinning.conf` path it belongs at,
//! so an operator can review or redirect them into place. `--unit <name>` restricts
//! output to one unit. This is the actionable end of the E0672-E0674 CCD partition:
//! "how the topology becomes real CPU affinity" — the source of truth is the Rust
//! crate, replacing the hardcoded ranges duplicated in scripts/hardware/ccd-pinning.py.

#![forbid(unsafe_code)]

use sovereign_cpu_pinning::{dropin_path, pinning_dropins};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!(
            "sovereign-cpu-pinning — emit systemd AllowedCPUs= drop-ins for the Trinity CPU agents\n\n\
             USAGE:\n\
             \x20   sovereign-cpu-pinning                emit all Trinity unit pinning drop-ins\n\
             \x20   sovereign-cpu-pinning --unit NAME    emit only the named unit\n\
             \x20   sovereign-cpu-pinning --help         print this help and exit\n\n\
             Core ranges come from sovereign-cpu-topology (E0672-E0674), the single\n\
             source of truth for the CCD partition."
        );
        return;
    }
    let only = args
        .iter()
        .position(|a| a == "--unit")
        .and_then(|i| args.get(i + 1))
        .cloned();

    let dropins = match pinning_dropins() {
        Ok(d) => d,
        Err(e) => {
            eprintln!("sovereign-cpu-pinning: invalid topology partition: {e}");
            std::process::exit(1);
        }
    };

    let mut emitted = 0u32;
    for d in dropins {
        if let Some(ref u) = only
            && &d.unit != u
        {
            continue;
        }
        println!("# --- {} ---", dropin_path(&d.unit));
        print!("{}", d.body);
        println!();
        emitted += 1;
    }
    if emitted == 0 {
        eprintln!("sovereign-cpu-pinning: no unit matched (try --help)");
        std::process::exit(1);
    }
}
