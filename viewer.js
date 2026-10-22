// blender-models viewer: a list of everything in this folder, one at a time on a
// turntable.
//
// The environment is built, not photographed, and that is the load-bearing choice
// here. A metalness:1 surface has no diffuse term — every pixel of it is a
// reflection — so the env map *is* the lighting, and every Poly Haven "studio" is
// a photograph of a small room: the metal reflects that room, and light stands and
// ceiling seams land on the walls as streaks. Real emissive panels rendered
// through PMREM get perspective and falloff because the geometry has them, which
// no painted gradient can fake. The long notes on why each panel sits where it
// does are in macmini-demo/macmini.js, where this rig was tuned.
import {
  WebGLRenderer, Scene, PerspectiveCamera, Group, Mesh, Box3, Vector3,
  MeshBasicMaterial, CanvasTexture, PMREMGenerator, PlaneGeometry,
  SphereGeometry, DoubleSide, BackSide, NeutralToneMapping, SRGBColorSpace,
  Color, GLTFLoader, MeshoptDecoder, toCreasedNormals,
} from './three-slim.js';

const W = 260;   // the model is normalised so its longest side is this many units
let H = 102;     // its real height, read off the model once it loads

const AUTO = 0.26;         // rad/s — one full turn every ~24s, always the same speed
const TILT0 = 26;          // degrees of look-down
const DRAG_Y = 0.0062;     // radians per px, horizontal — rotY is in radians
const DRAG_T = 0.30;       // DEGREES per px, vertical — tilt is in degrees
const TILT_MIN = -30, TILT_MAX = 96;   // Y is unlimited, X is a viewing range
const MAX_AVEL = 7;        // rad/s release clamp, so a violent flick can't blur

const canvas = document.getElementById('gl');
const blob = document.querySelector('.shadow');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const qs = new URLSearchParams(location.search);

// Khronos PBR Neutral, not ACES: ACES crushes midtones for the sake of filmic
// highlights, which is exactly wrong for a product shot that has to sit on a page.
const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.toneMapping = NeutralToneMapping;
// A calibration, not a look. The environment below is in arbitrary units, so this
// is the number that puts an aluminium wall on the 182 the reference measures —
// chosen by sweeping it and reading the pixels back, not by eye.
renderer.toneMappingExposure = Number(qs.get('exp') || 1.25);

const scene = new Scene();
// near/far are tight on purpose: 1..6000 spends almost the whole depth buffer on
// empty space in front of the camera, which is what let a logo z-fight its face.
const camera = new PerspectiveCamera(30, 1, 400, 3000);
camera.position.set(0, 0, 1500);

// --- environment ---------------------------------------------------------
// Panels are emissive surfaces, not painted blobs. Their colour is allowed to
// exceed 1 — that number is the emitter's brightness, and it survives because
// three applies tone mapping when drawing to the screen but never into the
// half-float target PMREM renders through. So the key really is brighter than
// white and the metal shows it as a soft gradient instead of one flat wash.
function lit(w, h, intensity, pos, tint = 0xffffff) {
  const m = new Mesh(
    new PlaneGeometry(w, h),
    new MeshBasicMaterial({ color: new Color(tint).multiplyScalar(intensity), side: DoubleSide }),
  );
  m.position.set(...pos);
  m.lookAt(0, 0, 0);
  return m;
}

// A softbox with a scrim on it: bright in the middle, falling off toward the edge.
// The falloff is the point — a flat metal face is a near-perfect mirror, so a hard
// edged panel lights the whole face at exactly one value and it comes out flat.
function softbox(w, h, intensity, pos, inner = 0xffffff, outer = 0xd0d4d8) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, '#' + new Color(inner).getHexString());
  grd.addColorStop(0.55, '#' + new Color(inner).lerp(new Color(outer), 0.42).getHexString());
  grd.addColorStop(0.80, '#' + new Color(inner).lerp(new Color(outer), 0.78).getHexString());
  grd.addColorStop(1, '#' + new Color(outer).getHexString());
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  const tex = new CanvasTexture(c);
  tex.colorSpace = SRGBColorSpace;
  const m = new Mesh(
    new PlaneGeometry(w, h),
    new MeshBasicMaterial({ map: tex, color: new Color(0xffffff).multiplyScalar(intensity), side: DoubleSide }),
  );
  m.position.set(...pos);
  m.lookAt(0, 0, 0);
  return m;
}

