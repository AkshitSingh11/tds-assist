"""Decisions a qualified reviewer has already made for a vendor and service.

Most AP volume is the same vendors billing the same services every month. Once a
reviewer has classified (PAN, SAC), later lines reuse that decision without the LLM,
and the audit record names the person who made it.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tds_assist.categories import Category


@dataclass(frozen=True)
class Precedent:
    pan: str
    sac: str
    category: Category
    decided_by: str
    decided_on: str  # ISO date
    note: str


def _key(pan: str | None, sac: str | None) -> tuple[str, str] | None:
    if not pan or not sac:
        return None
    return pan.strip().upper(), sac.strip()


class PrecedentStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._items: dict[tuple[str, str], Precedent] = {}
        if self._path.exists():
            for raw in json.loads(self._path.read_text(encoding="utf-8")):
                p = Precedent(**{**raw, "category": Category(raw["category"])})
                self._items[_key(p.pan, p.sac)] = p

    def lookup(self, pan: str | None, sac: str | None) -> Precedent | None:
        key = _key(pan, sac)
        return self._items.get(key) if key else None

    def add(self, p: Precedent) -> None:
        if p.category is Category.NEEDS_INFO:
            raise ValueError("A precedent must record a decided category")
        self._items[_key(p.pan, p.sac)] = p
        rows = [{**asdict(x), "category": x.category.value} for x in self._items.values()]
        self._path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
