"""Tests de l'intelligence disciplinaire : profils, héritage, détection, gabarits, terminologie."""

from pathlib import Path

import pytest
from mcp import Client

from academic_writer.core.config import Settings
from academic_writer.core.errors import NotFoundError, ValidationFailed
from academic_writer.core.models import DocumentRole, DocumentType, Language
from academic_writer.domains.detection import TextIndex, confidence_level, parse_keyword, score_profiles
from academic_writer.domains.registry import DomainRegistry
from academic_writer.domains.structures import build_template, load_structures
from academic_writer.server.app import mcp
from academic_writer.server.services import Services

EXPECTED = {
    "generaliste", "genie_mecanique", "fabrication_mecanique", "maintenance_industrielle", "automatisation",
    "informatique", "electronique", "genie_civil", "mathematiques", "physique", "chimie", "biologie",
    "medecine", "droit", "economie", "gestion", "sciences_humaines",
    # audit E-04 : couverture disciplinaire étendue
    "pharmacie", "agriculture", "geologie", "environnement", "finance_comptabilite", "sciences_politiques",
    "psychologie", "histoire", "philosophie", "langues_linguistique", "education", "architecture", "arts", "design",
    "mode", "audiovisuel", "sport", "tourisme",
}

MECHANICS_RU = (
    "Структурный и кинематический анализ механизма. Кривошип 1, шатун 2, ползун 3, кулиса 5, стойка 6. "
    "Кинематические пары вращательные. Степень подвижности W = 3n - 2p5 = 1. Построены план скоростей "
    "и план ускорений, определено ускорение Кориолиса. Звенья механизма образуют группы Ассура. " * 3
)
MEDICAL_FR = (
    "Essai clinique randomisé contre placebo chez des patients hospitalisés. Le diagnostic médical, la "
    "posologie du médicament et les symptômes ont été suivis. La prévalence et l'incidence dans la cohorte "
    "sont rapportées ; le traitement médical a été comparé. " * 3
)


@pytest.fixture
def registry(settings: Settings) -> DomainRegistry:
    return DomainRegistry(settings)


# --- chargement et héritage -------------------------------------------------

def test_all_builtin_profiles_load(registry: DomainRegistry) -> None:
    assert registry.errors == []
    assert set(registry.ids()) == EXPECTED
    assert registry.all()[0].id == "generaliste"
    for profile in registry.all():
        assert profile.names.fr and profile.names.ru and profile.names.en
        if profile.id != "generaliste":
            assert profile.keywords, profile.id


def test_inheritance_merges_lists_but_not_keywords(registry: DomainRegistry) -> None:
    fabrication = registry.get("fabrication_mecanique")
    term_ids = {t.id for t in fabrication.terminology}
    assert {"cutting_speed", "crank", "hypothesis"} <= term_ids  # propre + parent + généraliste
    rule_ids = {r.id for r in fabrication.validation_rules}
    assert {"cutting_units", "angular_units", "si_units"} <= rule_ids
    codes = {s.code for s in fabrication.standards}
    assert {"ГОСТ 3.1102-2011", "ГОСТ 2.770-68", "ГОСТ 7.32-2017"} <= codes
    assert "кривошип*" not in fabrication.keywords.get("ru", [])  # mots-clés non hérités
    assert fabrication.methodology == registry.get("genie_mecanique").methodology  # hérité si absent


def test_high_risk_profiles_have_notices(registry: DomainRegistry) -> None:
    high = {p.id for p in registry.all() if p.risk_level == "high"}
    assert high == {"medecine", "droit", "pharmacie", "finance_comptabilite", "psychologie", "sport"}
    for profile_id in high:
        notice = registry.get(profile_id).risk_notice
        assert notice.fr and notice.ru and notice.en


def _write_user_profile(settings: Settings, name: str, content: str) -> None:
    folder = settings.data_dir / "profiles"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(content, encoding="utf-8")


