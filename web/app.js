/* EHD viewer.
 *
 * 74k log rectangles on a shared time axis.  Rendering is canvas-based with
 * viewport culling; DOM nodes at this count would be hopeless.
 *
 * The archive is extremely top-heavy - 7 logs are alive in 5000 BC and 60,313
 * in 1971 - so the packed layout is ~60,000 rows tall.  That shape is the point
 * rather than a bug, so the viewer zooms on both axes instead of pretending the
 * data fits on one screen.
 */

'use strict';

const GAP = 2;                 // blank years between logs sharing a row
const BAND_GAP = 6;            // blank rows between taxon bands
const MIN_PX_PER_ROW = 0.002;  // ~61k rows must fit a screen at "reset view"
const MAX_PX_PER_ROW = 22;

const state = {
  index: null,
  buf: null,          // Int32Array, 6 fields per log
  n: 0,
  mode: 'band',
  era: 'all',
  enabled: new Set(),
  rows: null,         // Int32Array: current row per log (after any repack)
  rowCount: 0,
  visible: null,      // Int32Array of log indices currently shown
  bandOffsets: [],
  view: { xYear: 0, pxPerYear: 1, yRow: 0, pxPerRow: 1 },
  hover: -1,
  selected: -1,
  dpr: 1,

  display: 'timeline',  // or 'map'; not `view`, which is the timeline's viewport
  place: null,        // { sites: Set of site indices, label } restricting the timeline
  points: [],         // map circles: one per distinct published coordinate
  sitePoint: null,    // Int32Array: site index -> point index, -1 if unmapped
  pointCounts: null,  // Int32Array: logs per point per taxon, after taxon + era
  pointTotals: null,
  siteCounts: null,   // Int32Array: logs per site, after taxon + era
  drawOrder: [],      // non-empty points, largest first so small ones sit on top
  unmapped: { sites: 0, logs: 0 },
  basemap: null,
  mapView: { cx: 0, cy: 0, scale: 0.001, fitted: false },
  mapHover: -1,
  mapSelected: -1,
  mapFocus: -1,       // collection to mark in the place panel ("Show on map")
  selectedHidden: false,  // the timeline selection is filtered out
  sizeK: 1.2,         // px of radius per sqrt(log)
};

const F = 6;  // fields per log
const START = 0, END = 1, ROW_U = 2, ROW_B = 3, GROUP = 4, SITE = 5;

const $ = (id) => document.getElementById(id);
const canvas = $('canvas');
const ctx = canvas.getContext('2d', { alpha: false });

/* ------------------------------------------------------------------ load */

// Both first-paint payloads ship brotli-compressed under their plain names,
// with `Content-Encoding: br` from web/_headers as the only thing that tells
// the browser so.  If that header is ever dropped, index.json arrives as
// unparseable bytes and logs.bin as garbage geometry -- the latter silently,
// because a brotli stream is a perfectly valid ArrayBuffer.  Both are caught
// and named here, so the cause is on screen instead of a blank canvas.
const ENCODING_HINT =
  'data/index.json and data/logs.bin are served brotli-compressed; check that ' +
  'Content-Encoding: br is being applied.';

async function load() {
  const [index, binBuf] = await Promise.all([
    fetch('data/index.json')
      .then((r) => r.json())
      .catch((err) => {
        throw new Error(`data/index.json did not parse (${err}). ${ENCODING_HINT}`);
      }),
    fetch('data/logs.bin').then((r) => r.arrayBuffer()),
  ]);
  state.index = index;

  const expected = index.n_logs * F * 4;
  if (binBuf.byteLength !== expected) {
    throw new Error(
      `data/logs.bin is ${binBuf.byteLength} bytes, expected ${expected} ` +
      `(${index.n_logs} logs x ${F} fields x 4). ${ENCODING_HINT}`
    );
  }
  state.buf = new Int32Array(binBuf);
  state.n = index.n_logs;
  index.groups.forEach((g) => state.enabled.add(g));

  // Take the layout and era from the controls rather than assuming the
  // defaults: browsers restore a <select>'s last value on reload, which left
  // the menu saying "Packed together" over a by-taxon drawing.
  state.mode = $('mode').value;
  state.era = $('era').value;
  state.sizeK = Number($('size').value);
  if (location.hash === '#map') state.display = 'map';
  syncDisplayControls();

  buildPoints();
  buildLegend();
  applyFilters();
  $('loading').remove();

  const s = index.stats;
  $('headline').textContent =
    `${s.logs_plotted.toLocaleString()} logs · ${s.n_sites.toLocaleString()} sites · ` +
    `${fmtYear(index.year_min)} to ${fmtYear(index.year_max)}`;
  $('f-counts').textContent =
    `${s.files_used.toLocaleString()} files used of ${s.files_listed.toLocaleString()} listed ` +
    `(${s.files_skipped_noaa.toLocaleString()} duplicate encodings, ` +
    `${s.files_skipped_variant.toLocaleString()} variant measurements skipped)`;
  $('f-provenance').textContent =
    (s.logs_anchored
      ? `${s.logs_anchored.toLocaleString()} floating logs placed by their published calendar anchor · `
      : '') +
    `${s.logs_floating.toLocaleString()} floating logs withheld — they carry no calendar date` +
    (s.logs_withdrawn
      ? ` · ${s.logs_withdrawn.toLocaleString()} logs from ${s.sites_withdrawn} studies NCEI has withdrawn not shown`
      : '');
  // No resetView() here: it fits the rows to the canvas height, and filling
  // the footer above can wrap it and shrink the canvas by 30-70 px.  The
  // caller resets once layout has settled.
}

/* -------------------------------------------------------------- packing */

/* First-fit packing over a segment tree of row occupancy.
 *
 * rows[i] holds the leftmost (earliest) year occupied in row i, and a log fits
 * in the first row whose value clears its end year.  A linear scan would be
 * O(n * rows) - about 4 billion operations at this corpus size - so the tree
 * finds the leftmost qualifying row in O(log rows) instead. */
/* Writes each log's row into `out`, which the caller sizes to the whole corpus.
 *
 * `out` must be indexed by global log index, not by position within `order`:
 * a filtered `order` is short while its indices stay corpus-wide, and an
 * out-of-bounds TypedArray write is silently discarded rather than throwing -
 * which previously collapsed every filtered taxon onto row 0.
 *
 * Returns the number of rows used. */
function packRows(order, out) {
  const n = order.length;
  if (!n) return 0;

  // At most one row per log, so `n` leaves always suffice.
  let size = 1;
  while (size < n) size <<= 1;
  const INF = 0x7fffffff;
  const tree = new Int32Array(2 * size).fill(INF);  // max over each subtree

  let used = 0;

  for (let k = 0; k < n; k++) {
    const li = order[k];
    const start = state.buf[li * F + START];
    const end = state.buf[li * F + END];
    const target = end + GAP;

    // Descend to the leftmost leaf whose stored value exceeds `target`.
    let node = 1;
    if (tree[node] <= target) break;  // cannot happen: `size` >= n leaves
    while (node < size) {
      node = tree[2 * node] > target ? 2 * node : 2 * node + 1;
    }
    const row = node - size;
    out[li] = row;
    if (row + 1 > used) used = row + 1;

    // Publish the new leftmost year for that row.
    tree[node] = start;
    for (let p = node >> 1; p >= 1; p >>= 1) {
      const v = Math.max(tree[2 * p], tree[2 * p + 1]);
      if (tree[p] === v) break;
      tree[p] = v;
    }
  }
  return used;
}

