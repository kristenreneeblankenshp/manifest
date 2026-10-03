/* MWIR report builder: weekly inputs on the left, the 8-page report on the right.
   No build step and no dependencies; state is kept in localStorage. */
(function () {
  'use strict';

  var STORE_KEY = 'manifest-mwir-builder-v1';

  var SLEEVES = [
    { key: 'Strategic', name: 'Strategic Anchors' },
    { key: 'Growth', name: 'Growth Compounders' },
    { key: 'Digital', name: 'Digital Infrastructure / AI' },
    { key: 'Industrials', name: 'Industrials / Infrastructure' },
    { key: 'Financial', name: 'Financial Infrastructure' },
    { key: 'Healthcare', name: 'Healthcare Leadership' },
    { key: 'Energy', name: 'Energy / Natural Resources' },
    { key: 'Income', name: 'Income / Risk Management' },
    { key: 'Unassigned', name: 'Unassigned' }
  ];

  var GUIDANCE = ['SELECTIVE ADD', 'MAINTAIN', 'MAINTAIN / NO CHASE', 'HOLD <= TARGET', 'EVENT HOLD', 'TRIM', 'EXIT'];

  var CHIP = {
    'SELECTIVE ADD': ['#dcebe1', '#1f5a3c'],
    'MAINTAIN': ['#eceae4', '#3a3d45'],
    'MAINTAIN / NO CHASE': ['#f4e6c8', '#6e4a0c'],
    'HOLD <= TARGET': ['#f4e6c8', '#6e4a0c'],
    'EVENT HOLD': ['#f5dccd', '#843710'],
    'TRIM': ['#f5dccd', '#843710'],
    'EXIT': ['#f2d6d7', '#861c22']
  };

  var PASS = '#1f5a3c', FAIL = '#a3262a', WARN = '#843710';

  var SEED_HOLDINGS = [
    'Strategic|COST|3.02|3.49|MAINTAIN|Consumer resilience; redistributed anchor',
    'Strategic|JNJ|3.02|3.49|SELECTIVE ADD|Quality healthcare anchor',
    'Strategic|MSFT|3.02|3.49|MAINTAIN|AI platform; preserve discipline',
    'Strategic|V|2.88|3.33|MAINTAIN|Payments infrastructure',
    'Strategic|GOOGL|2.84|3.28|MAINTAIN|AI/platform anchor',
    'Strategic|MA|1.60|1.85|MAINTAIN|Payments infrastructure',
    'Strategic|AAPL|1.56|1.80|MAINTAIN|Ecosystem anchor',
    'Strategic|AMZN|1.55|1.79|MAINTAIN|Cloud/commerce anchor',
    'Growth|AVGO|3.02|3.02|EVENT HOLD|Sep 3 earnings gate',
    'Growth|LLY|3.02|3.02|SELECTIVE ADD|Healthcare quality priority',
    'Growth|NVDA|2.68|2.68|MAINTAIN|Q2 gate cleared; strong AI demand',
    'Growth|HD|1.56|1.56|MAINTAIN|Q2 beat; guidance reaffirmed',
    'Growth|META|1.56|1.56|MAINTAIN|Platform quality',
    'Growth|ANET|1.55|1.55|HOLD <= TARGET|Networking concentration',
    'Digital|PANW|1.99|1.99|EVENT HOLD|Sep 1 earnings gate',
    'Digital|AMAT|1.56|1.56|HOLD <= TARGET|Semi-cycle restraint',
    'Digital|CSCO|1.56|1.56|HOLD <= TARGET|Networking overlap',
    'Digital|KLAC|1.56|1.56|HOLD <= TARGET|Semi-cycle restraint',
    'Digital|MU|1.56|1.56|HOLD <= TARGET|Memory-cycle risk',
    'Digital|ORCL|1.56|1.56|MAINTAIN|Cloud/database exposure',
    'Digital|TXN|1.56|1.56|MAINTAIN|Analog quality',
    'Digital|VRT|1.55|1.55|HOLD <= TARGET|AI infra concentration',
    'Industrials|DHR|3.00|3.00|SELECTIVE ADD|Quality industrial/health tools',
    'Industrials|RTX|2.99|2.99|MAINTAIN|Defense/aerospace resilience',
    'Industrials|DE|1.77|1.77|SELECTIVE ADD|Q3 beat; ag cycle watch',
    'Industrials|CAT|1.56|1.56|SELECTIVE ADD|Infrastructure priority',
    'Industrials|ETN|1.56|1.56|SELECTIVE ADD|Electrification leader',
    'Industrials|GE|1.56|1.56|SELECTIVE ADD|Aerospace quality',
    'Industrials|PH|1.56|1.56|SELECTIVE ADD|Motion/control quality',
    'Industrials|TT|1.56|1.56|MAINTAIN|Efficiency infrastructure',
    'Industrials|UNP|1.55|1.55|MAINTAIN|Volume watch',
    'Financial|CME|3.02|3.02|MAINTAIN|Volatility beneficiary',
    'Financial|MMC|2.00|2.00|MAINTAIN|Risk infrastructure',
    'Financial|GS|1.56|1.56|MAINTAIN|Capital markets exposure',
    'Financial|JPM|1.56|1.56|MAINTAIN|Banking quality',
    'Financial|VFH|1.56|1.56|MAINTAIN|Diversified financials',
    'Healthcare|VHT|2.06|2.06|SELECTIVE ADD|Healthcare sleeve priority',
    'Healthcare|SYK|1.55|1.55|SELECTIVE ADD|Medtech quality',
    'Energy|LNG|3.02|3.02|MAINTAIN / NO CHASE|Geopolitical premium elevated',
    'Energy|VPU|3.02|3.02|MAINTAIN|Defensive; rate sensitive',
    'Energy|XOM|2.56|2.56|MAINTAIN / NO CHASE|Oil event premium',
    'Energy|CVX|1.56|1.56|MAINTAIN / NO CHASE|Oil event premium',
    'Energy|VDE|1.56|1.56|MAINTAIN / NO CHASE|Sector exposure sufficient',
    'Income|JEPI|3.02|3.02|MAINTAIN|Income / volatility moderation',
    'Income|JEPQ|3.02|3.02|HOLD <= TARGET|Tech overlap'
  ];

  function seedHoldings() {
    return SEED_HOLDINGS.map(function (s) {
      var p = s.split('|');
      return { sleeve: p[0], ticker: p[1], mfpdf: p[2], current: p[3], guidance: p[4], rationale: p[5], status: 'EVIDENCE HOLD' };
    });
  }

  // The 28 Aug 2026 MWIR, used as the starting example.
  function seedDoc() {
    return {
      weekEnding: '2026-08-28',
      pubDate: '2026-08-31',
      headline: 'CONSTRUCTIVE PARTICIPATION · HAWKISH FED / GEOPOLITICAL DISCIPLINE',
      subhead: 'Remain fully model-allocated, but do not expand aggregate risk. Strong earnings and tighter credit spreads are offset by a more hawkish Fed path and renewed Iran/oil escalation into publication morning.',
      composite: '62',
      compositeChange: '-1',
      deltaGamma: '-1 / -1', deltaNote: 'policy-event cooling',
      fedRange: '3.50–3.75%', fedNote: 'unchanged',
      hyOas: '2.63%', hyNote: 'calm / improving',
      tenY: '4.67%*', tenYNote: 'still restrictive',
      vix: '14.43', vixNote: 'contained',
      components: [
        { name: 'Growth', score: '5' }, { name: 'Breadth', score: '6' },
        { name: 'Inflation', score: '4' }, { name: 'Momentum', score: '6' },
        { name: 'Fed / Liquidity', score: '4' }, { name: 'Volatility', score: '7' },
        { name: 'Credit', score: '9' }, { name: 'Rates', score: '4' },
        { name: 'Earnings', score: '9' }, { name: 'Geopolitics / Oil', score: '2' }
      ],
      tape: 'S&P 500 | +0.49%\nNasdaq Composite | +0.85%\nDow Industrials | +0.53%\nVIX close | 14.43\nWTI crude | $83.40 Fri / ~$86.31 Mon\nBrent crude | $89.31 Fri / ~$90.97 Mon',
      interpretation: 'Credit improved again: HY OAS fell to 2.63% on the latest official observation.\nFinancial stress remains below zero: STLFSI4 -0.8107 (latest published week).\nNVIDIA Q2 results materially strengthened the earnings evidence set.\nFriday Jackson Hole guidance raised the probability of a September hike.\nMonday oil/geopolitical escalation offsets part of the week-ending improvement.\nComposite slips to 62 from 63; Gamma remains negative.',
      decisionRule: 'The signal mix supports full model participation with a defensive risk budget: preserve quality anchors, healthcare, industrial infrastructure and income ballast; allow NVIDIA to revert from event hold to maintain-at-target after strong results; constrain AVGO/PANW additions through their evidence gates; do not chase energy after the renewed geopolitical premium.',
      officialPosture: '100% MODEL ALLOCATION · SELECTIVE INTERNAL ROTATION ONLY',
      execPosture: "Retain the 100.00% rules-governed Merrill executable model. The week improved on earnings, credit and volatility, but Friday's hawkish Jackson Hole message and renewed U.S.-Iran strikes into Aug. 31 argue against a net risk increase.",
      execImplementation: "Enforce MRGES-001. Berkshire Hathaway remains analytical only at 0.00% executable. Release the prior NVIDIA event hold after the Aug. 26 evidence review, but keep semiconductor/networking exposure at disciplined targets; place AVGO and PANW behind this week's earnings gates.",
      execIncremental: 'Favor healthcare and quality industrials only when below approved bands. Maintain energy exposure without chasing the publication-morning oil spike.',
      execControl: 'Actual account weights remain unavailable. This report publishes model guidance and monitoring bands; it does not infer drift or authorize live trades.',
      footnote: '*Latest official FRED daily observation available for DGS10 was 4.67% on Aug 27; Friday market yield moved higher after Jackson Hole.',
      macroRates: "Fed target remains 3.50-3.75%. The latest official 10-year Treasury observation was 4.67% on Aug. 27, down modestly from Aug. 21, but Chair Kevin Warsh's Jackson Hole remarks reinforced a hawkish reaction and increased September hike expectations.",
      macroInflation: 'The 10-year breakeven averaged 2.32% for the week ending Aug. 28. Inflation remains the key policy constraint; renewed oil strength into Aug. 31 raises the risk of headline re-acceleration.',
      macroCredit: 'High-yield OAS tightened to 2.63% on Aug. 27. STLFSI4 was -0.8107 for the week ending Aug. 21, still below zero and consistent with below-average system stress. Credit is not validating broad de-risking.',
      macroEarnings: 'NVIDIA reported Q2 FY2027 revenue of $96.2B, +106% y/y, with Data Center revenue of $89.0B, +117% y/y. The result clears the prior Aug. 26 event gate, though concentration discipline remains in force.',
      macroGeo: 'WTI finished Aug. 28 at $83.40 and Brent at $89.31, both down on the week. Renewed U.S.-Iran strikes over the weekend pushed Monday indications to about $86.31 WTI and $90.97 Brent, restoring an inflationary event premium.',
      gatesWeek: 'WEEK OF AUG 31',
      events: 'SEP 1 | Palo Alto Networks | Maintain event hold; review cybersecurity evidence after release.\nSEP 3 | Broadcom | Hold AVGO at or below target into earnings; reassess AI/networking concentration.\nSEP 4 | U.S. payrolls | Re-score growth, rates and Fed/liquidity after employment data.',
      reconciliation: 'Berkshire Hathaway (BRK.B): MFPDF analytical baseline 3.02% · Merrill executable target 0.00% · excluded because Merrill coverage is unavailable. The 3.02% remains redistributed pro rata among the eight eligible Strategic Anchors, preserving the sleeve at 22.51% and the executable model at 100.00%.',
      bandStandard: 'Current recommendation equals the MRGES executable target unless an event gate says HOLD <= TARGET. Approved monitoring bands remain 75%-125% of target, subject to the 1.00% floor and 4.00% cap. Actual weights are not available; no drift classification is asserted.',
      hierarchy: "Selective adds: VHT, SYK, JNJ, LLY, DHR, DE, CAT, ETN, GE and PH · only when below band and after account controls.\nMaintain: core anchors, NVIDIA at disciplined target after evidence review, financial infrastructure, income ballast and existing energy exposure.\nConstrain: AVGO and PANW at or below target through this week's event gates; do not chase energy on the renewed geopolitical premium.",
      matrixDisclaimer: 'No live trade authorization. Apply suitability, tax, liquidity, firm and supervisory controls before any account action. Missing actual weights prevents drift and order-size certification.',
      clientBrief: "The Manifest portfolio remains fully allocated under its rules-governed model, with a neutral/risk-control posture. Credit spreads tightened and NVIDIA delivered strong earnings, but the Federal Reserve reinforced its inflation-fighting stance at Jackson Hole and renewed U.S.-Iran conflict lifted oil again into publication morning. Preserve the Merrill executable model, selectively fund healthcare and quality industrials only when below approved bands, maintain NVIDIA at target after its evidence gate, and hold AVGO/PANW at or below target into this week's events.",
      deliverables: 'MWIR-WGT-001 weight-guidance standard\nMFPDF Founders Edition v1.0 allocation\nMRGES-001 rules-governed execution standard\nMerrill executable workbook v1.1\nPrior MWIR continuity through Aug 21, 2026',
      strategicTarget: '22.51',
      disclosures: 'Actual weights | unavailable / disclosed\nLive trade status | not authorized\nComposite formula | not retrieved; continuity judgment\nConviction tier | not reconstructed',
      sources: 'Federal Reserve Bank of St. Louis · ICE BofA US HY OAS (BAMLH0A0HYM2)\nFederal Reserve Bank of St. Louis · 10-Year Treasury (DGS10)\nCboe · VIX spot close, Aug 28, 2026\nFederal Reserve Bank of St. Louis · Financial Stress Index (STLFSI4)\nReuters · Wall Street ends lower after Fed Chair Warsh reaffirms inflation fight, Aug 28, 2026\nNVIDIA Newsroom · Q2 FY2027 results, Aug 26, 2026\nReuters · Oil settles lower on Fed policy / Hormuz signals, Aug 28, 2026\nReuters · Oil rises after renewed U.S.-Iran military attacks, Aug 31, 2026\nReuters · Week Ahead: jobs report and Broadcom results, Aug 28, 2026\nZacks Investment Research · Zacks Rank, market cap and earnings calendar',
      freshness: 'Market levels use the latest published official observations available as of the publication run. Where Friday official series were not yet posted, the report identifies the latest official observation rather than fabricating a Friday value. Publication-morning geopolitical/oil moves are treated as an event overlay, not as week-ending data.',
      holdings: seedHoldings()
    };
  }

  var MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  var MONTHS_T = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function parseIso(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    return m ? { y: +m[1], mo: +m[2] - 1, d: +m[3] } : null;
  }
  function num(v) { var n = parseFloat(v); return isFinite(n) ? n : 0; }
  function pct(v) { return num(v).toFixed(2) + '%'; }
  function lines(s) { return String(s || '').split('\n').map(function (x) { return x.trim(); }).filter(Boolean); }
  function pipes(s) { return lines(s).map(function (l) { return l.split('|').map(function (x) { return x.trim(); }); }); }
  function band(t) {
    var lo = Math.max(1, t * 0.75), hi = Math.min(4, t * 1.25);
    return lo.toFixed(2) + '–' + hi.toFixed(2) + '%';
  }
  function h(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function parseCsv(text) {
    var rows = [], row = [], cur = '', q = false;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (q) {
        if (ch === '"' && text[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') q = false;
        else cur += ch;
      } else if (ch === '"') q = true;
      else if (ch === ',') { row.push(cur); cur = ''; }
      else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        row.push(cur); rows.push(row); row = []; cur = '';
      } else cur += ch;
    }
    if (cur !== '' || row.length) { row.push(cur); rows.push(row); }
    return rows;
  }

  function zacksFor(ticker) {
    var snap = window.ZACKS_SNAPSHOT;
    if (!snap) return null;
    var key = (snap.alias && snap.alias[ticker]) || ticker;
    var raw = snap.data[key];
    if (!raw) return null;
    if (!Array.isArray(raw)) return { etf: true, key: key, rank: raw.rank, text: raw.text };
    return { etf: false, key: key, rank: raw[0], text: raw[1], cap: raw[2], er: raw[3] };
  }

  // ---------- state ----------
  var state = { doc: seedDoc(), tab: 'holdings', importMsg: '', importOk: true };
  try {
    var saved = window.localStorage.getItem(STORE_KEY);
    if (saved) state.doc = Object.assign(seedDoc(), JSON.parse(saved));
  } catch (e) { /* storage unavailable */ }

  function save() {
    try { window.localStorage.setItem(STORE_KEY, JSON.stringify(state.doc)); } catch (e) { /* ignore */ }
  }

  // ---------- model: everything the report shows, derived from the doc ----------
  function model() {
    var d = state.doc;
    var we = parseIso(d.weekEnding), pd = parseIso(d.pubDate);
    var m = {
      weekUpper: we ? we.d + ' ' + MONTHS[we.mo] + ' ' + we.y : '—',
      pubLong: pd ? pd.d + ' ' + MONTHS[pd.mo] + ' ' + pd.y : '—',
      pubShort: pd ? pd.d + ' ' + MONTHS_T[pd.mo] + ' ' + pd.y : '—'
    };

    // Gauge zones: thresholds are an assumption until the framework's own are supplied.
    var c = Math.max(0, Math.min(100, num(d.composite)));
    var zone = c >= 70 ? { label: 'GREEN · CONSTRUCTIVE', color: '#2f6f4f' }
      : c >= 55 ? { label: 'YELLOW · NEUTRAL / RISK CONTROL', color: '#9a6f0e' }
        : c >= 40 ? { label: 'ORANGE · DEFENSIVE', color: '#b04e14' }
          : { label: 'RED · RISK-OFF', color: '#a3262a' };
    zone.deg = (c * 1.8 - 90).toFixed(1);
    zone.value = c;

    var sleeveName = {}; SLEEVES.forEach(function (s) { sleeveName[s.key] = s.name; });
    var hs = d.holdings || [];
    var total = hs.reduce(function (s, x) { return s + num(x.current); }, 0);
    var totalOk = Math.abs(total - 100) < 0.01;
    var rows = hs.map(function (x, i) {
      var chip = CHIP[x.guidance] || CHIP.MAINTAIN;
      return Object.assign({}, x, { idx: i, mfpdfFmt: pct(x.mfpdf), currentFmt: pct(x.current), band: band(num(x.current)), chipBg: chip[0], chipFg: chip[1] });
    });
    var order = {}; SLEEVES.forEach(function (s, i) { order[s.key] = i; });
    var ord = function (k) { return k in order ? order[k] : 99; };
    var matrix = rows.slice().sort(function (a, b) { return (ord(a.sleeve) - ord(b.sleeve)) || (a.idx - b.idx); });
    var half = Math.ceil(matrix.length / 2);
    var matrixPages = [{ roman: 'I', num: 5, rows: matrix.slice(0, half) }, { roman: 'II', num: 6, rows: matrix.slice(half) }];

    var sleeveTotals = SLEEVES.map(function (s) {
      var v = hs.filter(function (x) { return x.sleeve === s.key; }).reduce(function (a, x) { return a + num(x.current); }, 0);
      return { name: s.name, key: s.key, v: v };
    }).filter(function (s) { return s.v > 0 || s.key !== 'Unassigned'; });
    var maxS = Math.max.apply(null, sleeveTotals.map(function (s) { return s.v; }).concat([1]));
    var sleeveAlloc = sleeveTotals.map(function (s) { return { name: s.name, fmt: s.v.toFixed(2) + '%', bar: (s.v / maxS * 100).toFixed(1) }; });
    var top10 = rows.slice().sort(function (a, b) { return (num(b.current) - num(a.current)) || (a.idx - b.idx); }).slice(0, 10);

    // control assertions
    var strategic = (sleeveTotals.filter(function (s) { return s.key === 'Strategic'; })[0] || { v: 0 }).v;
    var stratTarget = num(d.strategicTarget);
    var stratOk = !d.strategicTarget || Math.abs(strategic - stratTarget) < 0.015;
    var brk = hs.filter(function (x) { return /^BRK/.test(x.ticker) && num(x.current) > 0; }).length;
    var overCap = hs.filter(function (x) { return num(x.current) > 4.0001; }).length;
    var unassigned = hs.filter(function (x) { return !sleeveName[x.sleeve] || x.sleeve === 'Unassigned'; }).length;
    var checks = [
      { label: 'Executable holdings', result: hs.length + ' / ' + (hs.length ? 'PASS' : 'FAIL'), ok: hs.length > 0 },
      { label: 'Executable target total', result: total.toFixed(2) + '% / ' + (totalOk ? 'PASS' : 'FAIL'), ok: totalOk },
      { label: 'Strategic Anchors', result: strategic.toFixed(2) + '% / ' + (stratOk ? 'PASS' : 'CHECK vs ' + stratTarget.toFixed(2) + '%'), ok: stratOk },
      { label: 'BRK.B executable rows', result: brk + ' / ' + (brk === 0 ? 'PASS' : 'FAIL'), ok: brk === 0 },
      { label: 'Positions above 4.00% cap', result: overCap + ' / ' + (overCap === 0 ? 'PASS' : 'FAIL'), ok: overCap === 0 },
      { label: 'Unassigned sleeves', result: unassigned + ' / ' + (unassigned === 0 ? 'PASS' : 'FAIL'), ok: unassigned === 0 }
    ];
    var allOk = checks.every(function (a) { return a.ok; });

    // Zacks screen: market cap > $100B and Zacks Rank <= 3; Tier 1 = Rank 1-2.
    var snap = window.ZACKS_SNAPSHOT;
    var zAsOf = parseIso(snap && snap.asOf);
    var pubTime = pd ? Date.UTC(pd.y, pd.mo, pd.d) : (zAsOf ? Date.UTC(zAsOf.y, zAsOf.mo, zAsOf.d) : Date.now());
    var SCR = {
      'TIER 1': ['#dcebe1', '#1f5a3c'], 'PASS': ['#eceae4', '#3a3d45'], 'REVIEW': ['#f5dccd', '#843710'],
      'ETF': ['#e1e6f0', '#1d2b4a'], 'NO DATA': ['#f2d6d7', '#861c22']
    };
    var counts = { 'TIER 1': 0, 'PASS': 0, 'REVIEW': 0, 'ETF': 0, 'NO DATA': 0 };
    var reviews = [], soon = [], aliases = [];
    var zRows = hs.filter(function (x) { return x.ticker; }).map(function (x) {
      var z = zacksFor(x.ticker), screen, rankLabel = '—', cap = '—', er = '—', capBad = false, erSoon = false;
      if (!z) screen = 'NO DATA';
      else if (z.etf) {
        screen = 'ETF';
        rankLabel = z.rank ? 'ETF ' + z.rank + ' · ' + z.text : 'ETF · unranked';
      } else {
        rankLabel = z.rank + ' · ' + z.text;
        cap = '$' + (z.cap / 1000).toFixed(z.cap < 1000000 ? 2 : 0) + 'B';
        capBad = z.cap <= 100000;
        var e = parseIso(z.er);
        if (e) {
          er = MONTHS_T[e.mo] + ' ' + e.d;
          var days = (Date.UTC(e.y, e.mo, e.d) - pubTime) / 86400000;
          erSoon = days >= -7 && days <= 21;
          if (erSoon) soon.push(x.ticker + ' ' + er);
        }
        var why = [];
        if (capBad) why.push('cap ' + cap);
        if (z.rank > 3) why.push('Rank ' + z.rank + ' ' + z.text);
        if (why.length) { screen = 'REVIEW'; reviews.push(x.ticker + ' (' + why.join(', ') + ')'); }
        else screen = z.rank <= 2 ? 'TIER 1' : 'PASS';
      }
      if (z && z.key !== x.ticker) aliases.push(x.ticker + ' is listed by Zacks as ' + z.key + '.');
      counts[screen]++;
      return { ticker: x.ticker, rankLabel: rankLabel, cap: cap, er: er, screen: screen, bg: SCR[screen][0], fg: SCR[screen][1],
        capColor: capBad ? WARN : '#1a1d24', erColor: erSoon ? WARN : '#3a3d45' };
    });
    var zHalf = Math.ceil(zRows.length / 2);
    var zk = {
      asOf: zAsOf ? zAsOf.d + ' ' + MONTHS_T[zAsOf.mo] + ' ' + zAsOf.y : 'not loaded',
      asOfUpper: zAsOf ? zAsOf.d + ' ' + MONTHS[zAsOf.mo] + ' ' + zAsOf.y : 'NOT LOADED',
      matched: zRows.length - counts['NO DATA'], counts: counts,
      tiles: ['TIER 1', 'PASS', 'REVIEW', 'ETF'].map(function (k) { return { label: k, n: counts[k], bg: SCR[k][0], fg: SCR[k][1] }; }),
      cols: [zRows.slice(0, zHalf), zRows.slice(zHalf)],
      reviewText: reviews.length ? reviews.join('; ') + '.' : 'none.',
      soonText: soon.length ? soon.join(', ') + '.' : 'none.',
      aliasText: aliases.join(' ')
    };
    var zOk = counts.REVIEW === 0 && counts['NO DATA'] === 0;

    // Screen exceptions are flagged in amber but do not block publication:
    // the framework may keep names the screen would drop.
    var assertions = checks.map(function (a) { return { label: a.label, result: a.result, color: a.ok ? PASS : FAIL }; })
      .concat([{ label: 'Zacks screen exceptions', result: (counts.REVIEW + counts['NO DATA']) + ' / ' + (zOk ? 'PASS' : 'REVIEW'), color: zOk ? PASS : WARN }])
      .concat(pipes(d.disclosures).map(function (p) { return { label: p[0], result: p[1] || '', color: '#3a3d45' }; }));
    var cert = allOk ? { label: 'PUBLISHED / FROZEN', color: PASS } : { label: 'HOLD · CONTROLS FAILING', color: FAIL };

    var components = (d.components || []).map(function (k) {
      var s = Math.max(0, Math.min(10, num(k.score)));
      var col = s >= 7 ? '#2f6f4f' : s >= 5 ? '#b08314' : s >= 3 ? '#c2571a' : '#a3262a';
      return { name: k.name, score: s, pct: s * 10, color: col };
    });

    return {
      d: d, m: m, zone: zone, rows: rows, matrixPages: matrixPages, sleeveAlloc: sleeveAlloc, top10: top10,
      stats: { count: hs.length, totalFmt: total.toFixed(2) + '%', totalOk: totalOk },
      assertions: assertions, cert: cert, zk: zk, components: components,
      compass: [{ label: 'CURRENT COMPOSITE', value: c + ' / 100', note: (d.compositeChange || '0') + ' w/w' }]
        .concat(COMPASS.map(function (x) { return { label: x[0], value: d[x[1]], note: d[x[2]] }; })),
      tape: pipes(d.tape).map(function (p) { return { label: p[0], value: p[1] || '' }; }),
      interpretation: lines(d.interpretation),
      execParas: [
        ['Portfolio posture:', d.execPosture], ['Implementation:', d.execImplementation],
        ['Incremental capital:', d.execIncremental], ['Control boundary:', d.execControl]
      ],
      macro: [
        ['RATES & LIQUIDITY', d.macroRates], ['INFLATION', d.macroInflation], ['CREDIT & STRESS', d.macroCredit],
        ['EARNINGS', d.macroEarnings], ['GEOPOLITICS / OIL', d.macroGeo]
      ],
      events: pipes(d.events),
      hierarchy: lines(d.hierarchy),
      deliverables: lines(d.deliverables), sources: lines(d.sources)
    };
  }

  var COMPASS = [
    ['DELTA / GAMMA', 'deltaGamma', 'deltaNote'], ['FED RANGE', 'fedRange', 'fedNote'],
    ['HY OAS', 'hyOas', 'hyNote'], ['10Y UST', 'tenY', 'tenYNote'], ['VIX', 'vix', 'vixNote']
  ];

  var TEXT_FIELDS = {
    signals: [
      ['tape', 'Weekly risk tape', 6, 'One per line: Label | Value'],
      ['interpretation', 'Signal interpretation', 6, 'One bullet per line'],
      ['decisionRule', 'Decision rule', 5],
      ['officialPosture', 'Official posture', 2]
    ],
    narrative: [
      ['headline', 'Posture headline', 2], ['subhead', 'Posture sub-line', 3],
      ['execPosture', 'Exec summary · Portfolio posture', 4], ['execImplementation', 'Exec summary · Implementation', 4],
      ['execIncremental', 'Exec summary · Incremental capital', 3], ['execControl', 'Exec summary · Control boundary', 3],
      ['footnote', 'Page 1 footnote', 2],
      ['macroRates', 'Macro · Rates & liquidity', 4], ['macroInflation', 'Macro · Inflation', 3],
      ['macroCredit', 'Macro · Credit & stress', 3], ['macroEarnings', 'Macro · Earnings', 3],
      ['macroGeo', 'Macro · Geopolitics / oil', 3],
      ['clientBrief', 'Client executive brief', 6]
    ],
    controls: [
      ['gatesWeek', 'Event gates heading', 1],
      ['events', 'Forward event gates', 4, 'One per line: DATE | Event | Action'],
      ['hierarchy', 'Capital deployment hierarchy', 5, 'One tier per line, in priority order'],
      ['reconciliation', 'MRGES-001 channel reconciliation', 4],
      ['bandStandard', 'Target / band standard', 4],
      ['strategicTarget', 'Frozen Strategic Anchors total (%)', 1, 'Control check compares the sleeve total to this'],
      ['matrixDisclaimer', 'Holding matrix disclaimer', 3],
      ['deliverables', 'Frozen deliverables applied', 5, 'One per line'],
      ['disclosures', 'Disclosed control items', 4, 'One per line: Label | Result'],
      ['sources', 'Primary evidence & sources', 8, 'One per line'],
      ['freshness', 'Data-freshness certification', 4]
    ]
  };

  // ---------- panel ----------
  function textField(f) {
    var d = state.doc;
    return '<label class="fld">' + h(f[1]) + (f[3] ? '<span class="hint">' + h(f[3]) + '</span>' : '') +
      '<textarea rows="' + f[2] + '" data-k="' + f[0] + '">' + h(d[f[0]]) + '</textarea></label>';
  }

  function options(list, cur, key, label) {
    return list.map(function (o) {
      var v = key ? o[key] : o, t = label ? o[label] : o;
      return '<option value="' + h(v) + '"' + (v === cur ? ' selected' : '') + '>' + h(t) + '</option>';
    }).join('');
  }

  function renderTabBody() {
    var d = state.doc, out = '';
    if (state.tab === 'holdings') {
      out += '<div class="row-between small"><span id="stat-line"></span><strong id="stat-check"></strong></div>' +
        '<p class="note">Current = executable target (from the CSV). MFPDF = frozen analytical baseline. Bands are 75–125% of Current, floored at 1.00% and capped at 4.00%.</p>';
      d.holdings.forEach(function (x, i) {
        out += '<div class="hold">' +
          '<div class="hold-a">' +
          '<label>Ticker<input class="mono" data-row="' + i + '" data-f="ticker" value="' + h(x.ticker) + '"></label>' +
          '<label>Sleeve<select data-row="' + i + '" data-f="sleeve">' + options(SLEEVES, x.sleeve, 'key', 'name') + '</select></label>' +
          '<label>MFPDF %<input type="number" step="0.01" data-row="' + i + '" data-f="mfpdf" value="' + h(x.mfpdf) + '"></label>' +
          '<label>Current %<input type="number" step="0.01" data-row="' + i + '" data-f="current" value="' + h(x.current) + '"></label>' +
          '<button type="button" class="x" data-action="remove" data-row="' + i + '" aria-label="Remove ' + h(x.ticker) + '">' +
          '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M3 3l8 8M11 3l-8 8"/></svg></button>' +
          '</div><div class="hold-b">' +
          '<label>Guidance<select data-row="' + i + '" data-f="guidance">' + options(GUIDANCE, x.guidance) + '</select></label>' +
          '<label>Rationale<input data-row="' + i + '" data-f="rationale" value="' + h(x.rationale) + '"></label>' +
          '<label>Status<input data-row="' + i + '" data-f="status" value="' + h(x.status) + '"></label>' +
          '</div></div>';
      });
      out += '<button type="button" class="add" data-action="add">Add holding</button>';
    } else if (state.tab === 'signals') {
      out += '<div class="grid2">' +
        '<label class="fld">Composite (0–100)<input type="number" min="0" max="100" data-k="composite" value="' + h(d.composite) + '"></label>' +
        '<label class="fld">Change w/w<input data-k="compositeChange" value="' + h(d.compositeChange) + '"></label></div>' +
        '<div class="small">Gauge zone: <span id="zone-chip" class="chip"></span></div>' +
        '<div class="sub">Institutional compass</div>';
      COMPASS.forEach(function (x) {
        out += '<div class="compass-row"><span>' + h(x[0]) + '</span>' +
          '<input data-k="' + x[1] + '" value="' + h(d[x[1]]) + '" aria-label="' + h(x[0]) + ' value">' +
          '<input data-k="' + x[2] + '" value="' + h(d[x[2]]) + '" aria-label="' + h(x[0]) + ' note"></div>';
      });
      out += '<div class="sub">Component scores (0–10)</div><div class="grid2">';
      d.components.forEach(function (k, i) {
        out += '<label class="comp">' + h(k.name) + '<input type="number" min="0" max="10" data-comp="' + i + '" value="' + h(k.score) + '"></label>';
      });
      out += '</div>' + TEXT_FIELDS.signals.map(textField).join('');
    } else {
      out += TEXT_FIELDS[state.tab].map(textField).join('');
    }
    return out;
  }

  function renderPanel() {
    var tabs = [['holdings', 'Holdings'], ['signals', 'Signals'], ['narrative', 'Narrative'], ['controls', 'Controls & sources']];
    document.getElementById('week-ending').value = state.doc.weekEnding;
    document.getElementById('pub-date').value = state.doc.pubDate;
    document.getElementById('tabs').innerHTML = tabs.map(function (t) {
      return '<button type="button" data-action="tab" data-tab="' + t[0] + '" aria-pressed="' + (state.tab === t[0]) + '">' + t[1] + '</button>';
    }).join('');
    document.getElementById('tab-body').innerHTML = renderTabBody();
    var msg = document.getElementById('import-msg');
    msg.hidden = !state.importMsg;
    msg.textContent = state.importMsg;
    msg.className = 'import-msg ' + (state.importOk ? 'ok' : 'warn');
  }

  // ---------- report ----------
  function foot(n, m, left) {
    return '<div class="foot"><span>' + (left || 'MANIFEST MWIR') + '</span><span>WEEK ENDING ' + h(m.weekUpper) + ' · ' + n + '/8</span></div>';
  }
  function head(kicker, title, extra) {
    return '<div class="head"><div class="kicker">' + kicker + '</div><h2>' + title + '</h2>' + (extra || '') + '</div>';
  }

  function renderReport(v) {
    var d = v.d, m = v.m, out = '';

    // 1 · cover
    out += '<section class="sheet"><div class="row-between kicker"><span>OFFICIAL PUBLICATION · FROZEN DELIVERABLES</span><span>PUBLISHED ' + h(m.pubLong) + '</span></div>' +
      '<div class="cover-head"><h2 class="big">Weekly Institutional Report</h2><div class="headline">' + h(d.headline) + '</div><div class="subhead">' + h(d.subhead) + '</div></div>' +
      '<div class="cover-grid"><div class="card gauge"><div class="label">MANIFEST INSTITUTIONAL GAUGE</div>' +
      '<svg width="260" height="140" viewBox="0 0 260 140" role="img" aria-label="Composite gauge at ' + v.zone.value + ' of 100">' +
      '<path d="M30 120 A100 100 0 0 1 99.10 24.89" stroke="#a3262a" stroke-width="22" fill="none"/>' +
      '<path d="M99.10 24.89 A100 100 0 0 1 145.64 21.23" stroke="#c2571a" stroke-width="22" fill="none"/>' +
      '<path d="M145.64 21.23 A100 100 0 0 1 188.78 39.10" stroke="#c9971c" stroke-width="22" fill="none"/>' +
      '<path d="M188.78 39.10 A100 100 0 0 1 230 120" stroke="#2f6f4f" stroke-width="22" fill="none"/>' +
      '<g transform="rotate(' + v.zone.deg + ' 130 120)"><path d="M130 120 L126 118 L130 34 L134 118 Z" fill="#1a1d24"/></g>' +
      '<circle cx="130" cy="120" r="8" fill="#1a1d24"/></svg>' +
      '<div class="score">' + v.zone.value + '</div><div class="zone" style="background:' + v.zone.color + '">' + h(v.zone.label) + '</div></div>' +
      '<div class="card compass"><div class="label pad">INSTITUTIONAL COMPASS</div>' +
      v.compass.map(function (c) { return '<div class="compass-line"><span>' + h(c.label) + '</span><span class="mono val">' + h(c.value) + '</span><span class="muted">' + h(c.note) + '</span></div>'; }).join('') +
      '</div></div>' +
      '<div class="exec"><h3 class="kicker">EXECUTIVE SUMMARY</h3><div class="grid2 gap28">' +
      v.execParas.map(function (p) { return '<p><strong>' + h(p[0]) + '</strong> ' + h(p[1]) + '</p>'; }).join('') +
      '</div></div><div class="fine">' + h(d.footnote) + '</div>' + foot(1, m) + '</section>';

    // 2 · signals
    out += '<section class="sheet">' + head('MFSO COMPONENT ARCHITECTURE', 'Institutional Signal Dashboard') +
      '<div><h3 class="label">COMPONENT SCORES · 0–10</h3><div class="grid2 gap40">' +
      v.components.map(function (c) { return '<div class="bar-row"><span>' + h(c.name) + '</span><div class="track"><div style="width:' + c.pct + '%;background:' + c.color + '"></div></div><span class="mono num">' + c.score + '</span></div>'; }).join('') +
      '</div></div><div class="tape-grid"><div><h3 class="label">WEEKLY RISK TAPE</h3><div class="tape">' +
      v.tape.map(function (t) { return '<div><span>' + h(t.label) + '</span><span class="mono">' + h(t.value) + '</span></div>'; }).join('') +
      '</div></div><div><h3 class="label">SIGNAL INTERPRETATION</h3><ul>' +
      v.interpretation.map(function (b) { return '<li>' + h(b) + '</li>'; }).join('') +
      '</ul></div></div><div class="box"><div class="kicker">DECISION RULE</div><div>' + h(d.decisionRule) + '</div></div>' +
      '<div class="posture"><span>OFFICIAL POSTURE</span><strong>' + h(d.officialPosture) + '</strong></div>' + foot(2, m) + '</section>';

    // 3 · macro
    out += '<section class="sheet">' + head('RATES · INFLATION · EARNINGS · GEOPOLITICS', 'Macro Stewardship &amp; Event Map') +
      '<div class="grid2 gap32 grow">' +
      v.macro.map(function (s) { return '<div class="macro"><h3>' + h(s[0]) + '</h3><p>' + h(s[1]) + '</p></div>'; }).join('') +
      '</div><div><h3 class="kicker">FORWARD EVENT GATES · ' + h(d.gatesWeek) + '</h3><div class="events">' +
      v.events.map(function (e) { return '<div><span class="mono">' + h(e[0]) + '</span><strong>' + h(e[1] || '') + '</strong><span>' + h(e[2] || '') + '</span></div>'; }).join('') +
      '</div></div>' + foot(3, m) + '</section>';

    // 4 · allocation
    out += '<section class="sheet">' + head('MFPDF BASELINE · MRGES-001 EXECUTABLE CHANNEL', 'Allocation &amp; Implementation Dashboard') +
      '<div class="alloc-grid"><div><h3 class="label">EXECUTABLE SLEEVE ALLOCATION · ' + h(v.stats.totalFmt) + '</h3>' +
      v.sleeveAlloc.map(function (s) { return '<div class="sleeve-row"><span>' + h(s.name) + '</span><div class="track t14"><div style="width:' + s.bar + '%;background:#1d2b4a"></div></div><span class="mono num">' + s.fmt + '</span></div>'; }).join('') +
      '</div><div><h3 class="label">TOP 10 EXECUTABLE TARGETS</h3><div class="t10 th"><span>TICKER</span><span class="r">TARGET</span><span class="r">APPROVED BAND</span></div>' +
      v.top10.map(function (t) { return '<div class="t10 mono"><span class="tick">' + h(t.ticker) + '</span><span class="r">' + t.currentFmt + '</span><span class="r muted">' + t.band + '</span></div>'; }).join('') +
      '</div></div><div class="grid2 gap24"><div class="box"><div class="kicker">MRGES-001 CHANNEL RECONCILIATION</div><div class="s12">' + h(d.reconciliation) + '</div></div>' +
      '<div class="box"><div class="kicker">TARGET / BAND STANDARD</div><div class="s12">' + h(d.bandStandard) + '</div></div></div>' +
      '<div class="grow"><h3 class="kicker">CAPITAL DEPLOYMENT HIERARCHY</h3>' +
      v.hierarchy.map(function (t, i) { return '<div class="tier"><span>' + (i + 1) + '</span><span>' + h(t) + '</span></div>'; }).join('') +
      '</div>' + foot(4, m) + '</section>';

    // 5-6 · holding matrix
    v.matrixPages.forEach(function (pg) {
      out += '<section class="sheet">' + head('HOLDING-BY-HOLDING WEIGHT GUIDANCE', 'Holding Action Matrix · ' + pg.roman,
        '<div class="muted s12">MFPDF = frozen analytical baseline. Current = MRGES executable recommendation. Actual = not supplied.</div>') +
        '<div class="grow"><div class="mx th"><span>SLEEVE</span><span>TICKER</span><span class="r">MFPDF</span><span class="r">CURRENT</span><span class="r">BAND</span><span>GUIDANCE</span><span>RATIONALE</span><span>STATUS</span></div>' +
        pg.rows.map(function (r) {
          return '<div class="mx"><span class="muted">' + h(r.sleeve) + '</span><span class="mono tick">' + h(r.ticker) + '</span><span class="mono r muted">' + r.mfpdfFmt + '</span><span class="mono r">' + r.currentFmt + '</span><span class="mono r">' + r.band + '</span>' +
            '<span class="tag" style="background:' + r.chipBg + ';color:' + r.chipFg + '">' + h(r.guidance) + '</span><span class="ell">' + h(r.rationale) + '</span><span class="s11">' + h(r.status) + '</span></div>';
        }).join('') +
        '</div><div class="fine">' + h(d.matrixDisclaimer) + '</div>' + foot(pg.num, m) + '</section>';
    });

    // 7 · Zacks screen
    var zk = v.zk;
    out += '<section class="sheet"><div class="head row-between end"><div><div class="kicker">ZACKS UNIVERSE SCREEN · DATA AS OF ' + h(zk.asOfUpper) + '</div><h2>Holdings Validation Screen</h2>' +
      '<div class="muted s12">Rule: market cap above $100B and Zacks Rank 1–3 (1 Strong Buy · 2 Buy · 3 Hold). Tier 1 = Rank 1 or 2. ETFs show their ETF rank and are not held to the market-cap rule.</div></div>' +
      '<div class="tiles">' + zk.tiles.map(function (t) { return '<div style="background:' + t.bg + ';color:' + t.fg + '"><strong>' + t.n + '</strong><span>' + t.label + '</span></div>'; }).join('') + '</div></div>' +
      '<div class="grid2 gap28 grow">' + zk.cols.map(function (col) {
        return '<div><div class="zr th"><span>TICKER</span><span>ZACKS RANK</span><span class="r">MKT CAP</span><span class="r">NEXT ER</span><span>SCREEN</span></div>' +
          col.map(function (z) {
            return '<div class="zr"><span class="mono tick">' + h(z.ticker) + '</span><span class="ell">' + h(z.rankLabel) + '</span><span class="mono r" style="color:' + z.capColor + '">' + h(z.cap) + '</span>' +
              '<span class="mono r" style="color:' + z.erColor + '">' + h(z.er) + '</span><span class="tag s10" style="background:' + z.bg + ';color:' + z.fg + '">' + z.screen + '</span></div>';
          }).join('') + '</div>';
      }).join('') + '</div>' +
      '<div class="box s12"><div><strong class="warn">Review:</strong> ' + h(zk.reviewText) + '</div><div><strong>Earnings within 21 days of publication:</strong> ' + h(zk.soonText) + '</div>' +
      '<div class="muted">A name under review is flagged, not dropped automatically. Framework overrides still apply. ' + h(zk.aliasText) + '</div></div>' +
      foot(7, m, 'MANIFEST MWIR · SOURCE: ZACKS INVESTMENT RESEARCH') + '</section>';

    // 8 · certification
    out += '<section class="sheet cert-page">' + head('PUBLICATION CONTROL RECORD', 'Certification, Client Brief &amp; Sources') +
      '<div class="box"><div class="kicker">CLIENT EXECUTIVE BRIEF</div><div>' + h(d.clientBrief) + '</div></div>' +
      '<div class="grid3 grow"><div><h3 class="label">FROZEN DELIVERABLES APPLIED</h3>' +
      v.deliverables.map(function (x) { return '<div class="li">' + h(x) + '</div>'; }).join('') +
      '<div class="label mt">CERTIFICATION RESULT</div><div class="cert" style="color:' + v.cert.color + '">' + v.cert.label + '</div></div>' +
      '<div><h3 class="label">CONTROL ASSERTIONS</h3>' +
      v.assertions.map(function (a) { return '<div class="li row-between"><span>' + h(a.label) + '</span><span class="mono r" style="color:' + a.color + '">' + h(a.result) + '</span></div>'; }).join('') +
      '</div><div><h3 class="label">PRIMARY EVIDENCE &amp; MARKET SOURCES</h3>' +
      v.sources.map(function (x) { return '<div class="li">' + h(x) + '</div>'; }).join('') +
      '</div></div><div class="s12"><strong>DATA-FRESHNESS CERTIFICATION:</strong> ' + h(d.freshness) + '</div>' +
      '<div class="muted s12">Prepared for Manifest Institutional Investment System · Publication date: ' + h(m.pubShort) + '</div>' + foot(8, m) + '</section>';

    return out;
  }

  // Updates everything that depends on values without rebuilding the input panel (keeps focus).
  function renderLive() {
    var v = model();
    document.getElementById('report').innerHTML = renderReport(v);
    var zk = v.zk, c = zk.counts;
    document.getElementById('zk-asof').textContent = 'Zacks data · as of ' + zk.asOf;
    document.getElementById('zk-matched').textContent = zk.matched + '/' + v.stats.count + ' matched';
    document.getElementById('zk-counts').innerHTML = 'Tier 1 <strong>' + c['TIER 1'] + '</strong> · Pass <strong>' + c.PASS +
      '</strong> · Review <strong class="warn">' + c.REVIEW + '</strong> · ETF <strong>' + c.ETF + '</strong> · No data <strong>' + c['NO DATA'] + '</strong>';
    var sl = document.getElementById('stat-line');
    if (sl) {
      sl.innerHTML = '<strong>' + v.stats.count + '</strong> positions · total <strong>' + v.stats.totalFmt + '</strong>';
      var sc = document.getElementById('stat-check');
      sc.textContent = v.stats.totalOk ? 'Sums to 100%' : 'Does not sum to 100%';
      sc.style.color = v.stats.totalOk ? PASS : FAIL;
    }
    var zc = document.getElementById('zone-chip');
    if (zc) { zc.textContent = v.zone.label; zc.style.background = v.zone.color; }
  }

  function renderAll() { renderPanel(); renderLive(); }

  // ---------- CSV import ----------
  function importCsv(text) {
    var rows = parseCsv(text);
    if (!rows.length) { state.importMsg = 'The file is empty.'; state.importOk = false; return; }
    var head = rows[0].map(function (x) { return x.trim().toLowerCase(); });
    var iSym = head.indexOf('symbol'); if (iSym < 0) iSym = head.indexOf('ticker');
    var iW = head.indexOf('weights'); if (iW < 0) iW = head.indexOf('weight');
    var iD = head.indexOf('date');
    if (iSym < 0 || iW < 0) { state.importMsg = 'Could not find Symbol and Weights columns in the header row.'; state.importOk = false; return; }
    var parsed = [], date = null;
    for (var r = 1; r < rows.length; r++) {
      var sym = (rows[r][iSym] || '').trim().toUpperCase();
      var w = parseFloat(rows[r][iW]);
      if (!sym || !isFinite(w)) continue;
      parsed.push({ ticker: sym, w: w });
      if (!date && iD >= 0 && rows[r][iD]) date = rows[r][iD].trim();
    }
    if (!parsed.length) { state.importMsg = 'No holdings rows found under the header.'; state.importOk = false; return; }
    var decimal = parsed.every(function (p) { return p.w <= 1; });
    var prior = {};
    state.doc.holdings.forEach(function (x) { prior[x.ticker] = x; });
    var added = [], seen = {};
    var holdings = parsed.map(function (p) {
      var cur = (decimal ? p.w * 100 : p.w).toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
      seen[p.ticker] = true;
      var old = prior[p.ticker];
      if (old) return Object.assign({}, old, { current: cur });
      added.push(p.ticker);
      return { ticker: p.ticker, sleeve: 'Unassigned', mfpdf: cur, current: cur, guidance: 'MAINTAIN', rationale: '', status: 'EVIDENCE HOLD' };
    });
    var dropped = Object.keys(prior).filter(function (t) { return !seen[t]; });
    state.doc.holdings = holdings;
    var m = date && /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(date);
    if (m) {
      state.doc.weekEnding = m[3] + '-' + ('0' + m[1]).slice(-2) + '-' + ('0' + m[2]).slice(-2);
      state.doc.pubDate = new Date(Date.UTC(+m[3], +m[1] - 1, +m[2] + 3)).toISOString().slice(0, 10);
    }
    save();
    var total = holdings.reduce(function (s, x) { return s + num(x.current); }, 0);
    var msg = 'Loaded ' + holdings.length + ' holdings' + (date ? ' dated ' + date : '') + ' · total ' + total.toFixed(2) + '%.';
    if (added.length) msg += '\nNew (set sleeve + rationale): ' + added.join(', ');
    if (dropped.length) msg += '\nDropped vs prior: ' + dropped.join(', ');
    state.importMsg = msg;
    state.importOk = !added.length;
  }

  // ---------- events ----------
  function onEdit(e) {
    var t = e.target, d = state.doc;
    if (t.dataset.k) d[t.dataset.k] = t.value;
    else if (t.dataset.row !== undefined && t.dataset.f) {
      var i = +t.dataset.row;
      d.holdings[i] = Object.assign({}, d.holdings[i]);
      d.holdings[i][t.dataset.f] = t.dataset.f === 'ticker' ? t.value.toUpperCase() : t.value;
    } else if (t.dataset.comp !== undefined) {
      d.components[+t.dataset.comp] = Object.assign({}, d.components[+t.dataset.comp], { score: t.value });
    } else return;
    save();
    renderLive();
  }

  function onClick(e) {
    var b = e.target.closest('[data-action]');
    if (!b) return;
    var a = b.dataset.action, d = state.doc;
    if (a === 'tab') state.tab = b.dataset.tab;
    else if (a === 'remove') { d.holdings.splice(+b.dataset.row, 1); save(); }
    else if (a === 'add') { d.holdings.push({ ticker: '', sleeve: 'Unassigned', mfpdf: '0', current: '0', guidance: 'MAINTAIN', rationale: '', status: 'EVIDENCE HOLD' }); save(); }
    else if (a === 'reset') { state.doc = seedDoc(); state.importMsg = 'Reset to the 28 Aug 2026 example.'; state.importOk = true; save(); }
    else if (a === 'print') { window.print(); return; }
    renderAll();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.getElementById('panel');
    panel.addEventListener('input', onEdit);
    panel.addEventListener('change', function (e) { if (e.target.tagName === 'SELECT') onEdit(e); });
    panel.addEventListener('click', onClick);
    document.getElementById('week-ending').addEventListener('change', function (e) { state.doc.weekEnding = e.target.value; save(); renderLive(); });
    document.getElementById('pub-date').addEventListener('change', function (e) { state.doc.pubDate = e.target.value; save(); renderLive(); });
    document.getElementById('csv').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () { importCsv(String(rd.result || '')); renderAll(); };
      rd.readAsText(f);
      e.target.value = '';
    });
    renderAll();
  });

  // exposed for tests
  window.MWIR = { parseCsv: parseCsv, band: band, model: model, state: state, importCsv: importCsv, seedDoc: seedDoc };
})();
