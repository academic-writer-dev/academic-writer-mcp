# Journal des décisions techniques

## D-001 — SDK MCP v2 (`mcp` 2.3.x), API `MCPServer` — 2026-11-08
- La v2 est la ligne stable depuis juillet 2026 ; `FastMCP` (v1) a été supprimé.
- Dépendance épinglée `mcp[cli]>=2.3,<3`.
- Protocole négocié vérifié : `2026-07-28` (compatible clients 2025-11-25).
- Conséquence : en 2026-07-28 le serveur ne peut plus initier de requêtes vers le client
  (sampling, elicitation) → ne pas fonder le produit sur le sampling.

## D-002 — Le serveur n'appelle pas de modèle IA dans le MVP — 2026-11-08
- L'assistant connecté est déjà le modèle. Les outils de rédaction préparent des dossiers
  structurés et enregistrent les brouillons comme révisions à valider.
- L'AI Provider Manager (OpenAI, Anthropic, local) sera optionnel, désactivé par défaut,
  activable sur consentement explicite (Phase 10).

## D-003 — Python 3.12 géré par uv — 2026-11-08
- Installé via `uv python install 3.12` (3.12.15), isolé des Python 3.11/3.14 du système.

## D-004 — Journalisation sur stderr en UTF-8 — 2026-11-08
- stdout est réservé au protocole stdio. stderr reconfiguré en UTF-8 (Windows : cp1252 par défaut).
- Les journaux ne doivent jamais contenir le contenu des documents.

## D-005 — Couche MCP dans `server/` (et non `mcp/`) — 2026-11-08
- Évite la confusion avec le paquet `mcp` du SDK.

## D-006 — Lancement des clients via `python -m academic_writer --no-sync` — 2026-11-08
- Sous Windows, un `academic-writer.exe` en cours d'exécution (lancé par Claude Desktop /
  Claude Code) est verrouillé et empêche uv de réinstaller le projet (`os error 32`).
- Les clients lancent donc `uv --directory <projet> run --no-sync python -m academic_writer` :
  aucun .exe du projet n'est verrouillé et les clients ne modifient pas l'environnement.
- Après ajout de dépendances, lancer `uv sync` soi-même, puis redémarrer les clients.

## D-007 — Configuration : pydantic-settings + TOML — 2026-11-08
- Priorité : environnement (`ACADEMIC_WRITER_*`) > `%APPDATA%\AcademicWriter\config.toml` > défauts.
- Données de l'utilisateur dans `D:\AcademicWriter-Data` (choix utilisateur).

## D-008 — SQLite : connexion courte par opération, WAL, migrations par `user_version` — 2026-11-08
- Les outils synchrones s'exécutent dans des threads ; plusieurs clients lancent chacun un
  processus serveur sur la même base → connexions courtes + WAL + `busy_timeout`.
- Sauvegarde automatique (API backup SQLite) avant chaque migration d'une base existante.
- Les tables des phases suivantes seront ajoutées par de nouvelles migrations.

## D-009 — Erreurs métier transmises via `ToolError` — 2026-11-08
- Le SDK v2 masque les exceptions inattendues (« Error executing tool X »).
- Les erreurs métier (`AcademicWriterError`) sont converties en `ToolError` : message clair
  en français pour l'assistant ; les autres erreurs restent masquées et journalisées.

## D-010 — Import : copie vérifiée en lecture seule, inspection sans dépendance native — 2026-11-08
- Inspection maison (signatures, structure OOXML, zip-bomb, macros VBA, JavaScript PDF)
  plutôt que `python-magic` (nécessite libmagic, fragile sous Windows).
- Dossiers d'import autorisés configurables ; import depuis le dossier de données refusé.
- Doublons détectés par SHA-256 dans un même projet.

## D-011 — Deux lecteurs PDF : permissif par défaut, PyMuPDF en option — 2026-11-09
- Défaut (`pdf_backend = 'auto'`) : pypdfium2 (BSD-3/Apache-2.0) pour texte, signets, images,
  rendu OCR + pdfplumber (MIT) pour tableaux et tailles de police → distribution libre.
