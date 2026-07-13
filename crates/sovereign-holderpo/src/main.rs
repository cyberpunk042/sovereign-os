//! `sovereign-holderpo` CLI — the runnable end of M078 (HölderPO + GRPO).
//!
//! The library holds the real, pure math of HölderPO (arXiv 2605.12058): the
//! Hölder mean `M_p(x)`, the dynamic-`p` anneal schedules, GRPO group-relative
//! advantages, and a validated training-config surface. But nothing *ran* it, so
//! "what does the Hölder aggregator actually output for these token
//! probabilities?" was unanswerable at the command line. This binary is that
//! runnable end — and it does REAL work (the same functions the training loop
//! would call), with no live training loop, gradients, or model weights required.
//!
//! Modes:
//!   * default (no args) — print the HölderPO model reference: the Hölder-mean
//!     formula and its `p` limits, the four anneal schedules, the default config,
//!     and the computable ops.
//!   * `--compute FILE` — run one of the pure functions on JSON input and print
//!     the JSON result. Accepts a single request object or a JSON array of them.
//!   * `--check FILE` — load a `HolderPoConfig` (or a JSON array of them),
//!     `validate()` each, and exit non-zero if any fail.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde_json::json;

use sovereign_holderpo::{
    AnnealSchedule, HolderPoConfig, Trajectory, aggregate_trajectory_probs,
    group_relative_advantages, holder_mean,
};

/// The stable kebab-case label for a schedule — identical to how
/// [`AnnealSchedule`] serializes to JSON (kept honest by the
/// `schedule_label_matches_serde` test).
fn schedule_label(schedule: AnnealSchedule) -> &'static str {
    match schedule {
        AnnealSchedule::Constant => "constant",
        AnnealSchedule::Linear => "linear",
        AnnealSchedule::Cosine => "cosine",
        AnnealSchedule::Step => "step",
    }
}

/// The human-readable reference: the HölderPO model in one screen.
fn reference_text() -> String {
    let d = HolderPoConfig::default();
    format!(
        "HölderPO — M078 post-training aggregation (arXiv 2605.12058)\n\n\
         The Hölder mean generalises GRPO's token aggregator:\n\
         \x20   M_p(x) = ( (1/n) Σ x_i^p )^(1/p)\n\n\
         Limits of the parameter p:\n\
         \x20   p → -∞   minimum        (gradient on the weakest token)\n\
         \x20   p =  0   geometric mean (multiplicative; GRPO default)\n\
         \x20   p =  1   arithmetic mean (additive)\n\
         \x20   p → +∞   maximum        (gradient on the strongest token)\n\n\
         Dynamic-p anneal schedules (p_start → p_end over total_steps):\n\
         \x20   {constant:<9} p held at p_start\n\
         \x20   {linear:<9} straight-line interpolation\n\
         \x20   {cosine:<9} smooth half-cosine ramp\n\
         \x20   {step:<9} 4 evenly-spaced jumps\n\n\
         Default config:\n\
         \x20   schema {ver}, p {ps} → {pe}, {sched}, {steps} steps, \
         group {group}, kl {kl}, clip {clip}\n\n\
         Computable ops (--compute FILE, JSON request(s)):\n\
         \x20   {{\"op\":\"holder-mean\",\"xs\":[0.1,0.4],\"p\":0.0}}\n\
         \x20   {{\"op\":\"p-at-step\",\"config\":{{…}},\"step\":50}}\n\
         \x20   {{\"op\":\"aggregate\",\"trajectories\":[{{\"token_probs\":[0.1,0.4],\
         \"reward\":1.0}}],\"p\":0.0}}\n\
         \x20   {{\"op\":\"advantages\",\"rewards\":[1,2,3,4],\"normalise\":true}}\n",
        constant = schedule_label(AnnealSchedule::Constant),
        linear = schedule_label(AnnealSchedule::Linear),
        cosine = schedule_label(AnnealSchedule::Cosine),
        step = schedule_label(AnnealSchedule::Step),
        ver = d.schema_version,
        ps = d.p_start,
        pe = d.p_end,
        sched = schedule_label(d.schedule),
        steps = d.total_steps,
        group = d.group_size,
        kl = d.kl_coef,
        clip = d.clip_range,
    )
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-holderpo — HölderPO + GRPO post-training aggregation (M078, arXiv 2605.12058)\n\n\
     The Hölder mean generalises GRPO's token aggregator via a parameter p; a\n\
     dynamic-p schedule anneals it during training. This CLI runs that real math.\n\n\
     USAGE:\n\
     \x20   sovereign-holderpo                  print the HölderPO model reference\n\
     \x20   sovereign-holderpo --compute FILE   run a computation from JSON, print JSON result\n\
     \x20   sovereign-holderpo --check FILE     validate HolderPoConfig(s) from JSON\n\
     \x20   sovereign-holderpo --help           print this help and exit\n\n\
     --compute FILE accepts one request object or a JSON array. Supported ops:\n\
     \x20   holder-mean  {\"op\":\"holder-mean\",\"xs\":[0.1,0.4],\"p\":0.0}\n\
     \x20   p-at-step    {\"op\":\"p-at-step\",\"config\":{…},\"step\":50}\n\
     \x20   aggregate    {\"op\":\"aggregate\",\"trajectories\":[{\"token_probs\":[…],\"reward\":1.0}],\"p\":0.0}\n\
     \x20   advantages   {\"op\":\"advantages\",\"rewards\":[1,2,3,4],\"normalise\":true}\n\n\
     --check FILE loads one HolderPoConfig object or a JSON array, runs validate()\n\
     on each, and exits non-zero if any fail.\n"
        .to_string()
}