const ERAS = {
  all: [-Infinity, Infinity],
  pre1000: [-Infinity, 1000],
  pre1500: [-Infinity, 1500],
  medieval: [500, 1500],
  ancient: [-Infinity, 0],       // astronomical 0 = 1 BC: "before 1 CE"
  lateglacial: [-Infinity, -9999],  // astronomical -9999 = 10,000 BC
};

/* One pass serves both views.  The map counts what passes the taxon and era
 * filters but ignores the place filter - every place stays on the map, so the
 * one you came from is still there to click - while the timeline honours all
 * three. */
function applyFilters() {
  const [lo, hi] = ERAS[state.era];
  const groups = state.index.groups;
  const G = groups.length;
  const pointCounts = new Int32Array(state.points.length * G);
  const siteCounts = new Int32Array(state.index.sites.length);
  const keep = [];
  let passing = 0;
  for (let i = 0; i < state.n; i++) {
    const b = i * F;
    const g = state.buf[b + GROUP];
    if (!state.enabled.has(groups[g])) continue;
    if (state.buf[b + START] > hi || state.buf[b + END] < lo) continue;
    const si = state.buf[b + SITE];
    passing++;
    siteCounts[si]++;
    const p = state.sitePoint[si];
    if (p >= 0) pointCounts[p * G + g]++;
    if (state.place && !state.place.sites.has(si)) continue;
    keep.push(i);
  }
  state.visible = Int32Array.from(keep);
  // A filtered-out selection is hidden, not dropped, so it comes back with
  // the filter.  It has no row while hidden: its outline would land on row 0.
  state.selectedHidden = state.selected >= 0 && !state.visible.includes(state.selected);
  $('detail').classList.toggle('open', state.display === 'timeline' && selectionShown());
  state.siteCounts = siteCounts;
  state.pointCounts = pointCounts;
  state.pointTotals = new Int32Array(state.points.length);
  for (let p = 0; p < state.points.length; p++) {
    for (let g = 0; g < G; g++) state.pointTotals[p] += pointCounts[p * G + g];
  }
  state.drawOrder = state.points
    .map((_, p) => p)
    .filter((p) => state.pointTotals[p] > 0)
    .sort((a, b) => state.pointTotals[b] - state.pointTotals[a]);
  state.unmapped = { sites: 0, logs: 0 };
  for (let si = 0; si < siteCounts.length; si++) {
    if (state.sitePoint[si] < 0 && siteCounts[si]) {
      state.unmapped.sites++;
      state.unmapped.logs += siteCounts[si];
    }
  }
  // Every log that passes the filters is in exactly one circle or in the
  // "not mapped" note; a mismatch means the map is misreporting the corpus.
  let mapped = 0;
  for (const t of state.pointTotals) mapped += t;
  if (mapped + state.unmapped.logs !== passing) {
    console.error(
      `map count violation: ${mapped} logs in circles + ${state.unmapped.logs} unmapped ` +
      `!= ${passing} passing the filters`
    );
  }

  const filtered =
    state.era !== 'all' || state.enabled.size !== state.index.groups.length ||
    state.place !== null;

  if (!filtered) {
    // Nothing removed: reuse the layout precomputed by the build step.
    state.rows = null;
    state.rowCount =
      state.mode === 'unified'
        ? state.index.unified_rows
        : bandTotal();
  } else {
    repack();
  }
  computeBandOffsets();
}

function repack() {
  const rows = new Int32Array(state.n);
  if (state.mode === 'unified') {
    const order = Array.from(state.visible).sort(sortByEndDesc);
    state.rowCount = packRows(order, rows);
  } else {
    // Each taxon band packs independently, so a band's height reflects only
    // its own logs.
    const heights = new Array(state.index.groups.length).fill(0);
    for (let g = 0; g < state.index.groups.length; g++) {
      const order = Array.from(state.visible)
        .filter((i) => state.buf[i * F + GROUP] === g)
        .sort(sortByEndDesc);
      if (!order.length) continue;
      heights[g] = packRows(order, rows);
    }
    state.bandHeights = heights;
    state.rowCount = bandTotal(heights);
  }
  state.rows = rows;
  assertNoOverlap();
}

/* The build step proves the *precomputed* layouts are overlap-free, but this
 * client-side repack only runs when a filter is active, so nothing covered it -
 * which is where a silent out-of-bounds write once collapsed whole taxa onto a
 * single row.  Checking here costs O(n log n) per filter change, not per frame. */
function assertNoOverlap() {
  const byRow = new Map();
  for (const i of state.visible) {
    const r = rowOf(i);
    let list = byRow.get(r);
    if (!list) byRow.set(r, (list = []));
    list.push(i);
  }
  for (const [row, items] of byRow) {
    items.sort((a, b) => state.buf[a * F + START] - state.buf[b * F + START]);
    for (let k = 1; k < items.length; k++) {
      const prevEnd = state.buf[items[k - 1] * F + END];
      const start = state.buf[items[k] * F + START];
      if (start - GAP <= prevEnd) {
        console.error(
          `packing violation in row ${row}: ${state.index.series_ids[items[k - 1]]} ` +
          `ends ${prevEnd} but ${state.index.series_ids[items[k]]} starts ${start}`
        );
        return false;
      }
    }
  }
  return true;
}

function sortByEndDesc(a, b) {
  const ea = state.buf[a * F + END], eb = state.buf[b * F + END];
  if (ea !== eb) return eb - ea;
  return state.buf[b * F + START] - state.buf[a * F + START];
}

function bandHeights() {
  return state.rows && state.bandHeights
    ? state.bandHeights
    : state.index.band_heights;
}

function bandTotal(h) {
  const heights = h || bandHeights();
  let t = 0;
  for (const v of heights) if (v) t += v + BAND_GAP;
  return t;
}

function computeBandOffsets() {
  const heights = bandHeights();
  const offs = [];
  let y = 0;
  for (let g = 0; g < heights.length; g++) {
    offs[g] = y;
    if (heights[g]) y += heights[g] + BAND_GAP;
  }
  state.bandOffsets = offs;
}

function selectionShown() {
  return state.selected >= 0 && !state.selectedHidden;
}

function rowOf(i) {
  if (state.rows) {
    const r = state.rows[i];
    return state.mode === 'band' ? state.bandOffsets[state.buf[i * F + GROUP]] + r : r;
  }
  return state.mode === 'unified'
    ? state.buf[i * F + ROW_U]
    : state.bandOffsets[state.buf[i * F + GROUP]] + state.buf[i * F + ROW_B];
}

/* --------------------------------------------------------------- render */

function groupColor(g) {
  const name = state.index.groups[g];
  return getComputedStyle(document.documentElement)
    .getPropertyValue(`--${name}`)
    .trim() || '#888';
}

