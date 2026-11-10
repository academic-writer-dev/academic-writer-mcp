<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Catalogue des logiciels

75 logiciels. Colonne « Academic Writer » : **native** = exécuté réellement par le serveur ; **détection** = détecté et conseillé, aucune exécution (sauf moteurs de `run_software_job`).

## Mathématiques et calcul

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| SymPy / NumPy (Python) | BSD | gratuit | Intégré : solve_math, evaluate_formula, validate_calculations | native | — |
| Python | PSF | gratuit | Scripts .py; Jupyter | détection | — |
| Jupyter | BSD | gratuit | Carnets .ipynb; CLI jupyter nbconvert --execute | détection | — |
| MATLAB | propriétaire | payant | MATLAB Engine API for Python; CLI matlab -batch; fichiers .m / .mat | détection | GNU Octave |
| GNU Octave | GPL-3.0 | gratuit | CLI octave-cli --eval; oct2py (Python) | détection | — |
| Wolfram Mathematica | propriétaire | payant | wolframscript (CLI); Wolfram Client Library for Python | détection | SymPy, SageMath, Maxima |
| Wolfram|Alpha | service propriétaire | clé gratuite limitée (non commercial) | API Web à clé (AppID) | détection | SymPy (solve_math) |
| Maple | propriétaire | payant | cmaple (CLI); OpenMaple | détection | SymPy, Maxima |
| Scilab / Xcos | GPL-2.0 | gratuit | CLI scilab-cli -e; Xcos (schémas blocs) | détection | — |
| GeoGebra | propriétaire (non commercial gratuit) | gratuit (usage non commercial) | Fichiers .ggb; GeoGebra Apps API (JavaScript) | détection | — |
| SageMath | GPL-3.0 | gratuit | CLI sage -c | détection | — |
| Maxima / wxMaxima | GPL-2.0 | gratuit | CLI maxima --batch-string | détection | — |

