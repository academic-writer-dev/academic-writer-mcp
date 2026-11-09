"""Calcul formel (SymPy) : dérivées, intégrales, limites, équations, systèmes, équations différentielles,
matrices, séries, extremums — avec vérification indépendante de chaque résultat.

Sécurité : la lecture d'expressions de SymPy évalue du Python. Chaque expression est d'abord contrôlée :
caractères autorisés, aucun « __ », aucune chaîne, aucun accès à un attribut, et chaque identifiant doit être
un symbole simple (lettres, chiffres, « _ ») ou une fonction mathématique de la liste blanche. La lecture se
fait ensuite avec un espace de noms restreint, sans fonctions Python intégrées.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Operation = Literal["simplify", "expand", "factor", "evaluate", "derivative", "integral", "limit", "solve",
                    "dsolve", "series", "extrema", "matrix"]
MatrixOperation = Literal["determinant", "inverse", "eigenvalues", "rank", "transpose", "solve_linear"]

_ALLOWED_CHARS = re.compile(r"^[\w\s+\-*/^().,=\[\]<>!]*$")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan", "atan2", "acot", "sinh", "cosh", "tanh", "asinh",
    "acosh", "atanh", "exp", "log", "ln", "sqrt", "cbrt", "root", "Abs", "abs", "sign", "floor", "ceiling", "factorial",
    "binomial", "gamma", "erf", "Heaviside", "DiracDelta", "Min", "Max", "re", "im", "conjugate", "pi", "E", "I", "oo",
    "Derivative", "diff", "Eq", "Matrix", "Rational", "Sum", "Product", "Piecewise",
}
_RESERVED = {"lambda", "import", "exec", "eval", "open", "compile", "globals", "locals", "vars", "getattr", "setattr",
             "delattr", "input", "print", "type", "object", "class", "def", "for", "while", "if", "else", "in", "is",
             "not", "and", "or", "from", "as", "with", "yield", "return", "del", "pass", "raise", "try", "except",
             "finally", "global", "nonlocal", "assert", "break", "continue", "None", "True", "False"}

NOTICE = ("Calcul symbolique exact par SymPy (bibliothèque libre, licence BSD), suivi d'une vérification indépendante. "
          "Il ne valide ni la modélisation ni les hypothèses du problème : à relire.")


class SymbolicResult(BaseModel):
    operation: str
    input: str = Field(description="Expression telle que lue (forme SymPy).")
    result: str
    result_latex: str
    numeric: list[str] = Field(default_factory=list, description="Valeurs numériques approchées (15 chiffres).")
    steps: list[str] = Field(default_factory=list, description="Démarche suivie.")
    verification: str = Field(description="Contrôle indépendant du résultat.")
    verified: bool | None = Field(description="True : contrôle réussi ; None : contrôle impossible.")
    warnings: list[str] = Field(default_factory=list)
    engine: str = "SymPy"
    notice: str = NOTICE


class SymbolicError(ValueError):
    pass


def _check(text: str, what: str = "expression") -> str:
    text = (text or "").strip()
    if not text:
        raise SymbolicError(f"{what} vide.")
    if len(text) > 2000:
        raise SymbolicError(f"{what} trop longue (2000 caractères au plus).")
    if "__" in text or not _ALLOWED_CHARS.match(text):
        raise SymbolicError(f"{what} : caractères non autorisés (seuls lettres, chiffres, opérateurs et parenthèses).")
    if re.search(r"[A-Za-z_)\]]\s*\.\s*[A-Za-z_]", text):
        raise SymbolicError(f"{what} : accès à un attribut interdit.")
    for name in _IDENT.findall(text):
        if name in _RESERVED:
            raise SymbolicError(f"{what} : mot réservé interdit « {name} ».")
        if name not in _FUNCTIONS and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}", name):
            raise SymbolicError(f"{what} : identifiant non autorisé « {name} ».")
    return text.replace("^", "**")


def _namespace():
    import sympy as sp

    allowed = {name: getattr(sp, name) for name in _FUNCTIONS if hasattr(sp, name)}
    allowed.update({"ln": sp.log, "abs": sp.Abs, "diff": sp.diff})
    return {"__builtins__": {}}, allowed


def parse(text: str, what: str = "expression", extra: dict | None = None):
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    cleaned = _check(text, what)
    global_dict, local_dict = _namespace()
    local_dict.update(extra or {})
    import sympy as sp

    global_dict.update({"Symbol": sp.Symbol, "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational})
    try:
        return parse_expr(cleaned, local_dict=local_dict, global_dict=global_dict,
                          transformations=standard_transformations + (implicit_multiplication_application,
                                                                      convert_xor))
    except Exception as exc:  # erreurs de syntaxe SymPy très variées
        raise SymbolicError(f"{what} illisible : {exc}") from exc


def _equation(text: str, extra: dict | None = None):
    import sympy as sp

    if "=" in text and "==" not in text:
        left, _, right = text.partition("=")
        return sp.Eq(parse(left, extra=extra), parse(right, extra=extra))
    return parse(text, extra=extra)


def _symbol(name: str | None, expr):
    import sympy as sp

    if name:
        _check(name, "variable")
        return sp.Symbol(name.strip())
    free = sorted(expr.free_symbols, key=str)
    if len(free) == 1:
        return free[0]
    raise SymbolicError("Précisez la variable (plusieurs symboles ou aucun : " + ", ".join(map(str, free)) + ").")


def _numeric(values) -> list[str]:
    out = []
    for value in values:
        try:
            out.append(str(value.evalf(15)))
        except Exception:  # noqa: BLE001 — valeur non numérique
            continue
    return out


def _result(operation, expr, result, steps, verification, verified, warnings=None, numeric=None) -> SymbolicResult:
    import sympy as sp

    return SymbolicResult(operation=operation, input=str(expr), result=str(result), result_latex=sp.latex(result),
                          numeric=numeric if numeric is not None else (
                              _numeric([result]) if getattr(result, "is_number", False) else []),
                          steps=steps, verification=verification, verified=verified, warnings=warnings or [])


def _is_zero(expr) -> bool | None:
    import sympy as sp

    try:
        simplified = sp.simplify(expr)
        if simplified == 0:
            return True
        return None if simplified.free_symbols else bool(abs(complex(simplified.evalf())) < 1e-10)
    except Exception:  # noqa: BLE001
        return None


TIMEOUT_SECONDS = 30


def compute(operation: str, expression: str, **options) -> SymbolicResult:
    """Calcule dans un fil séparé avec une limite de temps ; toute erreur de SymPy devient une SymbolicError."""
    import threading

    outcome: dict = {}

    def run() -> None:
        try:
            outcome["result"] = _compute(operation, expression, **options)
        except SymbolicError as exc:
            outcome["error"] = exc
        except Exception as exc:  # noqa: BLE001 — SymPy lève des erreurs très variées
            outcome["error"] = SymbolicError(f"Calcul impossible ({type(exc).__name__}) : {exc}")

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(TIMEOUT_SECONDS)
    if worker.is_alive():
        raise SymbolicError(f"Calcul trop long (plus de {TIMEOUT_SECONDS} s) : simplifier l'expression ou préciser "
                            "les hypothèses.")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


def _compute(operation: str, expression: str, *, variable: str | None = None, lower: str | None = None,
            upper: str | None = None, point: str | None = None, direction: str = "+-", order: int = 1,
            unknowns: list[str] | None = None, matrix_operation: str | None = None,
            vector: list[str] | None = None) -> SymbolicResult:
    import sympy as sp

    if operation in ("simplify", "expand", "factor", "evaluate"):
        expr = parse(expression)
        result = {"simplify": sp.simplify, "expand": sp.expand, "factor": sp.factor,
                  "evaluate": lambda e: e.evalf(15)}[operation](expr)
        ok = _is_zero(expr - result)
        return _result(operation, expr, result, [f"{operation} appliqué à {expr}"],
                       "Différence entre l'entrée et le résultat simplifiée à 0." if ok else
                       "Équivalence non démontrée automatiquement.", ok)

    if operation == "derivative":
        expr = parse(expression)
        x = _symbol(variable, expr)
        result = sp.diff(expr, x, max(1, min(order, 10)))
        check = sp.integrate(result, x) if order == 1 else None
        ok = _is_zero(sp.diff(check - expr, x)) if check is not None else None
        return _result(operation, expr, result, [f"d^{order}/d{x}^{order} [{expr}]"],
                       "Primitive du résultat égale à l'expression à une constante près." if ok else
                       "Vérification par intégration non concluante (ordre > 1 ou primitive non élémentaire).", ok)

    if operation == "integral":
        expr = parse(expression)
        x = _symbol(variable, expr)
        if (lower is None) != (upper is None):
            raise SymbolicError("Indiquez les deux bornes (lower et upper) ou aucune.")
        if lower is not None:
            a, b = parse(lower, "borne inférieure"), parse(upper, "borne supérieure")
            antiderivative = sp.integrate(expr, x)
            result = sp.integrate(expr, (x, a, b))
            steps = [f"Primitive F({x}) = {antiderivative}", f"F({b}) − F({a})"]
            numeric_check = None
            try:
                quad = sp.Integral(expr, (x, a, b)).evalf(15)
                numeric_check = _is_zero(quad - result)
            except Exception:  # noqa: BLE001
                pass
            return _result(operation, expr, result, steps,
                           "Résultat exact comparé à une intégration numérique indépendante." if numeric_check else
                           "Comparaison numérique impossible ou non concluante.", numeric_check)
        result = sp.integrate(expr, x)
        if result.has(sp.Integral):
            return _result(operation, expr, result, ["Aucune primitive élémentaire trouvée."],
                           "Non vérifiable : primitive non élémentaire.", None,
                           ["SymPy ne trouve pas de primitive élémentaire."])
        ok = _is_zero(sp.diff(result, x) - expr)
        return _result(operation, expr, result, [f"Primitive de {expr} par rapport à {x} (constante C omise)"],
                       "Dérivée du résultat égale à l'intégrande." if ok else "Vérification par dérivation non concluante.",
                       ok, ["Ajouter la constante d'intégration C."])

    if operation == "limit":
        expr = parse(expression)
        x = _symbol(variable, expr)
        if point is None:
            raise SymbolicError("Indiquez le point (point), par ex. 0 ou oo.")
        p = parse(point, "point")
        result = sp.limit(expr, x, p, dir=direction if direction in ("+", "-", "+-") else "+-")
        ok = None
        if p.is_finite and result.is_finite:
            near = [expr.subs(x, p + h) for h in (sp.Rational(1, 10**6), -sp.Rational(1, 10**6))]
            try:
                ok = all(abs(complex(v.evalf()) - complex(result.evalf())) < 1e-3 * max(1, abs(complex(result.evalf())))
                         for v in (near if direction == "+-" else near[:1] if direction == "+" else near[1:]))
            except Exception:  # noqa: BLE001
                ok = None
        return _result(operation, expr, result, [f"lim {x}→{p} ({direction}) de {expr}"],
                       "Valeurs de l'expression au voisinage du point proches de la limite." if ok else
                       "Contrôle numérique au voisinage non applicable.", ok)

    if operation == "solve":
        equations = [_equation(e) for e in re.split(r";|\n", expression) if e.strip()]
        symbols = ([_symbol(u, None) for u in unknowns] if unknowns else
                   sorted(set().union(*[e.free_symbols for e in equations]), key=str))
        solutions = sp.solve(equations, symbols, dict=True)
        if not solutions:
            return _result(operation, equations, "aucune solution", ["sympy.solve"], "Aucune solution trouvée.", None,
                           ["Aucune solution (ou solution non exprimable) : vérifier l'énoncé."], numeric=[])
        checks = []
        for sol in solutions:
            for eq in equations:
                residual = (eq.lhs - eq.rhs if isinstance(eq, sp.Equality) else eq).subs(sol)
                checks.append(_is_zero(residual))
        ok = all(checks) if all(c is not None for c in checks) else None
        numeric = [", ".join(f"{k} = {v.evalf(15)}" for k, v in sol.items()) for sol in solutions]
        return _result(operation, equations, solutions, [f"Résolution de {len(equations)} équation(s) en "
                                                         f"{', '.join(map(str, symbols))}"],
                       "Chaque solution réinjectée annule toutes les équations." if ok else
                       "Réinjection non concluante pour au moins une solution.", ok,
                       ["Plusieurs solutions : retenir celle qui a un sens physique."] if len(solutions) > 1 else [],
                       numeric=numeric)

    if operation == "dsolve":
        t = sp.Symbol(variable.strip()) if variable else sp.Symbol("t")
        names = {m.group(1) for m in re.finditer(r"([A-Za-z]\w*)\s*\(\s*" + re.escape(str(t)) + r"\s*\)", expression)}
        names -= _FUNCTIONS
        if not names:
            raise SymbolicError(f"Écrivez la fonction inconnue sous la forme y({t}) et ses dérivées diff(y({t}), {t}).")
        extra = {n: sp.Function(n) for n in names}
        equations = [_equation(e, extra) for e in re.split(r";|\n", expression) if e.strip()]
        functions = [extra[n](t) for n in sorted(names)]
        result = sp.dsolve(equations[0] if len(equations) == 1 else equations,
                           functions[0] if len(functions) == 1 else functions)
        try:
            check = sp.checkodesol(equations[0] if len(equations) == 1 else equations, result)
            ok = bool(check[0]) if isinstance(check, tuple) else all(c[0] for c in check)
        except Exception:  # noqa: BLE001
            ok = None
        return _result(operation, equations, result, ["sympy.dsolve (solution générale, constantes C1, C2…)"],
                       "Solution réinjectée dans l'équation différentielle (checkodesol)." if ok else
                       "Vérification par réinjection non concluante.", ok,
                       ["Conditions initiales : les appliquer aux constantes C1, C2… avec solve."], numeric=[])

    if operation == "series":
        expr = parse(expression)
        x = _symbol(variable, expr)
        p = parse(point, "point") if point else sp.Integer(0)
        n = max(2, min(order, 20))
        result = sp.series(expr, x, p, n)
        poly = result.removeO()
        ok = None
        try:
            h = p + sp.Rational(1, 100)
            ok = abs(complex((expr - poly).subs(x, h).evalf())) < 1e-2 ** (n - 1) * 10
        except Exception:  # noqa: BLE001
            pass
        return _result(operation, expr, result, [f"Développement limité de {expr} en {x} = {p} à l'ordre {n - 1}"],
                       "Écart avec la fonction négligeable près du point." if ok else "Contrôle numérique non concluant.",
                       ok)

    if operation == "extrema":
        expr = parse(expression)
        x = _symbol(variable, expr)
        derivative = sp.diff(expr, x)
        critical = [c for c in sp.solve(sp.Eq(derivative, 0), x) if c.is_real is not False]
        second = sp.diff(expr, x, 2)
        lines, details = [f"f'({x}) = {derivative}", f"f''({x}) = {second}"], []
        a = parse(lower, "borne inférieure") if lower else None
        b = parse(upper, "borne supérieure") if upper else None
        candidates = [c for c in critical if (a is None or c >= a) and (b is None or c <= b)]
        for c in candidates:
            curvature = second.subs(x, c)
            kind = ("minimum local" if curvature.is_positive else "maximum local" if curvature.is_negative
                    else "point critique (test de la dérivée seconde non concluant)")
            details.append(f"{x} = {c} : {kind}, f = {sp.simplify(expr.subs(x, c))}")
        for bound in (a, b):
            if bound is not None:
                details.append(f"borne {x} = {bound} : f = {sp.simplify(expr.subs(x, bound))}")
        ok = all(_is_zero(derivative.subs(x, c)) for c in candidates) if candidates else None
        return _result(operation, expr, "; ".join(details) or "aucun point critique", lines,
                       "f' s'annule en chaque point critique retenu." if ok else "Aucun point critique à vérifier.", ok,
                       numeric=_numeric([expr.subs(x, c) for c in candidates]))

    if operation == "matrix":
        matrix = parse(expression, "matrice")
        if not isinstance(matrix, sp.MatrixBase):
            raise SymbolicError("Écrivez la matrice sous la forme Matrix([[1, 2], [3, 4]]).")
        op = matrix_operation or "determinant"
        if op == "determinant":
            result = matrix.det()
            ok = _is_zero(result - matrix.det(method="berkowitz"))
            text = "Déterminant recalculé par une seconde méthode (Berkowitz)."
        elif op == "inverse":
            if matrix.det() == 0:
                raise SymbolicError("Matrice singulière (déterminant nul) : pas d'inverse.")
            result = matrix.inv()
            ok = (matrix * result - sp.eye(matrix.rows)).applyfunc(sp.simplify) == sp.zeros(matrix.rows)
            text = "A·A⁻¹ = I vérifié."
        elif op == "eigenvalues":
            result = matrix.eigenvals()
            ok = all(_is_zero((matrix - v * sp.eye(matrix.rows)).det()) for v in result)
            text = "det(A − λI) = 0 pour chaque valeur propre."
        elif op == "rank":
            result, ok, text = matrix.rank(), None, "Rang (pas de contrôle indépendant)."
        elif op == "transpose":
            result, ok, text = matrix.T, matrix.T.T == matrix, "(Aᵀ)ᵀ = A."
        elif op == "solve_linear":
            if not vector:
                raise SymbolicError("Indiquez le second membre (vector).")
            b_vec = sp.Matrix([parse(v, "second membre") for v in vector])
            result = matrix.LUsolve(b_vec)
            ok = (matrix * result - b_vec).applyfunc(sp.simplify) == sp.zeros(matrix.rows, 1)
            text = "A·x = b vérifié."
        else:
            raise SymbolicError(f"Opération matricielle inconnue : {op}.")
        return _result(f"matrix:{op}", matrix, result, [f"{op} de la matrice {matrix.shape[0]}×{matrix.shape[1]}"],
                       text, ok, numeric=[])

    raise SymbolicError(f"Opération inconnue : {operation}.")