def test_user_profile_child_of_high_risk_stays_high(settings: Settings) -> None:
    _write_user_profile(settings, "cardio.yaml", (
        "id: cardiologie\nparent: medecine\n"
        "names: {fr: Cardiologie, ru: Кардиология, en: Cardiology}\n"
        "keywords: {fr: [\"cardiaque*\"]}\n"))
    registry = DomainRegistry(settings)
    assert registry.errors == []
    profile = registry.get("cardiologie")
    assert profile.source == "user" and profile.risk_level == "high" and profile.risk_notice is not None


def test_user_profile_overrides_builtin(settings: Settings) -> None:
    _write_user_profile(settings, "physique.yaml", (
        "id: physique\nparent: generaliste\n"
        "names: {fr: Physique (perso), ru: Физика, en: Physics}\n"
        "keywords: {fr: [\"quark*\"]}\n"))
    profile = DomainRegistry(settings).get("physique")
    assert profile.source == "user" and profile.names.fr == "Physique (perso)"


@pytest.mark.parametrize("content, fragment", [
    ("id: x1\nnames: {fr: X, ru: Х, en: X}\nkeywordz: {}\n", "keywordz"),             # champ inconnu
    ("id: x2\nnames: {fr: X, en: X}\n", "ru"),                                       # nom russe manquant
    ("id: x3\nparent: inexistant\nnames: {fr: X, ru: Х, en: X}\n", "parent introuvable"),
    ("id: x4\nrisk_level: high\nnames: {fr: X, ru: Х, en: X}\n", "risk_notice"),     # haut risque sans avertissement
    ("id: Mauvais-Id\nnames: {fr: X, ru: Х, en: X}\n", "id"),
    ("- liste\n- au lieu d'un objet\n", "objet"),
])
def test_invalid_user_profiles_are_skipped(settings: Settings, content: str, fragment: str) -> None:
    _write_user_profile(settings, "invalide.yaml", content)
    registry = DomainRegistry(settings)
    assert len(registry.errors) == 1 and fragment in registry.errors[0]
    assert set(registry.ids()) == EXPECTED  # les profils valides restent disponibles


def test_inheritance_cycle_detected(settings: Settings) -> None:
    _write_user_profile(settings, "a.yaml", "id: cyc_a\nparent: cyc_b\nnames: {fr: A, ru: А, en: A}\n")
    _write_user_profile(settings, "b.yaml", "id: cyc_b\nparent: cyc_a\nnames: {fr: B, ru: Б, en: B}\n")
    registry = DomainRegistry(settings)
    assert any("circulaire" in e for e in registry.errors)
    with pytest.raises(NotFoundError):
        registry.get("cyc_a")


# --- détection ------------------------------------------------------------

def test_keyword_parsing_and_counting() -> None:
    assert parse_keyword("plan* de vitesse*") == [("plan", True), ("de", False), ("vitesse", True)]
    assert parse_keyword("génie-civil") == [("genie", False), ("civil", False)]
    index = TextIndex("Механизма, механизмов и МЕХАНИЗМ. План скоростей; планы скоростей. Étude, ÉTUDE.")
    assert index.count("механизм*") == 3
    assert index.count("план* скоростей") == 2
    assert index.count("etude") == 2
    assert index.count("ab*") == 0


def test_detection_mechanics_russian(registry: DomainRegistry) -> None:
    profiles = [p for p in registry.all() if p.id != "generaliste"]
    scores, words = score_profiles(MECHANICS_RU, profiles)
    assert scores[0].profile.id == "genie_mecanique"
    level, _ = confidence_level(scores, words, {p.id: p for p in registry.all()})
    assert level == "élevée"


def test_detection_medicine_french(registry: DomainRegistry) -> None:
    scores, words = score_profiles(MEDICAL_FR, [p for p in registry.all() if p.id != "generaliste"])
    assert scores[0].profile.id == "medecine"


