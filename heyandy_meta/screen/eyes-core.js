// Andy's eyes, in your browser: show it your thing once, and it finds that thing (not just one like it) in another
// photo. Meta's DINOv2 (with registers, small; Apache-2.0) runs here, in the page, through transformers.js: the photos
// never leave the device. The same idea as Andy's "my mug" on the robot (memory/mine.py): what a thing looks like, as
// numbers.
//
// How: DINOv2 turns each 14-pixel square of a photo into 384 numbers. The squares of the photo that look most like
// the squares of your thing (each one's three best matches) say where it might be: the top few places are cut out, at
// a few sizes, and looked at again whole, and DINOv2's view of the whole cut-out (its CLS token, what retrieval uses)
// is compared with its view of your thing. The best of those is the answer, and only if it's close enough.

export const MODEL = "onnx-community/dinov2-with-registers-small";
export const PATCH = 14;
const MEAN = [0.485, 0.456, 0.406], STD = [0.229, 0.224, 0.225];
const REGISTERS = 4;  // DINOv2 with registers: the CLS token, 4 registers, then the squares

// The model, loaded once: WebGPU where the browser has it, else plain CPU (WASM, 8-bit: 24 MB).
export async function load(transformers, onProgress) {
  const { AutoModel, env } = transformers;
  env.allowLocalModels = false;
  const gpu = typeof navigator !== "undefined" && navigator.gpu && await navigator.gpu.requestAdapter().catch(() => null);
  const options = gpu ? { device: "webgpu", dtype: "fp16" } : { device: "wasm", dtype: "q8" };
  try {
    return { model: await AutoModel.from_pretrained(MODEL, { ...options, progress_callback: onProgress }), ...options };
  } catch (e) {
    if (!gpu) throw e;  // a WebGPU that can't run it: the CPU can
    const cpu = { device: "wasm", dtype: "q8" };
    return { model: await AutoModel.from_pretrained(MODEL, { ...cpu, progress_callback: onProgress }), ...cpu };
  }
}

// A box of a picture as the model's input: its long side `long` pixels (a whole number of squares), normalised.
export function pixels(src, box, long) {
  const s = long / Math.max(box.w, box.h);
  const w = Math.max(PATCH, Math.round(box.w * s / PATCH) * PATCH), h = Math.max(PATCH, Math.round(box.h * s / PATCH) * PATCH);
  const c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(w, h) : Object.assign(document.createElement("canvas"), { width: w, height: h });
  const g = c.getContext("2d");
  g.imageSmoothingQuality = "high";
  g.drawImage(src, box.x, box.y, box.w, box.h, 0, 0, w, h);
  const d = g.getImageData(0, 0, w, h).data, n = w * h, out = new Float32Array(3 * n);
  for (let i = 0; i < n; i++)
    for (let k = 0; k < 3; k++) out[k * n + i] = (d[4 * i + k] / 255 - MEAN[k]) / STD[k];
  return { data: out, w, h, rgb: d };
}

function unit(v, off, dim) {
  let s = 0;
  for (let k = 0; k < dim; k++) s += v[off + k] * v[off + k];
  s = 1 / (Math.sqrt(s) || 1);
  const u = new Float32Array(dim);
  for (let k = 0; k < dim; k++) u[k] = v[off + k] * s;
  return u;
}

// What DINOv2 sees in a box of a picture: the whole (cls) and each square (squares, gw by gh), each of unit length.
export async function look(eyes, transformers, src, box, long) {
  const { Tensor } = transformers;
  await new Promise((r) => setTimeout(r, 0));  // the page's turn first: on a CPU a look never yields, and live it would freeze
  const p = pixels(src, box, long);
  const out = await eyes.model({ pixel_values: new Tensor("float32", p.data, [1, 3, p.h, p.w]) });
  const t = out.last_hidden_state, dim = t.dims[2], v = t.data;
  const gw = p.w / PATCH, gh = p.h / PATCH, squares = [];
  for (let i = 0; i < gw * gh; i++) squares.push(unit(v, (1 + REGISTERS + i) * dim, dim));
  const seen = { cls: unit(v, 0, dim), squares, gw, gh, box, dim };
  seen.colour = colourPrint(p.rgb, p.w, foreground(seen));
  return seen;
}

