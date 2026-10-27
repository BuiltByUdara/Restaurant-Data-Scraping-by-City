import csv
import json
from pathlib import Path
import tempfile
import unittest

from norway_restaurants.analyze_website import analyze_website
from norway_restaurants.deduplicate import deduplicate
from norway_restaurants.export_csv import export_csv
from norway_restaurants.filter_restaurants import filter_restaurants, normalize_name
from norway_restaurants.find_emails import find_emails
from norway_restaurants.find_websites import normalize_url
from norway_restaurants.get_companies import get_companies, resolve_city
from norway_restaurants.scrape_websites import scrape_website


class PipelineTests(unittest.TestCase):
    def test_city_uses_physical_establishment_location(self):
        class Fake:
            def __init__(self):
                self.calls = []
            def get(self, url, **kwargs):
                self.calls.append(url)
                if '/kommuner?' in url:
                    payload = {'_embedded': {'kommuner': [{'navn': 'OSLO', 'nummer': '0301'}]}, 'page': {'totalPages': 1}}
                else:
                    payload = {'_embedded': {'underenheter': [{'organisasjonsnummer': '123'}]}, 'page': {'totalPages': 1}}
                return json.dumps(payload), url, 'application/json'
        client = Fake()
        records = list(get_companies(client, city=' oslo ', limit=5))
        self.assertIn('/underenheter?', client.calls[-1])
        self.assertIn('beliggenhetsadresse.kommunenummer=0301', client.calls[-1])
        self.assertTrue(records[0]['registry_source'].endswith('/underenheter/123'))
        self.assertEqual(resolve_city(client, 'Sandvika'), {'beliggenhetsadresse.poststed': 'SANDVIKA'})

    def test_extraction_and_sources(self):
        contacts = find_emails('<script>hidden@example.no</script><a href="mailto:POST%40cafe.no?subject=Hi">Email</a> kari@cafe.no', 'https://cafe.no/kontakt')
        self.assertEqual({c['email'] for c in contacts}, {'post@cafe.no', 'kari@cafe.no'})
        self.assertEqual(next(c for c in contacts if c['email'].startswith('kari'))['classification'], 'review_required')
        self.assertTrue(all(c['source_url'].endswith('/kontakt') for c in contacts))

    def test_filter_and_deduplicate(self):
        row = {'organisasjonsnummer': '1', 'navn': 'CAFÉ AS', 'naeringskode1': {'kode': '56.110'}}
        data = [row, row, {**row, 'organisasjonsnummer': '2', 'konkurs': True}, {**row, 'organisasjonsnummer': '3'}]
        self.assertEqual(len(list(deduplicate(filter_restaurants(data)))), 2)
        self.assertEqual(normalize_name(' CAFÉ AS '), 'café')

    def test_pagination(self):
        class Fake:
            calls = []
            def get(self, url, **kwargs):
                self.calls.append(url)
                return json.dumps({'_embedded': {'enheter': [{'organisasjonsnummer': str(len(self.calls))}]}, 'page': {'totalPages': 2}}), url, 'application/json'
        client = Fake()
        self.assertEqual(len(list(get_companies(client, limit=3))), 2)
        self.assertIn('page=1', client.calls[1])

    def test_unknown_score_and_observed_score(self):
        self.assertIsNone(analyze_website([])['opportunity_score'])
        result = analyze_website([{'url': 'https://cafe.no', 'html': '<meta name="viewport" content="width=device-width">Meny Booking'}])
        self.assertEqual(result['opportunity_score'], 0)

    def test_robots_blocks_pages(self):
        class Fake:
            user_agent = 'test'
            delay = 0
            calls = []
            def get(self, url):
                self.calls.append(url)
                return 'User-agent: *\nDisallow: /', url, 'text/plain'
        client = Fake()
        pages, errors = scrape_website(client, 'https://cafe.no/', 2)
        self.assertEqual(pages, [])
        self.assertEqual(client.calls, ['https://cafe.no/robots.txt'])
        self.assertEqual(len(errors), 2)

    def test_csv_injection_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.csv'
            export_csv([{'name': '=1+1', 'municipality': 'Tromsø'}], path)
            with path.open(encoding='utf-8-sig', newline='') as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row['name'], "'=1+1")
            self.assertEqual(row['municipality'], 'Tromsø')

    def test_urls(self):
        self.assertEqual(normalize_url('www.example.no'), 'https://www.example.no/')
        with self.assertRaises(ValueError):
            normalize_url('file:///tmp/test')


if __name__ == '__main__':
    unittest.main()
