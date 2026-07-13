//! `sovereign-vm-channel` CLI — the runnable end of E0120 / M00222–M00224.
//!
//! The library fixes the Host↔4090 Communication Boundary: four narrow channels
//! (M00222), eight message types (M00223), and one invariant (M00224) — every VM
//! output is a *candidate*, never committed directly. But nothing *ran* it, so
//! "is this channel message well-formed, and does it honour M00224?" was
//! unanswerable at the command line. This binary is that runnable end, and it
//! does real work with no live VM: it validates message envelopes against the
//! crate's own authoritative decision functions ([`VmMessage::direction`] and
//! [`VmMessage::is_candidate`]).
//!
//! Modes:
//!   * default (no args) — print the channel protocol reference: the 4 channels,
//!     the 8 message types with their fixed direction + candidate status, and the
//!     M00224 invariant.
//!   * `--check FILE` — load a channel-message envelope (or a JSON array of them),
//!     validate each against the crate's decision functions (a claimed `direction`
//!     or `candidate` that contradicts the message type is rejected), and exit
//!     non-zero if any fail.
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use serde::{Deserialize, Serialize};
use sovereign_vm_channel::{Direction, VmChannel, VmMessage};

/// The stable kebab-case label for a channel — identical to how [`VmChannel`]
/// serializes to JSON (kept honest by the `channel_label_matches_serde` test).
fn channel_label(channel: VmChannel) -> &'static str {
    match channel {
        VmChannel::VirtioVsock => "virtio-vsock",
        VmChannel::GrpcOverVsock => "grpc-over-vsock",
        VmChannel::UnixSocketProxy => "unix-socket-proxy",
        VmChannel::ExchangeSharedFolder => "exchange-shared-folder",
    }
}

/// The stable kebab-case label for a message type — identical to how
/// [`VmMessage`] serializes to JSON (kept honest by `message_label_matches_serde`).
fn message_label(message: VmMessage) -> &'static str {
    match message {
        VmMessage::DraftRequest => "draft-request",
        VmMessage::DraftResult => "draft-result",
        VmMessage::EmbeddingRequest => "embedding-request",
        VmMessage::RerankResult => "rerank-result",
        VmMessage::VisionResult => "vision-result",
        VmMessage::ToolPlan => "tool-plan",
        VmMessage::RiskAssessment => "risk-assessment",
        VmMessage::PatchProposal => "patch-proposal",
    }
}

/// The stable kebab-case label for a direction — identical to how [`Direction`]
/// serializes to JSON (kept honest by the `direction_label_matches_serde` test).
fn direction_label(direction: Direction) -> &'static str {
    match direction {
        Direction::ToVm => "to-vm",
        Direction::FromVm => "from-vm",
    }
}

/// A single message as it crosses one of the four channels: which [`VmChannel`]
/// carried it, which [`VmMessage`] type it is, and (optionally) the sender's
/// claims about how it must be handled — its [`Direction`] and whether it is a
/// candidate. The claims are what [`ChannelMessage::validate`] checks against the
/// crate's authoritative decision functions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct ChannelMessage {
    /// The channel that carried the message.
    channel: VmChannel,
    /// The message type.
    message: VmMessage,
    /// The sender's claimed flow direction, if asserted.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    direction: Option<Direction>,
    /// The sender's claim that this is (or is not) a candidate, if asserted.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    candidate: Option<bool>,
}

/// Why a channel-message envelope failed the boundary contract.
#[derive(Debug, Clone, PartialEq, Eq)]
enum ChannelError {
    /// The envelope's claimed direction contradicts the message type's fixed
    /// direction (from [`VmMessage::direction`]).
    DirectionMismatch {
        /// The direction the envelope claimed.
        claimed: Direction,
        /// The direction this message type actually flows.
        actual: Direction,
    },
    /// The envelope's candidate claim contradicts the M00224 invariant (from
    /// [`VmMessage::is_candidate`]) — e.g. a VM output claimed as a non-candidate
    /// (committed directly), or a host request claimed as a candidate.
    CandidateViolation {
        /// The candidate status the envelope claimed.
        claimed: bool,
        /// The candidate status the invariant requires.
        actual: bool,
    },
}

impl std::fmt::Display for ChannelError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ChannelError::DirectionMismatch { claimed, actual } => write!(
                f,
                "claims direction {} but this message type is fixed as {}",
                direction_label(*claimed),
                direction_label(*actual),
            ),
            ChannelError::CandidateViolation { claimed, actual } => write!(
                f,
                "claims candidate={claimed} but M00224 fixes this message type as candidate={actual}",
            ),
        }
    }
}

impl std::error::Error for ChannelError {}