- Option : PyMuPDF (AGPL-3.0 ou licence Artifex), extra `pymupdf`, activé par
  `pdf_backend = 'pymupdf'`. PyMuPDF 2.x tire onnxruntime/numpy : jamais imposé par défaut.
- Titres PDF : signets (fiables, origine `outline`) sinon heuristique de taille de police
  (origine `font_heuristic`, signalée comme « titre supposé »). Un titre doit contenir un mot
  de ≥ 3 lettres (exclut les cotes de dessins techniques).

## D-012 — OCR : Tesseract 5.4 externe, langues dans `<data_dir>/tessdata` — 2026-11-09
- Installé via winget (UB-Mannheim.TesseractOCR). Langues fra/rus/eng (tessdata standard)
  téléchargées dans `D:\AcademicWriter-Data\tessdata` : pas de droits administrateur requis.
- Appel direct par `subprocess` (sans shell, délai maximal, fenêtre masquée) plutôt que pytesseract.
- OCR automatique des pages PDF sans texte ; limite `ocr_max_pages` (30) pour rester dans les
  délais des clients MCP.

## D-013 — Extraction mise en cache, index FTS5, contenu marqué non fiable — 2026-11-09
- Résultat complet en JSON dans `projects/<id>/derived/<doc>/extraction.json`, réutilisé tant
  que le SHA-256 de la copie ne change pas ; extraction refusée si la copie est altérée.
- Passages d'environ 1200 caractères indexés dans `chunks` + `chunks_fts`
  (`unicode61 remove_diacritics 2` : insensible à la casse et aux accents, cyrillique compris).
- Toute sortie contenant du texte de document porte un `trust_notice` ; détection d'indices
  d'injection de prompt (fr/en/ru) et de caractères invisibles.

## D-014 — Profils disciplinaires en YAML validés par Pydantic, avec héritage — 2026-11-09
- 17 profils intégrés (choix utilisateur : tous les domaines), trilingues fr/ru/en.
- Profils utilisateur dans `<data_dir>/profiles` (remplacent les intégrés de même id).
- `extra="forbid"` : un champ mal orthographié invalide le profil (signalé, non bloquant).
- Héritage : listes fusionnées par id ; mots-clés non hérités ; risque élevé transmis.
- PyYAML en `safe_load` uniquement ; taille de fichier limitée.

## D-015 — Trois conventions de présentation : ru (ГОСТ/ЕСКД), fr (NF/EN), intl (ISO) — 2026-11-09
- Choix utilisateur : les trois référentiels. Structures de base par famille de documents
  (11 familles couvrant les 20 types) ; les profils ajoutent leurs sections (`after:`).
- Convention par défaut déduite de la langue du projet ; modifiable par projet (migration v3).
- Normes marquées `verify_edition` : jamais présentées comme l'édition en vigueur certaine.

## D-016 — Identification du domaine par score de mots-clés explicable — 2026-11-09
- Pas de modèle opaque : score = Σ(1 + ln n) par mot-clé trouvé, atténué par la taille de
  la liste ; préfixes « * » pour les flexions russes et françaises ; casse et accents ignorés.
- Confiance calculée contre le meilleur concurrent d'une autre famille (un parent ou un enfant
  n'est pas un concurrent). Toujours une suggestion à confirmer (`requires_confirmation`).
- Vérifié sur un document réel (ДЗ1 ТММ) : génie mécanique, confiance élevée.

## D-017 — Le serveur peut appeler une IA (choix utilisateur, révise D-002) — 2026-11-09
- Fournisseurs : Anthropic (`claude-opus-5-5`, effort explicite, repli serveur en cas de refus)
  et OpenAI (`gpt-5.5`, API Responses, `store=False`), SDK officiels.
- Garde-fous : mode `connected` réglé par l'utilisateur ; consentement par projet avec phrase
  tapée par l'utilisateur ; budget mensuel ; clés dans le coffre Windows (keyring) ; journal
  d'usage sans contenu ; coût calculé seulement si l'utilisateur saisit les tarifs.