## CAO et mécanique

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| SOLIDWORKS | propriétaire | payant (licence étudiante) | API COM SldWorks.Application (VBA, C#, Python pywin32); Macros .swp; Échange STEP / IGES / STL | détection | FreeCAD |
| eDrawings | propriétaire | gratuit (visionneuse) | Visualisation de fichiers CAO | détection | — |
| Autodesk Inventor | propriétaire | payant (licence éducative gratuite) | API COM Inventor.Application; iLogic; Échange STEP / IGES | détection | FreeCAD |
| Autodesk Fusion | propriétaire | gratuit (usage personnel limité) | API Python interne; Échange STEP / F3D | détection | — |
| FreeCAD | LGPL-2.1 | gratuit | API Python; CLI FreeCADCmd; STEP / IGES / STL | détection | — |
| CATIA | propriétaire | payant | CAA / automation COM | détection | FreeCAD |
| Siemens NX | propriétaire | payant | NX Open (Python, C#) | détection | FreeCAD |
| PTC Creo | propriétaire | payant | Creo Toolkit / J-Link | détection | FreeCAD |
| AutoCAD | propriétaire | payant (licence éducative gratuite) | API COM / ActiveX; AutoLISP; Échange DXF / DWG | détection | LibreCAD, QCAD |
| T-FLEX CAD | propriétaire | payant (version éducative gratuite) | T-FLEX Open API (.NET); Échange STEP / DXF | détection | FreeCAD |
| КОМПАС-3D | propriétaire | payant (версия для учебы) | API КОМПАС (COM) | détection | FreeCAD |
| OpenSCAD | GPL-2.0 | gratuit | CLI openscad -o (STL) | détection | — |

## Simulation (éléments finis, CFD)

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Ansys | propriétaire | payant (Student gratuit limité) | PyAnsys (PyMAPDL, PyFluent); APDL en mode batch | détection | CalculiX, Code_Aster, Elmer |
| Abaqus | propriétaire | payant (Learning Edition gratuite limitée) | Scripts Python; Fichiers .inp | détection | CalculiX (format .inp proche) |
| CalculiX | GPL-2.0 | gratuit | CLI ccx (fichiers .inp) | détection | — |
| Code_Aster / Salome-Meca | GPL-3.0 / LGPL | gratuit | Fichiers .comm / .export; Salome (Python) | détection | — |
| OpenFOAM | GPL-3.0 | gratuit | CLI (Linux / WSL) | détection | — |
| Elmer FEM | GPL-2.0 | gratuit | CLI ElmerSolver (.sif) | détection | — |

## Automatisation et électricité

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Siemens TIA Portal | propriétaire | payant | TIA Portal Openness (.NET, groupe « Siemens TIA Openness »); PLCSIM (simulation); Export SCL / XML | détection ⚠ industriel | — |
| CODESYS | propriétaire | gratuit (extensions payantes) | Scripting Python (IronPython); Mode simulation; Export PLCopenXML | détection ⚠ industriel | OpenPLC |
| OpenPLC | GPL-3.0 | gratuit | Éditeur IEC 61131-3; Runtime web | détection ⚠ industriel | — |
| Factory I/O | propriétaire | payant (essai) | SDK .NET; Simulation 3D | détection ⚠ industriel | — |
| Simulink | propriétaire | payant | API MATLAB | détection | Scilab / Xcos |
| LTspice | propriétaire (freeware) | gratuit | CLI -b (batch, .raw) | détection | — |
| KiCad | GPL-3.0 | gratuit | kicad-cli; API Python | détection | — |
| Proteus | propriétaire | payant | Fichiers de projet | détection | KiCad + ngspice |
| NI Multisim | propriétaire | payant | API (Windows) | détection | LTspice, ngspice |
| QElectroTech | GPL-2.0 | gratuit | Fichiers .qet (XML) | détection | — |

## Statistiques et économie

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Microsoft Excel | propriétaire | payant (licence présente) | API COM Excel.Application; Fichiers .xlsx (lus par Academic Writer) | détection | LibreOffice Calc |
| LibreOffice | MPL-2.0 | gratuit | soffice --headless --convert-to; UNO (Python) | détection | — |
| R | GPL-2.0 | gratuit | CLI Rscript | détection | — |
| RStudio | AGPL-3.0 | gratuit | Utilise R | détection | — |
| Stata | propriétaire | payant | Mode batch (do-files) | détection | R, gretl |
| IBM SPSS Statistics | propriétaire | payant | Syntaxe SPSS; Plugin Python | détection | JASP, jamovi, R |
| gretl | GPL-3.0 | gratuit | CLI gretlcli | détection | — |
| EViews | propriétaire | payant | API COM | détection | gretl, R |
| JASP | AGPL-3.0 | gratuit | Fichiers .jasp | détection | — |
| jamovi | AGPL-3.0 | gratuit | Fichiers .omv | détection | — |
| GnuCash | GPL-2.0 | gratuit | Fichiers XML / SQLite | détection | — |

## Chimie et biologie

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Avogadro | GPL-2.0 | gratuit | Fichiers .cml / .xyz | détection | — |
| ChemDraw | propriétaire | payant | Fichiers .cdx | détection | Avogadro, RDKit |
| Open Babel | GPL-2.0 | gratuit | CLI obabel | détection | — |
| RDKit | BSD | gratuit | Bibliothèque Python | détection | — |
| GROMACS | LGPL-2.1 | gratuit | CLI gmx | détection | — |
| ImageJ / Fiji | domaine public / GPL | gratuit | Macros; mode headless | détection | — |
| Bioconductor | Artistic-2.0 / GPL | gratuit | Paquets R | détection | — |
| Biopython | Biopython (BSD) | gratuit | Bibliothèque Python | détection | — |

## Données et visualisation

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Matplotlib | PSF / BSD | gratuit | Intégré : create_chart | native | — |
| pandas | BSD | gratuit | Bibliothèque Python | détection | — |
| Plotly | MIT | gratuit | Bibliothèque Python / JavaScript | détection | — |
| Power BI Desktop | propriétaire | gratuit (Desktop) | Fichiers .pbix | détection | — |
| Tableau | propriétaire | payant (Tableau Public gratuit) | Fichiers .twb | détection | — |
| Orange Data Mining | GPL-3.0 | gratuit | Workflows .ows; Python | détection | — |
| KNIME Analytics Platform | GPL-3.0 | gratuit | Mode batch | détection | — |
| QGIS | GPL-2.0 | gratuit | qgis_process (CLI); PyQGIS | détection | — |

## Génie civil et architecture

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| ETABS | propriétaire | payant | CSI OAPI (COM) | détection | OpenSees |
| SAP2000 | propriétaire | payant | CSI OAPI (COM) | détection | OpenSees |
| OpenSees | licence académique (BSD-like) | gratuit | openseespy (Python); Tcl | détection | — |
| Autodesk Robot Structural Analysis | propriétaire | payant (licence éducative gratuite) | API COM | détection | OpenSees |
| Autodesk Revit | propriétaire | payant (licence éducative gratuite) | Revit API (.NET); Dynamo | détection | FreeCAD BIM |

## Bureautique

| Logiciel | Licence | Coût | Intégration officielle | Academic Writer | Alternative gratuite |
|---|---|---|---|---|---|
| Microsoft Word | propriétaire | payant (licence présente) | Intégré : export PDF et sommaire par COM | native | — |
| Tesseract OCR | Apache-2.0 | gratuit | Intégré : lecture des PDF scannés | native | — |
| LanguageTool (local) | LGPL-2.1 | gratuit | Intégré : check_language | native | — |

## Règles pour les automatismes industriels

- Privilégier la simulation (PLCSIM, mode simulation de CODESYS, Factory I/O) ; aucune connexion à un automate réel n'est faite par Academic Writer.
- Toute connexion à un équipement réel, tout transfert ou toute modification de programme exige l'autorisation explicite de l'utilisateur et une confirmation dans le logiciel lui-même.
- Sauvegarder le projet et le programme de l'automate avant toute modification.
- Les fonctions de sécurité (arrêt d'urgence, verrouillages, SIL/PL) sont validées par un professionnel qualifié (IEC 61508, IEC 62061, ISO 13849) : jamais par un texte généré.
