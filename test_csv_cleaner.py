"""Тесты на синтетике: py -3.14 -B -m unittest -v"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import csv_cleaner as cc


def run_on(text: str, encoding: str = "utf-8", **kw) -> cc.Result:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "in.csv"
        p.write_bytes(text.encode(encoding))
        return cc.clean(p, **kw)


class Amounts(unittest.TestCase):
    def test_malformed_grouping_not_guessed(self):
        for raw in ("1,2,3", "12,34.5", "1.2,345", "1,234,56"):
            self.assertIsNone(cc.parse_amount(raw), raw)

    def test_identifiers_and_malformed_signs_not_guessed(self):
        for raw in ("INV2026", "12abc", "--5", "12-3", "USD12USD"):
            self.assertIsNone(cc.parse_amount(raw), raw)

    def test_decimal_precision_for_large_amount(self):
        self.assertEqual(cc.parse_amount("9007199254740993.01"), "9007199254740993.01")

    def test_formats(self):
        for raw, want in [("12,5", "12.50"), ("1 234,50", "1234.50"), ("1,234.50", "1234.50"),
                          ("1.234,50", "1234.50"), ("€ 99.9", "99.90"), ("1,234", "1234.00"),
                          ("-5,00 EUR", "-5.00")]:
            self.assertEqual(cc.parse_amount(raw), want, raw)

    def test_garbage(self):
        self.assertIsNone(cc.parse_amount("n/a"))
        self.assertEqual(cc.parse_amount(""), "")


class Dates(unittest.TestCase):
    def test_day_first_default(self):
        self.assertEqual(cc.parse_date("03/04/2025", False), "2025-04-03")
        self.assertEqual(cc.parse_date("03/04/2025", True), "2025-03-04")

    def test_invalid(self):
        self.assertIsNone(cc.parse_date("31/02/2025", False))


class Phones(unittest.TestCase):
    def test_letters_and_invalid_country_prefix_not_normalised(self):
        for raw in ("+CALL123456789", "+0123456789"):
            self.assertEqual(cc.clean_phone(raw, "33"), (raw, False))

    def test_invalid_international_phone_preserved(self):
        for raw in (" +12 34 ", "+1234567890123456"):
            self.assertEqual(cc.clean_phone(raw, "33"), (raw, False))

    def test_fr(self):
        self.assertEqual(cc.clean_phone("06 39 98 12 34", "33"), ("+33639981234", True))
        self.assertEqual(cc.clean_phone("0033 6 39981234", "33"), ("+33639981234", True))

    def test_short_is_flagged_not_guessed(self):
        self.assertEqual(cc.clean_phone("12345", "33"), ("12345", False))


class Pipeline(unittest.TestCase):
    def test_unknown_columns_are_rejected_without_data_loss(self):
        with self.assertRaises(ValueError):
            run_on("Name,Notes\nAnna,important\n")

    def test_duplicate_alias_columns_are_rejected(self):
        with self.assertRaises(ValueError):
            run_on("Name,Customer Name\nAnna,Olga\n")

    def test_irregular_row_width_is_rejected(self):
        for text in ("Name,Total\nAnna,5,extra\n", "Name,Total\nAnna\n"):
            with self.assertRaises(ValueError):
                run_on(text)

    def test_records_without_reliable_identity_are_not_merged(self):
        res = run_on("Date,Total\n2025-01-01,10\n2025-01-02,20\n")
        self.assertEqual(len(res.rows), 2)
        self.assertEqual(len(res.dropped), 0)
        res = run_on("Name,Phone,Total\nAnna,123,10\nAnna,123,20\n")
        self.assertEqual(len(res.rows), 2)

    def test_unrecognised_values_are_preserved(self):
        res = run_on("Name,Phone,Date,Total,Country\nAnna, +123 , bad-date , INV2026 , spAIN \n")
        row = res.rows[0]
        self.assertEqual([row[k] for k in ("phone", "signup_date", "order_total", "country")],
                         [" +123 ", " bad-date ", " INV2026 ", " spAIN "])

    def test_output_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cleaned.csv"
            p.write_text("Name,Total\nAnna,5\n", encoding="utf-8")
            before = p.read_bytes()
            with self.assertRaises(ValueError):
                cc.write_outputs(cc.clean(p), Path(d), p)
            self.assertEqual(p.read_bytes(), before)
            self.assertFalse((Path(d) / "report.md").exists())

    TEXT = ("Customer Name;E-mail;Phone;Date;Amount;Country\r\n"
            "  ANNA  MARTIN ;ANNA@Example.com;06 39 98 12 34;03/04/2025;1 234,50;FRANCE\r\n"
            ";;;;;\r\n"
            "Anna Martin;anna@example.com;;2025-04-03;1234.50;fr\r\n"
            "Olga K;bad-mail;123;99/99/2025;n/a;Spain\r\n")

    def test_dedupe_keeps_most_complete(self):
        res = run_on(self.TEXT)
        emails = [r["email"] for r in res.rows]
        self.assertEqual(emails.count("anna@example.com"), 1)
        kept = next(r for r in res.rows if r["email"] == "anna@example.com")
        self.assertEqual(kept["phone"], "+33639981234")
        self.assertEqual(kept["name"], "Anna Martin")
        self.assertEqual((kept["signup_date"], kept["order_total"], kept["country"]),
                         ("2025-04-03", "1234.50", "France"))

    def test_bad_row_flagged_and_values_not_invented(self):
        res = run_on(self.TEXT)
        bad = next(r for r in res.rows if r["name"] == "Olga K")
        self.assertEqual(len(bad["review"]), 5)
        self.assertEqual((bad["signup_date"], bad["order_total"]), ("99/99/2025", "n/a"))

    def test_counts_and_drops(self):
        res = run_on(self.TEXT)
        self.assertEqual((res.rows_in, len(res.rows), len(res.dropped)), (4, 2, 2))

    def test_cp1252_semicolon(self):
        res = run_on("Name;Total\r\nRené;5,5 €\r\n", encoding="cp1252")
        self.assertEqual(res.encoding, "cp1252")
        self.assertEqual((res.rows[0]["name"], res.rows[0]["order_total"]), ("René", "5.50"))

    def test_lang_en_has_no_cyrillic_in_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "in.csv"
            p.write_bytes(self.TEXT.encode())
            res = cc.clean(p, lang="en")
            cc.write_outputs(res, Path(d) / "out", p)
            for name in ("report.md", "changes_log.csv", "cleaned.csv"):
                body = (Path(d) / "out" / name).read_text(encoding="utf-8")
                self.assertFalse(any("Ѐ" <= ch <= "ӿ" for ch in body), name)

    def test_lang_fr_has_no_cyrillic_and_keeps_data(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "in.csv"
            p.write_bytes(self.TEXT.encode())
            res = cc.clean(p, lang="fr")
            cc.write_outputs(res, Path(d) / "out", p)
            for name in ("report.md", "changes_log.csv", "cleaned.csv"):
                body = (Path(d) / "out" / name).read_text(encoding="utf-8")
                self.assertFalse(any("Ѐ" <= ch <= "ӿ" for ch in body), name)
        strip = lambda r: [{k: v for k, v in x.items() if k != "review"} for x in r.rows]
        self.assertEqual(strip(res), strip(run_on(self.TEXT, lang="en")))

    def test_lang_does_not_change_data(self):
        a, b = run_on(self.TEXT, lang="ru"), run_on(self.TEXT, lang="en")
        strip = lambda res: [{k: v for k, v in r.items() if k != "review"} for r in res.rows]
        self.assertEqual(strip(a), strip(b))
        self.assertEqual([len(r["review"]) for r in a.rows], [len(r["review"]) for r in b.rows])

    def test_input_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "in.csv"
            p.write_bytes(self.TEXT.encode())
            before = p.read_bytes()
            cc.write_outputs(cc.clean(p), Path(d) / "out", p)
            self.assertEqual(p.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