// One panel, a gradient across its own width. Two solid cards will not do the job:
// at 5000 across and 1500 out they each cover most of the lower hemisphere, so the
// second just hides behind the first and the split never reaches the model.
function gradPanel(w, h, intensity, pos, bright, dark) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 8;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 256, 0);
  grd.addColorStop(0, '#' + new Color(bright).getHexString());
  grd.addColorStop(1, '#' + new Color(dark).getHexString());
  g.fillStyle = grd;
  g.fillRect(0, 0, 256, 8);
  const tex = new CanvasTexture(c);
  tex.colorSpace = SRGBColorSpace;
  const m = new Mesh(
    new PlaneGeometry(w, h),
    new MeshBasicMaterial({ map: tex, color: new Color(0xffffff).multiplyScalar(intensity), side: DoubleSide }),
  );
  m.position.set(...pos);
  m.lookAt(0, 0, 0);
  return m;
}

function lightboxEnv(pmrem) {
  const s = new Scene();

  // The cyclorama: one huge soft vertical gradient, no features at all. It has to
  // be a mesh, not scene.background — PMREMGenerator's _sceneToCubeUV only handles
  // a Color background, so an equirect background leaves the cube target uncleared
  // and stale pixels land on the walls as vertical streaks.
  //
  // Solved backwards from the reference's own pixels: its top face sits at 246 and
  // its walls at 171..184. In linear light that is 0.92 against 0.43, a 2.1x ratio,
  // and this metal's F0 is 0.55, so the map has to deliver about 1.7 in the first
  // direction and 0.8 in the second. The 0.8 is the part every earlier version got
  // wrong: a metal shows only what it reflects, so the darkest a wall can be is the
  // darkest direction it can see.
  //
  // The dome only carries the falloff — a canvas is sRGB, so nothing painted into
  // it can exceed 1.0, and the 1.7 the top face needs comes from the emissive key
  // added below. That split is not a trick; it is the only way to express a light
  // brighter than white in a map.
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  const v = g.createLinearGradient(0, 0, 0, 256);
  // v=0 is the zenith. Which band matters was measured, not assumed. The camera
  // sits level and it is the MODEL that tips 26 degrees, so the top face reflects
  // 26+26 = 52 up and the front wall reflects 26 the other way, straight into the
  // floor. Treating the walls as reflecting the horizon put them at 120.
  v.addColorStop(0.00, '#fcfdfd');
  v.addColorStop(0.30, '#f4f6f8');
  v.addColorStop(0.44, '#d8dcdf');
  v.addColorStop(0.50, '#b8bcc0');   // horizon
  v.addColorStop(0.62, '#b2b6ba');
  v.addColorStop(1.00, '#aeb2b6');   // floor bounce, so the belly doesn't crush
  g.fillStyle = v;
  g.fillRect(0, 0, 256, 256);

  // Azimuth, and this is the change that stops the model looking like clay. A dome
  // that is a function of height only is rotationally symmetric, and a symmetric
  // environment is indistinguishable from a flat one: every wall of a square box
  // reflects the same value whichever way it is turned, so there is no lit side and
  // no shadow side and the eye reads it as untextured grey. Matching the reference's
  // *mean* buys nothing if the value is the same everywhere.
  //
  // Periodic by construction: u wraps 0->1, so the ramp has to return to where it
  // started or the seam lands on a wall as a hard line.
  g.globalCompositeOperation = 'multiply';
  const h = g.createLinearGradient(0, 0, 256, 0);
  h.addColorStop(0.00, '#ffffff');   // key side
  h.addColorStop(0.38, '#e2e6e9');
  h.addColorStop(0.62, '#9fa4a9');   // shadow side — the only real dark in the map
  h.addColorStop(0.82, '#d6dade');
  h.addColorStop(1.00, '#ffffff');   // back to the key side, seam-free
  g.fillStyle = h;
  g.fillRect(0, 0, 256, 256);
  g.globalCompositeOperation = 'source-over';

  const room = new CanvasTexture(c);
  room.colorSpace = SRGBColorSpace;
  // SphereGeometry's own UVs are already the equirect layout, so no mapping mode is
  // needed and the vertical wrap is seamless by construction.
  s.add(new Mesh(
    new SphereGeometry(7000, 48, 32),
    new MeshBasicMaterial({ map: room, side: BackSide }),
  ));

  // Two keys at opposite azimuths. The top face reflects 52 degrees up *in a
  // particular azimuth*, and that azimuth turns with the model, so a single
  // overhead panel is outside the reflection most of the time — raising one from
  // 2.4 to 3.15 moved the top face by 2. Two overlapping panels cover the sweep and
  // hand the highlight off between them, and a scrim wide enough to always be in
  // view would be a scrim with no gradient.
  s.add(softbox(3400, 3400, 2.6, [-900, 2600, 1500], 0xffffff, 0xb4b9be));
  s.add(softbox(3200, 3200, 2.6, [500, 2650, 1500], 0xffffff, 0xb0b5ba));

  // Strip softboxes, and these are what make it read as aluminium rather than as
  // painted plastic. Anodised metal has a satin finish — wide enough to blur a
  // reflection into a wash, sharp enough to keep a long highlight as a band — and
  // that band only exists if the environment contains a long source. Tall and
  // narrow rather than wide, so each occupies a small slice of azimuth: a wall
  // sweeps azimuth as it turns, so it sees one of these as a vertical band, and
  // widening them smears the band back into the flat wash.
  for (const a of [0.55, 2.65, 4.35]) {
    const r = 2600;
    s.add(lit(430, 5200, 3.2, [Math.cos(a) * r, 1250, Math.sin(a) * r], 0xfdfefe));
  }
  // Cards to either side. These are what the left and right walls show — those face
  // sideways, so they reflect the horizon, not the floor.
  s.add(lit(2600, 1900, 0.45, [2200, 300, 400], 0xc8ced4));
  s.add(lit(1900, 1700, 0.9, [-1900, 600, 1000], 0xeef2f6));
  s.add(lit(1500, 1300, 0.25, [1700, 0, -1000], 0xf2f5f8));
  // Floor bounce, doing more work than the name suggests: at a 26 degree tilt this
  // is the one surface the walls actually reflect. Leaving it dark is what made
  // them render at 120 against the reference's 182. One graded plane rather than
  // two cards — a single flat card pins all four walls to one number.
  s.add(gradPanel(9000, 9000, 1.0, [200, -900, 0], 0xf4f7fa, 0xa9afb5));

  return pmrem.fromScene(s, 0.02, 1, 20000).texture;
}