function resize() {
  const dpr = window.devicePixelRatio || 1;
  const r = canvas.getBoundingClientRect();
  state.dpr = dpr;
  canvas.width = Math.round(r.width * dpr);
  canvas.height = Math.round(r.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

/* The "Reset view" framing of what the filters leave visible. */
function timelineFit() {
  const r = canvas.getBoundingClientRect();
  let lo = state.index.year_min, hi = state.index.year_max;
  if (state.visible && state.visible.length) {
    lo = Infinity; hi = -Infinity;
    for (const i of state.visible) {
      const b = i * F;
      if (state.buf[b + START] < lo) lo = state.buf[b + START];
      if (state.buf[b + END] > hi) hi = state.buf[b + END];
    }
  }
  const pad = Math.max(20, (hi - lo) * 0.02);
  return {
    xYear: lo - pad,
    pxPerYear: r.width / (hi - lo + pad * 2),
    pxPerRow: clamp((r.height - 34) / Math.max(state.rowCount, 1), MIN_PX_PER_ROW, MAX_PX_PER_ROW),
  };
}

/* Zooming out stops a little past the fitted view, as on the map.  The old
 * absolute floors (1e-4 px/yr, MIN_PX_PER_ROW) let a 50" screen reach
 * 8,000,000 BC - 8,000,000 CE with the whole corpus 1.5" tall. */
const ZOOM_OUT_LIMIT = 0.75;

function resetView() {
  if (state.display === 'map') return resetMapView();
  const fit = timelineFit();
  state.view.xYear = fit.xYear;
  state.view.pxPerYear = fit.pxPerYear;
  state.view.yRow = 0;
  state.view.pxPerRow = fit.pxPerRow;
  draw();
}

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const xOf = (year) => (year - state.view.xYear) * state.view.pxPerYear;
const yOf = (row) => (row - state.view.yRow) * state.view.pxPerRow + 26;
const yearAt = (px) => px / state.view.pxPerYear + state.view.xYear;

/* Years are astronomical throughout the data, as in the Tucson files: year 0
 * exists and is 1 BC (neth009 has a ring measured in it).  Only the label
 * converts.  Printing -y for y < 0 put every BC label one year late and called
 * year 0 "0 CE", a year that does not exist. */
function fmtYear(y) {
  return y <= 0 ? `${1 - y} BC` : `${y} CE`;
}

/* The astronomical year that a round historical label belongs at.  Tick marks
 * step through historical numbering (..., -200, -100, 0, 100, ...) so labels
 * read "200 BC", not "201 BC"; historical 0 does not exist and stands for
 * 1 CE. */
function tickYear(h) {
  return h < 0 ? h + 1 : h === 0 ? 1 : h;
}

function draw() {
  if (!state.index) return;
  if (state.display === 'map') return drawMap();
  const r = canvas.getBoundingClientRect();
  const W = r.width, H = r.height;
  const css = getComputedStyle(document.documentElement);

  ctx.fillStyle = css.getPropertyValue('--surface-1').trim();
  ctx.fillRect(0, 0, W, H);

  drawTimeAxis(W, H, css);

  const { pxPerRow } = state.view;
  const h = Math.max(1, pxPerRow - (pxPerRow > 3 ? 1 : 0));
  const groups = state.index.groups;

  // Draw one taxon at a time so fillStyle changes once per group rather than
  // once per rectangle.
  for (let g = 0; g < groups.length; g++) {
    if (!state.enabled.has(groups[g])) continue;
    ctx.fillStyle = groupColor(g);
    const list = state.visible;
    for (let k = 0; k < list.length; k++) {
      const i = list[k];
      const b = i * F;
      if (state.buf[b + GROUP] !== g) continue;
      const y = yOf(rowOf(i));
      if (y < 20 || y > H) continue;
      const x0 = xOf(state.buf[b + START]);
      if (x0 > W) continue;
      const x1 = xOf(state.buf[b + END] + 1);
      if (x1 < 0) continue;
      ctx.fillRect(x0, y, Math.max(1, x1 - x0), h);
    }
  }

  drawBandLabels(W, H, css);
  if (state.hover >= 0) outline(state.hover, css, 1.5);
  if (selectionShown()) outline(state.selected, css, 2.5);
}

function outline(i, css, width) {
  const b = i * F;
  const y = yOf(rowOf(i));
  const x0 = xOf(state.buf[b + START]);
  const x1 = xOf(state.buf[b + END] + 1);
  const h = Math.max(2, state.view.pxPerRow);
  ctx.strokeStyle = css.getPropertyValue('--text-primary').trim();
  ctx.lineWidth = width;
  ctx.strokeRect(x0 - 1, y - 1, Math.max(2, x1 - x0) + 2, h + 2);
}

function niceStep(spanYears, targetTicks) {
  const raw = spanYears / targetTicks;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  for (const m of [1, 2, 2.5, 5, 10]) if (mag * m >= raw) return mag * m;
  return mag * 10;
}

function drawTimeAxis(W, H, css) {
  const left = yearAt(0), right = yearAt(W);
  const step = niceStep(right - left, Math.max(4, Math.floor(W / 110)));
  const start = Math.ceil(left / step) * step;

  ctx.fillStyle = css.getPropertyValue('--surface-2').trim();
  ctx.fillRect(0, 0, W, 22);
  ctx.strokeStyle = css.getPropertyValue('--grid').trim();
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let t = start; t <= right; t += step) {
    const x = Math.round(xOf(tickYear(t))) + 0.5;
    ctx.moveTo(x, 22);
    ctx.lineTo(x, H);
  }
  ctx.stroke();

  ctx.fillStyle = css.getPropertyValue('--text-secondary').trim();
  ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  for (let t = start; t <= right; t += step) {
    const y = tickYear(Math.round(t));
    ctx.textAlign = 'center';
    ctx.fillText(fmtYear(y), xOf(y), 11);
  }
}

function drawBandLabels(W, H, css) {
  if (state.mode !== 'band') return;
  const heights = bandHeights();
  ctx.font = '600 11px ui-sans-serif, system-ui, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  for (let g = 0; g < heights.length; g++) {
    const name = state.index.groups[g];
    if (!heights[g] || !state.enabled.has(name)) continue;
    // Label sits just inside the band's top edge; above it would collide with
    // the time axis for the first band.
    const y = yOf(state.bandOffsets[g]) + 2;
    if (heights[g] * state.view.pxPerRow < 14) continue;
    if (y < 24 || y > H - 12) continue;
    const w = ctx.measureText(name).width;
    ctx.fillStyle = css.getPropertyValue('--surface-1').trim();
    ctx.globalAlpha = 0.72;
    ctx.fillRect(4, y - 1, w + 8, 14);
    ctx.globalAlpha = 1;
    ctx.fillStyle = groupColor(g);
    ctx.fillText(name, 8, y);
  }
}

/* ---------------------------------------------------------- interaction */

function hitTest(px, py) {
  const h = Math.max(2, state.view.pxPerRow);
  for (let k = state.visible.length - 1; k >= 0; k--) {
    const i = state.visible[k];
    const b = i * F;
    const y = yOf(rowOf(i));
    if (py < y - 1 || py > y + h + 1) continue;
    const x0 = xOf(state.buf[b + START]);
    const x1 = Math.max(x0 + 1, xOf(state.buf[b + END] + 1));
    if (px >= x0 - 1 && px <= x1 + 1) return i;
  }
  return -1;
}

