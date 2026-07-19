/* webapp/_shared/quant-picker.js — SDD-049 load-time quantization picker.
 *
 * Groups the model catalog by base model (GET /api/models-catalog/by-base) and
 * lets the operator pick a model then its quantization. Read-only: choosing a
 * variant RESOLVES the catalog id and fills the signed `model-load` control on
 * the panel; the actual load stays that control's dry-run + operator-key +
 * type-to-confirm path (R10212 — this widget never mutates). Inlined verbatim
 * into every panel that carries a #quant-picker + the model-load control
 * (D-03, D-21), kept in lockstep by tests/lint/test_quant_picker_contract.py.
 * Self-contained: DEMO via window.soDemo, own scroll — no panel globals. */
(function () {
  var BY_BASE_URL = '/api/models-catalog/by-base';
  // DEMO (SDD-119/120): zero-network, badged sample — one multi-quant + one single.
  var DEMO_BASES = [
    { base: 'DeepSeek-R1-Distill-Llama-70B', variant_count: 2, variants: [
      { id: 'DeepSeek-R1-Distill-Llama-70B-FP16', quantization: 'fp16', vram_gib_min: 140, status: 'verified-real' },
      { id: 'DeepSeek-R1-Distill-Llama-70B-Q4_K_M', quantization: 'gguf-q4_k_m', vram_gib_min: 42, status: 'verified-real' } ] },
    { base: 'Ling-2.6-flash', variant_count: 1, variants: [
      { id: 'Ling-2.6-flash', quantization: 'bf16', vram_gib_min: 8, status: 'verified-real' } ] }
  ];
  function esc(s) { return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function demoOn() { return !!(window.soDemo && window.soDemo.on()); }
  function scrollToCard(card) {
    (card || document.body).scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (card) { card.style.outline = '2px solid var(--accent, #9bd1ff)';
                setTimeout(function () { card.style.outline = ''; }, 1600); }
  }
  function mount() {
    var sel = document.getElementById('qp-base');
    if (!sel) return;  // panel without the picker
    var varsEl = document.getElementById('qp-variants');
    var chosenEl = document.getElementById('qp-chosen');
    var BASES = [];
    function fillSelect(bases) {
      BASES = bases || [];
      if (!BASES.length) { sel.innerHTML = '<option value="">— catalog unavailable —</option>'; return; }
      var multi = BASES.filter(function (b) { return b.variant_count > 1; });
      var single = BASES.filter(function (b) { return b.variant_count <= 1; });
      function opt(b) { return '<option value="' + esc(b.base) + '">' + esc(b.base)
        + (b.variant_count > 1 ? ' · ' + b.variant_count + ' quants' : '') + '</option>'; }
      sel.innerHTML = '<option value="">— choose a model —</option>'
        + (multi.length ? '<optgroup label="multiple quantizations">' + multi.map(opt).join('') + '</optgroup>' : '')
        + '<optgroup label="single quantization">' + single.map(opt).join('') + '</optgroup>';
    }
    function renderVariants(base) {
      chosenEl.hidden = true; chosenEl.textContent = '';
      var g = BASES.filter(function (b) { return b.base === base; })[0];
      if (!g) { varsEl.innerHTML = ''; return; }
      varsEl.innerHTML = g.variants.map(function (v) {
        var vram = (v.vram_gib_min != null ? v.vram_gib_min + ' GiB' : '—');
        return '<button type="button" class="qp-variant" aria-pressed="false" data-id="' + esc(v.id)
          + '" data-quant="' + esc(v.quantization) + '"><span class="qp-q">' + esc(v.quantization)
          + '</span><span class="qp-meta">' + vram + ' · ' + esc(v.status || '') + '</span></button>';
      }).join('');
    }
    function choose(btn) {
      Array.prototype.forEach.call(varsEl.querySelectorAll('.qp-variant'), function (b) {
        b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
      var id = btn.getAttribute('data-id'), q = btn.getAttribute('data-quant');
      var surf = document.getElementById('control-surface');
      var card = surf && surf.querySelector('[data-cid="model-load"]');
      var input = card && card.querySelector('input.cs-arg[data-argkey="id"]');
      if (input) { input.value = id; input.dispatchEvent(new Event('input', { bubbles: true })); }
      chosenEl.hidden = false;
      chosenEl.innerHTML = 'Selected <b>' + esc(q) + '</b> → <code>' + esc(id) + '</code>. '
        + (input ? 'Filled into the Load Model control below — press <b>Execute</b> to apply (dry-run first).'
                 : 'Load Model control is not on this panel.');
      if (card) scrollToCard(card);
    }
    sel.addEventListener('change', function () { renderVariants(sel.value); });
    varsEl.addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('.qp-variant') : null;
      if (b) choose(b);
    });
    if (demoOn()) { fillSelect(DEMO_BASES); return; }  // DEMO: no fetch
    fetch(BY_BASE_URL, { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { fillSelect(d && d.bases); })
      .catch(function () { fillSelect([]); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();