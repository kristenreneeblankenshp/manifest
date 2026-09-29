// Shared helpers: API, formatting, DOM, toasts, modals
export const state = { meta: null, user: localStorage.getItem('mw.user') || '', version: 0 };

export async function api(path, opts = {}) {
  const r = await fetch(path, { method: opts.body ? 'POST' : 'GET', headers: opts.body ? { 'content-type': 'application/json' } : {}, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.error || r.statusText), { status: r.status });
  return j;
}
export const act = (name, params) => api('/api/action/' + name, { body: { user: state.user || 'Unknown user', params } });

// ---- DOM ----
export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v; else if (k === 'html') el.innerHTML = v; else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v); else if (k === 'value') el.value = v; else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat(Infinity)) { if (k === null || k === undefined || k === false) continue; el.append(k.nodeType ? k : document.createTextNode(String(k))); }
  return el;
}
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

// ---- dates & numbers ----
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MFULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const DFULL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
export const serialToISO = (n) => new Date(Math.round((n - 25569) * 86400000)).toISOString().slice(0, 10);
export const isoToSerial = (s) => (s ? Math.round(Date.parse(s + 'T00:00:00Z') / 86400000) + 25569 : null);
export const todaySerial = () => Math.floor(Date.now() / 86400000) + 25569;
function fmtDate(n, f) {
  const d = new Date(Math.round((n - 25569) * 86400000)); const Y = d.getUTCFullYear(), M = d.getUTCMonth(), D = d.getUTCDate(), W = d.getUTCDay();
  return f.replace(/yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d/gi, (t) => ({ yyyy: Y, yy: String(Y).slice(2), mmmm: MFULL[M], mmm: MONTHS[M], mm: String(M + 1).padStart(2, '0'), m: M + 1, dddd: DFULL[W], ddd: DFULL[W].slice(0, 3), dd: String(D).padStart(2, '0'), d: D }[t.toLowerCase()]));
}
const isDateCode = (f) => /[dmy]/i.test(f.replace(/"[^"]*"|\[[^\]]*\]/g, '')) && !/^[0#,.%x"\s\-()+]+$/i.test(f.replace(/"[^"]*"/g, ''));
export function fmtNum(v, code) {
  const secs = code.split(';'); let sec = secs[0]; let neg = false;
  if (v < 0 && secs[1]) { sec = secs[1]; neg = true; } else if (v === 0 && secs[2]) return secs[2].replace(/"/g, '');
  const clean = sec.replace(/\[[^\]]*\]/g, '');
  const pct = /%/.test(clean); const dec = (/\.(0+)/.exec(clean) || [, ''])[1].length; const comma = /#,##/.test(clean);
  let x = Math.abs(v) * (pct ? 100 : 1); let s = x.toFixed(dec); if (comma) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const pre = (/^"?([^0#"]*)/.exec(clean.replace(/[()+]/g, '')) || [, ''])[1].replace(/"/g, '');
  const suffix = /"([^"]+)"\s*$/.exec(clean); s = s + (pct ? '%' : '') + (suffix && !pct ? suffix[1] : '');
  if (neg && /\(/.test(clean)) return '(' + s + ')';
  if (/^\+/.test(clean)) return (v >= 0 ? '+' : '-') + s;
  return (v < 0 && !neg ? '-' : '') + s;
}
export function fmtValue(v, code, type) {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'object') return v.err || '#ERR';
  if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
  if (typeof v === 'number') {
    if (code && code !== 'General') return isDateCode(code) ? fmtDate(v, code.split(';')[0]) : fmtNum(v, code);
    if (type === 'date') return fmtDate(v, 'mmm d, yyyy');
    return Number.isInteger(v) ? String(v) : String(Math.round(v * 10000) / 10000);
  }
  return String(v);
}

