"""Cours et enseignants : profils réutilisables, politique de sources, couverture des questions par le cours.

- Un profil d'enseignant (nom, matière, cours, notations, méthodes, attentes, politique de sources par défaut)
  est réutilisable d'un projet à l'autre.
- ``course_coverage`` vérifie, pour chaque question ou tâche des consignes, si les documents de l'enseignant
  contiennent des passages qui la traitent ; une question sans passage est signalée « non traitée dans le
  cours » (jamais complétée). Les contradictions entre documents du cours (même symbole, valeurs différentes)
  sont relevées.
- ``extract_notations`` propose les notations définies dans le cours (« где m — масса », « où m est la masse »,
  « m : masse (kg) », « where m is the mass »), à confirmer par l'utilisateur.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from academic_writer.core.documents import DocumentService
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.history import record_event
from academic_writer.core.models import SOURCE_POLICY_LABELS, TEACHER_ROLES, Project, new_id, utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.core.teaching import (
    DETAIL_FIELDS,
    Notation,
    TeacherProfile,
    TeacherProfileList,
    load_profile,
    profile_from_row,
)
from academic_writer.core.writing import WritingService
from academic_writer.quality.calculations import check_calculations
from academic_writer.quality.models import Segment
from academic_writer.storage.db import Database

POLICIES = tuple(SOURCE_POLICY_LABELS)
_KEYWORD = re.compile(r"[^\W\d_]{4,}")
_STOP = frozenset(
    "dans pour avec sans sont être fait faire leur leurs cette ces quel quelle quels quelles comment pourquoi "
    "calculer déterminer expliquer donner indiquer décrire montrer exercice question réponse valeur valeurs "
    "чтобы какой какая какие каким каков почему определить рассчитать вычислить объяснить указать описать "
    "задача вопрос ответ значение значения работы работа which what where when explain describe calculate "
    "determine exercise question answer value values with from that this these those".split())
_NOTATION = re.compile(
    r"(?:где|where|où|avec)\s+(?P<sym>[A-Za-zА-Яа-яα-ωΑ-Ω][\w₀-₉']{0,4})\s*(?:[—–-]|est|is|:|=\s*(?=[^\d]))\s*"
    r"(?P<meaning>[^,;.\n]{3,80})"
    r"|^\s*(?P<sym2>[A-Za-zА-Яа-яα-ωΑ-Ω][\w₀-₉']{0,4})\s*[—–:]\s*(?P<meaning2>[^,;.\n]{3,80})", re.MULTILINE)
_UNIT_IN = re.compile(r"[,(]\s*([A-Za-zА-Яа-я°/·²³%]{1,10})\s*\)?\s*$")


class CoveragePassage(BaseModel):
    document: str
    page: int | None
    snippet: str


class CoverageItem(BaseModel):
    requirement_id: str
    kind: str
    text: str
    status: str = Field(description="covered (traité dans le cours), partial, not_covered (aucun passage trouvé).")
    matched_terms: list[str]
    missing_terms: list[str]
    passages: list[CoveragePassage]


class CourseContradiction(BaseModel):
    symbol: str
    values: list[str] = Field(description="Valeurs et document d'origine.")
    message: str


class CourseCoverage(BaseModel):
    project_id: str
    source_policy: str
    source_policy_label: str
    teacher_documents: list[str]
    items: list[CoverageItem]
    covered: int
    partial: int
    not_covered: int
    contradictions: list[CourseContradiction]
    notices: list[str]


class NotationProposal(BaseModel):
    symbol: str
    meaning: str
    unit: str | None
    document: str
    page: int | None


class NotationExtraction(BaseModel):
    project_id: str
    proposals: list[NotationProposal]
    notice: str = ("Propositions automatiques à faire confirmer par l'utilisateur, puis à enregistrer dans le profil "
                   "de l'enseignant (update_teacher_profile notations=...).")


class RubricProposal(BaseModel):
    criterion: str
    points: float | None
    document: str
    page: int | None


class DefinitionProposal(BaseModel):
    term: str
    definition: str
    document: str
    page: int | None


class TeacherMaterialExtraction(BaseModel):
    project_id: str
    criteria: list[RubricProposal]
    total_points: float | None
    definitions: list[DefinitionProposal]
    notices: list[str]


class ProjectTeaching(BaseModel):
    project: Project
    source_policy_label: str
    teacher: TeacherProfile | None
    effects: list[str]


def _effects(policy: str) -> list[str]:
    if policy == "course_only":
        return ["Rédaction fondée uniquement sur les documents de l'enseignant (consignes, cours, barème, modèles, "
                "exemples, données).",
                "Sources bibliographiques, recherches et téléchargements externes refusés pour ce projet.",
                "Toute citation [@clé] dans une rédaction est signalée comme une erreur.",
                "Les questions non traitées dans le cours sont signalées, jamais complétées."]
    if policy == "external_allowed":
        return ["Connaissances et sources externes permises, à signaler comme externes ; jamais attribuées au cours."]
    return ["Documents et sources enregistrées du projet (comportement par défaut)."]


class CourseService:
    def __init__(self, db: Database, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService, writing: WritingService) -> None:
        self.db = db
        self.projects = projects
        self.documents = documents
        self.extraction = extraction
        self.writing = writing

    # --- profils d'enseignants ------------------------------------------------------------------
    def create_profile(self, name: str, *, subject: str | None = None, course: str | None = None,
                       institution: str | None = None, source_policy: str = "course_only",
                       notations: list[Notation] | None = None, methods: str = "", expectations: str = "",
                       details: dict | None = None) -> TeacherProfile:
        if not name or not name.strip():
            raise ValidationFailed("Nom de l'enseignant obligatoire.")
        if source_policy not in POLICIES:
            raise ValidationFailed(f"Politique inconnue : {', '.join(POLICIES)}.")
        profile_id, now = new_id(), utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO teacher_profiles (id, name, subject, course, institution, source_policy, notations, "
                "methods, expectations, details, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (profile_id, name.strip()[:200], subject, course, institution, source_policy,
                 json.dumps([n.model_dump() for n in notations or []], ensure_ascii=False), methods[:5000],
                 expectations[:5000], self._details_json(details or {}), now, now))
        return self.get_profile(profile_id)

    @staticmethod
    def _details_json(details: dict) -> str:
        unknown = set(details) - set(DETAIL_FIELDS)
        if unknown:
            raise ValidationFailed(f"Champs inconnus : {', '.join(sorted(unknown))}.")
        probe = TeacherProfile(id="x", name="x", created_at="", updated_at="", **details)  # validation
        return json.dumps({k: getattr(probe, k) if not isinstance(getattr(probe, k), list) else
                           [i.model_dump() if hasattr(i, "model_dump") else i for i in getattr(probe, k)]
                           for k in DETAIL_FIELDS}, ensure_ascii=False)

    def get_profile(self, profile_id: str) -> TeacherProfile:
        with self.db.read() as conn:
            profile = load_profile(conn, profile_id)
        if profile is None:
            raise NotFoundError(f"Profil d'enseignant introuvable : {profile_id}")
        return profile

    def list_profiles(self) -> TeacherProfileList:
        with self.db.read() as conn:
            rows = conn.execute("SELECT * FROM teacher_profiles ORDER BY name, subject").fetchall()
        profiles = [profile_from_row(r) for r in rows]
        return TeacherProfileList(count=len(profiles), profiles=profiles)

    def update_profile(self, profile_id: str, changes: dict) -> TeacherProfile:
        current = self.get_profile(profile_id)
        allowed = {"name", "subject", "course", "institution", "source_policy", "notations", "methods", "expectations",
                   *DETAIL_FIELDS}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationFailed(f"Champs inconnus : {', '.join(sorted(unknown))}.")
        if "source_policy" in changes and changes["source_policy"] not in POLICIES:
            raise ValidationFailed(f"Politique inconnue : {', '.join(POLICIES)}.")
        if "name" in changes and not (changes["name"] or "").strip():
            raise ValidationFailed("Nom de l'enseignant obligatoire.")
        merged = current.model_dump() | {k: v for k, v in changes.items() if v is not None}
        notations = [Notation.model_validate(n) for n in merged["notations"]]
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE teacher_profiles SET name = ?, subject = ?, course = ?, institution = ?, source_policy = ?, "
                "notations = ?, methods = ?, expectations = ?, details = ?, updated_at = ? WHERE id = ?",
                (merged["name"].strip()[:200], merged["subject"], merged["course"], merged["institution"],
                 merged["source_policy"], json.dumps([n.model_dump() for n in notations], ensure_ascii=False),
                 (merged["methods"] or "")[:5000], (merged["expectations"] or "")[:5000],
                 self._details_json({k: merged[k] for k in DETAIL_FIELDS}), utc_now(), profile_id))
        return self.get_profile(profile_id)

    # --- rattachement à un projet -----------------------------------------------------------------
    def set_project_teaching(self, project_id: str, *, teacher_profile_id: str | None = None,
                             source_policy: str | None = None, unlink: bool = False) -> ProjectTeaching:
        project = self.writing._active_project(project_id)
        profile = self.get_profile(teacher_profile_id) if teacher_profile_id else None
        if source_policy is not None and source_policy not in POLICIES:
            raise ValidationFailed(f"Politique inconnue : {', '.join(POLICIES)}.")
        policy = source_policy or (profile.source_policy if profile else project.source_policy)
        profile_id = None if unlink else (profile.id if profile else project.teacher_profile_id)
        with self.db.transaction() as conn:
            conn.execute("UPDATE projects SET source_policy = ?, teacher_profile_id = ?, updated_at = ? WHERE id = ?",
                         (policy, profile_id, utc_now(), project_id))
            record_event(conn, project_id=project_id, entity_type="project", entity_id=project_id,
                         action="teaching_updated", details={"source_policy": policy, "teacher_profile_id": profile_id})
        return self.teaching(project_id)

    def teaching(self, project_id: str) -> ProjectTeaching:
        project = self.projects.get(project_id)
        with self.db.read() as conn:
            teacher = load_profile(conn, project.teacher_profile_id)
        return ProjectTeaching(project=project, source_policy_label=SOURCE_POLICY_LABELS[project.source_policy],
                               teacher=teacher, effects=_effects(project.source_policy))

    # --- couverture des questions par le cours -------------------------------------------------
    def _teacher_documents(self, project_id: str, course_only: bool = False):
        roles = ("course", "rubric", "example") if course_only else TEACHER_ROLES
        return [d for d in self.documents.list(project_id) if d.role.value in roles]

    def course_coverage(self, project_id: str) -> CourseCoverage:
        project = self.projects.get(project_id)
        documents = self._teacher_documents(project_id)
        if not documents:
            raise ValidationFailed("Aucun document de l'enseignant dans ce projet : importez le cours (rôle « course ») "
                                   "et les consignes (rôle « instructions »).")
        self.extraction.index_project(project_id)
        course_docs = self._teacher_documents(project_id, course_only=True)
        notices: list[str] = []
        search_roles: tuple[str, ...] = ("course", "rubric", "example") if course_docs else TEACHER_ROLES
        if not course_docs:
            notices.append("Aucun support de cours (rôle « course ») : la recherche porte sur les consignes elles-mêmes, "
                           "ce qui ne prouve pas que le cours traite la question.")
        requirements = [r for r in self.writing.list_requirements(project_id).requirements
                        if r.kind in ("question", "task") and r.status != "rejected"]
        if not requirements:
            notices.append("Aucune question ni tâche extraite : lancer d'abord analyze_assignment.")
        items: list[CoverageItem] = []
        for requirement in requirements:
            terms = list(dict.fromkeys(w.casefold() for w in _KEYWORD.findall(requirement.text)
                                       if w.casefold() not in _STOP))[:10]
            passages: list[CoveragePassage] = []
            matched: set[str] = set()
            if terms:
                try:
                    hits = self.extraction.search(project_id, " ".join(t[:-1] + "*" if len(t) > 5 else t for t in terms),
                                                  limit=4, match="any", roles=search_roles).hits
                except ValidationFailed:
                    hits = []
                with self.db.read() as conn:
                    for hit in hits:
                        row = conn.execute("SELECT text FROM chunks WHERE id = ?", (hit.chunk_id,)).fetchone()
                        text = (row["text"] if row else "").casefold()
                        found = {t for t in terms if t[: max(4, len(t) - 2)] in text}
                        if found:
                            matched |= found
                            passages.append(CoveragePassage(document=hit.original_filename, page=hit.page,
                                                            snippet=hit.snippet))
            ratio = len(matched) / len(terms) if terms else 0
            status = "covered" if ratio >= 0.6 and passages else "partial" if ratio >= 0.3 and passages else "not_covered"
            items.append(CoverageItem(requirement_id=requirement.id, kind=requirement.kind, text=requirement.text[:600],
                                      status=status, matched_terms=sorted(matched),
                                      missing_terms=[t for t in terms if t not in matched],
                                      passages=passages[:3] if status != "not_covered" else []))
        counts = {s: sum(1 for i in items if i.status == s) for s in ("covered", "partial", "not_covered")}
        if counts["not_covered"]:
            notices.append(f"{counts['not_covered']} question(s) ou tâche(s) sans passage correspondant dans le cours : "
                           "ne pas y répondre avec des connaissances externes sans l'accord de l'utilisateur "
                           "(politique actuelle : " + project.source_policy + ").")
        notices.append("Recherche par mots-clés : un passage trouvé indique où lire, il ne garantit pas que la réponse "
                       "s'y trouve ; une question « non traitée » peut l'être avec d'autres mots. Relecture humaine.")
        return CourseCoverage(project_id=project_id, source_policy=project.source_policy,
                              source_policy_label=SOURCE_POLICY_LABELS[project.source_policy],
                              teacher_documents=[f"{d.original_filename} ({d.role.value})" for d in documents],
                              items=items, covered=counts["covered"], partial=counts["partial"],
                              not_covered=counts["not_covered"], contradictions=self._contradictions(documents),
                              notices=notices)

    def _segments(self, document_id: str) -> list[Segment]:
        result, _ = self.extraction.extract(document_id)
        return [Segment(b.text, "paragraph", None, b.page) for b in result.blocks
                if b.type in ("paragraph", "list_item", "note") and b.text.strip()]

    def _contradictions(self, documents) -> list[CourseContradiction]:
        values: dict[str, list[tuple[float, str, str]]] = {}
        found: list[CourseContradiction] = []
        for document in documents:
            report = check_calculations(document.original_filename, self._segments(document.id))
            for issue in report.conflicts:
                found.append(CourseContradiction(symbol=issue.message.split()[2] if len(issue.message.split()) > 2 else "?",
                                                 values=[document.original_filename], message=issue.message))
            for definition in report.definitions:
                values.setdefault(definition.symbol, []).append(
                    (definition.si_value, definition.value, document.original_filename))
        for symbol, entries in values.items():
            docs = {doc for _, _, doc in entries}
            if len(docs) < 2:
                continue
            reference = entries[0][0]
            different = [e for e in entries if abs(e[0] - reference) > 0.02 * max(abs(reference), abs(e[0]), 1e-12)]
            if different:
                found.append(CourseContradiction(
                    symbol=symbol, values=[f"{v} ({doc})" for _, v, doc in entries][:6],
                    message=f"Le symbole {symbol} a des valeurs différentes selon les documents de l'enseignant : "
                            "signaler la contradiction et demander laquelle retenir (ou s'il s'agit de grandeurs "
                            "différentes)."))
        return found[:40]

    # --- notations du cours ------------------------------------------------------------------------
    def extract_notations(self, project_id: str) -> NotationExtraction:
        self.projects.get(project_id)
        proposals: dict[str, NotationProposal] = {}
        for document in self._teacher_documents(project_id):
            result, _ = self.extraction.extract(document.id)
            for block in result.blocks:
                if block.type not in ("paragraph", "list_item", "note"):
                    continue
                for match in _NOTATION.finditer(block.text):
                    symbol = match.group("sym") or match.group("sym2")
                    meaning = (match.group("meaning") or match.group("meaning2") or "").strip(" —–-:")
                    if not symbol or len(meaning.split()) > 12 or symbol.casefold() in _STOP or len(symbol) > 5:
                        continue
                    if len(symbol) > 2 and symbol.isalpha() and symbol.islower() and len(symbol) > 3:
                        continue  # mot ordinaire, pas un symbole
                    unit_match = _UNIT_IN.search(meaning)
                    unit = unit_match.group(1) if unit_match else None
                    if unit_match:
                        meaning = meaning[:unit_match.start()].strip(" ,(")
                    proposals.setdefault(symbol, NotationProposal(symbol=symbol, meaning=meaning[:200], unit=unit,
                                                                  document=document.original_filename,
                                                                  page=block.page))
        return NotationExtraction(project_id=project_id, proposals=list(proposals.values())[:80])

    # --- barème et définitions -------------------------------------------------------------------------------
    def extract_teacher_material(self, project_id: str) -> TeacherMaterialExtraction:
        """Critères du barème (rôle rubric, ou consignes) et définitions du cours, à faire confirmer."""
        from academic_writer.writing.teacher_extract import definitions, rubric_from_table, rubric_lines

        self.projects.get(project_id)
        documents = self._teacher_documents(project_id)
        if not documents:
            raise ValidationFailed("Aucun document de l'enseignant (rôles course, rubric, instructions…) dans le projet.")
        criteria: list[RubricProposal] = []
        found_definitions: dict[str, DefinitionProposal] = {}
        for document in documents:
            result, _ = self.extraction.extract(document.id)
            for table in result.tables:
                for criterion, points in rubric_from_table(table.rows):
                    criteria.append(RubricProposal(criterion=criterion, points=points,
                                                   document=document.original_filename, page=table.page))
            for block in result.blocks:
                if block.type in ("paragraph", "list_item", "note"):
                    for criterion, points in rubric_lines(block.text):
                        criteria.append(RubricProposal(criterion=criterion, points=points,
                                                       document=document.original_filename, page=block.page))
                    for term, definition in definitions(block.text):
                        found_definitions.setdefault(term.casefold(), DefinitionProposal(
                            term=term, definition=definition, document=document.original_filename, page=block.page))
        total = sum(c.points for c in criteria if c.points is not None) if criteria else None
        notices = ["Propositions automatiques : les faire confirmer, puis les enregistrer dans le profil de l'enseignant "
                   "(update_teacher_profile evaluation_criteria / definitions). Rien n'est enregistré automatiquement."]
        if not criteria:
            notices.append("Aucun barème reconnu (lignes « critère — 4 points » ou tableau critère / points).")
        return TeacherMaterialExtraction(project_id=project_id, criteria=criteria[:80], total_points=total,
                                         definitions=list(found_definitions.values())[:80], notices=notices)
