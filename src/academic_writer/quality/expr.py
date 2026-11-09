"""Analyse sûre d'expressions de calcul écrites dans un document (sans ``eval``).

Deux modes :
- ``units=True`` (calculs numériques du texte) : une lettre qui suit un nombre est une unité (« 0,5 м/с »);
- ``units=False`` (formules) : les identifiants sont des variables (« m*z », « π*n/30 »).

L'arbre produit est évalué soit numériquement (valeurs SI + valeurs « telles qu'écrites »), soit en SymPy.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from academic_writer.quality import units as U

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_THOUSANDS = re.compile(r"(?<![\d.])(\d{1,3})((?:[    ]\d{3})+)(?![\d.,])")
FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "tg": math.tan, "cot": lambda x: 1 / math.tan(x),
             "ctg": lambda x: 1 / math.tan(x), "asin": math.asin, "arcsin": math.asin, "acos": math.acos,
             "arccos": math.acos, "atan": math.atan, "arctg": math.atan, "arctan": math.atan, "sqrt": math.sqrt,
             "ln": math.log, "log": math.log, "lg": math.log10, "log10": math.log10, "exp": math.exp,
             "abs": abs}
CONSTANTS = {"π": math.pi, "pi": math.pi}
_IDENT = re.compile(r"[^\W\d][\w']*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+")


class ParseError(ValueError):
    pass


class Unresolved(ValueError):
    """Variable inconnue : le segment est symbolique."""


def normalize(text: str) -> str:
    text = text.translate(_SUBSCRIPT)
    text = _SUP_RUN.sub(lambda m: "^(" + m.group(0).translate(_SUPERSCRIPT) + ")", text)
    text = (text.replace("−", "-").replace("–", "-").replace("—", "-").replace("×", "*").replace("·", "*")
            .replace("⋅", "*").replace("∙", "*").replace("÷", "/").replace("√", " sqrt ").replace(" ", " "))
    text = _THOUSANDS.sub(lambda m: m.group(1) + re.sub(r"\D", "", m.group(2)), text)
    return _DECIMAL_COMMA.sub(".", text)


@dataclass
class Node:
    kind: str  # num, var, const, neg, bin, pow, func, unit
    value: float = 0.0
    text: str = ""
    op: str = ""
    args: list[Node] = field(default_factory=list)
    unit_factor: float = 1.0
    dims: U.Dims = U.ZERO


class Parser:
    def __init__(self, text: str, *, units: bool) -> None:
        self.s = normalize(text)
        self.i = 0
        self.units = units

    def parse(self) -> Node:
        node = self.expr()
        self._ws()
        if self.i != len(self.s):
            raise ParseError(f"caractère inattendu : {self.s[self.i:self.i + 10]!r}")
        return node

    # --- lexique -----------------------------------------------------------------
    def _ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def _peek(self) -> str:
        self._ws()
        return self.s[self.i] if self.i < len(self.s) else ""

    def _starts_primary(self) -> bool:
        char = self._peek()
        return bool(char) and (char == "(" or bool(_IDENT.match(self.s, self.i)))

    # --- grammaire ----------------------------------------------------------------
    def expr(self) -> Node:
        node = self.term()
        while self._peek() in ("+", "-"):
            op = self.s[self.i]
            self.i += 1
            node = Node("bin", op=op, args=[node, self.term()])
        return node

    def term(self) -> Node:
        node = self.unary()
        while True:
            char = self._peek()
            if char in ("*", "/"):
                self.i += 1
                node = Node("bin", op=char, args=[node, self.unary()])
            elif char and self._starts_primary():
                # multiplication implicite « 2π », « 2(a+b) », « 2 m » (les unités ont déjà été absorbées)
                node = Node("bin", op="*", args=[node, self.unary()])
            else:
                return node

    def unary(self) -> Node:
        char = self._peek()
        if char in ("-", "+"):
            self.i += 1
            operand = self.unary()
            return Node("neg", args=[operand]) if char == "-" else operand
        return self.power()

    def power(self) -> Node:
        base = self.primary()
        if self._peek() == "^" or self.s.startswith("**", self.i):
            self.i += 2 if self.s.startswith("**", self.i) else 1
            saved, self.units = self.units, False  # un exposant n'a pas d'unité : « 10³ мм » = (10³) мм
            try:
                exponent = self.unary()
            finally:
                self.units = saved
            base = Node("pow", args=[base, exponent])
        return self._maybe_unit(base)

    def _maybe_unit(self, node: Node) -> Node:
        if not self.units:
            return node
        start = self.i
        self._ws()
        parsed = U.parse_unit(self.s[self.i:])
        if parsed is None:
            self.i = start
            return node
        factor, dims, length = parsed
        end = self.i + length
        if end < len(self.s) and (self.s[end].isalnum() or self.s[end] == "_"):
            self.i = start  # « 2 mz » : pas une unité
            return node
        text = self.s[self.i:end]
        self.i = end
        return Node("unit", args=[node], unit_factor=factor, dims=dims, text=text)

    def primary(self) -> Node:
        char = self._peek()
        if not char:
            raise ParseError("expression incomplète")
        if char == "(":
            self.i += 1
            node = self.expr()
            if self._peek() != ")":
                raise ParseError("parenthèse non fermée")
            self.i += 1
            return node
        number = _NUMBER.match(self.s, self.i)
        if number:
            self.i = number.end()
            return Node("num", value=float(number.group(0)), text=number.group(0))
        ident = _IDENT.match(self.s, self.i)
        if ident:
            name = ident.group(0)
            self.i = ident.end()
            if name in FUNCTIONS:
                if self._peek() == "(":
                    return Node("func", op=name, args=[self.primary()])
                return Node("func", op=name, args=[self.power()])  # « sin 30° », « sqrt 2 »
            if name in CONSTANTS:
                return Node("const", text=name, value=CONSTANTS[name])
            if name.startswith("_") or "__" in name:
                raise ParseError("identifiant interdit")
            return Node("var", text=name)
        raise ParseError(f"caractère inattendu : {char!r}")


def parse(text: str, *, units: bool) -> Node:
    return Parser(text, units=units).parse()


def variables_of(node: Node) -> set[str]:
    found = {node.text} if node.kind == "var" else set()
    for arg in node.args:
        found |= variables_of(arg)
    return found


def has_units(node: Node) -> bool:
    return node.kind == "unit" or any(has_units(a) for a in node.args)


def is_literal(node: Node) -> bool:
    """Nombre seul, éventuellement « × 10^k » et/ou suivi d'une unité."""
    if node.kind == "unit":
        node = node.args[0]
    if node.kind == "num":
        return True
    if node.kind == "neg":
        return is_literal(node.args[0])
    if node.kind == "bin" and node.op == "*":
        left, right = node.args
        if right.kind == "unit":
            right = right.args[0]
        return left.kind == "num" and right.kind == "pow" and right.args[0].kind == "num" and right.args[0].value == 10
    return False


