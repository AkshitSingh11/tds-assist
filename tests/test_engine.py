from datetime import date
from decimal import Decimal

import pytest

from tds_assist.categories import Category
from tds_assist.engine import compute
from tds_assist.ledger import Ledger
from tds_assist.models import InvoiceLine, Vendor

FIRM = Vendor("Rao & Co, Chartered Accountants", "AAAFR1234M")
CO = Vendor("Cleanline Facility Services Pvt Ltd", "AABCC1234F")
PERSON = Vendor("Suresh Kumar", "ABCPK1234L")


def line(vendor, amount, *, on=date(2026, 6, 10), gst="0", gst_separate=True, **kw):
    return InvoiceLine(
        id="t", vendor=vendor, date=on, description="x", sac=None,
        taxable_value=Decimal(amount), gst=Decimal(gst), gst_separate=gst_separate, **kw,
    )


def test_gst_excluded_when_separate():
    c = compute(line(FIRM, "120000", gst="21600"), Category.PROFESSIONAL_FEES, Ledger())
    assert c.applies and c.base == Decimal("120000") and c.tds == Decimal("12000")
    assert c.section_ref == "393(1) Table Sl. No. 6(iii)(a)" and c.payment_code == "1027"


def test_gst_included_when_not_shown_separately():
    c = compute(line(FIRM, "120000", gst="21600", gst_separate=False), Category.PROFESSIONAL_FEES, Ledger())
    assert c.base == Decimal("141600") and c.tds == Decimal("14160")


def test_contract_single_below_threshold_no_tds():
    c = compute(line(CO, "25000"), Category.CONTRACT_WORK, Ledger())
    assert not c.applies and c.tds == Decimal("0")


def test_contract_single_above_threshold_taxed_alone():
    c = compute(line(PERSON, "45000"), Category.CONTRACT_WORK, Ledger())
    assert c.applies and c.rate == Decimal("0.01") and c.tds == Decimal("450")


def test_contract_aggregate_crossing_catches_up():
    ledger = Ledger()
    results = []
    for i in range(5):
        c = compute(line(CO, "25000", on=date(2026, 5, 1 + i)), Category.CONTRACT_WORK, ledger)
        ledger.post(c)
        results.append(c)
    assert [r.applies for r in results] == [False, False, False, False, True]
    assert results[4].base == Decimal("125000")
    assert results[4].tds == Decimal("2500")
    nxt = compute(line(CO, "25000", on=date(2026, 6, 1)), Category.CONTRACT_WORK, ledger)
    assert nxt.applies and nxt.base == Decimal("25000") and nxt.tds == Decimal("500")


def test_aggregate_resets_each_tax_year():
    ledger = Ledger()
    ledger.post(compute(line(FIRM, "45000", on=date(2026, 3, 1)), Category.PROFESSIONAL_FEES, ledger))
    c = compute(line(FIRM, "45000", on=date(2026, 4, 2)), Category.PROFESSIONAL_FEES, ledger)
    assert not c.applies


def test_unposted_lines_do_not_count_toward_aggregate():
    ledger = Ledger()
    compute(line(FIRM, "45000"), Category.PROFESSIONAL_FEES, ledger)
    c = compute(line(FIRM, "45000"), Category.PROFESSIONAL_FEES, ledger)
    assert not c.applies


def test_no_pan_twenty_percent():
    c = compute(line(Vendor("Unknown Tech", None), "60000"), Category.TECHNICAL_FEES, Ledger())
    assert c.rate == Decimal("0.20") and c.tds == Decimal("12000")
    assert any("397(2)" in t for t in c.trace)


def test_no_pan_goods_five_percent_on_excess():
    ledger = Ledger()
    ledger.post(compute(line(Vendor("X", None), "4000000"), Category.GOODS_PURCHASE, ledger))
    c = compute(line(Vendor("X", None), "2000000"), Category.GOODS_PURCHASE, ledger)
    assert c.rate == Decimal("0.05") and c.base == Decimal("1000000") and c.tds == Decimal("50000")


