//! A tiny, deterministic, *loadable* model fixture for model-backed daemon tests.
//!
//! Every `/v1/coat`, agentic, and generation test in the daemon has run
//! heuristic-only until now — there was no small real model to point
//! `SOVEREIGN_GATEWAY_MODEL` at, so the model-backed forward pass (and the
//! `thought_source: "model"` path it flags) went unexercised (F-2026-090; also
//! the "synthetic loadable model-dir fixture" that F-2026-066 wanted).
//!
//! This module writes a real, on-disk model dir — `config.json` +
//! `model.safetensors` + `tokenizer.json` — that the daemon's own
//! `load_generator_from_dir` loads through the production path (no test-only
//! shortcut into the loader). It is a 2-layer, GQA (2 query / 1 KV head),
//! `model_dim` 8, `vocab` 256 Llama-shaped model with deterministic pseudo-random
//! weights, so the fixture is byte-reproducible with no `rand` and no network.
//! The tensor layout mirrors the loader's own `fixture()` unit test; the
//! tokenizer is a vocab-256 byte-level BPE (the GPT-2 byte↔unicode alphabet),
//! matching the model's 256 vocab so the daemon's vocab-equality check passes.
//!
//! `TinyModelDir::new_gguf` writes the same-shaped model as a real GGUF v3
//! container (metadata-derived hyperparameters, F32 tensors) + a sidecar
//! `tokenizer.json`, so the daemon's *GGUF* load path (`load_gguf`) has
//! end-to-end coverage too (F-2026-085), not just the loader crate's unit tests.
//!
//! `TinyModelDir::new_moe` / `new_moe_gguf` write **mixture-of-experts** variants
//! — each layer's FFN is a router + expert bank (safetensors: per-expert
//! `mlp.experts.{e}.*`; GGUF: stacked `ffn_*_exps` + expert-count metadata) —
//! so the daemon's model-load-and-generate path has end-to-end MoE coverage
//! across both checkpoint formats (MoE Increments 2–3).

use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

// The tiny Llama-shaped geometry (mirrors the safetensors-loader `fixture()`).
const MODEL_DIM: usize = 8;
const N_LAYERS: usize = 2;
const N_Q_HEADS: usize = 2;
const N_KV_HEADS: usize = 1;
const HEAD_DIM: usize = 4;
const HIDDEN: usize = 16;
const VOCAB: usize = 256;

// MoE geometry for the mixture-of-experts fixtures (`*_moe_*`). A 4-expert,
// top-2 bank with a per-expert width distinct from the dense `HIDDEN`.
const MOE_N_EXPERTS: usize = 4;
const MOE_EXPERTS_PER_TOK: usize = 2;
const MOE_EXPERT_HIDDEN: usize = 12;

/// Deterministic pseudo-weights so the fixture is reproducible without `rand`.
fn seq(seed: f32, n: usize) -> Vec<f32> {
    (0..n)
        .map(|i| (((i as f32) + seed) * 0.017).sin() * 0.1)
        .collect()
}

/// Serialize named f32 tensors into the safetensors container format (header
/// length prefix + JSON header + packed little-endian f32 data).
fn write_safetensors(tensors: &[(String, Vec<usize>, Vec<f32>)]) -> Vec<u8> {
    let mut data = Vec::new();
    let mut entries = Vec::new();
    for (name, shape, vals) in tensors {
        let start = data.len();
        for v in vals {
            data.extend_from_slice(&v.to_le_bytes());
        }
        let end = data.len();
        let shape_json = shape
            .iter()
            .map(|d| d.to_string())
            .collect::<Vec<_>>()
            .join(",");
        entries.push(format!(
            "\"{name}\":{{\"dtype\":\"F32\",\"shape\":[{shape_json}],\"data_offsets\":[{start},{end}]}}"
        ));
    }
    let header = format!("{{{}}}", entries.join(","));
    let mut out = (header.len() as u64).to_le_bytes().to_vec();
    out.extend_from_slice(header.as_bytes());
    out.extend_from_slice(&data);
    out
}