let drag = null;

canvas.addEventListener('mousedown', (e) => {
  if (state.display === 'map') {
    drag = { x: e.offsetX, y: e.offsetY, cx: state.mapView.cx, cy: state.mapView.cy, moved: false };
    canvas.classList.add('panning');
    return;
  }
  drag = { x: e.offsetX, y: e.offsetY, xYear: state.view.xYear, yRow: state.view.yRow, moved: false };
  canvas.classList.add('panning');
});

window.addEventListener('mouseup', (e) => {
  if (drag && !drag.moved && state.display === 'map') {
    const p = mapHitTest(e.offsetX, e.offsetY);
    if (p >= 0) openPlace(p); else closePlace();
  } else if (drag && !drag.moved) {
    const i = hitTest(e.offsetX, e.offsetY);
    if (i >= 0) showDetail(i); else closeDetail();
  }
  drag = null;
  canvas.classList.remove('panning');
});

canvas.addEventListener('mousemove', (e) => {
  if (state.display === 'map') return mapMouseMove(e);
  if (drag) {
    const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) drag.moved = true;
    state.view.xYear = drag.xYear - dx / state.view.pxPerYear;
    state.view.yRow = drag.yRow - dy / state.view.pxPerRow;
    draw();
    return;
  }
  const i = hitTest(e.offsetX, e.offsetY);
  if (i !== state.hover) {
    state.hover = i;
    draw();
    updateTooltip(i, e.offsetX, e.offsetY);
  } else if (i >= 0) {
    positionTooltip(e.offsetX, e.offsetY);
  }
});

canvas.addEventListener('mouseleave', () => {
  state.hover = -1;
  state.mapHover = -1;
  $('tooltip').classList.remove('visible');
  draw();
});

/* The wheel zooms both axes about the cursor, as on the map; shift restricts
 * it to rows and alt (option) to time.  Each axis stops at its own clamp, so
 * past MAX_PX_PER_ROW a plain wheel keeps zooming time alone. */
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  if (state.display === 'map') return mapWheel(e);
  const [px, py] = canvasXY(e);
  zoomTimeline(px, py, Math.pow(1.0015, -e.deltaY), !e.altKey, !e.shiftKey);
  draw();
}, { passive: false });

/* Zoom by factor k about canvas point (px, py), keeping that point fixed.
 * Shared by the wheel and a two-finger pinch, so both obey the same clamps. */
function zoomTimeline(px, py, k, rows = true, time = true) {
  const fit = timelineFit();
  if (rows) {
    const before = (py - 26) / state.view.pxPerRow + state.view.yRow;
    state.view.pxPerRow = clamp(
      state.view.pxPerRow * k, Math.min(ZOOM_OUT_LIMIT * fit.pxPerRow, MAX_PX_PER_ROW), MAX_PX_PER_ROW
    );
    state.view.yRow = before - (py - 26) / state.view.pxPerRow;
  }
  if (time) {
    const before = yearAt(px);
    state.view.pxPerYear = clamp(state.view.pxPerYear * k, ZOOM_OUT_LIMIT * fit.pxPerYear, 40);
    state.view.xYear = before - px / state.view.pxPerYear;
  }
}

/* Touch: one finger pans, two pinch-zoom about their midpoint and pan with it.
 * Mouse input stays on the mouse handlers above.  A tap is left alone: the
 * browser follows it with compatibility mouse events (so mousedown/mouseup
 * select as for a click), which a preventDefault here would suppress.  The
 * canvas's touch-action: none keeps the browser from taking the gesture for
 * page scroll or page zoom. */
const touches = new Map();  // pointerId -> [x, y] in canvas px
let touchMoved = false;

function touchCentroid() {
  const ps = [...touches.values()];
  const x = ps.reduce((s, p) => s + p[0], 0) / ps.length;
  const y = ps.reduce((s, p) => s + p[1], 0) / ps.length;
  const d = ps.length > 1 ? Math.hypot(ps[0][0] - ps[1][0], ps[0][1] - ps[1][1]) : 0;
  return { x, y, d };
}

canvas.addEventListener('pointerdown', (e) => {
  if (e.pointerType !== 'touch') return;
  if (touches.size === 0) touchMoved = false;
  touches.set(e.pointerId, canvasXY(e));
});

canvas.addEventListener('pointermove', (e) => {
  if (e.pointerType !== 'touch' || !touches.has(e.pointerId)) return;
  const before = touchCentroid();
  touches.set(e.pointerId, canvasXY(e));
  if (touches.size > 2) return;  // a third finger: ignore until it lifts
  const after = touchCentroid();
  const dx = after.x - before.x, dy = after.y - before.y;
  if (!touchMoved && Math.abs(dx) + Math.abs(dy) < 1 && before.d === after.d) return;
  if (!touchMoved) {
    touchMoved = true;
    state.hover = -1;
    state.mapHover = -1;
    $('tooltip').classList.remove('visible');
  }
  const k = before.d > 0 && after.d > 0 ? after.d / before.d : 1;
  if (state.display === 'map') {
    const mv = state.mapView;
    mv.cx -= dx / mv.scale;
    mv.cy -= dy / mv.scale;
    if (k !== 1) zoomMap(after.x, after.y, k);
  } else {
    state.view.xYear -= dx / state.view.pxPerYear;
    state.view.yRow -= dy / state.view.pxPerRow;
    if (k !== 1) zoomTimeline(after.x, after.y, k);
  }
  draw();
});

for (const type of ['pointerup', 'pointercancel']) {
  canvas.addEventListener(type, (e) => { touches.delete(e.pointerId); });
}

/* From clientX, not offsetX: Chrome reported offsetX (304, 110) for a
 * WheelEvent dispatched at canvas (608, 354). */
function canvasXY(e) {
  const r = canvas.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}

/* -------------------------------------------------------------- tooltip */

function siteOf(i) {
  return state.index.sites[state.buf[i * F + SITE]];
}

function updateTooltip(i, px, py) {
  const tip = $('tooltip');
  if (i < 0) { tip.classList.remove('visible'); return; }
  const b = i * F;
  const site = siteOf(i);
  const s = state.buf[b + START], e = state.buf[b + END];
  tip.innerHTML =
    `<div class="tt-title">${esc(site.common || site.latin || site.species || 'unknown')}</div>` +
    `<div class="tt-years">${fmtYear(s)} – ${fmtYear(e)} · ${e - s + 1} rings</div>` +
    `<div class="tt-row">${esc(site.site)}${site.location ? ', ' + esc(site.location) : ''}</div>`;
  tip.classList.add('visible');
  positionTooltip(px, py);
}

function positionTooltip(px, py) {
  const tip = $('tooltip');
  const r = canvas.getBoundingClientRect();
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.min(px + 14, r.width - w - 6) + 'px';
  tip.style.top = (py > h + 20 ? py - h - 12 : py + 18) + 'px';
}

const esc = (s) =>
  String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* --------------------------------------------------------------- detail */

