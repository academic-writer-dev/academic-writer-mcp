"""Référentiels normatifs : catalogue vérifié (édition connue, accès légal) et contrôle des normes citées.

Règles : aucune norme inventée ; une norme absente du catalogue est « non vérifiée », jamais « fausse » ; l'accès
est indiqué tel qu'il est (la plupart des normes ISO, IEC, EN, DIN, ASTM, ASME sont PAYANTES : jamais présentées comme
gratuites). Éditions connues au 2026-11 : à revérifier auprès de l'organisme avant toute utilisation formelle.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from academic_writer.quality.claims import standard_references

CATALOG_DATE = "2026-11"


class StandardEntry(BaseModel):
    code: str = Field(description="Référence sans année (ex. « ISO 690 », « ГОСТ 7.32 »).")
    edition: str = Field(description="Dernière édition connue (année).")
    title: str
    organization: str
    scope: str
    access: str = Field(description="payant, consultation gratuite (texte officiel), ou libre.")
    note: str | None = None


def _s(code, edition, title, organization, scope, access, note=None) -> StandardEntry:
    return StandardEntry(code=code, edition=edition, title=title, organization=organization, scope=scope,
                         access=access, note=note)


_PAID = "payant (organisme de normalisation ou bibliothèque universitaire abonnée)"
_GOST = "consultation gratuite du texte officiel (Фонд стандартов / Росстандарт), exemplaire officiel payant"
CATALOG: tuple[StandardEntry, ...] = (
    _s("ISO 690", "2021", "Information et documentation — Principes directeurs pour les références bibliographiques",
       "ISO", "bibliographie", _PAID),
    _s("ISO 80000-1", "2022", "Grandeurs et unités — Partie 1 : Généralités", "ISO", "grandeurs et unités", _PAID),
    _s("ISO 9001", "2015", "Systèmes de management de la qualité — Exigences", "ISO", "qualité", _PAID,
       "Révision en cours : vérifier si une nouvelle édition est publiée."),
    _s("ISO 14001", "2015", "Systèmes de management environnemental", "ISO", "environnement", _PAID),
    _s("ISO 45001", "2018", "Systèmes de management de la santé et de la sécurité au travail", "ISO", "sécurité", _PAID),
    _s("ISO 286-1", "2010", "Système de codification ISO pour les tolérances sur les tailles linéaires — Partie 1",
       "ISO", "tolérances", _PAID),
    _s("ISO 1101", "2017", "Spécification géométrique des produits — Tolérancement géométrique", "ISO",
       "tolérancement", _PAID),
    _s("ISO 6336-1", "2019", "Calcul de la capacité de charge des engrenages cylindriques — Partie 1", "ISO",
       "engrenages", _PAID),
    _s("ISO 281", "2007", "Roulements — Charges dynamiques de base et durée nominale", "ISO", "roulements", _PAID),
    _s("ISO 6892-1", "2019", "Matériaux métalliques — Essai de traction — Partie 1 : à température ambiante", "ISO",
       "essais de matériaux", _PAID),
    _s("ISO 13849-1", "2023", "Sécurité des machines — Parties des systèmes de commande relatives à la sécurité",
       "ISO", "sécurité des machines", _PAID),
    _s("IEC 61508", "2010", "Sécurité fonctionnelle des systèmes E/E/PE relatifs à la sécurité (7 parties)", "IEC",
       "sécurité fonctionnelle", _PAID, "Édition 2 (2010) ; révision en cours."),
    _s("IEC 62061", "2021", "Sécurité des machines — Sécurité fonctionnelle des systèmes de commande", "IEC",
       "sécurité des machines", _PAID),
    _s("IEC 60204-1", "2016", "Sécurité des machines — Équipement électrique des machines — Partie 1", "IEC",
       "électricité des machines", _PAID),
    _s("IEC 61131-3", "2013", "Automates programmables — Partie 3 : Langages de programmation", "IEC",
       "automatismes", _PAID, "Une 4e édition a été préparée : vérifier l'édition en vigueur."),
    _s("IEEE 754", "2019", "Arithmétique en virgule flottante", "IEEE", "informatique", _PAID),
    _s("ASME Y14.5", "2018", "Dimensioning and Tolerancing", "ASME", "dessin technique", _PAID),
    _s("EN 1990", "2023", "Eurocode — Bases de calcul des structures (2e génération)", "CEN", "génie civil", _PAID,
       "La 1re génération (EN 1990:2002) reste utilisée pendant la période de coexistence nationale."),
    _s("ГОСТ 7.32", "2017", "Отчёт о научно-исследовательской работе. Структура и правила оформления",
       "Росстандарт / МГС", "оформление отчётов", _GOST),
    _s("ГОСТ Р 7.0.100", "2018", "Библиографическая запись. Библиографическое описание", "Росстандарт",
       "библиография", _GOST),
    _s("ГОСТ Р 7.0.5", "2008", "Библиографическая ссылка", "Росстандарт", "библиография", _GOST),
    _s("ГОСТ 2.105", "2019", "ЕСКД. Общие требования к текстовым документам", "Росстандарт / МГС",
       "оформление документов", _GOST),
    _s("ГОСТ 2.104", "2006", "ЕСКД. Основные надписи", "Росстандарт / МГС", "чертежи", _GOST),
    _s("ГОСТ 8.417", "2002", "ГСИ. Единицы величин", "Росстандарт / МГС", "единицы", _GOST),
    _s("ГОСТ 25346", "2013", "Основные нормы взаимозаменяемости. Характеристики изделий геометрические. Допуски",
       "Росстандарт / МГС", "допуски и посадки", _GOST),
    _s("ГОСТ 1497", "1984", "Металлы. Методы испытаний на растяжение", "Госстандарт СССР / МГС",
       "испытания металлов", _GOST),
    _s("SI (Brochure du BIPM)", "2019", "Le Système international d'unités, 9e édition", "BIPM", "unités",
       "libre (téléchargement gratuit sur bipm.org)"),
)
_INDEX = {re.sub(r"\s+", " ", e.code).casefold(): e for e in CATALOG}


class StandardCitation(BaseModel):
    cited: str
    code: str
    year: str | None
    status: str = Field(description="à jour, édition antérieure, sans année, non vérifiée (hors catalogue).")
    catalog: StandardEntry | None = None
    message: str


class StandardsReport(BaseModel):
    label: str
    citations: list[StandardCitation]
    notice: str = (f"Catalogue limité et daté ({CATALOG_DATE}) : une norme « non vérifiée » n'est pas fausse ; vérifier "
                   "l'édition en vigueur auprès de l'organisme. Les normes payantes ne sont jamais fournies.")


def _key(code: str) -> str:
    return re.sub(r"\s+", " ", code).casefold().replace("гост р", "гост р").strip()


def lookup(query: str) -> list[StandardEntry]:
    q = query.casefold().strip()
    return [e for e in CATALOG if q in e.code.casefold() or q in e.title.casefold() or q in e.scope.casefold()][:30]


def check(label: str, text: str) -> StandardsReport:
    citations: list[StandardCitation] = []
    seen: set[str] = set()
    for cited, code, year in standard_references(text):
        key = _key(code)
        if key in seen:
            continue
        seen.add(key)
        entry = _INDEX.get(key)
        year4 = None
        if year:
            year4 = int(year) + (1900 if len(year) == 2 and int(year) > 30 else 2000 if len(year) == 2 else 0)
        if entry is None:
            status, message = "non vérifiée", "Norme hors du catalogue : vérifier existence, intitulé et édition."
        elif year4 is None:
            status, message = "sans année", f"Préciser l'édition (dernière connue : {entry.edition})."
        elif str(year4) == entry.edition:
            status, message = "à jour", f"Édition {entry.edition} (dernière connue)."
        elif year4 < int(entry.edition[:4]):
            status, message = ("édition antérieure", f"Édition {year4} citée ; dernière connue : {entry.edition}. "
                                                     "Justifier l'emploi d'une édition ancienne ou mettre à jour.")
        else:
            status, message = "non vérifiée", f"Édition {year4} postérieure au catalogue ({entry.edition}) : à vérifier."
        citations.append(StandardCitation(cited=cited, code=code, year=str(year4) if year4 else None, status=status,
                                          catalog=entry, message=message + (f" {entry.note}" if entry and entry.note else "")))
    return StandardsReport(label=label, citations=citations)
