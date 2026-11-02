"""Exact TDS computation. No LLM involvement; every step is written to `trace`."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from tds_assist.categories import Category
from tds_assist.ledger import Ledger
from tds_assist.models import InvoiceLine
from tds_assist.pan import PayeeKind, payee_kind
from tds_assist.rules import lookup_rule, tax_year

_ZERO = Decimal("0")


@dataclass
class Computation:
    applies: bool
    act: str
    section_ref: str
    payment_code: str | None
    rate: Decimal
    base: Decimal  # amount TDS is charged on, including any catch-up
    tds: Decimal
    vendor_key: str
    group: str
    tax_year: str
    gross: Decimal  # this line's own amount after GST/material adjustments
    caught_up: Decimal = _ZERO  # earlier untaxed amounts pulled into this line's base
    trace: list[str] = field(default_factory=list)


def _check_amounts(line: InvoiceLine) -> None:
    if not isinstance(line.rent_months, int) or line.rent_months < 1:
        raise ValueError(f"rent_months must be a whole number of at least 1, got {line.rent_months!r}")
    for name in ("taxable_value", "gst", "material_value"):
        value = getattr(line, name)
        if value is not None and value < 0:
            raise ValueError(f"{name} is negative ({value}); credit notes are out of scope")
    if line.material_value and line.material_value > line.taxable_value:
        raise ValueError(f"material_value {line.material_value} exceeds taxable_value {line.taxable_value}")


def compute(line: InvoiceLine, category: Category, ledger: Ledger) -> Computation:
    _check_amounts(line)
    kind = payee_kind(line.vendor.pan)
    rule = lookup_rule(category, kind, line.date)
    if rule is None:
        raise ValueError(f"Cannot compute TDS for {category.value}")

    trace = [f"Payee type {kind.value} from PAN; Act {rule.act} applies on {line.date.isoformat()}; rule {rule.section_ref}"]

    gross = line.taxable_value
    if line.gst_separate:
        trace.append(f"GST {line.gst} shown separately, excluded from base (CBDT Circular 23/2017)")
    else:
        gross += line.gst
        trace.append(f"GST {line.gst} not shown separately, included in base")
    if category is Category.CONTRACT_WORK and line.material_value:
        gross -= line.material_value
        trace.append(f"Material {line.material_value} shown separately, excluded (s.393(1) Table Sl. No. 6 Note / 194C(3))")

    rate = rule.rate
    if kind is PayeeKind.NO_PAN:
        rate = max(rule.rate, rule.no_pan_rate)
        trace.append(f"No valid PAN: rate is the higher of {rule.rate} and {rule.no_pan_rate} (s.397(2)(b)(i) / 206AA)")

    ty = tax_year(line.date)
    vendor_key = (line.vendor.pan or "").strip().upper() if kind is not PayeeKind.NO_PAN else f"NOPAN:{line.vendor.name.strip().lower()}"
    prior_gross, prior_untaxed = ledger.prior(vendor_key, rule.group, ty)

    def result(applies: bool, base: Decimal, caught_up: Decimal = _ZERO) -> Computation:
        tds = (base * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if applies else _ZERO
        trace.append(f"TDS = {base} x {rate} = {tds}" if applies else "No TDS on this line")
        return Computation(applies, rule.act, rule.section_ref, rule.payment_code, rate, base if applies else _ZERO,
                           tds, vendor_key, rule.group, ty, gross, caught_up, trace)

    if category is Category.CONTRACT_WORK and line.vendor.transporter_declaration and kind is not PayeeKind.NO_PAN:
        ref = "s.393(4) Table Sl. No. 8" if rule.act == "ITA2025" else "s.194C(6)"
        trace.append(f"Goods-carriage operator declaration with PAN on file: no deduction ({ref})")
        return result(False, _ZERO)

    if rule.threshold_basis == "none":
        trace.append("No threshold for this category")
        return result(True, gross)

    if rule.threshold_basis == "month":
        monthly = gross / line.rent_months
        applies = monthly > rule.threshold_single
        trace.append(f"Rent per month {monthly:.2f} vs threshold {rule.threshold_single} per month")
        return result(applies, gross)

    total = prior_gross + gross
    if rule.threshold_basis == "excess":
        trace.append(f"Aggregate this tax year {total} vs {rule.threshold_aggregate}; tax only on the excess")
        if total <= rule.threshold_aggregate:
            return result(False, _ZERO)
        return result(True, min(gross, total - rule.threshold_aggregate))

    single_hit = rule.threshold_single is not None and gross > rule.threshold_single
    agg_hit = rule.threshold_aggregate is not None and total > rule.threshold_aggregate
    trace.append(
        f"Single {gross} vs {rule.threshold_single}; aggregate {total} (prior {prior_gross}) vs {rule.threshold_aggregate}"
    )
    if agg_hit and prior_untaxed > 0:
        trace.append(f"Aggregate threshold crossed: catch-up on earlier untaxed {prior_untaxed}")
        return result(True, gross + prior_untaxed, prior_untaxed)
    return result(single_hit or agg_hit, gross)