async function showDetail(i) {
  state.selected = i;
  state.selectedHidden = false;
  draw();
  const b = i * F;
  const site = siteOf(i);
  const seriesId = state.index.series_ids[i];
  const s = state.buf[b + START], e = state.buf[b + END];

  $('d-title').textContent = seriesId;
  const mapped = state.sitePoint[state.buf[b + SITE]] >= 0;
  $('d-map').disabled = !mapped;
  $('d-map').textContent = mapped ? 'Show on map' : 'No coordinates published';
  $('d-map').onclick = () => showOnMap(i);
  $('d-sub').innerHTML =
    `${esc(site.common || site.latin || site.species)} · ${fmtYear(s)} – ${fmtYear(e)} ` +
    `· ${e - s + 1} rings`;

  const rows = [
    ['Species', site.latin || site.species],
    ['Site', site.site],
    ['Location', site.location],
    ['Coordinates', site.lat != null ? `${site.lat.toFixed(3)}, ${site.lon.toFixed(3)}` : ''],
    ['Elevation', site.elev ? site.elev + ' m' : ''],
    ['Measurement', site.variant],
    ['Collected by', site.who],
    ['ITRDB code', site.code],
    ['Dating', datingBadge(site)],
    ['Study', site.url ? `<a href="${esc(site.url)}" target="_blank" rel="noopener">${esc(site.study || site.code)}</a>` : esc(site.study)],
    [site.dois && site.dois.length > 1 ? 'DOIs' : 'DOI', (site.dois || [])
      .map((d) => `<a href="https://doi.org/${esc(d)}" target="_blank" rel="noopener">${esc(d)}</a>`)
      .join('<br>')],
  ];
  $('d-fields').innerHTML = rows
    .filter(([, v]) => v)
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${k === 'Dating' || k === 'Study' || k.startsWith('DOI') ? v : esc(v)}</dd>`)
    .join('');

  $('detail').classList.add('open');
  drawSparkline(null);
  try {
    const site_code = site.code.toLowerCase();
    const data = await fetch(`data/values/${site_code}.json`).then((r) => r.json());
    const rec = data[seriesId];
    if (rec) drawSparkline(rec);
  } catch (err) {
    $('d-spark-caption').textContent = 'ring widths unavailable';
  }
}

function datingBadge(site) {
  const d = site.dating;
  if (d === 'anchored') {
    return '<span class="badge anchored">floating chronology, calendar-anchored ' +
      `±${site.anchor_sigma} yr (1σ)</span><br>${esc(site.anchor_source)}`;
  }
  if (d === 'floating') {
    return '<span class="badge floating">floating — no calendar date</span>';
  }
  if (d === 'unverified') {
    return '<span class="badge">unverified against archive metadata</span>';
  }
  return '<span class="badge">absolutely dated</span>';
}

function drawSparkline(rec) {
  const c = $('spark');
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth || 300, h = 76;
  c.width = w * dpr; c.height = h * dpr;
  const g = c.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = getComputedStyle(document.documentElement);
  g.clearRect(0, 0, w, h);

  if (!rec) { $('d-spark-caption').textContent = 'loading ring widths…'; return; }

  const v = rec.v;
  const real = v.filter((x) => x != null);
  if (!real.length) { $('d-spark-caption').textContent = 'no measurements'; return; }
  const max = Math.max(...real);
  const pad = 4;

  g.strokeStyle = css.getPropertyValue('--axis').trim();
  g.lineWidth = 1;
  g.beginPath(); g.moveTo(0, h - pad + 0.5); g.lineTo(w, h - pad + 0.5); g.stroke();

  g.strokeStyle = css.getPropertyValue('--text-primary').trim();
  g.lineWidth = 1.2;
  g.beginPath();
  let pen = false;
  for (let k = 0; k < v.length; k++) {
    if (v[k] == null) { pen = false; continue; }
    const x = (k / Math.max(v.length - 1, 1)) * w;
    const y = h - pad - (v[k] / max) * (h - pad * 2);
    if (!pen) { g.moveTo(x, y); pen = true; } else g.lineTo(x, y);
  }
  g.stroke();

  const missing = v.length - real.length;
  $('d-spark-caption').textContent =
    `ring width, ${fmtYear(rec.f)} – ${fmtYear(rec.f + v.length - 1)} · ` +
    `peak ${(max * rec.u).toFixed(2)} mm` +
    (missing ? ` · ${missing} year${missing > 1 ? 's' : ''} unmeasured` : '');
}

function closeDetail() {
  state.selected = -1;
  $('detail').classList.remove('open');
  draw();
}

/* ------------------------------------------------------------------ map */

/* One circle per distinct published coordinate, area proportional to the logs
 * there that pass the taxon and era filters, drawn as a pie by taxon.
 * Collections that share a point exactly (42 at one Regensburg coordinate)
 * become one circle; nearby points are never merged.  About 40% of
 * collections publish only 2 decimals (~1 km), so one place can still split
 * into neighbouring circles - that is the data, not a rendering choice.
 *
 * Circles keep their pixel size as the map zooms, as proportional symbols
 * should: zooming separates them rather than inflating them.  Only the hover
 * target has a floor (MAP_MIN_HIT); the drawn radius is always the honest one,
 * so a single log is a ~1 px dot. */

const MAP_MIN_HIT = 4;        // px
const MAP_MAX_SCALE = 60;     // px per km: well past the 0.01 deg precision
const MAP_PAD = 48;           // px kept clear around the data when fitting

/* Zooming out stops a little past "every mapped place fits".  Further out
 * there is nothing more to see, and the basemap's clip box (ehd/basemap.py
 * BBOX) would start to show as a false straight coastline. */
function mapMinScale() {
  return 0.75 * fitScale(state.points.map((_, p) => p));
}

function fitScale(ps) {
  const W = canvas.clientWidth, H = canvas.clientHeight;
  const e = extent(ps);
  return Math.min(
    (W - 2 * MAP_PAD) / Math.max(e.x1 - e.x0, 1),
    (H - 2 * MAP_PAD) / Math.max(e.y1 - e.y0, 1)
  );
}

function extent(ps) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const p of ps) {
    const { x, y } = state.points[p];
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  return { x0, x1, y0, y1 };
}

/* Spherical Lambert azimuthal equal-area, centred where ETRS89-LAEA
 * (EPSG:3035) is: 52 N, 10 E.  Equal-area so that land the circles sit on is
 * not inflated toward the Arctic, as Mercator would do to Fennoscandia.  The
 * sphere rather than the GRS80 ellipsoid moves a point by at most a few km at
 * this extent, below the precision the coordinates are published at.
 * Returns km, y increasing southward to match the canvas. */
const R_EARTH = 6371.0088;  // km, mean radius
const LAEA_PHI0 = (52 * Math.PI) / 180;
const LAEA_LAM0 = (10 * Math.PI) / 180;

function project(lon, lat) {
  const phi = (lat * Math.PI) / 180;
  const dl = (lon * Math.PI) / 180 - LAEA_LAM0;
  const s0 = Math.sin(LAEA_PHI0), c0 = Math.cos(LAEA_PHI0);
  const s = Math.sin(phi), c = Math.cos(phi), cl = Math.cos(dl);
  const k = Math.sqrt(2 / (1 + s0 * s + c0 * c * cl));
  return [R_EARTH * k * c * Math.sin(dl), -R_EARTH * k * (c0 * s - s0 * c * cl)];
}

function buildPoints() {
  const sites = state.index.sites;
  const byKey = new Map();
  const points = [];
  state.sitePoint = new Int32Array(sites.length).fill(-1);
  sites.forEach((s, si) => {
    if (s.lat == null || s.lon == null) return;
    const key = `${s.lat},${s.lon}`;
    let p = byKey.get(key);
    if (p === undefined) {
      const [x, y] = project(s.lon, s.lat);
      p = points.length;
      points.push({ lat: s.lat, lon: s.lon, x, y, sites: [] });
      byKey.set(key, p);
    }
    points[p].sites.push(si);
    state.sitePoint[si] = p;
  });
  state.points = points;
}

let basemapRequested = false;

/* Fetched on first use of the map, so the timeline's first paint does not wait
 * on it.  If it fails the circles still draw - they carry the data; the
 * outlines are only orientation - and the failure is printed on the map. */
function loadBasemap() {
  if (basemapRequested) return;
  basemapRequested = true;
  fetch('data/basemap.json')
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((bm) => {
      const proj = (flat) => {
        const out = new Float64Array(flat.length);
        for (let k = 0; k < flat.length; k += 2) {
          const [x, y] = project(flat[k] / bm.scale, flat[k + 1] / bm.scale);
          out[k] = x;
          out[k + 1] = y;
        }
        return out;
      };
      state.basemap = {
        land: bm.land.map(proj),
        lakes: bm.lakes.map(proj),
        borders: bm.borders.map(proj),
        source: bm.source,
      };
      draw();
    })
    .catch((err) => {
      state.basemap = { error: String(err) };
      draw();
    });
}

const mapX = (x) => (x - state.mapView.cx) * state.mapView.scale + canvas.clientWidth / 2;
const mapY = (y) => (y - state.mapView.cy) * state.mapView.scale + canvas.clientHeight / 2;

function resetMapView() {
  const ps = state.drawOrder.length ? state.drawOrder : state.points.map((_, p) => p);
  const e = extent(ps);
  const mv = state.mapView;
  mv.scale = clamp(fitScale(ps), mapMinScale(), MAP_MAX_SCALE);
  mv.cx = (e.x0 + e.x1) / 2;
  mv.cy = (e.y0 + e.y1) / 2;
  mv.fitted = true;
  draw();
}

function tracePart(pts, closed) {
  ctx.moveTo(mapX(pts[0]), mapY(pts[1]));
  for (let k = 2; k < pts.length; k += 2) ctx.lineTo(mapX(pts[k]), mapY(pts[k + 1]));
  if (closed) ctx.closePath();
}

function drawMap() {
  loadBasemap();
  const W = canvas.clientWidth, H = canvas.clientHeight;
  const css = getComputedStyle(document.documentElement);
  const tok = (name) => css.getPropertyValue(name).trim();

  ctx.fillStyle = tok('--map-water');
  ctx.fillRect(0, 0, W, H);

  const bm = state.basemap;
  if (bm && !bm.error) {
    // Even-odd, so holes in the land layer are holes whatever their winding.
    ctx.beginPath();
    for (const ring of bm.land) tracePart(ring, true);
    ctx.fillStyle = tok('--map-land');
    ctx.fill('evenodd');
    ctx.beginPath();
    for (const ring of bm.lakes) tracePart(ring, true);
    ctx.fillStyle = tok('--map-water');
    ctx.fill('evenodd');
    ctx.beginPath();
    for (const line of bm.borders) tracePart(line, false);
    ctx.strokeStyle = tok('--map-border');
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }

  const G = state.index.groups.length;
  const colors = state.index.groups.map((_, g) => groupColor(g));
  const halo = tok('--surface-1');
  for (const p of state.drawOrder) {
    const pt = state.points[p];
    const n = state.pointTotals[p];
    const sx = mapX(pt.x), sy = mapY(pt.y);
    const rad = state.sizeK * Math.sqrt(n);
    if (sx + rad < 0 || sx - rad > W || sy + rad < 0 || sy - rad > H) continue;
    let a = -Math.PI / 2;  // wedges run clockwise from 12 o'clock, in legend order
    for (let g = 0; g < G; g++) {
      const c = state.pointCounts[p * G + g];
      if (!c) continue;
      ctx.beginPath();
      if (c === n) {
        ctx.arc(sx, sy, rad, 0, 2 * Math.PI);
      } else {
        const da = (2 * Math.PI * c) / n;
        ctx.moveTo(sx, sy);
        ctx.arc(sx, sy, rad, a, a + da);
        ctx.closePath();
        a += da;
      }
      ctx.fillStyle = colors[g];
      ctx.fill();
    }
    if (rad >= 2) {
      ctx.beginPath();
      ctx.arc(sx, sy, rad, 0, 2 * Math.PI);
      ctx.strokeStyle = halo;
      ctx.lineWidth = 0.75;
      ctx.stroke();
    }
  }

  const ring = (p, width) => {
    if (p < 0 || !state.pointTotals[p]) return;
    const pt = state.points[p];
    ctx.beginPath();
    ctx.arc(mapX(pt.x), mapY(pt.y), state.sizeK * Math.sqrt(state.pointTotals[p]) + 2, 0, 2 * Math.PI);
    ctx.strokeStyle = tok('--text-primary');
    ctx.lineWidth = width;
    ctx.stroke();
  };
  ring(state.mapHover, 1.5);
  ring(state.mapSelected, 2.5);

  drawSizeLegend(H, tok);
  drawMapNotes(W, H, tok, bm);
}

/* Reference circles share a bottom point so their areas compare directly. */
function drawSizeLegend(H, tok) {
  if (!state.drawOrder.length) return;
  const max = state.pointTotals[state.drawOrder[0]];
  const vals = [1000, 100, 10, 1].filter((v) => v <= max).slice(0, 3);
  const rMax = state.sizeK * Math.sqrt(vals[0]);
  const labelW = 44;
  const boxW = 2 * rMax + labelW + 24, boxH = 2 * rMax + 34;
  const x0 = 12, y0 = H - 12 - boxH;
  ctx.fillStyle = tok('--surface-1');
  ctx.globalAlpha = 0.85;
  ctx.fillRect(x0, y0, boxW, boxH);
  ctx.globalAlpha = 1;

  ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';
  ctx.fillStyle = tok('--text-secondary');
  ctx.fillText('logs', x0 + 8, y0 + 6);

  const cx = x0 + 8 + rMax, base = y0 + boxH - 8;
  ctx.textBaseline = 'middle';
  ctx.strokeStyle = tok('--text-secondary');
  ctx.lineWidth = 1;
  for (const v of vals) {
    const r = state.sizeK * Math.sqrt(v);
    ctx.beginPath();
    ctx.arc(cx, base - r, r, 0, 2 * Math.PI);
    ctx.stroke();
    const top = Math.round(base - 2 * r) + 0.5;
    ctx.beginPath();
    ctx.moveTo(cx, top);
    ctx.lineTo(cx + rMax + 6, top);
    ctx.stroke();
    ctx.fillText(v.toLocaleString(), cx + rMax + 9, top);
  }
}

function drawMapNotes(W, H, tok, bm) {
  const notes = [];
  if (state.unmapped.sites) {
    const { sites, logs } = state.unmapped;
    notes.push(
      `Not mapped: ${sites} collection${sites > 1 ? 's' : ''} ` +
      `(${logs.toLocaleString()} log${logs > 1 ? 's' : ''}) published without coordinates`
    );
  }
  if (bm && bm.error) notes.push(`Base map unavailable (${bm.error}); circles are unaffected`);
  else if (bm) notes.push(bm.source);
  ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'bottom';
  ctx.fillStyle = tok('--text-muted');
  notes.forEach((t, k) => ctx.fillText(t, W - 10, H - 8 - 15 * (notes.length - 1 - k)));
}

function mapHitTest(px, py) {
  // Reverse draw order: the smallest circles are drawn last, so on top.
  for (let k = state.drawOrder.length - 1; k >= 0; k--) {
    const p = state.drawOrder[k];
    const pt = state.points[p];
    const r = Math.max(MAP_MIN_HIT, state.sizeK * Math.sqrt(state.pointTotals[p]));
    const dx = px - mapX(pt.x), dy = py - mapY(pt.y);
    if (dx * dx + dy * dy <= r * r) return p;
  }
  return -1;
}

function mapMouseMove(e) {
  if (drag) {
    const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) drag.moved = true;
    state.mapView.cx = drag.cx - dx / state.mapView.scale;
    state.mapView.cy = drag.cy - dy / state.mapView.scale;
    draw();
    return;
  }
  const p = mapHitTest(e.offsetX, e.offsetY);
  if (p !== state.mapHover) {
    state.mapHover = p;
    draw();
    updateMapTooltip(p, e.offsetX, e.offsetY);
  } else if (p >= 0) {
    positionTooltip(e.offsetX, e.offsetY);
  }
}

function mapWheel(e) {
  const [px, py] = canvasXY(e);
  zoomMap(px, py, Math.pow(1.0015, -e.deltaY));
  draw();
}

function zoomMap(px, py, k) {
  const mv = state.mapView;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  // Keep the point under the cursor fixed while the scale changes.
  const x = (px - W / 2) / mv.scale + mv.cx;
  const y = (py - H / 2) / mv.scale + mv.cy;
  mv.scale = clamp(mv.scale * k, mapMinScale(), MAP_MAX_SCALE);
  mv.cx = x - (px - W / 2) / mv.scale;
  mv.cy = y - (py - H / 2) / mv.scale;
}

/* Collections at a point that have logs passing the taxon and era filters. */
function placeSites(p) {
  return state.points[p].sites.filter((si) => state.siteCounts[si] > 0);
}

function placeLabel(p) {
  // Named after its largest collection.  The location field is often only a
  // region ("Bavaria" for 42 buildings in Regensburg), and guessing a shared
  // place name from the site names was tried and produced "Valley, Cyprus".
  const sites = placeSites(p).sort((a, b) => state.siteCounts[b] - state.siteCounts[a]);
  const top = state.index.sites[sites[0]];
  const name = top.site || top.code;
  return sites.length === 1 ? name : `${name} + ${sites.length - 1} more`;
}

function placeTaxa(p) {
  const G = state.index.groups.length;
  const out = [];
  for (let g = 0; g < G; g++) {
    const c = state.pointCounts[p * G + g];
    if (c) out.push([g, c]);
  }
  return out.sort((a, b) => b[1] - a[1]);
}

function fmtCoord(pt) {
  return `${Math.abs(pt.lat)}° ${pt.lat >= 0 ? 'N' : 'S'}, ` +
    `${Math.abs(pt.lon)}° ${pt.lon >= 0 ? 'E' : 'W'}`;
}

function updateMapTooltip(p, px, py) {
  const tip = $('tooltip');
  if (p < 0) { tip.classList.remove('visible'); return; }
  const sites = placeSites(p);
  const locs = [...new Set(sites.map((si) => state.index.sites[si].location).filter(Boolean))];
  const n = state.pointTotals[p];
  const taxa = placeTaxa(p)
    .map(([g, c]) =>
      `<span class="swatch" style="display:inline-block;width:8px;height:8px;border-radius:2px;` +
      `background:var(--${state.index.groups[g]})"></span> ${esc(state.index.groups[g])} ${c.toLocaleString()}`)
    .join(' · ');
  tip.innerHTML =
    `<div class="tt-title">${esc(placeLabel(p))}</div>` +
    (locs.length ? `<div class="tt-row">${esc(locs.join(' · '))}</div>` : '') +
    `<div class="tt-years">${n.toLocaleString()} log${n > 1 ? 's' : ''}` +
    (sites.length > 1 ? ` in ${sites.length} collections` : '') + `</div>` +
    `<div class="tt-row">${taxa}</div>` +
    `<div class="tt-row">${fmtCoord(state.points[p])}</div>`;
  tip.classList.add('visible');
  positionTooltip(px, py);
}