/// Read a required numeric field from a request object.
fn field_f64(req: &serde_json::Value, key: &str) -> Result<f64, String> {
    req.get(key)
        .and_then(serde_json::Value::as_f64)
        .ok_or_else(|| format!("field \"{key}\" must be a number"))
}

/// Read a required array-of-numbers field from a request object.
fn field_vec_f64(req: &serde_json::Value, key: &str) -> Result<Vec<f64>, String> {
    let value = req
        .get(key)
        .ok_or_else(|| format!("missing field \"{key}\""))?;
    serde_json::from_value::<Vec<f64>>(value.clone())
        .map_err(|e| format!("field \"{key}\" must be an array of numbers: {e}"))
}

/// Run one compute request: dispatch on `op` and return the JSON result.
///
/// This is the real work — each arm calls the same pure library function the
/// training loop would call, with no gradients, data, or live loop involved.
fn compute(req: &serde_json::Value) -> Result<serde_json::Value, String> {
    let op = req
        .get("op")
        .and_then(serde_json::Value::as_str)
        .ok_or("request must have a string \"op\" field")?;
    match op {
        "holder-mean" => {
            let xs = field_vec_f64(req, "xs")?;
            let p = field_f64(req, "p")?;
            let result = holder_mean(&xs, p).map_err(|e| e.to_string())?;
            Ok(json!({ "op": "holder-mean", "p": p, "n": xs.len(), "result": result }))
        }
        "p-at-step" => {
            let config_json = req
                .get("config")
                .cloned()
                .ok_or("p-at-step requires a \"config\" object")?;
            let config: HolderPoConfig =
                serde_json::from_value(config_json).map_err(|e| format!("invalid config: {e}"))?;
            let step = req
                .get("step")
                .and_then(serde_json::Value::as_u64)
                .ok_or("p-at-step requires an integer \"step\"")?;
            let p = config.p_at_step(step).map_err(|e| e.to_string())?;
            Ok(json!({
                "op": "p-at-step",
                "step": step,
                "schedule": config.schedule,
                "p": p,
            }))
        }
        "aggregate" => {
            let trajectories_json = req
                .get("trajectories")
                .cloned()
                .ok_or("aggregate requires a \"trajectories\" array")?;
            let trajectories: Vec<Trajectory> = serde_json::from_value(trajectories_json)
                .map_err(|e| format!("invalid trajectories: {e}"))?;
            let p = field_f64(req, "p")?;
            let aggregated =
                aggregate_trajectory_probs(&trajectories, p).map_err(|e| e.to_string())?;
            Ok(json!({ "op": "aggregate", "p": p, "aggregated_probs": aggregated }))
        }
        "advantages" => {
            let rewards = field_vec_f64(req, "rewards")?;
            let normalise = req
                .get("normalise")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false);
            let advantages = group_relative_advantages(&rewards, normalise);
            Ok(json!({ "op": "advantages", "normalise": normalise, "advantages": advantages }))
        }
        other => Err(format!(
            "unknown op \"{other}\" (expected holder-mean, p-at-step, aggregate, or advantages)"
        )),
    }
}

/// `--compute FILE`: read the file, run the request(s), print the JSON result,
/// and return a process exit code (non-zero on read/parse error or any failure).
fn run_compute(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let parsed: serde_json::Value = match serde_json::from_str(&json) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("error: {path} is not valid JSON: {e}");
            return ExitCode::FAILURE;
        }
    };

    let is_array = parsed.is_array();
    let requests: Vec<serde_json::Value> = match parsed {
        serde_json::Value::Array(a) => a,
        other => vec![other],
    };

    let mut outputs = Vec::with_capacity(requests.len());
    let mut all_ok = true;
    for req in &requests {
        match compute(req) {
            Ok(out) => outputs.push(out),
            Err(e) => {
                all_ok = false;
                eprintln!("error: {e}");
            }
        }
    }

    let rendered = if is_array {
        serde_json::to_string_pretty(&serde_json::Value::Array(outputs))
    } else if let Some(one) = outputs.first() {
        serde_json::to_string_pretty(one)
    } else {
        Ok(String::new())
    };
    match rendered {
        Ok(s) if !s.is_empty() => println!("{s}"),
        Ok(_) => {}
        Err(e) => eprintln!("error: could not render result: {e}"),
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

/// Accept either a single config object or a JSON array of them.
fn parse_configs(json: &str) -> Result<Vec<HolderPoConfig>, serde_json::Error> {
    match serde_json::from_str::<Vec<HolderPoConfig>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single config object, surfacing that error.
        Err(_) => serde_json::from_str::<HolderPoConfig>(json).map(|c| vec![c]),
    }
}

