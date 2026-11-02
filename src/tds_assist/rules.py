"""Section, rate, threshold and payment code for each category, by date.

This is the part of the system that goes out of date when the law changes, so it is
plain data in code, reviewed like code, and versioned. The LLM never sees or produces
any of it.

Sources:
- ITA2025: Income-tax Act 2025, s.393(1) Table (Sl. Nos. 1, 2, 6, 8) and s.397(2)(b)(i)
  for the no-PAN rate. Payment codes are from CBDT's section-code list as reported by
  several secondary sources (taxguru.in, figmentglobal.com); the goods code 1031 was found
  in only one source and should be checked before use.
- ITA1961 (FY 2025-26): ss.194C, 194J, 194H, 194-I, 194Q, 206AA, as amended by the
  Finance Act 2025 (thresholds raised from 1 April 2025). Payment codes did not exist
  under the old Act; returns used section codes, which are not modelled here.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from tds_assist.categories import Category
from tds_assist.pan import PayeeKind

RULES_VERSION = "2026-11-01.1"
ACT_2025_FROM = date(2026, 4, 1)

Basis = Literal["year", "month", "none", "excess"]


@dataclass(frozen=True)
class Rule:
    act: str
    category: Category
    section_ref: str
    payment_code: str | None
    rate: Decimal
    no_pan_rate: Decimal
    threshold_single: Decimal | None
    threshold_aggregate: Decimal | None
    threshold_basis: Basis
    chunk_id: str | None
    group: str


def tax_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


_D = Decimal
_TWENTY = _D("0.20")


def _r(act, cat, ref, code, rate, single, agg, basis, chunk, no_pan=_TWENTY):
    return Rule(act, cat, ref, code, _D(rate), no_pan, single and _D(single), agg and _D(agg), basis, chunk, cat.value)


C = Category

# (category, individual_or_huf) -> Rule. individual_or_huf only matters for contract work.
_ITA2025 = {
    (C.CONTRACT_WORK, True): _r("ITA2025", C.CONTRACT_WORK, "393(1) Table Sl. No. 6(i).D(a)", "1023", "0.01", "30000", "100000", "year", "2025:393(1)T6(i)"),
    (C.CONTRACT_WORK, False): _r("ITA2025", C.CONTRACT_WORK, "393(1) Table Sl. No. 6(i).D(b)", "1024", "0.02", "30000", "100000", "year", "2025:393(1)T6(i)"),
    (C.PROFESSIONAL_FEES, None): _r("ITA2025", C.PROFESSIONAL_FEES, "393(1) Table Sl. No. 6(iii)(a)", "1027", "0.10", None, "50000", "year", "2025:393(1)T6(iii)"),
    (C.TECHNICAL_FEES, None): _r("ITA2025", C.TECHNICAL_FEES, "393(1) Table Sl. No. 6(iii)(b)", "1026", "0.02", None, "50000", "year", "2025:393(1)T6(iii)"),
    (C.DIRECTOR_FEES, None): _r("ITA2025", C.DIRECTOR_FEES, "393(1) Table Sl. No. 6(iii)(c)", "1028", "0.10", None, None, "none", "2025:393(1)T6(iii)"),
    (C.COMMISSION, None): _r("ITA2025", C.COMMISSION, "393(1) Table Sl. No. 1(ii)", "1006", "0.02", None, "20000", "year", "2025:393(1)T1"),
    (C.RENT_PLANT_MACHINERY, None): _r("ITA2025", C.RENT_PLANT_MACHINERY, "393(1) Table Sl. No. 2(ii)(a)", "1008", "0.02", "50000", None, "month", "2025:393(1)T2"),
    (C.RENT_LAND_BUILDING, None): _r("ITA2025", C.RENT_LAND_BUILDING, "393(1) Table Sl. No. 2(ii)(b)", "1009", "0.10", "50000", None, "month", "2025:393(1)T2"),
    (C.GOODS_PURCHASE, None): _r("ITA2025", C.GOODS_PURCHASE, "393(1) Table Sl. No. 8(ii)", "1031", "0.001", None, "5000000", "excess", "2025:393(1)T8(ii)", no_pan=_D("0.05")),
}

_ITA1961 = {
    (C.CONTRACT_WORK, True): _r("ITA1961", C.CONTRACT_WORK, "194C(1)(i)", None, "0.01", "30000", "100000", "year", "1961:194C(1)"),
    (C.CONTRACT_WORK, False): _r("ITA1961", C.CONTRACT_WORK, "194C(1)(ii)", None, "0.02", "30000", "100000", "year", "1961:194C(1)"),
    (C.PROFESSIONAL_FEES, None): _r("ITA1961", C.PROFESSIONAL_FEES, "194J(1)(a)", None, "0.10", None, "50000", "year", "1961:194J-Expl"),
    (C.TECHNICAL_FEES, None): _r("ITA1961", C.TECHNICAL_FEES, "194J(1)(b)", None, "0.02", None, "50000", "year", "1961:194J-Expl"),
    (C.DIRECTOR_FEES, None): _r("ITA1961", C.DIRECTOR_FEES, "194J(1)(ba)", None, "0.10", None, None, "none", None),
    (C.COMMISSION, None): _r("ITA1961", C.COMMISSION, "194H", None, "0.02", None, "20000", "year", "1961:194H-Expl(i)"),
    (C.RENT_PLANT_MACHINERY, None): _r("ITA1961", C.RENT_PLANT_MACHINERY, "194-I(a)", None, "0.02", "50000", None, "month", "1961:194I-Expl(i)"),
    (C.RENT_LAND_BUILDING, None): _r("ITA1961", C.RENT_LAND_BUILDING, "194-I(b)", None, "0.10", "50000", None, "month", "1961:194I-Expl(i)"),
    (C.GOODS_PURCHASE, None): _r("ITA1961", C.GOODS_PURCHASE, "194Q", None, "0.001", None, "5000000", "excess", None, no_pan=_D("0.05")),
}

_ITA1961_FROM = date(2025, 4, 1)


def lookup_rule(category: Category, payee: PayeeKind, on: date) -> Rule | None:
    if category is Category.NEEDS_INFO:
        return None
    if on >= ACT_2025_FROM:
        table = _ITA2025
    elif on >= _ITA1961_FROM:
        table = _ITA1961
    else:
        raise ValueError(f"No rule table covers {on.isoformat()}")
    if category is Category.CONTRACT_WORK:
        return table[(category, payee in (PayeeKind.INDIVIDUAL, PayeeKind.HUF))]
    return table[(category, None)]