/// The model weights as safetensors bytes.
pub(crate) fn safetensors_bytes() -> Vec<u8> {
    let qd = N_Q_HEADS * HEAD_DIM;
    let kvd = N_KV_HEADS * HEAD_DIM;
    let mut t: Vec<(String, Vec<usize>, Vec<f32>)> = vec![
        (
            "model.embed_tokens.weight".into(),
            vec![VOCAB, MODEL_DIM],
            seq(0.5, VOCAB * MODEL_DIM),
        ),
        (
            "model.norm.weight".into(),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ),
        (
            "lm_head.weight".into(),
            vec![VOCAB, MODEL_DIM],
            seq(0.9, VOCAB * MODEL_DIM),
        ),
    ];
    for i in 0..N_LAYERS {
        let base = 10.0 + i as f32 * 7.0;
        let p = |s: &str| format!("model.layers.{i}.{s}");
        t.push((
            p("self_attn.q_proj.weight"),
            vec![qd, MODEL_DIM],
            seq(base, qd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.k_proj.weight"),
            vec![kvd, MODEL_DIM],
            seq(base + 1.0, kvd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.v_proj.weight"),
            vec![kvd, MODEL_DIM],
            seq(base + 2.0, kvd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.o_proj.weight"),
            vec![MODEL_DIM, qd],
            seq(base + 3.0, MODEL_DIM * qd),
        ));
        t.push((
            p("mlp.gate_proj.weight"),
            vec![HIDDEN, MODEL_DIM],
            seq(base + 4.0, HIDDEN * MODEL_DIM),
        ));
        t.push((
            p("mlp.up_proj.weight"),
            vec![HIDDEN, MODEL_DIM],
            seq(base + 5.0, HIDDEN * MODEL_DIM),
        ));
        t.push((
            p("mlp.down_proj.weight"),
            vec![MODEL_DIM, HIDDEN],
            seq(base + 6.0, MODEL_DIM * HIDDEN),
        ));
        t.push((
            p("input_layernorm.weight"),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ));
        t.push((
            p("post_attention_layernorm.weight"),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ));
    }
    write_safetensors(&t)
}

/// The MoE weights as safetensors bytes — same attention half as
/// [`safetensors_bytes`], but each layer's FFN is a router (`mlp.gate.weight`)
/// plus per-expert `mlp.experts.{e}.{gate,up,down}_proj.weight` SwiGLUs (the
/// Qwen3-MoE / Mixtral layout). No dense `mlp.*_proj`, so a load that succeeds
/// proves the daemon assembled MoE blocks.
pub(crate) fn moe_safetensors_bytes() -> Vec<u8> {
    let qd = N_Q_HEADS * HEAD_DIM;
    let kvd = N_KV_HEADS * HEAD_DIM;
    let mut t: Vec<(String, Vec<usize>, Vec<f32>)> = vec![
        (
            "model.embed_tokens.weight".into(),
            vec![VOCAB, MODEL_DIM],
            seq(0.5, VOCAB * MODEL_DIM),
        ),
        (
            "model.norm.weight".into(),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ),
        (
            "lm_head.weight".into(),
            vec![VOCAB, MODEL_DIM],
            seq(0.9, VOCAB * MODEL_DIM),
        ),
    ];
    for i in 0..N_LAYERS {
        let base = 10.0 + i as f32 * 7.0;
        let p = |s: &str| format!("model.layers.{i}.{s}");
        t.push((
            p("self_attn.q_proj.weight"),
            vec![qd, MODEL_DIM],
            seq(base, qd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.k_proj.weight"),
            vec![kvd, MODEL_DIM],
            seq(base + 1.0, kvd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.v_proj.weight"),
            vec![kvd, MODEL_DIM],
            seq(base + 2.0, kvd * MODEL_DIM),
        ));
        t.push((
            p("self_attn.o_proj.weight"),
            vec![MODEL_DIM, qd],
            seq(base + 3.0, MODEL_DIM * qd),
        ));
        t.push((
            p("input_layernorm.weight"),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ));
        t.push((
            p("post_attention_layernorm.weight"),
            vec![MODEL_DIM],
            vec![1.0; MODEL_DIM],
        ));
        t.push((
            p("mlp.gate.weight"),
            vec![MOE_N_EXPERTS, MODEL_DIM],
            seq(base + 4.0, MOE_N_EXPERTS * MODEL_DIM),
        ));
        for e in 0..MOE_N_EXPERTS {
            let ep = |s: &str| format!("model.layers.{i}.mlp.experts.{e}.{s}");
            let eb = base + 5.0 + e as f32 * 3.0;
            t.push((
                ep("gate_proj.weight"),
                vec![MOE_EXPERT_HIDDEN, MODEL_DIM],
                seq(eb, MOE_EXPERT_HIDDEN * MODEL_DIM),
            ));
            t.push((
                ep("up_proj.weight"),
                vec![MOE_EXPERT_HIDDEN, MODEL_DIM],
                seq(eb + 1.0, MOE_EXPERT_HIDDEN * MODEL_DIM),
            ));
            t.push((
                ep("down_proj.weight"),
                vec![MODEL_DIM, MOE_EXPERT_HIDDEN],
                seq(eb + 2.0, MODEL_DIM * MOE_EXPERT_HIDDEN),
            ));
        }
    }
    write_safetensors(&t)
}

/// The MoE `config.json` — the dense fields plus `num_experts` /
/// `num_experts_per_tok` / `moe_intermediate_size`.
pub(crate) fn moe_config_json() -> String {
    format!(
        "{{\"hidden_size\":{MODEL_DIM},\"num_hidden_layers\":{N_LAYERS},\
         \"num_attention_heads\":{N_Q_HEADS},\"num_key_value_heads\":{N_KV_HEADS},\
         \"vocab_size\":{VOCAB},\"intermediate_size\":{HIDDEN},\"head_dim\":{HEAD_DIM},\
         \"rms_norm_eps\":1e-6,\"tie_word_embeddings\":false,\"rope_theta\":10000.0,\
         \"num_experts\":{MOE_N_EXPERTS},\"num_experts_per_tok\":{MOE_EXPERTS_PER_TOK},\
         \"moe_intermediate_size\":{MOE_EXPERT_HIDDEN}}}"
    )
}

/// The HF `config.json` (field names the loader's `Config::from_json` expects).
pub(crate) fn config_json() -> String {
    format!(
        "{{\"hidden_size\":{MODEL_DIM},\"num_hidden_layers\":{N_LAYERS},\
         \"num_attention_heads\":{N_Q_HEADS},\"num_key_value_heads\":{N_KV_HEADS},\
         \"vocab_size\":{VOCAB},\"intermediate_size\":{HIDDEN},\"head_dim\":{HEAD_DIM},\
         \"rms_norm_eps\":1e-6,\"tie_word_embeddings\":false,\"rope_theta\":10000.0}}"
    )
}

/// The GPT-2 byte→unicode alphabet (a bijection of every byte 0..=255 onto a
/// printable codepoint) — mirrors `sovereign_hf_tokenizer`'s own mapping so the
/// pieces we emit are exactly what its parser expects to round-trip.
fn byte_level_alphabet() -> [char; 256] {
    let mut bs: Vec<u32> = Vec::new();
    bs.extend((b'!' as u32)..=(b'~' as u32));
    bs.extend(0xA1u32..=0xAC);
    bs.extend(0xAEu32..=0xFF);
    let mut cs = bs.clone();
    let mut n = 0u32;
    for b in 0u32..256 {
        if !bs.contains(&b) {
            bs.push(b);
            cs.push(256 + n);
            n += 1;
        }
    }
    let mut enc = ['\0'; 256];
    for (b, c) in bs.iter().zip(cs.iter()) {
        enc[*b as usize] = char::from_u32(*c).expect("valid codepoint");
    }
    enc
}

/// A vocab-256 byte-level BPE `tokenizer.json` (no merges) — one piece per byte,
/// so it round-trips arbitrary ASCII/bytes and matches the model's 256 vocab.
pub(crate) fn tokenizer_json() -> Vec<u8> {
    let enc = byte_level_alphabet();
    let mut vocab = serde_json::Map::new();
    for (b, ch) in enc.iter().enumerate() {
        vocab.insert(ch.to_string(), serde_json::Value::from(b as u64));
    }
    let doc = serde_json::json!({
        "version": "1.0",
        "model": { "type": "BPE", "vocab": vocab, "merges": [] }
    });
    serde_json::to_vec(&doc).expect("tokenizer json serializes")
}

// ── GGUF fixture (F-2026-085 daemon-level coverage) ──────────────────────────
// The daemon's GGUF load path (`load_generator_from_dir` → `load_gguf`) had no
// daemon-level model-backed test — only the loader crate's unit tests. This builds
// a tiny, real GGUF container (metadata + F32 tensors, GGUF v3) the daemon loads,
// paired with a sidecar `tokenizer.json` (the daemon prefers a sidecar over the
// GGUF's embedded tokenizer). A minimal port of the loader's own `GgufWriter`.

const GGUF_MAGIC: u32 = 0x4655_4747; // "GGUF" little-endian
const GGML_F32: u32 = 0;

struct GgufWriter {
    kv: Vec<u8>,
    n_kv: u64,
    infos: Vec<u8>,
    n_tensors: u64,
    data: Vec<u8>,
}

impl GgufWriter {
    fn new() -> Self {
        Self {
            kv: vec![],
            n_kv: 0,
            infos: vec![],
            n_tensors: 0,
            data: vec![],
        }
    }
    fn gstr(buf: &mut Vec<u8>, s: &str) {
        buf.extend_from_slice(&(s.len() as u64).to_le_bytes());
        buf.extend_from_slice(s.as_bytes());
    }
    fn kv_u32(&mut self, key: &str, v: u32) {
        Self::gstr(&mut self.kv, key);
        self.kv.extend_from_slice(&4u32.to_le_bytes()); // UINT32
        self.kv.extend_from_slice(&v.to_le_bytes());
        self.n_kv += 1;
    }
    fn kv_f32(&mut self, key: &str, v: f32) {
        Self::gstr(&mut self.kv, key);
        self.kv.extend_from_slice(&6u32.to_le_bytes()); // FLOAT32
        self.kv.extend_from_slice(&v.to_le_bytes());
        self.n_kv += 1;
    }
    fn kv_str(&mut self, key: &str, v: &str) {
        Self::gstr(&mut self.kv, key);
        self.kv.extend_from_slice(&8u32.to_le_bytes()); // STRING
        Self::gstr(&mut self.kv, v);
        self.n_kv += 1;
    }
    /// Add an F32 tensor with the given `ne` dims (fastest-varying first).
    fn tensor_f32(&mut self, name: &str, dims: &[usize], vals: &[f32]) {
        Self::gstr(&mut self.infos, name);
        self.infos
            .extend_from_slice(&(dims.len() as u32).to_le_bytes());
        for &d in dims {
            self.infos.extend_from_slice(&(d as u64).to_le_bytes());
        }
        self.infos.extend_from_slice(&GGML_F32.to_le_bytes());
        self.infos
            .extend_from_slice(&(self.data.len() as u64).to_le_bytes());
        for &v in vals {
            self.data.extend_from_slice(&v.to_le_bytes());
        }
        while self.data.len() % 32 != 0 {
            self.data.push(0);
        }
        self.n_tensors += 1;
    }
    fn finish(self) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&GGUF_MAGIC.to_le_bytes());
        out.extend_from_slice(&3u32.to_le_bytes()); // version
        out.extend_from_slice(&self.n_tensors.to_le_bytes());
        out.extend_from_slice(&self.n_kv.to_le_bytes());
        out.extend_from_slice(&self.kv);
        out.extend_from_slice(&self.infos);
        while out.len() % 32 != 0 {
            out.push(0);
        }
        out.extend_from_slice(&self.data);
        out
    }
}

/// A tiny llama-architecture GGUF (1 layer, `model_dim` 4, 2 heads, vocab 256 to
/// match the sidecar byte-level tokenizer), deterministic F32 weights. The daemon
/// derives its hyperparameters from the GGUF metadata (no config.json needed).
pub(crate) fn gguf_bytes() -> Vec<u8> {
    let md = 4usize;
    let heads = 2usize;
    let hidden = 8usize;
    let vocab = VOCAB; // 256, matches the sidecar tokenizer
    let mut w = GgufWriter::new();
    w.kv_str("general.architecture", "llama");
    w.kv_u32("llama.embedding_length", md as u32);
    w.kv_u32("llama.block_count", 1);
    w.kv_u32("llama.attention.head_count", heads as u32);
    w.kv_u32("llama.attention.head_count_kv", heads as u32);
    w.kv_u32("llama.feed_forward_length", hidden as u32);
    w.kv_f32("llama.attention.layer_norm_rms_epsilon", 1e-5);
    w.kv_f32("llama.rope.freq_base", 500000.0);
    let e = |scale: f32, n: usize| seq(scale, n);
    w.tensor_f32("token_embd.weight", &[md, vocab], &e(0.5, md * vocab));
    w.tensor_f32("output_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("output.weight", &[md, vocab], &e(0.9, md * vocab));
    w.tensor_f32("blk.0.attn_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("blk.0.ffn_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("blk.0.attn_q.weight", &[md, md], &e(10.0, md * md));
    w.tensor_f32("blk.0.attn_k.weight", &[md, md], &e(11.0, md * md));
    w.tensor_f32("blk.0.attn_v.weight", &[md, md], &e(12.0, md * md));
    w.tensor_f32("blk.0.attn_output.weight", &[md, md], &e(13.0, md * md));
    w.tensor_f32(
        "blk.0.ffn_gate.weight",
        &[md, hidden],
        &e(14.0, hidden * md),
    );
    w.tensor_f32("blk.0.ffn_up.weight", &[md, hidden], &e(15.0, hidden * md));
    w.tensor_f32(
        "blk.0.ffn_down.weight",
        &[hidden, md],
        &e(16.0, md * hidden),
    );
    w.finish()
}

/// A tiny llama-architecture **MoE** GGUF: same shape as [`gguf_bytes`] but the
/// FFN is a router (`ffn_gate_inp`) + stacked expert tensors
/// (`ffn_{gate,up,down}_exps`, expert-major in ne order) with the expert counts
/// in metadata. No dense `ffn_{gate,up,down}`, so a load that runs proves the
/// daemon assembled MoE blocks from GGUF.
pub(crate) fn moe_gguf_bytes() -> Vec<u8> {
    let md = 4usize;
    let heads = 2usize;
    let hidden = 8usize; // dense feed_forward_length (metadata-required)
    let ehid = 6usize; // per-expert width
    let n_exp = MOE_N_EXPERTS;
    let vocab = VOCAB; // 256, matches the sidecar tokenizer
    let mut w = GgufWriter::new();
    w.kv_str("general.architecture", "llama");
    w.kv_u32("llama.embedding_length", md as u32);
    w.kv_u32("llama.block_count", 1);
    w.kv_u32("llama.attention.head_count", heads as u32);
    w.kv_u32("llama.attention.head_count_kv", heads as u32);
    w.kv_u32("llama.feed_forward_length", hidden as u32);
    w.kv_f32("llama.attention.layer_norm_rms_epsilon", 1e-5);
    w.kv_f32("llama.rope.freq_base", 500000.0);
    w.kv_u32("llama.expert_count", n_exp as u32);
    w.kv_u32("llama.expert_used_count", MOE_EXPERTS_PER_TOK as u32);
    w.kv_u32("llama.expert_feed_forward_length", ehid as u32);
    let e = |scale: f32, n: usize| seq(scale, n);
    w.tensor_f32("token_embd.weight", &[md, vocab], &e(0.5, md * vocab));
    w.tensor_f32("output_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("output.weight", &[md, vocab], &e(0.9, md * vocab));
    w.tensor_f32("blk.0.attn_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("blk.0.ffn_norm.weight", &[md], &vec![1.0f32; md]);
    w.tensor_f32("blk.0.attn_q.weight", &[md, md], &e(10.0, md * md));
    w.tensor_f32("blk.0.attn_k.weight", &[md, md], &e(11.0, md * md));
    w.tensor_f32("blk.0.attn_v.weight", &[md, md], &e(12.0, md * md));
    w.tensor_f32("blk.0.attn_output.weight", &[md, md], &e(13.0, md * md));
    w.tensor_f32(
        "blk.0.ffn_gate_inp.weight",
        &[md, n_exp],
        &e(14.0, n_exp * md),
    );
    w.tensor_f32(
        "blk.0.ffn_gate_exps.weight",
        &[md, ehid, n_exp],
        &e(15.0, n_exp * ehid * md),
    );
    w.tensor_f32(
        "blk.0.ffn_up_exps.weight",
        &[md, ehid, n_exp],
        &e(16.0, n_exp * ehid * md),
    );
    w.tensor_f32(
        "blk.0.ffn_down_exps.weight",
        &[ehid, md, n_exp],
        &e(17.0, n_exp * md * ehid),
    );
    w.finish()
}

/// A temp model dir that removes itself on drop. Writes the loadable files.
pub(crate) struct TinyModelDir {
    dir: PathBuf,
}

static COUNTER: AtomicU64 = AtomicU64::new(0);

impl TinyModelDir {
    /// Materialize the safetensors fixture (config.json + model.safetensors +
    /// tokenizer.json) into a fresh unique temp dir.
    pub(crate) fn new() -> std::io::Result<Self> {
        let dir = Self::fresh_dir()?;
        std::fs::write(dir.join("config.json"), config_json())?;
        std::fs::write(dir.join("model.safetensors"), safetensors_bytes())?;
        std::fs::write(dir.join("tokenizer.json"), tokenizer_json())?;
        Ok(Self { dir })
    }

    /// Materialize the GGUF fixture (model.gguf + a sidecar tokenizer.json) — the
    /// daemon derives hyperparameters from the GGUF metadata, no config.json.
    pub(crate) fn new_gguf() -> std::io::Result<Self> {
        let dir = Self::fresh_dir()?;
        std::fs::write(dir.join("model.gguf"), gguf_bytes())?;
        std::fs::write(dir.join("tokenizer.json"), tokenizer_json())?;
        Ok(Self { dir })
    }

    /// Materialize the **MoE** safetensors fixture (moe config.json +
    /// model.safetensors + tokenizer.json) — a router + per-expert bank per layer.
    pub(crate) fn new_moe() -> std::io::Result<Self> {
        let dir = Self::fresh_dir()?;
        std::fs::write(dir.join("config.json"), moe_config_json())?;
        std::fs::write(dir.join("model.safetensors"), moe_safetensors_bytes())?;
        std::fs::write(dir.join("tokenizer.json"), tokenizer_json())?;
        Ok(Self { dir })
    }

    /// Materialize the **MoE** GGUF fixture (model.gguf with stacked expert
    /// tensors + expert metadata, + a sidecar tokenizer.json).
    pub(crate) fn new_moe_gguf() -> std::io::Result<Self> {
        let dir = Self::fresh_dir()?;
        std::fs::write(dir.join("model.gguf"), moe_gguf_bytes())?;
        std::fs::write(dir.join("tokenizer.json"), tokenizer_json())?;
        Ok(Self { dir })
    }

    fn fresh_dir() -> std::io::Result<PathBuf> {
        let uniq = format!(
            "sovereign-tiny-model-{}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        );
        let dir = std::env::temp_dir().join(uniq);
        std::fs::create_dir_all(&dir)?;
        Ok(dir)
    }

    pub(crate) fn path_str(&self) -> String {
        self.dir.to_string_lossy().into_owned()
    }
}

impl Drop for TinyModelDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}