- Anthropic et OpenAI ne prennent pas en charge la Russie (pays d'usage de l'utilisateur, vérifié
  le 2026-11-09) : aucun contournement n'est proposé.

## D-018 — Moteur de rédaction universel — 2026-11-09
- `writing_engine = auto` : cloud autorisé > Ollama local > assistant MCP (toujours disponible).
- Ollama 0.40 + `qwen3.5:4b` (RTX 2060 6 Go) ; modèles sur D: (C: presque plein) ; contexte 8192 ;
  modèle maintenu 30 min en mémoire. Aucun consentement requis : rien ne quitte l'ordinateur.

## D-019 — Correction : LanguageTool LOCAL + IA filtrée — 2026-11-09
- L'API publique LanguageTool interdit l'usage automatisé (« Do not send automated requests ») :
  serveur local uniquement (Java 21 + LanguageTool 6.6, démarrage automatique, URL limitée à localhost).
- Requêtes en UTF-8 via Python : la ligne de commande Windows corrompait le cyrillique.
- Corrections appliquées seulement si sûres (écart ≤ 2 caractères, hors formule, mot absent des
  sources/terminologie : « кориолиса » n'est pas changé en « кореопсиса »).
- Correction IA écartée automatiquement si elle modifie un chiffre ou ajoute un nom propre.

## D-020 — Contrôles issus d'essais réels avec le modèle local — 2026-11-09
- Erreurs observées : attribution inventée (« уравнение Григорьяна »), méthode inventée
  (« методом Планшера »), mots anglais, bibliographie inventée, hypothèse incohérente.
- Réponses : définitions de référence du profil dans le dossier ; contrôles `unsourced_names`,
  `mixed_language`, `generated_bibliography` (erreur), `unsourced_numbers`, fidélité des réécritures.
- La relecture humaine reste indispensable (vérification des calculs prévue en Phase 8).

## D-021 — Analyse des consignes structurelle et données d'entrée des calculs — 2026-11-09
- Retours d'essai réel (ЛР4 ТММ) : intertitres (objectif, étapes, questions, tâches), éléments
  numérotés non découpés, étapes « manipulation » distinctes des livrables, migration v6.
- Profils : chaque calcul déclare déclencheurs et données d'entrée ; valeurs par défaut seulement
  normalisées et sourcées (ex. α = 20°, ha* = 1, c* = 0,25 selon ГОСТ 13755-2015 / ISO 53),
  toujours PROPOSÉES à l'utilisateur.

## D-022 — Sources : marqueurs stables et vérification en deux temps — 2026-11-09
- Citations stockées sous forme stable `[@clé, с. 15]` ; numérotation et format calculés au
  moment de la bibliographie (une citation ajoutée ne décale rien).
- Vérification locale (complétude par type, ISBN/ISSN par somme de contrôle, DOI, année) :
  « bien formée » n'est jamais présenté comme « vérifiée ».
- Vérification en ligne en mode connecté seulement : Crossref (DOI, titre), Open Library (ISBN) ;
  seules des métadonnées sont envoyées. Absence d'un ISBN = non concluant (couverture partielle).
  Essai réel : vrai DOI confirmé, DOI détourné → divergente, DOI inventé → introuvable.
- Citation d'une source suspecte / introuvable / divergente refusée sauf décision explicite.
- Rédacteurs : citer uniquement les clés de la liste fournie ; clé inconnue = erreur bloquante.
- Styles : ГОСТ Р 7.0.100-2018 / 7.0.5-2008, APA 7, IEEE, Chicago auteur-date, Vancouver
  (éléments principaux ; à relire selon l'établissement).

## Points ouverts
- **Licence PyMuPDF (AGPL-3.0)** : résolu par D-011 (lecteur optionnel, défaut permissif).
- **Correction linguistique** : LanguageTool (LGPL, nécessite Java) à évaluer en Phase 5.
