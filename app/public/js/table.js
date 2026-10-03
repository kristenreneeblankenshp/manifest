// Record tables (pipeline, registry, evidence, ...) with filters, board, record drawer and workflow actions.
import { api, act, h, clear, state, toast, modal, fmtValue, pill, fieldInput, linkify, debounce, csvEscape, download, serialToISO, isoToSerial, todaySerial } from './ui.js';

const CLOSED = ['Rejected', 'Closed', 'Removed'];
const REQUIRED = {
  evidence: ['B', 'C', 'D', 'E', 'H', 'I', 'J', 'M', 'N', 'P', 'R', 'S', 'T'],
  reviews: ['B', 'C', 'E', 'F', 'P'],
  actions: ['B', 'C', 'D', 'E', 'F', 'G'],
  watch: ['A', 'B', 'C', 'E', 'F', 'G'],
  compare: ['B', 'C', 'D', 'E', 'F', 'G'],
};
const cache = {};
export async function loadTable(key, force) {
  if (!force && cache[key] && cache[key].version === state.version) return cache[key];
  const t = await api('/api/table/' + key); cache[key] = t; return t;
}
export const invalidate = () => { for (const k in cache) delete cache[k]; };
export async function tickers() {
  const t = await loadTable('registry'); return t.rows.map((r) => ({ t: r.v.B, n: r.v.C, cls: r.v.D })).filter((x) => x.t);
}
const col = (meta, l) => meta.cols.find((c) => c.letter === l);
export const cellText = (meta, r, l) => { const c = col(meta, l); return fmtValue(r.v[l], c && c.fmt, c && c.type); };
const hashRow = (key, id) => `#/${key}/${encodeURIComponent(id)}`;

