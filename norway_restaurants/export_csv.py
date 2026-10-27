import csv
import json
from pathlib import Path

FIELDS = ['organisasjonsnummer', 'name', 'normalized_name', 'legal_form', 'municipality', 'website', 'website_source', 'status', 'role_emails', 'review_emails', 'phones', 'opportunity_score', 'score_reasons', 'contact_sources', 'errors', 'checked_at']
FIELDS[5:5] = ['address', 'postal_code', 'city', 'parent_organization', 'registry_source']
FIELDS += ['record_id', 'data_source', 'country', 'latitude', 'longitude', 'cuisine', 'opening_hours', 'wheelchair', 'takeaway', 'delivery', 'attribution']
FIELDS.insert(0, 'email')


def email_addresses(record):
    return sorted(set(record.get('role_emails', []) + record.get('review_emails', [])))


def export_csv(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        for record in records:
            record = {**record, 'email': '; '.join(email_addresses(record))}
            row = {}
            for key in FIELDS:
                value = record.get(key, '')
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)
                if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
                    value = "'" + value
                row[key] = value
            writer.writerow(row)
