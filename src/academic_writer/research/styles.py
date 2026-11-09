"""Mise en forme bibliographique et appels de citation.

Styles : ГОСТ Р 7.0.100-2018 / 7.0.5-2008 (« gost »), APA 7, IEEE, Chicago (auteur-date), Vancouver,
Harvard (Cite Them Right) et ISO 690:2021 (auteur-date).
Les citations sont stockées dans le texte sous forme STABLE : [@clé] ou [@clé, с. 15] (plusieurs :
[@a; @b]). Leur rendu ([1], (Иванов, 2020)…) est calculé à partir du style choisi.
Mise en forme simplifiée mais fidèle aux éléments principaux de chaque norme : à relire selon les
exigences de l'établissement.
"""

from __future__ import annotations

import re

from academic_writer.research.models import Person, SourceData

STYLE_LABELS = {
    "gost": "ГОСТ Р 7.0.100-2018 (description) / ГОСТ Р 7.0.5-2008 (références)",
    "apa": "APA 7e édition", "ieee": "IEEE", "chicago": "Chicago (auteur-date)", "vancouver": "Vancouver (ICMJE)",
    "harvard": "Harvard (Cite Them Right)", "iso690": "ISO 690:2021 (auteur-date)",
}
NUMERIC_STYLES = {"gost", "ieee", "vancouver"}
MARKER = re.compile(r"\[(@[^\[\]]+)\]")
ITEM = re.compile(r"@([A-Za-z0-9_:\-]+)(?:\s*,\s*([^;]+))?")


def parse_markers(text: str) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """[(marqueur complet, [(clé, localisation)])] dans l'ordre d'apparition."""
    result = []
    for match in MARKER.finditer(text):
        items = [(m.group(1), (m.group(2) or "").strip() or None) for m in ITEM.finditer(match.group(1))]
        if items:
            result.append((match.group(0), items))
    return result


def _cyrillic(text: str | None) -> bool:
    return bool(text) and bool(re.search(r"[А-Яа-яЁё]", text or ""))


def _is_russian(data: SourceData) -> bool:
    return (data.language or "").lower() == "ru" or (not data.language and _cyrillic((data.title or "")
                                                                                     + (data.container or "")))


def initials(given: str | None, spaced: bool = True) -> str:
    if not given:
        return ""
    parts = []
    for word in re.split(r"\s+", given.strip()):
        pieces = [p for p in word.split("-") if p]
        joined = "-".join(f"{p[0].upper()}." for p in pieces if p[0].isalpha())
        if joined:
            parts.append(joined)
    return (" " if spaced else "").join(parts)


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.\s*\.", ".", text)
    # Pas d'espace avant . , ; — mais l'espace avant « : » est conservé (ГОСТ : « Москва : Издательство »).
    text = re.sub(r"\s+([.,;])", r"\1", text).replace(" .", ".")
    return text


def _segments(*parts: str | None) -> str:
    """Zones ГОСТ séparées par « . – »."""
    kept = [p.strip().rstrip(".") for p in parts if p and p.strip()]
    return _clean(". – ".join(kept) + ".") if kept else ""


# --- noms -------------------------------------------------------------------------

def gost_heading(person: Person) -> str:
    return f"{person.family}, {initials(person.given)}".rstrip(", ")


def gost_resp(person: Person) -> str:
    return f"{initials(person.given)} {person.family}".strip()


def apa_name(person: Person) -> str:
    return f"{person.family}, {initials(person.given)}".rstrip(", ")


def ieee_name(person: Person) -> str:
    return f"{initials(person.given)} {person.family}".strip()


def vancouver_name(person: Person) -> str:
    return f"{person.family} {initials(person.given, spaced=False).replace('.', '')}".strip()


def chicago_name(person: Person, first: bool) -> str:
    if not person.given:
        return person.family
    return f"{person.family}, {person.given}" if first else f"{person.given} {person.family}"


def _join(names: list[str], conj: str, oxford: bool = True) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}{',' if oxford and conj == '&' else ''} {conj} {names[1]}"
    return ", ".join(names[:-1]) + f"{',' if oxford else ''} {conj} {names[-1]}"