// ---------------------------------------------------------------- list view
export async function renderTable(root, key, params = {}) {
  const { meta, rows } = await loadTable(key, true);
  const S = { q: params.q || '', status: params.status || '', stage: params.stage || '', cls: params.cls || '', mode: params.mode || (key === 'pipeline' ? 'board' : 'list'), sort: null, dir: 1 };
  const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  const statusCol = meta.statusCol, stageCol = meta.stageCol;
  const isDone = (r) => stageCol && CLOSED.includes(r.v[stageCol]);

  const head = h('div', { class: 'page-h' },
    h('div', null, h('h1', null, meta.title), h('p', { class: 'sub' }, `${rows.length} record${rows.length === 1 ? '' : 's'} · live from “${meta.sheet}”`)),
    h('div', { class: 'row gap' },
      key === 'pipeline' ? h('div', { class: 'seg', role: 'tablist' }, ['board', 'list'].map((m) => h('button', { class: S.mode === m ? 'on' : '', role: 'tab', 'aria-selected': S.mode === m, onclick: () => { S.mode = m; draw(); head.querySelectorAll('.seg button').forEach((b) => b.classList.toggle('on', b.textContent.toLowerCase() === m)); } }, m[0].toUpperCase() + m.slice(1)))) : null,
      h('button', { class: 'btn ghost', onclick: () => exportCsv(meta, filtered()) }, 'Export CSV'),
      h('a', { class: 'btn ghost', href: `#/sheet/${encodeURIComponent(meta.sheet)}` }, 'Open sheet grid'),
      newButton(key, meta)));
  const search = h('input', { type: 'search', placeholder: `Search ${meta.title.toLowerCase()}…`, value: S.q, 'aria-label': 'Search', oninput: debounce((e) => { S.q = e.target.value; draw(); }, 120) });
  const chips = h('div', { class: 'chips' });
  const body = h('div', { class: 'tbl-wrap' });
  wrap.append(head, h('div', { class: 'toolbar' }, search, chips), body);

  const filtered = () => {
    const q = S.q.trim().toLowerCase();
    return rows.filter((r) => (!S.status || r.v[statusCol] === S.status) && (!S.stage || r.v[stageCol] === S.stage) && (!S.cls || r.v[meta.classCol] === S.cls) &&
      (!q || Object.values(r.v).some((x) => String(x).toLowerCase().includes(q))));
  };
  function drawChips() {
    clear(chips);
    if (!statusCol) return;
    const counts = {}; rows.forEach((r) => { const s = r.v[statusCol] || '—'; counts[s] = (counts[s] || 0) + 1; });
    chips.append(h('button', { class: 'chip' + (!S.status ? ' on' : ''), onclick: () => { S.status = ''; draw(); } }, `All ${rows.length}`));
    for (const [s, n] of Object.entries(counts).sort((a, b) => b[1] - a[1])) chips.append(h('button', { class: 'chip ' + (S.status === s ? 'on' : ''), onclick: () => { S.status = S.status === s ? '' : s; draw(); } }, h('span', { class: 'dot pill-dot ' + pillCls(s) }), `${s} `, h('b', null, n)));
    if (S.stage || S.cls) chips.append(h('button', { class: 'chip on', onclick: () => { S.stage = ''; S.cls = ''; draw(); } }, `Filter: ${S.stage || S.cls} ✕`));
  }
  const pillCls = (s) => pill(s).className.replace('pill ', '');

  function draw() {
    drawChips(); clear(body);
    const list = filtered();
    if (!list.length) { body.append(h('div', { class: 'empty' }, h('b', null, 'No records match.'), h('p', null, rows.length ? 'Clear a filter or search term.' : 'No records yet — use the New button to add the first one.'))); return; }
    if (S.mode === 'board' && stageCol) return drawBoard(list);
    drawList(list);
  }

  function drawList(list) {
    const cols = meta.listCols.map((l) => col(meta, l));
    if (S.sort) list = [...list].sort((a, b) => { const x = a.v[S.sort], y = b.v[S.sort]; return (x > y ? 1 : x < y ? -1 : 0) * S.dir; });
    const table = h('table', { class: 'tbl' },
      h('thead', null, h('tr', null, cols.map((c) => h('th', { scope: 'col', class: c.auto ? 'auto' : '', 'aria-sort': S.sort === c.letter ? (S.dir > 0 ? 'ascending' : 'descending') : 'none' }, h('button', { class: 'th-btn', onclick: () => { S.dir = S.sort === c.letter ? -S.dir : 1; S.sort = c.letter; draw(); } }, c.label, S.sort === c.letter ? (S.dir > 0 ? ' ▲' : ' ▼') : ''))), h('th', null))),
      h('tbody', null, list.map((r) => h('tr', { tabindex: 0, class: isDone(r) ? 'done' : '', onclick: () => openRecord(key, r.row), onkeydown: (e) => e.key === 'Enter' && openRecord(key, r.row) },
        cols.map((c) => h('td', { class: c.type === 'number' || c.type === 'pct' ? 'num' : '' }, cellNode(meta, r, c))),
        h('td', { class: 'go' }, '›')))));
    body.append(table);
  }

  function drawBoard(list) {
    const stages = col(meta, stageCol).options;
    const board = h('div', { class: 'board' });
    for (const st of stages) {
      const items = list.filter((r) => r.v[stageCol] === st);
      const c = h('div', { class: 'lane' + (CLOSED.includes(st) ? ' closed' : ''), 'data-stage': st },
        h('div', { class: 'lane-h' }, h('span', null, st), h('b', null, items.length)),
        h('div', { class: 'lane-b' }, items.map((r) => card(r))));
      c.addEventListener('dragover', (e) => { e.preventDefault(); c.classList.add('over'); });
      c.addEventListener('dragleave', () => c.classList.remove('over'));
      c.addEventListener('drop', (e) => { e.preventDefault(); c.classList.remove('over'); const id = e.dataTransfer.getData('text/plain'); if (id) advanceFlow(id, st); });
      board.append(c);
    }
    body.append(board, h('p', { class: 'hint' }, 'Drag a card to another stage to advance it — the workbook’s stage-gate formulas are checked first and any blocker is shown before anything is written.'));
  }
  function card(r) {
    const c = h('div', { class: 'card', draggable: 'true', tabindex: 0, role: 'button', onclick: () => openRecord(key, r.row), onkeydown: (e) => e.key === 'Enter' && openRecord(key, r.row) },
      h('div', { class: 'card-t' }, h('b', null, r.v.C || '—'), h('span', { class: 'muted' }, r.v.A)),
      h('div', { class: 'card-n' }, r.v.D || ''),
      h('div', { class: 'card-m' }, r.v.E || ''),
      h('div', { class: 'card-f' }, pill(r.v[statusCol]), r.v.AB ? h('span', { class: 'muted' }, 'due ' + fmtValue(r.v.AB, 'mmm d')) : null));
    c.addEventListener('dragstart', (e) => e.dataTransfer.setData('text/plain', r.v.A));
    return c;
  }

  draw();
  if (params.open) openRecord(key, params.open);
}

