//! `gguf` — load an **already-quantized GGUF checkpoint** from disk (F-2026-085).
//!
//! The sibling safetensors path loads dense F32/F16/BF16 weights and quantizes
//! them in-memory. A GGUF file is the other direction: the weights are ALREADY
//! quantized on disk (Q4_K / Q8_0 / …), so a 7B is ~4 GB (Q4_K_M) instead of
//! ~28 GB f32. This module parses the GGUF container, **dequantizes** each tensor
//! back to `f32`, derives a [`Config`] from the GGUF metadata, and feeds the
//! result through the SAME block-assembly path
//! ([`MhaDecoderBlock::from_weights`] + `.with_rope`) the safetensors loader uses
//! — so RoPE (SDD-950), the tokenizer, and the runtime stack are all reused.
//!
//! Sovereignty-clean: pure Rust, `unsafe_code = "forbid"` (all reads are
//! bounds-checked little-endian), only `half` for the f16 block scales.
//!
//! Supported quant types: the dense `F32`/`F16`, the legacy round-to-nearest
//! quants `Q4_0`/`Q4_1`/`Q5_0`/`Q5_1`/`Q8_0`/`Q8_1`, and the k-quants
//! `Q2_K`/`Q3_K`/`Q4_K`/`Q5_K`/`Q6_K`. That covers every mainstream GGUF weight
//! encoding — a `Q4_K_M` mixes Q4_K + Q6_K, `Q5_K_M` mixes Q5_K + Q6_K, the
//! legacy `Q4_0`/`Q5_1` files are single-type, etc. Each kernel is byte-exact
//! against the ggml `dequantize_row_*` reference (see the fixtures in `tests`).
//! Deprecated (`Q4_2`/`Q4_3`) and intermediate (`Q8_K`) types are rejected with
//! a clear error, not mis-decoded.
//!
//! **q/k permutation:** unlike HF safetensors (rotate-half convention, permuted
//! by [`permute_qk_hf_to_interleaved`]), GGUF stores q/k already in the runtime's
//! **interleaved** RoPE convention — so GGUF q/k are fed through verbatim, with
//! NO permutation. Applying the safetensors permute here would corrupt rotation.
//!
//! **Mixture-of-experts (MoE Increment 3):** when the GGUF metadata declares
//! `<arch>.expert_count > 1`, each layer's FFN is assembled as a MoE bank. GGUF
//! stores the experts as one stacked 3-D tensor each —
//! `blk.{i}.ffn_{gate,up,down}_exps.weight`, expert-major in `ne` order — plus a
//! router `blk.{i}.ffn_gate_inp.weight`; every expert quantizes back to `f32`
//! and slices out as a contiguous per-expert matrix, feeding
//! [`MhaDecoderBlock::from_weights_moe`]. Top-k is `expert_used_count`, the
//! per-expert width `expert_feed_forward_length`. This is the on-card quantized
//! path for the Qwen3-30B-A3B / Mixtral / GPT-OSS class (their `.gguf` builds;
//! llama.cpp de-interleaves GPT-OSS's fused gate_up into separate
//! `ffn_{gate,up}_exps` at conversion, so those load through this same path).
//! MoE-vs-dense is decided **per layer** by expert-tensor presence
//! (`ffn_gate_exps.weight`), so a model that interleaves dense and sparse layers
//! assembles each layer correctly. When a MoE layer additionally carries expert
//! biases (`ffn_{gate,up,down}_exps.bias` + `ffn_gate_inp.bias`), it is built as
//! a **GPT-OSS** block — per-expert + router biases and the clamped-α SwiGLU
//! activation — via [`MhaDecoderBlock::from_weights_moe_gpt_oss`]. GPT-OSS's
//! attention extras load too when present: the q/k/v/o projection biases
//! (`blk.{i}.attn_{q,k,v,output}.bias`) and the per-head attention sink
//! (`blk.{i}.attn_sinks`). YaRN threads through the shared `rope_scaling` path.
//! Per-layer **sliding-window** attention also wires: the span comes from
//! `<arch>.attention.sliding_window`, and — since the GGUF omits the per-layer
//! pattern — GPT-OSS's interleaved `layer_types` (sliding on even layers, full on
//! odd; llama.cpp's `set_swa_pattern(2)`) is synthesized so each block chains
//! `with_sliding_window` on its sliding layers. A bare span with no gpt-oss
//! signal applies uniformly (Mistral-style SWA). The remaining GPT-OSS piece is
//! the **MXFP4** dequant kernel for the safetensors release (the GGUF path uses
//! standard k-quants and sidesteps it).

use std::collections::BTreeMap;

use sovereign_decoder_layer::{DecoderLayer, LayerStack};
use sovereign_mha_block::{
    GptOssExpertBias, GptOssMoeWeights, MhaBlockWeights, MhaDecoderBlock, MoeBlockWeights,
    MoeExpertWeights,
};
use sovereign_quant_model::QuantModel;
use sovereign_rmsnorm::RmsNorm;

use crate::{Config, LoaderError, Precision, Sampler, elems};

const GGUF_MAGIC: u32 = 0x4655_4747; // "GGUF" little-endian
const DEFAULT_ALIGNMENT: usize = 32;

/// GPT-OSS FFN activation constants (fixed across the released 20b / 120b
/// checkpoints): the GLU gate scale α (the sigmoid-GELU approximation) and the
/// `swiglu_limit` clamp bound. Applied when a MoE layer carries expert biases.
const GPT_OSS_ALPHA: f32 = 1.702;
const GPT_OSS_SWIGLU_LIMIT: f32 = 7.0;

// ggml_type enum values. The full weight-bearing set is decoded: the legacy
// "type-0/1" quants (Q4_0/Q4_1/Q5_0/Q5_1/Q8_0/Q8_1) and the k-quants
// (Q2_K/Q3_K/Q4_K/Q5_K/Q6_K). Types 4/5 (deprecated Q4_2/Q4_3) and Q8_K (15,
// an intermediate never stored as weights) are intentionally unsupported.
const GGML_F32: u32 = 0;
const GGML_F16: u32 = 1;
const GGML_Q4_0: u32 = 2;
const GGML_Q4_1: u32 = 3;
const GGML_Q5_0: u32 = 6;
const GGML_Q5_1: u32 = 7;
const GGML_Q8_0: u32 = 8;
const GGML_Q8_1: u32 = 9;
const GGML_Q2_K: u32 = 10;
const GGML_Q3_K: u32 = 11;
const GGML_Q4_K: u32 = 12;
const GGML_Q5_K: u32 = 13;
const GGML_Q6_K: u32 = 14;

const QK_K: usize = 256;

// ── little-endian cursor (bounds-checked; no unsafe) ─────────────────────────

struct Cur<'a> {
    b: &'a [u8],
    p: usize,
}

