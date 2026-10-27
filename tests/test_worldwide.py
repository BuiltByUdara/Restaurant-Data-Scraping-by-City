import json
import tempfile
import unittest

from norway_restaurants.worldwide import locate_city, build_query, convert_restaurant
from norway_restaurants.deduplicate import deduplicate


class WorldwideTests(unittest.TestCase):
    def test_alias_country_and_cache(self):
        class Fake:
            delay = 0
            calls = []
            def get(self, url):
                self.calls.append(url)
                return json.dumps([{'display_name': 'Lisboa, Portugal'}]), url, 'application/json'
        client = Fake()
        with tempfile.TemporaryDirectory() as cache:
            locate_city(client, 'Lisban', 'PT', cache)
            locate_city(client, 'Lisban', 'PT', cache)
        self.assertEqual(len(client.calls), 1)
        self.assertIn('q=Lisbon', client.calls[0])
        self.assertIn('countrycodes=pt', client.calls[0])
        self.assertEqual(client.delay, 1)

    def test_area_and_bbox(self):
        query, _ = build_query({'osm_type': 'relation', 'osm_id': 123})
        self.assertIn('(area:3600000123)', query)
        query, boundary = build_query({'osm_type': 'node', 'boundingbox': ['1', '2', '3', '4']})
        self.assertIn('(1.0,3.0,2.0,4.0)', query)
        self.assertIn('bounding box', boundary)

    def test_real_fields_no_invented_org_number(self):
        place = {'address': {'city': 'Lisboa', 'country': 'Portugal'}}
        first = convert_restaurant({'type': 'node', 'id': 10, 'lat': 38, 'lon': -9, 'tags': {'name': 'Test', 'contact:email': 'info@example.com'}}, place)
        second = convert_restaurant({'type': 'way', 'id': 10, 'tags': {}}, place)
        self.assertEqual(first['organisasjonsnummer'], '')
        self.assertEqual(first['epostadresse'], 'info@example.com')
        self.assertEqual(first['latitude'], 38)
        self.assertEqual(len(list(deduplicate([first, first, second]))), 2)
        self.assertEqual(second['epostadresse'], '')
