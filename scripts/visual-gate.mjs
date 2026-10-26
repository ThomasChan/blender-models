#!/usr/bin/env node
// Render each candidate GLB beside the file it would replace, at fixed camera
// angles, and compare the actual frames. Metadata can say a model survived
// compression while a coplanar screen turns into gray wedges at one angle.
//
//   node scripts/visual-gate.mjs --candidate scripts/.optimize-out/level-0 --quick
//   node scripts/visual-gate.mjs --candidate scripts/.optimize-out/level-1 --apply
//
// --apply promotes only the models that pass and then rebuilds models.json.
// A full run is the 8 cardinal azimuths plus the 3 development angles, at 2
// tilts; --quick is just the 3 development angles and is refused with --apply
// unless --force is passed.
//
// Before rendering, each candidate is decoded independently and its world
// bounds and triangle count are compared to the file it would replace; a
// candidate larger in bytes than the file it would replace is rejected too.
// A meshopt GLB has no stored fallback accessors, so the Python checker in the
// skill cannot measure it; this is the second path that covers those files.
//
// --anim <seconds> pins a baked animation (default 4 s); without it the two
// sides can be captured at different points in the loop.
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { NodeIO, getBounds } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
import { chromium } from 'playwright';
import sharp from 'sharp';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'scripts', '.optimize-out');
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const flag = (name) => args.includes(`--${name}`);

const candidate = path.resolve(ROOT, arg('candidate', path.join(OUT, 'level-0')));
const apply = flag('apply');
const quick = flag('quick');
const only = arg('only', '').split(',').filter(Boolean);
const threshold = Number(arg('threshold', '500'));
if (apply && quick && !flag('force')) {
  throw new Error('--apply needs the full sweep; drop --quick (or pass --force to override)');
}
if (!fs.existsSync(candidate)) throw new Error(`candidate not found: ${candidate}`);

const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'models.json'), 'utf8'));
// The development angles caught the MacBook Pro's z-fighting at 1.40 rad; a
// uniform 8-angle sweep lands at 1.57 and can miss it. Keep both sets.
const DEV_AZIMUTHS = [0.3, 0.85, 1.4];
const AZIMUTHS = quick
  ? DEV_AZIMUTHS
  : [...new Set([
    ...[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (i * Math.PI) / 4),
    ...DEV_AZIMUTHS,
  ])].sort((a, b) => a - b);
const TILTS = quick ? [26] : [8, 26];   // degrees; 8 is a grazing look at vertical panels
const STAGE = { width: 1280, height: 860 };
const ARTIFACT_DIFF = 48;               // per-channel difference that counts as visible
// Baked animations are pinned to one time so both sides capture the same pose.
// 4 s is inside the MacBook's open-lid, screen-on window (0.9 s .. 11 s).
const animT = Number(arg('anim', '4'));
if (!Number.isFinite(animT) || animT < 0) throw new Error('--anim must be a non-negative number');

const models = manifest
  .map((e) => e.url)
  .filter((rel) => !only.length || only.some((s) => rel.includes(s)))
  .filter((rel) => fs.existsSync(path.join(candidate, rel)))
  .sort();
if (!models.length) throw new Error(`no candidate .glb matched under ${candidate}`);

const site = fs.mkdtempSync(path.join(os.tmpdir(), 'blender-models-gate-'));
const shots = path.join(OUT, 'gate', new Date().toISOString().replace(/[:.]/g, '-'));
fs.mkdirSync(shots, { recursive: true });
for (const side of ['before', 'after']) {
  const dir = path.join(site, side);
  fs.mkdirSync(dir, { recursive: true });
  for (const f of ['index.html', 'viewer.js', 'viewer.css', 'three-slim.js']) {
    fs.copyFileSync(path.join(ROOT, f), path.join(dir, f));
  }
}

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.glb': 'model/gltf-binary',
  '.webp': 'image/webp',
  '.png': 'image/png',
};
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  // Make the viewer exercise its production fallback: /api/models only exists
  // under serve.py, so a static page must read the committed models.json.
  if (pathname.endsWith('/api/models')) { res.writeHead(404); res.end(); return; }
  const rel = pathname.endsWith('/') ? `${pathname}index.html` : pathname;
  const file = path.join(site, rel);
  if (!file.startsWith(site + path.sep)) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, (err, body) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, {
      'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(body);
  });
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;

