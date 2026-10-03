'use strict';
// Declarative description of the record tables inside the workbook. Everything else
// (input vs. calculated, dropdown options, formats) is derived from the workbook itself.
const { colName, addrOf } = require('./engine');
const { colToNum } = require('./xlsxpatch');

const S = {
  pipeline: '24 RCC-004 Candidate Pipeline',
  registry: '23 RCC-004 MASR Registry',
  miar: '20 RCC-003 MIAR Registry',
  evidence: '18 RCC-002 Evidence Ledger',
  reviews: '21 RCC-003 MIAR Review Log',
  compare: '10 Candidate Comparison',
  actions: '04 Committee Operations',
  watch: '03 Research Intelligence',
  control4: '22 RCC-004 Control Center',
};

const TABLES = {
  pipeline: { title: 'Candidate Pipeline', sheet: S.pipeline, header: 13, first: 14, last: 213, idCol: 'A', idPrefix: 'MCP', tickerCol: 'C', titleCol: 'D', stageCol: 'Y', statusCol: 'AK', actionCol: 'AL', gateCol: 'Z',
    listCols: ['A', 'C', 'D', 'E', 'Y', 'M', 'Z', 'AK', 'AB', 'AA'], slot: 'idEmpty',
    groups: [['Identity', 'A', 'H'], ['Registry & research state', 'I', 'X'], ['Workflow', 'Y', 'AC'], ['Committee & PEW-004', 'AD', 'AJ'], ['Control', 'AK', 'AL'], ['Narrative & closure', 'AM', 'AQ']] },
  registry: { title: 'MASR Registry', sheet: S.registry, header: 13, first: 14, last: 163, idCol: 'B', tickerCol: 'B', titleCol: 'C', statusCol: 'AD', actionCol: 'AE', classCol: 'D',
    listCols: ['B', 'C', 'D', 'E', 'G', 'X', 'AD', 'AA'], slot: 'registry',
    groups: [['Identity & classification', 'A', 'J'], ['MIAR / research state', 'K', 'S'], ['Market & external research', 'T', 'W'], ['Eligibility & pipeline', 'X', 'AC'], ['Control', 'AD', 'AE'], ['Committee & notes', 'AF', 'AI']] },
  miar: { title: 'MIAR Dossiers', sheet: S.miar, header: 13, first: 14, last: 60, idCol: 'A', tickerCol: 'B', titleCol: 'C', statusCol: 'AB', actionCol: 'AC', listCols: ['B', 'C', 'D', 'M', 'Z', 'AA', 'AB', 'N'], slot: 'none',
    groups: [['Identity', 'A', 'H'], ['Research controls', 'I', 'T'], ['Activity', 'U', 'Y'], ['Control', 'Z', 'AD'], ['Certification & notes', 'AE', 'AG']] },
  evidence: { title: 'Evidence Ledger', sheet: S.evidence, header: 13, first: 14, last: 213, idCol: 'A', idPrefix: 'EVD', tickerCol: 'E', titleCol: 'F', statusCol: 'AE', listCols: ['A', 'B', 'E', 'H', 'J', 'K', 'T', 'U', 'AE'], slot: 'idEmpty',
    groups: [['Signal', 'A', 'H'], ['Assessment', 'I', 'Q'], ['Ownership & status', 'R', 'U'], ['Routing', 'V', 'AB'], ['Control', 'AC', 'AF'], ['Notes', 'AG', 'AG']] },
  reviews: { title: 'MIAR Review Log', sheet: S.reviews, header: 13, first: 14, last: 213, idCol: 'A', idPrefix: 'MIR', tickerCol: 'C', titleCol: 'D', statusCol: 'U', listCols: ['A', 'B', 'C', 'E', 'F', 'I', 'R', 'U'], slot: 'idEmpty',
    groups: [['Review', 'A', 'H'], ['Scores & status change', 'I', 'M'], ['Assessment', 'N', 'R'], ['Certification', 'S', 'U'], ['Notes', 'V', 'W']] },
  compare: { title: 'PEW-004 Comparison', sheet: S.compare, header: 13, first: 14, last: 33, idCol: 'A', tickerCol: 'D', titleCol: 'E', statusCol: 'Y', actionCol: 'V', listCols: ['A', 'D', 'E', 'C', 'Q', 'T', 'U', 'V', 'W', 'Y'], slot: 'compare',
    groups: [['Identity', 'A', 'G'], ['Inputs', 'H', 'P'], ['Scoring', 'Q', 'V'], ['Decision', 'W', 'Y']] },
  actions: { title: 'Committee Action Register', sheet: S.actions, header: 6, first: 7, last: 21, idCol: 'A', idPrefix: 'OP', idStyle: 'seq', titleCol: 'C', statusCol: 'G', listCols: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], slot: 'idEmpty', lastCol: 'I', groups: [['Action', 'A', 'I']] },
  watch: { title: 'Companies Requiring Review', sheet: S.watch, header: 6, first: 7, last: 15, idCol: 'A', tickerCol: 'A', titleCol: 'B', statusCol: 'G', listCols: ['A', 'B', 'C', 'D', 'E', 'F', 'G'], slot: 'idEmpty', lastCol: 'G', groups: [['Review', 'A', 'G']] },
};

