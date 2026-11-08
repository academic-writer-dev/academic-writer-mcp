"""Schéma des profils disciplinaires (fichiers YAML validés par Pydantic).

Un profil décrit une discipline : noms, mots-clés de détection, terminologie
trilingue, méthodologie, sections spécifiques par type de document, règles de
validation, types de calculs, exigences bibliographiques et normes applicables.
Les champs inconnus sont refusés (``extra="forbid"``) pour détecter les fautes de frappe.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Lang = Literal["fr", "ru", "en"]
Convention = Literal["ru", "fr", "intl"]
LANGS: tuple[str, ...] = ("fr", "ru", "en")

CONVENTION_LABELS: dict[str, str] = {
    "ru": "Russe (ГОСТ / ЕСКД)",
    "fr": "Française / européenne (NF / EN)",
    "intl": "Internationale (ISO / IEC / usages des revues)",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Localized(_Strict):
    fr: str | None = None
    ru: str | None = None
    en: str | None = None

    def get(self, lang: str) -> str:
        for candidate in (lang, "fr", "en", "ru"):
            value = getattr(self, candidate, None)
            if value:
                return value
        return ""


class Term(_Strict):
    id: str
    fr: str | None = None
    ru: str | None = None
    en: str | None = None
    definition: Localized | None = None
    avoid: dict[Lang, list[str]] = Field(default_factory=dict, description="Formulations à éviter.")
    note: Localized | None = None


class SectionSpec(_Strict):
    id: str
    title: Localized
    required: bool = True
    guidance: Localized | None = None
    standard: str | None = None
    after: str | None = Field(default=None, description="Insérer après cette section (sections de domaine).")


class ValidationRule(_Strict):
    id: str
    description: Localized
    severity: Literal["info", "warning", "error"] = "warning"
    check: str | None = Field(default=None, description="Clé d'un contrôle automatique (phases ultérieures).")


class CalcInput(_Strict):
    """Donnée d'entrée d'un calcul ; ``default`` uniquement pour une valeur normalisée, avec sa norme."""

    symbol: str
    name: Localized
    unit: str | None = None
    default: str | None = None
    standard: str | None = None

    @model_validator(mode="after")
    def _default_needs_standard(self) -> CalcInput:
        if self.default is not None and not self.standard:
            raise ValueError(f"Valeur par défaut de « {self.symbol} » sans norme de référence.")
        return self


class CalculationType(_Strict):
    id: str
    description: Localized
    tools: list[str] = Field(default_factory=list)
    triggers: dict[Lang, list[str]] = Field(default_factory=dict,
                                            description="Mots-clés signalant ce calcul dans des consignes.")
    inputs: list[CalcInput] = Field(default_factory=list)


class Standard(_Strict):
    code: str
    title: Localized
    convention: Convention
    scope: Localized | None = None
    verify_edition: bool = True


class Bibliography(_Strict):
    preferred_styles: dict[Convention, list[str]] = Field(default_factory=dict)
    notes: Localized | None = None
    min_sources: dict[str, int] = Field(default_factory=dict, description="Indicatif, par type de document.")


class DomainProfile(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: int = 1
    parent: str | None = None
    names: Localized
    description: Localized | None = None
    risk_level: Literal["normal", "high"] = "normal"
    risk_notice: Localized | None = None
    keywords: dict[Lang, list[str]] = Field(default_factory=dict)
    terminology: list[Term] = Field(default_factory=list)
    methodology: dict[Lang, list[str]] = Field(default_factory=dict)
    document_sections: dict[str, list[SectionSpec]] = Field(default_factory=dict)
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    calculations: list[CalculationType] = Field(default_factory=list)
    bibliography: Bibliography = Field(default_factory=Bibliography)
    standards: list[Standard] = Field(default_factory=list)
    source: str = Field(default="builtin", description="Origine : builtin ou user (rempli au chargement).")

    @model_validator(mode="after")
    def _check(self) -> DomainProfile:
        missing = [lang for lang in LANGS if not getattr(self.names, lang)]
        if missing:
            raise ValueError(f"names doit être renseigné en {', '.join(LANGS)} (manque : {', '.join(missing)})")
        if self.risk_level == "high" and self.risk_notice is None:
            raise ValueError("Un profil à haut risque doit définir risk_notice.")
        ids = [t.id for t in self.terminology]
        if len(ids) != len(set(ids)):
            raise ValueError("Identifiants de terminologie en double.")
        return self


class DomainSummary(BaseModel):
    id: str
    name: str
    parent: str | None
    risk_level: str
    source: str
    term_count: int
    standard_count: int
