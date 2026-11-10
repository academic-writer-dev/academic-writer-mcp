"""Graphiques scientifiques tracés exactement à partir des données fournies (matplotlib, licence PSF/BSD).

Types : courbe (line), nuage de points (scatter, régression facultative), barres (bar), histogramme, fonction
mathématique (function, lue de façon sûre par le module de calcul formel), escalier (step : diagrammes d'efforts
tranchants), aire (area : diagrammes de moments), série temporelle (timeseries), diagramme de Gantt (gantt).

Chaque graphique est enregistré en PNG (300 dpi) et SVG, avec un fichier JSON contenant les données et les
réglages utilisés (traçabilité : le graphique correspond aux données). Aucune donnée n'est inventée, lissée ou
complétée ; une régression est toujours affichée avec son équation et son R².
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ChartType = Literal["line", "scatter", "bar", "histogram", "function", "step", "area", "timeseries", "gantt"]
Regression = Literal["linear", "polynomial2", "polynomial3", "exponential", "power", "logarithmic"]

NOTICE = ("Graphique tracé exactement à partir des données fournies (aucune valeur ajoutée, lissée ou extrapolée). "
          "L'interprétation reste à faire et à vérifier par l'utilisateur.")


class Series(BaseModel):
    name: str = Field(default="", max_length=120)
    x: list[float | str] = Field(default_factory=list, description="Abscisses (nombres, dates ISO ou catégories).")
    y: list[float] = Field(default_factory=list)


class GanttTask(BaseModel):
    name: str = Field(max_length=120)
    start: str = Field(description="Date ISO (AAAA-MM-JJ).")
    end: str = Field(description="Date ISO (AAAA-MM-JJ).")


class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str = Field(min_length=1, max_length=200)
    x_label: str = Field(default="", max_length=120)
    x_unit: str = Field(default="", max_length=40)
    y_label: str = Field(default="", max_length=120)
    y_unit: str = Field(default="", max_length=40)
    source: str = Field(min_length=1, max_length=300, description="Origine des données (obligatoire).")
    series: list[Series] = Field(default_factory=list)
    regression: Regression | None = None
    function_expression: str | None = None
    x_min: float | None = None
    x_max: float | None = None
    bins: int | None = Field(default=None, ge=2, le=200)
    tasks: list[GanttTask] = Field(default_factory=list)
    annotate_extrema: bool = False
    language: Literal["fr", "ru", "en"] = "fr"


class SeriesSummary(BaseModel):
    name: str
    points: int
    x_range: list[str]
    y_min: float | None
    y_max: float | None
    x_at_y_max: str | None


class RegressionResult(BaseModel):
    series: str
    model: str
    equation: str
    r_squared: float
    coefficients: list[float]


class ChartResult(BaseModel):
    chart_id: str
    title: str
    png_path: str
    svg_path: str
    data_path: str
    script_path: str | None = Field(default=None, description="Script Python de régénération (reproductibilité).")
    markdown: str = Field(description="À insérer dans une section pour que l'export DOCX intègre le graphique.")
    summaries: list[SeriesSummary]
    regressions: list[RegressionResult]
    warnings: list[str]
    notice: str = NOTICE


class ChartError(ValueError):
    pass


_LABELS = {
    "fr": {"count": "Effectif", "source": "Source", "fit": "Ajustement", "tasks": "Tâches", "date": "Date"},
    "ru": {"count": "Частота", "source": "Источник", "fit": "Аппроксимация", "tasks": "Этапы", "date": "Дата"},
    "en": {"count": "Count", "source": "Source", "fit": "Fit", "tasks": "Tasks", "date": "Date"},
}


def _axis(label: str, unit: str) -> str:
    return f"{label}, {unit}" if label and unit else label


def _number(value) -> float:
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            number = float(text)
        except ValueError as exc:
            raise ChartError(f"Valeur non numérique : « {value} ».") from exc
    if not math.isfinite(number):
        raise ChartError(f"Valeur non finie : « {value} ».")
    return number


def _date(value) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ChartError(f"Date invalide (format AAAA-MM-JJ attendu) : « {value} ».") from exc


def _fit(x: list[float], y: list[float], model: str) -> RegressionResult | str:
    import numpy as np

    xs, ys = np.array(x, dtype=float), np.array(y, dtype=float)
    if len(xs) < 3:
        return "Régression non calculée : au moins 3 points nécessaires."
    if model in ("linear", "polynomial2", "polynomial3"):
        degree = {"linear": 1, "polynomial2": 2, "polynomial3": 3}[model]
        if len(xs) <= degree:
            return f"Régression de degré {degree} impossible avec {len(xs)} points."
        coefficients = np.polyfit(xs, ys, degree)
        scale = max(float(np.max(np.abs(ys))), 1e-300)
        coefficients = np.where(np.abs(coefficients) * np.max(np.abs(xs)) ** np.arange(degree, -1, -1)
                                < 1e-9 * scale, 0.0, coefficients)  # bruit numérique (2e-18) → 0
        predicted = np.polyval(coefficients, xs)
        terms = []
        for power, c in zip(range(degree, -1, -1), coefficients, strict=True):
            if c == 0 and power != degree:
                continue
            terms.append(f"{c:+.6g}" + ("" if power == 0 else "·x" if power == 1 else f"·x^{power}"))
        equation = "y = " + " ".join(terms).lstrip("+")
        coefs = [float(c) for c in coefficients]
    elif model in ("exponential", "power", "logarithmic"):
        if model in ("exponential", "power") and np.any(ys <= 0):
            return f"Modèle {model} impossible : valeurs y ≤ 0."
        if model in ("power", "logarithmic") and np.any(xs <= 0):
            return f"Modèle {model} impossible : valeurs x ≤ 0."
        if model == "exponential":
            b, ln_a = np.polyfit(xs, np.log(ys), 1)
            a = math.exp(ln_a)
            predicted, equation, coefs = a * np.exp(b * xs), f"y = {a:.6g}·exp({b:.6g}·x)", [a, float(b)]
        elif model == "power":
            b, ln_a = np.polyfit(np.log(xs), np.log(ys), 1)
            a = math.exp(ln_a)
            predicted, equation, coefs = a * xs ** b, f"y = {a:.6g}·x^{b:.6g}", [a, float(b)]
        else:
            b, a = np.polyfit(np.log(xs), ys, 1)
            predicted, equation, coefs = a + b * np.log(xs), f"y = {a:.6g} {b:+.6g}·ln(x)", [float(a), float(b)]
    else:
        return f"Modèle de régression inconnu : {model}."
    residual = float(np.sum((ys - predicted) ** 2))
    total = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1 - residual / total if total else 1.0
    return RegressionResult(series="", model=model, equation=equation, r_squared=round(r2, 6), coefficients=coefs)


_SCRIPT_TEMPLATE = '''"""Régénère le graphique « {title} » à partir des données conservées ({chart_id}.json).

