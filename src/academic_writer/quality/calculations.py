"""Vérification des calculs écrits : chaînes « v = ω·r = 10 · 0,05 = 0,5 м/с ».

- chaque membre numérique est recalculé (valeurs SI et nombres tels qu'écrits) ;
- les symboles définis dans le texte (« m = 2 мм », ou résultat d'un calcul) sont substitués dans les
  formules littérales qui suivent ;
- tolérance d'arrondi déduite du nombre de décimales affiché ;
- unités : contrôle dimensionnel quand les deux membres en portent.

Ne juge ni le choix des formules ni les données : seulement l'arithmétique et les unités écrites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from academic_writer.quality import expr as E
from academic_writer.quality import units as U
from academic_writer.quality.models import QualityIssue, Segment, excerpt

CalcStatus = Literal["ok", "rounding", "mismatch", "unit_mismatch"]
NOTICE = ("Contrôle de l'arithmétique et des unités écrites. Ne valide ni le choix des formules, ni les données "
          "d'entrée, ni l'interprétation : relecture humaine indispensable.")

_RELATION = re.compile(r"\s*(=|≈|≅)\s*")
_PIECE_SPLIT = re.compile(r"\n|;\s|,\s+(?=[^\d\s])|(?<=[^\d\s][.!?])\s+(?=[A-ZА-ЯЁ])")
_FIRST_NUMBER = re.compile(r"\d+(?:\.(\d+))?")
_SYMBOL = re.compile(r"^(?:[A-Za-zА-Яа-яЁё]{1,2}|[α-ωΑ-ΩΔ][\w']*|[A-Za-zА-Яа-яЁё]{1,3}[\d_'][\w']*|[A-Za-z]\w{0,2}_\w+)$")
_STRIP_TRAIL = ",.;:)»\"'"
_STRIP_LEAD = "(«\"':"


class CalcCheck(BaseModel):
    location: str | None
    expression: str = Field(description="Calcul tel qu'il apparaît dans le texte.")
    status: CalcStatus
    left: str
    right: str
    computed: str = Field(description="Valeur recalculée du membre de gauche.")
    stated: str = Field(description="Valeur du membre de droite.")
    message: str


class Definition(BaseModel):
    symbol: str
    value: str = Field(description="Valeur telle qu'écrite.")
    si_value: float
    unit_si: str | None
    location: str | None


class CalculationReport(BaseModel):
    label: str
    calculations_checked: int
    ok: int
    rounding: int
    mismatches: int
    unit_mismatches: int
    checks: list[CalcCheck] = Field(description="Écarts d'abord ; les calculs justes sont résumés au-delà de 40.")
    definitions: list[Definition]
    conflicts: list[QualityIssue]
    decimal_separators: dict[str, int] = Field(default_factory=dict)
    notice: str = NOTICE


@dataclass
class _Seg:
    text: str
    node: E.Node
    value: E.Value | None


def _symbol_like(name: str, known: dict) -> bool:
    return name in known or bool(_SYMBOL.match(name))


def _accept(text: str, known: dict[str, E.Variable]) -> _Seg | None:
    """Membre de calcul acceptable : numérique, ou littéral dont les symboles ressemblent à des symboles."""
    text = text.strip()
    if not text or not any(c.isalnum() for c in text):
        return None
    try:
        node = E.parse(text, units=True)
        return _Seg(text, node, E.evaluate(node))
    except E.Unresolved:
        pass
    except (E.ParseError, ArithmeticError, ValueError, OverflowError):
        return None
    try:
        node = E.parse(text, units=False)
    except E.ParseError:
        return None
    names = E.variables_of(node)
    if not names or not all(_symbol_like(n, known) for n in names):
        return None
    try:
        return _Seg(text, node, E.evaluate(node, known))
    except E.Unresolved:
        return _Seg(text, node, None)
    except (ArithmeticError, ValueError, OverflowError):
        return None


def _balanced(text: str) -> bool:
    return text.count("(") == text.count(")")


def _first_member(text: str, known) -> _Seg | None:
    tokens = text.split()
    best = None
    for k in range(1, min(len(tokens), 10) + 1):
        candidate = " ".join(tokens[-k:]).lstrip(_STRIP_LEAD)
        if not _balanced(candidate):
            continue
        seg = _accept(candidate, known)
        if seg:
            best = seg
    return best


def _last_member(text: str, known) -> _Seg | None:
    tokens = text.split()
    for k in range(min(len(tokens), 12), 0, -1):
        candidate = " ".join(tokens[:k]).rstrip(_STRIP_TRAIL)
        while candidate.endswith(")") and not _balanced(candidate):
            candidate = candidate[:-1].rstrip(_STRIP_TRAIL)
        if not _balanced(candidate):
            continue
        seg = _accept(candidate, known)
        if seg:
            return seg
    return None


def _decimals_scale(seg: _Seg) -> tuple[int, float] | None:
    if not E.is_literal(seg.node):
        return None
    normalized = E.normalize(seg.text)
    match = _FIRST_NUMBER.search(normalized)
    if not match:
        return None
    decimals = len(match.group(1) or "")
    node = seg.node.args[0] if seg.node.kind == "unit" else seg.node
    scale = 1.0
    if node.kind == "bin":
        try:
            scale = E.evaluate(node.args[1]).shown
        except (E.Unresolved, ArithmeticError, ValueError):
            scale = 1.0
    return decimals, scale


def _close(x: float, y: float, tol: float) -> bool:
    return abs(x - y) <= tol * 1.000001 + 1e-12 * max(abs(x), abs(y))


def _rel(x: float, y: float) -> float:
    scale = max(abs(x), abs(y))
    return abs(x - y) / scale if scale else 0.0


def _fmt(value: E.Value) -> str:
    text = f"{value.shown:.6g}"
    if value.has_unit and value.dims != U.ZERO:
        text += f" (SI : {value.si:.6g} {U.format_dims(value.dims)})"
    return text


def compare(a: _Seg, b: _Seg, approx: bool) -> tuple[CalcStatus, str]:
    va, vb = a.value, b.value
    assert va is not None and vb is not None
    shape = _decimals_scale(b) or _decimals_scale(a)
    if shape:
        decimals, scale = shape
        tol_shown = 0.5 * 10 ** (-decimals) * abs(scale)
    else:
        tol_shown = 1e-6 * max(abs(va.shown), abs(vb.shown))
    ratio = (vb.si / vb.shown) if vb.shown else 1.0
    tol_si = abs(tol_shown * ratio) if shape else 1e-6 * max(abs(va.si), abs(vb.si))
    limit = 0.02
    if va.has_unit and vb.has_unit:
        if _close(va.si, vb.si, tol_si) or (approx and _rel(va.si, vb.si) <= 0.01):
            if va.dims != vb.dims:
                return "unit_mismatch", (f"Valeurs concordantes mais unités différentes : {U.format_dims(va.dims)} "
                                         f"à gauche, {U.format_dims(vb.dims)} à droite (unité omise ou erronée ?).")
            return "ok", "Calcul exact à la précision affichée."
        if _close(va.shown, vb.shown, tol_shown):
            return "unit_mismatch", ("Les nombres concordent mais pas les unités : facteur d'échelle oublié "
                                     "(mm / m, кН / Н, об/мин / рад/с ?).")
        if _rel(va.si, vb.si) <= limit:
            return "rounding", f"Écart de {_rel(va.si, vb.si):.2%} : arrondi d'une valeur intermédiaire ?"
        return "mismatch", f"Écart de {_rel(va.si, vb.si):.1%} entre les deux membres."
    if _close(va.shown, vb.shown, tol_shown) or _close(va.si, vb.si, tol_si):
        return "ok", "Calcul exact à la précision affichée."
    if approx and min(_rel(va.shown, vb.shown), _rel(va.si, vb.si)) <= 0.01:
        return "ok", "Valeur approchée (≈) dans la tolérance de 1 %."
    best = min(_rel(va.shown, vb.shown), _rel(va.si, vb.si))
    if best <= limit:
        return "rounding", f"Écart de {best:.2%} : arrondi d'une valeur intermédiaire ?"
    return "mismatch", f"Écart de {best:.1%} entre les deux membres."


def _pieces(text: str) -> list[str]:
    return [p for p in _PIECE_SPLIT.split(text) if p and ("=" in p or "≈" in p or "≅" in p)]


def check_calculations(label: str, segments: list[Segment]) -> CalculationReport:
    known: dict[str, E.Variable] = {}
    definitions: list[Definition] = []
    first_definition: dict[str, tuple[E.Variable, Definition]] = {}
    conflicts: list[QualityIssue] = []
    checks: list[CalcCheck] = []
    separators = {"virgule": 0, "point": 0}
    for segment in segments:
        if segment.kind == "heading":
            continue
        for piece in _pieces(segment.text):
            parts = _RELATION.split(piece)
            members, relations = parts[0::2], parts[1::2]
            chain: list[_Seg | None] = [_first_member(members[0], known)]
            for middle in members[1:-1]:
                chain.append(_accept(middle.strip().rstrip(_STRIP_TRAIL), known) if _balanced(middle) else None)
            chain.append(_last_member(members[-1], known) if len(members) > 1 else None)
            for seg in chain:
                if seg and seg.value is not None and not E.variables_of(seg.node):
                    for match in re.finditer(r"\d[.,]\d", seg.text):
                        separators["virgule" if "," in match.group(0) else "point"] += 1
            # comparaisons des membres consécutifs évaluables (une rupture de chaîne interrompt la comparaison)
            previous: _Seg | None = None
            for index, seg in enumerate(chain):
                if seg is None:
                    previous = None
                    continue
                if seg.value is None or (index == 0 and seg.node.kind == "var"):
                    continue  # symbole défini par la chaîne : « m = 3 мм » est une (re)définition, pas un calcul
                if previous is not None:
                    approx = relations[index - 1] != "=" if index - 1 < len(relations) else False
                    status, message = compare(previous, seg, approx)
                    checks.append(CalcCheck(location=segment.location, expression=excerpt(piece, 260),
                                            status=status, left=previous.text, right=seg.text,
                                            computed=_fmt(previous.value), stated=_fmt(seg.value), message=message))
                previous = seg
            # définition : « m = 2 мм », ou résultat « d = m·z = 40 мм »
            head, tail = chain[0], chain[-1]
            if (head and head.node.kind == "var" and tail and tail is not head and tail.value is not None
                    and not E.variables_of(tail.node)):
                symbol, value = head.node.text, tail.value
                variable = E.Variable(value.si, value.shown, value.dims, value.has_unit)
                definition = Definition(symbol=symbol, value=tail.text, si_value=value.si,
                                        unit_si=U.format_dims(value.dims) if value.has_unit else None,
                                        location=segment.location)
                if symbol in first_definition:
                    old_var, old_def = first_definition[symbol]
                    same = _rel(old_var.si, variable.si) <= 0.02 or _rel(old_var.shown, variable.shown) <= 0.02
                    if not same:
                        conflicts.append(QualityIssue(
                            category="coherence", code="symbol_redefined", severity="warning",
                            message=(f"Le symbole {symbol} reçoit deux valeurs différentes : {old_def.value} "
                                     f"({old_def.location or 'début'}) puis {tail.text} ({segment.location or '?'})."),
                            location=segment.location, excerpt=excerpt(piece),
                            suggestion="Vérifier s'il s'agit de la même grandeur ; sinon, utiliser un indice distinct."))
                else:
                    first_definition[symbol] = (variable, definition)
                known[symbol] = variable
                definitions.append(definition)
    order = {"mismatch": 0, "unit_mismatch": 1, "rounding": 2, "ok": 3}
    counts = {status: sum(1 for c in checks if c.status == status) for status in order}
    shown = sorted(checks, key=lambda c: order[c.status])
    problems = [c for c in shown if c.status != "ok"]
    shown = problems + [c for c in shown if c.status == "ok"][: max(0, 40 - len(problems))]
    return CalculationReport(label=label, calculations_checked=len(checks), ok=counts["ok"],
                             rounding=counts["rounding"], mismatches=counts["mismatch"],
                             unit_mismatches=counts["unit_mismatch"], checks=shown, definitions=definitions[:200],
                             conflicts=conflicts, decimal_separators={k: v for k, v in separators.items() if v})


def calculation_issues(report: CalculationReport) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for check in report.checks:
        if check.status == "ok":
            continue
        severity = "error" if check.status == "mismatch" else "warning"
        issues.append(QualityIssue(
            category="calculs", code=check.status, severity=severity,
            message=f"{check.left} = {check.right} : {check.message} (recalculé : {check.computed})",
            location=check.location, excerpt=check.expression,
            suggestion="Refaire le calcul à partir des données ; ne pas corriger le résultat sans revoir la démarche."))
    return issues + report.conflicts


# --- formules à la demande ------------------------------------------------------------------

class FormulaResult(BaseModel):
    formula: str
    solved_for: str | None
    expression: str = Field(description="Expression évaluée (après résolution éventuelle).")
    values_used: dict[str, str]
    results_si: list[float]
    unit_si: str | None
    results_as_written: list[float] = Field(
        description="Résultat avec les nombres tels que donnés (unités ignorées) : utile quand la formule est écrite "
                    "pour des unités précises (n en об/мин, longueurs en мм...).")
    target_unit: str | None = None
    results_in_target: list[float] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notice: str = "Calcul fait avec les seules valeurs fournies : aucune donnée n'est supposée ni inventée."


class ConversionResult(BaseModel):
    value: str
    si_value: float
    unit_si: str
    target_unit: str
    converted: float


def parse_quantity(text: str) -> E.Value:
    try:
        node = E.parse(text, units=True)
        return E.evaluate(node)
    except E.Unresolved as exc:
        raise ValueError(f"« {text} » : unité ou symbole inconnu ({exc})") from exc
    except (E.ParseError, ArithmeticError) as exc:
        raise ValueError(f"« {text} » illisible : {exc}") from exc


def parse_target_unit(text: str) -> tuple[float, U.Dims]:
    cleaned = E.normalize(text.strip())
    parsed = U.parse_unit(cleaned)
    if not parsed or parsed[2] != len(cleaned):
        raise ValueError(f"Unité cible inconnue : « {text} »")
    return parsed[0], parsed[1]


def convert(value: str, target_unit: str) -> ConversionResult:
    quantity = parse_quantity(value)
    factor, dims = parse_target_unit(target_unit)
    if quantity.dims != dims:
        raise ValueError(f"Conversion impossible : {U.format_dims(quantity.dims)} vers {U.format_dims(dims)}.")
    return ConversionResult(value=value, si_value=quantity.si, unit_si=U.format_dims(quantity.dims),
                            target_unit=target_unit, converted=quantity.si / factor)


def _dims_of(expr, dims: dict, warnings: list[str]) -> U.Dims:
    import sympy as sp

    if expr.is_Symbol:
        return dims.get(expr, U.ZERO)
    if expr.is_Number or expr in (sp.pi, sp.E):
        return U.ZERO
    if expr.is_Mul:
        total = U.ZERO
        for arg in expr.args:
            total = U.mul(total, _dims_of(arg, dims, warnings))
        return total
    if expr.is_Pow:
        base, exponent = expr.args
        base_dims = _dims_of(base, dims, warnings)
        if exponent.is_Rational:
            scaled = [d * exponent for d in base_dims]
            if all(x.is_integer for x in scaled):
                return tuple(int(x) for x in scaled)  # type: ignore[return-value]
        if base_dims != U.ZERO:
            warnings.append("Puissance non entière d'une grandeur dimensionnée : unité du résultat non déterminée.")
        return U.ZERO
    if expr.is_Add:
        found = [_dims_of(arg, dims, warnings) for arg in expr.args]
        if len(set(found)) > 1:
            warnings.append("Somme de termes de dimensions différentes : vérifier la formule et les unités.")
        return found[0]
    return U.ZERO  # fonctions (sin, log...) : sans dimension


def evaluate_formula(formula: str, values: dict[str, str], target_unit: str | None = None) -> FormulaResult:
    import sympy as sp

    quantities = {name.strip(): parse_quantity(text) for name, text in values.items()}
    warnings: list[str] = []
    symbols: dict[str, sp.Symbol] = {}
    if formula.count("=") > 1:
        raise ValueError("Une seule égalité par formule.")
    if "=" in formula:
        left_text, right_text = formula.split("=")
        left = E.to_sympy(E.parse(left_text, units=False), symbols)
        right = E.to_sympy(E.parse(right_text, units=False), symbols)
        unknowns = [s for name, s in symbols.items() if name not in quantities]
        if len(unknowns) != 1:
            missing = ", ".join(sorted(str(u) for u in unknowns)) or "aucune"
            raise ValueError(f"Il faut exactement une inconnue ; inconnues actuelles : {missing}. "
                             "Fournissez les valeurs manquantes (elles ne seront jamais supposées).")
        unknown = unknowns[0]
        solutions = sp.solve(sp.Eq(left, right), unknown)
        if not solutions:
            raise ValueError(f"Impossible de résoudre la formule pour {unknown}.")
        expressions, solved_for = solutions, str(unknown)
    else:
        expressions = [E.to_sympy(E.parse(formula, units=False), symbols)]
        missing = sorted(name for name in symbols if name not in quantities)
        if missing:
            raise ValueError(f"Valeurs manquantes : {', '.join(missing)} (elles ne seront jamais supposées).")
        solved_for = None
    unused = sorted(set(quantities) - set(symbols))
    if unused:
        warnings.append(f"Valeurs fournies mais absentes de la formule : {', '.join(unused)}.")
    unitless = sorted(name for name in symbols if name in quantities and not quantities[name].has_unit)
    if unitless:
        warnings.append(f"Valeurs sans unité (considérées sans dimension) : {', '.join(unitless)}.")
    si_subs = {symbols[n]: quantities[n].si for n in symbols if n in quantities}
    shown_subs = {symbols[n]: quantities[n].shown for n in symbols if n in quantities}
    dims_map = {symbols[n]: quantities[n].dims for n in symbols if n in quantities}
    results_si: list[float] = []
    results_shown: list[float] = []
    result_dims: U.Dims | None = None
    for expression in expressions:
        try:
            si_value = complex(expression.subs(si_subs).evalf())
            shown_value = complex(expression.subs(shown_subs).evalf())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Évaluation numérique impossible : {exc}") from exc
        if abs(si_value.imag) > 1e-12 * max(1.0, abs(si_value.real)):
            warnings.append("Solution complexe ignorée.")
            continue
        results_si.append(si_value.real)
        results_shown.append(shown_value.real)
        result_dims = _dims_of(expression, dims_map, warnings)
    if not results_si:
        raise ValueError("Aucune solution réelle.")
    if len(results_si) > 1:
        warnings.append("Plusieurs solutions : choisir celle qui a un sens physique.")
    in_target: list[float] = []
    if target_unit:
        factor, dims = parse_target_unit(target_unit)
        if result_dims is not None and dims != result_dims:
            warnings.append(f"Unité cible incompatible : le résultat est en {U.format_dims(result_dims)}.")
        else:
            in_target = [v / factor for v in results_si]
    return FormulaResult(formula=formula, solved_for=solved_for,
                         expression="; ".join(str(e) for e in expressions), values_used=values,
                         results_si=results_si, unit_si=U.format_dims(result_dims) if result_dims is not None else None,
                         results_as_written=results_shown, target_unit=target_unit, results_in_target=in_target,
                         warnings=list(dict.fromkeys(warnings)))
