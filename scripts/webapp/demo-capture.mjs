#!/usr/bin/env node
/**
 * demo-capture.mjs — reusable, configurable Playwright capture + verify for the
 * cockpit's DEMO mode (SDD-116 rollout). Replaces the throwaway verify-batchN.mjs
 * scripts with one manifest-driven tool.
 *
 * Manifest: scripts/webapp/demo-panels.json (slug / demoConst / apiPrefix /
 * rowSelector). This is the SINGLE SOURCE OF TRUTH shared with the demo contract
 * lint (tests/lint/test_demo_mode_contract.py).
 *
 * Per panel (with DEMO on) it asserts the SB-077 / R10212 contract holds at runtime:
 *   - the DEMO badge is present (sample data is always labelled),
 *   - sample rows rendered (rowSelector count > 0, when a selector is given),
 *   - ZERO calls to the panel's own data endpoint (apiPrefix) — the demo path is
 *     client-side only,
 *   - zero uncaught page errors.
 * Exits non-zero if any selected panel fails → a local self-validation gate.
 * NOT wired into `make test` / CI (no browser there); run via `make demo-capture`.
 *
 * Usage:
 *   node scripts/webapp/demo-capture.mjs --all
 *   node scripts/webapp/demo-capture.mjs --panels d-12-networking,d-13-filesystem-grants
 *   node scripts/webapp/demo-capture.mjs --sdd SDD-123 --out /tmp/gold --json
 *   node scripts/webapp/demo-capture.mjs --panels d-04-costs --demo off   (baseline: no badge, live path)
 *
 * Flags:
 *   --panels a,b,c   comma-separated slugs (default: all in the manifest)
 *   --all            explicitly select all manifest panels
 *   --sdd SDD-123    select only panels whose manifest `sdd` matches
 *   --demo on|off    demo flag state (default on). off = assert NO badge (baseline).
 *   --out DIR        screenshot output dir (default ./.demo-captures)
 *   --viewport WxH   viewport (default 1280x1050)
 *   --json           also print a machine-readable JSON report
 *   --manifest PATH  override the manifest path
 *   --repo PATH      repo root (default: two levels up from this script)
 */

import { readFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── arg parsing ───────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const a = { demo: "on", viewport: "1280x1050", json: false, all: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === "--all") a.all = true;
    else if (k === "--json") a.json = true;
    else if (k === "--panels") a.panels = argv[++i];
    else if (k === "--sdd") a.sdd = argv[++i];
    else if (k === "--demo") a.demo = argv[++i];
    else if (k === "--out") a.out = argv[++i];
    else if (k === "--viewport") a.viewport = argv[++i];
    else if (k === "--manifest") a.manifest = argv[++i];
    else if (k === "--repo") a.repo = argv[++i];
    else if (k === "-h" || k === "--help") { a.help = true; }
    else { console.error(`unknown arg: ${k}`); process.exit(2); }
  }
  return a;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  console.log(readFileSync(fileURLToPath(import.meta.url), "utf8").split("\n").slice(1, 40).join("\n").replace(/^ \* +?/gm, "").replace(/^ \*\/?/gm, ""));
  process.exit(0);
}

const REPO = args.repo ? resolve(args.repo) : resolve(__dirname, "..", "..");
const MANIFEST = args.manifest ? resolve(args.manifest) : join(__dirname, "demo-panels.json");
const OUT = resolve(args.out || join(REPO, ".demo-captures"));
const DEMO_ON = args.demo !== "off";
const [VW, VH] = args.viewport.split("x").map((n) => parseInt(n, 10));

// ── resolve playwright (portable across "installed" vs the /opt global) ─────────
async function loadChromium() {
  const candidates = [
    "playwright",
    "/opt/node22/lib/node_modules/playwright/index.js",
    join(REPO, "node_modules/playwright/index.js"),
  ];
  for (const c of candidates) {
    try {
      const mod = await import(c);
      const chromium = mod.chromium || (mod.default && mod.default.chromium);
      if (chromium) return chromium;
    } catch { /* try next */ }
  }
  console.error("ERROR: could not load Playwright. Set NODE_PATH to the playwright install\n" +
    "(e.g. NODE_PATH=/opt/node22/lib/node_modules) or `npm i -D playwright`.");
  process.exit(3);
}

