// Faithful, editable view of any workbook sheet: styles, merges, formulas, validation lists.
import { api, act, h, clear, state, toast, fmtValue, esc, linkify, debounce } from './ui.js';
import { invalidate } from './table.js';

const px = (w) => Math.round((w || 8.43) * 7 + 5);
const REF = /(?:'([^']+)'|([A-Za-z0-9_]+))!\$?([A-Z]{1,3})\$?(\d+)(?::\$?[A-Z]{1,3}\$?\d+)?/g;
const colName = (n) => { let s = ''; n += 1; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = ((n - 1) / 26) | 0; } return s; };
const colNum = (s) => s.split('').reduce((n, c) => n * 26 + c.charCodeAt(0) - 64, 0) - 1;
const parse = (a) => { const m = /^([A-Z]+)(\d+)$/.exec(a); return { c: colNum(m[1]), r: +m[2] - 1 }; };

function styleCss(st) {
  if (!st) return '';
  let s = '';
  if (st.bg) s += `background:${st.bg};`; if (st.fg) s += `color:${st.fg};`; if (st.b) s += 'font-weight:700;'; if (st.i) s += 'font-style:italic;';
  if (st.sz) s += `font-size:${Math.round(st.sz * 1.28)}px;`;
  if (st.ha) s += `text-align:${st.ha === 'centerContinuous' ? 'center' : st.ha};`; if (st.va) s += `vertical-align:${st.va === 'center' ? 'middle' : st.va};`;
  if (st.bd) { const [t, r, b, l] = st.bd; if (t) s += `border-top:1px solid ${t};`; if (r) s += `border-right:1px solid ${r};`; if (b) s += `border-bottom:1px solid ${b};`; if (l) s += `border-left:1px solid ${l};`; }
  return s;
}

