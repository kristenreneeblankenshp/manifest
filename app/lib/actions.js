'use strict';
// Workflow actions. Each action only writes INPUT cells; every gate, status and roll-up is
// computed by the workbook's own formulas, so the app can never disagree with the workbook.
const { TABLES, S, freeRow } = require('./tables');

const serialToday = () => Math.floor(Date.now() / 86400000) + 25569;
const serialToYmd = (n) => new Date(Math.round((n - 25569) * 86400000)).toISOString().slice(0, 10).replace(/-/g, '');
const has = (v) => v !== undefined && v !== null && v !== '';
const CLOSED = ['Rejected', 'Closed', 'Removed'];

class ActionError extends Error { constructor(msg, extra) { super(msg); this.extra = extra; } }

module.exports = function makeActions(engine) {
  const val = (sh, a) => engine.cellValue(sh, a);
  const P = S.pipeline, R = S.registry;

  function findRow(key, id) {
    const T = TABLES[key];
    for (let r = T.first; r <= T.last; r++) { const v = val(T.sheet, T.idCol + r); if (v !== null && String(v) === String(id)) return r; }
    return null;
  }
  function registryRow(ticker) {
    for (let r = 14; r <= 163; r++) if (String(val(R, 'B' + r) || '').toUpperCase() === String(ticker).toUpperCase()) return r;
    return null;
  }
  function nextId(key, dateSerial) {
    const T = TABLES[key];
    if (T.idStyle === 'seq') {
      let max = 0; for (let r = T.first; r <= T.last; r++) { const m = new RegExp(`^${T.idPrefix}-(\\d+)$`).exec(String(val(T.sheet, T.idCol + r) || '')); if (m) max = Math.max(max, +m[1]); }
      return `${T.idPrefix}-${String(max + 1).padStart(3, '0')}`;
    }
    const ymd = serialToYmd(dateSerial); let max = 0;
    for (let r = T.first; r <= T.last; r++) { const m = new RegExp(`^${T.idPrefix}-${ymd}-(\\d+)$`).exec(String(val(T.sheet, T.idCol + r) || '')); if (m) max = Math.max(max, +m[1]); }
    return `${T.idPrefix}-${ymd}-${String(max + 1).padStart(3, '0')}`;
  }
  const cells = (sh, row, map) => Object.entries(map).filter(([, v]) => v !== undefined).map(([c, v]) => ({ sheet: sh, addr: c + row, value: v === null ? '' : v }));
  const state = (row) => ({ gate: val(P, 'Z' + row), status: val(P, 'AK' + row), action: val(P, 'AL' + row), stage: val(P, 'Y' + row) });
  const meta = (user, action, record, note) => ({ user, action, record, note });
  const need = (p, ...keys) => { const miss = keys.filter((k) => !has(p[k])); if (miss.length) throw new ActionError(`Required: ${miss.join(', ')}`); };

  const A = {
    // ---------- generic record creation for any table ----------
    'record.add': (p, user) => engine.run(async () => {
      const key = p.table; const T = TABLES[key]; if (!T) throw new ActionError('Unknown table');
      const row = freeRow(engine, key); if (!row) throw new ActionError(`${T.title} has no free slots.`);
      const values = { ...(p.values || {}) };
      let id = null;
      if (T.idPrefix) { id = nextId(key, has(values.B) && key !== 'pipeline' ? values.B : serialToday()); values[T.idCol] = id; }
      const changes = cells(T.sheet, row, values);
      const r = await engine._edit(changes, meta(user, `Add ${T.title} record`, id || values[T.tickerCol] || '', p.note || ''));
      return { ok: true, id, row, diff: r.diff, table: key };
    }),

    // ---------- registry ----------
    'registry.add': (p, user) => engine.run(async () => {
      need(p, 'ticker', 'security', 'class', 'status', 'basis', 'sleeve', 'role', 'type');
      const ticker = String(p.ticker).trim().toUpperCase();
      if (registryRow(ticker)) throw new ActionError(`${ticker} already has a MASR registry record (one active row per security).`);
      const row = freeRow(engine, 'registry'); if (!row) throw new ActionError('MASR registry is full (150 slots).');
      const map = { A: p.canonicalId, B: ticker, C: p.security, D: p.class, E: p.status, F: p.basis, G: p.sleeve, H: p.role, I: p.type, T: p.marketCap, U: p.zacks, V: p.merrill, W: p.empirical, AB: p.disposition || 'Pending', AI: p.notes };
      const r = await engine._edit(cells(R, row, map), meta(user, 'Add MASR record', ticker, p.note || ''));
      return { ok: true, row, ticker, diff: r.diff, status: val(R, 'AD' + row), action: val(R, 'AE' + row) };
    }),

    // ---------- candidate pipeline ----------
    'candidate.create': (p, user) => engine.run(async () => {
      need(p, 'ticker', 'type', 'source', 'owner', 'due');
      const ticker = String(p.ticker).trim().toUpperCase(); const intake = has(p.intake) ? +p.intake : serialToday();
      const row = freeRow(engine, 'pipeline'); if (!row) throw new ActionError('Pipeline is full (200 records).');
      const id = nextId('pipeline', intake);
      const map = { A: id, B: intake, C: ticker, E: p.type, F: p.group, G: p.target, H: p.source, W: p.evidence, Y: 'Intake', AA: p.owner, AB: +p.due, AM: p.summary, AN: p.memo };
      const r = await engine._edit(cells(P, row, map), meta(user, 'Create candidate', id, ''));
      return { ok: true, id, row, registryFound: !!registryRow(ticker), diff: r.diff, ...state(row) };
    }),

    'candidate.advance': (p, user) => engine.run(async () => {
      need(p, 'id', 'to');
      const row = findRow('pipeline', p.id); if (!row) throw new ActionError('Candidate not found');
      const changes = cells(P, row, { Y: p.to });
      const trial = engine._trial(changes, () => state(row));
      const passed = trial.gate === 'PASS — STAGE GATE';
      if (!passed && !p.force) return { ok: false, blocked: true, projected: trial, current: state(row) };
      const r = await engine._edit(changes, meta(user, passed ? 'Advance stage' : 'Advance stage (forced — gate exception)', p.id, `${state(row).stage} → ${p.to}${passed ? '' : ' | ' + trial.gate}`));
      return { ok: true, forced: !passed, diff: r.diff, ...state(row) };
    }),

    'candidate.disposition': (p, user) => engine.run(async () => {
      need(p, 'id', 'disposition');
      const row = findRow('pipeline', p.id); if (!row) throw new ActionError('Candidate not found');
      const date = has(p.date) ? +p.date : serialToday();
      const changes = cells(P, row, { AD: p.disposition, AE: date });
      const ticker = val(P, 'C' + row); const rr = registryRow(ticker);
      if (rr && val(R, 'D' + rr) !== 'Certified Portfolio Holding' && p.syncRegistry !== false) changes.push(...cells(R, rr, { AB: p.disposition, AF: date }));
      const r = await engine._edit(changes, meta(user, 'Committee disposition', p.id, p.disposition));
      return { ok: true, diff: r.diff, ...state(row) };
    }),

    'candidate.refer': (p, user) => engine.run(async () => {
      need(p, 'id');
      const row = findRow('pipeline', p.id); if (!row) throw new ActionError('Candidate not found');
      const ticker = val(P, 'C' + row);
      const changes = []; let pewId = p.pewId || val(P, 'AG' + row) || null; let created = false;
      if (!pewId) {
        const cr = freeRow(engine, 'compare'); if (!cr) throw new ActionError('PEW-004 comparison register has no free slots (20).');
        pewId = val(S.compare, 'A' + cr); created = true;
        const rr = registryRow(ticker); const rv = (c) => (rr ? val(R, c + rr) : null);
        const merrill = rv('V'); const okMerrill = engine.validationFor(S.compare, 'I' + cr) || [];
        const entries = { B: val(P, 'F' + row), C: val(P, 'E' + row) === 'Retention Review' ? 'Incumbent' : 'Candidate', D: ticker, E: val(P, 'D' + row), F: val(P, 'I' + row), G: val(P, 'J' + row), H: rv('T'), I: okMerrill.includes(merrill) ? merrill : undefined, J: rv('U'), K: rv('O'), L: rv('N'), M: rv('W'), X: `Referred from ${p.id}` };
        for (const [c, v] of Object.entries(entries)) { if (!has(v)) continue; const list = engine.validationFor(S.compare, c + cr); if (list && !list.map(String).includes(String(v))) continue; changes.push({ sheet: S.compare, addr: c + cr, value: v }); }
      }
      changes.push(...cells(P, row, { AF: 'Yes — Refer to PEW-004', AG: pewId, Y: 'Referred to PEW-004' }));
      const trial = engine._trial(changes, () => state(row));
      const passed = trial.gate === 'PASS — STAGE GATE';
      if (!passed && !p.force) return { ok: false, blocked: true, projected: trial, current: state(row) };
      const r = await engine._edit(changes, meta(user, 'Refer to PEW-004', p.id, `${created ? 'Opened' : 'Linked'} ${pewId}`));
      return { ok: true, pewId, created, forced: !passed, diff: r.diff, ...state(row) };
    }),

    'candidate.close': (p, user) => engine.run(async () => {
      need(p, 'id', 'stage', 'reason', 'by');
      if (!CLOSED.includes(p.stage)) throw new ActionError('Stage must be Rejected, Closed or Removed');
      const row = findRow('pipeline', p.id); if (!row) throw new ActionError('Candidate not found');
      const date = has(p.date) ? +p.date : serialToday();
      const dispOpts = (engine.validationFor(P, 'AD' + row) || []).map(String);
      const dflt = { Rejected: 'Reject Candidate', Removed: 'Remove from MASR', Closed: 'Defer' }[p.stage];
      const disposition = p.disposition || (['Pending', '', null].includes(val(P, 'AD' + row)) || !val(P, 'AD' + row) ? (dispOpts.includes(dflt) ? dflt : undefined) : undefined);
      const changes = cells(P, row, { Y: p.stage, AO: p.reason, AP: p.by, AQ: date, AD: disposition, AE: disposition ? date : undefined });
      const r = await engine._edit(changes, meta(user, `Close candidate — ${p.stage}`, p.id, p.reason));
      return { ok: true, diff: r.diff, ...state(row) };
    }),

    'candidate.reopen': (p, user) => engine.run(async () => {
      need(p, 'id');
      const row = findRow('pipeline', p.id); if (!row) throw new ActionError('Candidate not found');
      const r = await engine._edit(cells(P, row, { Y: p.stage || 'On Watch', AO: '', AP: '', AQ: '' }), meta(user, 'Reopen candidate', p.id, ''));
      return { ok: true, diff: r.diff, ...state(row) };
    }),

    // ---------- generic multi-cell save from the UI (record drawer / grid) ----------
    'cells.save': (p, user) => engine.run(async () => {
      if (!Array.isArray(p.changes) || !p.changes.length) throw new ActionError('Nothing to save');
      const r = await engine._edit(p.changes.map((c) => ({ sheet: c.sheet, addr: c.addr, value: c.value })), meta(user, p.label || 'Edit', p.record || '', p.note || ''));
      return { ok: true, diff: r.diff };
    }),
  };
  return A;
};
module.exports.serialToday = serialToday;