/// `--check FILE`: read the file, validate the config(s), print a report, and
/// return a process exit code (non-zero on read/parse error or any failure).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let configs = match parse_configs(&json) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {path} is not a HolderPoConfig (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if configs.is_empty() {
        println!("(no configs in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for c in &configs {
        match c.validate() {
            Ok(()) => println!(
                "OK   schema={} schedule={} p:{}→{} over {} steps, group {}",
                c.schema_version,
                schedule_label(c.schedule),
                c.p_start,
                c.p_end,
                c.total_steps,
                c.group_size,
            ),
            Err(err) => {
                all_ok = false;
                println!("FAIL schema={} — {err}", c.schema_version);
            }
        }
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--compute") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --compute requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_compute(path);
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

    #[test]
    fn schedule_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for s in [
            AnnealSchedule::Constant,
            AnnealSchedule::Linear,
            AnnealSchedule::Cosine,
            AnnealSchedule::Step,
        ] {
            let json = serde_json::to_string(&s).unwrap();
            assert_eq!(json, format!("\"{}\"", schedule_label(s)));
        }
    }

    #[test]
    fn reference_mentions_schedules_and_ops() {
        let t = reference_text();
        for label in ["constant", "linear", "cosine", "step"] {
            assert!(
                t.contains(label),
                "reference missing schedule {label}:\n{t}"
            );
        }
        for op in ["holder-mean", "p-at-step", "aggregate", "advantages"] {
            assert!(t.contains(op), "reference missing op {op}:\n{t}");
        }
        // The default schema version must appear (kept honest against the lib).
        assert!(t.contains(&HolderPoConfig::default().schema_version));
    }

    #[test]
    fn compute_holder_mean_is_geometric_at_p_zero() {
        let req = json!({ "op": "holder-mean", "xs": [0.1, 0.4], "p": 0.0 });
        let out = compute(&req).unwrap();
        assert_eq!(out["op"], "holder-mean");
        assert_eq!(out["n"], 2);
        let r = out["result"].as_f64().unwrap();
        assert!((r - 0.2).abs() < 1e-9, "got {r}");
    }

    #[test]
    fn compute_p_at_step_cosine_midpoint() {
        let config = json!({
            "schema_version": "1.0.0",
            "p_start": 0.0,
            "p_end": 8.0,
            "schedule": "cosine",
            "total_steps": 100,
            "group_size": 8,
            "kl_coef": 0.01,
            "clip_range": 0.2
        });
        let req = json!({ "op": "p-at-step", "config": config, "step": 50 });
        let out = compute(&req).unwrap();
        let p = out["p"].as_f64().unwrap();
        assert!((p - 4.0).abs() < 1e-9, "expected 4.0 got {p}");
        assert_eq!(out["schedule"], "cosine");
    }

    #[test]
    fn compute_aggregate_per_trajectory() {
        let req = json!({
            "op": "aggregate",
            "trajectories": [
                { "token_probs": [0.1, 0.4], "reward": 1.0 },
                { "token_probs": [0.5, 0.5], "reward": 0.5 }
            ],
            "p": 0.0
        });
        let out = compute(&req).unwrap();
        let aggs = out["aggregated_probs"].as_array().unwrap();
        assert!((aggs[0].as_f64().unwrap() - 0.2).abs() < 1e-9);
        assert!((aggs[1].as_f64().unwrap() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn compute_advantages_center_around_mean() {
        let req =
            json!({ "op": "advantages", "rewards": [1.0, 2.0, 3.0, 4.0], "normalise": false });
        let out = compute(&req).unwrap();
        let adv = out["advantages"].as_array().unwrap();
        let got: Vec<f64> = adv.iter().map(|v| v.as_f64().unwrap()).collect();
        assert_eq!(got, vec![-1.5, -0.5, 0.5, 1.5]);
    }

    #[test]
    fn compute_rejects_unknown_op() {
        assert!(compute(&json!({ "op": "nope" })).is_err());
    }

    #[test]
    fn compute_rejects_missing_field() {
        // holder-mean without xs.
        assert!(compute(&json!({ "op": "holder-mean", "p": 0.0 })).is_err());
    }

    #[test]
    fn compute_surfaces_library_validation_error() {
        // A zero probability must be rejected by holder_mean.
        let req = json!({ "op": "holder-mean", "xs": [0.5, 0.0], "p": 1.0 });
        assert!(compute(&req).is_err());
    }

    #[test]
    fn parse_configs_accepts_single_and_array() {
        let single = serde_json::to_string(&HolderPoConfig::default()).unwrap();
        assert_eq!(parse_configs(&single).unwrap().len(), 1);
        let array = format!("[{single},{single}]");
        assert_eq!(parse_configs(&array).unwrap().len(), 2);
    }

    #[test]
    fn parse_configs_default_validates() {
        let single = serde_json::to_string(&HolderPoConfig::default()).unwrap();
        let configs = parse_configs(&single).unwrap();
        assert!(configs[0].validate().is_ok());
    }
}