/* Zoom used when jumping to one circle: 100 km per 100 px, enough to pull the
 * Alpine clusters apart.  Never zooms out. */
const MAP_FOCUS_SCALE = 1;

function showOnMap(i) {
  const si = state.buf[i * F + SITE];
  const p = state.sitePoint[si];
  if (p < 0) return;
  setDisplay('map');
  const mv = state.mapView, pt = state.points[p];
  mv.scale = clamp(Math.max(mv.scale, MAP_FOCUS_SCALE), mapMinScale(), MAP_MAX_SCALE);
  mv.cx = pt.x;
  mv.cy = pt.y;
  openPlace(p, si);
}

/* focusSite, if given, is the collection to mark in the list. */
function openPlace(p, focusSite = -1) {
  state.mapSelected = p;
  state.mapFocus = focusSite;
  const [lo, hi] = ERAS[state.era];
  const groups = state.index.groups;
  // Per collection: the taxon and year span of the logs the circle counts.
  const info = new Map();
  for (let i = 0; i < state.n; i++) {
    const b = i * F;
    const si = state.buf[b + SITE];
    if (state.sitePoint[si] !== p) continue;
    const g = state.buf[b + GROUP];
    if (!state.enabled.has(groups[g])) continue;
    const s = state.buf[b + START], e = state.buf[b + END];
    if (s > hi || e < lo) continue;
    let r = info.get(si);
    if (!r) info.set(si, (r = { n: 0, lo: s, hi: e, groups: new Set() }));
    r.n++;
    r.groups.add(g);
    if (s < r.lo) r.lo = s;
    if (e > r.hi) r.hi = e;
  }
  const sites = [...info.keys()].sort((a, b) => info.get(b).n - info.get(a).n);
  const total = state.pointTotals[p];
  const hidden = state.points[p].sites.length - sites.length;
  const pt = state.points[p];

  $('p-title').textContent = placeLabel(p);
  $('p-sub').textContent =
    `${fmtCoord(pt)} · ${total.toLocaleString()} log${total > 1 ? 's' : ''} in ` +
    `${sites.length} collection${sites.length > 1 ? 's' : ''}` +
    (hidden ? ` · ${hidden} more here with no logs matching the filters` : '');
  $('p-show').textContent =
    sites.length > 1 ? `Show these ${sites.length} collections on the timeline` : 'Show on the timeline';
  $('p-show').onclick = () => setPlace(new Set(sites), placeLabel(p));

  const rows = sites.map((si) => {
    const s = state.index.sites[si];
    const r = info.get(si);
    const taxa = [...r.groups]
      .map((g) => `<span class="swatch" style="background:var(--${groups[g]})"></span>`)
      .join('');
    return `<tr data-site="${si}"${si === focusSite ? ' class="current"' : ''}>` +
      `<td>${esc(s.site)}<div class="code">${esc(s.code)}</div></td>` +
      `<td>${taxa}${esc(s.common || s.latin || s.species)}</td>` +
      `<td class="num">${r.n.toLocaleString()}</td>` +
      `<td class="num">${fmtYear(r.lo)} –<br>${fmtYear(r.hi)}</td></tr>`;
  });
  $('p-table').innerHTML =
    '<thead><tr><th>Collection</th><th>Taxon</th><th class="num">Logs</th><th class="num">Years</th></tr></thead>' +
    `<tbody>${rows.join('')}</tbody>`;
  for (const tr of $('p-table').querySelectorAll('tbody tr')) {
    const si = Number(tr.dataset.site);
    tr.title = 'Show this collection on the timeline';
    tr.onclick = () => setPlace(new Set([si]), state.index.sites[si].site || state.index.sites[si].code);
  }
  if (state.display === 'map') $('place').classList.add('open');
  const cur = $('p-table').querySelector('tr.current');
  if (cur) cur.scrollIntoView({ block: 'nearest' });
  draw();
}

