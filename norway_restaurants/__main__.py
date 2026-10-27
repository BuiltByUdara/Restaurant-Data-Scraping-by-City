import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .get_companies import get_companies
from .filter_restaurants import filter_restaurants
from .find_websites import find_website, load_mapping
from .scrape_websites import scrape_website
from .find_emails import find_emails, parse_page
from .analyze_website import analyze_website
from .deduplicate import deduplicate
from .export_csv import export_csv
from .http import Client


def main():
    parser = argparse.ArgumentParser(description='Enrich Norwegian restaurant entities from public sources')
    parser.add_argument('--input', help='Local registry JSON array; otherwise use Brreg API')
    parser.add_argument('--websites', help='CSV columns: organisasjonsnummer,website')
    parser.add_argument('--output', default='output/restaurants.csv')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--codes', default='56.1', help='Comma-separated industry prefixes')
    parser.add_argument('--municipality')
    parser.add_argument('--city', help='Norwegian city, e.g. Oslo, Bergen, Tromsø; fetch actual establishment records')
    parser.add_argument('--max-pages', type=int, default=6)
    parser.add_argument('--delay', type=float, default=1)
    parser.add_argument('--user-agent', default='NorwayRestaurantResearch/1.0')
    parser.add_argument('--no-scrape', action='store_true')
    args = parser.parse_args()
    if args.city and (args.input or args.municipality):
        parser.error('--city cannot be combined with --input or --municipality')
    if args.city is not None and not args.city.strip():
        parser.error('--city must not be empty')
    if args.limit < 1 or args.max_pages < 1 or args.delay < 0:
        parser.error('limit/max-pages must be positive; delay must be nonnegative')
    codes = tuple(c.strip() for c in args.codes.split(',') if c.strip())
    if not codes:
        parser.error('Provide at least one industry code')
    client = Client(delay=args.delay, user_agent=args.user_agent)
    companies = json.loads(Path(args.input).read_text(encoding='utf-8-sig')) if args.input else get_companies(client, codes, args.municipality, args.limit, city=args.city)
    mapping = load_mapping(args.websites)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    processed = 0
    # Flush each completed company to JSONL so interrupted work remains inspectable.
    with output.with_suffix('.jsonl').open('w', encoding='utf-8') as checkpoint:
        for company in deduplicate(filter_restaurants(companies, codes)):
            if processed >= args.limit:
                break
            processed += 1
            pages, errors = [], []
            website, source = '', 'unresolved'
            try:
                website, source = find_website(company, mapping)
                if website and not args.no_scrape:
                    pages, errors = scrape_website(client, website, args.max_pages)
            except Exception as exc:
                errors.append({'error': str(exc)})
            contacts = [contact for page in pages for contact in find_emails(page['html'], page['url'])]
            registry_source = company.get('registry_source', '')
            if company.get('epostadresse'):
                contacts.extend(find_emails(company['epostadresse'], registry_source))
            address = company.get('beliggenhetsadresse') or company.get('forretningsadresse', {})
            registry_phones = {company[key] for key in ('telefon', 'mobil') if company.get(key)}
            analysis = analyze_website(pages)
            record = {
                'organisasjonsnummer': str(company['organisasjonsnummer']),
                'name': company.get('navn', ''), 'normalized_name': company['normalized_name'],
                'legal_form': company.get('organisasjonsform', {}).get('kode', ''),
                'municipality': address.get('kommune', ''),
                'address': ', '.join(address.get('adresse', [])),
                'postal_code': address.get('postnummer', ''),
                'city': address.get('poststed', ''),
                'parent_organization': company.get('overordnetEnhet', ''),
                'registry_source': registry_source,
                'website': website, 'website_source': source, **analysis,
                'status': 'skipped' if args.no_scrape else ('unresolved' if not website else analysis['status']),
                'role_emails': sorted({c['email'] for c in contacts if c['classification'] == 'role'}),
                'review_emails': sorted({c['email'] for c in contacts if c['classification'] != 'role'}),
                'phones': sorted(registry_phones | {phone for p in pages for phone in parse_page(p['html']).phones}),
                'contact_sources': contacts, 'errors': errors,
                'checked_at': datetime.now(timezone.utc).isoformat(),
            }
            records.append(record)
            checkpoint.write(json.dumps(record, ensure_ascii=False) + '\n')
            checkpoint.flush()
            print(f"Processed {len(records)}: {record['name']} ({record['status']})", flush=True)
    export_csv(records, output)
    if not records:
        print('No matching restaurant records found. Check city spelling or industry codes.')
    print(f'Exported {len(records)} companies to {output}')


if __name__ == '__main__':
    main()
