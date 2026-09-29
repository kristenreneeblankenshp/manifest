'use strict';
// Surgical writer: patches individual <c> cells inside the original .xlsx package so that
// charts, styles, conditional formats and data validations are preserved byte-for-byte.
const fs = require('fs');
const JSZip = require('jszip');

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const colToNum = (c) => c.split('').reduce((n, ch) => n * 26 + ch.charCodeAt(0) - 64, 0);
const splitAddr = (a) => { const m = /^([A-Z]+)(\d+)$/.exec(a); return { col: m[1], row: +m[2] }; };

class XlsxPackage {
  constructor(zip, file) { this.zip = zip; this.file = file; this.sheetParts = {}; this.xml = {}; this.dirty = new Set(); }

  static async open(file) {
    const zip = await JSZip.loadAsync(fs.readFileSync(file));
    const pkg = new XlsxPackage(zip, file);
    await pkg.indexSheets();
    return pkg;
  }

  async indexSheets() {
    const wb = (await this.zip.file('xl/workbook.xml').async('string')).replace(/^﻿/, '');
    const rels = (await this.zip.file('xl/_rels/workbook.xml.rels').async('string')).replace(/^﻿/, '');
    const relMap = {};
    for (const m of rels.matchAll(/<Relationship\b[^>]*>/g)) {
      const id = /Id="([^"]+)"/.exec(m[0]); const t = /Target="([^"]+)"/.exec(m[0]);
      if (id && t) relMap[id[1]] = t[1].replace(/^\//, '').replace(/^(?!xl\/)/, 'xl/');
    }
    this.sheetParts = {};
    for (const m of wb.matchAll(/<(?:\w+:)?sheet\b[^>]*>/g)) {
      const name = /name="([^"]*)"/.exec(m[0]); const rid = /r:id="([^"]+)"/.exec(m[0]);
      if (name && rid) this.sheetParts[name[1].replace(/&amp;/g, '&')] = relMap[rid[1]];
    }
  }

  async sheetXml(name) {
    const part = this.sheetParts[name];
    if (!(part in this.xml)) this.xml[part] = (await this.zip.file(part).async('string')).replace(/^﻿/, '');
    return part;
  }

  prefix(xml) { const m = /<(\w+:)?worksheet\b/.exec(xml); return m && m[1] ? m[1] : ''; }

  /** edits: [{addr, kind:'const'|'cache', value}] for a single sheet */
  async patch(name, edits) {
    const part = await this.sheetXml(name);
    let xml = this.xml[part];
    const p = this.prefix(xml);
    const T = (t) => `<${p}${t}`;
    // group edits by row
    const byRow = new Map();
    for (const e of edits) { const { row } = splitAddr(e.addr); if (!byRow.has(row)) byRow.set(row, []); byRow.get(row).push(e); }
    for (const [row, list] of [...byRow.entries()].sort((a, b) => a[0] - b[0])) {
      let loc = this.findRow(xml, p, row);
      if (!loc) { xml = this.insertRow(xml, p, row); loc = this.findRow(xml, p, row); }
      let rowXml = xml.slice(loc.start, loc.end);
      for (const e of list) rowXml = this.patchCell(rowXml, p, e, xml, row);
      xml = xml.slice(0, loc.start) + rowXml + xml.slice(loc.end);
    }
    this.xml[part] = xml; this.dirty.add(part);
  }

  findRow(xml, p, row) {
    const re = new RegExp(`<${p}row r="${row}"(?=[\\s>/])[^>]*?(/>|>)`);
    const m = re.exec(xml); if (!m) return null;
    const start = m.index;
    if (m[1] === '/>') return { start, end: start + m[0].length, selfClosing: true };
    const close = `</${p}row>`; const end = xml.indexOf(close, start) + close.length;
    return { start, end };
  }

  insertRow(xml, p, row) {
    // find the first existing row with a larger index; insert before it, else before </sheetData>
    const re = new RegExp(`<${p}row r="(\\d+)"`, 'g'); let m; let at = -1;
    while ((m = re.exec(xml))) { if (+m[1] > row) { at = m.index; break; } }
    if (at < 0) { const c = xml.indexOf(`</${p}sheetData>`); if (c >= 0) at = c; else { // <sheetData/>
      const sd = new RegExp(`<${p}sheetData\\s*/>`).exec(xml); xml = xml.replace(sd[0], `<${p}sheetData></${p}sheetData>`); at = xml.indexOf(`</${p}sheetData>`); } }
    return xml.slice(0, at) + `<${p}row r="${row}"></${p}row>` + xml.slice(at);
  }

  patchCell(rowXml, p, e, fullXml, row) {
    const { col } = splitAddr(e.addr);
    const cre = new RegExp(`<${p}c r="${e.addr}"(?=[\\s>/])[^>]*?(?:/>|>[\\s\\S]*?</${p}c>)`);
    const m = cre.exec(rowXml);
    let style = null; let fPart = '';
    if (m) {
      const s = /\ss="(\d+)"/.exec(m[0].slice(0, m[0].indexOf('>') + 1)); if (s) style = s[1];
      const f = new RegExp(`<${p}f\\b[^>]*?(?:/>|>[\\s\\S]*?</${p}f>)`).exec(m[0]); if (f) fPart = f[0];
    } else {
      style = this.neighbourStyle(fullXml, p, col, row);
    }
    const sAttr = style != null ? ` s="${style}"` : '';
    let cell;
    const v = e.value;
    if (e.kind === 'cache' || fPart) {
      if (!fPart) return rowXml; // cache update for a non-formula cell: ignore
      if (v === null || v === undefined || v === '') cell = `<${p}c r="${e.addr}"${sAttr} t="str">${fPart}</${p}c>`;
      else if (typeof v === 'number') cell = `<${p}c r="${e.addr}"${sAttr} t="n">${fPart}<${p}v>${v}</${p}v></${p}c>`;
      else if (typeof v === 'boolean') cell = `<${p}c r="${e.addr}"${sAttr} t="b">${fPart}<${p}v>${v ? 1 : 0}</${p}v></${p}c>`;
      else if (typeof v === 'object' && v.error) cell = `<${p}c r="${e.addr}"${sAttr} t="e">${fPart}<${p}v>${esc(v.error)}</${p}v></${p}c>`;
      else cell = `<${p}c r="${e.addr}"${sAttr} t="str">${fPart}<${p}v>${esc(v)}</${p}v></${p}c>`;
    } else if (v === null || v === undefined || v === '') cell = `<${p}c r="${e.addr}"${sAttr} />`;
    else if (typeof v === 'number') cell = `<${p}c r="${e.addr}"${sAttr} t="n"><${p}v>${v}</${p}v></${p}c>`;
    else if (typeof v === 'boolean') cell = `<${p}c r="${e.addr}"${sAttr} t="b"><${p}v>${v ? 1 : 0}</${p}v></${p}c>`;
    else cell = `<${p}c r="${e.addr}"${sAttr} t="inlineStr"><${p}is><${p}t xml:space="preserve">${esc(v)}</${p}t></${p}is></${p}c>`;

    if (m) return rowXml.slice(0, m.index) + cell + rowXml.slice(m.index + m[0].length);
    // insert new cell in column order
    const open = new RegExp(`^<${p}row\\b[^>]*?>`).exec(rowXml)[0];
    let inner = rowXml.slice(open.length, rowXml.length - `</${p}row>`.length);
    const target = colToNum(col); let pos = inner.length;
    const cellRe = new RegExp(`<${p}c r="([A-Z]+)\\d+"`, 'g'); let cm;
    while ((cm = cellRe.exec(inner))) { if (colToNum(cm[1]) > target) { pos = cm.index; break; } }
    inner = inner.slice(0, pos) + cell + inner.slice(pos);
    const openFixed = open.endsWith('/>') ? open.replace(/\/>$/, '>') : open;
    return openFixed + inner + `</${p}row>`;
  }

  neighbourStyle(xml, p, col, row) {
    for (const d of [-1, 1, -2, 2]) {
      const m = new RegExp(`<${p}c r="${col}${row + d}"[^>]*?\\ss="(\\d+)"`).exec(xml);
      if (m) return m[1];
    }
    return null;
  }

  /** register a brand-new worksheet (used for the app audit log) */
  async addSheet(name, sheetXml) {
    const idx = Object.keys(this.sheetParts).length + 1;
    const part = `xl/worksheets/sheet${idx + 100}.xml`;
    const rid = 'RappAudit' + idx;
    let wb = (await this.zip.file('xl/workbook.xml').async('string')).replace(/^﻿/, '');
    const p = (/<(\w+:)?workbook\b/.exec(wb) || [])[1] || '';
    const ids = [...wb.matchAll(/sheetId="(\d+)"/g)].map((m) => +m[1]);
    const el = `<${p}sheet name="${esc(name)}" sheetId="${Math.max(...ids) + 1}" r:id="${rid}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" />`;
    wb = wb.replace(`</${p}sheets>`, el + `</${p}sheets>`);
    if (/<(\w+:)?calcPr\b/.test(wb)) wb = wb.replace(/<((?:\w+:)?)calcPr\b([^>]*?)\/>/, (m, pp, a) => `<${pp}calcPr${a.replace(/\sfullCalcOnLoad="[^"]*"/, '')} fullCalcOnLoad="1" />`);
    else wb = wb.replace(`</${p}workbook>`, `<${p}calcPr fullCalcOnLoad="1" /></${p}workbook>`);
    this.zip.file('xl/workbook.xml', wb);
    let rels = (await this.zip.file('xl/_rels/workbook.xml.rels').async('string')).replace(/^﻿/, '');
    rels = rels.replace('</Relationships>', `<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/${part}" Id="${rid}" /></Relationships>`);
    this.zip.file('xl/_rels/workbook.xml.rels', rels);
    let ct = (await this.zip.file('[Content_Types].xml').async('string')).replace(/^﻿/, '');
    ct = ct.replace('</Types>', `<Override PartName="/${part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" /></Types>`);
    this.zip.file('[Content_Types].xml', ct);
    this.zip.file(part, sheetXml);
    this.sheetParts[name] = part; this.xml[part] = sheetXml;
  }

  async ensureFullCalcOnLoad() {
    let wb = (await this.zip.file('xl/workbook.xml').async('string')).replace(/^﻿/, '');
    if (/fullCalcOnLoad="1"/.test(wb)) return;
    const p = (/<(\w+:)?workbook\b/.exec(wb) || [])[1] || '';
    if (/<(\w+:)?calcPr\b/.test(wb)) wb = wb.replace(/<((?:\w+:)?)calcPr\b([^>]*?)\/>/, (m, pp, a) => `<${pp}calcPr${a} fullCalcOnLoad="1" />`);
    else wb = wb.replace(`</${p}workbook>`, `<${p}calcPr fullCalcOnLoad="1" /></${p}workbook>`);
    this.zip.file('xl/workbook.xml', wb); this.wbDirty = true;
  }

  async save(file = this.file) {
    for (const part of this.dirty) this.zip.file(part, this.xml[part]);
    this.dirty.clear();
    const buf = await this.zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
    const tmp = file + '.tmp'; fs.writeFileSync(tmp, buf); fs.renameSync(tmp, file);
  }
}

module.exports = { XlsxPackage, colToNum, splitAddr };
