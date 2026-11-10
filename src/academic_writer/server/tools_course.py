"""Outils MCP : profils d'enseignants, politique de sources, couverture des questions par le cours."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.course import CourseCoverage, NotationExtraction, ProjectTeaching, TeacherMaterialExtraction
from academic_writer.core.teaching import Criterion, Notation, TeacherProfile, TeacherProfileList, TermDefinition
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
Policy = Literal["course_only", "project_sources", "external_allowed"]
_POLICY_HELP = ("course_only : uniquement les documents de l'enseignant (aucune source externe) ; project_sources : "
                "documents et sources du projet ; external_allowed : sources externes permises mais signalées.")


def _details(definitions, expected_structure, detail_level, writing_style, allowed_sources, bibliography_rules,
             layout_rules, evaluation_criteria, work_types) -> dict:
    values = {"definitions": definitions, "expected_structure": expected_structure, "detail_level": detail_level,
              "writing_style": writing_style, "allowed_sources": allowed_sources,
              "bibliography_rules": bibliography_rules, "layout_rules": layout_rules,
              "evaluation_criteria": evaluation_criteria, "work_types": work_types}
    return {k: ([i.model_dump() if hasattr(i, "model_dump") else i for i in v] if isinstance(v, list) else v)
            for k, v in values.items() if v is not None}


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Créer un profil d'enseignant", annotations=_WRITE)
    def create_teacher_profile(
        name: Annotated[str, Field(description="Nom de l'enseignant (tel que l'utilisateur le donne).")],
        subject: str | None = None,
        course: str | None = None,
        institution: str | None = None,
        source_policy: Annotated[Policy, Field(description=_POLICY_HELP)] = "course_only",
        notations: list[Notation] | None = None,
        methods: Annotated[str, Field(description="Méthodes et démarches imposées (ex. « méthode des plans de "
                                                  "vitesses », « unités SI uniquement »).")] = "",
        expectations: Annotated[str, Field(description="Attentes : présentation, niveau de détail, barème.")] = "",
        definitions: list[TermDefinition] | None = None,
        expected_structure: Annotated[list[str] | None, Field(description="Plan attendu (titres).")] = None,
        detail_level: str | None = None,
        writing_style: str | None = None,
        allowed_sources: str | None = None,
        bibliography_rules: str | None = None,
        layout_rules: str | None = None,
        evaluation_criteria: Annotated[list[Criterion] | None, Field(description="Barème : critère et points.")] = None,
        work_types: Annotated[list[str] | None, Field(description="Types de travaux (td, tp, memoire_master…).")] = None,
    ) -> TeacherProfile:
        """Profil réutilisable par enseignant, matière et cours : notations, méthodes, attentes et politique de sources
        appliquées aux projets rattachés. Uniquement avec les informations fournies par l'utilisateur ou le cours."""
        with user_errors():
            details = _details(definitions, expected_structure, detail_level, writing_style, allowed_sources,
                               bibliography_rules, layout_rules, evaluation_criteria, work_types)
            return get_services().course.create_profile(
                name, subject=subject, course=course, institution=institution, source_policy=source_policy,
                notations=notations, methods=methods, expectations=expectations, details=details)

    @mcp.tool(title="Lister les profils d'enseignants", annotations=_READ)
    def list_teacher_profiles() -> TeacherProfileList:
        """Profils d'enseignants enregistrés (réutilisables d'un projet à l'autre)."""
        with user_errors():
            return get_services().course.list_profiles()

    @mcp.tool(title="Modifier un profil d'enseignant", annotations=_WRITE)
    def update_teacher_profile(
        profile_id: str,
        name: str | None = None,
        subject: str | None = None,
        course: str | None = None,
        institution: str | None = None,
        source_policy: Annotated[Policy | None, Field(description=_POLICY_HELP)] = None,
        notations: Annotated[list[Notation] | None, Field(
            description="Remplace la liste des notations (ex. confirmées après extract_course_notations).")] = None,
        methods: str | None = None,
        expectations: str | None = None,
        definitions: list[TermDefinition] | None = None,
        expected_structure: Annotated[list[str] | None, Field(description="Plan attendu (titres).")] = None,
        detail_level: str | None = None,
        writing_style: str | None = None,
        allowed_sources: str | None = None,
        bibliography_rules: str | None = None,
        layout_rules: str | None = None,
        evaluation_criteria: Annotated[list[Criterion] | None, Field(description="Barème : critère et points.")] = None,
        work_types: Annotated[list[str] | None, Field(description="Types de travaux (td, tp, memoire_master…).")] = None,
    ) -> TeacherProfile:
        """Modifie les champs indiqués d'un profil d'enseignant ; les autres sont conservés."""
        changes = {k: v for k, v in {"name": name, "subject": subject, "course": course, "institution": institution,
                                     "source_policy": source_policy, "methods": methods,
                                     "expectations": expectations}.items() if v is not None}
        if notations is not None:
            changes["notations"] = [n.model_dump() for n in notations]
        changes |= _details(definitions, expected_structure, detail_level, writing_style, allowed_sources,
                            bibliography_rules, layout_rules, evaluation_criteria, work_types)
        with user_errors():
            return get_services().course.update_profile(profile_id, changes)

    @mcp.tool(title="Enseignant et sources autorisées du projet", annotations=_WRITE)
    def set_project_teaching(
        project_id: str,
        teacher_profile_id: Annotated[str | None, Field(
            description="Profil à rattacher (sa politique de sources est reprise si source_policy est vide).")] = None,
        source_policy: Annotated[Policy | None, Field(description=_POLICY_HELP)] = None,
        unlink: Annotated[bool, Field(description="Détacher le profil d'enseignant du projet.")] = False,
    ) -> ProjectTeaching:
        """Rattache un profil d'enseignant et/ou fixe les sources autorisées du projet. À faire sur décision de
        l'utilisateur (ou consigne explicite de l'enseignant)."""
        with user_errors():
            return get_services().course.set_project_teaching(
                project_id, teacher_profile_id=teacher_profile_id, source_policy=source_policy, unlink=unlink)

    @mcp.tool(title="Questions traitées par le cours", annotations=_READ)
    def check_course_coverage(project_id: str) -> CourseCoverage:
        """Pour chaque question ou tâche des consignes : passages du cours qui la traitent, ou « non traitée dans le
        cours » ; contradictions entre documents de l'enseignant (même symbole, valeurs différentes). À utiliser
        avant de répondre « uniquement à partir du cours » : une question non traitée est signalée, jamais complétée."""
        with user_errors():
            return get_services().course.course_coverage(project_id)

    @mcp.tool(title="Notations du cours", annotations=_READ)
    def extract_course_notations(project_id: str) -> NotationExtraction:
        """Propose les notations définies dans les documents de l'enseignant (« где m — масса », « où m est la
        masse »…), à faire confirmer puis enregistrer dans le profil de l'enseignant."""
        with user_errors():
            return get_services().course.extract_notations(project_id)

    @mcp.tool(title="Barème et définitions du cours", annotations=_READ)
    def extract_teacher_material(project_id: str) -> TeacherMaterialExtraction:
        """Propose les critères d'évaluation (barème : « critère — 4 points », tableau critère / points) et les
        définitions données dans les documents de l'enseignant (« X désigne… », « X — это… », « … называется X »),
        avec document et page. À faire confirmer, puis enregistrer dans le profil (update_teacher_profile)."""
        with user_errors():
            return get_services().course.extract_teacher_material(project_id)
