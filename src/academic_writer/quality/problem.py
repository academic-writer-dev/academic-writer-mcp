"""Démarche de résolution en 11 étapes : données, inconnues, unités, hypothèses, méthode, formules, étapes,
calculs, vérification, interprétation, limites.

Les formules sont enchaînées dans l'ordre : chacune doit avoir exactement une inconnue à son tour. Les valeurs
viennent uniquement des données fournies et des résultats intermédiaires ; rien n'est supposé.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from academic_writer.quality import calculations as calc
from academic_writer.quality import units as U


class Step(BaseModel):
    number: int
    title: str
    status: str = Field(description="ok, attention, erreur ou à faire (par l'utilisateur).")
    content: list[str]


class ProblemSolution(BaseModel):
    unknown: str
    result_si: float | None
    unit_si: str | None
    result_in_unit: float | None = None
    target_unit: str | None = None
    result_kind: str = "calculé"
    steps: list[Step]
    verified: bool
    notice: str = ("Démarche automatique fondée sur les seules données fournies. Le choix des formules et des "
                   "hypothèses relève de l'utilisateur ou du cours ; relecture humaine indispensable.")


def si_text(value: float, dims) -> str:
    """Valeur SI relisible par l'analyseur : « 15.9 s^-1 », « 2 m^1·s^-1 »."""
    parts = [f"{name}^{exp}" for name, exp in zip(U._BASE_NAMES, dims or (), strict=False) if exp]
    return f"{value!r} {'·'.join(parts)}".strip()


def _decimals(text: str) -> int:
    match = re.search(r"\d+(?:[.,](\d+))?", text)
    return len(match.group(1) or "") if match else 0