def test_rent_monthly_threshold():
    landlord = Vendor("Meera Iyer", "ABCPI1234K")
    quarterly = compute(line(landlord, "150000", rent_months=3), Category.RENT_LAND_BUILDING, Ledger())
    assert not quarterly.applies
    monthly = compute(line(landlord, "180000"), Category.RENT_LAND_BUILDING, Ledger())
    assert monthly.applies and monthly.tds == Decimal("18000")


def test_material_excluded():
    c = compute(line(CO, "200000", material_value=Decimal("120000")), Category.CONTRACT_WORK, Ledger())
    assert c.base == Decimal("80000") and c.tds == Decimal("1600")


def test_director_fee_nil_threshold():
    c = compute(line(PERSON, "10000"), Category.DIRECTOR_FEES, Ledger())
    assert c.applies and c.tds == Decimal("1000")


def test_transporter_declaration_exempt():
    t = Vendor("Ganesh Roadways", "ABCPG1234Q", transporter_declaration=True)
    c = compute(line(t, "90000"), Category.CONTRACT_WORK, Ledger())
    assert not c.applies and any("393(4)" in s for s in c.trace)


def test_transporter_declaration_ignored_without_pan():
    t = Vendor("Ganesh Roadways", None, transporter_declaration=True)
    c = compute(line(t, "90000"), Category.CONTRACT_WORK, Ledger())
    assert c.applies and c.tds == Decimal("18000")


def test_goods_excess_only():
    ledger = Ledger()
    ledger.post(compute(line(CO, "4000000"), Category.GOODS_PURCHASE, ledger))
    c = compute(line(CO, "2000000"), Category.GOODS_PURCHASE, ledger)
    assert c.base == Decimal("1000000") and c.tds == Decimal("1000")


def test_same_category_different_act_by_date():
    before = compute(line(FIRM, "80000", on=date(2026, 3, 20)), Category.PROFESSIONAL_FEES, Ledger())
    after = compute(line(FIRM, "80000", on=date(2026, 4, 20)), Category.PROFESSIONAL_FEES, Ledger())
    assert before.act == "ITA1961" and before.section_ref == "194J(1)(a)" and before.payment_code is None
    assert after.act == "ITA2025" and after.payment_code == "1027"
    assert before.tds == after.tds == Decimal("8000")


def test_tds_rounded_to_nearest_rupee():
    c = compute(line(PERSON, "45050"), Category.CONTRACT_WORK, Ledger())
    assert c.tds == Decimal("451")  # 450.50 rounds half-up


def test_needs_info_cannot_be_computed():
    with pytest.raises(ValueError):
        compute(line(FIRM, "1000"), Category.NEEDS_INFO, Ledger())


def test_rejects_invalid_amounts_and_months():
    import pytest
    from tds_assist.categories import Category
    from tds_assist.ledger import Ledger
    from tds_assist.engine import compute
    from tds_assist.models import InvoiceLine, Vendor
    from datetime import date
    from decimal import Decimal
    v = Vendor("X Ltd", "AABCX1234Q")
    bad = [
        InvoiceLine("a", v, date(2026, 6, 1), "rent", None, Decimal("100000"), Decimal("0"), True, rent_months=0),
        InvoiceLine("b", v, date(2026, 6, 1), "goods", None, Decimal("-100000"), Decimal("0"), True),
        InvoiceLine("c", v, date(2026, 6, 1), "print", None, Decimal("100000"), Decimal("0"), True, material_value=Decimal("150000")),
    ]
    cats = [Category.RENT_LAND_BUILDING, Category.GOODS_PURCHASE, Category.CONTRACT_WORK]
    for l, c in zip(bad, cats):
        with pytest.raises(ValueError):
            compute(l, c, Ledger())