// Resolve a Chromium executable. Prefer PLAYWRIGHT_BROWSERS_PATH auto-resolution;
// fall back to globbing the pinned /opt install used in this environment.
function resolveExecutablePath() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  try {
    const dirs = readdirSync(base).filter((d) => d.startsWith("chromium")).sort();
    for (const d of dirs.reverse()) {
      const exe = join(base, d, "chrome-linux", "chrome");
      if (existsSync(exe)) return exe;
    }
  } catch { /* let Playwright auto-resolve */ }
  return undefined; // undefined → Playwright resolves from its own registry
}

// ── panel selection ─────────────────────────────────────────────────────────────
function selectPanels() {
  const manifest = JSON.parse(readFileSync(MANIFEST, "utf8"));
  let panels = manifest.panels;
  if (args.sdd) panels = panels.filter((p) => p.sdd === args.sdd);
  if (args.panels) {
    const want = new Set(args.panels.split(",").map((s) => s.trim()).filter(Boolean));
    const known = new Set(manifest.panels.map((p) => p.slug));
    for (const w of want) if (!known.has(w)) { console.error(`panel not in manifest: ${w}`); process.exit(2); }
    panels = manifest.panels.filter((p) => want.has(p.slug));
  }
  if (!panels.length) { console.error("no panels selected"); process.exit(2); }
  return panels;
}

// ── main ────────────────────────────────────────────────────────────────────────
async function main() {
  const chromium = await loadChromium();
  const panels = selectPanels();
  mkdirSync(OUT, { recursive: true });
  const executablePath = resolveExecutablePath();
  const browser = await chromium.launch(executablePath ? { executablePath } : {});

  const results = [];
  for (const panel of panels) {
    const page = await browser.newPage({ viewport: { width: VW, height: VH } });
    const errs = [];
    page.on("pageerror", (e) => errs.push(String(e)));
    const apiCalls = [];
    page.on("request", (r) => { if (panel.apiPrefix && r.url().includes(panel.apiPrefix)) apiCalls.push(r.url()); });
    await page.addInitScript((on) => {
      if (on) localStorage.setItem("sovereign-os.demo", JSON.stringify({ schema: 1, on: true }));
      else localStorage.removeItem("sovereign-os.demo");
    }, DEMO_ON);

    const url = "file://" + join(REPO, "webapp", panel.slug, "index.html");
    await page.goto(url, { waitUntil: "load" });
    await page.waitForTimeout(800);

    const probe = await page.evaluate((rowSel) => ({
      badge: !!document.getElementById("so-demo-badge"),
      demoSignals: [...document.querySelectorAll("*")].filter(
        (e) => e.children.length === 0 && /demo[\/-]/.test(e.textContent)).length,
      rows: rowSel ? [...document.querySelectorAll(rowSel)].length : null,
    }), panel.rowSelector);

    const shot = join(OUT, `${panel.slug}-demo${DEMO_ON ? "" : "-off"}.png`);
    await page.screenshot({ path: shot, fullPage: false });
    await page.close();

    // contract assertions
    const fails = [];
    if (DEMO_ON && !probe.badge) fails.push("badge missing");
    if (!DEMO_ON && probe.badge) fails.push("badge present with demo off");
    if (DEMO_ON && panel.rowSelector && !(probe.rows > 0)) fails.push(`no rows for ${panel.rowSelector}`);
    if (DEMO_ON && panel.apiPrefix && apiCalls.length > 0) fails.push(`${apiCalls.length} data call(s) to ${panel.apiPrefix}`);
    if (errs.length > 0) fails.push(`${errs.length} page error(s)`);

    results.push({
      slug: panel.slug, ...probe, dataApiCalls: apiCalls.length,
      pageErrors: errs.length, shot, pass: fails.length === 0, fails,
    });
  }
  await browser.close();

  // report
  let failed = 0;
  for (const r of results) {
    const mark = r.pass ? "PASS" : "FAIL";
    console.log(`${mark}  ${r.slug.padEnd(28)} badge=${r.badge} rows=${r.rows} ` +
      `demoSignals=${r.demoSignals} dataApiCalls=${r.dataApiCalls} pageErrors=${r.pageErrors}` +
      (r.pass ? "" : `  << ${r.fails.join("; ")}`));
    if (!r.pass) failed++;
  }
  console.log(`\n${results.length - failed}/${results.length} panels passed · captures in ${OUT}`);
  if (args.json) console.log("\n" + JSON.stringify(results, null, 2));
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