export async function renderGrid(root, name, params = {}) {
  const P = await api('/api/sheet/' + encodeURIComponent(name));
  const cellData = new Map(); for (const [r, c, v, s, f] of P.cells) cellData.set(colName(c) + (r + 1), { v, s, f, r, c });
  const dvs = P.dv.map((d) => ({ list: d.list, rects: d.sqref.split(' ').map((p) => { const [a, b] = p.split(':'); const A = parse(a), B = parse(b || a); return { r1: A.r, r2: B.r, c1: A.c, c2: B.c }; }) }));
  const dvFor = (r, c) => { for (const d of dvs) for (const q of d.rects) if (r >= q.r1 && r <= q.r2 && c >= q.c1 && c <= q.c2) return d.list; return null; };

  let showF = false, sel = null; const els = new Map();
  const info = h('span', { class: 'muted' }, `${P.rows} rows × ${P.cols} columns · ${[...cellData.values()].filter((x) => x.f).length} formulas`);
  const addrBox = h('span', { class: 'fb-addr' }, '—'); const fbody = h('div', { class: 'fb-body' }, h('span', { class: 'muted' }, 'Select a cell'));
  const fToggle = h('label', { class: 'switch' }, h('input', { type: 'checkbox', onchange: (e) => { showF = e.target.checked; paintAll(); } }), ' Show formulas');
  const find = h('input', { type: 'search', placeholder: 'Find in sheet…', 'aria-label': 'Find in sheet', oninput: debounce((e) => findText(e.target.value), 200) });
  const wrapEl = h('div', { class: 'xl-wrap' });
  const page = h('div', { class: 'page grid-page' },
    h('div', { class: 'page-h' }, h('div', null, h('h1', null, name), h('p', { class: 'sub' }, info)), h('div', { class: 'row gap' }, find, fToggle)),
    h('div', { class: 'fbar' }, addrBox, h('span', { class: 'fx-lbl' }, 'fx'), fbody), wrapEl);
  clear(root).append(page);

  // merges
  const mergeTL = new Map(), covered = new Set();
  for (const m of P.merges) { const [a, b] = m.split(':'); const A = parse(a), B = parse(b); mergeTL.set(a, { rs: B.r - A.r + 1, cs: B.c - A.c + 1 }); for (let r = A.r; r <= B.r; r++) for (let c = A.c; c <= B.c; c++) if (r !== A.r || c !== A.c) covered.add(colName(c) + (r + 1)); }
  const hiddenCols = new Set(); const widths = {};
  for (const c of P.colWidths) for (let i = c.min; i <= Math.min(c.max, P.cols); i++) { widths[i] = c.w; if (c.hidden) hiddenCols.add(i); }
  const table = h('table', { class: 'xl' }, h('colgroup', null, Array.from({ length: P.cols }, (_, i) => h('col', { style: { width: px(widths[i + 1]) + 'px', display: hiddenCols.has(i + 1) ? 'none' : '' } }))));
  const tb = h('tbody'); table.append(tb);
  table.style.width = 34 + Array.from({ length: P.cols }, (_, i) => (hiddenCols.has(i + 1) ? 0 : px(widths[i + 1]))).reduce((a, b) => a + b, 0) + 'px';
  // frozen offsets
  const fz = P.freeze || { x: 0, y: 0 }; const rowPx = (r) => { const hh = P.rowHeights[r + 1]; return hh && hh.h ? Math.round(hh.h * 1.333) : 20; };
  const topOff = []; let acc = 0; for (let r = 0; r < fz.y; r++) { topOff[r] = acc; acc += rowPx(r); }
  const leftOff = []; acc = 0; for (let c = 0; c < fz.x; c++) { leftOff[c] = acc; acc += px(widths[c + 1]); }

  for (let r = 0; r < P.rows; r++) {
    const rh = P.rowHeights[r + 1]; if (rh && rh.hidden) continue;
    const tr = h('tr', { style: rh && rh.h ? { height: Math.round(rh.h * 1.333) + 'px' } : {} });
    tr.append(h('th', { class: 'rn' }, r + 1));
    for (let c = 0; c < P.cols; c++) {
      const a = colName(c) + (r + 1); if (covered.has(a) || hiddenCols.has(c + 1)) continue;
      const d = cellData.get(a); const st = d && P.styles[d.s];
      const td = h('td', { 'data-a': a, class: (d && d.f ? 'f ' : '') + (st && st.wrap ? 'wrap' : ''), style: styleCss(st) });
      const mg = mergeTL.get(a); if (mg) { if (mg.rs > 1) td.rowSpan = mg.rs; if (mg.cs > 1) td.colSpan = mg.cs; }
      if (r < fz.y) { td.classList.add('stk'); td.style.top = topOff[r] + 'px'; } if (c < fz.x) { td.classList.add('stkx'); td.style.left = leftOff[c] + 'px'; }
      els.set(a, td); paint(a);
      tr.append(td);
    }
    tb.append(tr);
  }
  wrapEl.append(table);
  // column header letters
  const thead = h('thead', null, h('tr', null, h('th', { class: 'corner' }), Array.from({ length: P.cols }, (_, i) => hiddenCols.has(i + 1) ? null : h('th', { class: 'cn' }, colName(i)))));
  table.insertBefore(thead, tb);

  function paint(a) {
    const td = els.get(a); if (!td) return; const d = cellData.get(a); const st = d && P.styles[d.s];
    clear(td);
    if (!d) return;
    if (showF && d.f) { td.append(h('span', { class: 'ftxt' }, '=' + d.f)); return; }
    const txt = fmtValue(d.v, st && st.fmt, null);
    const rh = P.rowHeights[d.r + 1]; const host = st && st.wrap && rh && rh.h ? td.appendChild(h('div', { class: 'clip', style: { maxHeight: Math.round(rh.h * 1.333) - 4 + 'px' } })) : td;
    if (typeof txt === 'string' && /https?:\/\//.test(txt)) host.append(linkify(txt)); else host.append(txt);
    if (d.v && d.v.err) td.classList.add('err'); else td.classList.remove('err');
  }
  function paintAll() { for (const a of els.keys()) paint(a); }

  // selection & editing
  wrapEl.addEventListener('click', (e) => { const td = e.target.closest('td[data-a]'); if (td && !e.target.closest('a')) select(td.dataset.a); });
  wrapEl.addEventListener('dblclick', (e) => { const td = e.target.closest('td[data-a]'); if (td) edit(td.dataset.a); });
  function select(a, scroll) {
    if (sel) els.get(sel)?.classList.remove('sel'); sel = a; const td = els.get(a); if (!td) return; td.classList.add('sel'); if (scroll) td.scrollIntoView({ block: 'center', inline: 'center' });
    const d = cellData.get(a); addrBox.textContent = a; clear(fbody);
    if (d && d.f) { fbody.append(h('code', null, refLinks('=' + d.f)), h('div', { class: 'muted small' }, 'Calculated by the workbook — edit its inputs, not the formula. Value: ', h('b', null, fmtValue(d.v, P.styles[d.s] && P.styles[d.s].fmt) || '(blank)'))); return; }
    const { r, c } = parse(a); const list = dvFor(r, c);
    const ctl = list ? h('select', { onchange: (e) => commit(a, e.target.value === '' ? '' : (list.find((o) => String(o) === e.target.value) ?? e.target.value)) }, h('option', { value: '' }, '(blank)'), list.map((o) => h('option', { value: o, selected: String(o) === String(d && d.v) }, o))) : h('input', { type: 'text', value: d && d.v != null ? (typeof d.v === 'number' ? d.v : d.v) : '', placeholder: 'Type a value and press Enter', onkeydown: (e) => { if (e.key === 'Enter') commit(a, e.target.value); } });
    fbody.append(ctl, h('span', { class: 'muted small' }, list ? ' Allowed values from the workbook’s validation list' : ' Input cell — Enter to save'));
  }
  function edit(a) {
    const d = cellData.get(a); if (d && d.f) return select(a);
    select(a); fbody.querySelector('input,select')?.focus();
  }
  async function commit(a, raw) {
    const d = cellData.get(a); let v = raw;
    if (typeof raw === 'string' && raw !== '' && raw.trim() !== '' && !isNaN(+raw)) v = +raw;
    if (typeof d?.v === 'number' && raw !== '' && isNaN(+raw)) { /* keep text */ }
    try {
      const res = await act('cells.save', { changes: [{ sheet: name, addr: a, value: v }], label: 'Edit cell', record: name + '!' + a });
      state.version++; invalidate(); applyDiff(res.diff, a, v);
      toast(`${a} saved · ${res.diff.length} dependent cell${res.diff.length === 1 ? '' : 's'} recalculated`, 'ok');
      window.dispatchEvent(new Event('mw:refresh:soft'));
    } catch (e) { toast(e.message, 'err'); select(a); }
  }
  function applyDiff(diff, a, v) {
    const d0 = cellData.get(a) || { r: parse(a).r, c: parse(a).c, s: 0 }; d0.v = v === '' ? null : v; cellData.set(a, d0); paint(a); els.get(a)?.classList.add('flash');
    for (const x of diff) if (x.sheet === name) { const d = cellData.get(x.addr) || { ...parse(x.addr), s: 0 }; d.v = x.value; cellData.set(x.addr, d); paint(x.addr); els.get(x.addr)?.classList.add('flash'); }
    setTimeout(() => wrapEl.querySelectorAll('.flash').forEach((e) => e.classList.remove('flash')), 1400);
    select(a);
  }
  function refLinks(f) {
    const frag = document.createDocumentFragment(); let last = 0;
    for (const m of f.matchAll(REF)) { frag.append(f.slice(last, m.index)); const sh = m[1] || m[2]; frag.append(h('a', { href: `#/sheet/${encodeURIComponent(sh)}?cell=${m[3]}${m[4]}` }, m[0])); last = m.index + m[0].length; }
    frag.append(f.slice(last)); return frag;
  }
  function findText(q) {
    wrapEl.querySelectorAll('.hit').forEach((e) => e.classList.remove('hit')); if (!q) return; q = q.toLowerCase(); let first = null;
    for (const [a, td] of els) if (td.textContent.toLowerCase().includes(q)) { td.classList.add('hit'); first = first || td; }
    first ? first.scrollIntoView({ block: 'center', inline: 'center' }) : toast('No match', 'info', 1500);
  }
  if (params.cell) select(params.cell, true);
  return { refresh: () => renderGrid(root, name, params) };
}
