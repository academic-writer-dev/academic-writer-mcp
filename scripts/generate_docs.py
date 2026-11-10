"""Génère les catalogues de la documentation à partir du code (toujours à jour).

Commande : uv run python scripts/generate_docs.py
Produit : docs/SOFTWARE_CATALOG.md, docs/provider_status.md, docs/approved_free_libraries.md,
docs/excluded_paid_providers.md, docs/access_verification_report.md, docs/DOMAIN_COVERAGE.md
"""

from __future__ import annotations

import sys
import tempfile
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
HEADER = "<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->\n\n"


def write(name: str, text: str) -> None:
    (DOCS / name).write_text(HEADER + text.rstrip() + "\n", encoding="utf-8")
    print("écrit :", name)


def software_catalog() -> None:
    from academic_writer.core.software import CATEGORIES, CATALOG, INDUSTRIAL_RULES

    lines = ["# Catalogue des logiciels", "",
             f"{len(CATALOG)} logiciels. Colonne « Academic Writer » : **native** = exécuté réellement par le serveur ; "
             "**détection** = détecté et conseillé, aucune exécution (sauf moteurs de `run_software_job`).", ""]
    for category, label in CATEGORIES.items():
        lines += [f"## {label}", "", "| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |",
                  "|---|---|---|---|---|---|"]
        for spec in (s for s in CATALOG if s.category == category):
            lines.append(f"| {spec.name} | {spec.license} | {spec.cost} | {'; '.join(spec.methods)} | "
                         f"{'native' if spec.native else 'détection'}{' ⚠ industriel' if spec.industrial else ''} | "
                         f"{spec.free_alternative or '—'} |")
        lines.append("")
    lines += ["## Règles pour les automatismes industriels", ""] + [f"- {r}" for r in INDUSTRIAL_RULES]
    write("SOFTWARE_CATALOG.md", "\n".join(lines))


REMOVED = (
    ("Semantic Scholar", "quota public saturé : refus (HTTP 429) pour 9 recherches sur 9 ; clé réservée aux adresses "
                         "institutionnelles"),
    ("CORE", "clé gratuite obligatoire, jamais obtenue (formulaire refusé à l'automatisation)"),
    ("Europeana", "clé gratuite obligatoire, jamais obtenue"),
    ("Unpaywall", "adresse e-mail obligatoire dans chaque requête : non configurée"),
    ("BASE (Bielefeld)", "accès refusé par adresse IP"),
    ("OAPEN, Gallica, Library of Congress", "HTTP 403 aux requêtes automatisées (jamais contourné)"),
    ("OECD", "requêtes de données refusées au client automatisé (HTTP 403)"),
    ("CiNii Research, Research Data Australia, engrXiv", "recherche interdite aux robots par robots.txt"),
    ("DPLA, Trove, DDB", "clé personnelle obligatoire, non obtenue"),
    ("Redalyc", "interface OAI-PMH sans résultat (revues présentes dans DOAJ et OpenAlex)"),
    ("DART-Europe, RePEc, IMF", "pas d'interface automatisée exploitable"),
    ("eLIBRARY, РГБ, НЭБ, РНБ, ГПНТБ, ФЭМБ", "pas d'API publique autorisée ; РГБ et НЭБ injoignables depuis le poste"),
    ("ВИНИТИ РАН", "accès payant"),
)


def providers() -> None:
    from academic_writer.research.providers import PROVIDERS, VERIFIED_ON, summary

    rows = ["| Fournisseur | Région | Contenu | Statut | Clé | Texte intégral | Intégration | Vérification réelle |",
            "|---|---|---|---|---|---|---|---|"]
    rows += [f"| [{p.name}]({p.url}) | {p.region} | {p.content} | `{p.access}` | {p.key} | {p.full_text} | "
             f"{p.integration} | {p.verification} |" for p in PROVIDERS]
    counts = ", ".join(f"{k} : {v}" for k, v in sorted(summary().items()))
    write("provider_status.md", "# Statut des fournisseurs documentaires\n\n"
          f"Vérification réelle le {VERIFIED_ON} depuis le poste de l'utilisateur (mode connecté). Répartition : {counts}.\n\n"
          "Statuts : PUBLIC_FREE (A), FREE_ACCOUNT / FREE_API_KEY (B), PAID_EXCLUDED, UNVERIFIED_EXCLUDED, "
          "UNAVAILABLE.\n\n" + "\n".join(rows))
    removed = "\n".join(f"| {name} | {reason} |" for name, reason in REMOVED)
    write("excluded_paid_providers.md", "# Services retirés du serveur\n\n"
          f"Retirés le {VERIFIED_ON} après test réel : ils ne sont plus ni interrogés, ni listés comme connectés. "
          "Ils pourront être rebranchés si leur situation change (clé gratuite obtenue, accès autorisé).\n\n"
          "| Service | Raison du retrait |\n|---|---|\n" + removed
          + "\n\nFournisseurs d'IA payants (Anthropic, OpenAI) : présents mais **désactivés par défaut** "
            "(mode connecté + clé + consentement écrit du projet) ; jamais obligatoires.")
    write("access_verification_report.md", "# Rapport de vérification des accès\n\n"
          f"Date : {VERIFIED_ON}. Méthode : requête réelle depuis le poste (seuls des termes de recherche ou des "
          "identifiants sont envoyés), lecture de la réponse, contrôle du format et des conditions affichées.\n\n"
          + "\n".join(f"- **{p.name}** — {p.verification} (`{p.access}`)" for p in PROVIDERS)
          + "\n\nPoints notables :\n- OpenAlex : sans clé, budget gratuit partagé par adresse IP ; une clé gratuite "
            "(sans paiement) relève la limite. La réponse contenait une invitation adressée aux « agents IA » à "
            "envoyer l'adresse e-mail de l'utilisateur : non suivie.\n- Test du 2026-11-10 : 9 thèmes (mécanique, "
            "médecine, droit, histoire, informatique, économie, agronomie, en français et en russe) ; une coupure "
            "de la connexion pendant le premier passage a été écartée par un second test.")


