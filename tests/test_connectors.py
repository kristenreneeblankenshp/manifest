"""Tests for the data connectors (no network: HTTP calls are replaced by fakes)."""

import datetime as dt
import unittest

from manifest_workbench import store as ST
from manifest_workbench.connectors import ConnectorError, _redact, research, weights, zacks
from manifest_workbench.engine import Workbench

TODAY = dt.date(2026, 9, 29)


def fresh():
    return ST.seed_store()


class ZacksApiTest(unittest.TestCase):
    def configured(self, **settings):
        store = fresh()
        store['settings'].update({'zacks_url': 'https://zacks.example/v1/rank?symbol={ticker}',
                                  'zacks_api_key': 'SECRET'}, **settings)
        return store

    def test_requires_endpoint_and_key(self):
        with self.assertRaisesRegex(ConnectorError, 'not configured'):
            zacks.fetch(fresh(), ['MU'], get_json=lambda u, h: {})
        store = fresh()
        store['settings']['zacks_url'] = 'https://zacks.example/{ticker}'
        with self.assertRaisesRegex(ConnectorError, 'API key'):
            zacks.fetch(store, ['MU'], get_json=lambda u, h: {})

    def test_query_key_and_field_mapping(self):
        calls = []

        def fake(url, headers):
            calls.append((url, headers))
            return {'data': {'rank': '#2 - Buy', 'mktcap': 125300}}
        store = self.configured(zacks_rank_field='data.rank', zacks_market_cap_field='data.mktcap')
        results, errors = zacks.fetch(store, ['MU'], get_json=fake)
        self.assertEqual(errors, [])
        self.assertEqual(results['MU'], {'rank': 2, 'market_cap': 125.3})
        self.assertIn('symbol=MU', calls[0][0])
        self.assertIn('api_key=SECRET', calls[0][0])

    def test_header_key_and_list_response(self):
        seen = {}

        def fake(url, headers):
            seen.update(headers)
            return [{'ticker': 'AAPL', 'zacks_rank': 1, 'market_cap': '3.4T'},
                    {'ticker': 'MU', 'zacks_rank': 4, 'market_cap': '120.5B'}]
        store = self.configured(zacks_auth='header', zacks_key_name='X-API-Key')
        results, _ = zacks.fetch(store, ['MU'], get_json=fake)
        self.assertEqual(seen['X-API-Key'], 'SECRET')
        self.assertEqual(results['MU'], {'rank': 4, 'market_cap': 120.5})

    def test_bad_ticker_reported_not_fatal(self):
        def fake(url, headers):
            if 'ZZZ' in url:
                raise ConnectorError('HTTP 404')
            return {'zacks_rank': 3}
        results, errors = zacks.fetch(self.configured(), ['MU', 'ZZZ'], get_json=fake)
        self.assertIn('MU', results)
        self.assertEqual(errors, ['ZZZ: HTTP 404'])

    def test_run_applies_and_records_rank_change(self):
        store = self.configured()
        rank = {'value': 3}
        zacks.run(store, 'Ada', TODAY, get_json=lambda u, h: {'zacks_rank': rank['value'], 'market_cap': 1000})
        rank['value'] = 5
        summary = zacks.run(store, 'Ada', TODAY, get_json=lambda u, h: {'zacks_rank': rank['value']})
        self.assertIn(('MU', 3, 5), summary['rank_changes'])
        mu = next(r for r in Workbench(store).masr if r.get('ticker') == 'MU')
        self.assertEqual(mu['zacks_rank'], 5)
        ev = [e for e in store['evidence'] if e and e.get('ticker') == 'MU'
              and e.get('activity_type') == 'Zacks Rank Change']
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]['materiality'], 'High')
        self.assertEqual(store['data_log'][-1]['connector'], 'zacks')


class ZacksCsvTest(unittest.TestCase):
    def test_parse_units_and_rank_text(self):
        text = ('Zacks Screen export\n\nTicker,Company,Zacks Rank,Market Cap ($B)\n'
                'MU,Micron,2-Buy,120.5\nAAPL,Apple,#1 Strong Buy,3400\nXYZ,,,\n')
        results, errors = zacks.parse_csv(text)
        self.assertEqual(results['MU'], {'rank': 2, 'market_cap': 120.5})
        self.assertEqual(results['AAPL']['rank'], 1)
        self.assertEqual(errors, ['XYZ: no usable rank or market cap'])

    def test_rejects_unrelated_csv(self):
        with self.assertRaises(ConnectorError):
            zacks.parse_csv('Name,Value\nfoo,1\n')


