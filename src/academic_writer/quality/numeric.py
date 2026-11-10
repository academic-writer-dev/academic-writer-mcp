"""Calcul numérique (SciPy, licence BSD) : optimisation, racines, intégration, équations différentielles,
ajustement de modèle, statistiques. Chaque résultat est accompagné d'un contrôle indépendant.

Les expressions passent par la lecture sûre du module de calcul formel (liste blanche, aucun code Python
arbitraire). Les résultats sont NUMÉRIQUES (approchés) : leur précision est indiquée.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.quality.symbolic import SymbolicError, parse

NumericOperation = Literal["minimize", "maximize", "root", "integrate", "ode", "fit", "statistics", "ttest", "anova",
                           "correlation"]
NOTICE = ("Calcul NUMÉRIQUE par SciPy (résultat approché, précision indiquée), contrôlé par une méthode indépendante. "
          "Il ne valide ni le modèle ni les données : à relire.")


class NumericResult(BaseModel):
    operation: str
    method: str
    result: dict
    table: list[dict] = Field(default_factory=list, description="Points calculés (équations différentielles).")
    verification: str
    verified: bool | None
    warnings: list[str] = Field(default_factory=list)
    result_kind: str = Field(default="calculé (numérique)", description="calculé, estimé (ajustement / statistique).")
    engine: str = "SciPy"
    notice: str = NOTICE


class NumericError(ValueError):
    pass


def _function(expression: str, variables: list[str]):
    import sympy as sp

    try:
        expr = parse(expression, "fonction")
    except SymbolicError as exc:
        raise NumericError(str(exc)) from exc
    symbols = [sp.Symbol(v) for v in variables]
    unknown = sorted(str(s) for s in expr.free_symbols if s not in symbols)
    if unknown:
        raise NumericError(f"Symboles sans valeur : {', '.join(unknown)} (fournir leur valeur ; rien n'est supposé).")
    return sp.lambdify(symbols, expr, "numpy"), expr


def _floats(values: list, label: str) -> list[float]:
    try:
        result = [float(str(v).replace(",", ".")) for v in values]
    except ValueError as exc:
        raise NumericError(f"{label} : valeur non numérique.") from exc
    if not result or not all(math.isfinite(v) for v in result):
        raise NumericError(f"{label} : valeurs absentes ou non finies.")
    return result


def compute(operation: str, *, expression: str | None = None, variables: list[str] | None = None,
            bounds: list[list[float]] | None = None, start: list[float] | None = None,
            interval: list[float] | None = None, initial: list[float] | None = None,
            unknown_functions: list[str] | None = None, parameters: list[str] | None = None,
            x_data: list | None = None, y_data: list | None = None, samples: list[list] | None = None,
            points: int = 50) -> NumericResult:
    import numpy as np
    from scipy import integrate, optimize, stats

    variables = variables or ["x"]
    if operation in ("minimize", "maximize"):
        f, expr = _function(expression or "", variables)
        sign = 1 if operation == "minimize" else -1

        def objective(v):
            return sign * float(f(*v))
        x0 = start or [0.0] * len(variables)
        if bounds and len(bounds) != len(variables):
            raise NumericError("Une borne [min, max] par variable.")
        first = optimize.minimize(objective, x0, bounds=bounds, method="L-BFGS-B" if bounds else "BFGS")
        second = optimize.minimize(objective, x0, bounds=bounds, method="Powell")
        best = first if first.fun <= second.fun else second
        agree = bool(np.allclose(first.x, second.x, rtol=1e-3, atol=1e-6))
        warnings = [] if first.success else [f"Convergence incomplète : {first.message}"]
        if not bounds:
            warnings.append("Optimum LOCAL depuis le point de départ ; d'autres optimums peuvent exister.")
        return NumericResult(operation=operation, method="L-BFGS-B / BFGS, contrôle Powell",
                             result={"point": dict(zip(variables, map(float, best.x), strict=True)),
                                     "value": float(sign * best.fun), "expression": str(expr)},
                             verification="Deux méthodes indépendantes (gradient, Powell) "
                                          + ("concordent." if agree else "divergent : optimum à examiner."),
                             verified=agree, warnings=warnings)
    if operation == "root":
        f, expr = _function(expression or "", variables)
        if len(variables) == 1 and interval:
            a, b = interval
            fa, fb = float(f(a)), float(f(b))
            if fa * fb > 0:
                raise NumericError("f(a) et f(b) de même signe : aucune racine garantie dans l'intervalle.")
            root = optimize.brentq(lambda x: float(f(x)), a, b, xtol=1e-12)
            residual = abs(float(f(root)))
            return NumericResult(operation=operation, method="Brent (intervalle encadrant)",
                                 result={variables[0]: root, "f(root)": residual, "expression": str(expr)},
                                 verification=f"Résidu |f(x)| = {residual:.2e}.", verified=residual < 1e-8)
        x0 = start or [1.0] * len(variables)
        solution = optimize.root(lambda v: [float(f(*v))] + [0.0] * (len(v) - 1), x0)
        residual = abs(float(f(*solution.x)))
        return NumericResult(operation=operation, method="scipy.optimize.root (hybride)",
                             result={**dict(zip(variables, map(float, solution.x), strict=True)), "f(root)": residual},
                             verification=f"Résidu |f(x)| = {residual:.2e}.", verified=residual < 1e-8,
                             warnings=["Racine trouvée près du point de départ ; d'autres racines peuvent exister."])
    if operation == "integrate":
        f, expr = _function(expression or "", variables[:1])
        if not interval or len(interval) != 2:
            raise NumericError("Intégration : interval = [a, b].")
        value, error = integrate.quad(lambda x: float(f(x)), *interval, limit=200)
        xs = np.linspace(interval[0], interval[1], 20001)
        check = float(integrate.simpson(np.asarray(f(xs), dtype=float) * np.ones_like(xs), x=xs))
        agree = abs(check - value) <= max(1e-6, 1e-6 * abs(value)) * 100
        return NumericResult(operation=operation, method="QUADPACK (quad), contrôle Simpson",
                             result={"value": value, "estimated_error": error, "expression": str(expr)},
                             verification=f"Méthode de Simpson : {check:.10g}" + (" (concordant)." if agree else
                                                                                   " (écart : intégrande à examiner)."),
                             verified=agree)
    if operation == "ode":
        names = unknown_functions or ["y"]
        t = variables[0] if variables else "t"
        if not expression or not interval or not initial or len(initial) != len(names):
            raise NumericError("Équation différentielle : expression (dérivées séparées par « ; »), interval [t0, t1], "
                               "initial (une valeur par fonction).")
        parts = [p.strip() for p in expression.split(";") if p.strip()]
        if len(parts) != len(names):
            raise NumericError("Une expression de dérivée par fonction inconnue (ex. « v ; -k*x/m » pour x, v).")
        functions = [_function(p, [t, *names])[0] for p in parts]

        def rhs(time, y):
            return [float(fn(time, *y)) for fn in functions]
        grid = np.linspace(interval[0], interval[1], max(2, min(points, 2000)))
        fine = integrate.solve_ivp(rhs, interval, initial, method="RK45", t_eval=grid, rtol=1e-9, atol=1e-12)
        check = integrate.solve_ivp(rhs, interval, initial, method="Radau", t_eval=grid, rtol=1e-9, atol=1e-12)
        if not fine.success:
            raise NumericError(f"Intégration impossible : {fine.message}")
        gap = float(np.max(np.abs(fine.y - check.y))) if check.success else float("nan")
        scale = float(np.max(np.abs(fine.y))) or 1.0
        table = [{t: float(fine.t[i]), **{n: float(fine.y[k][i]) for k, n in enumerate(names)}}
                 for i in range(len(fine.t))]
        return NumericResult(operation=operation, method="Runge-Kutta 4(5), contrôle Radau (implicite)",
                             result={"final": table[-1], "points": len(table)}, table=table,
                             verification=f"Écart maximal entre les deux méthodes : {gap:.2e}.",
                             verified=bool(gap <= 1e-5 * scale) if math.isfinite(gap) else None)
    if operation == "fit":
        names = parameters or []
        if not names:
            raise NumericError("Ajustement : indiquer les paramètres du modèle (ex. [\"a\", \"b\"]).")
        f, expr = _function(expression or "", [variables[0], *names])
        xs, ys = np.array(_floats(x_data or [], "x_data")), np.array(_floats(y_data or [], "y_data"))
        if len(xs) != len(ys) or len(xs) <= len(names):
            raise NumericError("Données : autant de x que de y, et plus de points que de paramètres.")
        values, covariance = optimize.curve_fit(lambda x, *p: np.asarray(f(x, *p), dtype=float) * np.ones_like(x), xs, ys,
                                                p0=start or [1.0] * len(names), maxfev=20000)
        predicted = np.asarray(f(xs, *values), dtype=float) * np.ones_like(xs)
        residual = float(np.sum((ys - predicted) ** 2))
        total = float(np.sum((ys - ys.mean()) ** 2)) or 1.0
        errors = np.sqrt(np.diag(covariance)) if np.all(np.isfinite(covariance)) else [float("nan")] * len(names)
        return NumericResult(operation=operation, method="Moindres carrés non linéaires (curve_fit)",
                             result={"parameters": {n: float(v) for n, v in zip(names, values, strict=True)},
                                     "standard_errors": {n: float(e) for n, e in zip(names, errors, strict=True)},
                                     "r_squared": 1 - residual / total, "expression": str(expr)},
                             verification=f"Somme des carrés des résidus : {residual:.4g} ; R² recalculé sur les données.",
                             verified=True, result_kind="estimé (ajustement aux données)",
                             warnings=["R² élevé ≠ modèle juste : examiner les résidus et le sens physique."])
    if operation in ("statistics", "ttest", "anova", "correlation"):
        groups = [_floats(s, f"échantillon {i + 1}") for i, s in enumerate(samples or [])]
        if not groups:
            raise NumericError("Indiquer au moins un échantillon (samples).")
        if operation == "statistics":
            data = np.array(groups[0])
            mean, sd = float(data.mean()), float(data.std(ddof=1)) if len(data) > 1 else 0.0
            ci = stats.t.interval(0.95, len(data) - 1, loc=mean, scale=sd / math.sqrt(len(data))) if len(data) > 1 else (mean, mean)
            return NumericResult(operation=operation, method="Statistiques descriptives (écart-type n-1, IC Student 95 %)",
                                 result={"n": len(data), "mean": mean, "std": sd, "min": float(data.min()),
                                         "max": float(data.max()), "median": float(np.median(data)),
                                         "ci95": [float(ci[0]), float(ci[1])]},
                                 verification="Moyenne recalculée par somme directe : "
                                              f"{sum(groups[0]) / len(groups[0]):.10g}.",
                                 verified=abs(sum(groups[0]) / len(groups[0]) - mean) < 1e-9 * max(1, abs(mean)),
                                 result_kind="estimé (statistique)")
        if operation == "ttest":
            if len(groups) != 2:
                raise NumericError("Test t : deux échantillons.")
            welch = stats.ttest_ind(groups[0], groups[1], equal_var=False)
            mann = stats.mannwhitneyu(groups[0], groups[1])
            return NumericResult(operation=operation, method="Test t de Welch ; contrôle Mann-Whitney (non paramétrique)",
                                 result={"t": float(welch.statistic), "p_value": float(welch.pvalue),
                                         "mann_whitney_p": float(mann.pvalue)},
                                 verification="Les deux tests " + ("concordent" if (welch.pvalue < 0.05) == (mann.pvalue < 0.05)
                                                                   else "divergent") + " au seuil de 5 %.",
                                 verified=(welch.pvalue < 0.05) == (mann.pvalue < 0.05), result_kind="estimé (statistique)",
                                 warnings=["p < 0,05 ne prouve pas l'effet ; vérifier les conditions (indépendance, taille)."])
        if operation == "anova":
            if len(groups) < 2:
                raise NumericError("ANOVA : au moins deux groupes.")
            anova = stats.f_oneway(*groups)
            kruskal = stats.kruskal(*groups)
            return NumericResult(operation=operation, method="ANOVA à un facteur ; contrôle Kruskal-Wallis",
                                 result={"F": float(anova.statistic), "p_value": float(anova.pvalue),
                                         "kruskal_p": float(kruskal.pvalue)},
                                 verification="Contrôle non paramétrique effectué.",
                                 verified=(anova.pvalue < 0.05) == (kruskal.pvalue < 0.05),
                                 result_kind="estimé (statistique)")
        if len(groups) != 2 or len(groups[0]) != len(groups[1]):
            raise NumericError("Corrélation : deux échantillons de même longueur.")
        pearson = stats.pearsonr(groups[0], groups[1])
        spearman = stats.spearmanr(groups[0], groups[1])
        return NumericResult(operation=operation, method="Pearson ; contrôle Spearman (rangs)",
                             result={"pearson_r": float(pearson.statistic), "p_value": float(pearson.pvalue),
                                     "spearman_rho": float(spearman.statistic)},
                             verification="Coefficients de Pearson et Spearman comparés.",
                             verified=abs(float(pearson.statistic) - float(spearman.statistic)) < 0.2,
                             result_kind="estimé (statistique)",
                             warnings=["Corrélation ≠ causalité."])
    raise NumericError(f"Opération inconnue : {operation}.")