impl ChannelMessage {
    /// Validate the envelope against the crate's authoritative decision
    /// functions: any asserted `direction` must match [`VmMessage::direction`],
    /// and any asserted `candidate` must match [`VmMessage::is_candidate`] (the
    /// M00224 invariant). An envelope that asserts neither is trivially
    /// well-formed — its channel and message type were already validated by serde.
    fn validate(&self) -> Result<(), ChannelError> {
        let actual_direction = self.message.direction();
        if let Some(claimed) = self.direction {
            if claimed != actual_direction {
                return Err(ChannelError::DirectionMismatch {
                    claimed,
                    actual: actual_direction,
                });
            }
        }
        let actual_candidate = self.message.is_candidate();
        if let Some(claimed) = self.candidate {
            if claimed != actual_candidate {
                return Err(ChannelError::CandidateViolation {
                    claimed,
                    actual: actual_candidate,
                });
            }
        }
        Ok(())
    }
}

/// The human-readable reference: the 4 channels, the 8 message types with their
/// fixed direction + candidate status, and the M00224 invariant.
fn reference_text() -> String {
    let mut s = String::from(
        "The Host↔4090 Communication Boundary (E0120 / M00222–M00224).\n\n\
         Channels (M00222) — every message crosses exactly one of these four:\n",
    );
    for (i, channel) in VmChannel::ALL.into_iter().enumerate() {
        s.push_str(&format!("  {}. {}\n", i + 1, channel_label(channel)));
    }
    s.push_str("\nMessage types (M00223) — each has a fixed direction and candidate status:\n");
    s.push_str(&format!(
        "  {:<9}  {:<9}  {}\n",
        "DIRECTION", "CANDIDATE", "MESSAGE"
    ));
    for message in VmMessage::ALL {
        s.push_str(&format!(
            "  {:<9}  {:<9}  {}\n",
            direction_label(message.direction()),
            if message.is_candidate() { "yes" } else { "no" },
            message_label(message),
        ));
    }
    s.push_str(
        "\nInvariant (M00224): every VM output (from-vm) is a candidate — the host\n\
         AVX-512 layer policy-filters it and the oracle verifies it before the\n\
         replay log commits. VM output is never trusted or committed directly.\n",
    );
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-vm-channel — the Host↔4090 Communication Boundary (E0120 / M00222–M00224)\n\n\
     Four narrow channels, eight message types, one invariant: every VM output is\n\
     a candidate, never committed directly.\n\n\
     USAGE:\n\
     \x20   sovereign-vm-channel                   print the channel protocol reference\n\
     \x20   sovereign-vm-channel --check FILE       validate channel-message envelope(s) from JSON\n\
     \x20   sovereign-vm-channel --help             print this help and exit\n\n\
     --check FILE loads a single envelope object or a JSON array of them. Each\n\
     envelope names a `channel` and a `message` type; it may also assert a\n\
     `direction` and/or a `candidate` flag. validate() rejects any assertion that\n\
     contradicts the crate's fixed decision functions (a from-vm message claimed\n\
     as to-vm, or a VM output claimed as a non-candidate — an M00224 violation).\n\
     Exits non-zero if any envelope fails.\n"
        .to_string()
}

/// The outcome of checking one channel-message envelope.
struct CheckOutcome {
    /// The channel the envelope named.
    channel: VmChannel,
    /// The message type the envelope named.
    message: VmMessage,
    /// The boundary-contract result.
    result: Result<(), ChannelError>,
}

/// Accept either a single envelope object or a JSON array of them.
fn parse_messages(json: &str) -> Result<Vec<ChannelMessage>, serde_json::Error> {
    match serde_json::from_str::<Vec<ChannelMessage>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single envelope object, surfacing that error.
        Err(_) => serde_json::from_str::<ChannelMessage>(json).map(|m| vec![m]),
    }
}

/// Parse one-or-many envelopes from JSON and validate each.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let messages = parse_messages(json)?;
    Ok(messages
        .into_iter()
        .map(|m| CheckOutcome {
            channel: m.channel,
            message: m.message,
            result: m.validate(),
        })
        .collect())
}

