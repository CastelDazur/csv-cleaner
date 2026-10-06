# Cleaning report: messy_customers.csv

- Encoding: cp1252, delimiter: ';'
- Rows in: 39
- Rows out: 36
- Removed: 3 (empty/duplicates)
- Value edits: 171 (see changes_log.csv)
- Need manual review: 6

## Removed rows

- row 22: empty row
- row 39: duplicate of row 4
- row 40: duplicate of row 9

## Need manual review (values were not guessed)

- row 7 (Luc Dubois): email: invalid format
- row 11 (Pierre Weber): signup_date: format not recognised
- row 13 (Anna Rossi): country: not in lookup
- row 14 (Marco Rossi): order_total: not a number
- row 16 (Luc Kovalenko): country: not in lookup
- row 19 (Tom Martin): phone: could not be normalised to international format
