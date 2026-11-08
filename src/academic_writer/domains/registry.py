"""Chargement des profils : intégrés au logiciel + profils de l'utilisateur, avec héritage.

- Profils intégrés : ``academic_writer/domain_profiles/*.yaml``.
- Profils utilisateur : ``<data_dir>/profiles/*.yaml`` ; un profil utilisateur portant le
  même identifiant qu'un profil intégré le remplace.
- Un profil invalide est écarté et signalé (le serveur continue de fonctionner).
- Fusion avec le parent : listes fusionnées par identifiant (l'enfant l'emporte) ;
  les mots-clés de détection ne sont pas hérités (ils doivent rester spécifiques).
"""

from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path

import yaml
from pydantic import ValidationError

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError
from academic_writer.domains.model import DomainProfile, SectionSpec

logger = logging.getLogger("academic_writer.domains")

GENERALIST_ID = "generaliste"
_MAX_PROFILE_BYTES = 1_000_000


def builtin_profiles_dir() -> Path:
    return Path(str(resources.files("academic_writer") / "domain_profiles"))


def _merge_by(parent: list, child: list, key: str) -> list:
    merged = {getattr(item, key): item for item in parent}
    for item in child:
        merged[getattr(item, key)] = item
    return list(merged.values())


def _merge_sections(parent: dict[str, list[SectionSpec]], child: dict[str, list[SectionSpec]]):
    result = {k: list(v) for k, v in parent.items()}
    for doc_type, sections in child.items():
        result[doc_type] = _merge_by(result.get(doc_type, []), sections, "id")
    return result


def merge_profiles(parent: DomainProfile, child: DomainProfile) -> DomainProfile:
    data = child.model_copy(deep=True)
    data.terminology = _merge_by(parent.terminology, child.terminology, "id")
    data.validation_rules = _merge_by(parent.validation_rules, child.validation_rules, "id")
    data.calculations = _merge_by(parent.calculations, child.calculations, "id")
    data.standards = _merge_by(parent.standards, child.standards, "code")
    data.document_sections = _merge_sections(parent.document_sections, child.document_sections)
    data.methodology = child.methodology or parent.methodology
    styles = dict(parent.bibliography.preferred_styles)
    styles.update(child.bibliography.preferred_styles)
    data.bibliography = child.bibliography.model_copy(update={
        "preferred_styles": styles,
        "notes": child.bibliography.notes or parent.bibliography.notes,
        "min_sources": {**parent.bibliography.min_sources, **child.bibliography.min_sources},
    })
    if parent.risk_level == "high" and child.risk_level != "high":
        data.risk_level = "high"
        data.risk_notice = child.risk_notice or parent.risk_notice
    return data


class DomainRegistry:
    def __init__(self, settings: Settings, builtin_dir: Path | None = None) -> None:
        self.settings = settings
        self.builtin_dir = builtin_dir or builtin_profiles_dir()
        self.user_dir = settings.data_dir / "profiles"
        self.errors: list[str] = []
        self._raw: dict[str, DomainProfile] = {}
        self._resolved: dict[str, DomainProfile] = {}
        self.reload()

    def reload(self) -> None:
        self.errors = []
        raw: dict[str, DomainProfile] = {}
        for source, directory in (("builtin", self.builtin_dir), ("user", self.user_dir)):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.yaml")):
                if path.name.startswith("_"):
                    continue
                profile = self._load_file(path, source)
                if profile is not None:
                    if profile.id in raw and source == "user":
                        logger.info("Profil utilisateur %s : remplace le profil intégré", profile.id)
                    raw[profile.id] = profile
        self._raw = raw
        self._resolved = {}
        for profile_id in list(raw):
            try:
                self._resolve(profile_id, [])
            except ValueError as exc:
                self.errors.append(str(exc))
        if GENERALIST_ID not in self._resolved:
            self.errors.append("Profil généraliste introuvable ou invalide.")

    def _load_file(self, path: Path, source: str) -> DomainProfile | None:
        label = f"{source}:{path.name}"
        try:
            if path.stat().st_size > _MAX_PROFILE_BYTES:
                raise ValueError("fichier trop volumineux")
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("le fichier doit contenir un objet YAML")
            data["source"] = source
            return DomainProfile.model_validate(data)
        except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
            message = str(exc).replace("\n", " ")[:500]
            self.errors.append(f"Profil {label} ignoré : {message}")
            logger.warning("Profil %s ignoré : %s", label, message)
            return None

    def _resolve(self, profile_id: str, chain: list[str]) -> DomainProfile:
        if profile_id in self._resolved:
            return self._resolved[profile_id]
        if profile_id in chain:
            raise ValueError(f"Héritage circulaire : {' → '.join(chain + [profile_id])}")
        profile = self._raw.get(profile_id)
        if profile is None:
            raise ValueError(f"Profil parent introuvable : {profile_id} (requis par {chain[-1] if chain else '?'})")
        if profile.parent:
            parent = self._resolve(profile.parent, chain + [profile_id])
            profile = merge_profiles(parent, profile)
        self._resolved[profile_id] = profile
        return profile

    # --- accès -------------------------------------------------------------
    def get(self, profile_id: str) -> DomainProfile:
        profile = self._resolved.get(profile_id)
        if profile is None:
            raise NotFoundError(f"Profil disciplinaire introuvable : {profile_id}")
        return profile

    def raw(self, profile_id: str) -> DomainProfile:
        return self._raw[profile_id]

    def all(self) -> list[DomainProfile]:
        return sorted(self._resolved.values(), key=lambda p: (p.id != GENERALIST_ID, p.id))

    def ids(self) -> list[str]:
        return [p.id for p in self.all()]
