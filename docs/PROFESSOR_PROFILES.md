# Profils d'enseignants et respect des consignes

## Documents de l'enseignant

Rôles à l'import : `instructions` (consignes), `course` (support de cours, notes, transcriptions), `rubric`
(barème, grille), `example` (exemple de travail), `template` (modèle), `data`.

## Profil réutilisable

`create_teacher_profile` / `update_teacher_profile` : enseignant, matière, cours, établissement, politique de
sources par défaut, notations, méthodes, attentes, **définitions du cours**, **structure attendue**, niveau de
détail, style, sources autorisées, règles bibliographiques, mise en page, **critères d'évaluation (barème)**,
types de travaux. `set_project_teaching` rattache le profil à un projet : tout est transmis au rédacteur.

Extraction assistée (propositions à confirmer, rien n'est enregistré seul) :
- `extract_teacher_material` : barème (« critère — 4 points », « 2 балла », tableau critère / points) et
  définitions (« X désigne… », « X — это… », « … называется X », « X is defined as… ») avec document et page ;
- `extract_course_notations` : notations (« где m — масса », « où m est la masse »).

## « Réponds uniquement à partir du cours »

Détectée automatiquement dans les consignes (fr, ru, en) → politique `course_only` :
- dossier du rédacteur limité aux documents de l'enseignant ; aucune source bibliographique ;
- citation `[@clé]` dans une rédaction = erreur ; enregistrement, import et téléchargement de sources refusés ;
- consigne au rédacteur : écrire `[NON TRAITÉ DANS LE COURS : …]` au lieu de compléter ;
- `check_course_coverage` : pour chaque question, passages du cours qui la traitent, ou « non traitée » ;
  contradictions entre documents de l'enseignant (même symbole, valeurs différentes).

`external_allowed` : connaissances externes permises mais toujours signalées, jamais attribuées à l'enseignant.

Limites : la couverture se fonde sur des mots-clés (un passage trouvé indique où lire, il ne garantit pas la
réponse) ; la consigne n'est pas détectée si elle est formulée de façon inhabituelle (la politique se règle alors
à la main).
