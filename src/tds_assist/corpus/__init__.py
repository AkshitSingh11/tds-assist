"""Statute text the LLM is allowed to cite, versioned by the Act in force on a date."""

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent
_FILES = ("ita1961.json", "ita2025.json")


@dataclass(frozen=True)
class Chunk:
    id: str
    act: str
    ref: str
    text: str
    source_url: str
    retrieved_on: str
    # (category, span) pairs: the parts of the clause that can ground that category; "*" = whole clause
    spans: tuple[tuple[str, str], ...] = ()

    @property
    def supports(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(cat for cat, _ in self.spans))


@cache
def _acts() -> tuple[tuple[date, date | None, tuple[Chunk, ...]], ...]:
    acts = []
    for name in _FILES:
        raw = json.loads((_DIR / name).read_text(encoding="utf-8"))
        chunks = tuple(
            Chunk(c["id"], raw["act"], c["ref"], c["text"], c["source_url"], raw["retrieved_on"],
                  tuple((cat, span) for cat, spans in c["supports"].items() for span in spans))
            for c in raw["chunks"]
        )
        start = date.fromisoformat(raw["effective_from"])
        end = date.fromisoformat(raw["effective_to"]) if raw["effective_to"] else None
        acts.append((start, end, chunks))
    return tuple(acts)


def load_corpus(on: date) -> list[Chunk]:
    for start, end, chunks in _acts():
        if start <= on and (end is None or on <= end):
            return list(chunks)
    raise ValueError(f"No statute corpus covers {on.isoformat()}")


def corpus_version(on: date) -> str:
    chunks = load_corpus(on)
    return f"{chunks[0].act}@{chunks[0].retrieved_on}"
