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
//! Supported quant types: `F32`, `F16`, `Q8_0`, `Q4_0`, `Q4_K`, `Q6_K` — the set
//! a `Q4_K_M` mixed checkpoint uses (Q6_K for a few sensitive tensors, Q4_K for
//! the rest). Other ggml types are rejected with a clear error, not mis-decoded.
//!
//! **q/k permutation:** unlike HF safetensors (rotate-half convention, permuted
//! by [`permute_qk_hf_to_interleaved`]), GGUF stores q/k already in the runtime's
//! **interleaved** RoPE convention — so GGUF q/k are fed through verbatim, with
//! NO permutation. Applying the safetensors permute here would corrupt rotation.

use std::collections::BTreeMap;

use sovereign_decoder_layer::{DecoderLayer, LayerStack};
use sovereign_mha_block::{MhaBlockWeights, MhaDecoderBlock};
use sovereign_quant_model::QuantModel;
use sovereign_rmsnorm::RmsNorm;

use crate::{Config, LoaderError, Precision, Sampler, elems};

const GGUF_MAGIC: u32 = 0x4655_4747; // "GGUF" little-endian
const DEFAULT_ALIGNMENT: usize = 32;

// ggml_type enum values (subset we decode).
const GGML_F32: u32 = 0;
const GGML_F16: u32 = 1;
const GGML_Q4_0: u32 = 2;
const GGML_Q8_0: u32 = 8;
const GGML_Q4_K: u32 = 12;
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

/// A parsed GGUF metadata value (only the scalar accessors the loader needs are
/// exposed; arrays are parsed + skipped so the tensor table is reached).
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
    /// An array — retained only as its length (we never need array contents for
    /// the Config; tokenizer arrays are consumed by the tokenizer path).
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
        9 => {
            // ARRAY: element_type u32, len u64, then len elements.
            let elem_t = cur.u32()?;
            let n = cur.u64()? as usize;
            for _ in 0..n {
                skip_typed_value(cur, elem_t)?;
            }
            MetaValue::Array
        }
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

    /// The model architecture (`general.architecture`), e.g. `llama`, `qwen2`.
    pub fn architecture(&self) -> Option<&str> {
        self.meta
            .get("general.architecture")
            .and_then(MetaValue::as_str)
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
        GGML_Q8_0 => {
            if n % 32 != 0 {
                return Err(bad_block(32));
            }
            (n / 32) * 34 // f16 scale (2) + 32 int8
        }
        GGML_Q4_K => {
            if n % QK_K != 0 {
                return Err(bad_block(QK_K));
            }
            (n / QK_K) * 144 // d(2)+dmin(2)+scales(12)+qs(128)
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
                dtype: format!("ggml type {other} (support F32/F16/Q8_0/Q4_0/Q4_K/Q6_K)"),
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
        GGML_Q4_K => {
            for blk in raw.chunks_exact(144) {
                dequant_q4_k(blk, &mut out);
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
        let weights = MhaBlockWeights {
            model_dim: md,
            head_dim: hd,
            num_q_heads: nq,
            num_kv_heads: nkv,
            hidden_dim: hidden,
            attn_norm: RmsNorm::with_gain(f.tensor_exact(&t("attn_norm.weight"), md)?, config.eps),
            ffn_norm: RmsNorm::with_gain(f.tensor_exact(&t("ffn_norm.weight"), md)?, config.eps),
            // GGUF q/k are ALREADY interleaved — feed verbatim (no HF permute).
            w_q: f.tensor_exact(&t("attn_q.weight"), elems(&[q_dim, md])?)?,
            w_k: f.tensor_exact(&t("attn_k.weight"), elems(&[kv_dim, md])?)?,
            w_v: f.tensor_exact(&t("attn_v.weight"), elems(&[kv_dim, md])?)?,
            w_o: f.tensor_exact(&t("attn_output.weight"), elems(&[md, q_dim])?)?,
            w_gate: f.tensor_exact(&t("ffn_gate.weight"), elems(&[hidden, md])?)?,
            w_up: f.tensor_exact(&t("ffn_up.weight"), elems(&[hidden, md])?)?,
            w_down: f.tensor_exact(&t("ffn_down.weight"), elems(&[md, hidden])?)?,
        };
        let block = MhaDecoderBlock::from_weights(&weights, precision)
            .map_err(|e| LoaderError::Build(format!("layer {i}: {e}")))?
            .with_rope(config.rope_theta, config.rope_scaling_resolved().as_ref());
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
    fn rejects_unknown_ggml_type() {
        // Q5_0 (type 6) is not supported → clean error, not a mis-decode.
        assert!(type_byte_len(6, 32).is_err());
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
}
