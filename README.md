# Worldwide restaurant scraper and email enrichment

Find restaurant records by city, collect publicly listed contact details, and export CSV/JSONL. Worldwide searches use OpenStreetMap; Norwegian registry lookup is also available.

**Only restaurants with an email are exported by default.** The `email` column contains addresses separated by semicolons. Emails are extracted, not guessed or tested for deliverability.

## Requirements

- Python 3.10 or newer and internet access.
- No extra Python packages or API keys are required.

Open PowerShell in the project folder:

```powershell
cd C:\Users\UsEr\Documents\ChatGPT\Scrape
python --version
```

If Windows recognizes `py` instead of `python`, substitute `py` in these commands.

## Quick start

Search a city and collect emails from available public websites:

```powershell
python -m norway_restaurants --city "Lisbon" --country PT --all --output output/lisbon-new.csv
```

Other examples:

```powershell
python -m norway_restaurants --city "London" --country GB --all --output output/london.csv
python -m norway_restaurants --city "Paris" --country FR --limit 25 --output output/paris-test.csv
```

Use a two-letter country code to disambiguate the city. The program prints the resolved location. `Lisban` is accepted as an alias for Lisbon; arbitrary misspellings are not guaranteed to work.

**Do not add `--no-scrape` when you want website email collection.** Full-city scans can take time. Keep the destination CSV closed in Excel while the program runs, otherwise Windows may block updates.

`--limit` bounds records processed, not emails found. The default is 100. `--all` processes all returned map records, not necessarily every restaurant in the real world.

## Recommended whole-city workflow: discover, then enrich

This workflow keeps candidates without emails during discovery and supports concurrent, resumable website checks.

### 1. Save all available restaurant records

```powershell
python -m norway_restaurants --city "Lisbon" --country PT --all --no-scrape --include-without-email --output output/lisbon-discovery.csv
```

This creates both `output/lisbon-discovery.csv` and `output/lisbon-discovery.jsonl`. **Keep `--include-without-email` in this step** so records needing enrichment remain in the input.

### 2. Collect emails from known websites

```powershell
python -m norway_restaurants.enrich_export output/lisbon-discovery.jsonl --output output/lisbon-emails.csv
```

For the original Lisbon data already in this workspace:

```powershell
python -m norway_restaurants.enrich_export output/lisbon.jsonl --output output/lisbon-emails.csv
```

Existing emails are retained. Records lacking emails are scanned if a website is known. The final CSV/JSONL contains only records with emails. There is no search-engine provider to discover missing websites.

Eight workers run by default, with scans sharing a hostname serialized. Optional settings:

```powershell
python -m norway_restaurants.enrich_export output/lisbon-discovery.jsonl --output output/lisbon-emails.csv --workers 8 --max-pages 6
```

Workers may be 1–16. The enrichment client uses request timeouts and a per-site scheduling budget.

### Resume an interrupted scan

Run the **same enrichment command with the same input and output paths**. Completed scans are loaded from the sibling `.progress.jsonl` file and are not repeated, including checks that found no email.

Use a unique output name for each source dataset. To retry every website, choose a fresh output name. Input and output paths must differ. The main city-search command does not automatically resume; this feature belongs to `enrich_export`.

## Output files

For `--output output/lisbon-emails.csv`:

| File | Purpose |
| --- | --- |
| `lisbon-emails.csv` | Spreadsheet-ready records with a readable `email` column |
| `lisbon-emails.jsonl` | Exported records as JSON, one per line |
| `lisbon-emails.progress.jsonl` | Enrichment checkpoint, including unsuccessful scans |

Enrichment saves CSV/JSONL at startup, every ten completed checks, and at completion. Checkpoints are flushed after each completed check. The main pipeline writes its CSV at completion and flushes selected JSONL records as it goes. Runs overwrite their chosen CSV/JSONL files.

Available details include name, address, city, country, coordinates, cuisine, opening hours, website, phone, email, source links, scan errors, and timestamps. Some records include wheelchair access, takeaway, and delivery. Missing fields stay empty; ratings/reviews are not supplied.

- `email`: extracted addresses separated by semicolons.
- `role_emails`: recognized role addresses such as `info@` and `booking@`.
- `review_emails`: other addresses requiring review. Both categories qualify for export.
- `contact_sources`: email classifications and source URLs.
- `record_id`: OpenStreetMap identifier. OSM records have no Norwegian organization number.
- `registry_source`: source link for either map or registry records.

