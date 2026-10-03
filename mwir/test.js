// Logic tests for the MWIR report builder. Run: node --test mwir/test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');

global.window = { localStorage: { getItem: () => null, setItem: () => {} } };
global.document = { addEventListener: () => {} };
require('./zacks.js');
require('./mwir.js');
const M = window.MWIR;

test('bands are 75-125% of target, floored at 1.00% and capped at 4.00%', () => {
  assert.strictEqual(M.band(3.49), '2.62–4.00%');
  assert.strictEqual(M.band(1.85), '1.39–2.31%');
  assert.strictEqual(M.band(1.2), '1.00–1.50%');
});

test('CSV import reads Date/Symbol/Weights and converts decimal weights', () => {
  M.state.doc = M.seedDoc();
  M.importCsv('Date,Symbol,Weights,,note\n9/25/2026,COST,0.6,,"a, quoted"\n9/25/2026,NEWCO,0.4,,\n,,,,\n');
  const hs = M.state.doc.holdings;
  assert.deepStrictEqual(hs.map((x) => [x.ticker, x.current, x.sleeve]), [['COST', '60', 'Strategic'], ['NEWCO', '40', 'Unassigned']]);
  assert.strictEqual(M.state.doc.weekEnding, '2026-09-25');
  assert.strictEqual(M.state.doc.pubDate, '2026-09-28');
  assert.match(M.state.importMsg, /New \(set sleeve \+ rationale\): NEWCO/);
  assert.match(M.state.importMsg, /Dropped vs prior: .*JNJ/);
});

test('Zacks screen flags cap and rank failures, maps aliases and counts ETFs', () => {
  M.state.doc = M.seedDoc();
  const zk = M.model().zk;
  assert.deepStrictEqual(zk.counts, { 'TIER 1': 6, PASS: 28, REVIEW: 5, ETF: 6, 'NO DATA': 0 });
  assert.match(zk.reviewText, /CME \(cap \$95\.10B, Rank 4 Sell\)/);
  assert.match(zk.aliasText, /MMC is listed by Zacks as MRSH/);
});

test('control assertions fail when weights do not total 100%', () => {
  M.state.doc = M.seedDoc();
  const v = M.model();
  assert.strictEqual(v.stats.totalOk, false);
  assert.strictEqual(v.cert.label, 'HOLD · CONTROLS FAILING');
  M.importCsv('Date,Symbol,Weights\n9/25/2026,COST,0.5\n9/25/2026,JNJ,0.5\n');
  assert.strictEqual(M.model().stats.totalOk, true);
});
