"""Outils MCP : contrôle qualité (calculs, affirmations, cohérence, structure, audit final)."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.quality import FinalAudit
from academic_writer.quality.calculations import CalculationReport, ConversionResult, FormulaResult
from academic_writer.quality.claims import ClaimsReport
from academic_writer.quality.compare import DocumentComparison
from academic_writer.quality.numeric import NumericOperation, NumericResult
from academic_writer.quality.problem import ProblemSolution
from academic_writer.quality.similarity import SimilarityReport
from academic_writer.quality.standards import StandardEntry, StandardsReport
from academic_writer.quality.consistency import ConsistencyReport
from academic_writer.quality.structure import StructureReport
from academic_writer.quality.symbolic import MatrixOperation, Operation, SymbolicResult
from academic_writer.server.services import get_services, user_errors

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)


def register(mcp: MCPServer) -> None:
    @mcp.tool(title="Vérifier les calculs", annotations=_READ)
    def validate_calculations(project_id: str | None = None, document_id: str | None = None) -> CalculationReport:
        """Recalcule les calculs écrits (« v = ω·r = 10·0,05 = 0,5 м/с ») d'un document importé (document_id) ou de
        la rédaction d'un projet (project_id) : arithmétique, arrondis, unités (SI, notations fr/ru/en), symboles
        définis puis réutilisés, symboles redéfinis avec une autre valeur. Ne juge ni les formules ni les données."""
        with user_errors():
            return get_services().quality.calculations(project_id, document_id)

    @mcp.tool(title="Calculer une formule", annotations=_READ)
    def evaluate_formula(formula: str, values: dict[str, str], target_unit: str | None = None) -> FormulaResult:
        """Calcule une formule avec les valeurs FOURNIES (jamais supposées), unités comprises.
        Exemples : formula « d = m*z », values {"m": "2 мм", "z": "20"} ; ou avec une seule inconnue
        « d = m*z », values {"d": "40 мм", "m": "2 мм"} (résolution SymPy). target_unit : « мм », « рад/с »...
        Écrire les multiplications explicitement (m*z). Fonctions : sin, cos, tg, sqrt, ln, lg, exp ; constante π."""
        with user_errors():
            return get_services().quality.evaluate_formula(formula, values, target_unit)

    @mcp.tool(title="Calcul formel", annotations=_READ)
    def solve_math(
        operation: Annotated[Operation, Field(description=(
            "simplify, expand, factor, evaluate ; derivative (variable, order) ; integral (variable, bornes "
            "lower/upper facultatives) ; limit (variable, point, direction) ; solve (équations séparées par « ; », "
            "unknowns) ; dsolve (ex. « diff(y(t), t, 2) + 4*y(t) = 0 ») ; series (point, order) ; extrema (bornes "
            "facultatives) ; matrix (matrix_operation, vector)."))],
        expression: Annotated[str, Field(description="Ex. « x^3*sin(x) », « x^2 - 5x + 6 = 0 », "
                                                     "« Matrix([[2, 1], [1, 3]]) ». Puissance : ^ ou **.")],
        variable: str | None = None,
        lower: str | None = None,
        upper: str | None = None,
        point: str | None = None,
        direction: Annotated[str, Field(description="Limite : « + », « - » ou « +- » (des deux côtés).")] = "+-",
        order: Annotated[int, Field(ge=1, le=20)] = 1,
        unknowns: list[str] | None = None,
        matrix_operation: MatrixOperation | None = None,
        vector: Annotated[list[str] | None, Field(description="Second membre b pour matrix_operation=solve_linear.")] = None,
    ) -> SymbolicResult:
        """Calcul formel exact (SymPy) : dérivées, intégrales, limites, équations et systèmes, équations
        différentielles, développements limités, extremums, matrices. Chaque résultat est VÉRIFIÉ indépendamment
        (dérivation de la primitive, réinjection des solutions, checkodesol, A·A⁻¹ = I…) ; le champ verified le dit.
        Le calcul est fait par SymPy : ne jamais l'attribuer à un autre logiciel (MATLAB, Mathematica…)."""
        with user_errors():
            return get_services().quality.solve_math(
                operation, expression, variable=variable, lower=lower, upper=upper, point=point, direction=direction,
                order=order, unknowns=unknowns, matrix_operation=matrix_operation, vector=vector)

    @mcp.tool(title="Convertir une grandeur", annotations=_READ)
    def convert_units(value: str, target_unit: str) -> ConversionResult:
        """Convertit une grandeur : « 1450 об/мин » en « рад/с », « 200 МПа » en « Н/мм2 », « 2,5 кВт·ч » en « МДж »."""
        with user_errors():
            return get_services().quality.convert(value, target_unit)

    @mcp.tool(title="Vérifier les affirmations", annotations=_READ)
    def verify_factual_claims(project_id: str | None = None, document_id: str | None = None) -> ClaimsReport:
        """Repère les affirmations factuelles (chiffres, dates, « selon X », formulations absolues, normes citées) et
        contrôle leur TRAÇABILITÉ : citation [@clé] vers une source vérifiée, chiffres retrouvés dans les documents du
        projet, édition des normes. Ne déclare jamais une affirmation vraie ou fausse."""
        with user_errors():
            return get_services().quality.claims(project_id, document_id)

    @mcp.tool(title="Vérifier la cohérence", annotations=_READ)
    def check_consistency(project_id: str | None = None, document_id: str | None = None) -> ConsistencyReport:
        """Cohérence interne : renvois aux figures / tableaux sans légende ou légendes jamais citées, numérotation,
        abréviations non définies ou définies trop tard, termes à éviter du domaine, séparateur décimal mélangé,
        symboles recevant deux valeurs différentes."""
        with user_errors():
            return get_services().quality.consistency(project_id, document_id)

    @mcp.tool(title="Vérifier la structure", annotations=_READ)
    def check_document_structure(project_id: str | None = None, document_id: str | None = None) -> StructureReport:
        """Compare la structure au gabarit du projet (type de document, convention ru/fr/intl, domaine) : sections
        obligatoires absentes, ordre, numérotation des titres, sections vides ou très courtes, [À COMPLÉTER] restants.
        Gabarit indicatif : les consignes de l'établissement priment."""
        with user_errors():
            return get_services().quality.structure(project_id, document_id)

    @mcp.tool(title="Audit qualité final",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                          open_world_hint=False))
    def final_quality_audit(project_id: str | None = None, document_id: str | None = None,
                            save_report: bool = True) -> FinalAudit:
        """Audit complet avant remise : calculs, affirmations, cohérence, structure, exigences confirmées des
        consignes, et pour un projet : sections non validées et audit des références. Verdict : bloquant /
        à corriger / prêt pour la relecture humaine (jamais « validé »). Rapport Markdown dans le dossier exports."""
        with user_errors():
            return get_services().quality.final_audit(project_id, document_id, save_report)

    @mcp.tool(title="Comparer deux documents", annotations=_READ)
    def compare_documents(document_a: str, document_b: str) -> DocumentComparison:
        """Compare deux documents d'un projet (deux versions d'un rapport, consigne et rendu, deux supports de cours) :
        similarité, titres présents d'un seul côté, passages ajoutés / supprimés / modifiés, nombres présents d'un seul
        côté, symboles définis avec des valeurs différentes. Constats seulement, aucune modification."""
        with user_errors():
            return get_services().quality.compare_documents(document_a, document_b)

    @mcp.tool(title="Similarité et citations manquantes", annotations=_READ)
    def check_similarity(project_id: str | None = None, document_id: str | None = None,
                         min_words: Annotated[int, Field(ge=5, le=30, description="Longueur minimale d'un passage "
                                                                                 "repris (mots).")] = 8) -> SimilarityReport:
        """Compare la rédaction du projet (project_id) ou un document importé (document_id) aux autres documents du
        projet : passages repris, cités ou non (citation manquante), part par source, répétitions internes,
        ruptures de style. Similarité ≠ plagiat ; reformulations non détectées ; pas de comparaison avec Internet."""
        with user_errors():
            return get_services().quality.similarity(project_id, document_id, min_words)

    @mcp.tool(title="Calcul numérique (SciPy)", annotations=_READ)
    def solve_numeric(
        operation: Annotated[NumericOperation, Field(description=(
            "minimize / maximize (expression, variables, bounds, start) ; root (expression, interval [a, b] ou start) ; "
            "integrate (expression, interval) ; ode (dérivées séparées par « ; », unknown_functions, variables=[t], "
            "interval, initial) ; fit (modèle, parameters, x_data, y_data) ; statistics / ttest / anova / correlation "
            "(samples)."))],
        expression: str | None = None,
        variables: list[str] | None = None,
        bounds: list[list[float]] | None = None,
        start: list[float] | None = None,
        interval: list[float] | None = None,
        initial: list[float] | None = None,
        unknown_functions: list[str] | None = None,
        parameters: list[str] | None = None,
        x_data: list[float] | None = None,
        y_data: list[float] | None = None,
        samples: list[list[float]] | None = None,
        points: Annotated[int, Field(ge=2, le=2000)] = 50,
    ) -> NumericResult:
        """Calcul NUMÉRIQUE par SciPy (optimisation, racines, intégrales, équations différentielles, ajustement de
        modèle, statistiques), chaque résultat contrôlé par une seconde méthode indépendante. Résultat approché ;
        result_kind distingue calculé / estimé. Aucune valeur manquante n'est supposée."""
        with user_errors():
            return get_services().quality.solve_numeric(
                operation, expression=expression, variables=variables, bounds=bounds, start=start, interval=interval,
                initial=initial, unknown_functions=unknown_functions, parameters=parameters, x_data=x_data,
                y_data=y_data, samples=samples, points=points)

    @mcp.tool(title="Résoudre un problème (démarche en 11 étapes)", annotations=_READ)
    def solve_problem(
        data: Annotated[dict[str, str], Field(description="Données avec unités, ex. {\"n\": \"1450 об/мин\", \"r\": \"50 мм\"}.")],
        unknown: str,
        formulas: Annotated[list[str], Field(description="Formules dans l'ordre d'utilisation (du cours ou de "
                                                         "l'utilisateur), ex. [\"omega = pi*n/30\", \"v = omega*r\"].")],
        hypotheses: list[str] | None = None,
        target_unit: str | None = None,
        plausible_range: Annotated[list[float] | None, Field(description="Ordre de grandeur attendu [min, max] "
                                                                         "dans l'unité cible.")] = None,
        values_as_written: Annotated[bool, Field(description="Formules écrites pour des unités précises (n en tr/min, "
                                                             "longueurs en mm…) : calculer avec les nombres tels "
                                                             "qu'écrits.")] = False,
    ) -> ProblemSolution:
        """Démarche complète en 11 étapes : données, inconnue, unités, hypothèses, méthode, formules, étapes,
        calculs, vérification (réinjection), interprétation (ordre de grandeur, signe), limites. Les formules sont
        fournies par l'utilisateur ou le cours ; rien n'est supposé ; un écart SI / « tel qu'écrit » est signalé."""
        with user_errors():
            return get_services().quality.solve_problem(data, unknown, formulas, hypotheses=hypotheses,
                                                        target_unit=target_unit, plausible_range=plausible_range,
                                                        values_as_written=values_as_written)

    @mcp.tool(title="Rechercher une norme", annotations=_READ)
    def lookup_standard(query: Annotated[str, Field(description="Code ou mot-clé : « ISO 690 », « ГОСТ 7.32 », "
                                                                "« tolérances », « sécurité des machines ».")]) -> list[StandardEntry]:
        """Catalogue vérifié de normes (ISO, IEC, IEEE, ASME, EN, ГОСТ, SI) : dernière édition connue, organisme, domaine
        et conditions d'accès (la plupart sont PAYANTES ; ГОСТ : consultation gratuite du texte officiel). Une norme
        absente n'est pas fausse : elle est hors catalogue."""
        from academic_writer.quality.standards import lookup

        return lookup(query)

    @mcp.tool(title="Contrôler les normes citées", annotations=_READ)
    def check_standards(project_id: str | None = None, document_id: str | None = None) -> StandardsReport:
        """Repère les normes citées dans la rédaction ou un document (ГОСТ, ISO, IEC, EN, DIN…) et compare leur édition
        au catalogue : à jour, édition antérieure, sans année, non vérifiée. Aucune norme n'est inventée ni corrigée."""
        with user_errors():
            return get_services().quality.check_standards(project_id, document_id)
