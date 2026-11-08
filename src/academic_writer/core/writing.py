"""Service de rédaction encadrée.

Workflow : consignes → exigences (confirmées par l'utilisateur) → plan (approuvé par
l'utilisateur) → rédaction section par section (moteur auto : cloud autorisé, modèle local
ou assistant) → contrôles automatiques → révision proposée → acceptée ou refusée.
Aucune révision n'est jamais écrasée ; l'original des documents n'est jamais modifié.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.domains import DomainService
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.extraction import TRUST_NOTICE, ExtractionService
from academic_writer.core.history import record_event
from academic_writer.core.models import DOCUMENT_TYPE_LABELS, DocumentRole, ProjectStatus, new_id, utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.providers.base import GenerationRequest
from academic_writer.providers.manager import ProviderManager
from academic_writer.storage.db import Database
from academic_writer.writing import briefs
from academic_writer.writing.checks import check_draft, check_fidelity, word_count
from academic_writer.writing.models import (
    AssignmentAnalysis,
    Check,
    DraftSectionStatus,
    DraftStatus,
    Outline,
    OutlineSection,
    OutlineValidation,
    Requirement,
    RequirementList,
    SectionBrief,
    SectionRevision,
    WriteResult,
)
from academic_writer.writing.outline import build_sections, coverage_issues
from academic_writer.writing.requirements import extract_candidates

logger = logging.getLogger("academic_writer.writing")

_BUDGET = {"ollama": 9000, "anthropic": 40000, "openai": 40000, "assistant": 40000}
_KINDS = ("task", "length", "structure", "format", "norm", "deadline", "variant", "data", "other")


class OutlineOperation(BaseModel):
    op: Literal["add", "remove", "rename", "move", "set"]
    section_id: str | None = Field(default=None, description="Section visée (remove, rename, move, set).")
    title: str | None = None
    level: int | None = Field(default=None, ge=1, le=4)
    after_section_id: str | None = Field(default=None, description="Position (add, move) ; vide = en tête.")
    target_words: int | None = Field(default=None, ge=0, le=200000)
    guidance: str | None = None
    requirement_ids: list[str] | None = None


def _req_from_row(row: sqlite3.Row) -> Requirement:
    return Requirement(
        id=row["id"], project_id=row["project_id"], source_document_id=row["source_document_id"],
        source_filename=row["original_filename"] if "original_filename" in row.keys() else None,
        page=row["page"], kind=row["kind"], text=row["text"], value=row["value"], status=row["status"],
        origin=row["origin"], position=row["position"],
    )


class WritingService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService, domains: DomainService, ai: ProviderManager) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction
        self.domains = domains
        self.ai = ai

    def _active_project(self, project_id: str):
        project = self.projects.get(project_id)
        if project.status is ProjectStatus.ARCHIVED:
            raise ValidationFailed("Projet archivé : modification impossible.")
        return project

    # ======================================================================
    # Exigences
    # ======================================================================
    def analyze_assignment(self, project_id: str, document_id: str | None = None) -> AssignmentAnalysis:
        self._active_project(project_id)
        warnings: list[str] = []
        if document_id:
            documents = [self.documents.get(document_id)]
            if documents[0].project_id != project_id:
                raise ValidationFailed("Ce document n'appartient pas au projet.")
        else:
            documents = self.documents.list(project_id, DocumentRole.INSTRUCTIONS)
            if not documents:
                raise ValidationFailed("Aucun document de consignes (rôle « instructions ») dans ce projet : "
                                       "importez les consignes ou précisez document_id.")
        now = utc_now()
        created: list[str] = []
        with self.db.read() as conn:
            existing = {(r["kind"], r["text"]) for r in conn.execute(
                "SELECT kind, text FROM requirements WHERE project_id = ? AND status != 'proposed'", (project_id,))}
        for document in documents:
            result, summary = self.extraction.extract(document.id)
            warnings.extend(f"{document.original_filename} : {w}" for w in summary.injection_warnings)
            candidates = extract_candidates(result)
            if not candidates:
                warnings.append(f"{document.original_filename} : aucune exigence reconnue automatiquement.")
            with self.db.transaction() as conn:
                conn.execute("DELETE FROM requirements WHERE project_id = ? AND source_document_id = ? "
                             "AND origin = 'extracted' AND status = 'proposed'", (project_id, document.id))
                for position, candidate in enumerate(candidates):
                    if (candidate.kind, candidate.text) in existing:
                        continue
                    requirement_id = new_id()
                    conn.execute(
                        "INSERT INTO requirements (id, project_id, source_document_id, page, kind, text, value, status, "
                        "origin, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', 'extracted', ?, ?, ?)",
                        (requirement_id, project_id, document.id, candidate.page, candidate.kind, candidate.text,
                         candidate.value, position, now, now))
                    created.append(requirement_id)
                record_event(conn, project_id=project_id, entity_type="document", entity_id=document.id,
                             action="requirements_extracted", details={"count": len(candidates)})
        listing = self.list_requirements(project_id)
        active = [r for r in listing.requirements if r.status != "rejected"]
        variants = sorted({r.value for r in active if r.kind == "variant" and r.value})
        if len(variants) > 1:
            warnings.append(f"Plusieurs variantes mentionnées ({', '.join(variants)}) : préciser la vôtre.")
        lengths = [r.value for r in active if r.kind == "length" and r.value]
        return AssignmentAnalysis(
            project_id=project_id, analyzed_documents=[d.original_filename for d in documents], extracted=len(created),
            by_kind=listing.by_kind, variant=variants[0] if len(variants) == 1 else None,
            length=lengths[0] if lengths else None,
            norms=sorted({n.strip() for r in active if r.kind == "norm" and r.value for n in r.value.split(",")}),
            deadlines=sorted({r.value for r in active if r.kind == "deadline" and r.value}),
            warnings=warnings, requirements=listing.requirements,
            next_step="Présenter les exigences à l'utilisateur, les faire confirmer ou rejeter (manage_requirement), "
                      "compléter les manques, puis créer le plan (create_academic_outline).",
        )

    def list_requirements(self, project_id: str, kind: str | None = None, status: str | None = None) -> RequirementList:
        self.projects.get(project_id)
        query = ("SELECT r.*, d.original_filename FROM requirements r LEFT JOIN documents d ON d.id = r.source_document_id "
                 "WHERE r.project_id = ?")
        params: list[object] = [project_id]
        if kind:
            query += " AND r.kind = ?"
            params.append(kind)
        if status:
            query += " AND r.status = ?"
            params.append(status)
        query += " ORDER BY CASE r.origin WHEN 'user' THEN 1 ELSE 0 END, d.original_filename, r.position"
        with self.db.read() as conn:
            requirements = [_req_from_row(r) for r in conn.execute(query, params)]
        by_kind: dict[str, int] = {}
        for req in requirements:
            by_kind[req.kind] = by_kind.get(req.kind, 0) + 1
        return RequirementList(project_id=project_id, count=len(requirements), by_kind=by_kind, requirements=requirements)

    def manage_requirement(self, project_id: str, action: str, requirement_id: str | None = None,
                           text: str | None = None, kind: str | None = None, value: str | None = None) -> Requirement:
        self._active_project(project_id)
        now = utc_now()
        if action == "add":
            if not text or not text.strip():
                raise ValidationFailed("Texte de l'exigence obligatoire.")
            kind = kind or "other"
            if kind not in _KINDS:
                raise ValidationFailed(f"Type inconnu : {kind}")
            requirement_id = new_id()
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT INTO requirements (id, project_id, kind, text, value, status, origin, position, created_at, "
                    "updated_at) VALUES (?, ?, ?, ?, ?, 'confirmed', 'user', 0, ?, ?)",
                    (requirement_id, project_id, kind, text.strip()[:2000], value, now, now))
                record_event(conn, project_id=project_id, entity_type="requirement", entity_id=requirement_id,
                             action="added", details={"kind": kind})
            return self._requirement(project_id, requirement_id)
        if not requirement_id:
            raise ValidationFailed("requirement_id obligatoire pour cette action.")
        current = self._requirement(project_id, requirement_id)
        updates: dict[str, object] = {"updated_at": now}
        if action == "confirm":
            updates["status"] = "confirmed"
        elif action == "reject":
            updates["status"] = "rejected"
        elif action == "edit":
            if text:
                updates["text"] = text.strip()[:2000]
            if kind:
                if kind not in _KINDS:
                    raise ValidationFailed(f"Type inconnu : {kind}")
                updates["kind"] = kind
            if value is not None:
                updates["value"] = value
            updates["status"] = "confirmed"
        else:
            raise ValidationFailed("Action inconnue : add, confirm, reject ou edit.")
        assignments = ", ".join(f"{column} = ?" for column in updates)
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE requirements SET {assignments} WHERE id = ?", (*updates.values(), current.id))
            record_event(conn, project_id=project_id, entity_type="requirement", entity_id=current.id, action=action)
        return self._requirement(project_id, requirement_id)

    def _requirement(self, project_id: str, requirement_id: str) -> Requirement:
        with self.db.read() as conn:
            row = conn.execute("SELECT r.*, d.original_filename FROM requirements r LEFT JOIN documents d "
                               "ON d.id = r.source_document_id WHERE r.id = ? AND r.project_id = ?",
                               (requirement_id, project_id)).fetchone()
        if row is None:
            raise NotFoundError(f"Exigence introuvable : {requirement_id}")
        return _req_from_row(row)

    # ======================================================================
    # Plan
    # ======================================================================
    def create_outline(self, project_id: str, target_words: int | None = None) -> Outline:
        project = self._active_project(project_id)
        template = self.domains.structure_template(project_id)
        requirements = self.list_requirements(project_id).requirements
        sections, global_ids, total = build_sections(template, requirements, project.language.value, target_words)
        outline_id = new_id()
        now = utc_now()
        with self.db.transaction() as conn:
            version = conn.execute("SELECT coalesce(max(version), 0) + 1 FROM outlines WHERE project_id = ?",
                                   (project_id,)).fetchone()[0]
            conn.execute("UPDATE outlines SET status = 'superseded' WHERE project_id = ? AND status != 'superseded'",
                         (project_id,))
            conn.execute(
                "INSERT INTO outlines (id, project_id, version, status, language, convention, domain_id, target_words, "
                "global_requirement_ids, created_at) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)",
                (outline_id, project_id, version, project.language.value, template.convention, template.domain_id,
                 total, json.dumps(global_ids), now))
            for position, section in enumerate(sections):
                conn.execute(
                    "INSERT INTO outline_sections (id, outline_id, position, section_key, title, level, required, guidance, "
                    "target_words, requirement_ids, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id(), outline_id, position, section.section_key, section.title, section.level,
                     int(section.required), section.guidance, section.target_words,
                     json.dumps(section.requirement_ids), section.origin))
            record_event(conn, project_id=project_id, entity_type="outline", entity_id=outline_id, action="created",
                         details={"version": version, "sections": len(sections)})
        return self.get_outline(outline_id)

    def get_outline(self, outline_id: str) -> Outline:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,)).fetchone()
            if row is None:
                raise NotFoundError(f"Plan introuvable : {outline_id}")
            sections = conn.execute("SELECT * FROM outline_sections WHERE outline_id = ? ORDER BY position",
                                    (outline_id,)).fetchall()
        return Outline(
            id=row["id"], project_id=row["project_id"], version=row["version"], status=row["status"],
            language=row["language"], convention=row["convention"], domain_id=row["domain_id"],
            target_words=row["target_words"], global_requirement_ids=json.loads(row["global_requirement_ids"]),
            created_at=row["created_at"], approved_at=row["approved_at"],
            sections=[OutlineSection(
                id=s["id"], position=s["position"], section_key=s["section_key"], title=s["title"], level=s["level"],
                required=bool(s["required"]), guidance=s["guidance"], target_words=s["target_words"],
                requirement_ids=json.loads(s["requirement_ids"]), status=s["status"], origin=s["origin"])
                for s in sections],
        )

    def current_outline(self, project_id: str) -> Outline | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT id FROM outlines WHERE project_id = ? AND status != 'superseded' "
                               "ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()
        return self.get_outline(row["id"]) if row else None

    def edit_outline(self, outline_id: str, operations: list[OutlineOperation]) -> Outline:
        outline = self.get_outline(outline_id)
        self._active_project(outline.project_id)
        if outline.status == "superseded":
            raise ValidationFailed("Ce plan a été remplacé par une version plus récente.")
        if not operations:
            raise ValidationFailed("Aucune opération.")
        order = [s.id for s in outline.sections]
        known = {s.id: s for s in outline.sections}
        with self.db.transaction() as conn:
            for operation in operations:
                if operation.op == "add":
                    if not operation.title or not operation.title.strip():
                        raise ValidationFailed("Titre obligatoire pour ajouter une section.")
                    section_id = new_id()
                    conn.execute(
                        "INSERT INTO outline_sections (id, outline_id, position, title, level, required, guidance, "
                        "target_words, requirement_ids, origin) VALUES (?, ?, 0, ?, ?, 1, ?, ?, ?, 'user')",
                        (section_id, outline_id, operation.title.strip()[:300], operation.level or 1,
                         operation.guidance, operation.target_words, json.dumps(operation.requirement_ids or [])))
                    index = order.index(operation.after_section_id) + 1 if operation.after_section_id in order else 0
                    order.insert(index, section_id)
                    continue
                if operation.section_id not in known and operation.section_id not in order:
                    raise NotFoundError(f"Section introuvable dans ce plan : {operation.section_id}")
                if operation.op == "remove":
                    with_revisions = conn.execute("SELECT count(*) FROM section_revisions WHERE section_id = ?",
                                                  (operation.section_id,)).fetchone()[0]
                    if with_revisions:
                        raise ValidationFailed("Section déjà rédigée : suppression refusée (son historique serait perdu). "
                                               "Renommez-la ou créez un nouveau plan.")
                    conn.execute("DELETE FROM outline_sections WHERE id = ?", (operation.section_id,))
                    order.remove(operation.section_id)
                elif operation.op == "move":
                    order.remove(operation.section_id)
                    index = order.index(operation.after_section_id) + 1 if operation.after_section_id in order else 0
                    order.insert(index, operation.section_id)
                elif operation.op in ("rename", "set"):
                    updates: dict[str, object] = {}
                    if operation.title:
                        updates["title"] = operation.title.strip()[:300]
                    if operation.level:
                        updates["level"] = operation.level
                    if operation.target_words is not None:
                        updates["target_words"] = operation.target_words
                    if operation.guidance is not None:
                        updates["guidance"] = operation.guidance
                    if operation.requirement_ids is not None:
                        updates["requirement_ids"] = json.dumps(operation.requirement_ids)
                    if not updates:
                        raise ValidationFailed("Rien à modifier pour cette opération.")
                    assignments = ", ".join(f"{column} = ?" for column in updates)
                    conn.execute(f"UPDATE outline_sections SET {assignments} WHERE id = ?",
                                 (*updates.values(), operation.section_id))
            for position, section_id in enumerate(order):
                conn.execute("UPDATE outline_sections SET position = ? WHERE id = ?", (position, section_id))
            conn.execute("UPDATE outlines SET status = 'draft', approved_at = NULL WHERE id = ?", (outline_id,))
            record_event(conn, project_id=outline.project_id, entity_type="outline", entity_id=outline_id,
                         action="edited", details={"operations": [o.op for o in operations]})
        return self.get_outline(outline_id)

    def validate_outline(self, outline_id: str, approve: bool = False, force: bool = False) -> OutlineValidation:
        outline = self.get_outline(outline_id)
        self._active_project(outline.project_id)
        if outline.status == "superseded":
            raise ValidationFailed("Ce plan a été remplacé par une version plus récente.")
        template = self.domains.structure_template(outline.project_id)
        required = {s.id: s.title for s in template.sections if s.required}
        requirements = self.list_requirements(outline.project_id).requirements
        issues = coverage_issues([s.model_dump() for s in outline.sections], requirements,
                                 outline.global_requirement_ids, required)
        errors = [i for i in issues if i.severity == "error"]
        approved = False
        if approve and (not errors or force):
            with self.db.transaction() as conn:
                conn.execute("UPDATE outlines SET status = 'approved', approved_at = ? WHERE id = ?", (utc_now(), outline_id))
                record_event(conn, project_id=outline.project_id, entity_type="outline", entity_id=outline_id,
                             action="approved", details={"forced": bool(errors), "issues": len(issues)})
            approved = True
        if approved:
            message = "Plan approuvé par l'utilisateur" + (" malgré des exigences non couvertes." if errors else ".")
        elif approve:
            message = f"Approbation refusée : {len(errors)} problème(s) bloquant(s). Corrigez le plan ou forcez l'approbation."
        else:
            message = "Contrôle effectué. Présentez le plan et les problèmes à l'utilisateur ; approuvez seulement sur sa demande."
        return OutlineValidation(outline=self.get_outline(outline_id), approved=approved, issues=issues, message=message)

    # ======================================================================
    # Dossiers de section et rédaction
    # ======================================================================
    def _section(self, project_id: str, section_id: str) -> tuple[Outline, OutlineSection]:
        outline = self.current_outline(project_id)
        if outline is None:
            raise ValidationFailed("Aucun plan pour ce projet : créez-le (create_academic_outline).")
        section = next((s for s in outline.sections if s.id == section_id), None)
        if section is None:
            raise NotFoundError(f"Section introuvable dans le plan actuel : {section_id}")
        return outline, section

    def _sources_text(self, project_id: str, limit: int = 300_000) -> str:
        parts: list[str] = []
        size = 0
        with self.db.read() as conn:
            for row in conn.execute("SELECT text FROM chunks WHERE project_id = ? ORDER BY document_id, seq", (project_id,)):
                parts.append(row["text"])
                size += len(row["text"])
                if size > limit:
                    break
            parts.extend(r["text"] + " " + (r["value"] or "") for r in conn.execute(
                "SELECT text, value FROM requirements WHERE project_id = ? AND status != 'rejected'", (project_id,)))
            parts.extend(r["text"] for r in conn.execute(
                "SELECT text FROM section_revisions WHERE project_id = ? AND status = 'accepted'", (project_id,)))
        return "\n".join(parts)

    def build_brief(self, project_id: str, section_id: str, *, instructions: str | None = None,
                    base_text: str | None = None, engine: str = "assistant") -> SectionBrief:
        project = self.projects.get(project_id)
        outline, section = self._section(project_id, section_id)
        language = project.language.value
        profile = self.domains.get_domain(outline.domain_id)
        template = self.domains.structure_template(project_id)
        requirements = {r.id: r for r in self.list_requirements(project_id).requirements}
        linked = [requirements[i] for i in section.requirement_ids if i in requirements and requirements[i].status != "rejected"]
        global_reqs = [requirements[i] for i in outline.global_requirement_ids
                       if i in requirements and requirements[i].status != "rejected"]

        self.extraction.index_project(project_id)
        words = re.findall(r"\w{5,}", " ".join([section.title, section.guidance or ""] + [r.text for r in linked]))
        query = " ".join(dict.fromkeys(words))[:400]
        excerpts: list[tuple[str, str]] = []
        if query:
            try:
                hits = self.extraction.search(project_id, query, limit=6, match="any").hits
            except ValidationFailed:
                hits = []
            with self.db.read() as conn:
                for hit in hits:
                    row = conn.execute("SELECT text FROM chunks WHERE id = ?", (hit.chunk_id,)).fetchone()
                    if row:
                        label = hit.original_filename + (f", p. {hit.page}" if hit.page else "")
                        excerpts.append((label, row["text"]))
        data_reqs = [r for r in requirements.values() if r.kind == "data" and r.status != "rejected"]
        context = " ".join([section.title, section.guidance or "", instructions or "", base_text or ""]
                           + [r.text for r in linked] + [text for _, text in excerpts]).casefold()
        relevant, others = [], []
        for term in profile.terminology:
            name = getattr(term, language) or term.fr or term.en
            if not name:
                continue
            avoid = term.avoid.get(language)
            line = name + (f" (éviter : {', '.join(avoid)})" if avoid else "")
            stems = [w[:6] for w in re.findall(r"\w{4,}", name.casefold())]
            if term.definition and stems and any(stem in context for stem in stems):
                relevant.append(f"{line} — définition de référence : {term.definition.get(language)}")
            else:
                others.append(line)
        terms = relevant + others  # définitions des termes concernés en premier
        with self.db.read() as conn:
            previous = [(r["title"], r["text"]) for r in conn.execute(
                "SELECT s.title, v.text FROM section_revisions v JOIN outline_sections s ON s.id = v.section_id "
                "WHERE v.project_id = ? AND v.status = 'accepted' AND s.outline_id = ? ORDER BY s.position",
                (project_id, outline.id))]

        def describe(req: Requirement) -> str:
            source = f" [{req.source_filename}" + (f", p. {req.page}" if req.page else "") + "]" if req.source_filename else ""
            return f"({req.kind}) {req.text}{source}"

        brief_text = briefs.build_brief(
            project_name=project.name, project_description=project.description, section_title=section.title,
            section_guidance=section.guidance, target_words=section.target_words,
            outline_titles=[("  " * (s.level - 1)) + s.title for s in outline.sections],
            requirements=[describe(r) for r in linked] + [describe(r) for r in data_reqs if r not in linked][:10],
            global_requirements=[describe(r) for r in global_reqs], excerpts=excerpts, terminology=terms,
            previous_sections=previous, instructions=instructions, base_text=base_text,
            budget_chars=_BUDGET.get(engine, 20000))
        system = briefs.system_prompt(
            language=language, document_type=DOCUMENT_TYPE_LABELS[project.document_type],
            domain_name=profile.names.get(language), convention_label=template.convention_label,
            rules=template.validation_rules,
            risk_notice=profile.risk_notice.get(language) if profile.risk_level == "high" and profile.risk_notice else None,
            mode="rewrite" if base_text else "draft")
        return SectionBrief(project_id=project_id, section_id=section_id, section_title=section.title, language=language,
                            target_words=section.target_words, system_prompt=system, brief=brief_text,
                            source_excerpts=len(excerpts), trust_notice=TRUST_NOTICE)

    def write_section(self, project_id: str, section_id: str, instructions: str | None = None,
                      engine: str | None = None) -> WriteResult:
        return self._generate(project_id, section_id, kind="draft", instructions=instructions, engine=engine)

    def rewrite_section(self, project_id: str, section_id: str, instructions: str,
                        revision_id: str | None = None, engine: str | None = None) -> WriteResult:
        if not instructions or not instructions.strip():
            raise ValidationFailed("Indiquez ce qu'il faut changer (instructions de réécriture).")
        base = self.get_revision(revision_id) if revision_id else self._latest_revision(section_id)
        if base is None:
            raise ValidationFailed("Aucune version existante à réécrire : rédigez d'abord la section.")
        if base.section_id != section_id:
            raise ValidationFailed("Cette révision n'appartient pas à la section indiquée.")
        return self._generate(project_id, section_id, kind="rewrite", instructions=instructions, engine=engine, base=base)

    def _generate(self, project_id: str, section_id: str, *, kind: str, instructions: str | None,
                  engine: str | None, base: SectionRevision | None = None) -> WriteResult:
        self._active_project(project_id)
        outline, section = self._section(project_id, section_id)
        if outline.status != "approved":
            raise ValidationFailed("Le plan n'est pas approuvé : faites-le valider par l'utilisateur (validate_outline).")
        choice = self.ai.resolve_engine(project_id, engine)
        brief = self.build_brief(project_id, section_id, instructions=instructions,
                                 base_text=base.text if base else None, engine=choice.engine)
        if choice.engine == "assistant":
            action = "réécris" if base else "rédige"
            return WriteResult(engine="assistant", engine_reason=choice.reason, brief=brief,
                               next_step=f"L'assistant {action} la section en respectant system_prompt et brief, puis appelle "
                                         f"save_section_draft (section_id={section_id}"
                                         + (f", parent_revision_id={base.id}, kind=rewrite" if base else "") + ").")
        target = section.target_words or 400
        result = self.ai.generate(project_id, GenerationRequest(
            task=f"section_{kind}", system=brief.system_prompt, prompt=brief.brief,
            max_output_tokens=max(1024, min(self.settings.ai_max_output_tokens, int(target * 3)))), provider=choice.engine)
        text = briefs.clean_output(result.text, section.title)
        revision = self._store_revision(project_id, section_id, text, kind=kind, engine=result.provider,
                                        model=result.model, parent=base, truncated=result.truncated,
                                        note=instructions or "")
        return WriteResult(engine=choice.engine, engine_reason=choice.reason, revision=revision,
                           next_step="Présenter le texte et les contrôles à l'utilisateur, puis accepter ou refuser la "
                                     "révision selon SA décision (review_revision).")

    def save_section_draft(self, project_id: str, section_id: str, text: str, *, kind: str = "draft",
                           parent_revision_id: str | None = None, note: str = "", engine: str = "assistant",
                           model: str | None = None) -> SectionRevision:
        self._active_project(project_id)
        outline, section = self._section(project_id, section_id)
        if outline.status != "approved":
            raise ValidationFailed("Le plan n'est pas approuvé : faites-le valider par l'utilisateur (validate_outline).")
        if kind not in ("draft", "rewrite", "translation", "correction"):
            raise ValidationFailed(f"Type de révision inconnu : {kind}")
        if not text or not text.strip():
            raise ValidationFailed("Texte vide.")
        parent = self.get_revision(parent_revision_id) if parent_revision_id else None
        if parent is not None and parent.section_id != section_id:
            raise ValidationFailed("La révision parente n'appartient pas à cette section.")
        return self._store_revision(project_id, section_id, briefs.clean_output(text, section.title), kind=kind,
                                    engine=engine, model=model, parent=parent, note=note)

    def _store_revision(self, project_id: str, section_id: str, text: str, *, kind: str, engine: str,
                        model: str | None, parent: SectionRevision | None, truncated: bool = False,
                        note: str = "") -> SectionRevision:
        project = self.projects.get(project_id)
        outline, section = self._section(project_id, section_id)
        language = project.language.value
        profile = self.domains.get_domain(outline.domain_id)
        checks: list[Check] = check_draft(text, language=language, target_words=section.target_words,
                                          sources_text=self._sources_text(project_id), profile=profile,
                                          truncated=truncated, is_references_section=section.section_key == "references")
        if parent is not None:
            checks += check_fidelity(parent.text, text, profile, language)
        revision_id = new_id()
        now = utc_now()
        with self.db.transaction() as conn:
            version = conn.execute("SELECT coalesce(max(version), 0) + 1 FROM section_revisions WHERE section_id = ?",
                                   (section_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO section_revisions (id, project_id, section_id, version, kind, engine, model, language, text, "
                "word_count, checks, status, parent_revision_id, note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?)",
                (revision_id, project_id, section_id, version, kind, engine, model, language, text, word_count(text),
                 json.dumps([c.model_dump() for c in checks], ensure_ascii=False), parent.id if parent else None,
                 note[:2000], now))
            conn.execute("UPDATE outline_sections SET status = 'drafted' WHERE id = ? AND status = 'planned'", (section_id,))
            record_event(conn, project_id=project_id, entity_type="section", entity_id=section_id, action=f"revision_{kind}",
                         details={"revision": revision_id, "engine": engine, "words": word_count(text),
                                  "warnings": sum(c.severity != "info" for c in checks)})
        logger.info("Révision %s (%s, %s) proposée pour la section %s", revision_id, kind, engine, section_id)
        return self.get_revision(revision_id)

    # ======================================================================
    # Révisions
    # ======================================================================
    def get_revision(self, revision_id: str) -> SectionRevision:
        with self.db.read() as conn:
            row = conn.execute("SELECT v.*, s.title FROM section_revisions v JOIN outline_sections s ON s.id = v.section_id "
                               "WHERE v.id = ?", (revision_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Révision introuvable : {revision_id}")
        return SectionRevision(
            id=row["id"], project_id=row["project_id"], section_id=row["section_id"], section_title=row["title"],
            version=row["version"], kind=row["kind"], engine=row["engine"], model=row["model"], language=row["language"],
            text=row["text"], word_count=row["word_count"], checks=[Check(**c) for c in json.loads(row["checks"])],
            status=row["status"], parent_revision_id=row["parent_revision_id"], note=row["note"],
            created_at=row["created_at"], decided_at=row["decided_at"])

    def _latest_revision(self, section_id: str) -> SectionRevision | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT id FROM section_revisions WHERE section_id = ? AND status IN ('accepted', 'proposed') "
                               "ORDER BY CASE status WHEN 'accepted' THEN 0 ELSE 1 END, version DESC LIMIT 1",
                               (section_id,)).fetchone()
        return self.get_revision(row["id"]) if row else None

    def review_revision(self, revision_id: str, decision: str, note: str = "") -> SectionRevision:
        revision = self.get_revision(revision_id)
        self._active_project(revision.project_id)
        if revision.status != "proposed":
            raise ValidationFailed(f"Révision déjà traitée (statut : {revision.status}).")
        if decision not in ("accept", "reject"):
            raise ValidationFailed("Décision : accept ou reject.")
        now = utc_now()
        with self.db.transaction() as conn:
            if decision == "accept":
                conn.execute("UPDATE section_revisions SET status = 'superseded', decided_at = coalesce(decided_at, ?) "
                             "WHERE section_id = ? AND status = 'accepted'", (now, revision.section_id))
                conn.execute("UPDATE outline_sections SET status = 'validated' WHERE id = ?", (revision.section_id,))
            conn.execute("UPDATE section_revisions SET status = ?, decided_at = ?, note = CASE WHEN ? = '' THEN note "
                         "ELSE note || ' | ' || ? END WHERE id = ?",
                         ("accepted" if decision == "accept" else "rejected", now, note, note[:1000], revision_id))
            record_event(conn, project_id=revision.project_id, entity_type="section", entity_id=revision.section_id,
                         action=f"revision_{decision}ed", details={"revision": revision_id})
        return self.get_revision(revision_id)

    def draft_status(self, project_id: str) -> DraftStatus:
        self.projects.get(project_id)
        outline = self.current_outline(project_id)
        if outline is None:
            return DraftStatus(project_id=project_id, outline_id=None, outline_status=None, sections=[], accepted_words=0,
                               target_words=None, progress="Aucun plan.")
        statuses: list[DraftSectionStatus] = []
        total = 0
        with self.db.read() as conn:
            for section in outline.sections:
                rows = conn.execute("SELECT id, status, word_count FROM section_revisions WHERE section_id = ? "
                                    "ORDER BY version", (section.id,)).fetchall()
                accepted = next((r for r in reversed(rows) if r["status"] == "accepted"), None)
                total += accepted["word_count"] if accepted else 0
                statuses.append(DraftSectionStatus(
                    section_id=section.id, title=section.title, level=section.level, status=section.status,
                    target_words=section.target_words, accepted_words=accepted["word_count"] if accepted else None,
                    accepted_revision_id=accepted["id"] if accepted else None,
                    pending_revision_ids=[r["id"] for r in rows if r["status"] == "proposed"]))
        writable = [s for s in statuses if s.target_words]
        done = sum(1 for s in writable if s.accepted_revision_id)
        return DraftStatus(project_id=project_id, outline_id=outline.id, outline_status=outline.status, sections=statuses,
                           accepted_words=total, target_words=outline.target_words,
                           progress=f"{done}/{len(writable)} sections rédigées et validées ; {total} mots acceptés.")
