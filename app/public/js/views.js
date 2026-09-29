// Overview dashboard, Security 360, audit log and admin views
import { api, act, h, clear, state, toast, modal, fmtValue, pill, fieldInput, download, todaySerial } from './ui.js';
import { loadTable, openRecord, openNew, cellText, invalidate } from './table.js';

const cv = (P, a) => { const c = P.cells.find((x) => x[0] === +/\d+/.exec(a)[0] - 1 && x[1] === colNum(/[A-Z]+/.exec(a)[0])); return c ? c[2] : null; };
const colNum = (s) => s.split('').reduce((n, c) => n * 26 + c.charCodeAt(0) - 64, 0) - 1;
const sheetIndex = (P) => { const m = new Map(); for (const [r, c, v] of P.cells) m.set(r + ':' + c, v); return (a) => m.get(+/\d+/.exec(a)[0] - 1 + ':' + colNum(/[A-Z]+/.exec(a)[0])) ?? null; };

const DEST = [[/registry/i, '#/registry'], [/MIAR/i, '#/miar'], [/pipeline/i, '#/pipeline'], [/comparison/i, '#/compare'], [/committee/i, '#/actions']];
const destOf = (t) => (DEST.find(([re]) => re.test(t || '')) || [, '#/home'])[1];

// ------------------------------------------------------------------ Overview
export async function renderHome(root) {
  const [P, pipe, reg, dc, sl] = await Promise.all([api('/api/sheet/' + encodeURIComponent('22 RCC-004 Control Center')), loadTable('pipeline', true), loadTable('registry', true), api('/api/sheet/' + encodeURIComponent('02 Decision Center')), api('/api/sheet/Sleeve%20Summary')]);
  const g = sheetIndex(P), d = sheetIndex(dc), s = sheetIndex(sl);
  const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  const ready = g('A13');
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('h1', null, 'Overview'), h('p', { class: 'sub' }, 'MOPS-003 · RCC-004 MASR Registry & Candidate Pipeline — every figure below is a live cell in the workbook.')),
    h('div', { class: 'row gap' }, h('button', { class: 'btn primary', onclick: () => openNew('pipeline') }, '＋ New candidate'), h('button', { class: 'btn', onclick: () => openNew('evidence') }, 'Log evidence'), h('button', { class: 'btn', onclick: () => openNew('registry') }, 'Add security'))));

  const tiles = [['MASR records', 'A7', '#/registry'], ['Certified holdings', 'E7', '#/registry?cls=Certified%20Portfolio%20Holding'], ['Approved non-holdings', 'I7', '#/registry?cls=MASR%20Approved%20Non-Holding'], ['Active candidates', 'M7', '#/pipeline'], ['PEW-004 referrals', 'Q7', '#/pipeline?stage=Referred%20to%20PEW-004'], ['Control exceptions', 'U7', '#/pipeline']];
  wrap.append(h('div', { class: 'banner ' + (/EXCEPTION|NOT INIT/.test(ready) ? 'warn' : 'ok') },
    h('div', null, h('div', { class: 'eyebrow' }, 'RCC-004 readiness'), h('b', null, ready)),
    h('div', { class: 'banner-m' }, h('span', null, g('G13')), h('span', null, 'Gates: ', g('M13')), h('span', null, 'Routing: ', g('S13')))));
  wrap.append(h('div', { class: 'tiles' }, tiles.map(([l, a, href]) => h('a', { class: 'tile' + (l === 'Control exceptions' && g(a) > 0 ? ' bad' : ''), href }, h('div', { class: 'tile-l' }, l), h('div', { class: 'tile-v' }, fmtValue(g(a))), h('div', { class: 'tile-a' }, 'Open ›')))));

  // exceptions table
  const exc = []; for (let r = 18; r <= 25; r++) exc.push({ p: g('A' + r), t: g('B' + r), n: g('D' + r), st: g('E' + r), act: g('F' + r), auth: g('I' + r), dest: g('K' + r), imp: g('L' + r) });
  const excCard = h('section', { class: 'card-panel wide' }, h('h3', null, 'Control exceptions & required actions'), h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' },
    h('thead', null, h('tr', null, ['#', 'Control', 'Count', 'State', 'Required action', 'Authority', ''].map((x) => h('th', null, x)))),
    h('tbody', null, exc.map((e) => h('tr', { class: e.st === 'PASS' ? '' : 'attn', tabindex: 0, onclick: () => (location.hash = destOf(e.dest)) }, h('td', null, e.p), h('td', null, h('b', null, e.t), h('div', { class: 'muted small' }, e.imp)), h('td', { class: 'num' }, e.n), h('td', null, pill(e.st)), h('td', null, e.act), h('td', null, e.auth), h('td', { class: 'go' }, '›')))))));

  // funnel
  const stages = []; for (let r = 18; r <= 25; r++) stages.push({ n: g('R' + r), c: g('S' + r), pass: g('T' + r), ex: g('U' + r) });
  const allStages = pipe.meta.cols.find((c) => c.letter === 'Y').options; const counts = {}; pipe.rows.forEach((r) => (counts[r.v.Y] = (counts[r.v.Y] || 0) + 1));
  const max = Math.max(1, ...Object.values(counts));
  const funnel = h('section', { class: 'card-panel' }, h('h3', null, 'Candidate stage funnel'), h('div', { class: 'bars' }, allStages.map((st) => h('a', { class: 'bar-row', href: '#/pipeline?stage=' + encodeURIComponent(st) }, h('span', { class: 'bar-l' }, st), h('span', { class: 'bar-t' }, h('span', { class: 'bar-f', style: { width: ((counts[st] || 0) / max) * 100 + '%' } })), h('b', null, counts[st] || 0)))));
  const comp = []; for (let r = 18; r <= 25; r++) comp.push({ n: g('N' + r), c: g('O' + r), ok: g('P' + r), ex: g('Q' + r) });
  const cmax = Math.max(1, ...comp.map((c) => c.c));
  const composition = h('section', { class: 'card-panel' }, h('h3', null, 'Registry composition'), h('div', { class: 'bars' }, comp.map((c) => h('a', { class: 'bar-row', href: '#/registry?cls=' + encodeURIComponent(c.n) }, h('span', { class: 'bar-l' }, c.n), h('span', { class: 'bar-t stack2' }, h('span', { class: 'bar-f ok', title: 'control clear', style: { width: (c.ok / cmax) * 100 + '%' } }), h('span', { class: 'bar-f ex', title: 'exceptions', style: { width: (c.ex / cmax) * 100 + '%' } })), h('b', null, c.c)))), h('div', { class: 'legend' }, h('span', { class: 'lg ok' }, 'Control clear'), h('span', { class: 'lg ex' }, 'Exception')));

  // work queue
  const queue = pipe.rows.filter((r) => r.v.AK && !['OPEN — ON TRACK', 'CLOSED'].includes(r.v.AK)).sort((a, b) => (a.v.AB || 0) - (b.v.AB || 0));
  const qCard = h('section', { class: 'card-panel wide' }, h('h3', null, `Candidate work queue`, h('span', { class: 'count' }, queue.length)), queue.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, ['Candidate', 'Ticker', 'Stage', 'Status', 'Next required action', 'Due', ''].map((x) => h('th', null, x)))),
    h('tbody', null, queue.slice(0, 12).map((r) => h('tr', { tabindex: 0, onclick: () => openRecord('pipeline', r.row) }, h('td', null, h('span', { class: 'idc' }, r.v.A)), h('td', null, h('a', { class: 'tick', href: '#/security/' + r.v.C, onclick: (e) => e.stopPropagation() }, r.v.C)), h('td', null, r.v.Y), h('td', null, pill(r.v.AK)), h('td', null, r.v.AL), h('td', null, fmtValue(r.v.AB, 'mmm d, yyyy')), h('td', { class: 'go' }, '›')))))) : h('div', { class: 'empty small' }, 'No candidate exceptions.'));
  const regEx = reg.rows.filter((r) => r.v.AD && !['CONTROL CLEAR', 'INACTIVE / CLOSED'].includes(r.v.AD));
  const byStatus = {}; regEx.forEach((r) => (byStatus[r.v.AD] = (byStatus[r.v.AD] || 0) + 1));
  const rCard = h('section', { class: 'card-panel' }, h('h3', null, 'Registry exceptions', h('span', { class: 'count' }, regEx.length)), h('div', { class: 'stack' }, Object.entries(byStatus).map(([k, n]) => h('a', { class: 'ex-row', href: '#/registry?status=' + encodeURIComponent(k) }, pill(k), h('span', { class: 'muted' }, reg.rows.find((r) => r.v.AD === k)?.v.AE || ''), h('b', null, n)))));

  // decision center + sleeves
  const dcCard = h('section', { class: 'card-panel' }, h('h3', null, 'Decision Center'), h('div', { class: 'kv' }, [['Decision state', d('B6')], ['Committee meeting', d('E6')], ['Highest priority', d('B14')], ['Data completeness', fmtValue(d('B7'), '0%')], ['Committee decisions', d('B13')]].map(([k, v]) => h('div', null, h('span', null, k), h('b', null, v == null ? '—' : String(v))))), h('a', { class: 'lnk', href: '#/sheet/02%20Decision%20Center' }, 'Open Decision Center ›'));
  const sleeves = []; for (let r = 3; r <= 10; r++) sleeves.push({ n: s('A' + r), w: s('B' + r), c: s('C' + r) });
  const slCard = h('section', { class: 'card-panel' }, h('h3', null, 'Certified sleeves'), h('div', { class: 'bars' }, sleeves.filter((x) => x.n).map((x) => h('div', { class: 'bar-row' }, h('span', { class: 'bar-l' }, x.n), h('span', { class: 'bar-t' }, h('span', { class: 'bar-f', style: { width: Math.min(100, (typeof x.w === 'number' ? x.w : 0) * 300) + '%' } })), h('b', null, typeof x.w === 'number' ? fmtValue(x.w, '0.0%') : x.w)))), h('a', { class: 'lnk', href: '#/sheet/Certified%20Allocation' }, 'Open Certified Allocation ›'));

  wrap.append(h('div', { class: 'cols' }, excCard, funnel, composition, qCard, rCard, dcCard, slCard));
}