const pmrem = new PMREMGenerator(renderer);
const envMap = lightboxEnv(pmrem);
pmrem.dispose();

// No lights. Metal has no diffuse term to receive them, and every non-metal part of
// a real model (a black underside, port interiors) already gets its diffuse from
// the environment. An ambient term on top only lifts the blacks, which is the one
// thing that makes a product shot look like a render.

// --- the turntable -------------------------------------------------------
// pivot = the table it stands on (tilt); device = the turntable itself (spin).
// Parenting this way keeps the spin about the model's own axis at every tilt,
// which is what a real turntable does and what a single rotation order can't give.
const pivot = new Group();
const device = new Group();
pivot.add(device);
scene.add(pivot);

// Held back until the first model exists — a metal lit by nothing renders black,
// and a black flash on load looks like a broken page.
canvas.style.opacity = '0';
canvas.style.transition = 'opacity 500ms ease';
const reveal = () => { canvas.style.opacity = '1'; };

// glTF packs metalness in the blue channel of the metallic-roughness texture and
// roughness in the green. Apple's USD carries only a roughness texture, and
// usd2gltf filled the metalness slot with that same greyscale image — so blue
// equals green and metalness gets read as *roughness*. Detected on the pixels
// rather than hardcoded to a name: a real packed map has different means per
// channel, these are identical to three decimals. Dropping the map falls metalness
// back to the authored factor, which is the difference between metal and plastic.
function sameChannels(tex) {
  const im = tex.source?.data;
  if (!im?.width || typeof document === 'undefined') return false;
  const c = document.createElement('canvas');
  c.width = c.height = 32;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(im, 0, 0, 32, 32);
  const d = g.getImageData(0, 0, 32, 32).data;
  for (let i = 0; i < d.length; i += 4) {
    if (Math.abs(d[i] - d[i + 1]) > 2 || Math.abs(d[i + 1] - d[i + 2]) > 2) return false;
  }
  return true;
}