def libraries() -> None:
    import tomllib

    project = tomllib.loads((DOCS.parent / "pyproject.toml").read_text(encoding="utf-8"))
    rows = ["| Bibliothèque | Version installée | Licence | Rôle |", "|---|---|---|---|"]
    roles = {"mcp": "serveur MCP", "pydantic": "validation", "pydantic-settings": "configuration",
             "pypdfium2": "PDF", "pdfplumber": "PDF (tableaux)", "python-docx": "Word", "openpyxl": "Excel",
             "python-pptx": "PowerPoint", "sympy": "calcul formel", "scipy": "calcul numérique",
             "matplotlib": "graphiques", "pillow": "images", "keyring": "coffre des clés", "truststore": "certificats",
             "charset-normalizer": "encodages", "pyyaml": "profils disciplinaires", "anthropic": "IA (facultatif)",
             "openai": "IA (facultatif)"}
    for requirement in project["project"]["dependencies"]:
        name = requirement.split(">")[0].split("[")[0].split("=")[0].split("<")[0].strip()
        try:
            dist = distribution(name)
            meta = dist.metadata
            license_text = meta.get("License-Expression") or next(
                (c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")),
                (meta.get("License") or "?").splitlines()[0][:40])
            rows.append(f"| {name} | {dist.version} | {license_text} | {roles.get(name, '')} |")
        except PackageNotFoundError:
            rows.append(f"| {name} | non installée | ? | {roles.get(name, '')} |")
    write("approved_free_libraries.md", "# Bibliothèques et logiciels libres utilisés\n\n"
          "Toutes gratuites ; aucune licence commerciale requise pour le fonctionnement de base.\n\n" + "\n".join(rows)
          + "\n\nOptionnel : PyMuPDF (AGPL-3.0, lecteur PDF alternatif, désactivé par défaut).\n\n"
            "Programmes externes facultatifs : Tesseract OCR (Apache-2.0), LanguageTool (LGPL-2.1) + Java 21 (GPL+CE), "
            "Microsoft Word / Excel / PowerPoint (licence de l'utilisateur, déjà possédée).")


def domains() -> None:
    from academic_writer.core.config import Settings
    from academic_writer.domains.registry import DomainRegistry

    registry = DomainRegistry(Settings(data_dir=Path(tempfile.mkdtemp())))
    registry.reload()
    rows = ["| Profil | Nom | Parent | Risque | Termes | Règles | Calculs | Normes | Mots-clés (fr/ru/en) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for profile in sorted(registry.all(), key=lambda p: p.id):
        raw = registry.raw(profile.id)
        keywords = "/".join(str(len(raw.keywords.get(lang, []))) for lang in ("fr", "ru", "en"))
        rows.append(f"| `{profile.id}` | {profile.names.get('fr')} | {raw.parent or '—'} | {profile.risk_level} | "
                    f"{len(raw.terminology)} | {len(raw.validation_rules)} | {len(raw.calculations)} | "
                    f"{len(raw.standards)} | {keywords} |")
    write("DOMAIN_COVERAGE.md", "# Couverture disciplinaire\n\n"
          f"{len(registry.all())} profils. Colonnes « Termes / Règles / Calculs / Normes » : éléments PROPRES au profil "
          "(hors héritage du parent). Un profil hérite de la terminologie et des règles de son parent.\n\n"
          "Opérationnel = détection par mots-clés testée, terminologie transmise au rédacteur, règles de validation "
          "et structures de documents appliquées. Les calculs listés sont des TYPES de calcul servis par les outils "
          "généraux (solve_problem, solve_math, solve_numeric), pas des bibliothèques spécialisées par métier.\n\n"
          + "\n".join(rows))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    software_catalog()
    providers()
    libraries()
    domains()