def test_detection_short_text_is_undetermined(registry: DomainRegistry) -> None:
    scores, words = score_profiles("Bonjour à tous.", [p for p in registry.all() if p.id != "generaliste"])
    level, _ = confidence_level(scores, words, {p.id: p for p in registry.all()})
    assert level == "indéterminée"


# --- gabarits ---------------------------------------------------------------

def test_every_document_type_convention_and_profile_builds(registry: DomainRegistry) -> None:
    load_structures.cache_clear()
    for profile in registry.all():
        for document_type in DocumentType:
            for convention in ("ru", "fr", "intl"):
                for language in ("fr", "ru", "en"):
                    template = build_template(document_type, convention, profile, language)
                    assert template.sections and all(s.title for s in template.sections)
                    assert len({s.id for s in template.sections}) == len(template.sections)


def test_template_gost_master_thesis(registry: DomainRegistry) -> None:
    template = build_template(DocumentType.MEMOIRE_MASTER, "ru", registry.get("generaliste"), "ru")
    titles = [s.title for s in template.sections]
    assert "Реферат" in titles and "Список использованных источников" in titles
    assert "ГОСТ 7.32-2017" in template.base_standard
    assert any("приоритет" in n for n in template.notices)


def test_template_domain_sections_inserted(registry: DomainRegistry) -> None:
    template = build_template(DocumentType.PROJET_UNIVERSITAIRE, "fr", registry.get("genie_mecanique"), "fr")
    ids = [s.id for s in template.sections]
    assert ids.index("kinematic_diagram") == ids.index("analysis") + 1
    assert ids.index("strength_check") == ids.index("calculations") + 1
    assert next(s for s in template.sections if s.id == "kinematic_diagram").origin == "domain:genie_mecanique"
    assert "ISO 3952" in {s.code for s in template.standards}
    assert "ГОСТ 2.770-68" not in {s.code for s in template.standards}  # convention ru exclue


def test_template_high_risk_notice_first(registry: DomainRegistry) -> None:
    template = build_template(DocumentType.ARTICLE_SCIENTIFIQUE, "intl", registry.get("medecine"), "en")
    assert "medical advice" in template.notices[0]
    assert "Vancouver" in template.bibliography_styles


# --- service et outils MCP ----------------------------------------------------

def test_lookup_terminology(services: Services) -> None:
    result = services.domains.lookup_terms("кривошип")
    assert result.entries[0].domain_id == "genie_mecanique" and result.entries[0].term.fr == "manivelle"
    avoided = services.domains.lookup_terms("vitesse de rotation")
    assert any(e.term.id == "rotational_frequency" for e in avoided.entries)
    with pytest.raises(ValidationFailed):
        services.domains.lookup_terms("a")


def test_identify_and_assign_domain(services: Services, inbox: Path) -> None:
    project = services.projects.create("ДЗ1 ТММ", DocumentType.DEVOIR, Language.RU)
    path = inbox / "dz1.txt"
    path.write_text(MECHANICS_RU, encoding="utf-8")
    services.documents.import_document(project.id, str(path), DocumentRole.DRAFT)

    result = services.domains.identify(project.id)
    assert result.suggested_domain_id == "genie_mecanique"
    assert result.confidence == "élevée" and result.requires_confirmation
    assert result.analyzed_documents == 1 and result.candidates[0].matched_terms

    assignment = services.domains.assign(project.id, "genie_mecanique")
    assert assignment.project.domain_id == "genie_mecanique" and assignment.project.domain_confirmed_at
    template = services.domains.structure_template(project.id)
    assert template.convention == "ru" and template.domain_id == "genie_mecanique"
    assert any(s.id == "diagram" for s in template.sections)  # section de domaine pour les devoirs


def test_identify_without_documents_is_undetermined(services: Services) -> None:
    project = services.projects.create("Projet vide", DocumentType.RAPPORT_TECHNIQUE, Language.FR)
    result = services.domains.identify(project.id)
    assert result.confidence == "indéterminée" and result.suggested_domain_id == "generaliste"