const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);

let current = null;
let anim = null;
let loadSeq = 0;   // arrow-key browsing can start a second load before the first lands

// The one place this viewer plays what the exporter baked. three-slim has no
// AnimationMixer and does not need one: the clips come out sampled once per frame --
// 500 samples for the MacBook's loop -- so reading the two neighbours and
// interpolating between them IS the animation, exactly, at any frame rate. A model
// with no clips (everything else here) leaves anim null and nothing runs.
function armAnim(gltf, root) {
  const tracks = [];
  for (const clip of gltf.animations || []) {
    for (const tr of clip.tracks) {
      const [name, prop] = tr.name.split('.');
      const node = root.getObjectByName(name);
      if (!node) continue;
      tracks.push({
        node, prop, times: tr.times, values: tr.values,
        stride: prop === 'quaternion' ? 4 : 3, t0: tr.times[0],
      });
    }
  }
  if (!tracks.length) { anim = null; return; }
  const t1 = Math.max(...tracks.map(k => k.times[k.times.length - 1]));
  const qa = tracks[0].node.quaternion.clone();
  const qb = qa.clone();
  anim = { tracks, t0: tracks[0].t0, dur: t1 - tracks[0].t0, t: 0, qa, qb };
}

function runAnim(dt) {
  if (!anim) return;
  const { qa, qb } = anim;
  anim.t = (anim.t + dt) % anim.dur;
  for (const { node, prop, times, values, stride, t0 } of anim.tracks) {
    let i = 0;
    while (i + 2 < times.length && times[i + 1] - t0 <= anim.t) i++;
    const j = Math.min(i + 1, times.length - 1);
    const ta = times[i] - t0, tb = times[j] - t0;
    const f = tb > ta ? Math.min(1, Math.max(0, (anim.t - ta) / (tb - ta))) : 0;
    const a = i * stride, b = j * stride;
    if (prop === 'quaternion') {
      qa.fromArray(values, a); qb.fromArray(values, b);
      node.quaternion.slerpQuaternions(qa, qb, f);
    } else {
      node.scale.set(values[a] + (values[b] - values[a]) * f,
                     values[a + 1] + (values[b + 1] - values[a + 1]) * f,
                     values[a + 2] + (values[b + 2] - values[a + 2]) * f);
    }
  }
}

function dispose(root) {
  const mats = new Set();
  root.traverse(o => {
    if (!o.isMesh) return;
    o.geometry.dispose();
    for (const m of [].concat(o.material)) mats.add(m);
  });
  for (const m of mats) {
    for (const k of ['map', 'normalMap', 'aoMap', 'metalnessMap', 'roughnessMap']) m[k]?.dispose();
    m.dispose();
  }
}