function cellNode(meta, r, c) {
  const v = r.v[c.letter];
  if (meta.statusCol === c.letter || /status|gate|state|eligibility|freshness|result/i.test(c.label) && typeof v === 'string' && /^[A-Z0-9 —\-\/&.]+$/.test(v)) return pill(v);
  if (c.letter === meta.tickerCol && v) return h('a', { class: 'tick', href: '#/security/' + encodeURIComponent(v), onclick: (e) => e.stopPropagation() }, v);
  if (c.letter === meta.idCol && v) return h('span', { class: 'idc' }, v);
  return fmtValue(v, c.fmt, c.type);
}

function newButton(key, meta) {
  if (key === 'miar') return null;
  const label = { pipeline: 'New candidate', registry: 'Add security', evidence: 'Log evidence', reviews: 'Log review', compare: 'Add comparison', actions: 'New action', watch: 'Add company' }[key];
  return h('button', { class: 'btn primary', onclick: () => openNew(key) }, '＋ ' + label);
}

function exportCsv(meta, rows) {
  const lines = [meta.cols.map((c) => csvEscape(c.label)).join(',')];
  for (const r of rows) lines.push(meta.cols.map((c) => csvEscape(fmtValue(r.v[c.letter], c.fmt, c.type))).join(','));
  download(meta.title.replace(/\W+/g, '_') + '.csv', lines.join('\n'));
}

// ---------------------------------------------------------------- record drawer
let drawerEl = null;
export function closeDrawer() { if (drawerEl) { drawerEl.remove(); drawerEl = null; document.removeEventListener('keydown', escDrawer); } }
const escDrawer = (e) => { if (e.key === 'Escape' && !document.querySelector('.modal-back')) closeDrawer(); };