impl<'a> Cur<'a> {
    fn new(b: &'a [u8]) -> Self {
        Self { b, p: 0 }
    }
    fn take(&mut self, n: usize) -> Result<&'a [u8], LoaderError> {
        let end = self
            .p
            .checked_add(n)
            .ok_or_else(|| LoaderError::Truncated("gguf read overflows".into()))?;
        if end > self.b.len() {
            return Err(LoaderError::Truncated(format!(
                "gguf truncated: need {n} bytes at offset {}, only {} left",
                self.p,
                self.b.len().saturating_sub(self.p)
            )));
        }
        let s = &self.b[self.p..end];
        self.p = end;
        Ok(s)
    }
    fn u32(&mut self) -> Result<u32, LoaderError> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn u64(&mut self) -> Result<u64, LoaderError> {
        Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    fn i8(&mut self) -> Result<i8, LoaderError> {
        Ok(self.take(1)?[0] as i8)
    }
    fn u8(&mut self) -> Result<u8, LoaderError> {
        Ok(self.take(1)?[0])
    }
    fn f32(&mut self) -> Result<f32, LoaderError> {
        Ok(f32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn f64(&mut self) -> Result<f64, LoaderError> {
        Ok(f64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    /// A GGUF string: u64 length + that many UTF-8 bytes.
    fn gstr(&mut self) -> Result<String, LoaderError> {
        let n = self.u64()? as usize;
        let s = self.take(n)?;
        Ok(String::from_utf8_lossy(s).into_owned())
    }
}

// ── metadata value ───────────────────────────────────────────────────────────

/// A parsed GGUF metadata value. Scalars back the [`Config`] derivation; string
/// and numeric arrays are retained (not just skipped) so the **embedded
/// tokenizer** (`tokenizer.ggml.tokens` / `.merges` / `.token_type` / `.scores`)
/// can be extracted — a GGUF that carries its own tokenizer loads standalone,
/// with no sidecar `tokenizer.json`.
#[derive(Debug, Clone)]
enum MetaValue {
    U(u64),
    I(i64),
    F(f64),
    // Parsed for completeness (e.g. tokenizer bool flags); the Config
    // derivation needs no bool today, so the payload is intentionally unread.
    #[allow(dead_code)]
    Bool(bool),
    Str(String),
    /// A `STRING` array — the tokenizer's token pieces and merge rules.
    StrArray(Vec<String>),
    /// An integer array (any int/bool element type, widened to `i64`) — the
    /// tokenizer's `token_type` lanes.
    IntArray(Vec<i64>),
    /// A float array — the tokenizer's SentencePiece `scores`. Retained so the
    /// array parse stays lossless; the byte-level BPE path needs no scores, so
    /// the payload is intentionally unread today.
    #[allow(dead_code)]
    FloatArray(Vec<f64>),
    /// A nested / otherwise-unmodeled array, retained only as a marker (its
    /// contents were skipped so the tensor table is still reached).
    Array,
}

impl MetaValue {
    fn as_u64(&self) -> Option<u64> {
        match self {
            MetaValue::U(v) => Some(*v),
            MetaValue::I(v) if *v >= 0 => Some(*v as u64),
            _ => None,
        }
    }
    fn as_f32(&self) -> Option<f32> {
        match self {
            MetaValue::F(v) => Some(*v as f32),
            MetaValue::U(v) => Some(*v as f32),
            MetaValue::I(v) => Some(*v as f32),
            _ => None,
        }
    }
    fn as_str(&self) -> Option<&str> {
        match self {
            MetaValue::Str(s) => Some(s),
            _ => None,
        }
    }
}

fn read_meta_value(cur: &mut Cur) -> Result<MetaValue, LoaderError> {
    // GGUF metadata value_type enum.
    let t = cur.u32()?;
    Ok(match t {
        0 => MetaValue::U(cur.u8()? as u64), // UINT8
        1 => MetaValue::I(cur.i8()? as i64), // INT8
        2 => MetaValue::U(u16::from_le_bytes(cur.take(2)?.try_into().unwrap()) as u64), // UINT16
        3 => MetaValue::I(i16::from_le_bytes(cur.take(2)?.try_into().unwrap()) as i64), // INT16
        4 => MetaValue::U(cur.u32()? as u64), // UINT32
        5 => MetaValue::I(cur.u32()? as i32 as i64), // INT32
        6 => MetaValue::F(cur.f32()? as f64), // FLOAT32
        7 => MetaValue::Bool(cur.u8()? != 0), // BOOL
        8 => MetaValue::Str(cur.gstr()?),    // STRING
        9 => read_array(cur)?,
        10 => MetaValue::U(cur.u64()?),        // UINT64
        11 => MetaValue::I(cur.u64()? as i64), // INT64
        12 => MetaValue::F(cur.f64()?),        // FLOAT64
        other => {
            return Err(LoaderError::Truncated(format!(
                "gguf: unknown metadata value type {other}"
            )));
        }
    })
}

/// Read a GGUF `ARRAY` value (element_type u32, len u64, then the elements).
/// String and numeric element arrays are retained (the tokenizer needs them);
/// nested / unmodeled element arrays are skipped to a bare marker. Capacity is
/// clamped so a corrupt length can't force a huge up-front allocation — the
/// element loop is still bounds-checked and errors on a truncated file.
fn read_array(cur: &mut Cur) -> Result<MetaValue, LoaderError> {
    const CAP_CLAMP: usize = 1 << 20;
    let elem_t = cur.u32()?;
    let n = cur.u64()? as usize;
    Ok(match elem_t {
        8 => {
            let mut v = Vec::with_capacity(n.min(CAP_CLAMP));
            for _ in 0..n {
                v.push(cur.gstr()?);
            }
            MetaValue::StrArray(v)
        }
        6 => {
            let mut v = Vec::with_capacity(n.min(CAP_CLAMP));
            for _ in 0..n {
                v.push(cur.f32()? as f64);
            }
            MetaValue::FloatArray(v)
        }
        12 => {
            let mut v = Vec::with_capacity(n.min(CAP_CLAMP));
            for _ in 0..n {
                v.push(cur.f64()?);
            }
            MetaValue::FloatArray(v)
        }
        // any integer / bool element type → widen to i64
        0 | 1 | 2 | 3 | 4 | 5 | 7 | 10 | 11 => {
            let mut v = Vec::with_capacity(n.min(CAP_CLAMP));
            for _ in 0..n {
                v.push(read_int_elem(cur, elem_t)?);
            }
            MetaValue::IntArray(v)
        }
        9 => {
            // nested array — skip each element (we never need arrays-of-arrays).
            for _ in 0..n {
                skip_typed_value(cur, 9)?;
            }
            MetaValue::Array
        }
        other => {
            return Err(LoaderError::Truncated(format!(
                "gguf: unknown array element type {other}"
            )));
        }
    })
}

/// Read one integer/bool array element of primitive type `t`, widened to `i64`.
fn read_int_elem(cur: &mut Cur, t: u32) -> Result<i64, LoaderError> {
    Ok(match t {
        0 => cur.u8()? as i64,
        1 => cur.i8()? as i64,
        2 => u16::from_le_bytes(cur.take(2)?.try_into().unwrap()) as i64,
        3 => i16::from_le_bytes(cur.take(2)?.try_into().unwrap()) as i64,
        4 => cur.u32()? as i64,
        5 => cur.u32()? as i32 as i64,
        7 => (cur.u8()? != 0) as i64,
        10 => cur.u64()? as i64,
        11 => cur.u64()? as i64,
        _ => {
            return Err(LoaderError::Truncated(format!(
                "gguf: non-integer array element type {t}"
            )));
        }
    })
}

/// Skip one metadata value of a known primitive type (array element path).
fn skip_typed_value(cur: &mut Cur, t: u32) -> Result<(), LoaderError> {
    match t {
        0 | 1 | 7 => {
            cur.take(1)?;
        }
        2..=3 => {
            cur.take(2)?;
        }
        4..=6 => {
            cur.take(4)?;
        }
        8 => {
            cur.gstr()?;
        }
        10..=12 => {
            cur.take(8)?;
        }
        9 => {
            // nested array
            let et = cur.u32()?;
            let n = cur.u64()? as usize;
            for _ in 0..n {
                skip_typed_value(cur, et)?;
            }
        }
        other => {
            return Err(LoaderError::Truncated(format!(
                "gguf: unknown array element type {other}"
            )));
        }
    }
    Ok(())
}

// ── tensor info ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct TensorInfo {
    dims: Vec<usize>,
    ggml_type: u32,
    offset: usize,
}

impl TensorInfo {
    fn elems(&self) -> usize {
        self.dims.iter().product()
    }
}

/// The tokenizer embedded in a GGUF checkpoint's metadata. A modern GGUF (Llama-3,
/// Qwen2, Mistral, …) carries its full vocab + merges here, so no sidecar
/// `tokenizer.json` is required to run it.
///
/// `model` names the segmentation family — `"gpt2"` (byte-level BPE, the
/// mainstream case) or `"llama"` (SentencePiece). `tokens[i]` is the piece for id
/// `i`; `token_types[i]` classifies it (1 normal, 2 unknown, 3 control, 4
/// user-defined, 6 byte). `merges` are the ranked BPE merge rules ("left right").
#[derive(Debug, Clone)]
pub struct GgufTokenizer {
    /// The ggml tokenizer model name (`gpt2` / `llama` / `bpe`).
    pub model: String,
    /// id → token piece (index is the id).
    pub tokens: Vec<String>,
    /// Ranked BPE merge rules, each `"left right"` (rank = position).
    pub merges: Vec<String>,
    /// Per-token type lane (ggml `llama_token_type`); empty if absent.
    pub token_types: Vec<i32>,
    /// Beginning-of-sequence token id, if declared.
    pub bos: Option<u32>,
    /// End-of-sequence token id, if declared.
    pub eos: Option<u32>,
}

impl GgufTokenizer {
    /// True when this is a byte-level BPE tokenizer (`gpt2`/`bpe`) — the family
    /// the runtime [`sovereign_hf_tokenizer`] GPT-2 path handles directly.
    #[must_use]
    pub fn is_byte_level_bpe(&self) -> bool {
        self.model == "gpt2" || self.model == "bpe"
    }

    /// Token ids classified as control/user-defined/unknown (ggml types 2/3/4) —
    /// the tokens a byte-level tokenizer must treat as atomic "special" pieces
    /// rather than BPE-merge candidates.
    #[must_use]
    pub fn special_ids(&self) -> Vec<u32> {
        self.token_types
            .iter()
            .enumerate()
            .filter(|&(_, &t)| t == 2 || t == 3 || t == 4)
            .map(|(i, _)| i as u32)
            .collect()
    }
}

/// A parsed GGUF file: metadata + tensor table + a slice into the tensor data
/// blob (which starts at the alignment-padded end of the tensor-info section).
pub struct GgufFile<'a> {
    meta: BTreeMap<String, MetaValue>,
    infos: BTreeMap<String, TensorInfo>,
    data: &'a [u8],
    data_start: usize,
}

impl<'a> GgufFile<'a> {
    /// Parse a GGUF byte stream (header + metadata + tensor infos + data blob).
    pub fn parse(bytes: &'a [u8]) -> Result<Self, LoaderError> {
        let mut cur = Cur::new(bytes);
        let magic = cur.u32()?;
        if magic != GGUF_MAGIC {
            return Err(LoaderError::Truncated(format!(
                "not a GGUF file (magic {magic:#010x}, want {GGUF_MAGIC:#010x})"
            )));
        }
        let version = cur.u32()?;
        if version != 2 && version != 3 {
            return Err(LoaderError::Truncated(format!(
                "unsupported GGUF version {version} (support 2/3)"
            )));
        }
        let n_tensors = cur.u64()? as usize;
        let n_kv = cur.u64()? as usize;

        let mut meta = BTreeMap::new();
        for _ in 0..n_kv {
            let key = cur.gstr()?;
            let val = read_meta_value(&mut cur)?;
            meta.insert(key, val);
        }

        let mut infos = BTreeMap::new();
        for _ in 0..n_tensors {
            let name = cur.gstr()?;
            let n_dims = cur.u32()? as usize;
            if n_dims > 4 {
                return Err(LoaderError::Truncated(format!(
                    "gguf tensor `{name}` has {n_dims} dims (max 4)"
                )));
            }
            let mut dims = Vec::with_capacity(n_dims);
            for _ in 0..n_dims {
                dims.push(cur.u64()? as usize);
            }
            let ggml_type = cur.u32()?;
            let offset = cur.u64()? as usize;
            infos.insert(
                name,
                TensorInfo {
                    dims,
                    ggml_type,
                    offset,
                },
            );
        }

        // The tensor data starts at the next `alignment` boundary after the
        // tensor-info section. `general.alignment` overrides the 32 default.
        let alignment = meta
            .get("general.alignment")
            .and_then(MetaValue::as_u64)
            .map_or(DEFAULT_ALIGNMENT, |v| v as usize)
            .max(1);
        let after_infos = cur.p;
        let data_start = after_infos.div_ceil(alignment) * alignment;
        if data_start > bytes.len() {
            return Err(LoaderError::Truncated(
                "gguf: aligned data section starts past end of file".into(),
            ));
        }
        Ok(Self {
            meta,
            infos,
            data: bytes,
            data_start,
        })
    }

    fn meta_u64(&self, key: &str) -> Option<u64> {
        self.meta.get(key).and_then(MetaValue::as_u64)
    }
    fn meta_f32(&self, key: &str) -> Option<f32> {
        self.meta.get(key).and_then(MetaValue::as_f32)
    }
    fn meta_str_array(&self, key: &str) -> Option<&[String]> {
        match self.meta.get(key) {
            Some(MetaValue::StrArray(v)) => Some(v),
            _ => None,
        }
    }
    fn meta_int_array(&self, key: &str) -> Option<&[i64]> {
        match self.meta.get(key) {
            Some(MetaValue::IntArray(v)) => Some(v),
            _ => None,
        }
    }

    /// Extract the embedded tokenizer, if this GGUF carries one
    /// (`tokenizer.ggml.tokens` present). Returns `None` for a weights-only GGUF
    /// (the caller then falls back to a sidecar `tokenizer.json`).
    #[must_use]
    pub fn tokenizer(&self) -> Option<GgufTokenizer> {
        let tokens = self.meta_str_array("tokenizer.ggml.tokens")?.to_vec();
        let model = self
            .meta
            .get("tokenizer.ggml.model")
            .and_then(MetaValue::as_str)
            .unwrap_or("")
            .to_string();
        let merges = self
            .meta_str_array("tokenizer.ggml.merges")
            .map(<[String]>::to_vec)
            .unwrap_or_default();
        let token_types = self
            .meta_int_array("tokenizer.ggml.token_type")
            .map(|v| v.iter().map(|&x| x as i32).collect())
            .unwrap_or_default();
        let bos = self
            .meta_u64("tokenizer.ggml.bos_token_id")
            .map(|v| v as u32);
        let eos = self
            .meta_u64("tokenizer.ggml.eos_token_id")
            .map(|v| v as u32);
        Some(GgufTokenizer {
            model,
            tokens,
            merges,
            token_types,
            bos,
            eos,
        })
    }

    /// The model architecture (`general.architecture`), e.g. `llama`, `qwen2`.
    pub fn architecture(&self) -> Option<&str> {
        self.meta
            .get("general.architecture")
            .and_then(MetaValue::as_str)
    }

    /// Whether a tensor by that exact name is present.
    #[must_use]
    pub fn has_tensor(&self, name: &str) -> bool {
        self.infos.contains_key(name)
    }

    /// The tensor names present.
    #[must_use]
    pub fn names(&self) -> Vec<&str> {
        self.infos.keys().map(String::as_str).collect()
    }

    fn info(&self, name: &str) -> Result<&TensorInfo, LoaderError> {
        self.infos
            .get(name)
            .ok_or_else(|| LoaderError::MissingTensor(name.to_string()))
    }

    /// Raw byte slice for a tensor (`[offset .. offset + byte_len]` inside the
    /// aligned data blob), bounds-checked against the file.
    fn tensor_bytes(&self, info: &TensorInfo) -> Result<&[u8], LoaderError> {
        let n = info.elems();
        let byte_len = type_byte_len(info.ggml_type, n)?;
        let a = self
            .data_start
            .checked_add(info.offset)
            .ok_or_else(|| LoaderError::Truncated("gguf tensor offset overflow".into()))?;
        let b = a
            .checked_add(byte_len)
            .ok_or_else(|| LoaderError::Truncated("gguf tensor length overflow".into()))?;
        if b > self.data.len() {
            return Err(LoaderError::Truncated(format!(
                "gguf tensor data [{a},{b}] out of range (file {} bytes)",
                self.data.len()
            )));
        }
        Ok(&self.data[a..b])
    }

    /// Decode a tensor to `f32` (dequantizing its quant type). Row-major, in the
    /// GGUF `ne` order — which for a 2-D weight is already `[out][in]` row-major,
    /// exactly what the block assembly expects.
    pub fn tensor_f32(&self, name: &str) -> Result<Vec<f32>, LoaderError> {
        let info = self.info(name)?;
        let n = info.elems();
        let raw = self.tensor_bytes(info)?;
        dequant(info.ggml_type, raw, n, name)
    }

    /// Decode a tensor and require exactly `expected` elements.
    fn tensor_exact(&self, name: &str, expected: usize) -> Result<Vec<f32>, LoaderError> {
        let v = self.tensor_f32(name)?;
        if v.len() != expected {
            return Err(LoaderError::ShapeMismatch {
                name: name.to_string(),
                expected,
                got: v.len(),
            });
        }
        Ok(v)
    }

    /// Build the runtime [`Config`] from GGUF metadata. Reads the arch-prefixed
    /// keys (`<arch>.embedding_length`, `.block_count`, `.attention.head_count`,
    /// …). `vocab` is derived from the token-embedding tensor's row count, and
    /// `tied` from the absence of an explicit `output.weight`.
    pub fn config(&self) -> Result<Config, LoaderError> {
        let arch = self
            .architecture()
            .ok_or_else(|| LoaderError::InvalidConfig("gguf: general.architecture missing".into()))?
            .to_string();
        let need = |k: &str| -> Result<u64, LoaderError> {
            self.meta_u64(&format!("{arch}.{k}"))
                .ok_or_else(|| LoaderError::InvalidConfig(format!("gguf: {arch}.{k} missing")))
        };
        let model_dim = need("embedding_length")? as usize;
        let n_layers = need("block_count")? as usize;
        let n_heads = need("attention.head_count")? as usize;
        let n_kv = self
            .meta_u64(&format!("{arch}.attention.head_count_kv"))
            .map_or(n_heads, |v| v as usize);
        let hidden = need("feed_forward_length")? as usize;
        let eps = self
            .meta_f32(&format!("{arch}.attention.layer_norm_rms_epsilon"))
            .unwrap_or(1e-5);
        let rope_theta = self
            .meta_f32(&format!("{arch}.rope.freq_base"))
            .unwrap_or(10000.0);
        // Explicit per-head dim (Qwen2/Llama-3.1 may set key_length); else derived.
        let head_dim = self
            .meta_u64(&format!("{arch}.attention.key_length"))
            .map(|v| v as usize);

        // vocab = rows of the token-embedding tensor. GGUF ne = [n_embd, n_vocab],
        // so dims[1] is n_vocab (fall back to output.weight rows if needed).
        let vocab = self
            .infos
            .get("token_embd.weight")
            .and_then(|t| t.dims.get(1).copied())
            .or_else(|| {
                self.infos
                    .get("output.weight")
                    .and_then(|t| t.dims.get(1).copied())
            })
            .ok_or_else(|| {
                LoaderError::InvalidConfig("gguf: cannot determine vocab size".into())
            })?;

        let tied = !self.infos.contains_key("output.weight");

        // MoE metadata: `<arch>.expert_count` (n_expert), `.expert_used_count`
        // (top-k), `.expert_feed_forward_length` (per-expert FFN width). Absent /
        // 0 experts ⇒ a dense model (fields stay `None`).
        let num_experts = self
            .meta_u64(&format!("{arch}.expert_count"))
            .map(|v| v as usize)
            .filter(|&n| n > 0);
        let num_experts_per_tok = self
            .meta_u64(&format!("{arch}.expert_used_count"))
            .map(|v| v as usize);
        let moe_intermediate_size = self
            .meta_u64(&format!("{arch}.expert_feed_forward_length"))
            .map(|v| v as usize);

        // Sliding-window attention: llama.cpp writes the span under
        // `<arch>.attention.sliding_window` (Mistral / Gemma-2 / GPT-OSS local
        // attention). The per-layer sliding-vs-full PATTERN is NOT in the GGUF —
        // llama.cpp derives it per-arch in code. GPT-OSS (LLM_ARCH_OPENAI_MOE)
        // uses `set_swa_pattern(2)`: alternating, sliding on even layers and full
        // on odd — which matches the released config.json's `layer_types` (24
        // layers, `sliding_attention` on even). We synthesize that here so the
        // shared `layer_types` machinery drives both loaders identically. GPT-OSS
        // is recognized the same way the FFN path recognizes it — by its
        // signature `attn_sinks` tensor (real gpt-oss GGUFs also set arch
        // `gpt-oss`, checked too). For any other arch that declares a span but no
        // pattern, `layer_types` stays `None` so the span applies uniformly (the
        // Mistral case). Models with no span key are unaffected.
        let sliding_window = self
            .meta_u64(&format!("{arch}.attention.sliding_window"))
            .map(|v| v as usize)
            .filter(|&w| w > 0);
        let is_gpt_oss = arch == "gpt-oss" || self.has_tensor("blk.0.attn_sinks");
        let layer_types = sliding_window.filter(|_| is_gpt_oss).map(|_| {
            (0..n_layers)
                .map(|l| {
                    if l % 2 == 0 {
                        "sliding_attention"
                    } else {
                        "full_attention"
                    }
                    .to_string()
                })
                .collect()
        });

        Ok(Config {
            model_dim,
            n_layers,
            n_heads,
            n_kv_heads: Some(n_kv),
            vocab,
            hidden,
            eps,
            tied,
            head_dim,
            rope_theta,
            rope_scaling: None,
            num_experts,
            num_experts_per_tok,
            moe_intermediate_size,
            // GGUF per-layer dense/MoE interleaving is detected by expert-tensor
            // presence at assembly time, not from config metadata.
            mlp_only_layers: None,
            decoder_sparse_step: None,
            sliding_window,
            layer_types,
        })
    }
}

// ── ggml type sizes ──────────────────────────────────────────────────────────

/// Byte length on disk for `n` elements of ggml type `t`.
fn type_byte_len(t: u32, n: usize) -> Result<usize, LoaderError> {
    let bad_block = |bs: usize| {
        LoaderError::Truncated(format!(
            "gguf: element count {n} not a multiple of block size {bs} for ggml type {t}"
        ))
    };
    Ok(match t {
        GGML_F32 => n * 4,
        GGML_F16 => n * 2,
        GGML_Q4_0 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 18 // f16 scale (2) + 16 packed nibbles
        }
        GGML_Q4_1 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 20 // d(2) + m(2) + 16 packed nibbles
        }
        GGML_Q5_0 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 22 // d(2) + qh(4) + 16 packed nibbles
        }
        GGML_Q5_1 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 24 // d(2) + m(2) + qh(4) + 16 packed nibbles
        }
        GGML_Q8_0 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 34 // f16 scale (2) + 32 int8
        }
        GGML_Q8_1 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 36 // d(2) + s(2) + 32 int8
        }
        GGML_Q2_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 84 // scales(16)+qs(64)+d(2)+dmin(2)
        }
        GGML_Q3_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 110 // hmask(32)+qs(64)+scales(12)+d(2)
        }
        GGML_Q4_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 144 // d(2)+dmin(2)+scales(12)+qs(128)
        }
        GGML_Q5_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 176 // d(2)+dmin(2)+scales(12)+qh(32)+qs(128)
        }
        GGML_Q6_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 210 // ql(128)+qh(64)+scales(16)+d(2)
        }
        other => {
            return Err(LoaderError::UnsupportedDtype {
                name: "<gguf tensor>".into(),
                dtype: format!(
                    "ggml type {other} (support F32/F16/Q4_0/Q4_1/Q5_0/Q5_1/\
                     Q8_0/Q8_1/Q2_K/Q3_K/Q4_K/Q5_K/Q6_K)"
                ),
            });
        }
    })
}

