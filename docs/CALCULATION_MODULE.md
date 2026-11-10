# Module de calcul

| Outil | Moteur | Usage | Contrôle indépendant |
|---|---|---|---|
| `validate_calculations` | analyseur maison + unités SI | Recalcule les calculs ÉCRITS d'un document ou d'une rédaction | double lecture SI / « tel qu'écrit », tolérance d'arrondi |
| `evaluate_formula` | SymPy | Formule à une inconnue avec valeurs fournies | dimensions du résultat |
| `convert_units` | analyseur maison | Conversion (notations fr / ru / en : мм, об/мин, МПа, кВт·ч…) | — |
| `solve_math` | SymPy (exact) | Dérivées, intégrales, limites, équations, systèmes, EDO, séries, extremums, matrices | dérivation de la primitive, réinjection, checkodesol, A·A⁻¹ = I… |
| `solve_numeric` | SciPy (numérique) | Optimisation, racines, intégrales, EDO, ajustement, statistiques, test t, ANOVA, corrélation | seconde méthode (Powell, Simpson, Radau, Mann-Whitney, Kruskal, Spearman) |
| `solve_problem` | chaîne de formules | Démarche en 11 étapes | réinjection, ordre de grandeur |

## Démarche en 11 étapes (`solve_problem`)

1 données (avec unités) · 2 inconnue · 3 unités (conversion SI) · 4 hypothèses · 5 méthode · 6 formules ·
7 étapes · 8 calculs · 9 vérification (réinjection) · 10 interprétation (ordre de grandeur, signe) · 11 limites.
Les formules sont fournies par l'utilisateur ou le cours ; une formule écrite pour des unités précises
(ex. ω = πn/30 avec n en tr/min) est détectée : l'écart SI / « tel qu'écrit » est signalé et `values_as_written`
calcule avec les nombres tels qu'écrits.

## Règles

- Aucune donnée manquante n'est supposée : refus explicite.
- `result_kind` : calculé (exact ou numérique) / estimé (ajustement, statistique).
- Sécurité : les expressions passent par une liste blanche (caractères, identifiants, fonctions) avant SymPy ;
  limite de 30 s.

## Valeurs de référence vérifiées par les tests

Racine de x³ − 2x − 5 = 2,0945514815 ; ∫₀¹ e^(−x²) dx = 0,7468241328 ; ∫ e^(−x²) sur ℝ = √π ;
oscillateur x″ = −4x, x(π/2) = −1 ; y′ = −2y, y(1) = e⁻² ; v = πn r / 30 = 7,59 m/s (n = 1450 tr/min, r = 0,05 m).
