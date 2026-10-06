"""Генерирует синтетический «грязный» CSV (вымышленные люди, example.com). Детерминированно."""
from __future__ import annotations

import random
from pathlib import Path

random.seed(7)
FIRST = ["Anna", "Pierre", "Olena", "Marco", "Sophie", "Jonas", "Maria", "Luc", "Iryna", "Tom"]
LAST = ["Martin", "Dubois", "Kovalenko", "Rossi", "Bernard", "Weber", "Petit", "Moreau", "Shevchenko", "Brown"]
COUNTRIES = ["FR", "France", "FRANCE", "UK", "United Kingdom", "DE", "Germany", "USA", "ua", "Spain"]


def messy_date(i: int) -> str:
    d, m, y = random.randint(13, 28), random.randint(1, 12), random.choice([2024, 2025, 2026])
    return random.choice([f"{y}-{m:02d}-{d:02d}", f"{d:02d}/{m:02d}/{y}", f"{d}.{m}.{y}", f"{d:02d}-{m:02d}-{y}"])


def messy_amount() -> str:
    v = random.randint(500, 250000) / 100
    s = f"{v:.2f}"
    return random.choice([s, s.replace(".", ","), f"€ {s}", f"{v:,.2f}", f"{s.replace('.', ',')} EUR"])


def messy_phone() -> str:
    n = "".join(random.choice("0123456789") for _ in range(8))
    n = "3998" + n[4:]  # ARCEP-reserved fictional mobile range 06 39 98 xx xx
    return random.choice([f"06 {n[:2]} {n[2:4]} {n[4:6]} {n[6:]}", f"+33 6{n}", f"06.{n[:2]}.{n[2:4]}.{n[4:6]}.{n[6:]}", f"0033 6{n}"])


rows = []
for i in range(36):
    f, l = random.choice(FIRST), random.choice(LAST)
    name = random.choice([f"{f} {l}", f"  {f.upper()}  {l.upper()} ", f"{f.lower()} {l.lower()}"])
    email = f"{f}.{l}{i}@example.com"
    email = random.choice([email, email.upper(), f" {email} "])
    rows.append([name, email, messy_phone(), messy_date(i), messy_amount(), random.choice(COUNTRIES)])

rows[5][1] = "not-an-email"              # неверный email
rows[9][3] = "31/02/2025"                # несуществующая дата
rows[12][4] = "n/a"                      # не число
rows[17][2] = "12345"                    # короткий телефон
rows.append(list(rows[2]))               # точный дубликат
dup = list(rows[7]); dup[1] = dup[1].upper(); dup[2] = ""; rows.append(dup)   # дубликат, менее полный
rows.insert(20, ["", "", "", "", "", ""])  # пустая строка

out = Path(__file__).parent / "input" / "messy_customers.csv"
out.parent.mkdir(exist_ok=True)
header = [" Customer Name ", "E-mail", "Phone number", "Signup date", "Order total (EUR)", "country"]
# разделитель ';' и cp1252, как отдаёт французский Excel
lines = [";".join(header)] + [";".join(r) for r in rows]
out.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp1252"))
print(f"{out}: {len(rows)} data rows")