// ------------------------------------------------------------------ Security 360
export async function renderSecurity(root, ticker) {
  if (!ticker) return renderSecurityIndex(root);
  const S = await api('/api/security/' + encodeURIComponent(ticker)); const reg = S.sections.registry.rows[0]; const miar = S.sections.miar.rows[0];
  const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  const rv = (l) => (reg ? reg.v[l] : null); const mv = (l) => (miar ? miar.v[l] : null);
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('div', { class: 'eyebrow' }, 'Security 360'), h('h1', null, S.ticker, rv('C') ? h('span', { class: 'h1-sub' }, ' ' + rv('C')) : null),
    h('div', { class: 'row gap wrap' }, reg ? [pill(rv('D')), pill(rv('AD')), pill(rv('X'))] : h('span', { class: 'pill p-warn' }, 'Not in MASR registry'))),
    h('div', { class: 'row gap' }, reg ? h('button', { class: 'btn primary', onclick: () => openNew('pipeline', { C: S.ticker, E: rv('D') === 'Certified Portfolio Holding' ? 'Retention Review' : 'MASR Addition Review' }) }, 'Start candidate review') : h('button', { class: 'btn primary', onclick: () => openNew('registry', { ticker: S.ticker }) }, 'Add to MASR registry'), h('button', { class: 'btn', onclick: () => openNew('evidence', { E: S.ticker }) }, 'Log evidence'), miar ? h('button', { class: 'btn', onclick: () => openNew('reviews', { C: S.ticker }) }, 'Log MIAR review') : null)));
  if (reg && rv('AE')) wrap.append(h('div', { class: 'callout' }, h('b', null, 'Registry next action · '), rv('AE')));
  const kp = [['Integrity', mv('K') ?? rv('N')], ['MICS', mv('L') ?? rv('O')], ['Empirical rank', rv('W')], ['Zacks rank', rv('U')], ['Merrill', rv('V')], ['Market cap ($B)', rv('T')], ['Conviction', rv('P')], ['Research freshness', rv('M')]];
  wrap.append(h('div', { class: 'tiles small' }, kp.map(([l, v]) => h('div', { class: 'tile static' }, h('div', { class: 'tile-l' }, l), h('div', { class: 'tile-v sm' }, v == null || v === '' ? '—' : String(v))))));
  if (S.certified) wrap.append(h('section', { class: 'card-panel' }, h('h3', null, 'Certified allocation (MFPDF)'), h('div', { class: 'kv' }, Object.entries(S.certified.values).map(([k, v]) => h('div', null, h('span', null, k), h('b', null, typeof v === 'number' && v < 1 && v > 0 ? fmtValue(v, '0.00%') : v == null ? '—' : String(v)))))));
  const sec = (key, title, listCols) => {
    const sct = S.sections[key]; const meta = sct.meta; const rows = sct.rows;
    const cols = listCols.map((l) => meta.cols.find((c) => c.letter === l));
    return h('section', { class: 'card-panel wide' }, h('h3', null, title, h('span', { class: 'count' }, rows.length), h('a', { class: 'lnk right', href: '#/' + key }, 'Open table ›')),
      rows.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, cols.map((c) => h('th', null, c.label)))),
        h('tbody', null, rows.map((r) => h('tr', { tabindex: 0, onclick: () => openRecord(key, r.row) }, cols.map((c) => h('td', null, meta.statusCol === c.letter ? pill(r.v[c.letter]) : fmtValue(r.v[c.letter], c.fmt, c.type)))))))) : h('div', { class: 'empty small' }, 'None on record.'));
  };
  wrap.append(h('div', { class: 'cols one' },
    sec('registry', 'MASR registry record', ['A', 'D', 'E', 'G', 'X', 'AD', 'AA']),
    sec('miar', 'MIAR dossier', ['A', 'M', 'K', 'L', 'Z', 'AA', 'AB']),
    sec('pipeline', 'Candidate pipeline', ['A', 'E', 'Y', 'Z', 'AK', 'AB']),
    sec('evidence', 'RCC-002 evidence', ['A', 'B', 'H', 'J', 'K', 'T', 'U']),
    sec('reviews', 'MIAR review log', ['A', 'B', 'E', 'F', 'I', 'R']),
    sec('compare', 'PEW-004 comparison', ['A', 'C', 'Q', 'T', 'U', 'V', 'Y'])));
}

