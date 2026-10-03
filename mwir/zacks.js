// Zacks snapshot used by the MWIR report builder's holdings validation screen.
// Source: Zacks Investment Research (Zacks Data connector), last trade date below.
// Refresh weekly by replacing this file; keep the same shape.
//
// Equity: [zacks rank, rank text, market cap in $M, next expected report date]
// ETF:    { etf: true, rank: ETF rank (0 = unranked), text: rank text }
window.ZACKS_SNAPSHOT = {
  asOf: '2026-09-25',
  // tickers the holdings file uses that Zacks lists under another symbol
  alias: { MMC: 'MRSH' },
  data: {
    COST: [3, 'Hold', 409227, '2026-12-10'],
    JNJ: [3, 'Hold', 653613, '2026-10-13'],
    MSFT: [3, 'Hold', 3832844, '2026-11-04'],
    V: [3, 'Hold', 655564, '2026-10-27'],
    GOOGL: [3, 'Hold', 4206142, '2026-11-04'],
    MA: [3, 'Hold', 497267, '2026-10-29'],
    AAPL: [3, 'Hold', 4977637, '2026-10-29'],
    AMZN: [3, 'Hold', 2693019, '2026-10-29'],
    AVGO: [3, 'Hold', 1684184, '2026-12-10'],
    LLY: [3, 'Hold', 1114058, '2026-10-29'],
    NVDA: [1, 'Strong Buy', 5424187, '2026-11-18'],
    HD: [3, 'Hold', 292523, '2026-11-17'],
    META: [3, 'Hold', 1914858, '2026-11-04'],
    ANET: [1, 'Strong Buy', 260506, '2026-11-03'],
    PANW: [3, 'Hold', 306537, '2026-11-18'],
    AMAT: [2, 'Buy', 384895, '2026-11-12'],
    CSCO: [2, 'Buy', 420674, '2026-11-11'],
    KLAC: [2, 'Buy', 245237, '2026-11-04'],
    MU: [3, 'Hold', 1222319, '2026-09-30'],
    ORCL: [3, 'Hold', 414554, '2026-12-09'],
    TXN: [3, 'Hold', 253947, '2026-10-20'],
    VRT: [2, 'Buy', 97510, '2026-10-28'],
    DHR: [3, 'Hold', 157813, '2026-10-21'],
    RTX: [3, 'Hold', 255265, '2026-10-20'],
    DE: [3, 'Hold', 186165, '2026-11-25'],
    CAT: [2, 'Buy', 377660, '2026-11-04'],
    ETN: [3, 'Hold', 170888, '2026-11-03'],
    GE: [3, 'Hold', 339376, '2026-10-20'],
    PH: [3, 'Hold', 123379, '2026-11-05'],
    TT: [3, 'Hold', 99987, '2026-10-29'],
    UNP: [3, 'Hold', 162652, '2026-10-22'],
    CME: [4, 'Sell', 95101, '2026-10-21'],
    MRSH: [3, 'Hold', 81660, '2026-10-15'],
    GS: [3, 'Hold', 272376, '2026-10-13'],
    JPM: [3, 'Hold', 911917, '2026-10-13'],
    SYK: [3, 'Hold', 104470, '2026-10-29'],
    LNG: [3, 'Hold', 55463, '2026-10-29'],
    XOM: [3, 'Hold', 665637, '2026-10-30'],
    CVX: [3, 'Hold', 403946, '2026-10-30'],
    VFH: { etf: true, rank: 3, text: 'Hold' },
    VHT: { etf: true, rank: 1, text: 'Strong Buy' },
    VPU: { etf: true, rank: 2, text: 'Buy' },
    VDE: { etf: true, rank: 1, text: 'Strong Buy' },
    JEPI: { etf: true, rank: 0, text: '' },
    JEPQ: { etf: true, rank: 0, text: '' }
  }
};
