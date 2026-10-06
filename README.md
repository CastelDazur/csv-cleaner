# CSV cleaner

[![test](https://github.com/CastelDazur/csv-cleaner/actions/workflows/test.yml/badge.svg)](https://github.com/CastelDazur/csv-cleaner/actions/workflows/test.yml)

Turns a messy customer CSV export (mixed date formats, `1,794.71` / `1788,62 EUR` amounts, phones in four notations, duplicates) into one consistent file, plus a log of every change and a short list of values a person must decide on. Nothing is guessed silently.

This is a **bounded demo on synthetic data**: standard library only, 25 tests, fictional people and `example.com` addresses.

## Before → after

Real rows from `input/messy_customers.csv` and `expected_output_en/cleaned.csv`:

| Row | Before | After |
|---|---|---|
| 2 | `  JONAS  KOVALENKO ` · ` Jonas.Kovalenko0@example.com ` · `14-02-2025` · `188,12` | `Jonas Kovalenko` · `jonas.kovalenko0@example.com` · `2025-02-14` · `188.12` |
| 4 | `06 39 98 35 18` · `1788,62 EUR` · `Germany` | `+33639983518` · `1788.62` · `Germany` |
| 8 | `0033 639986842` · `1,794.71` · `UK` | `+33639986842` · `1794.71` · `United Kingdom` |
| 11 | `31/02/2025` · `€ 394.41` | `31/02/2025` kept and flagged *signup_date: format not recognised* · `394.41` |
| 40 | `OLENA.DUBOIS7@EXAMPLE.COM`, phone empty | removed as a less complete duplicate of row 9 (listed in the report) |

## Quick start

Python 3.11 or newer, standard library only. No network access, credentials, services or GPU are required.

```bash
python3 csv_cleaner.py input/messy_customers.csv --out out --lang en
python3 -B -m unittest -v
```

On Windows, use `py` instead of `python3`.

Tested in CI on Windows, macOS and Linux with Python 3.11, 3.12, 3.13 and 3.14: the unit tests, plus a byte-for-byte rebuild of the sample and of all three expected outputs.

Options: `--lang ru|en|fr` (default `ru`), `--month-first` (US numeric date order; default day-first), `--default-cc 33` (agreed country code for domestic numbers starting with zero). Confirm these conventions before processing customer data.

## Supported scope

CSV fields: `name`, `email`, `phone`, `signup_date`, `order_total`, `country`, including aliases listed in `HEADER_ALIASES`. A subset is allowed. Unknown/empty header names, duplicate mappings or rows with the wrong number of cells cause an error before output is written. Agree or implement a mapping for a different schema; do not discard extra columns.

Native `.xlsx`, formulas, multiple sheets, PDF/OCR, APIs, fuzzy matching, external data enrichment and CRM integration are outside this demo. Excel may be the source if it is first exported to the agreed CSV format.

The UTF-8/Windows-1252/Latin-1 fallback and delimiter heuristic are checked on the sample formats, not a universal detector. Review the detected encoding, header and a sample of decoded text before accepting a real job; legacy Cyrillic/other encodings need explicit handling. Text month names depend on the interpreter's locale.

## Outputs

| File | Content |
|---|---|
| `cleaned.csv` | Normalised fields, `source_row`, `needs_review` |
| `changes_log.csv` | Value edits: source row, column, old/new value, rule |
| `report.md` | Counts, removed source rows/reasons and values needing a decision |

Output cannot overwrite the source file. An existing output directory may be replaced; use a new directory for each run. Changes to rows later removed by deduplication can also appear in the value-change log; removals are recorded separately in the report.

## Rules and decisions

- Names: trim/collapse whitespace; all-upper/all-lower values become title case. Agree this before applying it to names/brands.
- Emails: trim/lowercase and validate the demo's limited pattern; this is not a deliverability check.
- Phones: normalise supported international/domestic formats; unrecognised numbers are retained and flagged. The country code must be agreed.
- Dates: numeric supported formats become ISO; unrecognised dates remain unchanged and are flagged. `03/04/2025` depends on the agreed day/month order.
- Amounts: examples include `1 234,50` → `1234.50`, `1,234.50` → `1234.50`, `€ 12.5` → `12.50`. Decimal calculations avoid binary float precision loss. Separator conventions must be agreed; three digits after a separator are interpreted as thousands by this demo, not automatically as three decimal places. Unknown labels such as `INV2026` are retained and flagged.
- Countries: known aliases use the small built-in lookup. Unknown values are retained and flagged.
- Duplicates: valid same email, otherwise same nonempty name + valid phone; retain the more complete record. Records without a reliable identifier are retained separately. **This rule is suitable only when one customer record is expected: multiple legitimate orders from the same customer must not be merged.**
- Empty rows are removed. Retain the source and inspect all removals.

CSV opened in a spreadsheet may interpret values beginning with `=`, `+`, `-`, or `@` as formulas. Import untrusted fields as text and agree any escaping/export policy before delivery; this demo is not a complete spreadsheet formula sanitizer.

## Verification and sample

`input/messy_customers.csv` contains fictional people, `example.com` addresses and phone numbers from the range reserved for fiction in France (`06 39 98 xx xx`), generated deterministically by `make_sample.py`. It has planted errors, two duplicate records and one empty row. Expected results: **39 input rows → 36 output rows; 3 removals; 171 value edits; 6 rows requiring review**.

[Russian report](expected_output/report.md), [English report](expected_output_en/report.md), [French report](expected_output_fr/report.md). Client text is preserved; selecting a report language does not translate names or input values.

The 25 tests cover normal formats and safety regressions: identifier-like amounts, decimal precision, invalid phones, unknown/duplicate columns, irregular row width, unreliable duplicate identity and output/source collision. Expected files match byte-for-byte for all three report languages.

Synthetic 2,000- and 5,000-row runs completed while retaining every distinct record. Their sub-second script time does **not** estimate the hours needed for customer rules, mapping, communication, revisions or installation. Commercial limits must be confirmed against the actual sample.

## Support scope

Issues are welcome for reproducible defects in this demo: a command from this README that fails, or output that differs from `expected_output*/` on the bundled sample. Please include the Python version, OS and the exact command.

Adapting the script to a different schema, file format or set of rules is separate work, not a bug fix.

## Using it for a real file

Before a real file is processed, the rules are agreed in writing: day/month order for dates, the country code for domestic phone numbers, decimal and thousands separators, which columns are mapped, and what counts as a duplicate. The source file is kept unchanged; every edit is listed in `changes_log.csv` and every removal and open question in `report.md`.

## License

[MIT](LICENSE)

---

[castel.studio](https://castel.studio/)