// ── dequant ──────────────────────────────────────────────────────────────────

fn f16(b: &[u8], off: usize) -> f32 {
    half::f16::from_bits(u16::from_le_bytes([b[off], b[off + 1]])).to_f32()
}

fn dequant(t: u32, raw: &[u8], n: usize, _name: &str) -> Result<Vec<f32>, LoaderError> {
    let mut out = Vec::with_capacity(n);
    match t {
        GGML_F32 => {
            for c in raw.chunks_exact(4) {
                out.push(f32::from_le_bytes(c.try_into().unwrap()));
            }
        }
        GGML_F16 => {
            for c in raw.chunks_exact(2) {
                out.push(half::f16::from_bits(u16::from_le_bytes(c.try_into().unwrap())).to_f32());
            }
        }
        GGML_Q8_0 => {
            for blk in raw.chunks_exact(34) {
                let d = f16(blk, 0);
                for &q in &blk[2..34] {
                    out.push(d * (q as i8) as f32);
                }
            }
        }
        GGML_Q4_0 => {
            for blk in raw.chunks_exact(18) {
                let d = f16(blk, 0);
                let qs = &blk[2..18];
                let mut lo = [0f32; 16];
                let mut hi = [0f32; 16];
                for (j, &byte) in qs.iter().enumerate() {
                    lo[j] = d * (((byte & 0x0F) as i32) - 8) as f32;
                    hi[j] = d * (((byte >> 4) as i32) - 8) as f32;
                }
                out.extend_from_slice(&lo);
                out.extend_from_slice(&hi);
            }
        }
        GGML_Q4_1 => {
            for blk in raw.chunks_exact(20) {
                let d = f16(blk, 0);
                let m = f16(blk, 2);
                let qs = &blk[4..20];
                let mut lo = [0f32; 16];
                let mut hi = [0f32; 16];
                for (j, &byte) in qs.iter().enumerate() {
                    lo[j] = d * (byte & 0x0F) as f32 + m;
                    hi[j] = d * (byte >> 4) as f32 + m;
                }
                out.extend_from_slice(&lo);
                out.extend_from_slice(&hi);
            }
        }
        GGML_Q5_0 => {
            for blk in raw.chunks_exact(22) {
                let d = f16(blk, 0);
                let qh = u32::from_le_bytes(blk[2..6].try_into().unwrap());
                let qs = &blk[6..22];
                let mut lo = [0f32; 16];
                let mut hi = [0f32; 16];
                for (j, &byte) in qs.iter().enumerate() {
                    // 5th bit of each quant lives in qh (low 16 bits → lo lane,
                    // bits 16..32 → hi lane).
                    let xh0 = (((qh >> j) << 4) & 0x10) as i32;
                    let xh1 = ((qh >> (j + 12)) & 0x10) as i32;
                    lo[j] = d * ((((byte & 0x0F) as i32) | xh0) - 16) as f32;
                    hi[j] = d * ((((byte >> 4) as i32) | xh1) - 16) as f32;
                }
                out.extend_from_slice(&lo);
                out.extend_from_slice(&hi);
            }
        }
        GGML_Q5_1 => {
            for blk in raw.chunks_exact(24) {
                let d = f16(blk, 0);
                let m = f16(blk, 2);
                let qh = u32::from_le_bytes(blk[4..8].try_into().unwrap());
                let qs = &blk[8..24];
                let mut lo = [0f32; 16];
                let mut hi = [0f32; 16];
                for (j, &byte) in qs.iter().enumerate() {
                    let xh0 = (((qh >> j) << 4) & 0x10) as i32;
                    let xh1 = ((qh >> (j + 12)) & 0x10) as i32;
                    lo[j] = d * (((byte & 0x0F) as i32) | xh0) as f32 + m;
                    hi[j] = d * (((byte >> 4) as i32) | xh1) as f32 + m;
                }
                out.extend_from_slice(&lo);
                out.extend_from_slice(&hi);
            }
        }
        GGML_Q8_1 => {
            // d(f16) + s(f16, the block sum — used only for dot-product speedups,
            // irrelevant to dequant) + 32 int8.
            for blk in raw.chunks_exact(36) {
                let d = f16(blk, 0);
                for &q in &blk[4..36] {
                    out.push(d * (q as i8) as f32);
                }
            }
        }
        GGML_Q2_K => {
            for blk in raw.chunks_exact(84) {
                dequant_q2_k(blk, &mut out);
            }
        }
        GGML_Q3_K => {
            for blk in raw.chunks_exact(110) {
                dequant_q3_k(blk, &mut out);
            }
        }
        GGML_Q4_K => {
            for blk in raw.chunks_exact(144) {
                dequant_q4_k(blk, &mut out);
            }
        }
        GGML_Q5_K => {
            for blk in raw.chunks_exact(176) {
                dequant_q5_k(blk, &mut out);
            }
        }
        GGML_Q6_K => {
            for blk in raw.chunks_exact(210) {
                dequant_q6_k(blk, &mut out);
            }
        }
        other => {
            return Err(LoaderError::UnsupportedDtype {
                name: _name.to_string(),
                dtype: format!("ggml type {other}"),
            });
        }
    }
    Ok(out)
}