# --- ГОСТ ---------------------------------------------------------------------------

def format_gost(source_type: str, d: SourceData) -> str:
    ru = _is_russian(d)
    pages_total = (lambda p: f"{p} с." if ru else f"{p} p.")
    page_range = (lambda p: f"С. {p}" if ru else f"P. {p}")
    title = (d.title or "").strip()
    if d.subtitle:
        title += f" : {d.subtitle}"
    authors = d.authors
    heading = gost_heading(authors[0]) if 1 <= len(authors) <= 3 else ""
    if authors:
        shown = [gost_resp(p) for p in authors[:3]]
        resp = ", ".join(shown) + (" [и др.]" if len(authors) > 3 else "")
    elif d.editors:
        resp = ("под редакцией " if ru else "edited by ") + ", ".join(gost_resp(p) for p in d.editors[:3])
    else:
        resp = ""
    head = f"{heading} {title}" if heading else title
    if resp:
        head += f" / {resp}"
    edition = (f"{d.edition}-е изд." if ru and d.edition and d.edition.isdigit() else
               (f"{d.edition} ed." if d.edition and d.edition.isdigit() else d.edition))
    imprint = None
    if d.publisher or d.place or d.year:
        imprint = (f"{d.place} : " if d.place else "") + (d.publisher or "") + (f", {d.year}" if d.year else "")
        imprint = imprint.strip(" ,:")
    doi = f"DOI {d.doi}" if d.doi else None
    isbn = f"ISBN {d.isbn}" if d.isbn else None
    url = f"URL: {d.url}" + (f" (дата обращения: {d.accessed})" if d.accessed else "") if d.url else None
    if source_type in ("article", "conference"):
        volume = ", ".join(filter(None, [(f"Т. {d.volume}" if ru else f"Vol. {d.volume}") if d.volume else None,
                                          (f"№ {d.issue}" if ru else f"no. {d.issue}") if d.issue else None]))
        container = f"{head} // {d.container}" if d.container else head
        return _segments(container, str(d.year) if d.year else None, volume or None,
                         page_range(d.pages) if d.pages else None, doi, url)
    if source_type == "chapter":
        editors = (" / под редакцией " if ru else " / ed. by ") + ", ".join(gost_resp(p) for p in d.editors[:3]) \
            if d.editors else ""
        return _segments(f"{head} // {d.container or ''}{editors}", imprint, page_range(d.pages) if d.pages else None,
                         doi)
    if source_type == "standard":
        number = d.standard_number or ""
        return _segments(f"{number}. {title}" if number else title, edition, imprint,
                         pages_total(d.pages) if d.pages else None, url)
    if source_type == "web":
        return _segments(head, "Текст : электронный" + (f" // {d.container}" if d.container else ""), url)
    if source_type in ("thesis", "report"):
        kind = d.subtitle or ("диссертация" if source_type == "thesis" and ru else "отчет" if ru else None)
        base = f"{heading} {d.title or ''}".strip() if heading else (d.title or "")
        base += f" : {kind}" if kind and not d.subtitle else (f" : {d.subtitle}" if d.subtitle else "")
        base += f" / {resp}" if resp else ""
        return _segments(base, imprint, pages_total(d.pages) if d.pages else None, url)
    return _segments(head, edition, imprint, pages_total(d.pages) if d.pages else None, isbn, doi, url)


# --- APA 7 --------------------------------------------------------------------------