// `fix` comes from the model's sidecar JSON and is empty for anything exported
// straight out of Blender. It exists because a converted asset arrives with the
// converter's damage baked in; see macmini/macmini.json for the values and
// macmini-demo/macmini.js for how each one was measured.
function show(entry) {
  if (current) { device.remove(current); dispose(current); current = null; }
  anim = null;
  const seq = ++loadSeq;
  const fix = entry.fix || {};
  const crease = fix.crease ? (fix.crease * Math.PI) / 180 : 0;
  const creased = new Map();
  const seen = new Set();

  loader.load(entry.url, gltf => {
    // A newer selection won the race; this scene was never shown.
    if (seq !== loadSeq) { dispose(gltf.scene); return; }
    const root = gltf.scene;

    const box = new Box3().setFromObject(root);
    const size = box.getSize(new Vector3());
    const mid = box.getCenter(new Vector3());
    const s = W / Math.max(size.x, size.y, size.z);

    root.scale.setScalar(s);
    // centre it on the origin so the spin and the scale both work about the model's
    // own axis
    root.position.set(-mid.x * s, -mid.y * s, -mid.z * s);
    H = size.y * s;

    root.traverse(o => {
      if (!o.isMesh) return;
      if (crease) {
        // usd2gltf drops the USD faceVarying normals and glTF's default is flat, so
        // a converted model arrives faceted. Keyed by geometry, not by mesh: the
        // loader hands the same geometry to every node that references it, so a
        // per-mesh set leaves the second one uncreased.
        let g = creased.get(o.geometry.uuid);
        if (!g) {
          g = toCreasedNormals(o.geometry, crease);
          creased.set(o.geometry.uuid, g);
          if (g !== o.geometry) o.geometry.dispose();
        }
        o.geometry = g;
      }
      const m = o.material;
      if (!m || seen.has(m.uuid)) return;
      seen.add(m.uuid);
      m.envMap = envMap;
      m.envMapIntensity = 1.0;
      // Occlusion atlases are [0,1] and belong on TEXCOORD_0; usd2gltf wrote
      // texCoord 1 for them, which makes a bead-blast layout repeat hundreds of
      // times across a face. Measured per mesh, not guessed.
      if (fix.aoChannel != null && m.aoMap) m.aoMap.channel = fix.aoChannel;
      if (m.metalnessMap && sameChannels(m.metalnessMap)) m.metalnessMap = null;
      // The Apple inlay ships as a near-black swatch in the same palette as the
      // shell, so it renders as a matte printed sticker; on the real machine it is
      // a mirror-polished insert. Named, not inferred: re-export and the name moves.
      if (fix.mirror?.includes(m.name)) { m.metalness = 1; m.roughness = 0.16; }
      // A bead-blast normal authored for AR close-ups is sub-pixel at this size and
      // only aliases into speckle. Kept non-zero so edges still get their shading.
      if (fix.normalScale != null && m.normalMap) m.normalScale.set(fix.normalScale, fix.normalScale);
      m.needsUpdate = true;
    });

    device.add(root);
    armAnim(gltf, root);
    current = root;
    reveal();
  }, undefined, err => {
    console.error(`${entry.url} failed to load`, err);
    reveal();     // a blank stage beats an invisible one
  });
}

// --- state ---------------------------------------------------------------
let rotY = 0.5;
let tilt = TILT0;
let spin = reduce ? 0 : AUTO;
let unitsPerPx = 0.97;
let paused = false;
let open = false;   // the detail dialog; no point rendering a hidden canvas

const dragging = { on: false, id: -1, x: 0, y: 0, t: 0, avel: 0 };
const cur = { scale: 0 };

function resize() {
  // A closed <dialog> lays the canvas out at 0x0. Calibrating unitsPerPx from that
  // makes the first frame after opening compute a model thousands of pixels wide
  // (it then has to ease back). Keep the last good calibration until there is a
  // real size to measure.
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  unitsPerPx = (2 * Math.tan((camera.fov * Math.PI) / 360) * camera.position.z) / h;
}
addEventListener('resize', resize);
resize();

const ease = (a, b, rate, dt) => (reduce ? b : a + (b - a) * Math.min(1, dt * rate));