class WeightsTest(unittest.TestCase):
    def test_percent_column_and_symbol_normalisation(self):
        text = ('Symbol,Description,% of Account\n"BRK/B",Berkshire,"2.50%"\nMSFT,Microsoft,3.1%\n'
                'Cash & Cash Investments,,1.0%\nAccount Total,,100%\n')
        parsed = weights.parse(text)
        self.assertEqual(parsed['basis'], 'weight')
        self.assertAlmostEqual(parsed['weights']['BRK.B'], 0.025)
        self.assertAlmostEqual(parsed['weights']['MSFT'], 0.031)
        self.assertNotIn('CASH', ''.join(parsed['weights']))

    def test_quantity_times_price(self):
        parsed = weights.parse('Ticker,Quantity,Price\nMU,10,100\nMSFT,30,100\n')
        self.assertAlmostEqual(parsed['weights']['MU'], 0.25)
        self.assertAlmostEqual(parsed['weights']['MSFT'], 0.75)

    def test_preview_then_apply(self):
        store = fresh()
        preview = weights.preview(store, 'Symbol,Market Value\nMU,"$1,000"\nTSLA,"$1,000"\n')
        self.assertEqual(preview['matched'], 1)
        self.assertEqual(preview['not_in_portfolio'], ['TSLA'])
        self.assertEqual(len(preview['missing']), len(store['portfolio']) - 1)
        self.assertTrue(all(r.get('actual_weight') in (None, '') for r in store['portfolio']))
        weights.apply(store, preview, 'Ada', TODAY, 'positions.csv')
        mu = next(r for r in store['portfolio'] if r['symbol'] == 'MU')
        self.assertAlmostEqual(mu['actual_weight'], 0.5)
        others = [r['actual_weight'] for r in store['portfolio'] if r['symbol'] != 'MU']
        self.assertTrue(all(w == 0 for w in others))

    def test_rejects_file_without_symbols(self):
        with self.assertRaises(ConnectorError):
            weights.parse('Name,Amount\nfoo,1\n')


class ResearchTest(unittest.TestCase):
    FEED = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><title>8-K - Current report</title><updated>2026-09-28T16:00:00-04:00</updated>'
            '<link href="https://www.sec.gov/{t}/new.htm"/><category term="8-K"/></entry>'
            '<entry><title>8-K - Old</title><updated>2026-08-01T16:00:00-04:00</updated>'
            '<link href="https://www.sec.gov/{t}/old.htm"/><category term="8-K"/></entry></feed>')

    def fake_get(self, url, headers):
        self.headers = headers
        ticker = url.split('CIK=')[1].split('&')[0]
        return self.FEED.replace('{t}', ticker)

    def test_requires_sec_contact(self):
        summary = research.run(fresh(), 'Ada', TODAY, get=self.fake_get, tickers=['MU', 'MSFT'])
        self.assertEqual(summary['added'], 0)
        self.assertEqual(len(summary['errors']), 1)  # stops after the first contact error
        self.assertIn('contact e-mail', summary['errors'][0])

    def test_pull_filters_dedupes_and_prefills_evidence(self):
        store = fresh()
        store['settings'].update({'sec_contact': 'ops@example.com', 'sec_forms': '8-K'})
        summary = research.run(store, 'Ada', TODAY, get=self.fake_get, tickers=['MU'])
        self.assertEqual(summary['added'], 1)  # the August filing is outside the window
        self.assertIn('ops@example.com', self.headers['User-Agent'])
        again = research.run(store, 'Ada', TODAY, get=self.fake_get, tickers=['MU'])
        self.assertEqual(again['added'], 0)
        item = store['inbox'][0]
        self.assertEqual(item['id'], 'INB-20260929-001')
        self.assertEqual(item['status'], 'New')
        values = research.evidence_defaults(store, item, TODAY)
        self.assertEqual(values['ticker'], 'MU')

    def test_etfs_skipped_by_default(self):
        store = fresh()
        store['settings']['sec_contact'] = 'ops@example.com'
        asked = []
        research.run(store, 'Ada', TODAY, get=lambda u, h: asked.append(u) or self.FEED, days=7)
        self.assertFalse(any('CIK=VHT' in u for u in asked))
        self.assertTrue(any('CIK=MU' in u for u in asked))


class RedactTest(unittest.TestCase):
    def test_secrets_masked_in_logged_urls(self):
        red = _redact('https://x.example/rank?symbol=MU&api_key=SECRET&token=abc')
        self.assertNotIn('SECRET', red)
        self.assertNotIn('abc', red)
        self.assertIn('symbol=MU', red)


if __name__ == '__main__':
    unittest.main()
