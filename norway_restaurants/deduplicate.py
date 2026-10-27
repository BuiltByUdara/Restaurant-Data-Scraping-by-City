def deduplicate(companies):
    """Deduplicate legal entities, never merge distinct companies sharing a domain."""
    seen = set()
    for company in companies:
        key = company.get('record_id') or str(company['organisasjonsnummer'])
        if key not in seen:
            seen.add(key)
            yield company
