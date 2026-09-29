import { api, h, clear, state, toast, debounce } from './ui.js';
import { renderTable, closeDrawer, invalidate, tickers } from './table.js';
import { renderGrid } from './grid.js';
import { renderHome, renderSecurity, renderAudit, renderAdmin } from './views.js';

const TABLE_ROUTES = { pipeline: 'Candidate Pipeline', registry: 'MASR Registry', miar: 'MIAR Dossiers', evidence: 'Evidence Ledger', reviews: 'MIAR Review Log', compare: 'PEW-004 Comparison', actions: 'Committee Actions', watch: 'Companies to Review' };
const NAV = [
  ['Command', [['home', 'Overview', '◧'], ['sheet/02 Decision Center', 'Decision Center', '⚖'], ['actions', 'Committee Actions', '☑'], ['watch', 'Companies to Review', '◉'], ['sheet/00 CISC Dashboard', 'CISC Dashboard', '▦']]],
  ['Research pipeline', [['pipeline', 'Candidate Pipeline', '⇢'], ['registry', 'MASR Registry', '☰'], ['security', 'Security 360', '◎'], ['evidence', 'Evidence Ledger', '❏'], ['miar', 'MIAR Dossiers', '❐'], ['reviews', 'MIAR Review Log', '✎']]],
  ['Portfolio engineering', [['compare', 'PEW-004 Comparison', '⇄'], ['sheet/Certified Allocation', 'Certified Allocation', '▤'], ['sheet/Sleeve Summary', 'Sleeve Summary', '◔'], ['sheet/12 Allocation Lab', 'Allocation Lab', '⚗'], ['sheet/13 Validation & Cert', 'Validation & Cert', '✓']]],
  ['Workbook', [['audit', 'Audit log', '⌛'], ['admin', 'Snapshots & download', '⬇'], ['sheets', 'All sheets', '☷']]],
];

const $ = (id) => document.getElementById(id);
let current = null;

function parseHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, '')); const [pathPart, qs] = raw.split('?'); const parts = pathPart.split('/');
  return { route: parts[0] || 'home', rest: parts.slice(1).join('/'), q: Object.fromEntries(new URLSearchParams(qs || '')) };
}

async function route() {
  closeDrawer(); const { route: r, rest, q } = parseHash(); const view = $('view'); current = { r, rest, q };
  highlightNav(); view.scrollTop = 0;
  try {
    if (r === 'home') await renderHome(view);
    else if (TABLE_ROUTES[r]) await renderTable(view, r, { ...q, open: rest || undefined });
    else if (r === 'security') await renderSecurity(view, rest);
    else if (r === 'sheet') await renderGrid(view, rest, q);
    else if (r === 'sheets') await renderSheets(view);
    else if (r === 'audit') await renderAudit(view);
    else if (r === 'admin') await renderAdmin(view);
    else clear(view).append(h('div', { class: 'empty' }, 'Page not found'));
  } catch (e) { console.error(e); clear(view).append(h('div', { class: 'empty err' }, h('b', null, 'Could not load this view'), h('p', null, e.message), h('button', { class: 'btn', onclick: route }, 'Retry'))); }
  document.title = 'Manifest Workbench — ' + (TABLE_ROUTES[r] || (r === 'sheet' ? rest : r[0].toUpperCase() + r.slice(1)));
}

function highlightNav() {
  const { route: r, rest } = parseHash(); const key = r === 'sheet' ? `sheet/${rest}` : r;
  document.querySelectorAll('#nav a[data-k]').forEach((a) => a.classList.toggle('on', a.dataset.k === key));
}

async function renderSheets(view) {
  const wrap = h('div', { class: 'page' }); clear(view).append(wrap);
  const groups = [['Command & dashboard', /^(00|01|02|03|04|05|99)/], ['Portfolio (MFPDF)', /^(Executive|Certified|Sleeve|Rebalancing|Sources)/], ['Portfolio Engineering Workbench', /^(06|07|08|09|10|11|12|13|14|15|98)/], ['Research Control Centers (RCC)', /^(16|17|18|19|20|21|22|23|24|97)/], ['App', /^25/]];
  const q = h('input', { type: 'search', placeholder: 'Filter sheets…', oninput: draw }); const box = h('div');
  function draw() {
    clear(box); for (const [t, re] of groups) {
      const list = state.meta.sheets.filter((s) => re.test(s.name) && s.name.toLowerCase().includes(q.value.toLowerCase())); if (!list.length) continue;
      box.append(h('h3', { class: 'gh' }, t), h('div', { class: 'sheet-grid' }, list.map((s) => h('a', { class: 'sheet-card', href: '#/sheet/' + encodeURIComponent(s.name) }, h('b', null, s.name), h('span', { class: 'muted' }, `${s.rows} × ${s.cols}`)))));
    }
  }
  wrap.append(h('div', { class: 'page-h' }, h('div', null, h('h1', null, 'All sheets'), h('p', { class: 'sub' }, `${state.meta.sheets.length} sheets — every one is viewable and editable in place (formulas stay protected).`))), h('div', { class: 'toolbar' }, q), box); draw();
}