def solve(data: dict[str, str], unknown: str, formulas: list[str], hypotheses: list[str] | None = None,
          target_unit: str | None = None, plausible_range: list[float] | None = None,
          values_as_written: bool = False) -> ProblemSolution:
    steps: list[Step] = []
    hypotheses = hypotheses or []
    # 1. Données
    quantities = {}
    lines, status = [], "ok"
    for name, text in data.items():
        try:
            q = calc.parse_quantity(text)
            quantities[name] = q
            lines.append(f"{name} = {text}" + (f"  (SI : {q.si:.6g} {U.format_dims(q.dims)})" if q.has_unit else
                                               "  (sans unité)"))
        except ValueError as exc:
            lines.append(f"{name} = {text} : illisible ({exc})")
            status = "erreur"
    steps.append(Step(number=1, title="Données", status=status if data else "erreur",
                      content=lines or ["Aucune donnée fournie."]))
    # 2. Inconnues
    steps.append(Step(number=2, title="Inconnue", status="erreur" if unknown in data else "ok",
                      content=[f"Grandeur cherchée : {unknown}"] + (["Elle figure déjà dans les données."]
                                                                    if unknown in data else [])))
    # 3. Unités
    unitless = [n for n, q in quantities.items() if not q.has_unit]
    steps.append(Step(number=3, title="Unités", status="attention" if unitless else "ok",
                      content=["Toutes les données sont converties en unités SI pour le calcul."]
                      + ([f"Sans unité (considérées sans dimension) : {', '.join(unitless)} — vérifier."] if unitless else [])))
    # 4. Hypothèses
    steps.append(Step(number=4, title="Hypothèses", status="ok" if hypotheses else "attention",
                      content=hypotheses or ["Aucune hypothèse énoncée : préciser celles du modèle (régime permanent, "
                                             "frottements négligés…)."]))
    # 5-8. Méthode, formules, étapes, calculs
    known: dict[str, str] = dict(data)
    method_lines, formula_lines, step_lines, method_warnings = [], [], [], []
    final = None
    remaining = list(formulas)
    progress = True
    while remaining and progress:
        progress = False
        for formula in list(remaining):
            try:
                result = calc.evaluate_formula(formula, {k: v for k, v in known.items()
                                                         if re.search(rf"(?<![\w]){re.escape(k)}(?![\w])", formula)})
            except ValueError:
                continue
            remaining.remove(formula)
            progress = True
            name = result.solved_for or unknown
            si_value, written = result.results_si[0], result.results_as_written[0]
            if values_as_written:
                value, unit = written, ""
                known[name] = repr(written)
            else:
                value = si_value
                unit = result.unit_si if result.unit_si and result.unit_si != "(sans dimension)" else ""
                known[name] = si_text(si_value, result.dims_si)
                if abs(si_value - written) > 1e-6 * max(abs(si_value), abs(written), 1e-12) and re.search(
                        r"\d", formula.split("=", 1)[-1]):
                    method_warnings.append(
                        f"« {formula} » : avec les nombres tels qu'écrits, {name} = {written:.6g} au lieu de {si_value:.6g} "
                        "en SI. Si la formule est écrite pour des unités particulières (ex. n en tr/min), relancer "
                        "avec values_as_written=true.")
            formula_lines.append(formula)
            method_lines.append(f"{formula} → résolue pour {name}")
            step_lines.append(f"{name} = {result.expression} = {value:.6g} {unit}".strip()
                              + (f" ; {'; '.join(result.warnings)}" if result.warnings else ""))
            if name == unknown:
                final = (value, unit, result)
    blocked = [f"« {f} » : pas exactement une inconnue avec les valeurs disponibles" for f in remaining]
    steps.append(Step(number=5, title="Méthode",
                      status="erreur" if not method_lines else "attention" if method_warnings or blocked else "ok",
                      content=(method_lines + blocked + method_warnings
                               + (["Calcul avec les nombres tels qu'écrits (formules écrites pour des unités précises)."]
                                  if values_as_written else [])) or ["Aucune formule exploitable."]))
    steps.append(Step(number=6, title="Formules", status="ok" if formula_lines else "erreur",
                      content=formula_lines or formulas))
    steps.append(Step(number=7, title="Étapes", status="ok" if step_lines else "erreur", content=step_lines))
    if final is None:
        steps.append(Step(number=8, title="Calculs", status="erreur",
                          content=[f"{unknown} n'a pas pu être calculée : données ou formules manquantes "
                                   "(elles ne seront jamais supposées)."]))
        for number, title in ((9, "Vérification"), (10, "Interprétation"), (11, "Limites")):
            steps.append(Step(number=number, title=title, status="à faire", content=["Sans objet : pas de résultat."]))
        return ProblemSolution(unknown=unknown, result_si=None, unit_si=None, steps=steps, verified=False)
    value, unit, result = final
    in_unit = None
    calc_lines = [f"{unknown} = {value:.6g} {unit}".strip()]
    if target_unit:
        try:
            factor, dims = calc.parse_target_unit(target_unit)
            q = calc.parse_quantity(f"1 {unit}") if unit else None
            if q is not None and q.dims != dims:
                calc_lines.append(f"Unité demandée « {target_unit} » incompatible avec {unit}.")
            else:
                in_unit = value / factor
                calc_lines.append(f"{unknown} = {in_unit:.6g} {target_unit}")
        except ValueError as exc:
            calc_lines.append(str(exc))
    digits = min((_decimals(t) for t in data.values()), default=2)
    calc_lines.append(f"Précision : arrondir selon les données (≈ {max(2, digits + 2)} chiffres significatifs).")
    steps.append(Step(number=8, title="Calculs", status="ok", content=calc_lines))
    # 9. Vérification : réinjection dans la dernière formule utilisée
    import sympy as sp

    check_ok = False
    try:
        last = next(f for f in reversed(formula_lines) if re.search(rf"(?<![\w]){re.escape(unknown)}(?![\w])", f))
        left, right = last.split("=")
        values = {k: (calc.parse_quantity(v).shown if values_as_written else calc.parse_quantity(v).si)
                  for k, v in known.items() if re.search(rf"(?<![\w]){re.escape(k)}(?![\w])", last)}
        symbols: dict = {}
        from academic_writer.quality import expr as E

        lhs = E.to_sympy(E.parse(left, units=False), symbols)
        rhs = E.to_sympy(E.parse(right, units=False), symbols)
        subs = {symbols[k]: v for k, v in values.items() if k in symbols}
        residual = float(abs((lhs - rhs).subs(subs).evalf()))
        scale = max(abs(float(lhs.subs(subs).evalf())), 1e-12)
        check_ok = residual <= 1e-9 * scale
        verification = [f"Réinjection dans « {last} » : écart relatif {residual / scale:.1e}."]
    except (StopIteration, ValueError, TypeError, ZeroDivisionError, sp.SympifyError) as exc:
        verification = [f"Réinjection impossible : {exc}"]
    steps.append(Step(number=9, title="Vérification", status="ok" if check_ok else "attention", content=verification))
    # 10. Interprétation (ordre de grandeur, signe)
    interpretation = []
    status = "à faire"
    if plausible_range and len(plausible_range) == 2:
        low, high = sorted(plausible_range)
        shown = in_unit if in_unit is not None else value
        inside = low <= shown <= high
        interpretation.append(f"Ordre de grandeur attendu [{low:g} ; {high:g}] : "
                              + ("résultat plausible." if inside else "résultat HORS de la plage : revoir données ou formule."))
        status = "ok" if inside else "erreur"
    if value < 0:
        interpretation.append("Résultat négatif : vérifier le sens choisi (signe) ou la convention.")
    interpretation.append("Interpréter le résultat au regard du sujet (comparaison, conformité, conséquence).")
    steps.append(Step(number=10, title="Interprétation", status=status, content=interpretation))
    # 11. Limites
    steps.append(Step(number=11, title="Limites", status="ok", content=[
        "Valable dans le cadre des hypothèses énoncées." if hypotheses else "Hypothèses non énoncées : validité inconnue.",
        "Incertitudes des données non propagées (à évaluer si les mesures sont expérimentales)."]))
    return ProblemSolution(unknown=unknown, result_si=value, unit_si=unit or None, result_in_unit=in_unit,
                           target_unit=target_unit, steps=steps, verified=check_ok)
