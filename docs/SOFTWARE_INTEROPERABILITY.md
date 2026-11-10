# Interopérabilité logicielle

Catalogue complet (75 logiciels, licence, coût, intégration officielle) : [SOFTWARE_CATALOG.md](SOFTWARE_CATALOG.md).

## Ce que fait réellement Academic Writer

| Statut | Signification | Exemples |
|---|---|---|
| `native` | Calcul exécuté par Academic Writer lui-même | SymPy (`solve_math`), SciPy (`solve_numeric`), matplotlib (`create_chart`), Word (export PDF), Tesseract (OCR), LanguageTool |
| `mcp_server` | Logiciel piloté par un AUTRE serveur MCP déclaré dans Claude Desktop | SolidWorks, T-FLEX CAD (sur ce poste) |
| moteur de `run_software_job` | Lancement autorisé d'un traitement préparé | Python, Excel (recalcul COM), Octave, R, Scilab, CalculiX, Maxima s'ils sont détectés |
| `none` | Détection et conseils seulement | MATLAB, ANSYS, Inventor, TIA Portal… |

Règle : le résultat indique toujours le logiciel (et la version) qui l'a produit ; aucun calcul n'est attribué à
un logiciel qui ne l'a pas exécuté.

## Flux d'un traitement

1. `detect_software` / `list_software_engines` : logiciels présents (registre Windows, PATH, serveurs MCP).
2. `prepare_software_job` : fichiers d'entrée (script, CSV, classeur XLSX avec formules) dans
   `projects/<id>/software/<job>/`.
3. `run_software_job` (si `software_execution = true` ET `confirm=true`) : exécution avec durée maximale.
4. Résultats : sortie, fichiers produits, aperçu des tableaux, images ; `job.json` et `run-N.log` conservent
   commande, version, durée et code retour. Les tableaux peuvent alimenter `create_chart`, puis un rapport.

## Sécurité industrielle

TIA Portal, CODESYS, OpenPLC, Factory I/O : aucun traitement préparé ni lancé, aucune connexion à un automate ;
simulation dans le logiciel lui-même, sauvegarde avant modification, validation professionnelle des fonctions de
sécurité (IEC 61508, IEC 62061, ISO 13849).

## Testé sur ce poste

Détection réelle : SolidWorks 2025 (serveur MCP), Inventor 2027, TIA Portal V18 (règles industrielles),
T-FLEX CAD 17 (serveur MCP), Office 2019, Python, Tesseract. Traitements réels : script Python (NumPy,
Matplotlib) et recalcul de formules par Excel 2019.