function prepare(rel) {
  const entry = manifest.find((e) => e.url === rel);
  if (!entry) throw new Error(`${rel} is not in models.json`);
  for (const [side, file] of [['before', path.join(ROOT, rel)], ['after', path.join(candidate, rel)]]) {
    const dst = path.join(site, side, rel);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(file, dst);
    fs.writeFileSync(path.join(site, side, 'models.json'),
      `${JSON.stringify([entry], null, 2)}\n`);
    if (entry.thumb && fs.existsSync(path.join(ROOT, entry.thumb))) {
      const thumbDst = path.join(site, side, entry.thumb);
      fs.mkdirSync(path.dirname(thumbDst), { recursive: true });
      fs.copyFileSync(path.join(ROOT, entry.thumb), thumbDst);
    }
  }
}

async function settle(page) {
  let last = -1;
  for (let i = 0; i < 30; i++) {
    const scale = await page.evaluate(() => window.__probe().scale);
    if (Math.abs(scale - last) < 1e-4) return;
    last = scale;
    await page.waitForTimeout(100);
  }
  throw new Error('model scale never settled');
}

async function shot(page, side, rel, az, tilt) {
  const url = `${origin}/${side}/?m=${encodeURIComponent(rel)}`;
  await page.goto(url, { waitUntil: 'load' });
  // `scale` is already > 0 while the load-in tween runs; wait for `ready`, or
  // the debug hooks land before the model exists and the pose is whatever the
  // animation happened to reach by screenshot time.
  await page.waitForFunction(
    () => window.__probe && window.__probe().ready && window.__probe().scale > 0,
    null, { timeout: 30000 },
  );
  await page.evaluate(({ az, tilt, animT }) => {
    window.__debug.freeze(true);
    window.__debug.rot(az);
    window.__debug.tilt(tilt);
    window.__debug.anim(animT);
  }, { az, tilt, animT });
  await settle(page);
  await page.evaluate(
    () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  const box = await page.locator('canvas').boundingBox();
  if (!box) throw new Error('stage canvas has no box');
  const file = path.join(shots,
    `${rel.replace(/[\\/.]/g, '-')}-${az.toFixed(2)}-${tilt}-${side}.png`);
  await page.screenshot({
    path: file,
    clip: {
      x: Math.round(box.x), y: Math.round(box.y),
      width: Math.round(box.width), height: Math.round(box.height),
    },
  });
  return file;
}

async function pixels(file) {
  return sharp(file).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
}

function diff(a, b) {
  if (a.info.width !== b.info.width || a.info.height !== b.info.height) {
    throw new Error(`frame size changed: ${a.info.width}x${a.info.height} vs ${b.info.width}x${b.info.height}`);
  }
  const n = a.info.width * a.info.height;
  let big = 0;
  let max = 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const j = i * 4;
    const d = Math.max(
      Math.abs(a.data[j] - b.data[j]),
      Math.abs(a.data[j + 1] - b.data[j + 1]),
      Math.abs(a.data[j + 2] - b.data[j + 2]),
    );
    if (d > ARTIFACT_DIFF) big++;
    if (d > max) max = d;
    sum += d;
  }
  return { big, max, mean: sum / n, pixels: n };
}

await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.decoder': MeshoptDecoder,
});

function countTris(node) {
  let n = 0;
  const mesh = node.getMesh?.();
  if (mesh) {
    for (const prim of mesh.listPrimitives()) {
      if (prim.getMode() !== 4) throw new Error('non-triangle primitive');
      const pos = prim.getAttribute('POSITION');
      if (!pos) throw new Error('primitive has no POSITION');
      const idx = prim.getIndices();
      n += (idx ? idx.getCount() : pos.getCount()) / 3;
    }
  }
  for (const child of node.listChildren()) n += countTris(child);
  return n;
}

async function measure(file) {
  const doc = await io.read(file);
  const root = doc.getRoot();
  // macmini.glb has a scene but no default scene index; three.js renders
  // scenes[0] anyway, so measure the same one.
  const scene = root.getDefaultScene() || root.listScenes()[0];
  if (!scene) throw new Error('no scene');
  const b = getBounds(scene);
  const dims = [b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2]]
    .map((v) => v * 1000);
  return { dims, tris: countTris(scene) };
}