/// `--check FILE`: read the file, validate the envelope(s), print a report, and
/// return a process exit code (non-zero on read/parse error or any failure).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcomes = match check_json(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a channel-message envelope (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no channel messages in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let message = message_label(o.message);
        let channel = channel_label(o.channel);
        let dir = direction_label(o.message.direction());
        let cand = if o.message.is_candidate() {
            "candidate"
        } else {
            "non-candidate"
        };
        match &o.result {
            Ok(()) => println!("OK   {message} on {channel} [{dir}, {cand}]"),
            Err(err) => {
                all_ok = false;
                println!("FAIL {message} on {channel} — {err}");
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

    /// A minimal well-formed envelope: names a channel + message, asserts nothing.
    fn envelope(channel: VmChannel, message: VmMessage) -> ChannelMessage {
        ChannelMessage {
            channel,
            message,
            direction: None,
            candidate: None,
        }
    }

    #[test]
    fn channel_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for c in VmChannel::ALL {
            let json = serde_json::to_string(&c).unwrap();
            assert_eq!(json, format!("\"{}\"", channel_label(c)));
        }
    }

    #[test]
    fn message_label_matches_serde() {
        for m in VmMessage::ALL {
            let json = serde_json::to_string(&m).unwrap();
            assert_eq!(json, format!("\"{}\"", message_label(m)));
        }
    }

    #[test]
    fn direction_label_matches_serde() {
        for d in [Direction::ToVm, Direction::FromVm] {
            let json = serde_json::to_string(&d).unwrap();
            assert_eq!(json, format!("\"{}\"", direction_label(d)));
        }
    }

    #[test]
    fn reference_lists_all_channels_messages_and_the_invariant() {
        let t = reference_text();
        for c in VmChannel::ALL {
            assert!(
                t.contains(channel_label(c)),
                "reference missing {c:?}:\n{t}"
            );
        }
        for m in VmMessage::ALL {
            assert!(
                t.contains(message_label(m)),
                "reference missing {m:?}:\n{t}"
            );
        }
        assert!(
            t.contains("M00224"),
            "reference must name the invariant:\n{t}"
        );
    }

    #[test]
    fn check_accepts_minimal_well_formed_envelope() {
        let json =
            serde_json::to_string(&envelope(VmChannel::VirtioVsock, VmMessage::DraftRequest))
                .unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(outcomes[0].result.is_ok());
    }

    #[test]
    fn check_accepts_consistent_assertions() {
        // A patch proposal from the VM: from-vm and a candidate — both correct.
        let e = ChannelMessage {
            channel: VmChannel::GrpcOverVsock,
            message: VmMessage::PatchProposal,
            direction: Some(Direction::FromVm),
            candidate: Some(true),
        };
        let json = serde_json::to_string(&e).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert!(outcomes[0].result.is_ok());
    }

    #[test]
    fn check_rejects_direction_mismatch() {
        // A patch proposal is fixed as from-vm; claiming to-vm is a contradiction.
        let e = ChannelMessage {
            channel: VmChannel::GrpcOverVsock,
            message: VmMessage::PatchProposal,
            direction: Some(Direction::ToVm),
            candidate: None,
        };
        let json = serde_json::to_string(&e).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(
            outcomes[0].result,
            Err(ChannelError::DirectionMismatch {
                claimed: Direction::ToVm,
                actual: Direction::FromVm,
            })
        );
    }

    #[test]
    fn check_rejects_vm_output_claimed_as_non_candidate() {
        // The M00224 core: a VM output (PatchProposal) marked as non-candidate
        // would be committed directly — the exact thing the invariant forbids.
        let e = ChannelMessage {
            channel: VmChannel::GrpcOverVsock,
            message: VmMessage::PatchProposal,
            direction: None,
            candidate: Some(false),
        };
        let json = serde_json::to_string(&e).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(
            outcomes[0].result,
            Err(ChannelError::CandidateViolation {
                claimed: false,
                actual: true,
            })
        );
    }

    #[test]
    fn check_rejects_host_request_claimed_as_candidate() {
        // Host-originated requests are not candidates; claiming otherwise is wrong.
        let e = ChannelMessage {
            channel: VmChannel::VirtioVsock,
            message: VmMessage::DraftRequest,
            direction: None,
            candidate: Some(true),
        };
        let json = serde_json::to_string(&e).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(
            outcomes[0].result,
            Err(ChannelError::CandidateViolation {
                claimed: true,
                actual: false,
            })
        );
    }

    #[test]
    fn check_parses_array_and_validates_each() {
        let arr = vec![
            envelope(VmChannel::VirtioVsock, VmMessage::DraftRequest),
            envelope(VmChannel::GrpcOverVsock, VmMessage::PatchProposal),
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 2);
        assert!(outcomes.iter().all(|o| o.result.is_ok()));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
    }

    #[test]
    fn check_rejects_unknown_channel_or_message() {
        // serde rejects values outside the fixed four channels / eight messages.
        assert!(check_json(r#"{"channel":"virtio-vsock","message":"bogus"}"#).is_err());
        assert!(check_json(r#"{"channel":"telepathy","message":"draft-request"}"#).is_err());
    }
}
