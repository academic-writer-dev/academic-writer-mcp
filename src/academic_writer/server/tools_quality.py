"""Outils MCP : contrôle qualité (calculs, affirmations, cohérence, structure, audit final)."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from academic_writer.core.quality import FinalAudit
from academic_writer.quality.calculations import CalculationReport, ConversionResult, FormulaResult
from academic_writer.quality.claims import ClaimsReport
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
