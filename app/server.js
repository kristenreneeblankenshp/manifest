'use strict';
const express = require('express');
const compression = require('compression');
const fs = require('fs');
const path = require('path');
const { Engine, AUDIT_SHEET } = require('./lib/engine');
const { TABLES, S, buildMeta, tableRows } = require('./lib/tables');
const makeActions = require('./lib/actions');

const DATA = process.env.DATA_DIR || path.join(__dirname, 'data');
const FILE = path.join(DATA, 'workbook.xlsx');
const BACKUPS = path.join(DATA, 'snapshots');
const PORT = process.env.PORT || 3000;

(async () => {
  fs.mkdirSync(BACKUPS, { recursive: true });
  if (!fs.existsSync(FILE)) fs.copyFileSync(path.join(DATA, 'original.xlsx'), FILE);
  let engine = new Engine(FILE); await engine.init();
  let actions = makeActions(engine);
  const metaCache = {};
  const tableMeta = (k) => (metaCache[k] = metaCache[k] || buildMeta(engine, k));

  const app = express();
  app.use(compression()); app.use(express.json({ limit: '4mb' }));
  app.use(express.static(path.join(__dirname, 'public')));
  app.use('/mwir', express.static(path.join(__dirname, '..', 'mwir'))); // MWIR report builder
  const wrap = (fn) => async (req, res) => { try { res.json(await fn(req)); } catch (e) { console.error(e.message); res.status(e.extra || /Required|not an allowed|formula cell|not found|already|full|no free|Unknown|Must|Nothing|Stage/i.test(e.message) ? 400 : 500).json({ error: e.message }); } };
  const today = () => Math.floor(Date.now() / 86400000) + 25569;

  app.get('/api/meta', wrap(async () => ({
    version: engine.version, today: today(), audit: AUDIT_SHEET,
    sheets: engine.names.map((n) => ({ name: n, rows: engine.hf.getSheetDimensions(engine.sid(n)).height, cols: engine.hf.getSheetDimensions(engine.sid(n)).width })),
    tables: Object.fromEntries(Object.keys(TABLES).map((k) => [k, tableMeta(k)])),
    lists: engine.names.includes('97 RCC Lists') ? true : false,
  })));
  app.get('/api/version', (req, res) => res.json({ version: engine.version }));
  app.get('/api/sheet/:name', wrap(async (req) => { if (!engine.names.includes(req.params.name)) throw new Error('Sheet not found'); return engine.sheetPayload(req.params.name); }));
  app.get('/api/table/:key', wrap(async (req) => { if (!TABLES[req.params.key]) throw new Error('Table not found'); const m = tableMeta(req.params.key); return { meta: m, rows: tableRows(engine, req.params.key, m), version: engine.version }; }));

  // Security 360: everything the workbook knows about one ticker, across registries
  app.get('/api/security/:ticker', wrap(async (req) => {
    const t = req.params.ticker.toUpperCase(); const out = { ticker: t, version: engine.version, sections: {} };
    for (const k of ['registry', 'miar', 'pipeline', 'evidence', 'reviews', 'compare']) {
      const m = tableMeta(k); const rows = tableRows(engine, k, m).filter((r) => String(r.v[TABLES[k].tickerCol] || '').toUpperCase() === t);
      out.sections[k] = { meta: { key: k, title: m.title, sheet: m.sheet, idCol: m.idCol, titleCol: m.titleCol, statusCol: m.statusCol, actionCol: m.actionCol, listCols: m.listCols, cols: m.cols }, rows };
    }
    const sh = 'Certified Allocation'; const dims = engine.hf.getSheetDimensions(engine.sid(sh)); const hdr = {};
    for (let c = 0; c < dims.width; c++) { const h = engine.cellValue(sh, String.fromCharCode(65 + c) + '4'); if (h) hdr[String.fromCharCode(65 + c)] = h; }
    for (let r = 5; r <= 51; r++) if (String(engine.cellValue(sh, 'B' + r) || '').toUpperCase() === t) { out.certified = { row: r, values: Object.fromEntries(Object.entries(hdr).map(([c, h]) => [h, engine.cellValue(sh, c + r)])) }; break; }
    return out;
  }));

  app.post('/api/action/:name', wrap(async (req) => {
    const fn = actions[req.params.name]; if (!fn) throw new Error('Unknown action');
    const user = String(req.body.user || 'Unknown user').slice(0, 60);
    return fn(req.body.params || {}, user);
  }));

  app.get('/api/audit', wrap(async (req) => {
    const id = engine.sid(AUDIT_SHEET); const h = engine.hf.getSheetDimensions(id).height; const limit = Math.min(+req.query.limit || 200, 2000);
    const rows = []; for (let r = h - 1; r >= 1 && rows.length < limit; r--) rows.push(Array.from({ length: 10 }, (_, c) => engine.hf.getCellValue({ sheet: id, row: r, col: c })));
    return { total: Math.max(h - 1, 0), rows };
  }));

  app.get('/api/download', async (req, res) => { await engine.flush(); res.download(FILE, 'Manifest_Workbench.xlsx'); });
  const snapName = (s) => s.replace(/[^\w.\- ]/g, '_');
  app.get('/api/snapshots', wrap(async () => fs.readdirSync(BACKUPS).filter((f) => f.endsWith('.xlsx')).sort().reverse().map((f) => ({ name: f, size: fs.statSync(path.join(BACKUPS, f)).size }))));
  app.post('/api/snapshots', wrap(async (req) => { await engine.flush(); const n = `${new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19)}${req.body.label ? '_' + snapName(req.body.label) : ''}.xlsx`; fs.copyFileSync(FILE, path.join(BACKUPS, n)); return { ok: true, name: n }; }));
  app.post('/api/restore', wrap(async (req) => {
    const f = path.join(BACKUPS, path.basename(req.body.name || '')); if (!fs.existsSync(f)) throw new Error('Snapshot not found');
    await engine.flush(); fs.copyFileSync(FILE, path.join(BACKUPS, 'pre-restore-' + Date.now() + '.xlsx'));
    fs.copyFileSync(f, FILE); const v = engine.version; engine = new Engine(FILE); await engine.init(); engine.version = v + 1; actions = makeActions(engine); for (const k in metaCache) delete metaCache[k]; return { ok: true };
  }));
  app.use((req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

  app.listen(PORT, () => console.log(`Manifest Workbench app on http://localhost:${PORT}`));
  process.on('SIGINT', async () => { await engine.flush(); process.exit(0); });
  process.on('SIGTERM', async () => { await engine.flush(); process.exit(0); });
})();