// The colour of the thing's own pixels, as Andy's "my mug" keeps it on the robot (local/sam_server.py): DINOv2 learned
// to ignore colour (a blue and a red mug of one shape came out 0.94 alike), so a fingerprint of 12 hues by 3
// strengths and 4 greys, the square root of the histogram, so two fingerprints' dot product is how much they overlap.
// The thing's pixels are those in its squares (no SAM mask here): the squares least like the box's edge.
export function colourPrint(rgb, w, squares) {
  const hist = new Float32Array(40);
  for (const i of squares) {
    const gx = i % (w / PATCH), gy = Math.floor(i / (w / PATCH));
    for (let y = gy * PATCH; y < (gy + 1) * PATCH; y += 2) for (let x = gx * PATCH; x < (gx + 1) * PATCH; x += 2) {
      const o = 4 * (y * w + x), r = rgb[o], g = rgb[o + 1], b = rgb[o + 2], mx = Math.max(r, g, b), mn = Math.min(r, g, b);
      const sat = mx ? (mx - mn) * 255 / mx : 0;  // as OpenCV's HSV: hue 0 to 180, saturation and value 0 to 255
      if (sat >= 50) {
        let hue = mx === mn ? 0 : mx === r ? 60 * (((g - b) / (mx - mn)) % 6) : mx === g ? 60 * ((b - r) / (mx - mn) + 2) : 60 * ((r - g) / (mx - mn) + 4);
        if (hue < 0) hue += 360;
        hist[Math.floor(hue / 2 * 12 / 180) % 12 * 3 + Math.min(Math.floor((sat - 50) * 3 / 206), 2)] += 1;
      } else hist[36 + Math.min(3, mx >> 6)] += 1;
    }
  }
  let sum = 0;
  for (const v of hist) sum += v;
  return hist.map((v) => Math.sqrt(v / (sum || 1)));
}

const dot = (a, b) => { let s = 0; for (let k = 0; k < a.length; k++) s += a[k] * b[k]; return s; };

// The squares of a box that are the thing, not its background: those least like the box's edge (their indices).
export function foreground(t) {
  const edge = [];
  for (let y = 0; y < t.gh; y++) for (let x = 0; x < t.gw; x++)
    if (x === 0 || y === 0 || x === t.gw - 1 || y === t.gh - 1) edge.push(t.squares[y * t.gw + x]);
  const bg = new Float32Array(t.dim);
  for (const e of edge) for (let k = 0; k < t.dim; k++) bg[k] += e[k] / edge.length;
  const ranked = t.squares.map((s, i) => [dot(s, bg), i]).sort((a, b) => a[0] - b[0]);
  return ranked.slice(0, Math.max(4, Math.ceil(ranked.length / 2))).map(([, i]) => i);
}
export const thingSquares = (t) => foreground(t).map((i) => t.squares[i]);

// Where in the room each square looks like your thing: for each square, the mean of its three best matches among the
// thing's own squares, smoothed over its neighbours.
export function likeness(thing, room) {
  const mine = thingSquares(thing), raw = new Float32Array(room.squares.length);
  room.squares.forEach((s, i) => {
    let a = -1, b = -1, c = -1;
    for (const m of mine) {
      const d = dot(s, m);
      if (d > a) { c = b; b = a; a = d; } else if (d > b) { c = b; b = d; } else if (d > c) c = d;
    }
    raw[i] = (a + b + c) / 3;
  });
  const map = new Float32Array(raw.length), { gw, gh } = room;
  for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
    let s = 0, n = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const yy = y + dy, xx = x + dx;
      if (yy >= 0 && yy < gh && xx >= 0 && xx < gw) { s += raw[yy * gw + xx] * (dy || dx ? 0.5 : 1); n += dy || dx ? 0.5 : 1; }
    }
    map[y * gw + x] = s / n;
  }
  return map;
}