List/object fields are JSON inside CSV cells. CSV uses UTF-8 with a BOM for Excel and escapes dangerous spreadsheet formula prefixes. CSV can be imported into Google Sheets or a CRM; direct integrations are not included. Raw HTML is not saved.

## Main command options

| Option | Purpose |
| --- | --- |
| `--city "Lisbon"` | Search a city worldwide |
| `--country PT` | Restrict worldwide city lookup by two-letter country code |
| `--all` | Process all returned records, subject to provider limits |
| `--limit 100` | Cap processed records; default 100 |
| `--output output/leads.csv` | Choose CSV filename; default `output/restaurants.csv` |
| `--include-without-email` | Retain records without emails, especially for discovery |
| `--no-scrape` | Skip websites and collect only source-provided contacts |
| `--max-pages 6` | Maximum page attempts per website |
| `--delay 1` | Delay between main-pipeline requests |
| `--source brreg` | Use Norwegian registry city lookup |
| `--websites websites.csv` | Supply verified website mappings |
| `--user-agent` | Identify main-pipeline requests with your project/contact information |

Show complete help:

```powershell
python -m norway_restaurants --help
python -m norway_restaurants.enrich_export --help
```

## Norway registry and local inputs

```powershell
python -m norway_restaurants --city "Oslo" --source brreg --all --output output/oslo.csv
python -m norway_restaurants --limit 25 --municipality 0301 --output output/norway.csv
python -m norway_restaurants --input companies.json --websites websites.csv --output output/leads.csv
```

With `--source brreg --city`, the pipeline retrieves establishments by physical location. Municipality names match the whole municipality; other names are searched as postal towns. Without `--city`, it uses registry legal entities or a local registry JSON array supplied with `--input`.

The default industry prefix is `56.1`, configurable with `--codes`. Inactive registry companies are excluded. Registry pagination is capped at 10,000 records per query; narrow geography or use a local registry export for larger datasets.

Website mappings override source-provided URLs. Use a UTF-8 CSV:

```csv
organisasjonsnummer,website
000000001,https://example.com
```

For OSM records, use the full `record_id`, such as `osm:node:123`, in the `organisasjonsnummer` column. Domains are never guessed.

Offline demonstration using a fictional company with no email:

```powershell
python -m norway_restaurants --input examples/companies.json --no-scrape --include-without-email --output output/demo.csv
```

## Coverage and crawling

Worldwide search selects OSM `amenity=restaurant` records, excluding cafes, bars, and fast-food-only records. Mapped/administrative boundaries are used when available; otherwise a bounding-box search is reported. Coverage varies, and different OSM IDs can describe the same venue. Neither source guarantees that a venue is currently open.

The crawler checks robots.txt, observes crawl delays, limits page attempts and response sizes, and uses bounded retries. A robots.txt 404 permits crawling; other retrieval failures block it conservatively. Common contact/about paths include Portuguese contact paths.

Emails come from source data, HTML text, and mailto links; website phone extraction uses tel links. JavaScript rendering, image-based emails, and obfuscated contacts are not supported. Public emails may be outdated or belong to third parties; inspect their sources. No outreach is sent.

The main pipeline's `opportunity_score` is an HTML heuristic: missing HTTPS adds 20, missing viewport metadata adds 30, no menu keyword adds 25, and no booking keyword adds 25. Unscanned sites have no score. Email enrichment preserves existing analysis fields instead of recalculating them.

## Troubleshooting

- **Fewer rows than expected:** email filtering, missing websites, blocked pages, and incomplete source data reduce counts. Use the two-step workflow to retain enrichment candidates.
- **No additional emails:** omit `--no-scrape` or enrich a discovery JSONL that retained records without emails.
- **Permission denied saving CSV:** close the file in Excel or other apps, then rerun. Keep the same enrichment output name to reuse the checkpoint.
- **Wrong city:** add `--country` or a more specific city name; check the printed resolved location.
- **Service error or timeout:** retry later. Completed enrichment checks remain in the progress file; main city searches do not automatically resume.
- **Python not recognized:** try `py`, or install Python with its PATH option enabled.

## Sources and attribution

Map data is [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright), under ODbL. Attribution is included in exported rows. Nominatim city lookups use a disk cache in `output/geocache` and at least one second between requests per process. Run one city-lookup process at a time against the public service. See the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

Set `NOMINATIM_URL` and `OVERPASS_URL` to alternative endpoints or your own services. Public endpoints have availability and capacity limits.

Norwegian data comes from the [Brønnøysund registry API](https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html), under NLOD.

## Tests

```powershell
python -m unittest discover -s tests -v
```