/* Filters changed under a place selection: recount its panel, or hide it
 * while the filters empty its circle - kept, like a hidden timeline
 * selection, so it comes back when the filter is undone. */
function refreshPlace() {
  const p = state.mapSelected;
  if (p < 0) return;
  if (state.pointTotals[p] > 0) {
    openPlace(p, state.mapFocus);
  } else {
    $('place').classList.remove('open');
    draw();
  }
}

function closePlace() {
  state.mapSelected = -1;
  $('place').classList.remove('open');
  draw();
}

/* Restrict the timeline to some collections and go there.  The chip in the
 * controls is the only way back, so it must always say what is applied. */
function setPlace(sites, label) {
  state.place = { sites, label };
  $('place-chip').textContent = `Place: ${label}`;
  $('place-chip').hidden = false;
  applyFilters();  // first, so a selection outside the place is hidden before it can reopen
  setDisplay('timeline');
  resetView();
}

function clearPlace() {
  state.place = null;
  $('place-chip').hidden = true;
  applyFilters();
  // The map never applied the place, so it has nothing to refit.
  if (state.display === 'map') draw(); else resetView();
}

const HELP = matchMedia('(pointer: coarse)').matches ? {
  timeline: 'Drag to pan · pinch to zoom · tap a log for details',
  map: 'Drag to pan · pinch to zoom · tap a circle for its collections',
} : {
  timeline: 'Drag to pan · wheel to zoom · shift+wheel rows only · alt+wheel time only',
  map: 'Drag to pan · wheel to zoom · circle area proportional to logs · click a circle for its collections',
};

