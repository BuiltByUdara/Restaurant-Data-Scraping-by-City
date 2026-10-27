import re
import unicodedata


def normalize_name(name):
    name = unicodedata.normalize('NFKC', name).casefold()
    name = re.sub(r'\b(?:as|asa|enk|ans|da)\s*$', '', name)
    return ' '.join(re.sub(r'[^\w\s]', ' ', name).split())


def filter_restaurants(companies, codes=('56.1',)):
    for company in companies:
        if any(company.get(k) for k in ('slettedato', 'konkurs', 'underAvvikling', 'underTvangsavviklingEllerTvangsopplosning')):
            continue
        industry = [company.get(f'naeringskode{i}', {}).get('kode', '') for i in range(1, 4)]
        if any(code.startswith(prefix) for code in industry for prefix in codes):
            yield {**company, 'normalized_name': normalize_name(company.get('navn', ''))}