async function renderSecurityIndex(root) {
  const ts = (await loadTable('registry')).rows; const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  const input = h('input', { type: 'search', placeholder: 'Type a ticker or company…', 'aria-label': 'Find security', oninput: draw });
  const list = h('div', { class: 'sec-grid' });
  function draw() { const q = input.value.toLowerCase(); clear(list).append(...ts.filter((r) => !q || (r.v.B + ' ' + r.v.C).toLowerCase().includes(q)).slice(0, 120).map((r) => h('a', { class: 'sec-chip', href: '#/security/' + encodeURIComponent(r.v.B) }, h('b', null, r.v.B), h('span', null, r.v.C), pill(r.v.AD)))); }
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('h1', null, 'Security 360'), h('p', { class: 'sub' }, 'Everything the workbook holds on one security — registry, MIAR, pipeline, evidence, reviews and PEW-004.'))), h('div', { class: 'toolbar' }, input), list); draw();
}

// ------------------------------------------------------------------ Audit
export async function renderAudit(root) {
  const A = await api('/api/audit?limit=500'); const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('h1', null, 'Audit log'), h('p', { class: 'sub' }, `${A.total} recorded change${A.total === 1 ? '' : 's'} — stored in the workbook sheet “25 App Audit Log”.`)), h('a', { class: 'btn ghost', href: '#/sheet/25%20App%20Audit%20Log' }, 'Open sheet grid')));
  wrap.append(A.rows.length ? h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' }, h('thead', null, h('tr', null, ['When (UTC)', 'User', 'Action', 'Record', 'Field', 'From', 'To', 'Note'].map((x) => h('th', null, x)))),
    h('tbody', null, A.rows.map((r) => h('tr', null, h('td', null, r[0]), h('td', null, r[1]), h('td', null, r[2]), h('td', null, h('a', { href: `#/sheet/${encodeURIComponent(r[3])}?cell=${r[4]}` }, r[8] || `${r[3]}!${r[4]}`)), h('td', null, r[5]), h('td', { class: 'muted' }, r[6]), h('td', null, r[7]), h('td', { class: 'muted' }, r[9]))))))
    : h('div', { class: 'empty' }, h('b', null, 'No changes yet.'), h('p', null, 'Every edit and workflow action made in the app is logged here with user, previous value and new value.')));
}

