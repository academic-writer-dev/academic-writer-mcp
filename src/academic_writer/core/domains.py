"""Service disciplinaire : profils, identification du domaine, gabarits, terminologie."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.errors import ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.models import DocumentType, Project
from academic_writer.core.projects import ProjectService
from academic_writer.domains.detection import confidence_level, fold, score_profiles
from academic_writer.domains.model import DomainProfile, DomainSummary, Term
from academic_writer.domains.registry import GENERALIST_ID, DomainRegistry
from academic_writer.domains.structures import StructureTemplate, build_template
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.domains")

_MAX_ANALYZED_CHARS = 200_000
_DEFAULT_CONVENTION = {"ru": "ru", "fr": "fr", "en": "intl"}


class MatchedTerm(BaseModel):
    term: str
    count: int


class DomainCandidate(BaseModel):
    domain_id: str
    name: str
    score: float
    risk_level: str
    matched_terms: list[MatchedTerm]


class DomainIdentification(BaseModel):
    project_id: str
    analyzed_documents: int
    analyzed_words: int
    confidence: Literal["élevée", "moyenne", "faible", "indéterminée"]
    suggested_domain_id: str
    candidates: list[DomainCandidate]
    explanation: str
    requires_confirmation: bool = Field(default=True, description="Toujours vrai : l'utilisateur confirme avec set_project_domain.")
    risk_notices: list[str] = Field(default_factory=list)


class DomainList(BaseModel):
    count: int
    domains: list[DomainSummary]
    load_errors: list[str] = Field(description="Profils écartés car invalides.")


class TermEntry(BaseModel):
    domain_id: str
    term: Term


class TermLookup(BaseModel):
    query: str
    count: int
    entries: list[TermEntry]


class DomainAssignment(BaseModel):
    project: Project
    domain_name: str
    risk_level: str
    risk_notice: str | None
    message: str


class DomainService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService,
                 extraction: ExtractionService, registry: DomainRegistry | None = None) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.extraction = extraction
        self._registry = registry

    @property
    def registry(self) -> DomainRegistry:
        """Profils chargés au premier usage (démarrage du serveur plus rapide)."""
        if self._registry is None:
            self._registry = DomainRegistry(self.settings)
        return self._registry

    # --- profils -----------------------------------------------------------
    def list_domains(self, language: str = "fr") -> DomainList:
        domains = [
            DomainSummary(id=p.id, name=p.names.get(language), parent=p.parent, risk_level=p.risk_level,
                          source=p.source, term_count=len(p.terminology), standard_count=len(p.standards))
            for p in self.registry.all()
        ]
        return DomainList(count=len(domains), domains=domains, load_errors=self.registry.errors)

    def get_domain(self, domain_id: str) -> DomainProfile:
        return self.registry.get(domain_id)

    def reload(self) -> DomainList:
        self.registry.reload()
        return self.list_domains()

    # --- identification ----------------------------------------------------
    def identify(self, project_id: str, document_id: str | None = None, language: str | None = None) -> DomainIdentification:
        project = self.projects.get(project_id)
        language = language or project.language.value
        if document_id:
            self.extraction.extract(document_id)
        else:
            self.extraction.index_project(project_id)
        query = "SELECT document_id, text FROM chunks WHERE project_id = ?"
        params: list[object] = [project_id]
        if document_id:
            query += " AND document_id = ?"
            params.append(document_id)
        query += " ORDER BY document_id, seq"
        parts = [project.name, project.description or "", project.discipline or ""]
        documents: set[str] = set()
        size = 0
        with self.db.read() as conn:
            for row in conn.execute(query, params):
                if size >= _MAX_ANALYZED_CHARS:
                    break
                parts.append(row["text"])
                documents.add(row["document_id"])
                size += len(row["text"])
        text = "\n".join(parts)

        profiles = [p for p in self.registry.all() if p.id != GENERALIST_ID]
        scores, word_count = score_profiles(text, profiles)
        by_id = {p.id: p for p in self.registry.all()}
        confidence, gap = confidence_level(scores, word_count, by_id)
        suggested = scores[0].profile.id if confidence != "indéterminée" else GENERALIST_ID
        candidates = [
            DomainCandidate(domain_id=s.profile.id, name=s.profile.names.get(language), score=s.score,
                            risk_level=s.profile.risk_level,
                            matched_terms=[MatchedTerm(term=m.keyword, count=m.count) for m in s.matches[:10]])
            for s in scores[:5] if s.score > 0
        ]
        explanation = self._explain(confidence, scores, word_count, gap, language, len(documents))
        notices = [p.risk_notice.get(language) for p in (by_id[c.domain_id] for c in candidates[:2])
                   if p.risk_level == "high" and p.risk_notice]
        return DomainIdentification(
            project_id=project_id, analyzed_documents=len(documents), analyzed_words=word_count,
            confidence=confidence, suggested_domain_id=suggested, candidates=candidates,
            explanation=explanation, risk_notices=notices,
        )

    @staticmethod
    def _explain(confidence: str, scores, words: int, gap: float, language: str, documents: int) -> str:
        if confidence == "indéterminée":
            reason = ("trop peu de texte analysé" if words < 30
                      else "aucun vocabulaire disciplinaire suffisamment caractéristique")
            return (f"Domaine indéterminé ({reason} ; {documents} document(s), {words} mots). "
                    "Profil généraliste proposé par défaut ; indiquez la discipline si vous la connaissez.")
        top = scores[0]
        terms = ", ".join(f"{m.keyword} ×{m.count}" for m in top.matches[:5])
        return (f"Suggestion : {top.profile.names.get(language)} (score {top.score}, écart ×{gap:.1f} avec le "
                f"domaine concurrent le plus proche ; confiance {confidence}). Termes caractéristiques : {terms}. "
                f"Analyse fondée sur {documents} document(s) et {words} mots : à confirmer par l'utilisateur.")

    # --- affectation -------------------------------------------------------
    def assign(self, project_id: str, domain_id: str, convention: str | None = None,
               language: str | None = None) -> DomainAssignment:
        profile = self.registry.get(domain_id)
        project = self.projects.set_domain(project_id, domain_id, convention)
        language = language or project.language.value
        notice = profile.risk_notice.get(language) if profile.risk_level == "high" and profile.risk_notice else None
        message = f"Domaine « {profile.names.get(language)} » enregistré pour le projet."
        if notice:
            message += " ATTENTION : domaine à haut risque — " + notice
        return DomainAssignment(project=project, domain_name=profile.names.get(language),
                                risk_level=profile.risk_level, risk_notice=notice, message=message)

    # --- gabarits ----------------------------------------------------------
    def effective_convention(self, project: Project) -> str:
        return project.convention or _DEFAULT_CONVENTION.get(project.language.value, "intl")

    def structure_template(self, project_id: str | None = None, *, document_type: str | None = None,
                           convention: str | None = None, domain_id: str | None = None,
                           language: str | None = None) -> StructureTemplate:
        project = self.projects.get(project_id) if project_id else None
        doc_type_value = document_type or (project.document_type.value if project else None)
        if doc_type_value is None:
            raise ValidationFailed("Indiquez un projet ou un type de document.")
        try:
            doc_type = DocumentType(doc_type_value)
        except ValueError as exc:
            raise ValidationFailed(f"Type de document inconnu : {doc_type_value}") from exc
        language = language or (project.language.value if project else "fr")
        convention = convention or (self.effective_convention(project) if project else _DEFAULT_CONVENTION.get(language, "intl"))
        if convention not in ("ru", "fr", "intl"):
            raise ValidationFailed("Convention inconnue : utilisez ru, fr ou intl.")
        profile = self.registry.get(domain_id or (project.domain_id if project and project.domain_id else GENERALIST_ID))
        return build_template(doc_type, convention, profile, language)

    # --- terminologie --------------------------------------------------------
    def lookup_terms(self, query: str, domain_id: str | None = None, limit: int = 20) -> TermLookup:
        needle = fold(query.strip())
        if len(needle) < 2:
            raise ValidationFailed("Indiquez au moins 2 caractères.")
        # Avec un domaine : ses termes y compris hérités. Sans domaine : termes propres de chaque profil.
        profiles = ([self.registry.get(domain_id)] if domain_id
                    else [self.registry.raw(p.id) for p in self.registry.all()])
        entries: list[TermEntry] = []
        seen: set[tuple[str, str]] = set()
        for profile in profiles:
            for term in profile.terminology:
                values = [term.fr, term.ru, term.en, term.id] + [a for avoid in term.avoid.values() for a in avoid]
                if any(v and needle in fold(v) for v in values):
                    key = (term.id, term.fr or term.en or "")
                    if key not in seen:
                        seen.add(key)
                        entries.append(TermEntry(domain_id=profile.id, term=term))
        limit = max(1, min(limit, 100))
        return TermLookup(query=query, count=len(entries[:limit]), entries=entries[:limit])