def format_apa(source_type: str, d: SourceData) -> str:
    names = [apa_name(p) for p in d.authors[:20]]
    authors = _join(names, "&")
    year = f"({d.year})" if d.year else "(n.d.)"
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    doi = f" https://doi.org/{d.doi}" if d.doi else (f" {d.url}" if d.url else "")
    if source_type in ("article", "conference"):
        volume = f", *{d.volume}*" if d.volume else ""
        issue = f"({d.issue})" if d.issue else ""
        pages = f", {d.pages}" if d.pages else ""
        return _clean(f"{authors} {year}. {title}. *{d.container or ''}*{volume}{issue}{pages}.{doi}")
    if source_type == "chapter":
        editors = _join([ieee_name(p) for p in d.editors], "&")
        eds = f"In {editors} ({'Eds.' if len(d.editors) > 1 else 'Ed.'}), " if editors else "In "
        pages = f" (pp. {d.pages})" if d.pages else ""
        return _clean(f"{authors} {year}. {title}. {eds}*{d.container or ''}*{pages}. {d.publisher or ''}.{doi}")
    if source_type == "standard":
        return _clean(f"{d.publisher or d.standard_number or ''} {year}. *{d.standard_number or ''} {title}*.{doi}")
    if source_type == "web":
        who = authors or d.container or ""
        return _clean(f"{who} {year}. *{title}*. {d.container or ''}.{doi}")
    if source_type == "thesis":
        return _clean(f"{authors} {year}. *{title}* [Thesis, {d.publisher or ''}].{doi}")
    edition = f" ({d.edition} ed.)" if d.edition else ""
    return _clean(f"{authors} {year}. *{title}*{edition}. {d.publisher or ''}.{doi}")


# --- IEEE ---------------------------------------------------------------------------

def format_ieee(source_type: str, d: SourceData) -> str:
    names = [ieee_name(p) for p in d.authors]
    authors = (names[0] + " et al.") if len(names) > 6 else _join(names, "and")
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    doi = f", doi: {d.doi}" if d.doi else ""
    if source_type in ("article", "conference"):
        parts = [f"*{d.container}*" if d.container else None,
                 f"vol. {d.volume}" if d.volume else None, f"no. {d.issue}" if d.issue else None,
                 f"pp. {d.pages}" if d.pages else None, str(d.year) if d.year else None]
        prefix = "in " if source_type == "conference" else ""
        return _clean(f"{authors}, “{title},” {prefix}" + ", ".join(p for p in parts if p) + f"{doi}.")
    if source_type == "chapter":
        eds = _join([ieee_name(p) for p in d.editors], "and")
        return _clean(f"{authors}, “{title},” in *{d.container or ''}*, {eds}{', Eds.' if eds else ''} "
                      f"{d.place or ''}: {d.publisher or ''}, {d.year or ''}, pp. {d.pages or ''}.")
    if source_type == "standard":
        return _clean(f"*{title}*, {d.standard_number or ''}, {d.year or ''}.")
    if source_type == "web":
        return _clean(f"{authors + ', ' if authors else ''}“{title}.” {d.container or ''}. "
                      f"Accessed: {d.accessed or ''}. [Online]. Available: {d.url or ''}")
    if source_type == "thesis":
        return _clean(f"{authors}, “{title},” Thesis, {d.publisher or ''}, {d.place or ''}, {d.year or ''}.")
    edition = f", {d.edition} ed." if d.edition else ""
    place = f" {d.place}:" if d.place else ""
    return _clean(f"{authors}, *{title}*{edition}.{place} {d.publisher or ''}, {d.year or ''}.")


# --- Chicago auteur-date --------------------------------------------------------------

def format_chicago(source_type: str, d: SourceData) -> str:
    names = [chicago_name(p, i == 0) for i, p in enumerate(d.authors[:10])]
    # Premier auteur inversé (« Ivanov, Ivan ») : virgule avant « and », même avec deux auteurs.
    authors = f"{names[0]}, and {names[1]}" if len(names) == 2 and "," in names[0] else _join(names, "and")
    year = str(d.year) if d.year else "n.d."
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    doi = f" https://doi.org/{d.doi}." if d.doi else (f" {d.url}." if d.url else "")
    if source_type in ("article", "conference"):
        issue = f" ({d.issue})" if d.issue else ""
        pages = f": {d.pages}" if d.pages else ""
        return _clean(f"{authors}. {year}. “{title}.” *{d.container or ''}* {d.volume or ''}{issue}{pages}.{doi}")
    if source_type == "chapter":
        eds = _join([f"{p.given or ''} {p.family}".strip() for p in d.editors], "and")
        return _clean(f"{authors}. {year}. “{title}.” In *{d.container or ''}*, edited by {eds}, {d.pages or ''}. "
                      f"{d.place or ''}: {d.publisher or ''}.{doi}")
    if source_type == "standard":
        return _clean(f"{d.standard_number or ''}. {year}. *{title}*. {d.place or ''}: {d.publisher or ''}.")
    if source_type == "web":
        return _clean(f"{authors or d.container or ''}. {year}. “{title}.” {d.container or ''}. "
                      f"Accessed {d.accessed or ''}.{doi}")
    place = f"{d.place}: " if d.place else ""
    return _clean(f"{authors}. {year}. *{title}*. {place}{d.publisher or ''}.{doi}")