function buildNav() {
  const nav = clear($('nav'));
  nav.append(h('a', { class: 'brand', href: '#/home' }, h('svg', { viewBox: '0 0 32 32', width: 30, height: 30, 'aria-hidden': 'true', html: '<rect width="32" height="32" rx="7" fill="#e8b64c"/><path d="M7 23V9l9 9 9-9v14" fill="none" stroke="#071d3a" stroke-width="3" stroke-linejoin="round"/>' }), h('div', null, h('b', null, 'Manifest'), h('span', null, 'Workbench'))));
  for (const [title, items] of NAV) nav.append(h('div', { class: 'nav-g' }, h('div', { class: 'nav-t' }, title), items.map(([k, l, ic]) => h('a', { href: '#/' + k.split('/').map(encodeURIComponent).join('/'), 'data-k': k }, h('span', { class: 'ic', 'aria-hidden': 'true' }, ic), l))));
  nav.append(h('div', { class: 'nav-foot' }, h('span', { id: 'sync' }, '● live'), h('span', { class: 'muted' }, 'Source of truth: workbook.xlsx')));
}

async function buildTop() {
  const top = clear($('top'));
  const ts = await tickers().catch(() => []);
  const dl = h('datalist', { id: 'gs-dl' }, ts.map((t) => h('option', { value: t.t }, t.n)));
  const search = h('input', { type: 'search', list: 'gs-dl', placeholder: 'Jump to ticker or record ID (VRT, MCP-…, EVD-…)', 'aria-label': 'Global search', onkeydown: (e) => {
    if (e.key !== 'Enter') return; const v = e.target.value.trim(); if (!v) return;
    const id = v.toUpperCase();
    if (/^MCP-/.test(id)) location.hash = '#/pipeline/' + id; else if (/^EVD-/.test(id)) location.hash = '#/evidence/' + id; else if (/^MIR-/.test(id)) location.hash = '#/reviews/' + id; else if (/^OP-/.test(id)) location.hash = '#/actions/' + id; else location.hash = '#/security/' + id;
    e.target.value = ''; } });
  const user = h('label', { class: 'user' }, h('span', null, 'Acting as'), h('input', { type: 'text', value: state.user, placeholder: 'your name', 'aria-label': 'Your name', onchange: (e) => { state.user = e.target.value.trim(); localStorage.setItem('mw.user', state.user); } }));
  top.append(h('button', { class: 'icon-btn menu', 'aria-label': 'Menu', onclick: () => document.body.classList.toggle('nav-open') }, '☰'), h('div', { class: 'search' }, search, dl), h('div', { class: 'grow' }), user, h('a', { class: 'btn small', href: '/api/download', title: 'Download the live workbook' }, '⬇ .xlsx'));
}

async function boot() {
  state.meta = await api('/api/meta'); state.version = state.meta.version;
  if (!state.user) { state.user = 'Research Analyst'; }
  buildNav(); await buildTop(); await route();
  window.addEventListener('hashchange', () => { document.body.classList.remove('nav-open'); route(); });
  window.addEventListener('mw:refresh', () => { if (current && !['sheet'].includes(current.r)) softRefresh(); });
  window.addEventListener('mw:refresh:soft', () => {});
  setInterval(async () => {
    try { const v = (await api('/api/version')).version; $('sync') && ($('sync').className = ''); if (v !== state.version) { state.version = v; invalidate(); if (!document.querySelector('.modal-back') && !document.querySelector('.drawer') && current.r !== 'sheet') route(); toast('Workbook updated', 'info', 1800); } } catch { $('sync') && ($('sync').className = 'off'); }
  }, 6000);
}
async function softRefresh() {
  // re-render the underlying list without closing an open drawer
  if (document.querySelector('.drawer')) return; await route();
}
boot();