async function verify(rel) {
  const want = await measure(path.join(ROOT, rel));
  const got = await measure(path.join(candidate, rel));
  const wantBytes = fs.statSync(path.join(ROOT, rel)).size;
  const gotBytes = fs.statSync(path.join(candidate, rel)).size;
  const ws = [...want.dims].sort((a, b) => a - b);
  const gs = [...got.dims].sort((a, b) => a - b);
  const off = gs.map((v, i) => Math.abs(v - ws[i]));
  const reason = [];
  // An optimization that grows the file is a regression, not a promotion.
  if (gotBytes > wantBytes) {
    reason.push(`bytes ${wantBytes} -> ${gotBytes} (candidate is larger)`);
  }
  if (got.tris !== want.tris) {
    reason.push(`tris ${want.tris} -> ${got.tris}`);
  }
  if (Math.max(...off) > 0.1) {
    reason.push(`dims ${ws.map((v) => v.toFixed(2)).join('x')} -> `
      + `${gs.map((v) => v.toFixed(2)).join('x')} mm`);
  }
  return {
    ok: reason.length === 0,
    wantDims: want.dims,
    gotDims: got.dims,
    wantSorted: ws,
    gotSorted: gs,
    wantBytes,
    gotBytes,
    wantTris: want.tris,
    gotTris: got.tris,
    reason: reason.join('; '),
  };
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: STAGE, deviceScaleFactor: 1, reducedMotion: 'reduce',
});
const pageErrors = [];
page.on('pageerror', (e) => pageErrors.push(String(e)));

const results = [];
for (const rel of models) {
  const entry = manifest.find((e) => e.url === rel);
  let check;
  try {
    check = await verify(rel);
  } catch (e) {
    check = { ok: false, reason: `could not measure: ${e.message}` };
  }
  if (!check.ok) {
    results.push({ rel, title: entry?.title || rel, pass: false, verify: check });
    console.log(`FAIL  ${rel.padEnd(34)} precheck: ${check.reason}`);
    continue;
  }
  console.log(`OK    ${rel.padEnd(34)} dims (glb axes) `
    + `${check.gotDims.map((v) => v.toFixed(2)).join(' x ')} mm, `
    + `tris=${check.gotTris}, ${(check.gotBytes / 1048576).toFixed(2)} MB`);
  prepare(rel);
  let worst = { big: -1, mean: 0, max: 0, az: 0, tilt: 0, before: '', after: '' };
  for (const az of AZIMUTHS) {
    for (const tilt of TILTS) {
      const before = await shot(page, 'before', rel, az, tilt);
      const after = await shot(page, 'after', rel, az, tilt);
      const d = diff(await pixels(before), await pixels(after));
      if (d.big > worst.big || (d.big === worst.big && d.max > worst.max)) {
        worst = { ...d, az, tilt, before, after };
      }
    }
  }
  const pass = worst.big <= threshold;
  results.push({ rel, title: entry?.title || rel, pass, verify: check, ...worst });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${rel.padEnd(34)} worst ${worst.az.toFixed(2)}rad/${worst.tilt}deg  big=${worst.big}  mean=${worst.mean.toFixed(2)}  max=${worst.max}`);
  if (!pass) console.log(`      ${worst.before}\n      ${worst.after}`);
}
await browser.close();
await new Promise((resolve) => server.close(resolve));

const report = {
  candidate: path.relative(ROOT, candidate),
  quick,
  threshold,
  artifactDiff: ARTIFACT_DIFF,
  animT,
  pageErrors,
  results,
};
fs.writeFileSync(path.join(shots, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
console.log(`\nreport: ${path.relative(ROOT, path.join(shots, 'report.json'))}`);
if (pageErrors.length) console.log(`page errors: ${pageErrors.join(' | ')}`);

if (apply) {
  const passed = results.filter((r) => r.pass);
  for (const r of passed) {
    fs.copyFileSync(path.join(candidate, r.rel), path.join(ROOT, r.rel));
    console.log(`applied ${r.rel}`);
  }
  if (passed.length) {
    const run = spawnSync('python3', ['build_manifest.py'], { cwd: ROOT, stdio: 'inherit' });
    if (run.status !== 0) process.exitCode = 1;
  }
  if (passed.length < results.length) {
    console.log(`${results.length - passed.length} model(s) kept at their previous level`);
    process.exitCode = 1;
  }
}

fs.rmSync(site, { recursive: true, force: true });
if (results.some((r) => !r.pass)) process.exitCode = 1;
