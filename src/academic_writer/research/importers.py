"""Import de notices bibliographiques exportées depuis un catalogue (RIS ou BibTeX).

Formats produits par Zotero, Mendeley, Google Scholar, eLIBRARY, les catalogues de bibliothèques
(РГБ, bibliothèque universitaire) : les métadonnées sont celles du catalogue, donc fiables.
Analyse tolérante, sans exécution de contenu ; encodage détecté automatiquement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from academic_writer.research.models import Person, SourceData

RIS_TYPES = {"BOOK": "book", "EBOOK": "book", "EDBOOK": "book", "JOUR": "article", "EJOUR": "article",
             "MGZN": "article", "NEWS": "article", "CHAP": "chapter", "ECHAP": "chapter", "CONF": "conference",
             "CPAPER": "conference", "THES": "thesis", "STAND": "standard", "ELEC": "web", "WEB": "web",
             "RPRT": "report", "PAT": "patent"}
BIB_TYPES = {"book": "book", "mvbook": "book", "article": "article", "inbook": "chapter", "incollection": "chapter",
             "inproceedings": "conference", "conference": "conference", "phdthesis": "thesis",
             "mastersthesis": "thesis", "thesis": "thesis", "techreport": "report", "report": "report",
             "online": "web", "standard": "standard", "patent": "patent", "misc": "other"}


@dataclass
class ImportedEntry:
    source_type: str
    data: SourceData
    key: str | None = None
    problems: list[str] = field(default_factory=list)


def _person(text: str) -> Person:
    text = " ".join(text.replace("{", "").replace("}", "").split()).strip(" ,;")
    if "," in text:
        family, given = [p.strip() for p in text.split(",", 1)]
        return Person(family=family, given=given or None)
    parts = text.split(" ")
    if len(parts) == 1:
        return Person(family=parts[0])
    if re.search(r"[А-Яа-яЁё]", text) or re.fullmatch(r"(?:[A-ZА-Я]\.\s?){1,3}", " ".join(parts[1:])):
        return Person(family=parts[0], given=" ".join(parts[1:]))
    return Person(family=parts[-1], given=" ".join(parts[:-1]))


def _year(value: str | None) -> int | None:
    match = re.search(r"(1[5-9]|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _isbn_or_issn(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    compact = re.sub(r"[^0-9Xx]", "", value)
    if len(compact) == 8:
        return None, value.strip()
    if len(compact) in (10, 13):
        return value.strip(), None
    return None, None


# --- RIS -----------------------------------------------------------------------------

def parse_ris(text: str) -> list[ImportedEntry]:
    entries: list[ImportedEntry] = []
    record: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line.rstrip())
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "ER":
            if record:
                entries.append(_ris_entry(record))
            record = {}
            continue
        record.setdefault(tag, []).append(value)
    if record.get("TY"):
        entries.append(_ris_entry(record))
    return entries


def _ris_entry(r: dict[str, list[str]]) -> ImportedEntry:
    first = lambda *tags: next((r[t][0] for t in tags if r.get(t) and r[t][0]), None)  # noqa: E731
    ris_type = (first("TY") or "GEN").upper()
    source_type = RIS_TYPES.get(ris_type, "other")
    start, end = first("SP"), first("EP")
    pages = f"{start}–{end}" if start and end else start
    isbn, issn = _isbn_or_issn(first("SN"))
    container = first("T2", "JO", "JF", "JA", "BT") if source_type != "book" else None
    data = SourceData(
        authors=[_person(a) for t in ("AU", "A1") for a in r.get(t, [])],
        editors=[_person(a) for t in ("ED", "A2", "A3") for a in r.get(t, [])] if source_type in ("chapter", "book") else [],
        title=first("TI", "T1", "CT"), container=container, publisher=first("PB"), place=first("CY", "PP"),
        year=_year(first("PY", "Y1", "DA")), edition=first("ET"), volume=first("VL"), issue=first("IS"), pages=pages,
        doi=first("DO"), isbn=isbn, issn=issn, url=first("UR", "L2"), language=first("LA"),
        accessed=first("Y2") if source_type == "web" else None,
        standard_number=first("M1") if source_type == "standard" else None,
    )
    return ImportedEntry(source_type=source_type, data=data, key=first("ID"))


# --- BibTeX ------------------------------------------------------------------------------

def _bib_value(raw: str) -> str:
    value = raw.strip().rstrip(",").strip()
    if (value.startswith("{") and value.endswith("}")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    value = value.replace("{", "").replace("}", "").replace("\\&", "&").replace("--", "–")
    return " ".join(value.split())


def _bib_fields(body: str) -> dict[str, str]:
    """Champs « nom = {valeur} » avec accolades imbriquées."""
    fields: dict[str, str] = {}
    index = 0
    while index < len(body):
        match = re.compile(r"\s*([A-Za-z][\w-]*)\s*=\s*").match(body, index)
        if not match:
            next_comma = body.find(",", index)
            if next_comma == -1:
                break
            index = next_comma + 1
            continue
        name, index = match.group(1).lower(), match.end()
        if index < len(body) and body[index] in "{\"":
            opener = body[index]
            depth, start = 0, index
            while index < len(body):
                char = body[index]
                if opener == "{":
                    depth += char == "{"
                    depth -= char == "}"
                    if depth == 0:
                        index += 1
                        break
                elif char == '"' and index > start:
                    index += 1
                    break
                index += 1
            fields[name] = _bib_value(body[start:index])
        else:
            end = body.find(",", index)
            end = len(body) if end == -1 else end
            fields[name] = _bib_value(body[index:end])
            index = end
        comma = body.find(",", index)
        index = len(body) if comma == -1 else comma + 1
    return fields


def parse_bibtex(text: str) -> list[ImportedEntry]:
    entries: list[ImportedEntry] = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", text):
        kind = match.group(1).lower()
        if kind in ("comment", "preamble", "string"):
            continue
        depth, index = 1, match.end()
        while index < len(text) and depth:
            depth += text[index] == "{"
            depth -= text[index] == "}"
            index += 1
        f = _bib_fields(text[match.end(): index - 1])
        source_type = BIB_TYPES.get(kind, "other")
        if source_type == "other" and f.get("url"):
            source_type = "web"
        isbn, issn = f.get("isbn"), f.get("issn")
        data = SourceData(
            authors=[_person(a) for a in re.split(r"\s+and\s+", f["author"]) if a.strip()] if f.get("author") else [],
            editors=[_person(a) for a in re.split(r"\s+and\s+", f["editor"]) if a.strip()] if f.get("editor") else [],
            title=f.get("title"), subtitle=f.get("subtitle"),
            container=f.get("journal") or f.get("journaltitle") or f.get("booktitle"),
            publisher=f.get("publisher") or f.get("school") or f.get("institution") or f.get("organization"),
            place=f.get("address") or f.get("location"), year=_year(f.get("year") or f.get("date")),
            edition=f.get("edition"), volume=f.get("volume"), issue=f.get("number") or f.get("issue"),
            pages=f.get("pages") or f.get("pagetotal"), doi=f.get("doi"), isbn=isbn, issn=issn, url=f.get("url"),
            accessed=f.get("urldate"), language=f.get("langid") or f.get("language"),
            standard_number=f.get("number") if source_type == "standard" else None,
        )
        key = match.group(2) if re.fullmatch(r"[A-Za-z0-9_:\-]{2,40}", match.group(2) or "") else None
        entries.append(ImportedEntry(source_type=source_type, data=data, key=key))
    return entries


def parse_file(text: str, extension: str) -> list[ImportedEntry]:
    if extension == ".bib" or (extension == ".txt" and "@" in text and re.search(r"@\w+\s*\{", text)):
        return parse_bibtex(text)
    return parse_ris(text)