const isDateFmt = (f) => f && /[dmy]/i.test(f.replace(/"[^"]*"|\[[^\]]*\]|0\.0*%?/g, '').replace(/[;()+\-\s]/g, '')) && !/^[0#,.%x"]+$/.test(f);
const isPctFmt = (f) => f && /%/.test(f);

function buildMeta(engine, key) {
  const T = TABLES[key]; const sh = T.sheet; const L = engine.layout[sh];
  const lastCol = T.lastCol ? colToNum(T.lastCol) : Math.max(...Object.keys(L.styles).map((a) => colToNum(/^[A-Z]+/.exec(a)[0])), 1);
  const cols = [];
  for (let c = 1; c <= lastCol; c++) {
    const letter = colName(c - 1);
    let label = engine.cellValue(sh, letter + T.header); if (label == null) label = letter;
    label = String(label); const auto = /\(Auto\)/.test(label); const input = /\(Input\)/.test(label);
    label = label.replace(/\s*\((Input|Auto)\)\s*$/, '');
    // sample column style/type from the first data row that has a style
    let fmt = null;
    for (let r = T.first; r <= Math.min(T.last, T.first + 3) && !fmt; r++) { const s = L.styles[letter + r]; if (s !== undefined) fmt = engine.stylesTbl[s]?.fmt || null; }
    let anyFormula = false;
    for (let r = T.first; r <= T.last; r++) if (engine.isFormula(sh, letter + r)) { anyFormula = true; break; }
    const options = engine.validationFor(sh, letter + T.first);
    const type = isDateFmt(fmt) ? 'date' : isPctFmt(fmt) ? 'pct' : options ? 'select' : /^(0|0\.0+|#,##0.*)$/.test((fmt || '').split(';')[0]) ? 'number' : 'text';
    cols.push({ letter, label, auto: auto || (anyFormula && !input), input, fmt, type, options: options || undefined });
  }
  return { key, title: T.title, sheet: sh, header: T.header, first: T.first, last: T.last, idCol: T.idCol, tickerCol: T.tickerCol, titleCol: T.titleCol, stageCol: T.stageCol, statusCol: T.statusCol, actionCol: T.actionCol, gateCol: T.gateCol, classCol: T.classCol, listCols: T.listCols, groups: T.groups, idPrefix: T.idPrefix, idStyle: T.idStyle, cols };
}

function tableRows(engine, key, meta) {
  const T = TABLES[key]; const sh = T.sheet; const rows = [];
  for (let r = T.first; r <= T.last; r++) {
    const keyv = engine.cellValue(sh, (T.tickerCol || T.idCol) + r); const idv = engine.cellValue(sh, T.idCol + r);
    const has = (x) => x !== null && x !== '';
    const filled = T.slot === 'compare' ? has(keyv) : has(keyv) || has(idv);
    if (!filled) { if (T.slot === 'idEmpty' || T.slot === 'compare') continue; else continue; }
    const v = {}; const f = {};
    for (const c of meta.cols) { const val = engine.cellValue(sh, c.letter + r); if (val !== null && val !== '') v[c.letter] = val; if (engine.isFormula(sh, c.letter + r)) f[c.letter] = 1; }
    rows.push({ row: r, v, f });
  }
  return rows;
}

/** first free row per the table's slot rule */
function freeRow(engine, key) {
  const T = TABLES[key]; const sh = T.sheet;
  for (let r = T.first; r <= T.last; r++) {
    const keyc = T.slot === 'registry' ? 'B' : T.slot === 'compare' ? 'D' : T.idCol;
    const v = engine.cellValue(sh, keyc + r);
    if ((v === null || v === '') && !engine.isFormula(sh, keyc + r)) return r;
  }
  return null;
}

module.exports = { TABLES, S, buildMeta, tableRows, freeRow, isDateFmt };
