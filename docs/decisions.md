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

## Points ouverts
- **Licence PyMuPDF (AGPL-3.0)** : résolu par D-011 (lecteur optionnel, défaut permissif).
- **Correction linguistique** : LanguageTool (LGPL, nécessite Java) à évaluer en Phase 5.