/// 6-bit scale/min unpack for Q4_K (`get_scale_min_k4` from ggml, verbatim).
fn get_scale_min_k4(j: usize, sc: &[u8]) -> (u8, u8) {
    if j < 4 {
        (sc[j] & 63, sc[j + 4] & 63)
    } else {
        (
            (sc[j + 4] & 0x0F) | ((sc[j - 4] >> 6) << 4),
            (sc[j + 4] >> 4) | ((sc[j] >> 6) << 4),
        )
    }
}

/// Dequant one Q4_K superblock (256 values) — matches ggml `dequantize_row_q4_K`.
/// Layout: d(f16) dmin(f16) scales[12] qs[128].
fn dequant_q4_k(blk: &[u8], out: &mut Vec<f32>) {
    let d = f16(blk, 0);
    let dmin = f16(blk, 2);
    let scales = &blk[4..16];
    let qs = &blk[16..144];
    let mut is = 0usize;
    let mut q_off = 0usize;
    while q_off < 128 {
        let (sc1, m1) = get_scale_min_k4(is, scales);
        let (sc2, m2) = get_scale_min_k4(is + 1, scales);
        let d1 = d * sc1 as f32;
        let mn1 = dmin * m1 as f32;
        let d2 = d * sc2 as f32;
        let mn2 = dmin * m2 as f32;
        for l in 0..32 {
            out.push(d1 * (qs[q_off + l] & 0x0F) as f32 - mn1);
        }
        for l in 0..32 {
            out.push(d2 * (qs[q_off + l] >> 4) as f32 - mn2);
        }
        q_off += 32;
        is += 2;
    }
}

/// Dequant one Q2_K superblock (256 values) — matches ggml `dequantize_row_q2_K`.
/// Layout: scales[16] qs[64] d(f16) dmin(f16). Each value is 2-bit; the 4-bit
/// scale/min pair per 16-lane comes from a `scales` byte (low nibble = scale,
/// high nibble = min).
fn dequant_q2_k(blk: &[u8], out: &mut Vec<f32>) {
    let scales = &blk[0..16];
    let qs = &blk[16..80];
    let d = f16(blk, 80);
    let dmin = f16(blk, 82);
    let mut y = [0f32; QK_K];
    let mut yi = 0usize;
    let mut is = 0usize;
    let mut q_base = 0usize;
    for _ in 0..2 {
        // two 128-value halves
        let mut shift = 0u32;
        for _ in 0..4 {
            let sc = scales[is];
            is += 1;
            let dl = d * (sc & 0xF) as f32;
            let ml = dmin * (sc >> 4) as f32;
            for l in 0..16 {
                y[yi] = dl * ((qs[q_base + l] >> shift) & 3) as f32 - ml;
                yi += 1;
            }
            let sc = scales[is];
            is += 1;
            let dl = d * (sc & 0xF) as f32;
            let ml = dmin * (sc >> 4) as f32;
            for l in 0..16 {
                y[yi] = dl * ((qs[q_base + 16 + l] >> shift) & 3) as f32 - ml;
                yi += 1;
            }
            shift += 2;
        }
        q_base += 32;
    }
    out.extend_from_slice(&y);
}

/// Dequant one Q3_K superblock (256 values) — matches ggml `dequantize_row_q3_K`.
/// Layout: hmask[32] qs[64] scales[12] d(f16). The 12 scale bytes pack 16 signed
/// 6-bit scales (unpacked via the ggml `aux[]` bit-shuffle below); the 3rd quant
/// bit for each value lives in `hmask` (an UNSET hmask bit means subtract 4).
fn dequant_q3_k(blk: &[u8], out: &mut Vec<f32>) {
    const KMASK1: u32 = 0x0303_0303;
    const KMASK2: u32 = 0x0f0f_0f0f;
    let hmask = &blk[0..32];
    let qs = &blk[32..96];
    let d_all = f16(blk, 108);
    // Unpack the 12 packed bytes into 16 signed 6-bit scales (ggml aux shuffle).
    let mut aux = [
        u32::from_le_bytes(blk[96..100].try_into().unwrap()),
        u32::from_le_bytes(blk[100..104].try_into().unwrap()),
        u32::from_le_bytes(blk[104..108].try_into().unwrap()),
        0u32,
    ];
    let tmp = aux[2];
    aux[2] = ((aux[0] >> 4) & KMASK2) | (((tmp >> 4) & KMASK1) << 4);
    aux[3] = ((aux[1] >> 4) & KMASK2) | (((tmp >> 6) & KMASK1) << 4);
    aux[0] = (aux[0] & KMASK2) | ((tmp & KMASK1) << 4);
    aux[1] = (aux[1] & KMASK2) | (((tmp >> 2) & KMASK1) << 4);
    let mut scales = [0i8; 16];
    for (i, s) in scales.iter_mut().enumerate() {
        *s = ((aux[i / 4] >> ((i % 4) * 8)) & 0xff) as u8 as i8;
    }
    let mut y = [0f32; QK_K];
    let mut yi = 0usize;
    let mut is = 0usize;
    let mut m: u8 = 1;
    let mut q_base = 0usize;
    for _ in 0..2 {
        let mut shift = 0u32;
        for _ in 0..4 {
            let dl = d_all * (scales[is] as i32 - 32) as f32;
            is += 1;
            for l in 0..16 {
                let sub = if hmask[l] & m != 0 { 0 } else { 4 };
                y[yi] = dl * (((qs[q_base + l] >> shift) & 3) as i32 - sub) as f32;
                yi += 1;
            }
            let dl = d_all * (scales[is] as i32 - 32) as f32;
            is += 1;
            for l in 0..16 {
                let sub = if hmask[16 + l] & m != 0 { 0 } else { 4 };
                y[yi] = dl * (((qs[q_base + 16 + l] >> shift) & 3) as i32 - sub) as f32;
                yi += 1;
            }
            shift += 2;
            m <<= 1; // value overflow (128<<1) truncates to 0 — matches C
        }
        q_base += 32;
    }
    out.extend_from_slice(&y);
}

/// Dequant one Q5_K superblock (256 values) — matches ggml `dequantize_row_q5_K`.
/// Layout: d(f16) dmin(f16) scales[12] qh[32] qs[128]. Same 6-bit scale/min
/// unpack as Q4_K (`get_scale_min_k4`), plus a 5th high bit per value in `qh`.
fn dequant_q5_k(blk: &[u8], out: &mut Vec<f32>) {
    let d = f16(blk, 0);
    let dmin = f16(blk, 2);
    let scales = &blk[4..16];
    let qh = &blk[16..48];
    let ql = &blk[48..176];
    let mut y = [0f32; QK_K];
    let mut yi = 0usize;
    let mut is = 0usize;
    let mut u1: u8 = 1;
    let mut u2: u8 = 2;
    let mut ql_base = 0usize;
    for _ in 0..4 {
        // four 64-value groups
        let (sc1, m1) = get_scale_min_k4(is, scales);
        let d1 = d * sc1 as f32;
        let mn1 = dmin * m1 as f32;
        let (sc2, m2) = get_scale_min_k4(is + 1, scales);
        let d2 = d * sc2 as f32;
        let mn2 = dmin * m2 as f32;
        for l in 0..32 {
            let hi = if qh[l] & u1 != 0 { 16 } else { 0 };
            y[yi] = d1 * ((ql[ql_base + l] & 0x0F) as i32 + hi) as f32 - mn1;
            yi += 1;
        }
        for l in 0..32 {
            let hi = if qh[l] & u2 != 0 { 16 } else { 0 };
            y[yi] = d2 * ((ql[ql_base + l] >> 4) as i32 + hi) as f32 - mn2;
            yi += 1;
        }
        ql_base += 32;
        is += 2;
        u1 <<= 2; // value overflow truncates to 0 on the last group — matches C
        u2 <<= 2;
    }
    out.extend_from_slice(&y);
}

/// Dequant one Q6_K superblock (256 values) — matches ggml `dequantize_row_q6_K`.
/// Layout: ql[128] qh[64] scales[16] (i8) d(f16).
fn dequant_q6_k(blk: &[u8], out: &mut Vec<f32>) {
    let ql = &blk[0..128];
    let qh = &blk[128..192];
    let scales = &blk[192..208];
    let d = f16(blk, 208);
    // The output is written in 4 interleaved lanes; assemble into a local buffer
    // then push in order.
    let mut y = [0f32; QK_K];
    let mut yb = 0usize; // base into y (0, then 128)
    let mut qlb = 0usize;
    let mut qhb = 0usize;
    let mut scb = 0usize;
    for _ in 0..2 {
        for l in 0..32 {
            let is = l / 16;
            let q1 = (((ql[qlb + l] & 0x0F) as i32) | (((qh[qhb + l] & 3) as i32) << 4)) - 32;
            let q2 = (((ql[qlb + l + 32] & 0x0F) as i32)
                | ((((qh[qhb + l] >> 2) & 3) as i32) << 4))
                - 32;
            let q3 = (((ql[qlb + l] >> 4) as i32) | ((((qh[qhb + l] >> 4) & 3) as i32) << 4)) - 32;
            let q4 =
                (((ql[qlb + l + 32] >> 4) as i32) | ((((qh[qhb + l] >> 6) & 3) as i32) << 4)) - 32;
            y[yb + l] = d * (scales[scb + is] as i8) as f32 * q1 as f32;
            y[yb + l + 32] = d * (scales[scb + is + 2] as i8) as f32 * q2 as f32;
            y[yb + l + 64] = d * (scales[scb + is + 4] as i8) as f32 * q3 as f32;
            y[yb + l + 96] = d * (scales[scb + is + 6] as i8) as f32 * q4 as f32;
        }
        yb += 128;
        qlb += 64;
        qhb += 32;
        scb += 8;
    }
    out.extend_from_slice(&y);
}

// ── assembly ─────────────────────────────────────────────────────────────────