// The few best places: peaks of the likeness, at least two squares apart. Each comes with a few boxes to try, of
// different sizes: the squares around the peak that are almost as like the thing, and squares a quarter and two
// fifths of the picture's short side; whichever looks most like your thing, looked at again whole, wins.
export function places(map, room, count = 3) {
  const { gw, gh, box } = room, sx = box.w / gw, sy = box.h / gh, taken = new Uint8Array(map.length), out = [];
  const sorted = Float32Array.from(map).sort(), median = sorted[sorted.length >> 1];
  const clip = (x, y, w, h) => {
    const cx = Math.max(box.x, x), cy = Math.max(box.y, y);
    return { x: cx, y: cy, w: Math.min(box.x + box.w, x + w) - cx, h: Math.min(box.y + box.h, y + h) - cy };
  };
  for (let n = 0; n < count; n++) {
    let best = -1;
    for (let i = 0; i < map.length; i++) if (!taken[i] && (best < 0 || map[i] > map[best])) best = i;
    if (best < 0) break;
    const peak = map[best], floor = median + 0.7 * (peak - median), seen = new Uint8Array(map.length), stack = [best];
    let x0 = gw, y0 = gh, x1 = 0, y1 = 0;
    seen[best] = 1;
    while (stack.length) {
      const i = stack.pop(), x = i % gw, y = (i / gw) | 0;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const xx = x + dx, yy = y + dy, j = yy * gw + xx;
        if (xx >= 0 && xx < gw && yy >= 0 && yy < gh && !seen[j] && map[j] >= floor) { seen[j] = 1; stack.push(j); }
      }
    }
    for (let y = Math.max(0, y0 - 2); y <= Math.min(gh - 1, y1 + 2); y++)
      for (let x = Math.max(0, x0 - 2); x <= Math.min(gw - 1, x1 + 2); x++) taken[y * gw + x] = 1;
    const at = { x: box.x + (best % gw + 0.5) * sx, y: box.y + (((best / gw) | 0) + 0.5) * sy }, short = Math.min(box.w, box.h);
    const grown = clip(box.x + (x0 - 1) * sx, box.y + (y0 - 1) * sy, (x1 - x0 + 3) * sx, (y1 - y0 + 3) * sy);
    const tries = [grown];
    for (const f of [0.25, 0.4]) tries.push(clip(at.x - f * short / 2, at.y - f * short / 2, f * short, f * short));
    out.push({ peak, median, at, tries: tries.filter((t) => t.w > 2 * sx && t.h > 2 * sy && t.w * t.h < 0.6 * box.w * box.h) });
  }
  return out.filter((p) => p.tries.length);
}

// The whole search: where it might be, each place looked at again whole, the closest to your thing; and whether
// it's close enough to say "there it is". onLook(what) is told before each look and returns what to call after it.
// How close is close enough was measured (evals/eyes.py: tables put together from two photos of each of eight museum
// objects, CC0, on the CPU as most visitors run it). With it there, among three others: the closest place in 24 of 24,
// "found" in 20, never a wrong one; its colour 0.82 or more. Without it: never "found"; the closest anything came was a
// cup very like the one shown, 0.80. Its twin in other colours (the other photo, hues turned half round): never
// "found" for the three objects in strong colours (their colour 0.66 at most); the white cup's twin, with only its
// painted flowers recoloured, still was, 4 times in 6. Between MAYBE and SURE, or alike but another colour, Andy asks.
export const SURE = 0.82, MAYBE = 0.62, SAME_COLOUR = 0.75;
// What Andy says of the best place: "found" only if it looks like your thing and is its colour; "maybe" (it asks) if
// it's close, or alike but another colour; else "none".
export const verdict = (c) => !c ? "none" : c.whole >= SURE && c.colour >= SAME_COLOUR ? "found" : c.whole >= MAYBE ? "maybe" : "none";
// Live, from a camera (the page's "Sweep the room"), it's the same check with one place a frame and a smaller first
// look: two to four looks a frame instead of about seven, so a frame or two a second on a laptop's CPU.
export async function find(eyes, transformers, thing, src, roomBox, long = 448, onLook = () => () => {}, count = 3, what = "the photo") {
  let done = onLook(what);
  const room = await look(eyes, transformers, src, roomBox, long);
  done();
  const map = likeness(thing, room), candidates = places(map, room, count);
  for (const [k, c] of candidates.entries()) {
    done = onLook(`place ${k + 1} of ${candidates.length}, again`);
    c.whole = -1;
    for (const b of c.tries) {
      const again = await look(eyes, transformers, src, b, 224), whole = dot(again.cls, thing.cls);
      if (whole > c.whole) Object.assign(c, { whole, box: b, colour: dot(again.colour, thing.colour) });
    }
    done();
  }
  candidates.sort((a, b) => b.whole - a.whole);
  const best = candidates[0];
  return { best, candidates, map, gw: room.gw, gh: room.gh,
           verdict: verdict(best) };
}