Commande : uv run python {chart_id}.py (dans ce dossier, avec Academic Writer installé).
"""

import json
from pathlib import Path

from academic_writer.charts import ChartSpec, render

here = Path(__file__).resolve().parent
spec = ChartSpec.model_validate(json.loads((here / "{chart_id}.json").read_text(encoding="utf-8"))["spec"])
result = render(spec, here, "{chart_id}-regenere")
print(result.png_path)
'''


def render(spec: ChartSpec, folder: Path, chart_id: str) -> ChartResult:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np

    labels = _LABELS[spec.language]
    warnings: list[str] = []
    summaries: list[SeriesSummary] = []
    regressions: list[RegressionResult] = []
    used: dict = {"spec": spec.model_dump(), "plotted": []}

    if spec.chart_type not in ("gantt", "function") and not spec.series:
        raise ChartError("Aucune série de données.")
    if spec.chart_type == "gantt" and not spec.tasks:
        raise ChartError("Diagramme de Gantt : indiquez les tâches (tasks).")
    if spec.chart_type not in ("gantt", "histogram", "bar", "timeseries"):
        for axis, label, unit in (("x", spec.x_label, spec.x_unit), ("y", spec.y_label, spec.y_unit)):
            if not label:
                raise ChartError(f"Intitulé de l'axe {axis} obligatoire.")
            if not unit:
                warnings.append(f"Axe {axis} sans unité : à préciser si la grandeur en a une.")

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    try:
        if spec.chart_type == "function":
            if not spec.function_expression or spec.x_min is None or spec.x_max is None:
                raise ChartError("Fonction : indiquez function_expression, x_min et x_max.")
            if spec.x_min >= spec.x_max:
                raise ChartError("x_min doit être inférieur à x_max.")
            import sympy as sp

            from academic_writer.quality.symbolic import SymbolicError, parse

            try:
                expr = parse(spec.function_expression, "fonction")
            except SymbolicError as exc:
                raise ChartError(str(exc)) from exc
            free = sorted(expr.free_symbols, key=str)
            if len(free) > 1:
                raise ChartError("La fonction doit dépendre d'une seule variable.")
            variable = free[0] if free else sp.Symbol("x")
            f = sp.lambdify(variable, expr, "numpy")
            xs = np.linspace(spec.x_min, spec.x_max, 600)
            with np.errstate(all="ignore"):
                ys = np.asarray(f(xs), dtype=float) * np.ones_like(xs)
            invalid = ~np.isfinite(ys)
            if invalid.all():
                raise ChartError("La fonction n'est définie en aucun point de l'intervalle.")
            if invalid.any():
                warnings.append(f"{int(invalid.sum())} point(s) hors du domaine de définition non tracés.")
            ys[invalid] = np.nan
            ax.plot(xs, ys, label=f"y = {spec.function_expression}")
            used["plotted"].append({"name": spec.function_expression, "x": [spec.x_min, spec.x_max],
                                    "samples": 600})
            finite = ~invalid
            summaries.append(SeriesSummary(name=spec.function_expression, points=int(finite.sum()),
                                           x_range=[str(spec.x_min), str(spec.x_max)],
                                           y_min=float(np.nanmin(ys)), y_max=float(np.nanmax(ys)),
                                           x_at_y_max=f"{xs[int(np.nanargmax(ys))]:.6g}"))
        elif spec.chart_type == "gantt":
            tasks = [(t.name, _date(t.start), _date(t.end)) for t in spec.tasks]
            for name, start, end in tasks:
                if end < start:
                    raise ChartError(f"Tâche « {name} » : fin avant le début.")
            for index, (name, start, end) in enumerate(reversed(tasks)):
                ax.barh(index, mdates.date2num(end) - mdates.date2num(start), left=mdates.date2num(start),
                        height=0.5)
            ax.set_yticks(range(len(tasks)), [t[0] for t in reversed(tasks)])
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
            fig.autofmt_xdate()
            ax.set_xlabel(spec.x_label or labels["date"])
            used["plotted"] = [t.model_dump() for t in spec.tasks]
            summaries.append(SeriesSummary(name=labels["tasks"], points=len(tasks),
                                           x_range=[min(t[1] for t in tasks).date().isoformat(),
                                                    max(t[2] for t in tasks).date().isoformat()],
                                           y_min=None, y_max=None, x_at_y_max=None))
        else:
            for position, series in enumerate(spec.series):
                name = series.name or f"Série {position + 1}"
                if spec.chart_type == "histogram":
                    values = [_number(v) for v in (series.y or series.x)]
                    if not values:
                        raise ChartError(f"{name} : aucune valeur.")
                    ax.hist(values, bins=spec.bins or "auto", alpha=0.75, label=name, edgecolor="black")
                    used["plotted"].append({"name": name, "values": values})
                    summaries.append(SeriesSummary(name=name, points=len(values), x_range=[str(min(values)), str(max(values))],
                                                   y_min=min(values), y_max=max(values), x_at_y_max=None))
                    continue
                if len(series.x) != len(series.y):
                    raise ChartError(f"{name} : {len(series.x)} abscisses pour {len(series.y)} ordonnées.")
                if not series.y:
                    raise ChartError(f"{name} : aucune donnée.")
                ys = [_number(v) for v in series.y]
                if spec.chart_type == "bar":
                    categories = [str(v) for v in series.x]
                    width = 0.8 / len(spec.series)
                    positions = np.arange(len(categories)) + position * width
                    ax.bar(positions, ys, width=width, label=name)
                    ax.set_xticks(np.arange(len(categories)) + width * (len(spec.series) - 1) / 2, categories)
                    xs_text = categories
                elif spec.chart_type == "timeseries":
                    dates = [_date(v) for v in series.x]
                    ax.plot(dates, ys, marker="o", markersize=3, label=name)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
                    fig.autofmt_xdate()
                    xs_text = [d.date().isoformat() if isinstance(d, (date, datetime)) else str(d) for d in dates]
                else:
                    xs = [_number(v) for v in series.x]
                    if spec.chart_type == "scatter":
                        ax.scatter(xs, ys, label=name, s=18)
                    elif spec.chart_type == "step":
                        ax.step(xs, ys, where="post", label=name)
                        ax.fill_between(xs, ys, step="post", alpha=0.25)
                        ax.axhline(0, color="black", linewidth=0.8)
                    elif spec.chart_type == "area":
                        ax.plot(xs, ys, label=name)
                        ax.fill_between(xs, ys, alpha=0.25)
                        ax.axhline(0, color="black", linewidth=0.8)
                    else:
                        ax.plot(xs, ys, marker="o", markersize=3, label=name)
                    if spec.regression:
                        fit = _fit(xs, ys, spec.regression)
                        if isinstance(fit, str):
                            warnings.append(f"{name} : {fit}")
                        else:
                            fit.series = name
                            regressions.append(fit)
                            grid = np.linspace(min(xs), max(xs), 300)
                            c = fit.coefficients
                            curve = {"linear": lambda g: np.polyval(c, g), "polynomial2": lambda g: np.polyval(c, g),
                                     "polynomial3": lambda g: np.polyval(c, g),
                                     "exponential": lambda g: c[0] * np.exp(c[1] * g),
                                     "power": lambda g: c[0] * g ** c[1],
                                     "logarithmic": lambda g: c[0] + c[1] * np.log(g)}[fit.model](grid)
                            ax.plot(grid, curve, linestyle="--",
                                    label=f"{labels['fit']}{' :' if spec.language == 'fr' else ':'} {fit.equation} "
                                          f"(R² = {fit.r_squared:.4f})")
                            if fit.r_squared < 0.9:
                                warnings.append(f"{name} : R² = {fit.r_squared:.3f} — ajustement médiocre, modèle à "
                                                "discuter.")
                    if spec.annotate_extrema:
                        i_max, i_min = int(np.argmax(ys)), int(np.argmin(ys))
                        for i in {i_max, i_min}:
                            ax.annotate(f"{ys[i]:.4g}", (xs[i], ys[i]), textcoords="offset points", xytext=(0, 6),
                                        ha="center", fontsize=8)
                    xs_text = [f"{v:.6g}" for v in xs]
                used["plotted"].append({"name": name, "x": xs_text, "y": ys})
                i_max = int(np.argmax(ys))
                summaries.append(SeriesSummary(name=name, points=len(ys), x_range=[xs_text[0], xs_text[-1]],
                                               y_min=min(ys), y_max=max(ys), x_at_y_max=xs_text[i_max]))
        if spec.chart_type not in ("gantt",):
            ax.set_xlabel(_axis(spec.x_label, spec.x_unit))
            ax.set_ylabel(_axis(spec.y_label or (labels["count"] if spec.chart_type == "histogram" else ""), spec.y_unit))
        ax.set_title(spec.title)
        ax.grid(True, alpha=0.3)
        handles, _ = ax.get_legend_handles_labels()
        if len(handles) > 1 or spec.regression or spec.chart_type == "function":
            ax.legend(fontsize=8)
        colon = " :" if spec.language == "fr" else ":"
        fig.text(0.01, 0.01, f"{labels['source']}{colon} {spec.source}", fontsize=7, alpha=0.8)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        folder.mkdir(parents=True, exist_ok=True)
        png, svg, data = (folder / f"{chart_id}.png", folder / f"{chart_id}.svg", folder / f"{chart_id}.json")
        fig.savefig(png, dpi=300)
        fig.savefig(svg)
    finally:
        plt.close(fig)
    used["regressions"] = [r.model_dump() for r in regressions]
    data.write_text(json.dumps(used, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    script = folder / f"{chart_id}.py"
    script.write_text(_SCRIPT_TEMPLATE.format(title=spec.title, chart_id=chart_id), encoding="utf-8")
    return ChartResult(chart_id=chart_id, title=spec.title, png_path=str(png), svg_path=str(svg), data_path=str(data),
                       script_path=str(script),
                       markdown=f"![{spec.title}](chart:{chart_id})", summaries=summaries, regressions=regressions,
                       warnings=warnings)
