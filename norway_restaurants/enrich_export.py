"""Resume website enrichment from a previous JSONL export, without re-querying maps."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit

from .http import Client
from .scrape_websites import scrape_website
from .find_emails import find_emails
from .export_csv import export_csv, email_addresses


def enrich(record, lock, max_pages):
    record = dict(record)
    with lock:
        pages, errors = scrape_website(Client(timeout=10, budget=60), record['website'], max_pages)
    contacts = list(record.get('contact_sources', []))
    contacts.extend(c for page in pages for c in find_emails(page['html'], page['url']))
    record.update(
        role_emails=sorted(set(record.get('role_emails', [])) | {c['email'] for c in contacts if c['classification'] == 'role'}),
        review_emails=sorted(set(record.get('review_emails', [])) | {c['email'] for c in contacts if c['classification'] != 'role'}),
        contact_sources=contacts, errors=errors,
        status='observed' if pages else 'not_observed',
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
    return record


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Existing JSONL export')
    parser.add_argument('--output', default='output/restaurants-with-email.csv')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--max-pages', type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16 or args.max_pages < 1:
        parser.error('workers must be 1–16 and max-pages positive')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = output.with_suffix('.progress.jsonl')
    if Path(args.input).resolve() in (output.resolve(), checkpoint.resolve(), output.with_suffix('.jsonl').resolve()):
        parser.error('Input and output paths must differ')
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding='utf-8').splitlines() if line.strip()]
    key = lambda r: r.get('record_id') or r['organisasjonsnummer']
    completed = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                completed[key(row)] = row
    pending = [r for r in rows if r.get('website') and not email_addresses(r) and key(r) not in completed]
    locks = {urlsplit(r['website']).hostname: threading.Lock() for r in pending}

    def save():
        selected = [completed.get(key(r), r) for r in rows]
        selected = [r for r in selected if email_addresses(r)]
        export_csv(selected, output)
        output.with_suffix('.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in selected), encoding='utf-8')
        return len(selected)

    print(f'{len(rows)} restaurants; {len(pending)} websites to check; {save()} already have email.', flush=True)
    with checkpoint.open('a', encoding='utf-8') as log, ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(enrich, r, locks[urlsplit(r['website']).hostname], args.max_pages): r for r in pending}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            completed[key(row)] = row
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
            if index % 10 == 0 or index == len(pending):
                print(f'Checked {index}/{len(pending)} websites; {save()} restaurants with email.', flush=True)
    print(f'Exported {save()} restaurants with email to {output}', flush=True)


if __name__ == '__main__':
    main()
