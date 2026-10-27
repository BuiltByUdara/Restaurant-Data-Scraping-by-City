import json
from urllib.parse import urlencode

API = 'https://data.brreg.no/enhetsregisteret/api/enheter'


def resolve_city(client, city):
    """Resolve municipality names exactly, or use a postal town for other cities."""
    page = 0
    while True:
        body, _, _ = client.get(f'{API.rsplit("/", 1)[0]}/kommuner?size=100&page={page}')
        payload = json.loads(body)
        for municipality in payload.get('_embedded', {}).get('kommuner', []):
            if municipality['navn'].casefold() == city.strip().casefold():
                return {'beliggenhetsadresse.kommunenummer': municipality['nummer']}
        if page + 1 >= payload.get('page', {}).get('totalPages', 1):
            return {'beliggenhetsadresse.poststed': city.strip().upper()}
        page += 1


def get_companies(client, codes=('56.1',), municipality=None, limit=100, city=None):
    """Yield registry entities; fail explicitly instead of silently truncating at 10k."""
    page, emitted = 0, 0
    size = min(100, limit)
    collection = 'underenheter' if city else 'enheter'
    endpoint = API.rsplit('/', 1)[0] + '/' + collection
    city_filter = resolve_city(client, city) if city else {}
    while emitted < limit:
        if (page + 1) * size > 10000:
            raise ValueError('Registry pagination limit: narrow by municipality or use a local registry export')
        params = {'naeringskode': ','.join(codes), 'page': page, 'size': size}
        params.update(city_filter)
        if municipality:
            params['kommunenummer'] = municipality
        body, _, _ = client.get(endpoint + '?' + urlencode(params), max_bytes=10_000_000)
        payload = json.loads(body)
        entities = payload.get('_embedded', {}).get(collection, [])
        for company in entities:
            company['registry_source'] = endpoint + '/' + str(company['organisasjonsnummer'])
            yield company
            emitted += 1
            if emitted >= limit:
                return
        if not entities or page + 1 >= payload.get('page', {}).get('totalPages', page + 1):
            return
        page += 1