/// Load a GGUF checkpoint into a runnable [`QuantModel`] at the caller-chosen
/// runtime `precision` (the dequantized f32 weights are re-quantized to
/// `precision` by [`MhaDecoderBlock::from_weights`], exactly as the safetensors
/// path does). Derives the [`Config`] from GGUF metadata and threads the model's
/// real `rope_theta` into every block. GGUF q/k are already interleaved, so —
/// unlike the safetensors loader — NO q/k permutation is applied.
pub fn load_gguf(
    bytes: &[u8],
    precision: Precision,
    sampler: Sampler,
) -> Result<QuantModel, LoaderError> {
    let f = GgufFile::parse(bytes)?;
    let config = f.config()?;
    config.validate()?;

    let md = config.model_dim;
    let hd = config.head_dim();
    if hd % 2 != 0 {
        return Err(LoaderError::OddHeadDim(hd));
    }
    let nq = config.n_heads;
    let nkv = config.kv_heads();
    let hidden = config.hidden;
    let vocab = config.vocab;
    let q_dim = elems(&[nq, hd])?;
    let kv_dim = elems(&[nkv, hd])?;

    let mut layers: Vec<Box<dyn DecoderLayer>> = Vec::with_capacity(config.n_layers);
    for i in 0..config.n_layers {
        let t = |suffix: &str| format!("blk.{i}.{suffix}");
        // Attention half — identical for dense and MoE layers. GGUF q/k are
        // ALREADY interleaved, so (unlike safetensors) NO permute is applied.
        let attn_norm = RmsNorm::with_gain(f.tensor_exact(&t("attn_norm.weight"), md)?, config.eps);
        let ffn_norm = RmsNorm::with_gain(f.tensor_exact(&t("ffn_norm.weight"), md)?, config.eps);
        let w_q = f.tensor_exact(&t("attn_q.weight"), elems(&[q_dim, md])?)?;
        let w_k = f.tensor_exact(&t("attn_k.weight"), elems(&[kv_dim, md])?)?;
        let w_v = f.tensor_exact(&t("attn_v.weight"), elems(&[kv_dim, md])?)?;
        let w_o = f.tensor_exact(&t("attn_output.weight"), elems(&[md, q_dim])?)?;

        // FFN half — a MoE bank of stacked expert tensors when THIS layer has
        // them, otherwise the dense SwiGLU. GGUF stores the experts as one 3-D
        // tensor each (`ffn_{gate,up,down}_exps`), expert-major in ne order, so
        // expert `e` is a contiguous per-expert slice. Detection is per-layer by
        // tensor presence, so a model that interleaves dense and sparse layers
        // (some `blk.{i}` carry `ffn_gate.weight`, others `ffn_gate_exps.weight`)
        // assembles each layer correctly.
        let layer_is_moe = config.is_moe() && f.has_tensor(&t("ffn_gate_exps.weight"));
        let block = if layer_is_moe {
            let n_exp = config.experts();
            let moe_hid = config.moe_hidden();
            let per_gate = elems(&[moe_hid, md])?; // [moe_hid, md] per expert
            let per_down = elems(&[md, moe_hid])?; // [md, moe_hid] per expert
            let gate_exps =
                f.tensor_exact(&t("ffn_gate_exps.weight"), elems(&[n_exp, per_gate])?)?;
            let up_exps = f.tensor_exact(&t("ffn_up_exps.weight"), elems(&[n_exp, per_gate])?)?;
            let down_exps =
                f.tensor_exact(&t("ffn_down_exps.weight"), elems(&[n_exp, per_down])?)?;
            let mut experts = Vec::with_capacity(n_exp);
            for e in 0..n_exp {
                experts.push(MoeExpertWeights {
                    w_gate: gate_exps[e * per_gate..(e + 1) * per_gate].to_vec(),
                    w_up: up_exps[e * per_gate..(e + 1) * per_gate].to_vec(),
                    w_down: down_exps[e * per_down..(e + 1) * per_down].to_vec(),
                });
            }
            let weights = MoeBlockWeights {
                model_dim: md,
                head_dim: hd,
                num_q_heads: nq,
                num_kv_heads: nkv,
                hidden_dim: moe_hid,
                experts_per_tok: config.experts_per_tok(),
                attn_norm,
                ffn_norm,
                w_q,
                w_k,
                w_v,
                w_o,
                w_router: f.tensor_exact(&t("ffn_gate_inp.weight"), elems(&[n_exp, md])?)?,
                experts,
            };
            // GPT-OSS carries a bias on every expert + router projection (and its
            // FFN uses a clamped-α SwiGLU). When those bias tensors are present,
            // build the GPT-OSS block; otherwise the standard SwiGLU MoE. Bias
            // tensors are stacked per expert (`ffn_{gate,up}_exps.bias`:
            // `[moe_hid]` per expert, `ffn_down_exps.bias`: `[model_dim]`),
            // expert-major in ne order like their weight tensors.
            if f.has_tensor(&t("ffn_gate_exps.bias")) {
                let gate_b = f.tensor_exact(&t("ffn_gate_exps.bias"), elems(&[n_exp, moe_hid])?)?;
                let up_b = f.tensor_exact(&t("ffn_up_exps.bias"), elems(&[n_exp, moe_hid])?)?;
                let down_b = f.tensor_exact(&t("ffn_down_exps.bias"), elems(&[n_exp, md])?)?;
                let router_bias = f.tensor_exact(&t("ffn_gate_inp.bias"), n_exp)?;
                let expert_biases = (0..n_exp)
                    .map(|e| GptOssExpertBias {
                        gate: gate_b[e * moe_hid..(e + 1) * moe_hid].to_vec(),
                        up: up_b[e * moe_hid..(e + 1) * moe_hid].to_vec(),
                        down: down_b[e * md..(e + 1) * md].to_vec(),
                    })
                    .collect();
                // Attention half: GPT-OSS biases every attention projection and
                // has a per-query-head learned attention sink. Read them when
                // present (they travel with the FFN biases in a gpt-oss GGUF).
                let attn_q_bias = f
                    .has_tensor(&t("attn_q.bias"))
                    .then(|| f.tensor_exact(&t("attn_q.bias"), q_dim))
                    .transpose()?;
                let attn_k_bias = f
                    .has_tensor(&t("attn_k.bias"))
                    .then(|| f.tensor_exact(&t("attn_k.bias"), kv_dim))
                    .transpose()?;
                let attn_v_bias = f
                    .has_tensor(&t("attn_v.bias"))
                    .then(|| f.tensor_exact(&t("attn_v.bias"), kv_dim))
                    .transpose()?;
                let attn_o_bias = f
                    .has_tensor(&t("attn_output.bias"))
                    .then(|| f.tensor_exact(&t("attn_output.bias"), md))
                    .transpose()?;
                let attn_sinks = f
                    .has_tensor(&t("attn_sinks"))
                    .then(|| f.tensor_exact(&t("attn_sinks"), nq))
                    .transpose()?;
                let go = GptOssMoeWeights {
                    base: weights,
                    router_bias,
                    expert_biases,
                    // The released GPT-OSS constants (α = sigmoid-GELU approx;
                    // swiglu_limit = 7.0 for gpt-oss-20b / 120b).
                    alpha: GPT_OSS_ALPHA,
                    limit: GPT_OSS_SWIGLU_LIMIT,
                    attn_q_bias,
                    attn_k_bias,
                    attn_v_bias,
                    attn_o_bias,
                    attn_sinks,
                };
                MhaDecoderBlock::from_weights_moe_gpt_oss(&go, precision)
                    .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
            } else {
                MhaDecoderBlock::from_weights_moe(&weights, precision)
                    .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
            }
        } else {
            let weights = MhaBlockWeights {
                model_dim: md,
                head_dim: hd,
                num_q_heads: nq,
                num_kv_heads: nkv,
                hidden_dim: hidden,
                attn_norm,
                ffn_norm,
                w_q,
                w_k,
                w_v,
                w_o,
                w_gate: f.tensor_exact(&t("ffn_gate.weight"), elems(&[hidden, md])?)?,
                w_up: f.tensor_exact(&t("ffn_up.weight"), elems(&[hidden, md])?)?,
                w_down: f.tensor_exact(&t("ffn_down.weight"), elems(&[md, hidden])?)?,
            };
            MhaDecoderBlock::from_weights(&weights, precision)
                .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
        };
        let block = block.with_rope(config.rope_theta, config.rope_scaling_resolved().as_ref());
        // Per-layer sliding window. GPT-OSS interleaves sliding + full attention
        // (synthesized into `layer_types` from the GGUF span for arch `gpt-oss`);
        // a bare span with no pattern applies uniformly (Mistral-style SWA).
        let block = match config.sliding_window_for_layer(i) {
            Some(w) => block.with_sliding_window(w),
            None => block,
        };
        layers.push(Box::new(block));
    }

    let stack = LayerStack::new(layers).map_err(|e| LoaderError::Build(e.to_string()))?;
    let embedding = f.tensor_exact("token_embd.weight", elems(&[vocab, md])?)?;
    let final_norm = RmsNorm::with_gain(f.tensor_exact("output_norm.weight", md)?, config.eps);

    if config.tied {
        QuantModel::new_tied(vocab, md, embedding, stack, final_norm, sampler)
            .map_err(|e| LoaderError::Build(e.to_string()))
    } else {
        let head = f.tensor_exact("output.weight", elems(&[vocab, md])?)?;
        QuantModel::new(vocab, md, embedding, stack, final_norm, head, sampler)
            .map_err(|e| LoaderError::Build(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── byte-exact dequant fixtures ──────────────────────────────────────────

    fn f16_bytes(x: f32) -> [u8; 2] {
        half::f16::from_f32(x).to_bits().to_le_bytes()
    }

    #[test]
    fn q8_0_dequant_is_exact() {
        // one block of 32: d = 2.0, q[i] = i-16 → value = 2.0*(i-16)
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(2.0));
        for i in 0..32i32 {
            blk.push(((i - 16) as i8) as u8);
        }
        let got = dequant(GGML_Q8_0, &blk, 32, "t").unwrap();
        let d = half::f16::from_f32(2.0).to_f32();
        for i in 0..32 {
            assert!((got[i] - d * (i as i32 - 16) as f32).abs() < 1e-4, "i={i}");
        }
    }

    #[test]
    fn q4_0_dequant_is_exact() {
        // d = 1.0; each nibble n → (n-8). low nibbles fill [0..16], high [16..32].
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(1.0));
        for j in 0..16u8 {
            // low nibble = j%16, high nibble = (j+1)%16
            let lo = j & 0x0F;
            let hi = (j + 1) & 0x0F;
            blk.push((hi << 4) | lo);
        }
        let got = dequant(GGML_Q4_0, &blk, 32, "t").unwrap();
        let d = half::f16::from_f32(1.0).to_f32();
        for j in 0..16 {
            assert!(
                (got[j] - d * ((j as i32 & 0x0F) - 8) as f32).abs() < 1e-4,
                "lo j={j}"
            );
            assert!(
                (got[j + 16] - d * (((j as i32 + 1) & 0x0F) - 8) as f32).abs() < 1e-4,
                "hi j={j}"
            );
        }
    }

    #[test]
    fn q4_k_dequant_matches_formula() {
        // Build a superblock with d=1, dmin=0 (so out = d1 * quant), scales chosen
        // so every sub-block scale sc=1 (scales[0..4] low6 = 1; mins ignored since
        // dmin=0). qs nibbles all = 3 → every value should be sc*3 = 3.
        let mut blk = vec![0u8; 144];
        blk[0..2].copy_from_slice(&f16_bytes(1.0)); // d
        blk[2..4].copy_from_slice(&f16_bytes(0.0)); // dmin
        // scales[12]: set the 6-bit scale of every sub-block to 1.
        // sub-blocks 0..4 read sc = scales[j]&63 → set scales[0..4]=1.
        // sub-blocks 4..8 read sc = (scales[j+4]&0xF)|((scales[j-4]>>6)<<4).
        // set scales[8..12] low nibble = 1, and scales[0..4] top bits = 0 → sc=1.
        for j in 0..4 {
            blk[4 + j] = 1; // scales[0..4] = 1 (low6=1, top2=0)
        }
        for j in 8..12 {
            blk[4 + j] = 0x01; // scales[8..12] low nibble = 1
        }
        // qs[128] nibbles all 3 → 0x33 per byte.
        for b in blk.iter_mut().skip(16) {
            *b = 0x33;
        }
        let got = dequant(GGML_Q4_K, &blk, QK_K, "t").unwrap();
        assert_eq!(got.len(), QK_K);
        let d = half::f16::from_f32(1.0).to_f32();
        for (idx, &v) in got.iter().enumerate() {
            assert!((v - d * 3.0).abs() < 1e-3, "idx={idx} v={v}");
        }
    }

    #[test]
    fn q6_k_dequant_matches_formula() {
        // d=1, all scales=1, ql nibbles=0, qh bits=0 → q = (0|0)-32 = -32 → value
        // = 1*1*(-32) = -32 for every element.
        let mut blk = vec![0u8; 210];
        for s in blk.iter_mut().take(208).skip(192) {
            *s = 1; // scales[16] = 1
        }
        blk[208..210].copy_from_slice(&f16_bytes(1.0)); // d
        let got = dequant(GGML_Q6_K, &blk, QK_K, "t").unwrap();
        assert_eq!(got.len(), QK_K);
        let d = half::f16::from_f32(1.0).to_f32();
        for (idx, &v) in got.iter().enumerate() {
            assert!((v - d * -32.0).abs() < 1e-3, "idx={idx} v={v}");
        }
    }

    #[test]
    fn q4_1_dequant_is_exact() {
        // d=1, m=0.5; each byte lo-nibble 2, hi-nibble 5. lo lane fills [0..16],
        // hi lane [16..32]. value = d*nibble + m.
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(1.0)); // d
        blk.extend_from_slice(&f16_bytes(0.5)); // m
        for _ in 0..16 {
            blk.push((5 << 4) | 2);
        }
        let got = dequant(GGML_Q4_1, &blk, 32, "t").unwrap();
        let d = half::f16::from_f32(1.0).to_f32();
        let m = half::f16::from_f32(0.5).to_f32();
        for v in &got[0..16] {
            assert!((v - (d * 2.0 + m)).abs() < 1e-3, "lo v={v}");
        }
        for v in &got[16..32] {
            assert!((v - (d * 5.0 + m)).abs() < 1e-3, "hi v={v}");
        }
    }

    #[test]
    fn q5_0_dequant_is_exact() {
        // d=1, qs byte lo=2/hi=5, qh bit0 set → lane-0-lo gains the 5th bit (+16).
        // value = d*((nibble | 5th_bit) - 16).
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(1.0)); // d
        blk.extend_from_slice(&1u32.to_le_bytes()); // qh: only bit 0 set
        for _ in 0..16 {
            blk.push((5 << 4) | 2);
        }
        let got = dequant(GGML_Q5_0, &blk, 32, "t").unwrap();
        // lane-0-lo: (2 | 16) - 16 = 2
        assert!((got[0] - 2.0).abs() < 1e-3, "got[0]={}", got[0]);
        // other lo lanes: (2) - 16 = -14
        for v in &got[1..16] {
            assert!((v - -14.0).abs() < 1e-3, "lo v={v}");
        }
        // hi lanes: (5) - 16 = -11 (qh bits 16..32 all clear)
        for v in &got[16..32] {
            assert!((v - -11.0).abs() < 1e-3, "hi v={v}");
        }
    }

    #[test]
    fn q5_1_dequant_is_exact() {
        // d=1, m=0.5, qh=0; byte lo=2/hi=5. value = d*nibble + m.
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(1.0)); // d
        blk.extend_from_slice(&f16_bytes(0.5)); // m
        blk.extend_from_slice(&0u32.to_le_bytes()); // qh: no 5th bits
        for _ in 0..16 {
            blk.push((5 << 4) | 2);
        }
        let got = dequant(GGML_Q5_1, &blk, 32, "t").unwrap();
        let m = half::f16::from_f32(0.5).to_f32();
        for v in &got[0..16] {
            assert!((v - (2.0 + m)).abs() < 1e-3, "lo v={v}");
        }
        for v in &got[16..32] {
            assert!((v - (5.0 + m)).abs() < 1e-3, "hi v={v}");
        }
    }

    #[test]
    fn q8_1_dequant_ignores_sum_field() {
        // d=2, s=garbage (must be ignored), q[i]=i-16 → value = 2*(i-16).
        let mut blk = Vec::new();
        blk.extend_from_slice(&f16_bytes(2.0)); // d
        blk.extend_from_slice(&f16_bytes(999.0)); // s — MUST NOT affect output
        for i in 0..32i32 {
            blk.push(((i - 16) as i8) as u8);
        }
        let got = dequant(GGML_Q8_1, &blk, 32, "t").unwrap();
        let d = half::f16::from_f32(2.0).to_f32();
        for i in 0..32 {
            assert!((got[i] - d * (i as i32 - 16) as f32).abs() < 1e-3, "i={i}");
        }
    }

    #[test]
    fn q2_k_dequant_matches_formula() {
        // d=1, dmin=1; every scale byte 0x21 (scale-nibble 1, min-nibble 2);
        // qs 0xAA → each 2-bit quant is 0b10 = 2. value = (1*1)*2 - (1*2) = 0.
        // A nonzero result would mean the min term was dropped.
        let mut blk = vec![0u8; 84];
        for s in blk.iter_mut().take(16) {
            *s = 0x21;
        }
        for q in blk.iter_mut().take(80).skip(16) {
            *q = 0xAA;
        }
        blk[80..82].copy_from_slice(&f16_bytes(1.0)); // d
        blk[82..84].copy_from_slice(&f16_bytes(1.0)); // dmin
        let got = dequant(GGML_Q2_K, &blk, QK_K, "t").unwrap();
        assert_eq!(got.len(), QK_K);
        for (idx, &v) in got.iter().enumerate() {
            assert!(v.abs() < 1e-3, "idx={idx} v={v}");
        }
    }

    #[test]
    fn q3_k_dequant_matches_formula() {
        // Craft the 12 packed scale bytes so the aux[] unpack yields all-33 scales
        // (→ scale-32 = 1). hmask all 0 → every value subtracts 4. qs 0 → quant 0.
        // value = d_all * (0 - 4) = -4. A bug in the aux shuffle → wrong scale →
        // wrong magnitude; a bug in the hmask sub → 0 not -4.
        let mut blk = vec![0u8; 110];
        // hmask[0..32] = 0, qs[32..96] = 0 (already zero).
        // scales[96..108]: bytes 96..100 = 0x11, 100..104 = 0x11, 104..108 = 0xAA.
        for b in blk.iter_mut().take(100).skip(96) {
            *b = 0x11;
        }
        for b in blk.iter_mut().take(104).skip(100) {
            *b = 0x11;
        }
        for b in blk.iter_mut().take(108).skip(104) {
            *b = 0xAA;
        }
        blk[108..110].copy_from_slice(&f16_bytes(1.0)); // d_all
        let got = dequant(GGML_Q3_K, &blk, QK_K, "t").unwrap();
        assert_eq!(got.len(), QK_K);
        for (idx, &v) in got.iter().enumerate() {
            assert!((v - -4.0).abs() < 1e-3, "idx={idx} v={v}");
        }
    }

    #[test]
    fn q5_k_dequant_matches_formula() {
        // d=1, dmin=0 (min term drops out); scales set so every get_scale_min_k4
        // sub-scale = 1 (same trick as the Q4_K fixture). ql byte lo=3/hi=5. qh
        // bit0 set → the very first lo-lane value gains the 5th bit (+16).
        let mut blk = vec![0u8; 176];
        blk[0..2].copy_from_slice(&f16_bytes(1.0)); // d
        blk[2..4].copy_from_slice(&f16_bytes(0.0)); // dmin → mins ignored
        // scales[4..16]: sc=1 for every sub-block (scales[0..4]=1, scales[8..12] low
        // nibble=1), mirroring get_scale_min_k4's two index regimes.
        for j in 0..4 {
            blk[4 + j] = 1;
        }
        for j in 8..12 {
            blk[4 + j] = 0x01;
        }
        blk[16] = 0x01; // qh[0] bit0 → 5th bit on first lo-lane value
        for q in blk.iter_mut().take(176).skip(48) {
            *q = (5 << 4) | 3; // ql: lo nibble 3, hi nibble 5
        }
        let got = dequant(GGML_Q5_K, &blk, QK_K, "t").unwrap();
        assert_eq!(got.len(), QK_K);
        // first value: (3 + 16) = 19
        assert!((got[0] - 19.0).abs() < 1e-3, "got[0]={}", got[0]);
        // rest of the first 32 (lo lane, no 5th bit): 3
        for v in &got[1..32] {
            assert!((v - 3.0).abs() < 1e-3, "lo v={v}");
        }
        // next 32 (hi lane): 5
        for v in &got[32..64] {
            assert!((v - 5.0).abs() < 1e-3, "hi v={v}");
        }
    }

    #[test]
    fn rejects_unknown_ggml_type() {
        // Type 4 (deprecated Q4_2) and 15 (Q8_K, intermediate, never a weight
        // encoding) are not supported → clean error, not a mis-decode.
        assert!(type_byte_len(4, 32).is_err());
        assert!(type_byte_len(15, QK_K).is_err());
        // …but the whole mainstream family now decodes.
        for t in [
            GGML_Q4_0, GGML_Q4_1, GGML_Q5_0, GGML_Q5_1, GGML_Q8_0, GGML_Q8_1,
        ] {
            assert!(type_byte_len(t, 32).is_ok(), "type {t} should size-ok");
        }
        for t in [GGML_Q2_K, GGML_Q3_K, GGML_Q4_K, GGML_Q5_K, GGML_Q6_K] {
            assert!(type_byte_len(t, QK_K).is_ok(), "type {t} should size-ok");
        }
    }

    #[test]
    fn block_size_mismatch_is_an_error() {
        assert!(type_byte_len(GGML_Q8_0, 30).is_err()); // 30 not a multiple of 32
        assert!(type_byte_len(GGML_Q4_K, 128).is_err()); // 128 not a multiple of 256
    }

    // ── GGUF container parse ─────────────────────────────────────────────────

    /// Minimal GGUF writer for tests (version 3, alignment 32).
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
        fn kv_str_array(&mut self, key: &str, vals: &[&str]) {
            Self::gstr(&mut self.kv, key);
            self.kv.extend_from_slice(&9u32.to_le_bytes()); // ARRAY
            self.kv.extend_from_slice(&8u32.to_le_bytes()); // element type STRING
            self.kv
                .extend_from_slice(&(vals.len() as u64).to_le_bytes());
            for v in vals {
                Self::gstr(&mut self.kv, v);
            }
            self.n_kv += 1;
        }
        fn kv_i32_array(&mut self, key: &str, vals: &[i32]) {
            Self::gstr(&mut self.kv, key);
            self.kv.extend_from_slice(&9u32.to_le_bytes()); // ARRAY
            self.kv.extend_from_slice(&5u32.to_le_bytes()); // element type INT32
            self.kv
                .extend_from_slice(&(vals.len() as u64).to_le_bytes());
            for v in vals {
                self.kv.extend_from_slice(&v.to_le_bytes());
            }
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
            // pad tensor data to 32 within the blob so successive offsets align.
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

    #[test]
    fn parses_header_metadata_and_tensor() {
        let mut w = GgufWriter::new();
        w.kv_str("general.architecture", "llama");
        w.kv_u32("llama.embedding_length", 8);
        w.kv_u32("llama.block_count", 1);
        w.kv_u32("llama.attention.head_count", 2);
        w.tensor_f32("token_embd.weight", &[8, 5], &[0.5f32; 40]); // ne=[n_embd, n_vocab]
        let bytes = w.finish();

        let f = GgufFile::parse(&bytes).unwrap();
        assert_eq!(f.architecture(), Some("llama"));
        assert_eq!(f.meta_u64("llama.embedding_length"), Some(8));
        let t = f.tensor_f32("token_embd.weight").unwrap();
        assert_eq!(t.len(), 40);
        assert!((t[0] - 0.5).abs() < 1e-6);
    }

    #[test]
    fn extracts_embedded_tokenizer() {
        // A GGUF that carries its own byte-level BPE tokenizer in metadata.
        // token_type 3 = CONTROL (special); 1 = NORMAL.
        let mut w = GgufWriter::new();
        w.kv_str("general.architecture", "llama");
        w.kv_str("tokenizer.ggml.model", "gpt2");
        w.kv_str_array(
            "tokenizer.ggml.tokens",
            &["<unk>", "a", "b", "c", "\u{0120}", "ab"],
        );
        w.kv_str_array("tokenizer.ggml.merges", &["a b"]);
        w.kv_i32_array("tokenizer.ggml.token_type", &[3, 1, 1, 1, 1, 1]);
        w.kv_u32("tokenizer.ggml.bos_token_id", 0);
        w.kv_u32("tokenizer.ggml.eos_token_id", 2);
        let bytes = w.finish();

        let f = GgufFile::parse(&bytes).unwrap();
        let tk = f.tokenizer().expect("tokenizer metadata present");
        assert_eq!(tk.model, "gpt2");
        assert!(tk.is_byte_level_bpe());
        assert_eq!(tk.tokens.len(), 6);
        assert_eq!(tk.tokens[5], "ab");
        assert_eq!(tk.merges, vec!["a b".to_string()]);
        assert_eq!(tk.bos, Some(0));
        assert_eq!(tk.eos, Some(2));
        // only id 0 is CONTROL (type 3) → the single special id
        assert_eq!(tk.special_ids(), vec![0]);
    }

    #[test]
    fn weights_only_gguf_has_no_tokenizer() {
        // The tiny model fixture carries no tokenizer.ggml.* keys → None (caller
        // falls back to a sidecar tokenizer.json).
        let bytes = tiny_model_gguf();
        let f = GgufFile::parse(&bytes).unwrap();
        assert!(f.tokenizer().is_none());
    }

    /// Build a tiny but COMPLETE 1-layer llama GGUF and load it end-to-end into a
    /// runnable QuantModel — proves the metadata→Config derivation, the name-map,
    /// and the (no-permute) block assembly all compose.
    fn tiny_model_gguf() -> Vec<u8> {
        let md = 4usize;
        let heads = 2usize;
        let hd = md / heads; // 2
        let hidden = 8usize;
        let vocab = 6usize;
        let mut w = GgufWriter::new();
        w.kv_str("general.architecture", "llama");
        w.kv_u32("llama.embedding_length", md as u32);
        w.kv_u32("llama.block_count", 1);
        w.kv_u32("llama.attention.head_count", heads as u32);
        w.kv_u32("llama.attention.head_count_kv", heads as u32);
        w.kv_u32("llama.feed_forward_length", hidden as u32);
        w.kv_f32("llama.attention.layer_norm_rms_epsilon", 1e-5);
        w.kv_f32("llama.rope.freq_base", 500000.0); // Llama-3 base — must thread through
        let _ = hd;
        // embedding + output norm + head
        w.tensor_f32(
            "token_embd.weight",
            &[md, vocab],
            &vec![0.02f32; md * vocab],
        );
        w.tensor_f32("output_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("output.weight", &[md, vocab], &vec![0.02f32; md * vocab]);
        // one block
        w.tensor_f32("blk.0.attn_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("blk.0.ffn_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("blk.0.attn_q.weight", &[md, md], &vec![0.02f32; md * md]);
        w.tensor_f32("blk.0.attn_k.weight", &[md, md], &vec![0.02f32; md * md]);
        w.tensor_f32("blk.0.attn_v.weight", &[md, md], &vec![0.02f32; md * md]);
        w.tensor_f32(
            "blk.0.attn_output.weight",
            &[md, md],
            &vec![0.02f32; md * md],
        );
        w.tensor_f32(
            "blk.0.ffn_gate.weight",
            &[md, hidden],
            &vec![0.02f32; hidden * md],
        );
        w.tensor_f32(
            "blk.0.ffn_up.weight",
            &[md, hidden],
            &vec![0.02f32; hidden * md],
        );
        w.tensor_f32(
            "blk.0.ffn_down.weight",
            &[hidden, md],
            &vec![0.02f32; md * hidden],
        );
        w.finish()
    }

    #[test]
    fn config_derived_from_metadata() {
        let bytes = tiny_model_gguf();
        let f = GgufFile::parse(&bytes).unwrap();
        let c = f.config().unwrap();
        assert_eq!(c.model_dim, 4);
        assert_eq!(c.n_layers, 1);
        assert_eq!(c.n_heads, 2);
        assert_eq!(c.vocab, 6);
        assert_eq!(c.hidden, 8);
        assert!(!c.tied); // output.weight present
        assert!((c.rope_theta - 500000.0).abs() < 1.0); // threaded through
    }

    #[test]
    fn loads_tiny_gguf_end_to_end() {
        let bytes = tiny_model_gguf();
        let mut model = load_gguf(&bytes, Precision::F32, Sampler::greedy())
            .expect("tiny gguf should load into a runnable QuantModel");
        // A runnable model reports the vocab it was built with.
        assert_eq!(model.vocab(), 6);
        // End-to-end: a GGUF-loaded model must actually RUN a forward pass and
        // return vocab-length logits — proving metadata→Config, the name-map, the
        // (no-permute) block assembly, and RoPE all compose into a live model.
        let logits = model.forward(0).expect("forward pass on GGUF-loaded model");
        assert_eq!(logits.len(), 6);
        assert!(
            logits.iter().all(|x| x.is_finite()),
            "logits must be finite"
        );
    }

    // ── GGUF mixture-of-experts (MoE Increment 3) ────────────────────────────

    // A 1-layer MoE GGUF: router `ffn_gate_inp` + stacked expert tensors
    // `ffn_{gate,up,down}_exps` (one 3-D tensor each, expert-major in ne order),
    // and NO dense `ffn_{gate,up,down}` — so a successful load proves the MoE
    // branch (not the dense one) was taken.
    const MOE_MD: usize = 4;
    const MOE_HEADS: usize = 2;
    const MOE_HID: usize = 8; // dense feed_forward_length (metadata-required)
    const MOE_EXP_HID: usize = 6; // per-expert width
    const MOE_N_EXP: usize = 4;
    const MOE_VOCAB: usize = 6;

    fn varying(seed: f32, n: usize) -> Vec<f32> {
        (0..n)
            .map(|i| (((i as f32) + seed) * 0.05).sin() * 0.1)
            .collect()
    }

    fn tiny_moe_gguf(used: u32) -> Vec<u8> {
        tiny_moe_gguf_opt(used, false)
    }

    // `gpt_oss = true` adds the GPT-OSS expert + router bias tensors, so the
    // loader builds the block via the clamped-α GPT-OSS FFN path.
    fn tiny_moe_gguf_opt(used: u32, gpt_oss: bool) -> Vec<u8> {
        tiny_moe_gguf_swa(used, gpt_oss, None)
    }

    // Adds `sliding_window` metadata (span) when `swa` is `Some`. With `gpt_oss`
    // (which writes the signature `attn_sinks` tensor), the loader synthesizes the
    // GPT-OSS interleaved `layer_types` and applies the per-layer window.
    fn tiny_moe_gguf_swa(used: u32, gpt_oss: bool, swa: Option<u32>) -> Vec<u8> {
        let (md, hid, ehid, n_exp, vocab) = (MOE_MD, MOE_HID, MOE_EXP_HID, MOE_N_EXP, MOE_VOCAB);
        let mut w = GgufWriter::new();
        w.kv_str("general.architecture", "llama");
        w.kv_u32("llama.embedding_length", md as u32);
        w.kv_u32("llama.block_count", 1);
        w.kv_u32("llama.attention.head_count", MOE_HEADS as u32);
        w.kv_u32("llama.attention.head_count_kv", MOE_HEADS as u32);
        w.kv_u32("llama.feed_forward_length", hid as u32);
        w.kv_f32("llama.attention.layer_norm_rms_epsilon", 1e-5);
        w.kv_f32("llama.rope.freq_base", 500000.0);
        // MoE metadata.
        w.kv_u32("llama.expert_count", n_exp as u32);
        w.kv_u32("llama.expert_used_count", used);
        w.kv_u32("llama.expert_feed_forward_length", ehid as u32);
        if let Some(win) = swa {
            w.kv_u32("llama.attention.sliding_window", win);
        }
        // embedding + output norm + head
        w.tensor_f32("token_embd.weight", &[md, vocab], &varying(0.5, md * vocab));
        w.tensor_f32("output_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("output.weight", &[md, vocab], &varying(0.9, md * vocab));
        // one block — attention half
        w.tensor_f32("blk.0.attn_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("blk.0.ffn_norm.weight", &[md], &vec![1.0f32; md]);
        w.tensor_f32("blk.0.attn_q.weight", &[md, md], &varying(1.0, md * md));
        w.tensor_f32("blk.0.attn_k.weight", &[md, md], &varying(2.0, md * md));
        w.tensor_f32("blk.0.attn_v.weight", &[md, md], &varying(3.0, md * md));
        w.tensor_f32(
            "blk.0.attn_output.weight",
            &[md, md],
            &varying(4.0, md * md),
        );
        // MoE FFN — router (ne [md, n_exp]) + stacked experts.
        w.tensor_f32(
            "blk.0.ffn_gate_inp.weight",
            &[md, n_exp],
            &varying(5.0, n_exp * md),
        );
        // ffn_gate_exps / ffn_up_exps: ne [md, ehid, n_exp], expert-major
        // [ehid, md] row-major slices. ffn_down_exps: ne [ehid, md, n_exp],
        // [md, ehid] slices.
        w.tensor_f32(
            "blk.0.ffn_gate_exps.weight",
            &[md, ehid, n_exp],
            &varying(6.0, n_exp * ehid * md),
        );
        w.tensor_f32(
            "blk.0.ffn_up_exps.weight",
            &[md, ehid, n_exp],
            &varying(7.0, n_exp * ehid * md),
        );
        w.tensor_f32(
            "blk.0.ffn_down_exps.weight",
            &[ehid, md, n_exp],
            &varying(8.0, n_exp * md * ehid),
        );
        if gpt_oss {
            // GPT-OSS biases: gate/up per-expert `[ehid]` (ne [ehid, n_exp]),
            // down per-expert `[md]` (ne [md, n_exp]), router `[n_exp]`.
            w.tensor_f32(
                "blk.0.ffn_gate_exps.bias",
                &[ehid, n_exp],
                &varying(9.0, n_exp * ehid),
            );
            w.tensor_f32(
                "blk.0.ffn_up_exps.bias",
                &[ehid, n_exp],
                &varying(10.0, n_exp * ehid),
            );
            w.tensor_f32(
                "blk.0.ffn_down_exps.bias",
                &[md, n_exp],
                &varying(11.0, n_exp * md),
            );
            w.tensor_f32("blk.0.ffn_gate_inp.bias", &[n_exp], &varying(12.0, n_exp));
            // GPT-OSS attention biases + per-head sinks. heads=2 → hd=md/2,
            // q_dim=kv_dim=heads·hd=md, nq=heads.
            let (qd, kvd, nq) = (md, md, MOE_HEADS);
            w.tensor_f32("blk.0.attn_q.bias", &[qd], &varying(13.0, qd));
            w.tensor_f32("blk.0.attn_k.bias", &[kvd], &varying(14.0, kvd));
            w.tensor_f32("blk.0.attn_v.bias", &[kvd], &varying(15.0, kvd));
            w.tensor_f32("blk.0.attn_output.bias", &[md], &varying(16.0, md));
            w.tensor_f32("blk.0.attn_sinks", &[nq], &varying(17.0, nq));
        }
        w.finish()
    }

    #[test]
    fn moe_config_derived_from_gguf_metadata() {
        let bytes = tiny_moe_gguf(2);
        let c = GgufFile::parse(&bytes).unwrap().config().unwrap();
        assert!(c.is_moe());
        assert_eq!(c.experts(), MOE_N_EXP);
        assert_eq!(c.experts_per_tok(), 2);
        assert_eq!(c.moe_hidden(), MOE_EXP_HID);
    }

    #[test]
    fn loads_moe_gguf_end_to_end() {
        // The FFN tensors present are ONLY the router + stacked experts, so a
        // load that runs proves the loader built MoE blocks from GGUF.
        let bytes = tiny_moe_gguf(2);
        let mut model = load_gguf(&bytes, Precision::F32, Sampler::greedy())
            .expect("MoE gguf should load into a runnable QuantModel");
        assert_eq!(model.vocab(), MOE_VOCAB);
        let logits = model.forward(0).expect("forward on GGUF MoE model");
        assert_eq!(logits.len(), MOE_VOCAB);
        assert!(logits.iter().all(|x| x.is_finite()), "logits finite");
    }

    #[test]
    fn moe_gguf_top1_and_full_topk_and_quantized_all_run() {
        // top-1, top-N, and a quantized runtime precision all assemble + run.
        for used in [1u32, MOE_N_EXP as u32] {
            let bytes = tiny_moe_gguf(used);
            for p in [Precision::F32, Precision::Int8, Precision::Nvfp4] {
                let mut model = load_gguf(&bytes, p, Sampler::greedy())
                    .unwrap_or_else(|e| panic!("MoE gguf top-{used} at {p:?}: {e:?}"));
                let logits = model.forward(1).expect("forward");
                assert_eq!(logits.len(), MOE_VOCAB);
                assert!(
                    logits.iter().all(|x| x.is_finite()),
                    "top-{used} {p:?} finite"
                );
            }
        }
    }

    #[test]
    fn gpt_oss_gguf_uses_the_biased_clamped_ffn() {
        // A GGUF MoE whose experts carry biases loads via the GPT-OSS FFN path
        // (per-expert + router biases, clamped-α activation) and must decode
        // differently from the same weights loaded without the bias tensors
        // (the standard SwiGLU path) — proving the GPT-OSS branch was taken.
        let with_bias = tiny_moe_gguf_opt(2, true);
        let no_bias = tiny_moe_gguf_opt(2, false);
        let mut a =
            load_gguf(&with_bias, Precision::F32, Sampler::greedy()).expect("gpt-oss gguf loads");
        let mut b =
            load_gguf(&no_bias, Precision::F32, Sampler::greedy()).expect("standard gguf loads");
        assert_eq!(a.vocab(), MOE_VOCAB);
        let mut differed = false;
        for tok in [0usize, 1, 2, 3] {
            let ya = a.forward(tok).expect("gpt-oss forward");
            let yb = b.forward(tok).expect("standard forward");
            assert_eq!(ya.len(), MOE_VOCAB);
            assert!(ya.iter().all(|x| x.is_finite()), "gpt-oss logits finite");
            if ya != yb {
                differed = true;
            }
        }
        assert!(
            differed,
            "the GPT-OSS biased/clamped FFN must decode differently from SwiGLU"
        );
    }

    #[test]
    fn gpt_oss_gguf_synthesizes_sliding_window_pattern() {
        // A gpt-oss GGUF that declares `attention.sliding_window` gets the
        // GPT-OSS interleaved `layer_types` synthesized (sliding on even layers,
        // full on odd — matching the released config's `layer_types`), and the
        // span reads through. `block_count` is 1 here, so only layer 0 (even →
        // sliding) exists; the alternation itself is covered by the Config unit
        // test in lib.rs.
        let bytes = tiny_moe_gguf_swa(2, true, Some(2));
        let c = GgufFile::parse(&bytes).unwrap().config().unwrap();
        assert_eq!(c.sliding_window, Some(2), "span read from GGUF metadata");
        assert_eq!(
            c.layer_types.as_deref(),
            Some(&["sliding_attention".to_string()][..]),
            "gpt-oss synthesizes the interleaved layer_types",
        );
        assert_eq!(c.sliding_window_for_layer(0), Some(2), "even layer slides");

        // A non-gpt-oss MoE with the same span key gets NO synthesized pattern
        // (its `layer_types` stays None ⇒ uniform SWA would apply, but here we
        // only assert the pattern is not gpt-oss-shaped).
        let plain = tiny_moe_gguf_swa(2, false, Some(2));
        let pc = GgufFile::parse(&plain).unwrap().config().unwrap();
        assert_eq!(pc.sliding_window, Some(2));
        assert_eq!(pc.layer_types, None, "no attn_sinks ⇒ no gpt-oss pattern");
    }

    #[test]
    fn gpt_oss_gguf_with_sliding_window_still_loads_and_runs() {
        // End-to-end: a gpt-oss GGUF whose layer 0 is a sliding layer assembles
        // (the loader chains `.with_sliding_window` onto the block) and decodes
        // finite logits across several positions.
        let bytes = tiny_moe_gguf_swa(2, true, Some(2));
        let mut m = load_gguf(&bytes, Precision::F32, Sampler::greedy())
            .expect("gpt-oss gguf with sliding window loads");
        for tok in [0usize, 1, 2, 3] {
            let y = m.forward(tok).expect("forward");
            assert_eq!(y.len(), MOE_VOCAB);
            assert!(y.iter().all(|x| x.is_finite()), "logits finite at {tok}");
        }
    }

    #[test]
    fn gpt_oss_gguf_quantized_runs() {
        // The biased GPT-OSS experts also re-quantize to a runtime precision.
        let bytes = tiny_moe_gguf_opt(2, true);
        for p in [Precision::Int8, Precision::Nvfp4] {
            let mut model = load_gguf(&bytes, p, Sampler::greedy())
                .unwrap_or_else(|e| panic!("gpt-oss gguf at {p:?}: {e:?}"));
            let logits = model.forward(1).expect("forward");
            assert_eq!(logits.len(), MOE_VOCAB);
            assert!(logits.iter().all(|x| x.is_finite()), "{p:?} finite");
        }
    }

    // A MoE-metadata GGUF whose single block carries the chosen FFN tensors.
    // `moe=true` writes the expert bank; `moe=false` writes dense ffn tensors
    // (the per-layer-dense case that interleaving must accept). `full_bank`
    // controls whether the expert bank is complete.
    fn moe_meta_gguf(moe: bool, full_bank: bool) -> Vec<u8> {
        let md = MOE_MD;
        let ehid = MOE_EXP_HID;
        let n_exp = MOE_N_EXP;
        let mut w = GgufWriter::new();
        w.kv_str("general.architecture", "llama");
        w.kv_u32("llama.embedding_length", md as u32);
        w.kv_u32("llama.block_count", 1);
        w.kv_u32("llama.attention.head_count", MOE_HEADS as u32);
        w.kv_u32("llama.attention.head_count_kv", MOE_HEADS as u32);
        w.kv_u32("llama.feed_forward_length", MOE_HID as u32);
        w.kv_u32("llama.expert_count", n_exp as u32);
        w.kv_u32("llama.expert_used_count", 2);
        w.kv_u32("llama.expert_feed_forward_length", ehid as u32);
        w.tensor_f32(
            "token_embd.weight",
            &[md, MOE_VOCAB],
            &vec![0.02; md * MOE_VOCAB],
        );
        w.tensor_f32("output_norm.weight", &[md], &vec![1.0; md]);
        w.tensor_f32(
            "output.weight",
            &[md, MOE_VOCAB],
            &vec![0.02; md * MOE_VOCAB],
        );
        w.tensor_f32("blk.0.attn_norm.weight", &[md], &vec![1.0; md]);
        w.tensor_f32("blk.0.ffn_norm.weight", &[md], &vec![1.0; md]);
        w.tensor_f32("blk.0.attn_q.weight", &[md, md], &vec![0.02; md * md]);
        w.tensor_f32("blk.0.attn_k.weight", &[md, md], &vec![0.02; md * md]);
        w.tensor_f32("blk.0.attn_v.weight", &[md, md], &vec![0.02; md * md]);
        w.tensor_f32("blk.0.attn_output.weight", &[md, md], &vec![0.02; md * md]);
        if moe {
            w.tensor_f32(
                "blk.0.ffn_gate_inp.weight",
                &[md, n_exp],
                &vec![0.02; n_exp * md],
            );
            w.tensor_f32(
                "blk.0.ffn_gate_exps.weight",
                &[md, ehid, n_exp],
                &vec![0.02; n_exp * ehid * md],
            );
            if full_bank {
                w.tensor_f32(
                    "blk.0.ffn_up_exps.weight",
                    &[md, ehid, n_exp],
                    &vec![0.02; n_exp * ehid * md],
                );
                w.tensor_f32(
                    "blk.0.ffn_down_exps.weight",
                    &[ehid, md, n_exp],
                    &vec![0.02; n_exp * md * ehid],
                );
            }
            // full_bank=false omits ffn_up_exps / ffn_down_exps → incomplete.
        } else {
            // Dense FFN tensors instead of the expert bank.
            w.tensor_f32(
                "blk.0.ffn_gate.weight",
                &[md, MOE_HID],
                &vec![0.02; MOE_HID * md],
            );
            w.tensor_f32(
                "blk.0.ffn_up.weight",
                &[md, MOE_HID],
                &vec![0.02; MOE_HID * md],
            );
            w.tensor_f32(
                "blk.0.ffn_down.weight",
                &[MOE_HID, md],
                &vec![0.02; md * MOE_HID],
            );
        }
        w.finish()
    }

    #[test]
    fn moe_gguf_dense_layer_loads_via_interleaving() {
        // A MoE-metadata GGUF whose only block has DENSE ffn tensors (no expert
        // bank) is treated as a dense layer by per-layer tensor-presence
        // detection — the interleaving case — and loads + runs.
        let bytes = moe_meta_gguf(false, false);
        let mut model = load_gguf(&bytes, Precision::F32, Sampler::greedy())
            .expect("a dense-FFN layer under MoE metadata must load as dense");
        let logits = model.forward(0).expect("forward");
        assert_eq!(logits.len(), MOE_VOCAB);
        assert!(logits.iter().all(|x| x.is_finite()));
    }

    #[test]
    fn moe_gguf_incomplete_expert_bank_errors() {
        // A layer that HAS `ffn_gate_exps` (so it's detected as MoE) but is
        // missing `ffn_up_exps` must fail on the absent stacked tensor.
        let bytes = moe_meta_gguf(true, false);
        assert!(matches!(
            load_gguf(&bytes, Precision::F32, Sampler::greedy()),
            Err(LoaderError::MissingTensor(_))
        ));
    }

    #[test]
    fn dense_gguf_stays_dense() {
        // The existing dense fixture has no expert metadata → not MoE.
        let c = GgufFile::parse(&tiny_model_gguf())
            .unwrap()
            .config()
            .unwrap();
        assert!(!c.is_moe());
        assert_eq!(c.experts_per_tok(), 0);
    }
}
