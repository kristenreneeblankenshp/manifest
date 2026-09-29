// End-to-end workflow test: boots the server on a scratch copy of the workbook and drives
// a candidate from intake to PEW-004 referral through the same API the UI uses.
const test = require('node:test'); const assert = require('node:assert');
const { spawn } = require('node:child_process'); const fs = require('node:fs'); const os = require('node:os'); const path = require('node:path');
const PORT = 3999, B = `http://localhost:${PORT}`; let proc, dir;
const call = async (n, params) => { const r = await fetch(`${B}/api/action/${n}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ user: 'test', params }) }); return { status: r.status, ...(await r.json()) }; };
const table = async (k) => (await fetch(`${B}/api/table/${k}`)).json();
test.before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mw-')); fs.copyFileSync(path.join(__dirname, '../data/original.xlsx'), path.join(dir, 'original.xlsx'));
  proc = spawn('node', [path.join(__dirname, '../server.js')], { env: { ...process.env, DATA_DIR: dir, PORT }, stdio: 'ignore' });
  for (let i = 0; i < 60; i++) { try { if ((await fetch(`${B}/api/version`)).ok) return; } catch {} await new Promise((r) => setTimeout(r, 500)); }
  throw new Error('server did not start');
});
test.after(() => proc && proc.kill());

test('formula cells are protected and validation lists enforced', async () => {
  const a = await call('cells.save', { changes: [{ sheet: '24 RCC-004 Candidate Pipeline', addr: 'Z14', value: 'x' }] }); assert.equal(a.status, 400);
  const b = await call('cells.save', { changes: [{ sheet: '24 RCC-004 Candidate Pipeline', addr: 'Y14', value: 'Nonsense' }] }); assert.equal(b.status, 400);
});

test('candidate lifecycle is gated by the workbook formulas and refers into PEW-004', async () => {
  const today = Math.floor(Date.now() / 86400000) + 25569;
  const R = (await table('registry')).rows.find((r) => r.v.B === 'VRT'), M = (await table('miar')).rows.find((r) => r.v.B === 'VRT');
  const setup = [['23 RCC-004 MASR Registry', 'A' + R.row, 'MASR-VRT'], ['23 RCC-004 MASR Registry', 'W' + R.row, 5], ['20 RCC-003 MIAR Registry', 'A' + M.row, 'MIAR-VRT'], ['20 RCC-003 MIAR Registry', 'M' + M.row, 'Active'], ['20 RCC-003 MIAR Registry', 'K' + M.row, 82], ['20 RCC-003 MIAR Registry', 'L' + M.row, 77], ['20 RCC-003 MIAR Registry', 'N' + M.row, 'Analyst'], ['20 RCC-003 MIAR Registry', 'O' + M.row, 'Quarterly — 90 Days'], ['20 RCC-003 MIAR Registry', 'Q' + M.row, today]];
  assert.ok((await call('cells.save', { changes: setup.map(([sheet, addr, value]) => ({ sheet, addr, value })) })).ok);
  const c = await call('candidate.create', { ticker: 'VRT', type: 'Retention Review', source: 'Advisor Observation', owner: 'Research Committee', due: today + 30 });
  assert.match(c.id, /^MCP-\d{8}-\d{3}$/);
  const blocked = await call('candidate.advance', { id: c.id, to: 'Candidate Comparison' });
  assert.equal(blocked.ok, false); assert.equal(blocked.projected.gate, 'FAIL — EVIDENCE');
  const ev = await call('record.add', { table: 'evidence', values: { B: today, C: today, D: 'Certified Holding', E: 'VRT', H: 'Company Review', I: 'Earnings and Guidance', J: 'High', K: 'Positive', L: 'Primary — Verified', M: 'Company Filing', N: 'SEC', P: 'Q3 results', R: 'Analyst', S: today + 7, T: 'Under Review', U: 'Yes' } });
  assert.match(ev.id, /^EVD-/);
  for (const st of ['Evidence Gathering', 'MIAR Review', 'Eligibility Review', 'Candidate Comparison', 'Committee Review']) assert.ok((await call('candidate.advance', { id: c.id, to: st })).ok, st);
  assert.equal((await call('candidate.advance', { id: c.id, to: 'Approved for MASR' })).projected.gate, 'FAIL — COMMITTEE DISPOSITION');
  await call('candidate.disposition', { id: c.id, disposition: 'Advance to PEW-004' });
  assert.ok((await call('candidate.advance', { id: c.id, to: 'Approved for MASR' })).ok);
  const ref = await call('candidate.refer', { id: c.id }); assert.ok(ref.ok); assert.match(ref.pewId, /^CAND-/);
  assert.equal((await table('compare')).rows.find((r) => r.v.A === ref.pewId).v.D, 'VRT');
  const audit = await (await fetch(`${B}/api/audit?limit=1000`)).json(); assert.ok(audit.total > 20);
});
