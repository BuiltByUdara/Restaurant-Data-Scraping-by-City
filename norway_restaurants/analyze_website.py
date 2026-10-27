from .find_emails import parse_page


def analyze_website(pages):
    if not pages:
        return {'status': 'not_observed', 'opportunity_score': None, 'score_reasons': []}
    parsed = [parse_page(page['html']) for page in pages]
    text = ' '.join(' '.join(p.text) + ' ' + ' '.join(p.links) for p in parsed).lower()
    signals = {
        'https': pages[0]['url'].startswith('https://'),
        'viewport': parsed[0].viewport,
        'menu_detected': any(word in text for word in ('meny', 'menu')),
        'booking_detected': any(word in text for word in ('booking', 'reservasjon', 'reserve', 'bestill bord')),
    }
    weights = {'https': 20, 'viewport': 30, 'menu_detected': 25, 'booking_detected': 25}
    missing = [key for key, present in signals.items() if not present]
    return {'status': 'observed', **signals, 'opportunity_score': sum(weights[k] for k in missing), 'score_reasons': ['not_detected:' + k for k in missing]}
