"""Worldwide restaurant discovery from OpenStreetMap, via Nominatim and Overpass."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from .filter_restaurants import normalize_name

ATTRIBUTION = '© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright'


def locate_city(client, city, country=None, cache_dir='output/geocache'):
    city = {'lisban': 'Lisbon'}.get(city.strip().casefold(), city.strip())
    endpoint = os.environ.get('NOMINATIM_URL', 'https://nominatim.openstreetmap.org/search')
    params = {'q': city, 'format': 'jsonv2', 'addressdetails': 1, 'limit': 5, 'featuretype': 'city'}
    if country:
        params['countrycodes'] = country.lower()
    url = endpoint + '?' + urlencode(params)
    cache = Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if cache.exists():
        results = json.loads(cache.read_text(encoding='utf-8'))
    else:
        client.delay = max(1, client.delay)
        body, _, _ = client.get(url)
        results = json.loads(body)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(results, ensure_ascii=False), encoding='utf-8')
    if not results:
        raise ValueError(f'City not found: {city}. Try the official spelling and --country (two-letter country code).')
    place = results[0]
    print(f"Resolved city: {place['display_name']}", flush=True)
    if len(results) > 1:
        print('Using the highest-ranked city match. Use --country or a more specific city name if needed.', flush=True)
    return place


def build_query(place):
    if place.get('osm_type') == 'relation':
        area = 3600000000 + int(place['osm_id'])
        scope = f'(area:{area})'
        boundary = 'administrative area'
    elif place.get('osm_type') == 'way':
        scope = f'(area:{2400000000 + int(place["osm_id"])})'
        boundary = 'mapped area'
    else:
        south, north, west, east = map(float, place['boundingbox'])
        scope = f'({south},{west},{north},{east})'
        boundary = 'bounding box (may include nearby venues)'
    return f'[out:json][timeout:90];nwr["amenity"="restaurant"]{scope};out center tags;', boundary


def convert_restaurant(element, place):
    tags = element.get('tags', {})
    source = f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}'
    center = element.get('center', element)
    address = place.get('address', {})
    name = tags.get('name') or tags.get('name:en', '')
    return {
        'organisasjonsnummer': '',
        'record_id': f'osm:{element["type"]}:{element["id"]}',
        'navn': name, 'normalized_name': normalize_name(name),
        'data_source': 'openstreetmap', 'registry_source': source,
        'hjemmeside': tags.get('contact:website') or tags.get('website', ''),
        'epostadresse': tags.get('contact:email') or tags.get('email', ''),
        'telefon': tags.get('contact:phone') or tags.get('phone', ''),
        'beliggenhetsadresse': {
            'adresse': [tags.get('addr:full') or ' '.join(filter(None, [tags.get('addr:housenumber'), tags.get('addr:street')]))],
            'postnummer': tags.get('addr:postcode', ''),
            'poststed': tags.get('addr:city') or address.get('city') or address.get('town') or place.get('name', ''),
        },
        'country': address.get('country', ''),
        'latitude': center.get('lat', ''), 'longitude': center.get('lon', ''),
        'cuisine': tags.get('cuisine', ''), 'opening_hours': tags.get('opening_hours', ''),
        'wheelchair': tags.get('wheelchair', ''), 'takeaway': tags.get('takeaway', ''),
        'delivery': tags.get('delivery', ''), 'attribution': ATTRIBUTION,
    }


def get_worldwide_restaurants(client, city, country=None, limit=100):
    place = locate_city(client, city, country)
    query, boundary = build_query(place)
    print(f'Searching restaurant records within {boundary}...', flush=True)
    endpoint = os.environ.get('OVERPASS_URL', 'https://overpass-api.de/api/interpreter')
    old_timeout = client.timeout
    client.timeout = 120
    try:
        body, _, _ = client.get(endpoint + '?' + urlencode({'data': query}), max_bytes=50_000_000)
    finally:
        client.timeout = old_timeout
    payload = json.loads(body)
    if payload.get('remark'):
        raise ValueError('Overpass returned an incomplete result: ' + payload['remark'])
    elements = payload.get('elements', [])
    print(f'Found {len(elements)} mapped restaurant records. {ATTRIBUTION}', flush=True)
    for element in elements[:limit]:
        yield convert_restaurant(element, place)
