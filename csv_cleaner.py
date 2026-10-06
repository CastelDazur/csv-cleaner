"""CSV cleaner: приводит «грязный» CSV (клиенты/заказы) к проверенному виду.

Только стандартная библиотека; проверено на Python 3.14. Входной файл не меняется.
Выход: cleaned.csv, changes_log.csv (каждая правка: что было -> что стало, по какому правилу),
report.md (сводка + строки, требующие ручной проверки).

Запуск Windows: py -3.14 csv_cleaner.py input.csv --out out_dir [--month-first] [--default-cc 33] [--lang ru|en|fr]
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ["name", "email", "phone", "signup_date", "order_total", "country"]

HEADER_ALIASES = {
    "name": "name", "customer_name": "name", "full_name": "name", "customer": "name",
    "email": "email", "e_mail": "email", "mail": "email", "email_address": "email",
    "phone": "phone", "phone_number": "phone", "tel": "phone", "telephone": "phone",
    "signup_date": "signup_date", "date": "signup_date", "created": "signup_date",
    "order_total": "order_total", "order_total_eur": "order_total", "amount": "order_total",
    "total": "order_total",
    "country": "country",
}

COUNTRY_ALIASES = {
    "fr": "France", "france": "France",
    "uk": "United Kingdom", "gb": "United Kingdom", "united kingdom": "United Kingdom",
    "de": "Germany", "germany": "Germany", "deutschland": "Germany",
    "us": "United States", "usa": "United States", "united states": "United States",
    "ua": "Ukraine", "ukraine": "Ukraine",
}

I18N = {
    "ru": {
        "r_name": "пробелы/регистр", "r_email": "trim+lower", "r_phone": "международный формат",
        "r_date": "дата -> ISO", "r_amount": "сумма -> 0.00", "r_country": "страна -> справочник",
        "v_email_bad": "email: неверный формат", "v_email_empty": "email: пусто",
        "v_phone": "phone: не удалось привести к международному формату",
        "v_date": "signup_date: формат не распознан", "v_amount": "order_total: не число",
        "v_country": "country: нет в справочнике",
        "d_empty": "пустая строка", "d_dup": "дубликат строки {n}", "d_dup_full": "дубликат строки {n} (она полнее)",
        "h_title": "# Отчёт очистки: {f}", "h_enc": "- Кодировка: {e}, разделитель: {d!r}",
        "h_in": "- Строк на входе: {n}", "h_out": "- Строк на выходе: {n}",
        "h_drop": "- Удалено: {n} (пустые/дубликаты)", "h_chg": "- Правок значений: {n} (см. changes_log.csv)",
        "h_rev": "- Требуют ручной проверки: {n}", "h_dropped": "## Удалённые строки",
        "h_flagged": "## Требуют ручной проверки (значения не угадывались)",
        "none": "- нет", "row": "- строка {n}", "noname": "без имени",
        "done": "{a} -> {b} строк; правок {c}; на проверку {d}; отчёт: {p}",
    },
    "en": {
        "r_name": "whitespace/case", "r_email": "trim+lower", "r_phone": "international format",
        "r_date": "date -> ISO", "r_amount": "amount -> 0.00", "r_country": "country -> lookup",
        "v_email_bad": "email: invalid format", "v_email_empty": "email: empty",
        "v_phone": "phone: could not be normalised to international format",
        "v_date": "signup_date: format not recognised", "v_amount": "order_total: not a number",
        "v_country": "country: not in lookup",
        "d_empty": "empty row", "d_dup": "duplicate of row {n}", "d_dup_full": "duplicate of row {n} (that one is more complete)",
        "h_title": "# Cleaning report: {f}", "h_enc": "- Encoding: {e}, delimiter: {d!r}",
        "h_in": "- Rows in: {n}", "h_out": "- Rows out: {n}",
        "h_drop": "- Removed: {n} (empty/duplicates)", "h_chg": "- Value edits: {n} (see changes_log.csv)",
        "h_rev": "- Need manual review: {n}", "h_dropped": "## Removed rows",
        "h_flagged": "## Need manual review (values were not guessed)",
        "none": "- none", "row": "- row {n}", "noname": "no name",
        "done": "{a} -> {b} rows; edits {c}; to review {d}; report: {p}",
    },
    "fr": {
        "r_name": "espaces/casse", "r_email": "trim+minuscules", "r_phone": "format international",
        "r_date": "date -> ISO", "r_amount": "montant -> 0.00", "r_country": "pays -> référentiel",
        "v_email_bad": "e-mail : format invalide", "v_email_empty": "e-mail : vide",
        "v_phone": "téléphone : format international impossible",
        "v_date": "date : format non reconnu", "v_amount": "montant : valeur non numérique",
        "v_country": "pays : absent du référentiel",
        "d_empty": "ligne vide", "d_dup": "doublon de la ligne {n}", "d_dup_full": "doublon de la ligne {n} (celle-ci est plus complète)",
        "h_title": "# Rapport de nettoyage : {f}", "h_enc": "- Encodage : {e}, séparateur : {d!r}",
        "h_in": "- Lignes en entrée : {n}", "h_out": "- Lignes en sortie : {n}",
        "h_drop": "- Supprimées : {n} (vides/doublons)", "h_chg": "- Valeurs modifiées : {n} (voir changes_log.csv)",
        "h_rev": "- À vérifier manuellement : {n}", "h_dropped": "## Lignes supprimées",
        "h_flagged": "## À vérifier manuellement (aucune valeur n'a été devinée)",
        "none": "- aucune", "row": "- ligne {n}", "noname": "sans nom",
        "done": "{a} -> {b} lignes ; modifications {c} ; à vérifier {d} ; rapport : {p}",
    },
}

EMAIL_RE =re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$")
DATE_FORMATS_DAY_FIRST = ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d %b %Y", "%B %d, %Y"]
DATE_FORMATS_MONTH_FIRST = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d.%m.%Y", "%d %b %Y", "%B %d, %Y"]


@dataclass
class Change:
    row: int
    column: str
    old: str
    new: str
    rule: str


@dataclass
class Result:
    rows: list[dict] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    dropped: list[tuple[int, str]] = field(default_factory=list)
    encoding: str = "utf-8"
    delimiter: str = ","
    rows_in: int = 0
    lang: str = "ru"


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def sniff_delimiter(text: str) -> str:
    head = text.splitlines()[0] if text.splitlines() else ""
    counts = {d: head.count(d) for d in [",", ";", "\t", "|"]}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def clean_name(v: str) -> str:
    v = re.sub(r"\s+", " ", v).strip()
    return v.title() if v and (v.isupper() or v.islower()) else v


def clean_phone(v: str, default_cc: str) -> tuple[str, bool]:
    original = v
    v = v.strip()
    if not v:
        return "", True
    if not re.fullmatch(r"\+?[0-9\s().-]+", v):
        return original, False
    plus = v.startswith("+") or v.startswith("00")
    digits = re.sub(r"\D", "", v)
    if v.startswith("00"):
        digits = digits[2:]
    if not plus:
        if digits.startswith("0") and len(digits) == 10:
            digits = default_cc + digits[1:]
        else:
            return original, False
    ok = 8 <= len(digits) <= 15 and not digits.startswith("0")
    return ("+" + digits, True) if ok else (original, False)


def parse_date(v: str, month_first: bool) -> str | None:
    v = re.sub(r"\s+", " ", v.strip())
    if not v:
        return ""
    for fmt in (DATE_FORMATS_MONTH_FIRST if month_first else DATE_FORMATS_DAY_FIRST):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_amount(v: str) -> str | None:
    s = re.sub(r"\s+", "", v)
    s = re.sub(r"(?i)^(?:EUR|[€$£])|(?:EUR|[€$£])$", "", s)
    # Do not turn identifiers such as INV2026 or 12abc into invented amounts.
    if not re.fullmatch(r"-?[0-9]+(?:[,.][0-9]+)*", s):
        return "" if not v.strip() else None
    if not s or not re.search(r"\d", s):
        return "" if not v.strip() else None
    neg = s.startswith("-")
    s = s.lstrip("-")
    seps = [i for i, c in enumerate(s) if c in ",."]
    if seps:
        last = seps[-1]
        tail = s[last + 1:]
        prefix = s[:last]
        if len(tail) in (1, 2):
            # Thousands groups must be regular; reject malformed 1,2,3 / 12,34.5.
            if any(c in prefix for c in ',.'):
                group_sep = ',' if s[last] == '.' else '.'
                if not re.fullmatch(rf"[0-9]{{1,3}}(?:{re.escape(group_sep)}[0-9]{{3}})+", prefix):
                    return None
        elif not re.fullmatch(rf"[0-9]{{1,3}}(?:{re.escape(s[last])}[0-9]{{3}})+", s):
            return None
        if len(tail) in (1, 2) and not (len(tail) == 3):
            s = s[:last].replace(",", "").replace(".", "") + "." + tail
        else:
            s = s.replace(",", "").replace(".", "")
    try:
        val = Decimal(s)
    except InvalidOperation:
        return None
    return f"{-val if neg else val:.2f}"


def clean(path: Path, month_first: bool = False, default_cc: str = "33", lang: str = "ru") -> Result:
    t = I18N[lang]
    text, enc = read_text(path)
    delim = sniff_delimiter(text)
    res = Result(encoding=enc, delimiter=delim, lang=lang)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header = next(reader, [])
    colmap = {i: HEADER_ALIASES.get(normalize_header(h)) for i, h in enumerate(header)}
    if not header or any(f is None for f in colmap.values()):
        raise ValueError("Unknown/empty CSV column: agree a mapping before cleaning; no output written")
    if len(set(colmap.values())) != len(colmap):
        raise ValueError("Multiple CSV columns map to the same field; no output written")

    parsed: list[tuple[int, dict]] = []
    for lineno, cells in enumerate(reader, start=2):
        res.rows_in += 1
        if cells and len(cells) != len(header):
            raise ValueError(f"CSV row {lineno}: expected {len(header)} cells, got {len(cells)}; no output written")
        raw = {f: "" for f in FIELDS}
        for i, c in enumerate(cells):
            f = colmap.get(i)
            if f:
                raw[f] = c
        if not any(v.strip() for v in raw.values()):
            res.dropped.append((lineno, t["d_empty"]))
            continue
        row = {"source_row": lineno, "review": []}

        def log(col: str, old: str, new: str, rule: str) -> None:
            if old != new:
                res.changes.append(Change(lineno, col, old, new, rule))

        name = clean_name(raw["name"])
        log("name", raw["name"], name, t["r_name"])
        row["name"] = name

        email = raw["email"].strip().lower()
        log("email", raw["email"], email, t["r_email"])
        if email and not EMAIL_RE.match(email):
            row["review"].append(t["v_email_bad"])
        if not email:
            row["review"].append(t["v_email_empty"])
        row["email"] = email

        phone, ok = clean_phone(raw["phone"], default_cc)
        log("phone", raw["phone"], phone, t["r_phone"])
        if not ok:
            row["review"].append(t["v_phone"])
        row["phone"] = phone

        d = parse_date(raw["signup_date"], month_first)
        if d is None:
            row["review"].append(t["v_date"])
            d = raw["signup_date"]
        else:
            log("signup_date", raw["signup_date"], d, t["r_date"])
        row["signup_date"] = d

        amt = parse_amount(raw["order_total"])
        if amt is None:
            row["review"].append(t["v_amount"])
            amt = raw["order_total"]
        else:
            log("order_total", raw["order_total"], amt, t["r_amount"])
        row["order_total"] = amt

        c = raw["country"].strip()
        mapped = COUNTRY_ALIASES.get(c.lower())
        if mapped is None and c:
            mapped = raw["country"]
            row["review"].append(t["v_country"])
        mapped = mapped or ""
        log("country", raw["country"], mapped, t["r_country"])
        row["country"] = mapped
        parsed.append((lineno, row))

    # дубликаты: ключ = email, иначе (имя, телефон)
    seen: dict[tuple, int] = {}
    kept: dict[int, dict] = {}
    for lineno, row in parsed:
        if row["email"] and EMAIL_RE.match(row["email"]):
            key = ("e", row["email"])
        elif row["name"] and row["phone"] and clean_phone(row["phone"], default_cc)[1]:
            key = ("np", row["name"].lower(), row["phone"])
        else:
            key = ("source", lineno)  # No reliable identity: retain both records.
        if key in seen:
            first = seen[key]
            if sum(bool(kept[first][f]) for f in FIELDS) >= sum(bool(row[f]) for f in FIELDS):
                res.dropped.append((lineno, t["d_dup"].format(n=first)))
            else:
                res.dropped.append((first, t["d_dup_full"].format(n=lineno)))
                del kept[first]
                seen[key] = lineno
                kept[lineno] = row
        else:
            seen[key] = lineno
            kept[lineno] = row
    res.rows = [kept[k] for k in sorted(kept)]
    return res


def write_outputs(res: Result, out: Path, source: Path) -> None:
    targets = [out / name for name in ("cleaned.csv", "changes_log.csv", "report.md")]
    if any(p.resolve() == source.resolve() for p in targets):
        raise ValueError("Output would overwrite the input file; choose a different --out directory")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "cleaned.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS + ["source_row", "needs_review"])
        for r in res.rows:
            w.writerow([r[f] for f in FIELDS] + [r["source_row"], "; ".join(r["review"])])
    with (out / "changes_log.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_row", "column", "old", "new", "rule"])
        for c in res.changes:
            w.writerow([c.row, c.column, c.old, c.new, c.rule])
    t = I18N[res.lang]
    flagged = [r for r in res.rows if r["review"]]
    lines = [
        t["h_title"].format(f=source.name), "",
        t["h_enc"].format(e=res.encoding, d=res.delimiter),
        t["h_in"].format(n=res.rows_in),
        t["h_out"].format(n=len(res.rows)),
        t["h_drop"].format(n=len(res.dropped)),
        t["h_chg"].format(n=len(res.changes)),
        t["h_rev"].format(n=len(flagged)), "",
        t["h_dropped"], "",
    ]
    lines += [f"{t['row'].format(n=n)}: {why}" for n, why in sorted(res.dropped)] or [t["none"]]
    lines += ["", t["h_flagged"], ""]
    lines += [f"{t['row'].format(n=r['source_row'])} ({r['name'] or t['noname']}): {'; '.join(r['review'])}"
              for r in flagged] or [t["none"]]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # non-UTF-8 consoles must not crash after outputs are written
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path)
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--month-first", action="store_true", help="1/2/2026 = 2 января (США); по умолчанию день/месяц")
    p.add_argument("--default-cc", default="33", help="код страны для номеров с 0 в начале (33 = Франция)")
    p.add_argument("--lang", choices=sorted(I18N), default="ru", help="язык отчёта, лога правил и пометок / report language")
    a = p.parse_args(argv)
    res = clean(a.input, a.month_first, a.default_cc, a.lang)
    write_outputs(res, a.out, a.input)
    print(I18N[a.lang]["done"].format(a=res.rows_in, b=len(res.rows), c=len(res.changes),
                                      d=sum(bool(r["review"]) for r in res.rows), p=a.out / "report.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
