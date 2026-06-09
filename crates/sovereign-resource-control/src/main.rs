//! `sovereign-resource-control` — emit the E0429 systemd resource-control
//! drop-ins for the five service boundaries.
//!
//! Default: print every profile's drop-in, each preceded by the
//! `/etc/systemd/system/<unit>.d/50-sovereign-resource.conf` path it belongs
//! at, so an operator can review or redirect them into place. `--unit <name>`
//! restricts output to one boundary. This is the actionable end of E0429:
//! "how profiles become real OS behavior."

#![forbid(unsafe_code)]

use sovereign_resource_control::canonical_profiles;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let only = args
        .iter()
        .position(|a| a == "--unit")
        .and_then(|i| args.get(i + 1))
        .cloned();

    let mut emitted = 0u32;
    for p in canonical_profiles() {
        if let Some(ref u) = only
            && &p.unit != u
        {
            continue;
        }
        println!(
            "# --- /etc/systemd/system/{}.d/50-sovereign-resource.conf ---",
            p.unit
        );
        print!("{}", p.to_systemd_dropin());
        println!();
        emitted += 1;
    }

    if emitted == 0 {
        eprintln!(
            "sovereign-resource-control: no profile matched {:?}; \
             known units: oracle.service scout.slice sandbox.slice \
             eval.slice gateway.service",
            only.unwrap_or_default()
        );
        std::process::exit(1);
    }
}
