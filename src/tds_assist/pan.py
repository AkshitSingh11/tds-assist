import re
from enum import Enum

_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class PayeeKind(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    HUF = "HUF"
    COMPANY = "COMPANY"
    FIRM = "FIRM"
    OTHER = "OTHER"
    NO_PAN = "NO_PAN"


_FOURTH_CHAR = {"P": PayeeKind.INDIVIDUAL, "H": PayeeKind.HUF, "C": PayeeKind.COMPANY, "F": PayeeKind.FIRM}


def payee_kind(pan: str | None) -> PayeeKind:
    """Payee status from the 4th character of the PAN. Malformed or missing PAN counts as NO_PAN.

    This only checks the format. Whether the PAN is real and operative (linked to Aadhaar) needs
    a lookup against the income-tax portal, which is outside this prototype.
    """
    if not pan:
        return PayeeKind.NO_PAN
    pan = pan.strip().upper()
    if not _PAN.match(pan):
        return PayeeKind.NO_PAN
    return _FOURTH_CHAR.get(pan[3], PayeeKind.OTHER)