def test_assign_high_risk_returns_warning(services: Services) -> None:
    project = services.projects.create("Étude clinique", DocumentType.ARTICLE_SCIENTIFIQUE, Language.FR)
    assignment = services.domains.assign(project.id, "medecine", convention="intl")
    assert assignment.risk_level == "high" and "avis médical" in assignment.risk_notice
    assert assignment.project.convention == "intl"


def test_assign_unknown_domain_rejected(services: Services) -> None:
    project = services.projects.create("P", DocumentType.TD, Language.EN)
    with pytest.raises(NotFoundError):
        services.domains.assign(project.id, "astrologie")


@pytest.mark.anyio
async def test_mcp_domain_tools(services: Services, inbox: Path) -> None:
    project = services.projects.create("Rapport", DocumentType.RAPPORT_MAINTENANCE, Language.FR)
    async with Client(mcp) as client:
        listed = await client.call_tool("list_domain_profiles", {"language": "ru"})
        assert listed.structured_content["count"] == len(EXPECTED)

        profile = await client.call_tool("get_domain_profile", {"domain_id": "maintenance_industrielle"})
        assert profile.structured_content["parent"] == "genie_mecanique"

        identified = await client.call_tool("identify_domain", {"project_id": project.id})
        assert identified.structured_content["requires_confirmation"] is True

        assigned = await client.call_tool("set_project_domain", {
            "project_id": project.id, "domain_id": "maintenance_industrielle"})
        assert not assigned.is_error

        template = await client.call_tool("get_document_structure_template", {"project_id": project.id})
        data = template.structured_content
        assert data["family"] == "rapport_intervention" and data["convention"] == "fr"
        assert any(s["id"] == "kpi" for s in data["sections"])

        term = await client.call_tool("lookup_terminology", {"query": "MTBF"})
        assert term.structured_content["count"] >= 1

        resource = await client.read_resource("academic-writer://domains/droit")
        assert "risk_notice" in resource.contents[0].text


@pytest.mark.parametrize(("expected", "text"), [
    ("pharmacie", "Étude de la pharmacocinétique : biodisponibilité, demi-vie et clairance du principe actif ; posologie."),
    ("geologie", "Описание месторождения: керн скважин, содержание руды, разломы и стратиграфия."),
    ("psychologie", "Participants completed a questionnaire on a Likert scale; cognitive bias and personality."),
    ("histoire", "Analyse des archives du XVIIe siècle : critique des sources primaires et historiographie du règne."),
    ("tourisme", "Анализ загрузки номерного фонда гостиницы, туроператоры и турпоток в дестинации."),
    ("finance_comptabilite", "Bilan et compte de résultat : fonds de roulement, trésorerie, amortissements, ratios financiers."),
    ("agriculture", "Урожайность пшеницы, севооборот, удобрения и полевой опыт с повторностями."),
    ("sport", "Тренировочная нагрузка, ЧСС и МПК спортсменов, выносливость."),
])
def test_extended_profiles_detected(registry: DomainRegistry, expected: str, text: str) -> None:
    """Audit E-04 : les nouvelles disciplines sont réellement détectées, pas seulement déclarées."""
    from academic_writer.domains.detection import score_profiles

    scores, _ = score_profiles(text, registry.all())
    assert scores[0].profile.id == expected


@pytest.mark.parametrize("document_type", ["expose", "presentation_orale", "etude_de_cas", "fiche_de_lecture",
                                           "synthese_bibliographique", "rapport_de_stage"])
@pytest.mark.parametrize("language", ["fr", "ru", "en"])
def test_new_document_types_have_structures(services: Services, document_type: str, language: str) -> None:
    from academic_writer.core.models import DocumentType, Language

    project = services.projects.create("Travail", DocumentType(document_type), Language(language))
    services.domains.assign(project.id, "generaliste", {"fr": "fr", "ru": "ru", "en": "intl"}[language])
    template = services.domains.structure_template(project.id)
    assert len(template.sections) >= 6 and all(s.title for s in template.sections)
