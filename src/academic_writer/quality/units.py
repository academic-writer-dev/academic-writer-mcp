"""Unités physiques (SI) en notation française, russe et internationale.

Chaque unité est un facteur vers le SI et un vecteur de dimensions (m, kg, s, A, K, mol).
Les angles (rad, °, tours) sont sans dimension, comme dans le SI.
"""

from __future__ import annotations

import math
import re

Dims = tuple[int, int, int, int, int, int]
ZERO: Dims = (0, 0, 0, 0, 0, 0)
_BASE_NAMES = ("m", "kg", "s", "A", "K", "mol")

L = (1, 0, 0, 0, 0, 0)
M = (0, 1, 0, 0, 0, 0)
T = (0, 0, 1, 0, 0, 0)
I = (0, 0, 0, 1, 0, 0)  # noqa: E741
TH = (0, 0, 0, 0, 1, 0)
N_ = (0, 0, 0, 0, 0, 1)


def mul(a: Dims, b: Dims) -> Dims:
    return tuple(x + y for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def power(a: Dims, n: int) -> Dims:
    return tuple(x * n for x in a)  # type: ignore[return-value]


def inv(a: Dims) -> Dims:
    return power(a, -1)


FORCE = mul(M, mul(L, power(T, -2)))
ENERGY = mul(FORCE, L)
POWER = mul(ENERGY, inv(T))
PRESSURE = mul(FORCE, power(L, -2))
VOLTAGE = mul(POWER, inv(I))

# Unités de base (préfixables) : symbole -> (facteur SI, dimensions)
_PREFIXABLE_LATIN: dict[str, tuple[float, Dims]] = {
    "m": (1.0, L), "g": (1e-3, M), "s": (1.0, T), "N": (1.0, FORCE), "Pa": (1.0, PRESSURE), "J": (1.0, ENERGY),
    "W": (1.0, POWER), "V": (1.0, VOLTAGE), "A": (1.0, I), "Hz": (1.0, inv(T)), "Ω": (1.0, mul(VOLTAGE, inv(I))),
    "L": (1e-3, power(L, 3)), "mol": (1.0, N_),
}
_PREFIXABLE_CYRILLIC: dict[str, tuple[float, Dims]] = {
    "м": (1.0, L), "г": (1e-3, M), "с": (1.0, T), "Н": (1.0, FORCE), "Па": (1.0, PRESSURE), "Дж": (1.0, ENERGY),
    "Вт": (1.0, POWER), "В": (1.0, VOLTAGE), "А": (1.0, I), "Гц": (1.0, inv(T)), "Ом": (1.0, mul(VOLTAGE, inv(I))),
    "л": (1e-3, power(L, 3)), "моль": (1.0, N_),
}
_PREFIX_LATIN = {"k": 1e3, "M": 1e6, "G": 1e9, "m": 1e-3, "µ": 1e-6, "μ": 1e-6, "u": 1e-6, "n": 1e-9, "c": 1e-2,
                 "d": 1e-1, "da": 10.0}
_PREFIX_CYRILLIC = {"к": 1e3, "М": 1e6, "Г": 1e9, "м": 1e-3, "мк": 1e-6, "н": 1e-9, "с": 1e-2, "д": 1e-1, "да": 10.0}

_TURN = 2 * math.pi
UNITS: dict[str, tuple[float, Dims]] = {}
for _base, (_f, _d) in _PREFIXABLE_LATIN.items():
    UNITS[_base] = (_f, _d)
    for _p, _pf in _PREFIX_LATIN.items():
        UNITS.setdefault(_p + _base, (_f * _pf, _d))
for _base, (_f, _d) in _PREFIXABLE_CYRILLIC.items():
    UNITS[_base] = (_f, _d)
    for _p, _pf in _PREFIX_CYRILLIC.items():
        UNITS.setdefault(_p + _base, (_f * _pf, _d))
UNITS.update({
    # temps
    "min": (60.0, T), "мин": (60.0, T), "h": (3600.0, T), "ч": (3600.0, T), "sec": (1.0, T), "сек": (1.0, T),
    # masse
    "t": (1e3, M), "т": (1e3, M), "kg": (1.0, M), "кг": (1.0, M),
    # pression
    "bar": (1e5, PRESSURE), "бар": (1e5, PRESSURE), "атм": (101325.0, PRESSURE), "atm": (101325.0, PRESSURE),
    # angles et tours (sans dimension)
    "rad": (1.0, ZERO), "рад": (1.0, ZERO), "°": (math.pi / 180, ZERO), "град": (math.pi / 180, ZERO),
    "tr": (_TURN, ZERO), "об": (_TURN, ZERO), "rev": (_TURN, ZERO),
    "rpm": (_TURN / 60, inv(T)), "tr/min": (_TURN / 60, inv(T)), "об/мин": (_TURN / 60, inv(T)),
    # température (écarts uniquement)
    "K": (1.0, TH), "К": (1.0, TH), "°C": (1.0, TH), "℃": (1.0, TH),
    # sans dimension
    "%": (0.01, ZERO), "‰": (0.001, ZERO),
    # volume
    "ml": (1e-6, power(L, 3)), "мл": (1e-6, power(L, 3)),
})
# collisions sans intérêt pratique générées par les préfixes
for _bad in ("сс", "мс" + "с", "Мм", "dam"):
    UNITS.pop(_bad, None)

_ATOM = re.compile(r"°C|℃|°|%|‰|[A-Za-zА-Яа-яЁёµμΩ]+")
_EXPONENT = re.compile(r"\^\(?(-?\d+)\)?|(?<=[A-Za-zА-Яа-яЁё])([23])(?![\d])")


def parse_unit(text: str) -> tuple[float, Dims, int] | None:
    """Analyse une unité composée en tête de ``text`` (« м/с^(2) », « Н*м », « кН/м2 », « об/мин »).

    Renvoie (facteur SI, dimensions, longueur consommée) ou None. Pas d'espace à l'intérieur de l'unité.
    """
    pos = 0
    factor, dims = 1.0, ZERO
    sign = 1
    consumed = 0
    while True:
        # unités contenant elles-mêmes « / »
        special = next((u for u in ("об/мин", "tr/min") if text.startswith(u, pos)), None)
        if special:
            unit_factor, unit_dims = UNITS[special]
            pos += len(special)
        else:
            match = _ATOM.match(text, pos)
            if not match or match.group(0) not in UNITS:
                return (factor, dims, consumed) if consumed else None
            unit_factor, unit_dims = UNITS[match.group(0)]
            pos = match.end()
        exponent = 1
        exp_match = _EXPONENT.match(text, pos)
        if exp_match:
            exponent = int(exp_match.group(1) or exp_match.group(2))
            pos = exp_match.end()
        exponent *= sign
        factor *= unit_factor ** exponent
        dims = mul(dims, power(unit_dims, exponent))
        consumed = pos
        if pos < len(text) and text[pos] in "/*." and pos + 1 < len(text) and _ATOM.match(text, pos + 1):
            sign = -1 if text[pos] == "/" else 1
            pos += 1
            continue
        return factor, dims, consumed


def format_dims(dims: Dims) -> str:
    """Dimensions en unités SI lisibles (N, Pa, J, W reconnus)."""
    named = {FORCE: "N", PRESSURE: "Pa", ENERGY: "J", POWER: "W", VOLTAGE: "V", ZERO: "(sans dimension)",
             inv(T): "1/s", mul(L, inv(T)): "m/s", mul(L, power(T, -2)): "m/s²"}
    if dims in named:
        return named[dims]
    up = [f"{n}{'' if e == 1 else _sup(e)}" for n, e in zip(_BASE_NAMES, dims, strict=True) if e > 0]
    down = [f"{n}{'' if e == -1 else _sup(-e)}" for n, e in zip(_BASE_NAMES, dims, strict=True) if e < 0]
    top = "·".join(up) or "1"
    return top + ("/" + "·".join(down) if down else "")


def _sup(n: int) -> str:
    return str(n).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