// ------------------------------------------------------------------ Admin
export async function renderAdmin(root) {
  const wrap = h('div', { class: 'page' }); clear(root).append(wrap);
  const snaps = await api('/api/snapshots');
  const label = h('input', { type: 'text', placeholder: 'Snapshot label (optional)' });
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('h1', null, 'Workbook & snapshots'), h('p', { class: 'sub' }, 'The .xlsx workbook is the single source of truth. Every change is written into it; download it any time to keep working in Excel.'))),
    h('div', { class: 'cols' },
      h('section', { class: 'card-panel' }, h('h3', null, 'Workbook file'), h('p', null, 'Manifest_Workbench.xlsx — formulas, charts, validations and formatting are preserved. Excel recalculates on open.'), h('a', { class: 'btn primary', href: '/api/download' }, 'Download .xlsx')),
      h('section', { class: 'card-panel' }, h('h3', null, 'Acting as'), h('p', null, 'Your name is stamped on every audit-log entry.'), h('input', { type: 'text', value: state.user, placeholder: 'Your name', onchange: (e) => { state.user = e.target.value.trim(); localStorage.setItem('mw.user', state.user); window.dispatchEvent(new Event('mw:user')); toast('Saved', 'ok'); } })),
      h('section', { class: 'card-panel wide' }, h('h3', null, 'Snapshots'), h('div', { class: 'row gap' }, label, h('button', { class: 'btn', onclick: async () => { await api('/api/snapshots', { body: { label: label.value } }); toast('Snapshot saved', 'ok'); renderAdmin(root); } }, 'Create snapshot')),
        snaps.length ? h('table', { class: 'tbl' }, h('tbody', null, snaps.map((s) => h('tr', null, h('td', null, s.name), h('td', { class: 'muted' }, Math.round(s.size / 1024) + ' KB'), h('td', null, h('button', { class: 'btn small danger', onclick: () => modal('Restore snapshot?', h('p', null, `Replace the live workbook with ${s.name}? The current state is saved first as a pre-restore snapshot.`), { actions: [{ label: 'Restore', kind: 'danger', run: async () => { await api('/api/restore', { body: { name: s.name } }); invalidate(); state.version++; toast('Restored', 'ok'); location.hash = '#/home'; location.reload(); } }] }) }, 'Restore')))))) : h('p', { class: 'muted' }, 'No snapshots yet.'))));
}
