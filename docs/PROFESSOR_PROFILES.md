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

## Consignes de mise en forme : appliquées automatiquement

`analyze_assignment` lit dans les consignes (fr / ru / en) : police, taille, interligne, marges, retrait de première
ligne, alignement, position des numéros de page, style des références (APA, IEEE, ISO 690, ГОСТ Р 7.0.5,
Vancouver, Chicago, Harvard) et format de remise (PDF, Word). Chaque phrase devient une exigence « format »
(ex. `font=Arial; size_pt=11; line_spacing=2`).

Ordre de priorité, du plus faible au plus fort :
1. gabarit de la convention (ГОСТ 7.32, usage universitaire francophone, APA, IEEE) ;
2. profil de l'enseignant (`layout_rules`, `bibliography_rules`) ;
3. consignes du travail (exigences « format » non rejetées).

Le gabarit obtenu (« … + consignes de l'enseignant ») sert à `export_document`, `check_formatting`,
`apply_formatting` et au dossier de recherche. Une exigence rejetée par l'utilisateur n'est plus appliquée.

## Plan imposé par l'enseignant

Si le profil contient `expected_structure`, `create_academic_outline` suit CE plan (ordre et titres) ; les parties
reconnues (introduction, conclusion, références…) gardent les indications du gabarit.

## Longueur et normes internationales

`check_academic_norms` (aussi inclus dans `final_quality_audit`) contrôle :
- la longueur demandée par l'enseignant (pages estimées à 280 mots par page, ou mots) ;
- les éléments attendus selon le type : thèse et mémoire (ISO 7144), rapport (ANSI/NISO Z39.18), compte rendu de TP ;
- le résumé (ISO 214), la numérotation des titres (ISO 2145), les figures et tableaux numérotés et appelés,
  les valeurs et unités SI (ISO 80000-1), les dates ambiguës (ISO 8601), les sigles définis.

## Dossier de recherche à partir d'un thème

`build_research_dossier(project_id, topic, queries)` : domaine reconnu, sources réelles des bases gratuites,
consignes de l'enseignant, plan proposé, démarche de la discipline, normes applicables, modèle de déclaration
d'utilisation d'outils numériques → fichier Word mis en forme selon les consignes (et Markdown). Chaque source est à
lire et à confirmer (`register_source`) avant d'être citée.
