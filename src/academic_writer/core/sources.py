"""Service des sources : enregistrement, vérification, citations, bibliographie, audit.

Principe : aucune référence n'apparaît dans un texte sans source enregistrée. Les citations sont
des marqueurs stables [@clé] ; la bibliographie et les appels ([1], (Иванов, 2020)) sont calculés
à partir des textes acceptés et du style choisi.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3

from academic_writer.core.config import Settings
from academic_writer.core.documents import DocumentService
from academic_writer.core.errors import ConflictError, NotFoundError, ValidationFailed
from academic_writer.core.extraction import ExtractionService
from academic_writer.core.history import record_event
from academic_writer.core.models import new_id, utc_now
from academic_writer.core.projects import ProjectService
from academic_writer.core.writing import WritingService
from academic_writer.research import styles
from academic_writer.research.models import (
    STATUS_LABELS,
    TRUSTED_STATUSES,
    AuditIssue,
    Bibliography,
    BibliographyEntry,
    CitationResult,
    Finding,
    Person,
    ReferenceAudit,
    ImportedSource,
    OpenAccessDownload,
    ReferenceExport,
    Source,
    SourceData,
    SourceImport,
    SourceList,
    SourceSearch,
    VerificationResult,
)
from academic_writer.document.text_reader import decode_text
from academic_writer.providers import secrets
from academic_writer.research.discovery import DiscoveryResult, find_by_topic
from academic_writer.research.fulltext import DownloadRefused, http_bytes, http_text, resolve_pdf, to_bibtex, to_ris
from academic_writer.research.importers import parse_file
from academic_writer.research.manual import manual_links
from academic_writer.research.online import Fetcher, http_fetch, search_online, similarity, verify_online
from academic_writer.research.validation import check_source, make_key, normalize_doi
from academic_writer.security.paths import ensure_within, resolve_user_file
from academic_writer.storage.db import Database

logger = logging.getLogger("academic_writer.sources")

DOUBTFUL = {"suspicious", "not_found", "mismatch"}
_RAW_CITATION = re.compile(r"\[\d+(?:[,–-]\s*\d+)*\]|\([A-ZА-ЯЁ][\w\-]+(?: et al\.| и др\.)?,? \d{4}[a-z]?\)")


def _row_to_source(row: sqlite3.Row, citations: int = 0) -> Source:
    status = row["verification_status"]
    data = SourceData.model_validate_json(row["data"])
    return Source(
        id=row["id"], project_id=row["project_id"], key=row["key"], source_type=row["source_type"],
        data=data, document_id=row["document_id"], origin=row["origin"],
        verification_status=status, status_label=STATUS_LABELS[status],
        verification_details=[Finding(**f) for f in json.loads(row["verification_details"])],
        verified_at=row["verified_at"], citation_count=citations, manual_links=manual_links(data),
    )


def person_from_text(text: str) -> Person:
    """« Иванов Иван Иванович », « Иванов И. И. », « Dupont, Marie » ou « Marie Dupont » → Person."""
    text = " ".join(text.split()).strip(" ,;")
    if "," in text:
        family, given = [p.strip() for p in text.split(",", 1)]
        return Person(family=family, given=given or None)
    parts = text.split(" ")
    if len(parts) == 1:
        return Person(family=parts[0])
    if re.search(r"[А-Яа-яЁё]", text) or re.fullmatch(r"(?:[A-ZА-Я]\.\s?){1,3}", " ".join(parts[1:])):
        return Person(family=parts[0], given=" ".join(parts[1:]))
    return Person(family=parts[-1], given=" ".join(parts[:-1]))


def same_work(a: SourceData, b: SourceData) -> bool:
    """Même ouvrage : DOI ou ISBN identiques, ou même année + titres très proches (ou proches et même
    premier auteur : « Теория механизмов и машин : учебник » = « Теория механизмов и машин »)."""
    if a.doi and b.doi and normalize_doi(a.doi).casefold() == normalize_doi(b.doi).casefold():
        return True
    if a.isbn and b.isbn and re.sub(r"[^0-9Xx]", "", a.isbn) == re.sub(r"[^0-9Xx]", "", b.isbn):
        return True
    if not (a.title and b.title) or a.year is None or a.year != b.year:
        return False
    score = similarity(a.title, b.title)
    same_author = bool(a.authors and b.authors and a.authors[0].family.casefold() == b.authors[0].family.casefold())
    return score >= 0.85 or (score >= 0.6 and same_author)


class SourceService:
    def __init__(self, db: Database, settings: Settings, projects: ProjectService, documents: DocumentService,
                 extraction: ExtractionService, writing: WritingService, fetcher: Fetcher | None = None) -> None:
        self.db = db
        self.settings = settings
        self.projects = projects
        self.documents = documents
        self.extraction = extraction
        self.writing = writing
        self.fetcher = fetcher or http_fetch
        self.text_fetcher = http_text
        self.bytes_fetcher = http_bytes

    # --- lecture ---------------------------------------------------------------
    def _cited_counts(self, project_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for text in self._accepted_texts(project_id).values():
            for _, items in styles.parse_markers(text):
                for key, _ in items:
                    counts[key] = counts.get(key, 0) + 1
        return counts

    def get(self, source_id: str) -> Source:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Source introuvable : {source_id}")
        return _row_to_source(row, self._cited_counts(row["project_id"]).get(row["key"], 0))

    def by_key(self, project_id: str, key: str) -> Source:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM sources WHERE project_id = ? AND key = ?", (project_id, key)).fetchone()
        if row is None:
            raise NotFoundError(f"Aucune source de clé « {key} » dans ce projet.")
        return self.get(row["id"])

    def list(self, project_id: str, status: str | None = None) -> SourceList:
        self.projects.get(project_id)
        counts = self._cited_counts(project_id)
        query, params = "SELECT * FROM sources WHERE project_id = ?", [project_id]
        if status:
            query += " AND verification_status = ?"
            params.append(status)
        with self.db.read() as conn:
            rows = conn.execute(query + " ORDER BY key", params).fetchall()
        sources = [_row_to_source(r, counts.get(r["key"], 0)) for r in rows]
        by_status: dict[str, int] = {}
        for source in sources:
            by_status[source.verification_status] = by_status.get(source.verification_status, 0) + 1
        return SourceList(project_id=project_id, count=len(sources), by_status=by_status, sources=sources)

    def keys(self, project_id: str) -> set[str]:
        with self.db.read() as conn:
            return {r["key"] for r in conn.execute("SELECT key FROM sources WHERE project_id = ?", (project_id,))}

    # --- enregistrement ------------------------------------------------------------
    def _duplicate_of(self, project_id: str, data: SourceData, exclude: str | None = None) -> str | None:
        for source in self.list(project_id).sources:
            if source.id != exclude and same_work(data, source.data):
                return source.key
        return None

    def register(self, project_id: str, source_type: str, data: SourceData, key: str | None = None,
                 document_id: str | None = None, allow_duplicate: bool = False) -> Source:
        self._require_external_sources(project_id, "Enregistrer une source bibliographique")
        self.writing._active_project(project_id)
        if document_id:
            document = self.documents.get(document_id)
            if document.project_id != project_id:
                raise ValidationFailed("Ce document n'appartient pas au projet.")
        if data.doi:
            data.doi = normalize_doi(data.doi)
        duplicate = self._duplicate_of(project_id, data)
        if duplicate and not allow_duplicate:
            raise ConflictError(f"Doublon probable de la source « {duplicate} » (même DOI, ISBN ou titre et année).")
        existing = self.keys(project_id)
        if key:
            if not re.fullmatch(r"[A-Za-z0-9_:\-]{2,40}", key):
                raise ValidationFailed("Clé invalide : lettres latines, chiffres, _ : - (2 à 40 caractères).")
            if key in existing:
                raise ConflictError(f"La clé « {key} » existe déjà dans ce projet.")
        else:
            key = make_key(data, existing)
        status, findings = check_source(source_type, data)
        source_id = new_id()
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO sources (id, project_id, key, source_type, data, document_id, origin, verification_status, "
                "verification_details, verified_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, project_id, key, source_type, data.model_dump_json(exclude_none=True), document_id,
                 "document" if document_id else "user", status,
                 json.dumps([f.model_dump() for f in findings], ensure_ascii=False), now, now, now))
            record_event(conn, project_id=project_id, entity_type="source", entity_id=source_id, action="registered",
                         details={"key": key, "type": source_type, "status": status})
        return self.get(source_id)

    def register_from_document(self, project_id: str, document_id: str, source_type: str = "other") -> Source:
        """Pré-remplit une fiche avec les métadonnées d'un document importé (à compléter par l'utilisateur)."""
        self._require_external_sources(project_id, "Enregistrer un document comme source")
        result, _ = self.extraction.extract(document_id)
        meta = result.metadata
        title = meta.get("title") or next((b.text for b in result.blocks if b.type == "heading"), None)
        author = meta.get("author") or meta.get("creator")
        year = None
        for field in ("created", "creationdate", "modified"):
            match = re.search(r"(19|20)\d{2}", meta.get(field, "") or "")
            if match:
                year = int(match.group(0))
                break
        data = SourceData(title=title[:500] if title else None,
                          authors=[person_from_text(a) for a in re.split(r"[;,]\s*(?=[A-ZА-ЯЁ])", author) if a.strip()]
                          if author else [],
                          year=year, notes="Pré-rempli depuis les métadonnées du fichier : à vérifier et compléter.")
        return self.register(project_id, source_type, data, document_id=document_id)

    def update(self, source_id: str, changes: dict, source_type: str | None = None) -> Source:
        source = self.get(source_id)
        self.writing._active_project(source.project_id)
        merged = source.data.model_dump()
        merged.update({k: v for k, v in changes.items()})
        try:
            data = SourceData.model_validate(merged)
        except ValueError as exc:
            raise ValidationFailed(f"Métadonnées invalides : {exc}") from exc
        if data.doi:
            data.doi = normalize_doi(data.doi)
        source_type = source_type or source.source_type
        duplicate = self._duplicate_of(source.project_id, data, exclude=source.id)
        if duplicate:
            raise ConflictError(f"Après modification, doublon probable de « {duplicate} ».")
        status, findings = check_source(source_type, data)
        with self.db.transaction() as conn:
            conn.execute("UPDATE sources SET source_type = ?, data = ?, verification_status = ?, verification_details = ?, "
                         "verified_at = ?, updated_at = ? WHERE id = ?",
                         (source_type, data.model_dump_json(exclude_none=True), status,
                          json.dumps([f.model_dump() for f in findings], ensure_ascii=False), utc_now(), utc_now(),
                          source_id))
            record_event(conn, project_id=source.project_id, entity_type="source", entity_id=source_id,
                         action="updated", details={"fields": sorted(changes)})
        return self.get(source_id)

    # --- vérification -------------------------------------------------------------------
    def confirm_manual(self, source_id: str, where: str, note: str = "") -> Source:
        """L'utilisateur déclare avoir trouvé la source dans un catalogue (РГБ, eLIBRARY, bibliothèque…)."""
        source = self.get(source_id)
        self.writing._active_project(source.project_id)
        if not where or not where.strip():
            raise ValidationFailed("Indiquez où la source a été vérifiée (ex. « РГБ », « eLIBRARY », « bibliothèque »).")
        status, findings = check_source(source.source_type, source.data)
        if status == "suspicious":
            raise ValidationFailed("Fiche suspecte (identifiant invalide ou date impossible) : corrigez-la d'abord.")
        now = utc_now()
        findings.append(Finding(severity="info", message=f"Vérifiée manuellement par l'utilisateur dans « {where.strip()} » "
                                                         f"le {now[:10]}" + (f" : {note.strip()}" if note.strip() else ".")))
        with self.db.transaction() as conn:
            conn.execute("UPDATE sources SET verification_status = 'verified_manual', verification_details = ?, "
                         "verified_at = ?, updated_at = ? WHERE id = ?",
                         (json.dumps([f.model_dump() for f in findings], ensure_ascii=False), now, now, source_id))
            record_event(conn, project_id=source.project_id, entity_type="source", entity_id=source_id,
                         action="verified_manual", details={"where": where.strip()[:100]})
        return self.get(source_id)

    def verify(self, source_id: str, online: bool = True) -> VerificationResult:
        source = self.get(source_id)
        status, findings = check_source(source.source_type, source.data)
        if source.verification_status == "verified_manual" and status == "well_formed":
            status = "verified_manual"  # une vérification humaine n'est pas effacée par un résultat non concluant
            findings += [f for f in source.verification_details if "manuellement" in f.message]
        notice, candidates, checked = None, [], False
        if online and status != "suspicious":
            if self.settings.mode != "connected":
                notice = ("Mode local : vérification en ligne non effectuée (Crossref, Open Library). Elle n'envoie que "
                          "des métadonnées (DOI, ISBN, titre) ; activable avec mode = 'connected'.")
            else:
                try:
                    outcome = verify_online(source.data, self.fetcher, self._service_keys())
                    checked = True
                    findings += outcome.findings
                    candidates = outcome.candidates
                    if outcome.status in ("not_found", "mismatch") or (
                            outcome.status == "verified_online" and status != "incomplete"):
                        status = outcome.status
                except OSError as exc:
                    notice = f"Vérification en ligne impossible (réseau) : {exc}"
        with self.db.transaction() as conn:
            conn.execute("UPDATE sources SET verification_status = ?, verification_details = ?, verified_at = ?, "
                         "updated_at = ? WHERE id = ?",
                         (status, json.dumps([f.model_dump() for f in findings], ensure_ascii=False), utc_now(), utc_now(),
                          source_id))
            record_event(conn, project_id=source.project_id, entity_type="source", entity_id=source_id,
                         action="verified", details={"status": status, "online": checked})
        return VerificationResult(source=self.get(source_id), online_checked=checked, online_notice=notice,
                                  candidates=candidates)

    def _service_keys(self) -> dict[str, str]:
        keys = {}
        for name in secrets.METADATA_SERVICES:
            key = secrets.get_key(name)
            if key:
                keys[name] = key
        return keys

    # --- recherche et import ----------------------------------------------------------------
    def search(self, query: str, author: str | None = None, isbn: str | None = None,
               kind: str = "all", limit: int = 5) -> SourceSearch:
        if not (query and query.strip()) and not isbn:
            raise ValidationFailed("Indiquez un titre (query) ou un ISBN.")
        if self.settings.mode != "connected":
            raise ValidationFailed("Mode local : la recherche en ligne (Google Books, OpenAlex, Crossref) est désactivée. "
                                   "Elle n'envoie que les termes de recherche ; activable avec mode = 'connected'.")
        candidates, services, notices = search_online(query or "", author, self.fetcher, self._service_keys(),
                                                      kind=kind, isbn=isbn, limit=max(1, min(limit, 10)))
        notices.append("Fiches proposées à partir de catalogues : les faire CONFIRMER par l'utilisateur avant "
                       "register_source (data = candidat.data).")
        return SourceSearch(query=query or isbn or "", services=services, candidates=candidates, notices=notices)

    def _require_external_sources(self, project_id: str, what: str) -> None:
        """Politique « course_only » : l'enseignant exige de répondre uniquement à partir du cours."""
        if self.projects.get(project_id).source_policy == "course_only":
            raise ValidationFailed(
                f"{what} : refusé. Ce projet suit la consigne de l'enseignant « uniquement à partir du cours » "
                "(politique course_only). Pour autoriser des sources externes, l'utilisateur doit changer la "
                "politique (set_project_teaching source_policy=project_sources ou external_allowed).")

    def _require_connected(self, what: str) -> None:
        if self.settings.mode != "connected":
            raise ValidationFailed(f"Mode local : {what} est désactivé(e). Seuls les termes de recherche ou "
                                   "l'identifiant sont envoyés ; activable avec mode = 'connected'.")

    def discover(self, query: str, kind: str = "all", open_access_only: bool = False, language: str | None = None,
                 limit: int = 10, services: list[str] | None = None, author: str | None = None,
                 year_from: int | None = None, year_to: int | None = None,
                 publication_type: str | None = None, discipline: str | None = None,
                 project_id: str | None = None) -> DiscoveryResult:
        if not query or len(query.strip()) < 3:
            raise ValidationFailed("Indiquez un thème de recherche (au moins 3 caractères).")
        self._require_connected("la recherche d'ouvrages par thème")
        auto_domain = None
        if discipline == "aucune":
            discipline = None
        elif discipline is None:  # reconnaissance automatique : domaine du projet, sinon vocabulaire de la recherche
            if project_id:
                auto_domain = self.projects.get(project_id).domain_id
            if not auto_domain:
                auto_domain = self._detect_domain(query)
        return find_by_topic(query.strip(), self.text_fetcher, kind, open_access_only, language,
                             max(1, min(limit, 25)), keys=self._service_keys(),
                             services_filter=services,
                             author=author, year_from=year_from, year_to=year_to, publication_type=publication_type,
                             local_records=self._cyberleninka_records(), discipline=discipline,
                             auto_domain=auto_domain, auto_label=self._domain_label(auto_domain))

    def _domain_label(self, domain_id: str | None) -> str | None:
        from academic_writer.domains.registry import DomainRegistry

        if not domain_id:
            return None
        try:
            if getattr(self, "_domain_registry", None) is None:
                self._domain_registry = DomainRegistry(self.settings)
            return self._domain_registry.get(domain_id).names.get("fr")
        except (NotFoundError, OSError, ValueError):  # libellé facultatif : jamais bloquant
            return None

    def _detect_domain(self, query: str) -> str | None:
        from academic_writer.domains.registry import DomainRegistry
        from academic_writer.research import disciplines

        try:
            if getattr(self, "_domain_registry", None) is None:
                self._domain_registry = DomainRegistry(self.settings)
            return disciplines.detect(query, self._domain_registry.all())
        except (OSError, ValueError):
            return None

    def download_open_access(self, project_id: str, item_id: str) -> OpenAccessDownload:
        self._require_external_sources(project_id, "Télécharger un texte externe")
        self.writing._active_project(project_id)
        self._require_connected("le téléchargement en libre accès")
        try:
            url, license_text, filename = resolve_pdf(item_id, self.text_fetcher, self._service_keys())
            data = self.bytes_fetcher(url, self.settings.max_file_size_bytes)
        except DownloadRefused as exc:
            raise ValidationFailed(str(exc)) from exc
        except OSError as exc:
            raise ValidationFailed(f"Téléchargement impossible : {exc}") from exc
        temp_dir = self.settings.data_dir / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp = temp_dir / f"{new_id()}.pdf"
        try:
            temp.write_bytes(data)
            result = self.documents.import_downloaded(project_id, temp, original_name=filename, source_label=url)
        finally:
            temp.unlink(missing_ok=True)
        message = (f"Texte intégral en libre accès importé dans le projet (licence : {license_text}). "
                   "Il peut maintenant être lu, cherché et cité ; enregistrez aussi sa fiche (register_source).")
        if result.duplicate:
            message = "Ce fichier était déjà présent dans le projet."
        return OpenAccessDownload(item_id=item_id, document_id=result.document.id,
                                  original_filename=result.document.original_filename, duplicate=result.duplicate,
                                  license=license_text, url=url, message=message)

    def export_references(self, project_id: str, fmt: str = "bibtex", style: str = "gost",
                          keys: list[str] | None = None) -> ReferenceExport:
        listing = self.list(project_id)
        sources = [s for s in listing.sources if not keys or s.key in keys]
        if not sources:
            raise ValidationFailed("Aucune source à exporter.")
        if fmt == "bibtex":
            content, extension = "\n\n".join(to_bibtex(s.key, s.source_type, s.data) for s in sources), "bib"
        elif fmt == "ris":
            content, extension = "\n\n".join(to_ris(s.key, s.source_type, s.data) for s in sources), "ris"
        elif fmt == "text":
            if style not in styles.FORMATTERS:
                raise ValidationFailed("Style : gost, apa, ieee, chicago, vancouver, harvard ou iso690.")
            ordered = sorted(sources, key=lambda s: styles.sort_key(s.data))
            content = "\n".join(f"{i}. {styles.format_entry(style, s.source_type, s.data)}" for i, s in enumerate(ordered, 1))
            extension = "txt"
        else:
            raise ValidationFailed("Format : bibtex, ris ou text.")
        folder = self.settings.projects_dir / project_id / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"references-{utc_now()[:19].replace(':', '').replace('-', '').replace('T', '-')}.{extension}"
        path.write_text(content + "\n", encoding="utf-8")
        return ReferenceExport(project_id=project_id, format=fmt, count=len(sources), path=str(path),
                               content=content[:20000])

    def import_file(self, project_id: str, file_path: str) -> SourceImport:
        self._require_external_sources(project_id, "Importer des références")
        self.writing._active_project(project_id)
        path = resolve_user_file(file_path)
        ensure_within(path, self.settings.allowed_import_dirs)
        extension = path.suffix.lower()
        if extension not in (".ris", ".bib", ".txt"):
            raise ValidationFailed("Format accepté : .ris, .bib (ou .txt contenant du RIS / BibTeX).")
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValidationFailed("Fichier de notices trop volumineux (5 Mo maximum).")
        text, _ = decode_text(path.read_bytes())
        entries = parse_file(text, extension)
        if not entries:
            raise ValidationFailed("Aucune notice RIS ou BibTeX reconnue dans ce fichier.")
        imported: list[ImportedSource] = []
        duplicates: list[str] = []
        errors: list[str] = []
        existing = self.keys(project_id)
        for entry in entries:
            label = (entry.data.title or "(sans titre)")[:80]
            key = entry.key if entry.key and entry.key not in existing else None
            try:
                source = self.register(project_id, entry.source_type, entry.data, key=key)
            except ConflictError:
                duplicates.append(label)
                continue
            except (ValidationFailed, ValueError) as exc:
                errors.append(f"{label} : {exc}")
                continue
            existing.add(source.key)
            imported.append(ImportedSource(key=source.key, title=source.data.title, source_type=source.source_type,
                                           status=source.verification_status))
        fmt = "BibTeX" if extension == ".bib" or text.lstrip().startswith("@") else "RIS"
        problems = sum(1 for s in imported if s.status in ("incomplete", "suspicious"))
        message = (f"{len(imported)} source(s) importée(s), {len(duplicates)} doublon(s) ignoré(s), "
                   f"{len(errors)} erreur(s)." + (f" {problems} fiche(s) à compléter ou à vérifier." if problems else ""))
        return SourceImport(project_id=project_id, file=path.name, format=fmt, found=len(entries), imported=imported,
                            duplicates=duplicates, errors=errors, message=message)

    # --- citations ------------------------------------------------------------------------
    def insert_citation(self, project_id: str, section_id: str, source_key: str, anchor_text: str,
                        locator: str | None = None, claim: str | None = None, force: bool = False) -> CitationResult:
        self._require_external_sources(project_id, "Insérer une citation")
        self.writing._active_project(project_id)
        source = self.by_key(project_id, source_key)
        if source.verification_status in DOUBTFUL and not force:
            raise ValidationFailed(f"Source « {source_key} » {STATUS_LABELS[source.verification_status]} : citation "
                                   "refusée. Corrigez la fiche, ou forcez sur décision explicite de l'utilisateur.")
        base = self.writing.base_revision(section_id, None)
        if not anchor_text or base.text.count(anchor_text) != 1:
            count = base.text.count(anchor_text) if anchor_text else 0
            raise ValidationFailed(f"Le passage d'ancrage doit apparaître exactement une fois dans la section "
                                   f"(trouvé {count} fois). Donnez un extrait exact et unique.")
        marker = f"[@{source_key}" + (f", {locator.strip()}" if locator and locator.strip() else "") + "]"
        start = base.text.index(anchor_text)
        insert_at = start + len(anchor_text)
        while insert_at > start and base.text[insert_at - 1] in ".,;:!?…":
            insert_at -= 1  # l'appel se place avant la ponctuation finale du passage
        text = base.text[:insert_at].rstrip() + " " + marker + base.text[insert_at:]
        revision = self.writing._store_revision(project_id, section_id, text, kind="rewrite", engine="citation",
                                                model=None, parent=base, language=base.language,
                                                note=f"citation {marker}")
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO citations (id, project_id, source_id, section_id, revision_id, locator, claim, "
                         "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (new_id(), project_id, source.id, section_id, revision.id, locator, claim, utc_now()))
        warning = "" if source.verification_status in TRUSTED_STATUSES else \
            f" Attention : source {STATUS_LABELS[source.verification_status]}."
        return CitationResult(marker=marker, source=source, revision_id=revision.id,
                              message="Révision proposée avec la citation : à accepter par l'utilisateur." + warning)

    # --- bibliographie -------------------------------------------------------------------------
    def _accepted_texts(self, project_id: str) -> dict[str, str]:
        """Textes acceptés (langue du projet), dans l'ordre du plan : {titre de section: texte}."""
        outline = self.writing.current_outline(project_id)
        if outline is None:
            return {}
        texts: dict[str, str] = {}
        with self.db.read() as conn:
            for section in outline.sections:
                row = conn.execute("SELECT text FROM section_revisions WHERE section_id = ? AND status = 'accepted' "
                                   "AND language = ? ORDER BY version DESC LIMIT 1",
                                   (section.id, outline.language)).fetchone()
                if row and section.section_key != "references":
                    texts[section.title] = row["text"]
        return texts

    def generate_bibliography(self, project_id: str, style: str = "gost", ordering: str | None = None,
                              include_uncited: bool = False, save: bool = False) -> Bibliography:
        if style not in styles.FORMATTERS:
            raise ValidationFailed("Style : gost, apa, ieee, chicago, vancouver, harvard ou iso690.")
        ordering = ordering or ("appearance" if style in styles.NUMERIC_STYLES else "alphabetical")
        sources = {s.key: s for s in self.list(project_id).sources}
        order: list[str] = []
        warnings: list[str] = []
        unknown: set[str] = set()
        for text in self._accepted_texts(project_id).values():
            for _, items in styles.parse_markers(text):
                for key, _ in items:
                    if key not in sources:
                        unknown.add(key)
                    elif key not in order:
                        order.append(key)
        if unknown:
            warnings.append(f"Citations vers des clés inconnues (aucune source enregistrée) : {', '.join(sorted(unknown))}.")
        keys = list(order)
        uncited = [k for k in sources if k not in order]
        if include_uncited:
            keys += uncited
        elif uncited:
            warnings.append(f"{len(uncited)} source(s) enregistrée(s) jamais citée(s), exclue(s) : {', '.join(uncited)}.")
        if ordering == "alphabetical":
            keys.sort(key=lambda k: styles.sort_key(sources[k].data))
        doubtful = [k for k in keys if sources[k].verification_status not in TRUSTED_STATUSES]
        if doubtful:
            warnings.append("Sources non vérifiées ou problématiques : " + ", ".join(
                f"{k} ({STATUS_LABELS[sources[k].verification_status]})" for k in doubtful))
        numbers = {key: index for index, key in enumerate(keys, start=1)}
        entries: list[BibliographyEntry] = []
        lines: list[str] = []
        for key in keys:
            source = sources[key]
            text = styles.format_entry(style, source.source_type, source.data)
            number = numbers[key] if style in styles.NUMERIC_STYLES else None
            marker = styles.render_markers(f"[@{key}]", style, numbers, {k: s.data for k, s in sources.items()})
            entries.append(BibliographyEntry(key=key, number=number, marker=marker, text=text,
                                             status=source.verification_status, cited=key in order))
            lines.append(f"[{number}] {text}" if style == "ieee" else f"{number}. {text}" if number else text)
        bibliography_text = "\n\n".join(lines)
        revision_id = None
        if save:
            outline = self.writing.current_outline(project_id)
            section = next((s for s in outline.sections if s.section_key == "references"), None) if outline else None
            if section is None:
                warnings.append("Aucune section « bibliographie » dans le plan : rien n'a été enregistré.")
            elif not entries:
                warnings.append("Bibliographie vide : rien n'a été enregistré.")
            else:
                revision_id = self.writing._store_revision(project_id, section.id, bibliography_text, kind="draft",
                                                           engine="bibliography", model=None, parent=None,
                                                           note=f"bibliographie {style}").id
        return Bibliography(project_id=project_id, style=style, style_label=styles.STYLE_LABELS[style],
                            ordering=ordering, entries=entries, text=bibliography_text, warnings=warnings,
                            revision_id=revision_id)

    # --- audit -----------------------------------------------------------------------------------
    def audit(self, project_id: str) -> ReferenceAudit:
        sources = {s.key: s for s in self.list(project_id).sources}
        texts = self._accepted_texts(project_id)
        issues: list[AuditIssue] = []
        cited: set[str] = set()
        total = 0
        for title, text in texts.items():
            for _, items in styles.parse_markers(text):
                for key, _ in items:
                    total += 1
                    if key in sources:
                        cited.add(key)
                    else:
                        issues.append(AuditIssue(severity="error", code="unknown_key", source_key=key, section_title=title,
                                                 message=f"Citation [@{key}] sans source enregistrée."))
            raw = sorted(set(_RAW_CITATION.findall(styles.MARKER.sub("", text))))
            if raw:
                issues.append(AuditIssue(severity="warning", code="unmanaged_citation", section_title=title,
                                         message=f"Citations écrites à la main, non reliées à une source : {', '.join(raw[:8])} "
                                                 "(utiliser insert_citation)."))
        for key, source in sources.items():
            if key not in cited:
                issues.append(AuditIssue(severity="info", code="uncited", source_key=key,
                                         message=f"Source « {key} » jamais citée dans les sections acceptées."))
            status = source.verification_status
            if status in DOUBTFUL:
                issues.append(AuditIssue(severity="error", code=f"status_{status}", source_key=key,
                                         message=f"Source « {key} » : {STATUS_LABELS[status]}."))
            elif status in ("incomplete", "unverified"):
                issues.append(AuditIssue(severity="warning", code=f"status_{status}", source_key=key,
                                         message=f"Source « {key} » : {STATUS_LABELS[status]}."))
        keys = list(sources)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if same_work(sources[a].data, sources[b].data):
                    issues.append(AuditIssue(severity="warning", code="duplicate", source_key=b,
                                             message=f"Sources « {a} » et « {b} » probablement identiques."))
        errors = sum(i.severity == "error" for i in issues)
        summary = (f"{len(sources)} source(s), {len(cited)} citée(s), {total} citation(s) dans le texte ; "
                   f"{errors} erreur(s), {sum(i.severity == 'warning' for i in issues)} avertissement(s).")
        return ReferenceAudit(project_id=project_id, sources=len(sources), cited_sources=len(cited),
                              citations_in_text=total, issues=issues, summary=summary)

    def uncited(self, project_id: str) -> SourceList:
        listing = self.list(project_id)
        counts = self._cited_counts(project_id)
        sources = [s for s in listing.sources if counts.get(s.key, 0) == 0]
        return SourceList(project_id=project_id, count=len(sources), by_status={}, sources=sources)

    # --- rétractations, chercheurs, données ouvertes ------------------------------------------------------------
    def check_retractions(self, project_id: str | None = None, doi: str | None = None):
        from academic_writer.research.openscience_more import crossref_updates
        from academic_writer.research.validation import normalize_doi

        self._require_connected("la vérification des rétractations (Crossref)")
        targets: list[tuple[str, str]] = []
        if doi:
            targets.append(("DOI", normalize_doi(doi) or doi))
        if project_id:
            targets += [(s.key, s.data.doi) for s in self.list(project_id).sources if s.data.doi]
        if not targets:
            raise ValidationFailed("Aucun DOI à vérifier (indiquez doi ou un projet dont les sources ont un DOI).")
        results = []
        for label, value in targets[:60]:
            try:
                notices = crossref_updates(value, self.text_fetcher)
                results.append({"source": label, "doi": value, "notices": [n.model_dump() for n in notices],
                                "status": ("RÉTRACTÉ" if any(n.type in ("retraction", "withdrawal", "removal")
                                                              for n in notices) else
                                           "à examiner" if notices else "aucun avis connu")})
            except OSError as exc:
                results.append({"source": label, "doi": value, "notices": [], "status": f"non vérifié ({exc})"})
        return {"checked": len(results), "results": results,
                "notice": "Avis de Crossref (rétractation, retrait, correction, avis d'inquiétude). « Aucun avis connu » "
                          "ne garantit pas l'absence de problème."}

    def find_researcher(self, family: str, given: str | None = None):
        from academic_writer.research.openscience_more import search_orcid

        self._require_connected("la recherche ORCID")
        if not family or len(family.strip()) < 2:
            raise ValidationFailed("Indiquez le nom de famille.")
        return search_orcid(family.strip(), given.strip() if given else None, self.text_fetcher)

    def open_data(self, provider: str, dataset: str, country: str | None = None, years: str | None = None,
                  filters: dict[str, str] | None = None):
        from academic_writer.research import openscience_more as more

        self._require_connected("l'accès aux données ouvertes")
        try:
            if provider == "worldbank":
                return more.worldbank(dataset, country or "", years, self.text_fetcher)
            if provider == "eurostat":
                return more.eurostat(dataset, filters or {}, self.text_fetcher)
        except (ValueError, OSError) as exc:
            raise ValidationFailed(str(exc)) from exc
        raise ValidationFailed("Fournisseur : worldbank ou eurostat.")

    # --- données de référence : constantes CODATA (NIST) -----------------------------
    def physical_constants(self, query: str):
        from academic_writer.research.reference_data import load_codata, search_constants

        if not query or len(query.strip()) < 2:
            raise ValidationFailed("Indiquez le nom d'une constante (ex. « Avogadro », « electron mass »).")
        try:
            constants, origin = load_codata(self.settings.data_dir / "reference", self.text_fetcher,
                                            self.settings.mode == "connected")
        except (ValueError, OSError) as exc:
            raise ValidationFailed(str(exc)) from exc
        found = search_constants(constants, query)
        return {"query": query, "origin": origin, "constants": [c.model_dump() for c in found],
                "notice": "Valeurs officielles CODATA publiées par le NIST (noms en anglais) ; citer l'édition CODATA."}

    # --- КиберЛенинка (OAI-PMH officiel, index local) -------------------------------------------------------
    def _cyberleninka_records(self) -> list:
        from academic_writer.research.cyberleninka import harvested

        try:
            return harvested(self.settings.data_dir)
        except OSError:
            return []

    def cyberleninka_journals(self, query: str):
        from academic_writer.research.cyberleninka import find_journals, journals

        if not query or len(query.strip()) < 3:
            raise ValidationFailed("Indiquez un mot du titre de la revue (ex. « машиностроение », « Бауман »).")
        try:
            listing = journals(self.settings.data_dir, self.text_fetcher, self.settings.mode == "connected")
        except (ValueError, OSError) as exc:
            raise ValidationFailed(str(exc)) from exc
        found = find_journals(listing, query)
        return {"query": query, "total_journals": len(listing), "journals": [j.model_dump() for j in found],
                "next_step": "Moissonner une revue avec cyberleninka_harvest(set_spec) ; ses articles apparaissent ensuite "
                             "dans find_works_by_topic (base « cyberleninka »)."}

    def cyberleninka_harvest(self, set_spec: str, max_pages: int = 60):
        from academic_writer.research.cyberleninka import harvest, journals

        self._require_connected("le moissonnage КиберЛенинка (OAI-PMH)")
        listing = {j.set_spec: j.name for j in journals(self.settings.data_dir, self.text_fetcher, True)}
        if set_spec not in listing:
            raise ValidationFailed("Revue inconnue : chercher d'abord son identifiant avec cyberleninka_journals.")
        try:
            return harvest(self.settings.data_dir, self.text_fetcher, set_spec, listing[set_spec],
                           max(1, min(max_pages, 300)))
        except (ValueError, OSError) as exc:
            raise ValidationFailed(f"Moissonnage interrompu : {exc}") from exc

    def cyberleninka_harvest_discipline(self, discipline: str, max_pages_per_journal: int = 20):
        """Moissonne les revues КиберЛенинка d'une discipline (une page par seconde)."""
        from academic_writer.research import disciplines
        from academic_writer.research.cyberleninka import harvest

        self._require_connected("le moissonnage КиберЛенинка (OAI-PMH)")
        try:
            profile = disciplines.get(discipline)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
        results = []
        for set_spec, name in profile.cyberleninka_journals.items():
            try:
                results.append(harvest(self.settings.data_dir, self.text_fetcher, set_spec, name,
                                       max(1, min(max_pages_per_journal, 100))).model_dump())
            except (ValueError, OSError) as exc:
                results.append({"set_spec": set_spec, "journal": name, "records": 0, "error": str(exc)})
        return {"discipline": profile.name, "journals": len(results),
                "records": sum(r.get("records", 0) for r in results), "results": results,
                "next_step": "Les articles moissonnés apparaissent dans find_works_by_topic (base « cyberleninka »)."}