export async function openRecord(key, rowOrId) {
  const { meta, rows } = await loadTable(key, true);
  const r = rows.find((x) => x.row === rowOrId || x.v[meta.idCol] === rowOrId || x.v[meta.tickerCol] === rowOrId);
  if (!r) return toast('Record not found', 'err');
  closeDrawer();
  const dirty = new Map(); const inputs = new Map();
  const title = r.v[meta.titleCol] || r.v[meta.idCol] || '';
  const saveBtn = h('button', { class: 'btn primary', disabled: true, onclick: save }, 'Save changes');
  const dirtyNote = h('span', { class: 'muted' }, '');
  const status = meta.statusCol ? r.v[meta.statusCol] : null;

  const actionBar = h('div', { class: 'row gap wrap' }, ...recordActions(key, meta, r, () => openRecord(key, r.row)));
  const secs = meta.groups.map(([name, from, to]) => {
    const fi = meta.cols.findIndex((c) => c.letter === from), ti = meta.cols.findIndex((c) => c.letter === to);
    const fields = meta.cols.slice(fi, ti + 1).map((c) => fieldRow(meta, r, c, dirty, inputs, () => { saveBtn.disabled = dirty.size === 0; dirtyNote.textContent = dirty.size ? `${dirty.size} unsaved change${dirty.size > 1 ? 's' : ''}` : ''; }));
    return h('section', { class: 'fs' }, h('h4', null, name), h('div', { class: 'fgrid' }, fields));
  });
  const panel = h('aside', { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': meta.title + ' record' },
    h('div', { class: 'drawer-h' },
      h('div', null, h('div', { class: 'eyebrow' }, meta.title, ' · row ', r.row), h('h2', null, r.v[meta.idCol] && r.v[meta.idCol] !== title ? `${r.v[meta.idCol]} — ${title}` : title || '(untitled)'), h('div', { class: 'row gap' }, status ? pill(status) : null, meta.stageCol ? pill(r.v[meta.stageCol]) : null)),
      h('button', { class: 'icon-btn', 'aria-label': 'Close record', onclick: closeDrawer }, '✕')),
    meta.actionCol && r.v[meta.actionCol] ? h('div', { class: 'callout' }, h('b', null, 'Next required action · '), r.v[meta.actionCol]) : null,
    r.v[meta.tickerCol] ? h('div', { class: 'row gap wrap links' }, h('a', { class: 'lnk', href: '#/security/' + encodeURIComponent(r.v[meta.tickerCol]) }, `Security 360 · ${r.v[meta.tickerCol]}`), h('a', { class: 'lnk', href: `#/sheet/${encodeURIComponent(meta.sheet)}?cell=${meta.idCol}${r.row}` }, 'Show in workbook grid')) : h('div', { class: 'row gap links' }, h('a', { class: 'lnk', href: `#/sheet/${encodeURIComponent(meta.sheet)}?cell=${meta.idCol}${r.row}` }, 'Show in workbook grid')),
    actionBar.children.length ? h('div', { class: 'act-bar' }, h('h4', null, 'Actions'), actionBar) : null,
    h('div', { class: 'drawer-b' }, secs),
    h('div', { class: 'drawer-f' }, dirtyNote, h('div', { class: 'grow' }), h('button', { class: 'btn ghost', onclick: closeDrawer }, 'Close'), saveBtn));
  drawerEl = h('div', { class: 'drawer-back', onclick: (e) => e.target === drawerEl && closeDrawer() }, panel);
  document.getElementById('drawer-root').append(drawerEl); document.addEventListener('keydown', escDrawer);
  history.replaceState(null, '', hashRow(key, r.v[meta.idCol] ?? r.row).replace(/^#/, '#'));

  async function save() {
    const changes = [...dirty.entries()].map(([l, v]) => ({ sheet: meta.sheet, addr: l + r.row, value: v }));
    try {
      saveBtn.disabled = true;
      const res = await act('cells.save', { changes, label: `Edit ${meta.title}`, record: r.v[meta.idCol] || '' });
      state.version++; invalidate();
      toast(`Saved ${changes.length} field${changes.length > 1 ? 's' : ''} · ${res.diff.length} cells recalculated by the workbook`, 'ok');
      window.dispatchEvent(new Event('mw:refresh'));
      openRecord(key, r.row);
    } catch (e) { toast(e.message, 'err'); saveBtn.disabled = false; }
  }
}

function fieldRow(meta, r, c, dirty, inputs, onDirty) {
  const v = r.v[c.letter]; const isFormula = r.f[c.letter];
  const label = h('label', { for: 'f-' + c.letter }, c.label, isFormula ? h('span', { class: 'fx', title: `Calculated by the workbook — ${meta.sheet}!${c.letter}${r.row}` }, 'fx') : null);
  let ctrl;
  if (isFormula) {
    ctrl = h('div', { class: 'ro', id: 'f-' + c.letter }, meta.statusCol === c.letter ? pill(v) : c.letter === meta.tickerCol && v ? h('a', { href: '#/security/' + encodeURIComponent(v) }, v) : fmtValue(v, c.fmt, c.type) || h('span', { class: 'muted' }, '—'));
  } else if (c.letter === meta.tickerCol && meta.key !== 'pipeline' && meta.key !== 'registry') {
    ctrl = tickerInput(v, (nv) => { dirty.set(c.letter, nv); onDirty(); }, 'f-' + c.letter);
  } else {
    const isRef = /Evidence IDs|Candidate ID/.test(c.label);
    ctrl = fieldInput(c, v, (nv) => { if (nv === (v ?? '')) dirty.delete(c.letter); else dirty.set(c.letter, nv); onDirty(); }, { id: 'f-' + c.letter });
    if (/url|source|memo/i.test(c.label) && typeof v === 'string' && /https?:\/\//.test(v)) return h('div', { class: 'field wide' }, label, ctrl, h('div', { class: 'links-in' }, linkify(v)));
    if (isRef && v) ctrl = h('div', null, ctrl, h('div', { class: 'links-in' }, refLinks(String(v))));
  }
  const wide = c.type === 'text' && /summary|thesis|notes|rationale|memo|source|reason|findings/i.test(c.label);
  return h('div', { class: 'field' + (wide ? ' wide' : '') }, label, ctrl);
}
function refLinks(s) {
  const frag = document.createDocumentFragment();
  s.split(/[,;\s]+/).filter(Boolean).forEach((id, i) => { if (i) frag.append(' '); const key = /^EVD/.test(id) ? 'evidence' : /^MIR/.test(id) ? 'reviews' : /^MCP/.test(id) ? 'pipeline' : /^CAND/.test(id) ? 'compare' : null; frag.append(key ? h('a', { class: 'idc', href: hashRow(key, id) }, id) : id); });
  return frag;
}
function tickerInput(v, onChange, id) {
  const dl = h('datalist', { id: id + '-dl' });
  tickers().then((ts) => ts.forEach((t) => dl.append(h('option', { value: t.t }, t.n))));
  return h('div', null, h('input', { id, list: id + '-dl', type: 'text', value: v ?? '', oninput: (e) => onChange(e.target.value.toUpperCase().trim()) }), dl);
}

// ---------------------------------------------------------------- per-table actions
function recordActions(key, meta, r, reopen) {
  const btn = (label, fn, kind = '') => h('button', { class: 'btn small ' + kind, onclick: fn }, label);
  const out = [];
  if (key === 'pipeline') {
    const stage = r.v.Y; const stages = col(meta, 'Y').options; const i = stages.indexOf(stage);
    const closed = CLOSED.includes(stage);
    if (!closed) {
      const next = stages[i + 1] && !CLOSED.includes(stages[i + 1]) ? stages[i + 1] : null;
      if (next) out.push(btn(`Advance → ${next}`, () => advanceFlow(r.v.A, next, reopen), 'primary'));
      out.push(btn('Move to stage…', () => stagePicker(r, stages, reopen)));
      out.push(btn('Record committee disposition', () => dispositionDialog(r, meta, reopen)));
      out.push(btn('Refer to PEW-004', () => referFlow(r, reopen)));
      out.push(btn('Log evidence', () => openNew('evidence', { E: r.v.C })));
      out.push(btn('Close / reject…', () => closeDialog(r, meta, reopen), 'danger'));
    } else out.push(btn('Reopen on watch', async () => { try { await act('candidate.reopen', { id: r.v.A }); done('Candidate reopened'); reopen(); } catch (e) { toast(e.message, 'err'); } }));
  }
  if (key === 'registry' && r.v.B) {
    out.push(btn('Start candidate review', () => openNew('pipeline', { C: r.v.B, E: r.v.D === 'Certified Portfolio Holding' ? 'Retention Review' : 'MASR Addition Review' }), 'primary'));
    out.push(btn('Log evidence', () => openNew('evidence', { E: r.v.B })));
    if (r.v.D === 'Certified Portfolio Holding') out.push(btn('Log MIAR review', () => openNew('reviews', { C: r.v.B })));
  }
  if (key === 'miar' && r.v.B) { out.push(btn('Log MIAR review', () => openNew('reviews', { C: r.v.B }), 'primary')); out.push(btn('Log evidence', () => openNew('evidence', { E: r.v.B }))); }
  if (key === 'evidence' && r.v.E) out.push(btn('Start candidate review', () => openNew('pipeline', { C: r.v.E, W: r.v.A })));
  return out;
}
const done = (msg) => { state.version++; invalidate(); toast(msg, 'ok'); window.dispatchEvent(new Event('mw:refresh')); };

function stagePicker(r, stages, reopen) {
  let to = stages[stages.indexOf(r.v.Y) + 1] || stages[0];
  const sel = h('select', { onchange: (e) => (to = e.target.value) }, stages.filter((s) => !CLOSED.includes(s)).map((s) => h('option', { selected: s === to }, s)));
  modal('Move candidate to stage', h('div', null, h('p', null, `${r.v.A} is currently at `, h('b', null, r.v.Y), '. The workbook’s gate formulas decide whether the move is allowed.'), h('label', { class: 'lbl' }, 'Target stage', sel)),
    { actions: [{ label: 'Check gate & move', kind: 'primary', close: false, run: async (close) => { close(); await advanceFlow(r.v.A, to, reopen); return false; } }] });
}

export async function advanceFlow(id, to, reopen) {
  try {
    const res = await act('candidate.advance', { id, to });
    if (res.ok) { done(`${id} → ${to}`); reopen ? reopen() : 0; return; }
    blockedDialog(id, to, res, reopen, async () => { const f = await act('candidate.advance', { id, to, force: true }); done(`${id} → ${to} (gate exception recorded in audit log)`); reopen && reopen(); });
  } catch (e) { toast(e.message, 'err'); }
}

const FIXES = {
  'FAIL — EVIDENCE': ['Log evidence for this ticker', (r) => openNew('evidence', { E: r })],
  'FAIL — INCOMPLETE': ['Open the record to complete required fields', null],
  'FAIL — COMMITTEE DISPOSITION': ['Record committee disposition', 'disposition'],
  'FAIL — MASR RECORD REQUIRED': ['Add the security to the MASR registry', () => openNew('registry')],
  'FAIL — ELIGIBILITY': ['Review eligibility in Security 360', 'sec'],
  'FAIL — MIAR GATE': ['Review the MIAR dossier in Security 360', 'sec'],
  'FAIL — PEW REFERRAL': ['Complete the PEW-004 referral', 'refer'],
};
async function blockedDialog(id, to, res, reopen, force) {
  const t = await loadTable('pipeline', true); const row = t.rows.find((x) => x.v.A === id);
  const g = res.projected.gate; const fix = FIXES[g];
  const body = h('div', null,
    h('p', null, `Moving `, h('b', null, id), ' to ', h('b', null, to), ' would fail the stage gate:'),
    h('div', { class: 'gate-box' }, pill(g), h('div', null, h('b', null, res.projected.status), h('div', { class: 'muted' }, res.projected.action))),
    h('p', { class: 'muted' }, 'Nothing has been written. Resolve the blocker, or advance anyway to record a documented gate exception in the audit log.'),
    fix ? h('div', { class: 'row gap wrap' }, h('button', { class: 'btn', onclick: () => { document.querySelector('.modal-back')?.remove(); if (fix[1] === 'disposition') dispositionDialog(row, t.meta, reopen); else if (fix[1] === 'sec') location.hash = '#/security/' + encodeURIComponent(row.v.C); else if (fix[1] === 'refer') referFlow(row, reopen); else if (typeof fix[1] === 'function') fix[1](row.v.C); } }, fix[0])) : null);
  modal('Stage gate blocked', body, { actions: [{ label: 'Advance anyway (record exception)', kind: 'danger', run: force }, { label: 'Cancel', close: true, run: async () => true }] });
}

function dispositionDialog(r, meta, reopen) {
  const opts = col(meta, 'AD').options; let disp = r.v.AD || 'Pending'; let date = r.v.AE || todaySerial();
  modal('Committee disposition — ' + r.v.A, h('div', { class: 'stack' },
    h('label', { class: 'lbl' }, 'Disposition', h('select', { onchange: (e) => (disp = e.target.value) }, opts.map((o) => h('option', { selected: o === disp }, o)))),
    h('label', { class: 'lbl' }, 'Decision date', h('input', { type: 'date', value: serialToISO(date), onchange: (e) => (date = isoToSerial(e.target.value)) })),
    h('p', { class: 'muted' }, 'Also mirrored to the security’s MASR registry record (Committee Disposition and Last Committee Review).')),
    { actions: [{ label: 'Record disposition', kind: 'primary', run: async () => { await act('candidate.disposition', { id: r.v.A, disposition: disp, date }); done('Disposition recorded'); reopen && reopen(); } }] });
}

async function referFlow(r, reopen) {
  try {
    const res = await act('candidate.refer', { id: r.v.A });
    if (res.ok) { done(`${r.v.A} referred to PEW-004 as ${res.pewId}${res.created ? ' (new comparison slot opened)' : ''}`); reopen && reopen(); return; }
    blockedDialog(r.v.A, 'Referred to PEW-004', res, reopen, async () => { await act('candidate.refer', { id: r.v.A, force: true }); done('Referral recorded with gate exception'); reopen && reopen(); });
  } catch (e) { toast(e.message, 'err'); }
}

function closeDialog(r, meta, reopen) {
  const reasons = col(meta, 'AO').options; const f = { stage: 'Rejected', reason: reasons[0], by: state.user || '', date: todaySerial() };
  modal('Close candidate — ' + r.v.A, h('div', { class: 'stack' },
    h('label', { class: 'lbl' }, 'Outcome', h('select', { onchange: (e) => (f.stage = e.target.value) }, ['Rejected', 'Closed', 'Removed'].map((s) => h('option', null, s)))),
    h('label', { class: 'lbl' }, 'Reason', h('select', { onchange: (e) => (f.reason = e.target.value) }, reasons.map((s) => h('option', null, s)))),
    h('label', { class: 'lbl' }, 'Closed by', h('input', { type: 'text', value: f.by, oninput: (e) => (f.by = e.target.value) })),
    h('label', { class: 'lbl' }, 'Date', h('input', { type: 'date', value: serialToISO(f.date), onchange: (e) => (f.date = isoToSerial(e.target.value)) }))),
    { actions: [{ label: 'Close candidate', kind: 'danger', run: async () => { await act('candidate.close', { id: r.v.A, ...f }); done('Candidate closed'); reopen && reopen(); } }] });
}

// ---------------------------------------------------------------- creation forms
export async function openNew(key, presets = {}) {
  if (key === 'pipeline') return newCandidate(presets);
  if (key === 'registry') return newSecurity(presets);
  const { meta } = await loadTable(key);
  const req = new Set(REQUIRED[key] || []); const values = {};
  const today = todaySerial();
  const defaults = { evidence: { B: today, C: today, T: 'New', U: 'No' }, reviews: { B: today } }[key] || {};
  Object.assign(values, defaults, presets);
  const inputs = meta.cols.filter((c) => !c.auto && c.letter !== meta.idCol || (key === 'actions' && c.letter === 'A' && false));
  const rowsF = inputs.map((c) => {
    const ctrl = c.letter === meta.tickerCol ? tickerInput(values[c.letter], (v) => (values[c.letter] = v)) : fieldInput(c, values[c.letter], (v) => (values[c.letter] = v));
    return h('div', { class: 'field' + (c.type === 'text' && /summary|notes|rationale|memo|source|findings/i.test(c.label) ? ' wide' : '') }, h('label', null, c.label, req.has(c.letter) ? h('span', { class: 'req', title: 'Required' }, '*') : null), ctrl);
  });
  modal(`New — ${meta.title}`, h('div', { class: 'fgrid' }, rowsF), {
    wide: true, actions: [{ label: 'Create record', kind: 'primary', run: async () => {
      const miss = [...req].filter((l) => values[l] === undefined || values[l] === ''); if (miss.length) throw new Error('Required: ' + miss.map((l) => col(meta, l).label).join(', '));
      const res = await act('record.add', { table: key, values });
      done(`${meta.title}: created ${res.id || 'record'} (row ${res.row})`); if (res.id) location.hash = hashRow(key, res.id); else location.hash = `#/${key}`;
    } }],
  });
}

async function newCandidate(pre) {
  const { meta } = await loadTable('pipeline'); const ts = await tickers();
  const v = { type: pre.E || 'Research Candidate', source: 'Advisor Observation', owner: 'Research Committee', due: todaySerial() + 30, ticker: pre.C || '', evidence: pre.W || '', ...pre.extra };
  const dl = h('datalist', { id: 'nc-dl' }, ts.map((t) => h('option', { value: t.t }, t.n)));
  const known = h('div', { class: 'hint-line' });
  const upd = () => { const t = ts.find((x) => x.t === v.ticker); clear(known).append(v.ticker ? (t ? h('span', { class: 'ok-t' }, `✓ In MASR registry — ${t.n} (${t.cls})`) : h('span', { class: 'warn-t' }, '⚠ Not in the MASR registry yet — the stage gate will require a registry record before it can pass MIAR Review.')) : ''); };
  const sel = (c, k) => h('select', { onchange: (e) => (v[k] = e.target.value) }, col(meta, c).options.map((o) => h('option', { selected: o === v[k] }, o)));
  modal('New candidate', h('div', { class: 'fgrid' },
    h('div', { class: 'field' }, h('label', null, 'Ticker', h('span', { class: 'req' }, '*')), h('input', { type: 'text', list: 'nc-dl', value: v.ticker, oninput: (e) => { v.ticker = e.target.value.toUpperCase().trim(); upd(); } }), dl, known),
    h('div', { class: 'field' }, h('label', null, 'Candidate type *'), sel('E', 'type')),
    h('div', { class: 'field' }, h('label', null, 'Source / referral *'), sel('H', 'source')),
    h('div', { class: 'field' }, h('label', null, 'Comparison group'), h('input', { type: 'text', oninput: (e) => (v.group = e.target.value) })),
    h('div', { class: 'field' }, h('label', null, 'Incumbent / replacement target'), h('input', { type: 'text', oninput: (e) => (v.target = e.target.value) })),
    h('div', { class: 'field' }, h('label', null, 'Assigned owner *'), h('input', { type: 'text', value: v.owner, oninput: (e) => (v.owner = e.target.value) })),
    h('div', { class: 'field' }, h('label', null, 'Due date *'), h('input', { type: 'date', value: serialToISO(v.due), onchange: (e) => (v.due = isoToSerial(e.target.value)) })),
    h('div', { class: 'field' }, h('label', null, 'Evidence IDs referenced'), h('input', { type: 'text', value: v.evidence, placeholder: 'EVD-YYYYMMDD-001, …', oninput: (e) => (v.evidence = e.target.value) })),
    h('div', { class: 'field wide' }, h('label', null, 'Decision / thesis summary'), h('textarea', { rows: 3, oninput: (e) => (v.summary = e.target.value) })),
    h('div', { class: 'field wide' }, h('label', null, 'Source / internal memo / exception rationale'), h('textarea', { rows: 2, oninput: (e) => (v.memo = e.target.value) }))),
    { wide: true, actions: [{ label: 'Create candidate', kind: 'primary', run: async () => { const res = await act('candidate.create', v); done(`Created ${res.id} · ${res.status}`); location.hash = hashRow('pipeline', res.id); } }] });
  upd();
}

async function newSecurity(pre) {
  const { meta } = await loadTable('registry');
  const v = { class: 'Research Candidate', status: 'Candidate — Under Research', basis: 'Manifest Research', type: 'Equity', ...pre };
  const sel = (c, k) => h('select', { onchange: (e) => (v[k] = e.target.value === '' ? undefined : col(meta, c).options.find((o) => String(o) === e.target.value)) }, h('option', { value: '' }, '—'), col(meta, c).options.map((o) => h('option', { value: o, selected: o === v[k] }, o)));
  const txt = (k, ph, type = 'text') => h('input', { type, placeholder: ph || '', value: v[k] ?? '', oninput: (e) => (v[k] = type === 'number' ? (e.target.value === '' ? undefined : +e.target.value) : e.target.value) });
  modal('Add security to MASR registry', h('div', { class: 'fgrid' },
    h('div', { class: 'field' }, h('label', null, 'Ticker *'), txt('ticker')), h('div', { class: 'field' }, h('label', null, 'Security name *'), txt('security')),
    h('div', { class: 'field' }, h('label', null, 'Record class *'), sel('D', 'class')), h('div', { class: 'field' }, h('label', null, 'Registry status *'), sel('E', 'status')),
    h('div', { class: 'field' }, h('label', null, 'Admission basis *'), sel('F', 'basis')), h('div', { class: 'field' }, h('label', null, 'Production sleeve *'), sel('G', 'sleeve')),
    h('div', { class: 'field' }, h('label', null, 'Approved / proposed role *'), txt('role')), h('div', { class: 'field' }, h('label', null, 'Security type *'), sel('I', 'type')),
    h('div', { class: 'field' }, h('label', null, 'Canonical MASR ID'), txt('canonicalId', 'from institutional registry')), h('div', { class: 'field' }, h('label', null, 'Market cap ($B)'), txt('marketCap', '', 'number')),
    h('div', { class: 'field' }, h('label', null, 'Zacks rank'), sel('U', 'zacks')), h('div', { class: 'field' }, h('label', null, 'Merrill status'), sel('V', 'merrill')),
    h('div', { class: 'field' }, h('label', null, 'Empirical rank'), txt('empirical', '', 'number')),
    h('div', { class: 'field wide' }, h('label', null, 'Notes / source / exception rationale'), h('textarea', { rows: 2, oninput: (e) => (v.notes = e.target.value) }))),
    { wide: true, actions: [{ label: 'Add to registry', kind: 'primary', run: async () => { const res = await act('registry.add', v); done(`${res.ticker} added · ${res.status}`); location.hash = '#/security/' + encodeURIComponent(res.ticker); } }] });
}
