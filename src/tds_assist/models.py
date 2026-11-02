from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Vendor:
    name: str
    pan: str | None
    # Goods-carriage operator who has declared owning <= 10 carriages (s.393(4) Table Sl. No. 8).
    transporter_declaration: bool = False


@dataclass(frozen=True)
class InvoiceLine:
    id: str
    vendor: Vendor
    date: date
    description: str
    sac: str | None  # GST Services Accounting Code, as printed on the invoice
    taxable_value: Decimal
    gst: Decimal
    gst_separate: bool
    # Fill only for jobs under s.402(47)(e) (manufacture to the customer's specification),
    # where the invoice shows the value of material separately.
    material_value: Decimal | None = None
    rent_months: int = 1  # number of months a rent invoice covers
