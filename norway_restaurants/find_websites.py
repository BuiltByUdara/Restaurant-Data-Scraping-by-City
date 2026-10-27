import csv
from urllib.parse import urlsplit, urlunsplit


def normalize_url(value):
    value = (value or '').strip()
    if not value:
        return ''
    parts = urlsplit(value if '://' in value else 'https://' + value)
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Invalid website URL')
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query, ''))


def load_mapping(path):
    if not path:
        return {}
    with open(path, encoding='utf-8-sig', newline='') as handle:
        return {row['organisasjonsnummer']: row['website'] for row in csv.DictReader(handle)}


def find_website(company, mapping):
    org = company.get('record_id') or str(company['organisasjonsnummer'])
    value = mapping.get(org) or company.get('hjemmeside')
    return normalize_url(value), ('mapping' if mapping.get(org) else company.get('data_source', 'registry')) if value else 'unresolved'
