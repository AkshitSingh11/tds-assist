from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tds_assist.engine import Computation

_ZERO = Decimal("0")


class Ledger:
    """Per-vendor, per-rule-group running totals for a tax year.

    Thresholds such as "₹1,00,000 in aggregate" are about the year, not the invoice, so a
    per-invoice classifier cannot get them right on its own. Only approved lines are posted.
    """

    def __init__(self) -> None:
        self._gross: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: _ZERO)
        self._untaxed: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: _ZERO)

    def prior(self, vendor_key: str, group: str, tax_year: str) -> tuple[Decimal, Decimal]:
        key = (vendor_key, group, tax_year)
        return self._gross[key], self._untaxed[key]

    def post(self, c: "Computation") -> None:
        key = (c.vendor_key, c.group, c.tax_year)
        self._gross[key] += c.gross
        if c.caught_up:
            self._untaxed[key] = _ZERO
        if not c.applies:
            self._untaxed[key] += c.gross
