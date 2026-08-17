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
};

const F = 6;  // fields per log
const START = 0, END = 1, ROW_U = 2, ROW_B = 3, GROUP = 4, SITE = 5;

const $ = (id) => document.getElementById(id);
const canvas = $('canvas');
const ctx = canvas.getContext('2d', { alpha: false });

/* ------------------------------------------------------------------ load */

async function load() {
  const [index, binBuf] = await Promise.all([
    fetch('data/index.json').then((r) => r.json()),
    fetch('data/logs.bin').then((r) => r.arrayBuffer()),
  ]);
  state.index = index;
  state.buf = new Int32Array(binBuf);
  state.n = index.n_logs;
  index.groups.forEach((g) => state.enabled.add(g));

  buildLegend();
  applyFilters();
  resetView();
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
    `${s.logs_floating.toLocaleString()} floating logs withheld — they carry no calendar date`;
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
  ancient: [-Infinity, 0],
};

function applyFilters() {
  const [lo, hi] = ERAS[state.era];
  const groups = state.index.groups;
  const keep = [];
  for (let i = 0; i < state.n; i++) {
    const b = i * F;
    if (!state.enabled.has(groups[state.buf[b + GROUP]])) continue;
    if (state.buf[b + START] > hi || state.buf[b + END] < lo) continue;
    keep.push(i);
  }
  state.visible = Int32Array.from(keep);

  const filtered =
    state.era !== 'all' || state.enabled.size !== state.index.groups.length;

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

function resetView() {
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
  state.view.xYear = lo - pad;
  state.view.pxPerYear = r.width / (hi - lo + pad * 2);
  state.view.yRow = 0;
  state.view.pxPerRow = clamp(
    (r.height - 34) / Math.max(state.rowCount, 1),
    MIN_PX_PER_ROW,
    MAX_PX_PER_ROW
  );
  draw();
}

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const xOf = (year) => (year - state.view.xYear) * state.view.pxPerYear;
const yOf = (row) => (row - state.view.yRow) * state.view.pxPerRow + 26;
const yearAt = (px) => px / state.view.pxPerYear + state.view.xYear;

function fmtYear(y) {
  return y < 0 ? `${-y} BC` : `${y} CE`;
}

function draw() {
  if (!state.index) return;
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
  if (state.selected >= 0) outline(state.selected, css, 2.5);
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
  for (let y = start; y <= right; y += step) {
    const x = Math.round(xOf(y)) + 0.5;
    ctx.moveTo(x, 22);
    ctx.lineTo(x, H);
  }
  ctx.stroke();

  ctx.fillStyle = css.getPropertyValue('--text-secondary').trim();
  ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  for (let y = start; y <= right; y += step) {
    ctx.textAlign = 'center';
    ctx.fillText(fmtYear(Math.round(y)), xOf(y), 11);
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
  drag = { x: e.offsetX, y: e.offsetY, xYear: state.view.xYear, yRow: state.view.yRow, moved: false };
  canvas.classList.add('panning');
});

window.addEventListener('mouseup', (e) => {
  if (drag && !drag.moved) {
    const i = hitTest(e.offsetX, e.offsetY);
    if (i >= 0) showDetail(i); else closeDetail();
  }
  drag = null;
  canvas.classList.remove('panning');
});

canvas.addEventListener('mousemove', (e) => {
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
  $('tooltip').classList.remove('visible');
  draw();
});

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  if (e.shiftKey) {
    const before = (e.offsetY - 26) / state.view.pxPerRow + state.view.yRow;
    state.view.pxPerRow = clamp(
      state.view.pxPerRow * Math.pow(1.0015, -e.deltaY),
      MIN_PX_PER_ROW, MAX_PX_PER_ROW
    );
    state.view.yRow = before - (e.offsetY - 26) / state.view.pxPerRow;
  } else {
    const before = yearAt(e.offsetX);
    state.view.pxPerYear = clamp(
      state.view.pxPerYear * Math.pow(1.0015, -e.deltaY), 1e-4, 40
    );
    state.view.xYear = before - e.offsetX / state.view.pxPerYear;
  }
  draw();
}, { passive: false });

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
    `<div class="tt-title">${esc(site.common || site.species || 'unknown')}</div>` +
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
  draw();
  const b = i * F;
  const site = siteOf(i);
  const seriesId = state.index.series_ids[i];
  const s = state.buf[b + START], e = state.buf[b + END];

  $('d-title').textContent = seriesId;
  $('d-sub').innerHTML =
    `${esc(site.common || site.species)} · ${fmtYear(s)} – ${fmtYear(e)} ` +
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
    ['Dating', datingBadge(site.dating)],
    ['Study', site.url ? `<a href="${esc(site.url)}" target="_blank" rel="noopener">${esc(site.study || site.code)}</a>` : esc(site.study)],
    ['DOI', site.doi ? `<a href="https://doi.org/${esc(site.doi)}" target="_blank" rel="noopener">${esc(site.doi)}</a>` : ''],
  ];
  $('d-fields').innerHTML = rows
    .filter(([, v]) => v)
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${k === 'Dating' || k === 'Study' || k === 'DOI' ? v : esc(v)}</dd>`)
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

function datingBadge(d) {
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
    `peak ${(max / 100).toFixed(2)} mm` +
    (missing ? ` · ${missing} year${missing > 1 ? 's' : ''} unmeasured` : '');
}

function closeDetail() {
  state.selected = -1;
  $('detail').classList.remove('open');
  draw();
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
  resetView();
};
$('reset').onclick = resetView;
$('detail-close').onclick = closeDetail;
$('theme').onclick = () => {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : cur === 'light' ? '' : 'dark';
  if (next) document.documentElement.setAttribute('data-theme', next);
  else document.documentElement.removeAttribute('data-theme');
  draw();
};

window.addEventListener('resize', resize);
new ResizeObserver(resize).observe($('stage'));

load().then(resize).catch((err) => {
  $('loading').textContent = 'failed to load: ' + err;
});
