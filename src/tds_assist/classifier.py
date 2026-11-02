"""The one probabilistic step: invoice line -> nature-of-payment category, with verbatim citations."""

import json
import re
from dataclasses import dataclass

from tds_assist.categories import DESCRIPTIONS, Category
from tds_assist.corpus import Chunk
from tds_assist.models import InvoiceLine

CONFIDENCE = ("high", "medium", "low")
MIN_QUOTE_WORDS = 4


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    quote: str


@dataclass
class Classification:
    category: Category
    citations: list[Citation]
    missing_facts: list[str]
    confidence: str
    rationale: str


SYSTEM = """You help an accounts-payable team in India decide the nature of a payment to a resident vendor, for tax deduction at source (TDS). The payer is a company.

Your only job is to choose ONE category for the invoice line and show which words of the statute support it. You do not decide rates, thresholds, section numbers or amounts; other software does that.

Categories:
{categories}

Rules:
1. Use only the statute clauses given in the user message. Do not rely on section numbers, circulars or case law from memory.
2. Each citation is an exact, contiguous quote of at least {min_words} words copied from one clause, with that clause's id.
3. If the line could reasonably fall into two categories that are taxed differently and the invoice text does not settle which, answer NEEDS_INFO and list the facts that would settle it. Do not guess.
4. confidence is "high" only if a tax reviewer reading the same invoice and clauses would almost certainly agree; "medium" if you lean one way but a reasonable reviewer could differ; otherwise "low".
5. Reply with one JSON object and nothing else:
{{"category": "<CATEGORY>", "citations": [{{"chunk_id": "<id>", "quote": "<exact words>"}}], "missing_facts": ["<fact>"], "confidence": "high|medium|low", "rationale": "<one or two sentences>"}}"""


def build_messages(line: InvoiceLine, chunks: list[Chunk]) -> list[dict]:
    categories = "\n".join(f"- {c.value}: {d}" for c, d in DESCRIPTIONS.items())
    clauses = "\n\n".join(f"[{c.id}] {c.ref}\n{c.text}" for c in chunks)
    user = (
        f"Statute clauses in force on {line.date.isoformat()} ({chunks[0].act}):\n\n{clauses}\n\n"
        f"Invoice line:\nVendor: {line.vendor.name}\nDescription: {line.description}\n"
        f"SAC code: {line.sac or 'not given'}"
    )
    return [
        {"role": "system", "content": SYSTEM.format(categories=categories, min_words=MIN_QUOTE_WORDS)},
        {"role": "user", "content": user},
    ]


def _first_json_object(raw: str) -> dict:
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", raw):
        try:
            obj, _ = decoder.raw_decode(raw[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "category" in obj:
            return obj
    raise ParseError("No JSON object with a 'category' field in the response")


def parse(raw: str) -> Classification:
    obj = _first_json_object(raw)
    try:
        category = Category(str(obj["category"]).strip().upper())
    except ValueError as e:
        raise ParseError(f"Unknown category {obj['category']!r}") from e
    confidence = str(obj.get("confidence", "")).strip().lower()
    if confidence not in CONFIDENCE:
        raise ParseError(f"Invalid confidence {obj.get('confidence')!r}")
    raw_citations = obj.get("citations") or []
    if not isinstance(raw_citations, list) or not all(isinstance(c, dict) for c in raw_citations):
        raise ParseError(f"citations must be a list of objects, got {raw_citations!r}")
    try:
        citations = [Citation(str(c["chunk_id"]), str(c["quote"])) for c in raw_citations]
    except KeyError as e:
        raise ParseError(f"Malformed citations: {e}") from e
    missing = obj.get("missing_facts") or []
    if isinstance(missing, str):
        missing = [missing]
    if not isinstance(missing, list):
        raise ParseError(f"missing_facts must be a list, got {missing!r}")
    missing = [str(m) for m in missing]
    return Classification(category, citations, missing, confidence, str(obj.get("rationale", "")))


def _norm(s: str) -> str:
    """Matching ignores case, whitespace, quotation marks, dashes and the rupee sign: models copy
    the words faithfully but drop or retype that punctuation. Every word must still match."""
    s = re.sub(r"[\s\"'“”‘’\-–—₹]+", "", s.lower())
    return s.strip(".,;:")


def _occurrences(needle: str, hay: str) -> list[tuple[int, int]]:
    out, i = [], hay.find(needle)
    while i != -1:
        out.append((i, i + len(needle)))
        i = hay.find(needle, i + 1)
    return out


def _supports(chunk: Chunk, quote: str, category: str) -> bool:
    """True if some occurrence of the quote overlaps a part of the clause that grounds `category`
    and no part that grounds a different category. A clause shared by several categories
    (e.g. rent of machinery at 2% vs rent of land at 10%) supports each only through its own words."""
    text = _norm(chunk.text)
    regions = [(cat, (0, len(text)) if span == "*" else _occurrences(_norm(span), text)[0])
               for cat, span in chunk.spans]
    for start, end in _occurrences(_norm(quote), text):
        hits = {cat for cat, (s, e) in regions if start < e and s < end}
        if hits == {category}:
            return True
    return False


def verify(c: Classification, chunks: list[Chunk]) -> list[str]:
    """Deterministic grounding check. An empty list means every citation is real and in force."""
    by_id = {ch.id: ch for ch in chunks}
    errors = []
    if c.category is Category.NEEDS_INFO:
        if not c.missing_facts:
            errors.append("NEEDS_INFO without any missing facts named")
        return errors
    if not c.citations:
        return [f"{c.category.value} given without any citation"]
    supported = False
    for cit in c.citations:
        chunk = by_id.get(cit.chunk_id)
        if chunk is None:
            errors.append(f"{cit.chunk_id}: clause not in force on the invoice date (or unknown id)")
            continue
        if len(cit.quote.split()) < MIN_QUOTE_WORDS:
            errors.append(f"{cit.chunk_id}: quote shorter than {MIN_QUOTE_WORDS} words: {cit.quote!r}")
            continue
        if _norm(cit.quote) not in _norm(chunk.text):
            errors.append(f"{cit.chunk_id}: quote not found in clause text: {cit.quote!r}")
            continue
        supported = supported or _supports(chunk, cit.quote, c.category.value)
    if not errors and not supported:
        errors.append(f"No cited clause supports {c.category.value}")
    return errors
