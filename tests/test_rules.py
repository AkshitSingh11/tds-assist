from datetime import date
from decimal import Decimal

from tds_assist.categories import Category
from tds_assist.corpus import load_corpus
from tds_assist.pan import PayeeKind, payee_kind
from tds_assist.rules import lookup_rule, tax_year


def test_payee_kind_from_fourth_pan_character():
    assert payee_kind("AABCT1234F") == PayeeKind.COMPANY
    assert payee_kind("ABCPK1234L") == PayeeKind.INDIVIDUAL
    assert payee_kind("AAAHS1234K") == PayeeKind.HUF
    assert payee_kind("AAAFR1234M") == PayeeKind.FIRM
    assert payee_kind("AAATR1234M") == PayeeKind.OTHER


def test_malformed_pan_is_no_pan():
    assert payee_kind("bad") == PayeeKind.NO_PAN
    assert payee_kind("ABCPK12345") == PayeeKind.NO_PAN
    assert payee_kind("") == PayeeKind.NO_PAN
    assert payee_kind(None) == PayeeKind.NO_PAN


def test_pan_is_normalised_before_checking():
    assert payee_kind(" abcpk1234l ") == PayeeKind.INDIVIDUAL


def test_professional_fees_after_switch_maps_to_section_393():
    rule = lookup_rule(Category.PROFESSIONAL_FEES, PayeeKind.FIRM, date(2026, 5, 1))
    assert "393(1)" in rule.section_ref
    assert rule.payment_code == "1027"
    assert rule.rate == Decimal("0.10")
    assert rule.chunk_id == "2025:393(1)T6(iii)"


def test_professional_fees_before_switch_maps_to_194j():
    rule = lookup_rule(Category.PROFESSIONAL_FEES, PayeeKind.FIRM, date(2026, 3, 15))
    assert rule.section_ref == "194J(1)(a)"
    assert rule.act == "ITA1961"


def test_contract_rate_depends_on_payee_kind():
    on = date(2026, 6, 1)
    assert lookup_rule(Category.CONTRACT_WORK, PayeeKind.INDIVIDUAL, on).rate == Decimal("0.01")
    assert lookup_rule(Category.CONTRACT_WORK, PayeeKind.HUF, on).rate == Decimal("0.01")
    assert lookup_rule(Category.CONTRACT_WORK, PayeeKind.COMPANY, on).rate == Decimal("0.02")
    assert lookup_rule(Category.CONTRACT_WORK, PayeeKind.COMPANY, on).payment_code == "1024"


def test_no_pan_contract_uses_non_individual_row_and_twenty_percent():
    rule = lookup_rule(Category.CONTRACT_WORK, PayeeKind.NO_PAN, date(2026, 6, 1))
    assert rule.no_pan_rate == Decimal("0.20")


def test_needs_info_has_no_rule():
    assert lookup_rule(Category.NEEDS_INFO, PayeeKind.COMPANY, date(2026, 6, 1)) is None


def test_every_category_has_a_rule_in_both_acts():
    for on in (date(2025, 10, 1), date(2026, 10, 1)):
        for cat in Category:
            if cat is Category.NEEDS_INFO:
                continue
            assert lookup_rule(cat, PayeeKind.COMPANY, on) is not None, (cat, on)


def test_rule_cites_chunk_in_force_on_that_date():
    for on in (date(2025, 10, 1), date(2026, 10, 1)):
        ids = {c.id for c in load_corpus(on)}
        for cat in Category:
            rule = lookup_rule(cat, PayeeKind.COMPANY, on)
            if rule is not None and rule.chunk_id is not None:
                assert rule.chunk_id in ids, (cat, on, rule.chunk_id)


def test_corpus_selected_by_date():
    before = load_corpus(date(2026, 3, 31))
    after = load_corpus(date(2026, 4, 1))
    assert before and all(c.act == "ITA1961" for c in before)
    assert after and all(c.act == "ITA2025" for c in after)
    assert all(c.source_url.startswith("https://") for c in before + after)


def test_corpus_outside_supported_range_raises():
    import pytest

    with pytest.raises(ValueError):
        load_corpus(date(2024, 12, 1))


def test_tax_year():
    assert tax_year(date(2026, 3, 31)) == "2025-26"
    assert tax_year(date(2026, 4, 1)) == "2026-27"
