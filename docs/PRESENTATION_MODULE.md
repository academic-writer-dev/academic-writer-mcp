# Module de présentations

## Outils

- `plan_presentation(project_id, occasion, duration_minutes, document_id | topic)` : structure adaptée à
  l'occasion (exposé ; soutenances Licence, Master, doctorat ; présentation scientifique ; professionnelle) et à
  la durée (≈ 1 diapositive / minute), rôle et temps de chaque diapositive, matière SOURCÉE extraite de la
  rédaction ou du document (phrases chiffrées d'abord), graphiques disponibles.
- `create_presentation(project_id, deck, duration_minutes, export_pdf, export_odp, preview)` : PPTX modifiable
  16:9, contrôles, export PDF / ODP et aperçus PNG par PowerPoint.

## Design

10 styles : academique, technique, sobre, clair, minimal_premium, corporate, scientifique, industriel,
futuriste (sombre), editorial. Couleur de titre par thème ; texte posé sur une couleur choisie selon le contraste ;
tous les thèmes testés à ≥ 4,5:1 (WCAG) pour titres et texte. Taille de police calculée pour tenir dans le cadre
sans couper un mot (minimum 14 pt, sinon la diapositive est signalée « surchargée »).

Mises en page : titre, section, puces, deux colonnes, graphique (avec points clés), image (source obligatoire),
tableau, chiffres clés (sourcés), citation (référence obligatoire), démarche (cartes numérotées), sommaire,
comparaison, définitions, chronologie, conclusion, références (bibliographie du projet), questions.

## Notes du présentateur

Texte à dire, transition, questions possibles du jury avec éléments de réponse fondés sur le travail.

## Contrôles automatiques

Chiffres absents des documents, de la rédaction et des graphiques du projet (erreur) ; texte trop long ; plus de
6 puces ; puces > 130 caractères ; diapositive dense ; figure ou citation sans source ; notes absentes ; titres
répétés ; marqueurs à compléter ; références manquantes ; durée estimée (≈ 130 mots / minute) ; chevauchements et
éléments hors cadre.

## Contrôle visuel

Aperçus PNG de chaque diapositive (PowerPoint ; dossier temporaire ASCII car `Slide.Export` refuse les chemins
cyrilliques). Inspections réalisées pendant le développement : mots coupés dans les chevrons (remplacés par des
cartes), ponctuation française en russe, contraste insuffisant sur fond sombre, chronologie ambiguë — corrigés.

## Limites

Pas de recherche ni de génération d'images (photographies, schémas techniques) : seules les images du projet
(extraites des documents) et les graphiques créés à partir des données sont insérés, pour ne jamais fabriquer une
illustration trompeuse. LibreOffice n'est pas installé sur ce poste : conversion par PowerPoint.