# --- Vancouver --------------------------------------------------------------------------

def format_vancouver(source_type: str, d: SourceData) -> str:
    names = [vancouver_name(p) for p in d.authors]
    authors = ", ".join(names[:6]) + (", et al" if len(names) > 6 else "")
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    if source_type in ("article", "conference"):
        volume = f"{d.volume or ''}" + (f"({d.issue})" if d.issue else "")
        doi = f" doi:{d.doi}" if d.doi else ""
        return _clean(f"{authors}. {title}. {d.container or ''}. {d.year or ''};{volume}:{d.pages or ''}.{doi}")
    if source_type == "chapter":
        eds = ", ".join(vancouver_name(p) for p in d.editors)
        return _clean(f"{authors}. {title}. In: {eds}, editors. {d.container or ''}. {d.place or ''}: "
                      f"{d.publisher or ''}; {d.year or ''}. p. {d.pages or ''}.")
    if source_type == "web":
        return _clean(f"{authors + '. ' if authors else ''}{title} [Internet]. {d.container or ''}; {d.year or ''} "
                      f"[cited {d.accessed or ''}]. Available from: {d.url or ''}")
    if source_type == "standard":
        return _clean(f"{d.standard_number or ''}. {title}. {d.place or ''}: {d.publisher or ''}; {d.year or ''}.")
    edition = f" {d.edition} ed." if d.edition else ""
    return _clean(f"{authors}. {title}.{edition} {d.place or ''}: {d.publisher or ''}; {d.year or ''}.")


# --- Harvard (Cite Them Right) ------------------------------------------------------------

def harvard_name(person: Person) -> str:
    return f"{person.family}, {initials(person.given, spaced=False)}".rstrip(", ")


def format_harvard(source_type: str, d: SourceData) -> str:
    names = [harvard_name(p) for p in d.authors]
    authors = (names[0] + " et al.") if len(names) > 3 else _join(names, "and", oxford=False)
    year = f"({d.year})" if d.year else "(no date)"
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    doi = f" Available at: https://doi.org/{d.doi}." if d.doi else (
        f" Available at: {d.url}" + (f" (Accessed: {d.accessed})." if d.accessed else ".") if d.url else "")
    if source_type in ("article", "conference"):
        volume = f", {d.volume}" if d.volume else ""
        issue = f"({d.issue})" if d.issue else ""
        pages = f", pp. {d.pages}" if d.pages else ""
        return _clean(f"{authors} {year} ‘{title}’, *{d.container or ''}*{volume}{issue}{pages}.{doi}")
    if source_type == "chapter":
        eds = _join([f"{initials(p.given)} {p.family}".strip() for p in d.editors], "and", oxford=False)
        eds = f"{eds} ({'eds' if len(d.editors) > 1 else 'ed.'}) " if eds else ""
        place = f"{d.place}: " if d.place else ""
        return _clean(f"{authors} {year} ‘{title}’, in {eds}*{d.container or ''}*. {place}{d.publisher or ''}, "
                      f"pp. {d.pages or ''}.{doi}")
    if source_type == "standard":
        return _clean(f"{d.publisher or ''} {year} *{d.standard_number or ''}: {title}*. {d.place or ''}"
                      f"{': ' if d.place else ''}{d.publisher or ''}.{doi}")
    if source_type == "web":
        return _clean(f"{authors or d.container or ''} {year} *{title}*.{doi}")
    edition = f" {d.edition} edn." if d.edition else ""
    place = f" {d.place}:" if d.place else ""
    return _clean(f"{authors} {year} *{title}*.{edition}{place} {d.publisher or ''}.{doi}")


# --- ISO 690:2021 (auteur-date) --------------------------------------------------------------

