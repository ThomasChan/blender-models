#!/usr/bin/env node
// Compress the shipped GLBs. Adapted from dioramas' scripts/optimize.mjs
// (MIT, https://github.com/blendi-remade/dioramas), with the two operations
// that break thin screens removed: no `weld`, and Level 0 does not quantize.
//
//   node scripts/optimize-models.mjs --level 0
//   node scripts/optimize-models.mjs --level 1 --only macstudio,macpro
//
// Output goes to scripts/.optimize-out/level-<n>/ and the repo is never
// touched. Promote a candidate only after scripts/visual-gate.mjs passes:
//
//   node scripts/visual-gate.mjs --candidate scripts/.optimize-out/level-0 --apply
//
// Level 0 rewrites textures to WebP and leaves geometry alone. Level 1 also
// quantizes positions (16 bit) and meshopt-compresses the geometry; that is
// what cuts the files to ~1/6, but it can expose z-fighting on coplanar
// screen/back panels, so it must clear the render gate per model.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import {
  dedup, meshopt, prune, quantize, reorder, textureCompress,
} from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'scripts', '.optimize-out');
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const level = Number(arg('level', '0'));
if (level !== 0 && level !== 1) throw new Error('--level must be 0 or 1');
const only = arg('only', '').split(',').filter(Boolean);

function listModels() {
  return fs.readdirSync(ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('.')
      && d.name !== 'scripts' && d.name !== 'skills' && d.name !== 'node_modules')
    .flatMap((d) => fs.readdirSync(path.join(ROOT, d.name))
      .filter((f) => f.endsWith('.glb'))
      .map((f) => `${d.name}/${f}`))
    .filter((rel) => !only.length || only.some((s) => rel.includes(s)))
    .sort();
}

const usesMeshopt = (doc) => doc.getRoot().listExtensionsUsed()
  .some((ext) => ext.extensionName === 'EXT_meshopt_compression');

await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.encoder': MeshoptEncoder,
  'meshopt.decoder': MeshoptDecoder,
});
const outDir = path.join(OUT, `level-${level}`);
const models = listModels();
if (!models.length) throw new Error('no .glb matched');

let beforeTotal = 0;
let afterTotal = 0;
for (const rel of models) {
  const src = path.join(ROOT, rel);
  const dst = path.join(outDir, rel);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  const before = fs.statSync(src).size;

  const doc = await io.read(src);
  // Re-encoding an already meshopt-compressed file without meshopt would
  // decompress it (macmini grew 876 KB -> 2.0 MB). Level 1 recompresses it.
  if (level === 0 && usesMeshopt(doc)) {
    fs.copyFileSync(src, dst);
    beforeTotal += before;
    afterTotal += before;
    console.log(`${rel.padEnd(34)} kept (already meshopt)  ${(before / 1048576).toFixed(2)} MB`);
    continue;
  }

  const ops = [
    dedup(),
    prune(),
    // 2048 is the largest texture any of these models ships; withoutEnlargement
    // inside textureCompress leaves smaller maps alone.
    textureCompress({
      encoder: sharp, targetFormat: 'webp', resize: [2048, 2048], quality: 88,
    }),
    reorder({ encoder: MeshoptEncoder }),
  ];
  if (level === 1) {
    ops.push(quantize({
      quantizePosition: 16, quantizeNormal: 10, quantizeTexcoord: 14,
    }));
  }
  await doc.transform(...ops);
  if (level === 1) await doc.transform(meshopt({ encoder: MeshoptEncoder, level: 'high' }));
  await io.write(dst, doc);

  const after = fs.statSync(dst).size;
  beforeTotal += before;
  afterTotal += after;
  const saved = Math.round(100 * (1 - after / before));
  console.log(`${rel.padEnd(34)} ${(before / 1048576).toFixed(2)} → ${(after / 1048576).toFixed(2)} MB  (${saved}%)`);
}

console.log(`\nlevel ${level}: ${(beforeTotal / 1048576).toFixed(2)} → ${(afterTotal / 1048576).toFixed(2)} MB, ${models.length} models`);
console.log(`candidates: ${path.relative(ROOT, outDir)}`);
