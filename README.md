# Worldwide restaurant enrichment

## Worldwide city search

```powershell
python -m norway_restaurants --city "Lisban" --country PT --all --no-scrape --output output/lisbon.csv
python -m norway_restaurants --city "Paris" --country FR --limit 100 --output output/paris.csv
python -m norway_restaurants --city "Oslo" --source brreg --limit 100 --output output/oslo.csv
```

City search defaults to OpenStreetMap worldwide. `Lisban` is an explicit alias for Lisbon; other names use Nominatim search, and arbitrary misspellings are not guaranteed. The resolved location is printed before retrieval. Use `--country` (two-letter ISO code) or a fuller city name to disambiguate. Add `--source brreg` to the Norwegian city examples below to retain registry lookup. Without `--city`, registry/local-input behavior is unchanged.

`--all` exports all restaurant records returned for the area; the default cap is 100. This means all available mapped results, not every real-world restaurant. Coverage and contact completeness vary. Administrative/mapped boundaries are used when available; otherwise a clearly reported bounding box is used. Only `amenity=restaurant` is selected; cafes, bars, and fast-food-only records are excluded. Different OSM IDs can describe the same venue. Records without emails are included.

Available fields include name, address, country, coordinates, cuisine, opening hours, website, phones, email, wheelchair access, takeaway, delivery, and source link. Missing fields remain empty; ratings/reviews are not supplied. Remove `--no-scrape` to also enrich from public websites, which can take a long time for a whole city.

Data: [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL. Attribution is included in export rows. Nominatim is used only for city lookup with disk caching in `output/geocache` and at least one second between requests per process. Run one process at a time against public services. Set `NOMINATIM_URL` and `OVERPASS_URL` to use another provider or your own instance. Public services have capacity and availability limits; see the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).

OSM IDs use `record_id`; Norwegian organization numbers remain blank for OSM records. Website mappings may use an OSM record ID in the `organisasjonsnummer` column. `registry_source` contains the source link for either provider.

## Norwegian registry workflow

A Python 3.10+ pipeline using only the standard library. Fetches Brønnøysund registry entities, filters active restaurant companies, normalizes names, resolves known websites, scans public HTML, extracts contact details, scores observed website signals, deduplicates by organization number, and exports CSV plus detailed JSONL.

## Run

### Get real restaurants by city

```powershell
python -m norway_restaurants --city Oslo --limit 100 --output output/oslo.csv
python -m norway_restaurants --city Bergen --limit 100 --no-scrape --output output/bergen.csv
python -m norway_restaurants --city "Tromsø" --limit 100 --output output/tromso.csv
```

`--city` queries live Brreg establishment records (`underenheter`) by physical location. Municipality names match their full municipality boundary; other names are searched as postal towns. Results contain real registered establishment names, street addresses, postal codes, parent organization IDs, registry links, and available public contact details. The registry does not guarantee a venue is currently open or that every venue has a website/email. `--no-scrape` retrieves registry data quickly without visiting websites. No example records are mixed into live results.

From this directory:

```powershell
# Offline demonstration (the included company is fictional)
python -m norway_restaurants --input examples/companies.json --no-scrape

# Fetch and enrich up to 25 registry results
python -m norway_restaurants --limit 25 --municipality 0301

# Use your own registry JSON and verified website mapping
python -m norway_restaurants --input companies.json --websites websites.csv --output output/leads.csv

# Tests
python -m unittest discover -s tests -v
```

No API key or dependency installation is needed. Set `--user-agent` to identify your project and a contact URL. Other options: `--codes 56.1`, `--max-pages 6`, `--delay 1`.

## Data and website discovery

All matching restaurants are written to CSV and JSONL, including those without email addresses. Emails may come from the registry or scanned public pages. `--limit` bounds records processed. With `--no-scrape`, only registry emails are collected.

The API source is https://data.brreg.no/enhetsregisteret/api/enheter. Reference: https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html (NLOD license). Industry prefixes are configurable; the default `56.1` selects restaurant activities. Validate the classification against your intended scope. Catering and bars outside this prefix are excluded. These are legal entities, not necessarily individual restaurant locations. `--limit` caps fetched registry records before local inactive-company filtering, so output can be smaller.

The API allows at most 10,000 results per query. For larger work, narrow by municipality or supply a JSON array of registry records with `--input`. The pipeline raises an error instead of silently passing the pagination boundary.

Website resolution prefers a user-supplied mapping, then the registry's `hjemmeside`. Missing websites remain `unresolved`; no domains are guessed. This version does not include a search-engine or business-directory provider. Add verified results to a UTF-8 CSV:

```csv
organisasjonsnummer,website
000000001,https://example.com
```

## Crawling and contacts

The crawler checks robots.txt, observes crawl delays, limits page attempts and response sizes, uses timeouts and bounded retries, and follows relevant same-host contact links alongside common contact/about paths. A missing robots.txt (404) permits crawling; other retrieval failures conservatively block it. HTTP redirects are followed with public-address validation. DNS checks are a basic safeguard, not a network isolation boundary; run untrusted large-scale workloads behind suitable network controls.

Only visible HTML text and mailto links supply emails; telephone links supply phone numbers. Role addresses are separated from `review_required` addresses, including Gmail and name-like addresses. Every email retains its source URL. This classification does not establish ownership or marketing consent. No outreach is sent. Registry legal form is preserved for downstream review.

JavaScript rendering, obfuscated emails, image-based contacts, and arbitrary listing extraction are not supported. Shared domains never merge separate organization numbers. The crawler does not verify that a registry website still belongs to the business.

## Scoring and output

`opportunity_score` is a transparent website-improvement heuristic, 0–100: missing HTTPS adds 20, missing viewport meta adds 30, no menu keyword adds 25, and no booking keyword adds 25. It is based on scanned HTML; missing signals are not proof of missing features. If no HTML is retrieved, the score is null. It is not a performance, accessibility, or commercial-value audit.

CSV includes company details, website provenance, role/review email lists, phones, score reasons, email source URLs, scan errors, and UTC timestamps. Lists are JSON inside CSV cells. UTF-8 BOM supports Excel, and dangerous spreadsheet formula prefixes are escaped. Import the CSV into Google Sheets or your CRM; direct integrations are not included.

A sibling `.jsonl` file is flushed after every completed entity for interruption recovery and inspection. Runs overwrite the chosen output files; automatic resume is not implemented. Use a different `--output` per run if retaining history. Raw HTML is not saved.