// Narrow screens fold the two long footer lines away behind a toggle.
$('f-more').addEventListener('click', () => {
  const open = $('app').querySelector('footer').classList.toggle('expanded');
  $('f-more').textContent = open ? 'less' : 'more';
  $('f-more').setAttribute('aria-expanded', String(open));
  resize();
});

function syncDisplayControls() {
  const map = state.display === 'map';
  $('view-timeline').setAttribute('aria-pressed', String(!map));
  $('view-map').setAttribute('aria-pressed', String(map));
  $('ctl-mode').hidden = map;
  $('ctl-size').hidden = !map;
  $('f-help').textContent = HELP[state.display];
}

function setDisplay(d) {
  if (d === state.display) return;
  state.display = d;
  syncDisplayControls();
  state.hover = state.mapHover = -1;
  $('tooltip').classList.remove('visible');
  // Each view keeps its own selection across a switch; only its panel hides.
  $('detail').classList.toggle('open', d === 'timeline' && selectionShown());
  $('place').classList.toggle(
    'open', d === 'map' && state.mapSelected >= 0 && state.pointTotals[state.mapSelected] > 0
  );
  try {
    history.replaceState(null, '', d === 'map' ? '#map' : location.pathname + location.search);
  } catch (err) { /* file:// and sandboxed frames refuse; the hash is a convenience */ }
  if (d === 'map' && !state.mapView.fitted) resetMapView();
  else draw();
}

/* --------------------------------------------------------------- legend */

function buildLegend() {
  const counts = new Array(state.index.groups.length).fill(0);
  for (let i = 0; i < state.n; i++) counts[state.buf[i * F + GROUP]]++;
  const el = $('legend');
  el.innerHTML = '';
  state.index.groups.forEach((g, gi) => {
    if (!counts[gi]) return;
    const b = document.createElement('button');
    b.setAttribute('aria-pressed', 'true');
    b.innerHTML =
      `<span class="swatch" style="background:var(--${g})"></span>` +
      `<span>${g}</span><span class="count">${counts[gi].toLocaleString()}</span>`;
    b.onclick = () => {
      if (state.enabled.has(g)) state.enabled.delete(g); else state.enabled.add(g);
      if (!state.enabled.size) state.enabled.add(g);
      b.setAttribute('aria-pressed', String(state.enabled.has(g)));
      applyFilters();
      refreshPlace();
      draw();
    };
    el.appendChild(b);
  });
}

/* --------------------------------------------------------------- wiring */

$('mode').onchange = (e) => {
  state.mode = e.target.value;
  applyFilters();
  resetView();
};
$('era').onchange = (e) => {
  state.era = e.target.value;
  applyFilters();
  refreshPlace();
  // The map keeps its frame across eras, so the same places can be compared;
  // the timeline refits because its extent is the era.
  if (state.display === 'map') draw(); else resetView();
};
$('view-timeline').onclick = () => setDisplay('timeline');
$('view-map').onclick = () => setDisplay('map');
$('size').oninput = (e) => {
  state.sizeK = Number(e.target.value);
  draw();
};
$('place-chip').onclick = clearPlace;
$('place-close').onclick = closePlace;
$('reset').onclick = resetView;
$('detail-close').onclick = closeDetail;
/* Every click flips the theme on screen.  It used to cycle auto -> dark ->
 * light, and under a dark system theme auto -> dark changed nothing, so
 * leaving dark took two clicks.  Choosing what the system already shows drops
 * the override, so the page goes back to following the system. */
$('theme').onclick = () => {
  const root = document.documentElement;
  const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const shown = root.getAttribute('data-theme') || (sysDark ? 'dark' : 'light');
  const next = shown === 'dark' ? 'light' : 'dark';
  if ((next === 'dark') === sysDark) root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', next);
  draw();
};

window.addEventListener('resize', resize);
new ResizeObserver(resize).observe($('stage'));

load().then(() => { resize(); resetView(); }).catch((err) => {
  $('loading').textContent = 'failed to load: ' + err;
});