def iso_name(person: Person) -> str:
    return f"{person.family.upper()}, {person.given or ''}".rstrip(", ")


def format_iso690(source_type: str, d: SourceData) -> str:
    names = [iso_name(p) for p in d.authors]
    authors = (names[0] + " et al.") if len(names) > 3 else _join(names, "and", oxford=False)
    year = str(d.year) if d.year else "[s.d.]"
    title = (d.title or "") + (f": {d.subtitle}" if d.subtitle else "")
    ids = "".join([f" DOI {d.doi}." if d.doi else "", f" ISBN {d.isbn}." if d.isbn else "",
                   f" Available from: {d.url}" + (f" [viewed {d.accessed}]." if d.accessed else ".") if d.url else ""])
    if source_type in ("article", "conference"):
        parts = ", ".join(filter(None, [f"vol. {d.volume}" if d.volume else None,
                                        f"no. {d.issue}" if d.issue else None, f"pp. {d.pages}" if d.pages else None]))
        return _clean(f"{authors}. {year}. {title}. *{d.container or ''}*. {parts}.{ids}")
    if source_type == "chapter":
        eds = _join([iso_name(p) for p in d.editors], "and", oxford=False)
        return _clean(f"{authors}. {year}. {title}. In: {eds}{', ed.' if eds else ''} *{d.container or ''}*. "
                      f"{d.place or ''}{': ' if d.place else ''}{d.publisher or ''}, pp. {d.pages or ''}.{ids}")
    if source_type == "standard":
        return _clean(f"{d.publisher or ''}. {year}. *{d.standard_number or ''}. {title}*. "
                      f"{d.place or ''}{': ' if d.place else ''}{d.publisher or ''}.{ids}")
    edition = f" {d.edition} ed." if d.edition else ""
    place = f" {d.place}:" if d.place else ""
    return _clean(f"{authors}. {year}. *{title}*.{edition}{place} {d.publisher or ''}.{ids}")


FORMATTERS = {"gost": format_gost, "apa": format_apa, "ieee": format_ieee, "chicago": format_chicago,
              "vancouver": format_vancouver, "harvard": format_harvard, "iso690": format_iso690}


def format_entry(style: str, source_type: str, data: SourceData) -> str:
    return FORMATTERS[style](source_type, data)


def sort_key(data: SourceData) -> tuple:
    first = data.authors[0].family if data.authors else (data.standard_number or data.title or "")
    return (first.casefold(), data.year or 0, (data.title or "").casefold())


def in_text(style: str, data: SourceData, number: int | None, locator: str | None) -> str:
    """Appel de citation pour UNE source."""
    if style in NUMERIC_STYLES:
        return f"{number}" + (f", {locator}" if locator else "")
    families = [p.family for p in data.authors]
    ru = _cyrillic("".join(families))
    if not families:
        label = data.standard_number or (data.title or "")[:30]
    elif len(families) == 1:
        label = families[0]
    elif len(families) == 2:
        label = f"{families[0]} {'и' if ru else ('&' if style == 'apa' else 'and')} {families[1]}"
    else:
        label = f"{families[0]} {'и др.' if ru else 'et al.'}"
    year = str(data.year) if data.year else "n.d."
    if style == "apa":
        return f"{label}, {year}" + (f", {locator}" if locator else "")
    return f"{label} {year}" + (f", {locator}" if locator else "")


def render_markers(text: str, style: str, numbers: dict[str, int], sources: dict[str, SourceData]) -> str:
    """Remplace [@clé, loc] par l'appel du style ; une clé inconnue reste visible : [?clé]."""
    def replace(match: re.Match) -> str:
        items = [(m.group(1), (m.group(2) or "").strip() or None) for m in ITEM.finditer(match.group(1))]
        rendered = []
        for key, locator in items:
            if key not in sources:
                rendered.append(f"?{key}")
                continue
            rendered.append(in_text(style, sources[key], numbers.get(key), locator))
        joined = ("; " if style not in NUMERIC_STYLES or any(loc for _, loc in items) else ", ").join(rendered)
        return f"[{joined}]" if style in NUMERIC_STYLES else f"({joined})"
    return MARKER.sub(replace, text)