// ---- status pills ----
export function pillClass(s) {
  s = String(s || '').toUpperCase();
  if (!s) return 'p-none';
  if (/^(PASS|CONTROL CLEAR|CERTIFIED|ELIGIBLE$|OPEN — ON TRACK|CURRENT|ACTIVE$|COMPLETED|CLOSED|YES|APPROVE|DECISION RECORDED|CERTIFIED HOLDING)/.test(s) || s === 'ELIGIBLE') return 'p-ok';
  if (/OVERDUE|FAIL|BLOCK|NOT ELIGIBLE|DUPLICATE|REJECT|MISSING|SETUP REQUIRED|INCOMPLETE|ACTION REQUIRED|EXPIRED|MATERIAL EVENT/.test(s)) return 'p-bad';
  if (/REQUIRED|EXCEPTION|PENDING|REVIEW|DUE|WATCH|UNDER|OPEN|IN PROGRESS|ELIGIBLE WITH/.test(s)) return 'p-warn';
  return 'p-info';
}
export const pill = (s) => (s === '' || s == null ? h('span', { class: 'muted' }, '—') : h('span', { class: 'pill ' + pillClass(s) }, s));

// ---- toasts / modal ----
export function toast(msg, kind = 'info', ms = 4200) {
  const t = h('div', { class: 'toast ' + kind, role: 'status' }, msg); document.getElementById('toasts').append(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, ms);
}
export function modal(title, body, { actions = [], wide = false, onClose } = {}) {
  const root = document.getElementById('modal-root');
  const close = () => { back.remove(); document.removeEventListener('keydown', esc_); onClose && onClose(); };
  const esc_ = (e) => { if (e.key === 'Escape') close(); };
  const box = h('div', { class: 'modal' + (wide ? ' wide' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
    h('div', { class: 'modal-h' }, h('h3', null, title), h('button', { class: 'icon-btn', 'aria-label': 'Close', onclick: close }, '✕')),
    h('div', { class: 'modal-b' }, body),
    actions.length ? h('div', { class: 'modal-f' }, actions.map((a) => h('button', { class: 'btn ' + (a.kind || ''), onclick: async (e) => { const b = e.currentTarget; b.disabled = true; try { const r = await a.run(close); if (r !== false && a.close !== false) close(); } catch (er) { toast(er.message, 'err'); } finally { b.disabled = false; } } }, a.label))) : null);
  const back = h('div', { class: 'modal-back', onclick: (e) => e.target === back && close() }, box);
  root.append(back); document.addEventListener('keydown', esc_);
  const f = box.querySelector('input,select,textarea'); f && f.focus();
  return { close, box };
}

// ---- field editor (input control by column type) ----
export function fieldInput(col, value, onChange, { id } = {}) {
  const set = (v) => onChange(v);
  if (col.type === 'select' || (col.options && col.options.length)) {
    const s = h('select', { id, onchange: (e) => set(e.target.value === '' ? '' : coerce(e.target.value, col.options)) }, h('option', { value: '' }, '—'), ...col.options.map((o) => h('option', { value: o, selected: String(o) === String(value) }, o)));
    return s;
  }
  if (col.type === 'date') return h('input', { id, type: 'date', value: typeof value === 'number' ? serialToISO(value) : '', onchange: (e) => set(e.target.value ? isoToSerial(e.target.value) : '') });
  if (col.type === 'number' || col.type === 'pct') return h('input', { id, type: 'number', step: 'any', value: value ?? '', onchange: (e) => set(e.target.value === '' ? '' : +e.target.value) });
  const long = /summary|thesis|notes|rationale|memo|source|reason|findings|action|description/i.test(col.label);
  return long ? h('textarea', { id, rows: 3, onchange: (e) => set(e.target.value) }, value ?? '') : h('input', { id, type: 'text', value: value ?? '', onchange: (e) => set(e.target.value) });
}
const coerce = (v, opts) => { const m = opts.find((o) => String(o) === v); return m === undefined ? v : m; };

export function linkify(text) {
  const frag = document.createDocumentFragment(); const s = String(text ?? ''); let last = 0;
  for (const m of s.matchAll(/https?:\/\/[^\s|)]+/g)) {
    frag.append(s.slice(last, m.index)); frag.append(h('a', { href: m[0], target: '_blank', rel: 'noopener noreferrer' }, m[0].replace(/^https?:\/\/(www\.)?/, '').slice(0, 48) + (m[0].length > 60 ? '…' : ''))); last = m.index + m[0].length;
  }
  frag.append(s.slice(last)); return frag;
}
export const debounce = (fn, ms = 200) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const csvEscape = (v) => { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
export function download(name, text, type = 'text/csv') { const a = h('a', { href: URL.createObjectURL(new Blob([text], { type })), download: name }); document.body.append(a); a.click(); a.remove(); }
