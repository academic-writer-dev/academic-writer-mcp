"""Gabarits de structure des documents selon la convention (ГОСТ, française, internationale)
et la discipline.

Les structures de base sont décrites dans ``domain_profiles/_document_structures.yaml`` ;
les profils disciplinaires y ajoutent leurs sections propres (``document_sections``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from academic_writer.core.models import DOCUMENT_TYPE_LABELS, DocumentType
from academic_writer.domains.model import CONVENTION_LABELS, DomainProfile, Localized, SectionSpec
from academic_writer.domains.registry import builtin_profiles_dir

GENERAL_NOTICES = {
    "fr": [
        "Les consignes de votre établissement ou de votre enseignant priment sur ce gabarit.",
        "Normes citées : vérifiez l'édition en vigueur et les exigences locales avant de vous y référer.",
    ],
    "ru": [
        "Требования вашего вуза или преподавателя имеют приоритет над этим шаблоном.",
        "Указанные стандарты: проверьте действующую редакцию и локальные требования.",
    ],
    "en": [
        "Your institution's or instructor's requirements take precedence over this template.",
        "Cited standards: check the edition in force and local requirements before relying on them.",
    ],
}


class TemplateSection(BaseModel):
    id: str
    title: str
    required: bool
    guidance: str | None = None
    origin: str = Field(description="convention:<code> ou domain:<profil>")
    standard: str | None = None


class StandardRef(BaseModel):
    code: str
    title: str
    verify_edition: bool


class StructureTemplate(BaseModel):
    document_type: str
    document_type_label: str
    family: str
    convention: str
    convention_label: str
    language: str
    domain_id: str
    domain_name: str
    base_standard: str | None
    sections: list[TemplateSection]
    methodology: list[str]
    validation_rules: list[str]
    bibliography_styles: list[str]
    standards: list[StandardRef]
    notices: list[str]


class _ConventionStructure(BaseModel):
    standard: str | None = None
    sections: list[SectionSpec]


class _StructuresFile(BaseModel):
    families: dict[str, list[DocumentType]]
    structures: dict[str, dict[str, _ConventionStructure]]


@lru_cache(maxsize=4)
def load_structures(path: Path | None = None) -> _StructuresFile:
    path = path or builtin_profiles_dir() / "_document_structures.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    parsed = _StructuresFile.model_validate(data)
    covered = {t for types in parsed.families.values() for t in types}
    missing = set(DocumentType) - covered
    if missing:
        raise ValueError(f"Types de documents sans famille : {sorted(missing)}")
    return parsed


def family_of(document_type: DocumentType) -> str:
    for family, types in load_structures().families.items():
        if document_type in types:
            return family
    raise ValueError(document_type)


def _localize(value: Localized | None, lang: str) -> str | None:
    return value.get(lang) if value is not None else None


def build_template(document_type: DocumentType, convention: str, profile: DomainProfile,
                   language: str) -> StructureTemplate:
    structures = load_structures()
    family = family_of(document_type)
    base = structures.structures[convention][family]
    sections: list[TemplateSection] = [
        TemplateSection(id=s.id, title=s.title.get(language), required=s.required,
                        guidance=_localize(s.guidance, language), origin=f"convention:{convention}",
                        standard=s.standard)
        for s in base.sections
    ]
    extra: list[SectionSpec] = []
    for key in ("*", family, document_type.value):
        extra.extend(profile.document_sections.get(key, []))
    for spec in extra:
        section = TemplateSection(id=spec.id, title=spec.title.get(language), required=spec.required,
                                  guidance=_localize(spec.guidance, language), origin=f"domain:{profile.id}",
                                  standard=spec.standard)
        existing = next((i for i, s in enumerate(sections) if s.id == spec.id), None)
        if existing is not None:
            sections[existing] = section
            continue
        anchor = spec.after
        position = next((i + 1 for i, s in enumerate(sections) if s.id == anchor), None) if anchor else None
        if position is None:
            position = next((i for i, s in enumerate(sections) if s.id in ("conclusion", "conclusions")),
                            len(sections))
        sections.insert(position, section)

    notices = list(GENERAL_NOTICES.get(language, GENERAL_NOTICES["fr"]))
    if profile.risk_level == "high" and profile.risk_notice:
        notices.insert(0, profile.risk_notice.get(language))
    styles = profile.bibliography.preferred_styles.get(convention) or profile.bibliography.preferred_styles.get("intl", [])
    return StructureTemplate(
        document_type=document_type.value, document_type_label=DOCUMENT_TYPE_LABELS[document_type],
        family=family, convention=convention, convention_label=CONVENTION_LABELS[convention], language=language,
        domain_id=profile.id, domain_name=profile.names.get(language), base_standard=base.standard,
        sections=sections,
        methodology=profile.methodology.get(language) or profile.methodology.get("fr", []),
        validation_rules=[r.description.get(language) for r in profile.validation_rules],
        bibliography_styles=list(styles),
        standards=[StandardRef(code=s.code, title=s.title.get(language), verify_edition=s.verify_edition)
                   for s in profile.standards if s.convention in (convention, "intl")],
        notices=notices,
    )