@dataclass
class Value:
    si: float
    shown: float  # nombres pris tels qu'écrits (facteurs d'unité ignorés)
    dims: U.Dims
    has_unit: bool


@dataclass
class Variable:
    si: float
    shown: float
    dims: U.Dims
    has_unit: bool


def evaluate(node: Node, variables: dict[str, Variable] | None = None) -> Value:
    """Évalue l'arbre ; lève Unresolved si une variable est inconnue, ArithmeticError/ValueError si impossible."""
    variables = variables or {}
    kind = node.kind
    if kind == "num":
        return Value(node.value, node.value, U.ZERO, False)
    if kind == "const":
        return Value(node.value, node.value, U.ZERO, False)
    if kind == "var":
        if node.text not in variables:
            raise Unresolved(node.text)
        v = variables[node.text]
        return Value(v.si, v.shown, v.dims, v.has_unit)
    if kind == "unit":
        inner = evaluate(node.args[0], variables)
        # « 30° » : la valeur telle qu'écrite garde le facteur d'angle (sin 30° doit valoir 0,5 dans les deux voies)
        shown = inner.shown * node.unit_factor if node.text in ("°", "град", "%", "‰") else inner.shown
        return Value(inner.si * node.unit_factor, shown, U.mul(inner.dims, node.dims), True)
    if kind == "neg":
        inner = evaluate(node.args[0], variables)
        return Value(-inner.si, -inner.shown, inner.dims, inner.has_unit)
    if kind == "bin":
        a, b = (evaluate(x, variables) for x in node.args)
        unit = a.has_unit or b.has_unit
        if node.op == "+":
            return Value(a.si + b.si, a.shown + b.shown, a.dims if a.has_unit or not b.has_unit else b.dims, unit)
        if node.op == "-":
            return Value(a.si - b.si, a.shown - b.shown, a.dims if a.has_unit or not b.has_unit else b.dims, unit)
        if node.op == "*":
            return Value(a.si * b.si, a.shown * b.shown, U.mul(a.dims, b.dims), unit)
        return Value(a.si / b.si, a.shown / b.shown, U.mul(a.dims, U.inv(b.dims)), unit)
    if kind == "pow":
        a, b = (evaluate(x, variables) for x in node.args)
        exponent = b.si
        dims = U.power(a.dims, round(exponent)) if float(exponent).is_integer() else U.ZERO
        return Value(a.si ** exponent, a.shown ** exponent, dims, a.has_unit)
    if kind == "func":
        arg = evaluate(node.args[0], variables)
        func = FUNCTIONS[node.op]
        if node.op == "sqrt":
            dims = tuple(d // 2 for d in arg.dims)  # type: ignore[assignment]
            return Value(math.sqrt(arg.si), math.sqrt(arg.shown), dims, arg.has_unit)
        # fonctions trigonométriques : argument en radians (valeur SI) dans les deux voies
        result = func(arg.si)
        return Value(result, result, U.ZERO, False)
    raise ParseError(kind)


def to_sympy(node: Node, symbols: dict):
    """Convertit l'arbre (mode formule) en expression SymPy, sans évaluation de texte."""
    import sympy as sp

    funcs = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "tg": sp.tan, "cot": sp.cot, "ctg": sp.cot,
             "asin": sp.asin, "arcsin": sp.asin, "acos": sp.acos, "arccos": sp.acos, "atan": sp.atan,
             "arctg": sp.atan, "arctan": sp.atan, "sqrt": sp.sqrt, "ln": sp.log, "log": sp.log,
             "lg": lambda x: sp.log(x, 10), "log10": lambda x: sp.log(x, 10), "exp": sp.exp, "abs": sp.Abs}
    kind = node.kind
    if kind == "num":
        return sp.nsimplify(node.text) if len(node.text) < 12 else sp.Float(node.value)
    if kind == "const":
        return sp.pi
    if kind == "var":
        if node.text not in symbols:
            symbols[node.text] = sp.Symbol(node.text)
        return symbols[node.text]
    if kind == "neg":
        return -to_sympy(node.args[0], symbols)
    if kind == "bin":
        a, b = (to_sympy(x, symbols) for x in node.args)
        return {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[node.op]
    if kind == "pow":
        return to_sympy(node.args[0], symbols) ** to_sympy(node.args[1], symbols)
    if kind == "func":
        return funcs[node.op](to_sympy(node.args[0], symbols))
    raise ParseError("unités non admises dans une formule : donnez-les dans les valeurs")