let prev = performance.now();
function frame(now) {
  // An rAF timestamp can predate the performance.now() taken when the dialog opened,
  // and a negative dt makes the ease() overshoot: a scale of -2.25 mirrored the model
  // and sized it 750px instead of 460. Never let time run backwards.
  const dt = Math.max(0, Math.min(0.05, (now - prev) / 1000));
  prev = now;

  // Nothing on this canvas is visible while the dialog is closed; skip the whole
  // update so the gallery idles at zero GPU work.
  if (open) {
    // The model is sized as a fraction of the stage, never in pixels. The clamp it used
    // to have (30% of the width, floor 240, ceiling 560) pinned it at 560 on a 3840x2160
    // display -- a stamp in the middle of a 4K field. Fractions keep it proportional at
    // any size. W is the model's *longest* side, so the height cap is the one that
    // matters for tall machines (Mac Pro); 0.68 / 0.66 fills the modal stage without
    // touching its edges, and still gives a phone-sized stage a usable 265px subject.
    const vw = canvas.clientWidth || 1;
    const vh = canvas.clientHeight || 1;
    const target = Math.max(200, Math.min(vw * 0.68, vh * 0.56));
    cur.scale = ease(cur.scale, (target * unitsPerPx) / W, 5.0, dt);

    // The blob under the model is HTML, so it has to be told how big the model got --
    // otherwise it stays 360px wide under a 1200px machine. 0.83 / 0.7 / 0.35 / 0.06 are
    // the numbers the fixed CSS used at 1440, expressed against the model instead.
    const px = (W * cur.scale) / unitsPerPx;
    blob.style.width = `${px * 0.83}px`;
    blob.style.height = `${px * 0.7}px`;
    blob.style.transform = `translate(-50%, -50%) translateY(${px * 0.35}px)`;
    blob.style.filter = `blur(${px * 0.06}px)`;

    if (!dragging.on && !paused) {
      if (Math.abs(spin) > AUTO) {
        spin *= Math.pow(0.22, dt);        // momentum bleeds off over a second or two
      } else {
        spin += (AUTO - spin) * Math.min(1, dt * 2.2);
      }
      rotY += spin * dt;
      tilt = ease(tilt, TILT0, 3.2, dt);   // tilt springs back; yaw keeps wherever you left it
    }

    pivot.rotation.x = (tilt * Math.PI) / 180;
    device.rotation.y = rotY;
    device.scale.setScalar(cur.scale);
    runAnim(dt);

    renderer.render(scene, camera);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// --- drag: grab it, throw it, let it settle back into the fixed-speed turn ---
canvas.addEventListener('pointerdown', e => {
  dragging.on = true;
  dragging.id = e.pointerId;
  dragging.x = e.clientX; dragging.y = e.clientY;
  dragging.t = performance.now();
  dragging.avel = 0;
  canvas.setPointerCapture(e.pointerId);
  canvas.style.cursor = 'grabbing';
});

canvas.addEventListener('pointermove', e => {
  if (!dragging.on || e.pointerId !== dragging.id) return;
  const now = performance.now();
  const dt = Math.max(0.008, (now - dragging.t) / 1000);
  const dx = e.clientX - dragging.x;
  const dy = e.clientY - dragging.y;

  const drot = dx * DRAG_Y;
  rotY += drot;
  tilt = Math.min(TILT_MAX, Math.max(TILT_MIN, tilt + dy * DRAG_T));
  dragging.avel = dragging.avel * 0.72 + (drot / dt) * 0.28;

  dragging.x = e.clientX; dragging.y = e.clientY; dragging.t = now;
});

function release(e) {
  if (!dragging.on || e.pointerId !== dragging.id) return;
  dragging.on = false;
  canvas.style.cursor = 'grab';
  spin = Math.min(MAX_AVEL, Math.max(-MAX_AVEL, dragging.avel));
  if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
}
canvas.addEventListener('pointerup', release);
canvas.addEventListener('pointercancel', release);

// --- the gallery ---------------------------------------------------------
const grid = document.getElementById('grid');
const countEl = document.getElementById('model-count');
const dialog = document.getElementById('detail');
const dClose = document.getElementById('detail-close');
const dIndex = document.getElementById('detail-index');
const dTitle = document.getElementById('detail-title');
const dTris = document.getElementById('detail-tris');
const dTags = document.getElementById('detail-tags');
const dUrl = document.getElementById('detail-url');
const dFix = document.getElementById('detail-fix');
const dPrev = document.getElementById('detail-prev');
const dNext = document.getElementById('detail-next');
const dDownload = document.getElementById('detail-download');

const faces = n => (n ? `${n.toLocaleString('en-US')} 面` : '—');
const pad = n => String(n).padStart(2, '0');
let shownEntry = null;
let pushedEntry = false;

function card(entry, i) {
  const a = document.createElement('a');
  a.className = 'card';
  a.href = `?m=${encodeURIComponent(entry.url)}`;
  a.setAttribute('aria-label', `打开 ${entry.title} 的 3D 详情`);
  a.style.setProperty('--d', `${Math.min(i, 7) * 55}ms`);

  const media = document.createElement('div');
  media.className = 'card-media';
  if (entry.thumb) {
    const img = document.createElement('img');
    img.src = entry.thumb;
    img.alt = '';
    img.loading = i < 4 ? 'eager' : 'lazy';
    img.decoding = 'async';
    media.append(img);
  }

  const meta = document.createElement('div');
  meta.className = 'card-meta';
  const num = document.createElement('span');
  num.className = 'card-num';
  num.textContent = pad(i + 1);
  const title = document.createElement('span');
  title.className = 'card-title';
  title.textContent = entry.title;
  const tris = document.createElement('span');
  tris.className = 'card-tris';
  tris.textContent = faces(entry.tris);
  meta.append(num, title, tris);

  const go = document.createElement('span');
  go.className = 'card-go';
  go.textContent = '打开';
  go.setAttribute('aria-hidden', 'true');

  a.append(media, meta, go);
  a.addEventListener('click', ev => {
    // A modified click is a request for a new tab; the href is a working deep link.
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    openEntry(entry, { push: true });
  });
  return a;
}

function fillPanel(entry) {
  const i = entries.indexOf(entry);
  dIndex.textContent = `MODEL ${pad(i + 1)} / ${pad(entries.length)}`;
  dTitle.textContent = entry.title;
  dTris.textContent = entry.tris ? `${entry.tris.toLocaleString('en-US')} 三角面` : '—';
  dTags.replaceChildren();
  for (const tag of ['GLB', 'Y-up', '1 unit = 1 m', 'CORS *']) {
    const s = document.createElement('span');
    s.textContent = tag;
    dTags.append(s);
  }
  dUrl.textContent = new URL(entry.url, location.href).href;
  dFix.hidden = !Object.keys(entry.fix || {}).length;
  dDownload.href = entry.url;
  dDownload.setAttribute('download', entry.url.split('/').pop());
}

function openEntry(entry, { push = false } = {}) {
  if (!entry) return;
  shownEntry = entry;
  fillPanel(entry);

  if (!dialog.open) {
    dialog.showModal();
    dialog.focus();                 // showModal() otherwise lands on the close button
    open = true;
    document.body.classList.add('detail-open');
    resize();                       // showModal forces layout, so this measures the real stage
  }
  show(entry);
  document.title = `${entry.title} · blender-models`;

  const url = `?m=${encodeURIComponent(entry.url)}`;
  if (push) {
    history.pushState({ model: entry.url }, '', url);
    pushedEntry = true;
  } else {
    history.replaceState({ model: entry.url }, '', url);
  }
}

function requestClose() {
  if (!dialog.open) return;
  // If opening the dialog added a history entry, closing should consume it rather
  // than leave the back button pointing at a model nobody is looking at.
  if (pushedEntry) { history.back(); return; }
  dialog.close();
}

function step(delta) {
  if (!shownEntry || !entries.length) return;
  const i = entries.indexOf(shownEntry);
  openEntry(entries[(i + delta + entries.length) % entries.length]);
}

dClose.addEventListener('click', requestClose);
dPrev.addEventListener('click', () => step(-1));
dNext.addEventListener('click', () => step(1));
dialog.addEventListener('cancel', ev => { ev.preventDefault(); requestClose(); });
dialog.addEventListener('click', ev => { if (ev.target === dialog) requestClose(); });
dialog.addEventListener('keydown', ev => {
  if (ev.key === 'ArrowLeft') { ev.preventDefault(); step(-1); }
  if (ev.key === 'ArrowRight') { ev.preventDefault(); step(1); }
});
dialog.addEventListener('close', () => {
  open = false;
  document.body.classList.remove('detail-open');
  document.title = 'blender-models — Apple 产品高精度模型库';
  pushedEntry = false;
  if (location.search) history.replaceState(null, '', location.pathname);
});

addEventListener('popstate', () => {
  const want = new URLSearchParams(location.search).get('m');
  const entry = entries.find(e => e.url === want);
  if (entry) { pushedEntry = false; openEntry(entry); }
  else if (dialog.open) dialog.close();
});

// GitHub Pages is static: there is no /api/models, so fall back to the manifest
// committed by build_manifest.py. Locally the live index stays authoritative, so
// dropping a .glb in a folder still shows up without regenerating anything.
const entries = await fetch('api/models')
  .then(r => (r.ok ? r.json() : Promise.reject(new Error(`api/models ${r.status}`))))
  .catch(() => fetch('models.json').then(r => r.json()));
countEl.textContent = entries.length ? `${entries.length} 个模型` : '还没有模型';

if (entries.length) {
  const io = 'IntersectionObserver' in window
    ? new IntersectionObserver((rows, obs) => {
        for (const r of rows) {
          if (!r.isIntersecting) continue;
          r.target.classList.add('in');
          obs.unobserve(r.target);
        }
      }, { threshold: .12, rootMargin: '0px 0px -6% 0px' })
    : null;
  entries.forEach((entry, i) => {
    const a = card(entry, i);
    grid.append(a);
    if (io) io.observe(a); else a.classList.add('in');
  });
} else {
  const empty = document.createElement('p');
  empty.className = 'card-empty';
  empty.textContent = '把导出的 .glb 放进这个目录下的任意文件夹，刷新即可。';
  grid.append(empty);
}

// Deep link: ?m=imac27/imac27.glb opens that model straight away.
const initial = entries.find(e => e.url === qs.get('m'));
if (initial) openEntry(initial);

// --- page chrome ---------------------------------------------------------
const top = document.getElementById('top');
const onScroll = () => top.classList.toggle('scrolled', scrollY > 24);
addEventListener('scroll', onScroll, { passive: true });
onScroll();

// The card's radial highlight follows the pointer; one delegated listener rather
// than eight, and only the hovered card is touched.
grid.addEventListener('pointermove', ev => {
  const el = ev.target.closest('.card');
  if (!el) return;
  const r = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${ev.clientX - r.left}px`);
  el.style.setProperty('--my', `${ev.clientY - r.top}px`);
});

for (const btn of document.querySelectorAll('.copy')) {
  btn.addEventListener('click', async () => {
    const target = btn.dataset.copy;
    const text = (target ? document.querySelector(target)?.textContent
                         : btn.closest('.snippet')?.querySelector('pre code')?.textContent) || '';
    const label = btn.textContent;
    try {
      await navigator.clipboard.writeText(text.trim());
      btn.textContent = '已复制';
      btn.classList.add('done');
    } catch {
      btn.textContent = '复制失败';
    }
    setTimeout(() => { btn.textContent = label; btn.classList.remove('done'); }, 1400);
  });
}

// screenshot probes — a spinning turntable can't be screenshotted at a known angle
window.__probe = () => ({ px: (W * cur.scale) / unitsPerPx, py: (H * cur.scale) / unitsPerPx, scale: cur.scale, tilt, rotY, spin });
window.__debug = {
  scene, freeze: v => { paused = v; }, rot: v => { rotY = v; }, tilt: v => { tilt = v; },
  open: (url) => openEntry(entries.find(e => e.url === url)),
};
