'use strict';
// Workbook engine: the .xlsx file is the single source of truth.
//  - reads values/formulas (SheetJS) and styles/layout (own parser, file uses x: prefixed OOXML)
//  - recalculates with HyperFormula after each edit
//  - writes edits + refreshed cached values back into the original package (see xlsxpatch.js)
const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');
const { HyperFormula, FunctionPlugin } = require('hyperformula');
const { XMLParser } = require('fast-xml-parser');
const { XlsxPackage, colToNum } = require('./xlsxpatch');


const AUDIT_SHEET = '25 App Audit Log';
const AUDIT_HEADERS = ['Timestamp (UTC)', 'User', 'Action', 'Sheet', 'Cell', 'Field', 'Previous Value', 'New Value', 'Record', 'Note'];

const colName = (n) => { let s = ''; n += 1; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = ((n - 1) / 26) | 0; } return s; };
const addrOf = (r, c) => colName(c) + (r + 1);
const parseAddr = (a) => { const m = /^([A-Z]+)(\d+)$/.exec(a); return { c: colToNum(m[1]) - 1, r: +m[2] - 1 }; };

// ---------- Excel serial dates / TEXT() ----------
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const serialToDate = (n) => new Date(Math.round((n - 25569) * 86400000));
function formatDateSerial(n, fmt) {
  const d = serialToDate(n);
  const Y = d.getUTCFullYear(), M = d.getUTCMonth(), D = d.getUTCDate(), W = d.getUTCDay();
  return fmt.replace(/yyyy|yy|mmmm|mmm|mm|m|dddd|ddd|dd|d/gi, (t) => {
    switch (t.toLowerCase()) {
      case 'yyyy': return String(Y); case 'yy': return String(Y).slice(2);
      case 'mmmm': return MONTHS[M]; case 'mmm': return MONTHS[M].slice(0, 3);
      case 'mm': return String(M + 1).padStart(2, '0'); case 'm': return String(M + 1);
      case 'dddd': return DAYS[W]; case 'ddd': return DAYS[W].slice(0, 3);
      case 'dd': return String(D).padStart(2, '0'); default: return String(D);
    }
  });
}
function excelText(v, fmt) {
  if (typeof v !== 'number') return v == null ? '' : String(v);
  if (/[dmy]/i.test(fmt.replace(/"[^"]*"/g, ''))) return formatDateSerial(v, fmt);
  if (/%/.test(fmt)) { const dec = (/\.(0+)/.exec(fmt) || [, ''])[1].length; return (v * 100).toFixed(dec) + '%'; }
  const dec = (/\.(0+)/.exec(fmt) || [, ''])[1].length; let s = Math.abs(v).toFixed(dec);
  if (/,/.test(fmt)) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return (v < 0 ? '-' : '') + s;
}

class ExtraFunctions extends FunctionPlugin {
  xtext(ast, state) {
    return this.runFunction(ast.args, state, this.metadata('XTEXT'), (v, f) => excelText(v, f));
  }
  rank(ast, state) {
    return this.runFunction(ast.args, state, this.metadata('RANK'), (num, range, order) => {
      const vals = range.valuesFromTopLeftCorner().flat().filter((x) => typeof x === 'number');
      if (!vals.includes(num)) return new (require('hyperformula').CellError)('NA');
      return 1 + vals.filter((x) => (order ? x < num : x > num)).length;
    });
  }
}
ExtraFunctions.implementedFunctions = {
  XTEXT: { method: 'xtext', parameters: [{ argumentType: 'ANY' }, { argumentType: 'STRING' }] },
  RANK: { method: 'rank', parameters: [{ argumentType: 'NUMBER' }, { argumentType: 'RANGE' }, { argumentType: 'NUMBER', optionalArg: true, defaultValue: 0 }] },
};
HyperFormula.registerFunctionPlugin(ExtraFunctions, { enGB: { XTEXT: 'XTEXT', RANK: 'RANK' } });
const PURE_REF = /^(?:'[^']+'|[A-Za-z0-9_]+)?!?\$?[A-Z]{1,3}\$?\d+$/;
// Excel evaluates a bare reference to an empty cell as 0; HyperFormula returns empty.
const toHF = (f) => (PURE_REF.test(f) && f.includes('!') ? `=IF(ISBLANK(${f}),0,${f})` : '=' + f.replace(/\bTEXT\(/g, 'XTEXT('));

// ---------- styles ----------
const xp = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@', removeNSPrefix: true, isArray: (n) => ['xf', 'font', 'fill', 'border', 'numFmt'].includes(n) });
const argb = (c) => (c && c['@rgb'] ? '#' + c['@rgb'].slice(2) : null);
function parseStyles(xml) {
  const s = xp.parse(xml).styleSheet;
  const fmts = {}; for (const n of s.numFmts?.numFmt || []) fmts[n['@numFmtId']] = n['@formatCode'];
  const builtin = { 9: '0%', 10: '0.00%', 14: 'm/d/yyyy', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00' };
  const fonts = s.fonts.font, fills = s.fills.fill, borders = s.borders.border;
  const bd = (b) => (b && b['@style'] ? argb(b.color) || '#9aa4b2' : null);
  return (s.cellXfs.xf || []).map((x) => {
    const f = fonts[x['@fontId'] || 0] || {}, fl = fills[x['@fillId'] || 0] || {}, b = borders[x['@borderId'] || 0] || {};
    const al = x.alignment || {};
    const o = {};
    const bg = fl.patternFill && fl.patternFill['@patternType'] === 'solid' ? argb(fl.patternFill.fgColor) : null;
    if (bg) o.bg = bg;
    const fg = argb(f.color); if (fg) o.fg = fg;
    if (f.b !== undefined) o.b = 1; if (f.i !== undefined) o.i = 1;
    if (f.sz) o.sz = +f.sz['@val'];
    if (al['@horizontal']) o.ha = al['@horizontal']; if (al['@vertical']) o.va = al['@vertical']; if (al['@wrapText']) o.wrap = 1;
    const bt = bd(b.top), br = bd(b.right), bb = bd(b.bottom), bl = bd(b.left);
    if (bt || br || bb || bl) o.bd = [bt, br, bb, bl];
    const id = x['@numFmtId'] || 0; const code = fmts[id] || builtin[id]; if (code) o.fmt = code;
    return o;
  });
}

function parseSheetLayout(xml) {
  xml = xml.replace(/^﻿/, '');
  const cols = []; for (const m of xml.matchAll(/<(?:\w+:)?col\b([^>]*)\/?>/g)) {
    const a = m[1]; const g = (k) => (new RegExp(`\\b${k}="([^"]*)"`).exec(a) || [])[1];
    cols.push({ min: +g('min'), max: +g('max'), w: +g('width'), hidden: g('hidden') === '1' });
  }
  const rows = {}; for (const m of xml.matchAll(/<(?:\w+:)?row\b([^>]*?)\/?>/g)) {
    const r = /\br="(\d+)"/.exec(m[1]); const h = /\bht="([\d.]+)"/.exec(m[1]); const hid = /\bhidden="1"/.test(m[1]);
    if (r && (h || hid)) rows[r[1]] = { h: h ? +h[1] : undefined, hidden: hid || undefined };
  }
  const merges = [...xml.matchAll(/<(?:\w+:)?mergeCell\b[^>]*ref="([^"]+)"/g)].map((m) => m[1]);
  const styles = {}; for (const m of xml.matchAll(/<(?:\w+:)?c r="([A-Z]+\d+)"[^>]*?\ss="(\d+)"/g)) styles[m[1]] = +m[2];
  const pane = /<(?:\w+:)?pane\b([^>]*)>/.exec(xml); let freeze = null;
  if (pane) { const x = /xSplit="(\d+)"/.exec(pane[1]); const y = /ySplit="(\d+)"/.exec(pane[1]); freeze = { x: x ? +x[1] : 0, y: y ? +y[1] : 0 }; }
  const dv = []; for (const m of xml.matchAll(/<(?:\w+:)?dataValidation\b([^>]*)>\s*<(?:\w+:)?formula1>([\s\S]*?)<\/(?:\w+:)?formula1>/g)) {
    const sq = /sqref="([^"]+)"/.exec(m[1]); const ty = /type="([^"]+)"/.exec(m[1]);
    if (sq) dv.push({ sqref: sq[1], type: ty && ty[1], f: m[2].replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>') });
  }
  return { cols, rows, merges, styles, freeze, dv };
}

class Engine {
  constructor(file) { this.file = file; this.queue = Promise.resolve(); this.version = 0; }

  async init() {
    this.pkg = await XlsxPackage.open(this.file);
    if (!this.pkg.sheetParts[AUDIT_SHEET]) await this.createAuditSheet();
    await this.pkg.ensureFullCalcOnLoad(); await this.pkg.save();
    await this.load();
    await this.refreshCaches();
    this.day = Math.floor(Date.now() / 86400000);
    this.dayTimer = setInterval(() => { const d = Math.floor(Date.now() / 86400000); if (d !== this.day) { this.day = d; this.run(async () => { this.hf.rebuildAndRecalculate(); await this.refreshCaches(); this.version++; }); } }, 600000);
    this.dayTimer.unref();
  }

  /** Bring the cached values stored in the .xlsx in line with the live recalculation (TODAY() drift, engine differences). */
  async refreshCaches() {
    const edits = {};
    for (const n of this.names) for (const [a, cv] of Object.entries(this.cached[n] || {})) {
      const v = this.cellValue(n, a); const x = v && v.err ? v.err : v; const y = cv == null ? '' : cv; const z = x == null ? '' : x;
      const same = typeof y === 'number' && typeof z === 'number' ? Math.abs(y - z) < 1e-9 : String(y) === String(z);
      if (!same) (edits[n] = edits[n] || []).push({ addr: a, kind: 'cache', value: v && v.err ? { error: v.err } : v });
      this.cached[n][a] = x;
    }
    let count = 0; for (const [n, list] of Object.entries(edits)) { await this.pkg.patch(n, list); count += list.length; }
    if (count) { await this.pkg.save(); console.log(`Refreshed ${count} stale cached values in workbook`); }
  }

  async createAuditSheet() {
    const p = this.pkg.prefix(await this.pkg.zip.file(this.pkg.sheetParts['24 RCC-004 Candidate Pipeline']).async('string'));
    const hdr = AUDIT_HEADERS.map((h, i) => `<${p}c r="${colName(i)}1" t="inlineStr"><${p}is><${p}t>${h}</${p}t></${p}is></${p}c>`).join('');
    const cols = [22, 18, 26, 30, 10, 30, 40, 40, 22, 50].map((w, i) => `<${p}col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1" />`).join('');
    const xml = `<?xml version="1.0" encoding="utf-8"?><${p}worksheet xmlns${p ? ':' + p.slice(0, -1) : ''}="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><${p}cols>${cols}</${p}cols><${p}sheetData><${p}row r="1">${hdr}</${p}row></${p}sheetData></${p}worksheet>`;
    await this.pkg.addSheet(AUDIT_SHEET, xml);
  }

  async load() {
    const buf = fs.readFileSync(this.file);
    const wb = XLSX.read(buf, { type: 'buffer', cellFormula: true, cellDates: false, cellNF: true });
    this.names = wb.SheetNames.slice();
    const data = {}; this.cached = {}; this.numfmt = {};
    for (const n of this.names) {
      const ws = wb.Sheets[n]; const arr = []; this.cached[n] = {};
      if (ws['!ref']) {
        const ref = XLSX.utils.decode_range(ws['!ref']);
        for (let r = 0; r <= ref.e.r; r++) { arr[r] = []; for (let c = 0; c <= ref.e.c; c++) {
          const cell = ws[XLSX.utils.encode_cell({ r, c })];
          if (!cell) { arr[r][c] = null; continue; }
          if (cell.f) { arr[r][c] = toHF(cell.f); this.cached[n][addrOf(r, c)] = cell.v; } else arr[r][c] = cell.v === undefined ? null : cell.v;
        } }
      }
      data[n] = arr;
    }
    this.hf = HyperFormula.buildFromSheets(data, { licenseKey: 'gpl-v3', useColumnIndex: false, useArrayArithmetic: true });
    this.stylesTbl = parseStyles((await this.pkg.zip.file('xl/styles.xml').async('string')).replace(/^﻿/, ''));
    this.layout = {};
    for (const n of this.names) {
      const part = await this.pkg.sheetXml(n); this.layout[n] = parseSheetLayout(this.pkg.xml[part]);
    }
    // keep a copy of raw formulas (Excel syntax) for display
    this.formulas = {};
    for (const n of this.names) {
      this.formulas[n] = {}; const ws = wb.Sheets[n];
      for (const k of Object.keys(ws)) if (k[0] !== '!' && ws[k].f) this.formulas[n][k] = ws[k].f;
    }
    this.sid = (n) => this.hf.getSheetId(n);
  }

  // ---- reading ----
  cellValue(sheet, addr) {
    const { r, c } = parseAddr(addr); const v = this.hf.getCellValue({ sheet: this.sid(sheet), row: r, col: c });
    return this.norm(v);
  }
  norm(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === 'object') return { err: v.value || String(v.type) };
    return v;
  }
  isFormula(sheet, addr) { return !!this.formulas[sheet][addr]; }

  sheetPayload(name) {
    const L = this.layout[name]; const id = this.sid(name);
    const dims = this.hf.getSheetDimensions(id);
    const used = new Map(); const cells = [];
    const rowsN = dims.height, colsN = dims.width;
    for (let r = 0; r < rowsN; r++) for (let c = 0; c < colsN; c++) {
      const a = addrOf(r, c); const v = this.norm(this.hf.getCellValue({ sheet: id, row: r, col: c }));
      const s = L.styles[a]; const f = this.formulas[name][a];
      if (v === null && f === undefined && s === undefined) continue;
      if (s !== undefined && !used.has(s)) used.set(s, this.stylesTbl[s] || {});
      const row = [r, c, v]; row.push(s === undefined ? 0 : s); if (f) row.push(f);
      cells.push(row);
    }
    const styles = {}; for (const [k, v] of used) styles[k] = v;
    const dv = this.resolveValidations(name);
    return { name, rows: rowsN, cols: colsN, cells, styles, colWidths: L.cols, rowHeights: L.rows, merges: L.merges, freeze: L.freeze, dv, version: this.version };
  }

  resolveValidations(name) {
    const out = [];
    for (const d of this.layout[name].dv) {
      let list = null;
      if (d.type === 'list') {
        if (d.f.startsWith('"')) list = d.f.replace(/^"|"$/g, '').split(',');
        else list = this.rangeList(d.f);
      }
      if (list) out.push({ sqref: d.sqref, list });
    }
    return out;
  }
  rangeList(ref) {
    const m = /^'?([^'!]+)'?!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$/.exec(ref); if (!m) return null;
    const [, sh, c1, r1, c2, r2] = m; const a = parseAddr(c1 + r1), b = parseAddr((c2 || c1) + (r2 || r1)); const out = [];
    for (let r = a.r; r <= b.r; r++) for (let c = a.c; c <= b.c; c++) { const v = this.hf.getCellValue({ sheet: this.sid(sh), row: r, col: c }); if (v !== null && v !== '' && typeof v !== 'object') out.push(v); }
    return out;
  }
  validationFor(sheet, addr) {
    const { r, c } = parseAddr(addr);
    for (const d of this.layout[sheet].dv) for (const part of d.sqref.split(' ')) {
      const [s, e] = part.split(':'); const A = parseAddr(s), B = parseAddr(e || s);
      if (r >= A.r && r <= B.r && c >= A.c && c <= B.c) {
        if (d.type !== 'list') return null;
        return d.f.startsWith('"') ? d.f.replace(/^"|"$/g, '').split(',') : this.rangeList(d.f);
      }
    }
    return null;
  }

  // ---- writing ----
  /** Apply constant-cell edits. changes: [{sheet, addr, value}]. Returns {changed, error?}. */
  applyEdits(changes, { validate = true } = {}) {
    const before = new Map(); const snap = (sh, a) => { const k = sh + '!' + a; if (!before.has(k)) before.set(k, this.cellValue(sh, a)); };
    for (const ch of changes) {
      if (this.isFormula(ch.sheet, ch.addr)) throw new Error(`${ch.sheet}!${ch.addr} is a formula cell (calculated by the workbook) and cannot be overwritten.`);
      if (validate && ch.value !== null && ch.value !== '') {
        const list = this.validationFor(ch.sheet, ch.addr);
        if (list && !list.map(String).includes(String(ch.value))) throw new Error(`"${ch.value}" is not an allowed value for ${ch.sheet}!${ch.addr}.`);
      }
    }
    // collect every current value (for diffing after recalculation)
    const watched = this.snapshotAll();
    const stash = changes.map((ch) => ({ ch, old: this.rawConst(ch.sheet, ch.addr) }));
    this.hf.batch(() => { for (const ch of changes) { const { r, c } = parseAddr(ch.addr); this.hf.setCellContents({ sheet: this.sid(ch.sheet), row: r, col: c }, [[ch.value === '' ? null : ch.value]]); } });
    for (const ch of changes) delete this.cached[ch.sheet]?.[ch.addr];
    const diff = this.diffAll(watched);
    return { diff, stash };
  }
  rawConst(sheet, addr) { const { r, c } = parseAddr(addr); const v = this.hf.getCellSerialized({ sheet: this.sid(sheet), row: r, col: c }); return v === undefined ? null : v; }

  snapshotAll() {
    const snap = {};
    for (const n of this.names) { snap[n] = this.hf.getSheetValues(this.sid(n)).map((row) => row.map((v) => (v && typeof v === 'object' ? 'ERR:' + (v.value || v.type) : v))); }
    return snap;
  }
  diffAll(before) {
    const diff = [];
    for (const n of this.names) {
      const now = this.hf.getSheetValues(this.sid(n)); const old = before[n];
      for (let r = 0; r < Math.max(now.length, old.length); r++) {
        const a = now[r] || [], b = old[r] || [];
        for (let c = 0; c < Math.max(a.length, b.length); c++) {
          let x = a[c]; if (x && typeof x === 'object') x = 'ERR:' + (x.value || x.type);
          const y = b[c];
          if (x !== y && !(x == null && y == null) && !(x === '' && y == null) && !(x == null && y === '')) diff.push({ sheet: n, addr: addrOf(r, c), value: this.norm(a[c]) });
        }
      }
    }
    return diff;
  }

  /** run a function that may edit, and persist edits + recalculated caches */
  async commit(edits, diff, audit) {
    const bySheet = {};
    const push = (sh, e) => (bySheet[sh] = bySheet[sh] || []).push(e);
    for (const e of edits) push(e.sheet, { addr: e.addr, kind: 'const', value: e.value === '' ? null : e.value });
    const editKeys = new Set(edits.map((e) => e.sheet + '!' + e.addr));
    for (const d of diff) {
      if (editKeys.has(d.sheet + '!' + d.addr)) continue;
      if (!this.isFormula(d.sheet, d.addr)) continue;
      const v = d.value && d.value.err ? { error: d.value.err } : d.value;
      push(d.sheet, { addr: d.addr, kind: 'cache', value: v });
    }
    for (const [sh, list] of Object.entries(bySheet)) await this.pkg.patch(sh, list);
    if (audit && audit.length) await this.writeAudit(audit);
    this.version++;
    this.scheduleSave();
  }

  async writeAudit(rows) {
    const id = this.sid(AUDIT_SHEET); let next = this.hf.getSheetDimensions(id).height; // zero-based row index of new row
    const edits = [];
    for (const row of rows) { row.forEach((v, i) => edits.push({ sheet: AUDIT_SHEET, addr: colName(i) + (next + 1), kind: 'const', value: v })); next++; }
    this.hf.batch(() => { for (const e of edits) { const { r, c } = parseAddr(e.addr); this.hf.setCellContents({ sheet: id, row: r, col: c }, [[e.value === '' ? null : e.value]]); } });
    await this.pkg.patch(AUDIT_SHEET, edits.map((e) => ({ addr: e.addr, kind: 'const', value: e.value })));
  }

  scheduleSave() {
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.flush(), 300);
  }
  flush() { this.queue = this.queue.then(() => this.pkg.save()).catch((e) => console.error('save failed', e)); return this.queue; }

  /** serialise all mutations */
  run(fn) { const p = this.mut = (this.mut || Promise.resolve()).then(fn, fn); this.mut = p.catch(() => {}); return p; }

  /** edit with audit (serialised) */
  edit(changes, meta = {}) { return this.run(() => this._edit(changes, meta)); }
  async _edit(changes, { user = 'unknown', action = 'Edit', record = '', note = '' } = {}) {
    const { diff, stash } = this.applyEdits(changes);
    const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const audit = stash.filter(({ ch, old }) => String(old ?? '') !== String(ch.value ?? '')).map(({ ch, old }) => [ts, user, action, ch.sheet, ch.addr, this.fieldName(ch.sheet, ch.addr), old == null ? '' : String(old), ch.value == null ? '' : String(ch.value), record, note]);
    await this.commit(changes, diff, audit);
    return { diff, version: this.version };
  }
  fieldName(sheet, addr) {
    const { c, r } = parseAddr(addr);
    for (const hr of [12, 11, 3, 4]) { const v = this.hf.getCellValue({ sheet: this.sid(sheet), row: hr, col: c }); if (v && typeof v === 'string' && r > hr) return v.replace(/\s*\((Input|Auto)\)$/, ''); }
    return addr;
  }

  /** Apply edits, run probe(), then always restore the previous values (dry run for gated actions). Not serialised: call inside run(). */
  _trial(changes, probe) {
    const prev = changes.map((ch) => ({ sheet: ch.sheet, addr: ch.addr, value: this.rawConst(ch.sheet, ch.addr) }));
    this.applyEdits(changes);
    try { return probe(); } finally { this.applyEdits(prev, { validate: false }); }
  }
}

module.exports = { Engine, AUDIT_SHEET, colName, addrOf, parseAddr, formatDateSerial };
