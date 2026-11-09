"""Gestionnaire central des logiciels scientifiques et techniques.

- Détection réelle sur le poste : programmes installés (registre Windows), exécutables dans le PATH, serveurs
  MCP déjà déclarés dans Claude Desktop (ex. SolidWorks, T-FLEX).
- Catalogue : licence, coût, méthodes d'intégration officielles (API, CLI, COM, échange de fichiers).
- Statut honnête : « native » = Academic Writer exécute réellement le calcul avec ce composant ; « mcp_server »
  = un autre serveur MCP du poste pilote ce logiciel ; « none » = détection et conseils seulement : le serveur
  n'exécute rien dans ce logiciel et ne doit jamais prétendre l'avoir fait.
- Automatismes industriels (PLC, SCADA) : simulation privilégiée, aucune connexion à un automate réel depuis ce
  serveur, confirmation et sauvegarde avant tout transfert, validation par un professionnel.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

CATEGORIES = {
    "math": "Mathématiques et calcul", "cad": "CAO et mécanique", "simulation": "Simulation (éléments finis, CFD)",
    "automation": "Automatisation et électricité", "statistics": "Statistiques et économie",
    "chemistry_biology": "Chimie et biologie", "data": "Données et visualisation",
    "civil": "Génie civil et architecture", "office": "Bureautique",
}
INDUSTRIAL_RULES = [
    "Privilégier la simulation (PLCSIM, mode simulation de CODESYS, Factory I/O) ; aucune connexion à un automate "
    "réel n'est faite par Academic Writer.",
    "Toute connexion à un équipement réel, tout transfert ou toute modification de programme exige l'autorisation "
    "explicite de l'utilisateur et une confirmation dans le logiciel lui-même.",
    "Sauvegarder le projet et le programme de l'automate avant toute modification.",
    "Les fonctions de sécurité (arrêt d'urgence, verrouillages, SIL/PL) sont validées par un professionnel qualifié "
    "(IEC 61508, IEC 62061, ISO 13849) : jamais par un texte généré.",
]


@dataclass(frozen=True)
class Spec:
    id: str
    name: str
    category: str
    license: str
    cost: str  # gratuit, payant, gratuit (usage non commercial), version éducative gratuite...
    methods: tuple[str, ...]
    registry: str = ""  # expression régulière sur DisplayName
    executables: tuple[str, ...] = ()
    native: bool = False  # exécuté réellement par Academic Writer
    industrial: bool = False
    mcp_names: tuple[str, ...] = ()
    free_alternative: str | None = None


CATALOG: tuple[Spec, ...] = (
    # --- mathématiques et calcul
    Spec("sympy", "SymPy / NumPy (Python)", "math", "BSD", "gratuit",
         ("Intégré : solve_math, evaluate_formula, validate_calculations",), native=True),
    Spec("python", "Python", "math", "PSF", "gratuit", ("Scripts .py", "Jupyter"),
         r"^Python \d[\d.]* Core Interpreter|^Python \d[\d.]* \(64-bit\)$", ("python", "py")),
    Spec("jupyter", "Jupyter", "math", "BSD", "gratuit", ("Carnets .ipynb", "CLI jupyter nbconvert --execute"),
         executables=("jupyter",)),
    Spec("matlab", "MATLAB", "math", "propriétaire", "payant",
         ("MATLAB Engine API for Python", "CLI matlab -batch", "fichiers .m / .mat"), r"^MATLAB", ("matlab",),
         free_alternative="GNU Octave"),
    Spec("octave", "GNU Octave", "math", "GPL-3.0", "gratuit", ("CLI octave-cli --eval", "oct2py (Python)"),
         r"GNU Octave", ("octave-cli", "octave")),
    Spec("mathematica", "Wolfram Mathematica", "math", "propriétaire", "payant",
         ("wolframscript (CLI)", "Wolfram Client Library for Python"), r"Mathematica|Wolfram", ("wolframscript",),
         free_alternative="SymPy, SageMath, Maxima"),
    Spec("wolfram_alpha", "Wolfram|Alpha", "math", "service propriétaire", "clé gratuite limitée (non commercial)",
         ("API Web à clé (AppID)",), free_alternative="SymPy (solve_math)"),
    Spec("maple", "Maple", "math", "propriétaire", "payant", ("cmaple (CLI)", "OpenMaple"), r"^Maple", ("cmaple",),
         free_alternative="SymPy, Maxima"),
    Spec("scilab", "Scilab / Xcos", "math", "GPL-2.0", "gratuit", ("CLI scilab-cli -e", "Xcos (schémas blocs)"),
         r"^Scilab", ("scilab-cli", "WScilex-cli")),
    Spec("geogebra", "GeoGebra", "math", "propriétaire (non commercial gratuit)", "gratuit (usage non commercial)",
         ("Fichiers .ggb", "GeoGebra Apps API (JavaScript)"), r"GeoGebra"),
    Spec("sagemath", "SageMath", "math", "GPL-3.0", "gratuit", ("CLI sage -c",), r"SageMath", ("sage",)),
    Spec("maxima", "Maxima / wxMaxima", "math", "GPL-2.0", "gratuit", ("CLI maxima --batch-string",), r"Maxima",
         ("maxima",)),
    # --- CAO
    Spec("solidworks", "SOLIDWORKS", "cad", "propriétaire", "payant (licence étudiante)",
         ("API COM SldWorks.Application (VBA, C#, Python pywin32)", "Macros .swp", "Échange STEP / IGES / STL"),
         r"^SOLIDWORKS(?! (?:Login|eDrawings))|^SOLIDWORKS \d{4}", ("SLDWORKS",), mcp_names=("solidworks",),
         free_alternative="FreeCAD"),
    Spec("edrawings", "eDrawings", "cad", "propriétaire", "gratuit (visionneuse)", ("Visualisation de fichiers CAO",),
         r"eDrawings"),
    Spec("inventor", "Autodesk Inventor", "cad", "propriétaire", "payant (licence éducative gratuite)",
         ("API COM Inventor.Application", "iLogic", "Échange STEP / IGES"), r"^Autodesk Inventor (?:Professional|Private) \d",
         free_alternative="FreeCAD"),
    Spec("fusion360", "Autodesk Fusion", "cad", "propriétaire", "gratuit (usage personnel limité)",
         ("API Python interne", "Échange STEP / F3D"), r"Autodesk Fusion"),
    Spec("freecad", "FreeCAD", "cad", "LGPL-2.1", "gratuit", ("API Python", "CLI FreeCADCmd", "STEP / IGES / STL"),
         r"^FreeCAD", ("FreeCADCmd", "freecadcmd")),
    Spec("catia", "CATIA", "cad", "propriétaire", "payant", ("CAA / automation COM",), r"^CATIA", free_alternative="FreeCAD"),
    Spec("nx", "Siemens NX", "cad", "propriétaire", "payant", ("NX Open (Python, C#)",), r"Siemens NX",
         free_alternative="FreeCAD"),
    Spec("creo", "PTC Creo", "cad", "propriétaire", "payant", ("Creo Toolkit / J-Link",), r"^(?:PTC )?Creo",
         free_alternative="FreeCAD"),
    Spec("autocad", "AutoCAD", "cad", "propriétaire", "payant (licence éducative gratuite)",
         ("API COM / ActiveX", "AutoLISP", "Échange DXF / DWG"), r"^AutoCAD", free_alternative="LibreCAD, QCAD"),
    Spec("tflex", "T-FLEX CAD", "cad", "propriétaire", "payant (version éducative gratuite)",
         ("T-FLEX Open API (.NET)", "Échange STEP / DXF"), r"^T-FLEX CAD", mcp_names=("tflex", "tflex-harness"),
         free_alternative="FreeCAD"),
    Spec("kompas", "КОМПАС-3D", "cad", "propriétaire", "payant (версия для учебы)", ("API КОМПАС (COM)",),
         r"КОМПАС|KOMPAS", free_alternative="FreeCAD"),
    Spec("openscad", "OpenSCAD", "cad", "GPL-2.0", "gratuit", ("CLI openscad -o (STL)",), r"^OpenSCAD", ("openscad",)),
    # --- simulation
    Spec("ansys", "Ansys", "simulation", "propriétaire", "payant (Student gratuit limité)",
         ("PyAnsys (PyMAPDL, PyFluent)", "APDL en mode batch"), r"^ANSYS|^Ansys", free_alternative="CalculiX, Code_Aster, Elmer"),
    Spec("abaqus", "Abaqus", "simulation", "propriétaire", "payant (Learning Edition gratuite limitée)",
         ("Scripts Python", "Fichiers .inp"), r"Abaqus", free_alternative="CalculiX (format .inp proche)"),
    Spec("calculix", "CalculiX", "simulation", "GPL-2.0", "gratuit", ("CLI ccx (fichiers .inp)",), r"CalculiX", ("ccx",)),
    Spec("code_aster", "Code_Aster / Salome-Meca", "simulation", "GPL-3.0 / LGPL", "gratuit",
         ("Fichiers .comm / .export", "Salome (Python)"), r"[Ss]alome|Code.Aster", ("as_run", "run_aster")),
    Spec("openfoam", "OpenFOAM", "simulation", "GPL-3.0", "gratuit", ("CLI (Linux / WSL)",), r"OpenFOAM",
         ("simpleFoam", "blockMesh")),
    Spec("elmer", "Elmer FEM", "simulation", "GPL-2.0", "gratuit", ("CLI ElmerSolver (.sif)",), r"^Elmer", ("ElmerSolver",)),
    # --- automatisation et électricité
    Spec("tia_portal", "Siemens TIA Portal", "automation", "propriétaire", "payant",
         ("TIA Portal Openness (.NET, groupe « Siemens TIA Openness »)", "PLCSIM (simulation)", "Export SCL / XML"),
         r"^Totally Integrated Automation Portal|TIA Portal Single SetupPackage", industrial=True),
    Spec("codesys", "CODESYS", "automation", "propriétaire", "gratuit (extensions payantes)",
         ("Scripting Python (IronPython)", "Mode simulation", "Export PLCopenXML"), r"^CODESYS", industrial=True,
         free_alternative="OpenPLC"),
    Spec("openplc", "OpenPLC", "automation", "GPL-3.0", "gratuit", ("Éditeur IEC 61131-3", "Runtime web"), r"OpenPLC",
         industrial=True),
    Spec("factory_io", "Factory I/O", "automation", "propriétaire", "payant (essai)", ("SDK .NET", "Simulation 3D"),
         r"Factory I/O", industrial=True),
    Spec("simulink", "Simulink", "automation", "propriétaire", "payant", ("API MATLAB",), r"Simulink",
         free_alternative="Scilab / Xcos"),
    Spec("ltspice", "LTspice", "automation", "propriétaire (freeware)", "gratuit", ("CLI -b (batch, .raw)",), r"LTspice",
         ("LTspice", "XVIIx64")),
    Spec("kicad", "KiCad", "automation", "GPL-3.0", "gratuit", ("kicad-cli", "API Python"), r"^KiCad", ("kicad-cli",)),
    Spec("proteus", "Proteus", "automation", "propriétaire", "payant", ("Fichiers de projet",), r"Proteus",
         free_alternative="KiCad + ngspice"),
    Spec("multisim", "NI Multisim", "automation", "propriétaire", "payant", ("API (Windows)",), r"Multisim",
         free_alternative="LTspice, ngspice"),
    Spec("qelectrotech", "QElectroTech", "automation", "GPL-2.0", "gratuit", ("Fichiers .qet (XML)",), r"QElectroTech"),
    # --- statistiques et économie
    Spec("excel", "Microsoft Excel", "statistics", "propriétaire", "payant (licence présente)",
         ("API COM Excel.Application", "Fichiers .xlsx (lus par Academic Writer)"), r"^Microsoft Excel|Office (?:Professionnel|Professional)",
         free_alternative="LibreOffice Calc"),
    Spec("libreoffice", "LibreOffice", "statistics", "MPL-2.0", "gratuit", ("soffice --headless --convert-to", "UNO (Python)"),
         r"^LibreOffice", ("soffice",)),
    Spec("r", "R", "statistics", "GPL-2.0", "gratuit", ("CLI Rscript",), r"^R for Windows", ("Rscript",)),
    Spec("rstudio", "RStudio", "statistics", "AGPL-3.0", "gratuit", ("Utilise R",), r"^RStudio"),
    Spec("stata", "Stata", "statistics", "propriétaire", "payant", ("Mode batch (do-files)",), r"^Stata",
         free_alternative="R, gretl"),
    Spec("spss", "IBM SPSS Statistics", "statistics", "propriétaire", "payant", ("Syntaxe SPSS", "Plugin Python"),
         r"SPSS", free_alternative="JASP, jamovi, R"),
    Spec("gretl", "gretl", "statistics", "GPL-3.0", "gratuit", ("CLI gretlcli",), r"^gretl", ("gretlcli",)),
    Spec("eviews", "EViews", "statistics", "propriétaire", "payant", ("API COM",), r"EViews", free_alternative="gretl, R"),
    Spec("jasp", "JASP", "statistics", "AGPL-3.0", "gratuit", ("Fichiers .jasp",), r"^JASP"),
    Spec("jamovi", "jamovi", "statistics", "AGPL-3.0", "gratuit", ("Fichiers .omv",), r"^jamovi"),
    Spec("gnucash", "GnuCash", "statistics", "GPL-2.0", "gratuit", ("Fichiers XML / SQLite",), r"^GnuCash"),
    # --- chimie et biologie
    Spec("avogadro", "Avogadro", "chemistry_biology", "GPL-2.0", "gratuit", ("Fichiers .cml / .xyz",), r"^Avogadro"),
    Spec("chemdraw", "ChemDraw", "chemistry_biology", "propriétaire", "payant", ("Fichiers .cdx",), r"ChemDraw",
         free_alternative="Avogadro, RDKit"),
    Spec("openbabel", "Open Babel", "chemistry_biology", "GPL-2.0", "gratuit", ("CLI obabel",), r"Open ?Babel", ("obabel",)),
    Spec("rdkit", "RDKit", "chemistry_biology", "BSD", "gratuit", ("Bibliothèque Python",)),
    Spec("gromacs", "GROMACS", "chemistry_biology", "LGPL-2.1", "gratuit", ("CLI gmx",), r"GROMACS", ("gmx",)),
    Spec("imagej", "ImageJ / Fiji", "chemistry_biology", "domaine public / GPL", "gratuit", ("Macros", "mode headless"),
         r"^ImageJ|^Fiji", ("ImageJ-win64",)),
    Spec("bioconductor", "Bioconductor", "chemistry_biology", "Artistic-2.0 / GPL", "gratuit", ("Paquets R",)),
    Spec("biopython", "Biopython", "chemistry_biology", "Biopython (BSD)", "gratuit", ("Bibliothèque Python",)),
    # --- données et visualisation
    Spec("matplotlib", "Matplotlib", "data", "PSF / BSD", "gratuit", ("Intégré : create_chart",), native=True),
    Spec("pandas", "pandas", "data", "BSD", "gratuit", ("Bibliothèque Python",)),
    Spec("plotly", "Plotly", "data", "MIT", "gratuit", ("Bibliothèque Python / JavaScript",)),
    Spec("powerbi", "Power BI Desktop", "data", "propriétaire", "gratuit (Desktop)", ("Fichiers .pbix",), r"Power BI"),
    Spec("tableau", "Tableau", "data", "propriétaire", "payant (Tableau Public gratuit)", ("Fichiers .twb",), r"^Tableau"),
    Spec("orange", "Orange Data Mining", "data", "GPL-3.0", "gratuit", ("Workflows .ows", "Python"), r"^Orange"),
    Spec("knime", "KNIME Analytics Platform", "data", "GPL-3.0", "gratuit", ("Mode batch",), r"^KNIME", ("knime",)),
    Spec("qgis", "QGIS", "data", "GPL-2.0", "gratuit", ("qgis_process (CLI)", "PyQGIS"), r"^QGIS", ("qgis_process-qgis",)),
    # --- génie civil et architecture
    Spec("etabs", "ETABS", "civil", "propriétaire", "payant", ("CSI OAPI (COM)",), r"ETABS", free_alternative="OpenSees"),
    Spec("sap2000", "SAP2000", "civil", "propriétaire", "payant", ("CSI OAPI (COM)",), r"SAP2000", free_alternative="OpenSees"),
    Spec("opensees", "OpenSees", "civil", "licence académique (BSD-like)", "gratuit", ("openseespy (Python)", "Tcl"),
         r"OpenSees", ("OpenSees",)),
    Spec("robot", "Autodesk Robot Structural Analysis", "civil", "propriétaire", "payant (licence éducative gratuite)",
         ("API COM",), r"Robot Structural Analysis", free_alternative="OpenSees"),
    Spec("revit", "Autodesk Revit", "civil", "propriétaire", "payant (licence éducative gratuite)",
         ("Revit API (.NET)", "Dynamo"), r"^Autodesk Revit \d", free_alternative="FreeCAD BIM"),
    # --- bureautique (intégrations natives)
    Spec("word", "Microsoft Word", "office", "propriétaire", "payant (licence présente)",
         ("Intégré : export PDF et sommaire par COM",), r"^Microsoft Word|Office (?:Professionnel|Professional)",
         native=True),
    Spec("tesseract", "Tesseract OCR", "office", "Apache-2.0", "gratuit", ("Intégré : lecture des PDF scannés",),
         r"^Tesseract", ("tesseract",), native=True),
    Spec("languagetool", "LanguageTool (local)", "office", "LGPL-2.1", "gratuit", ("Intégré : check_language",),
         native=True),
)


class SoftwareStatus(BaseModel):
    id: str
    name: str
    category: str
    category_label: str
    detected: bool
    version: str | None = None
    location: str | None = None
    evidence: list[str] = Field(default_factory=list, description="Ce qui prouve la présence (registre, PATH, MCP).")
    license: str
    cost: str
    integration_methods: list[str]
    academic_writer_integration: str = Field(
        description="native : exécuté réellement par Academic Writer ; mcp_server : piloté par un autre serveur MCP "
                    "déclaré ; none : détection et conseils seulement, aucune exécution.")
    industrial_safety: list[str] = Field(default_factory=list)
    free_alternative: str | None = None


class SoftwareReport(BaseModel):
    platform: str
    detected_count: int
    software: list[SoftwareStatus]
    mcp_servers: list[str] = Field(description="Serveurs MCP déclarés dans Claude Desktop.")
    notices: list[str]


@dataclass
class _Installed:
    names: list[tuple[str, str | None, str | None]] = field(default_factory=list)  # (nom, version, dossier)


def _registry_programs() -> list[tuple[str, str | None, str | None]]:
    if sys.platform != "win32":
        return []
    import winreg

    found: list[tuple[str, str | None, str | None]] = []
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        with winreg.OpenKey(key, winreg.EnumKey(key, index)) as sub:
                            def value(name: str) -> str | None:
                                try:
                                    return str(winreg.QueryValueEx(sub, name)[0]) or None
                                except OSError:
                                    return None
                            name = value("DisplayName")
                            if name:
                                found.append((name, value("DisplayVersion"), value("InstallLocation")))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _mcp_servers() -> list[str]:
    from academic_writer.core.maintenance import desktop_config_candidates

    names: set[str] = set()
    for path in desktop_config_candidates():
        try:
            names |= set(json.loads(path.read_text(encoding="utf-8")).get("mcpServers", {}))
        except (OSError, ValueError):
            continue
    return sorted(names)


def detect(category: str | None = None, *, programs: list[tuple[str, str | None, str | None]] | None = None,
           which=shutil.which, mcp_servers: list[str] | None = None, only_detected: bool = False) -> SoftwareReport:
    if category and category not in CATEGORIES:
        raise ValueError(f"Catégorie inconnue : {', '.join(CATEGORIES)}.")
    programs = _registry_programs() if programs is None else programs
    servers = _mcp_servers() if mcp_servers is None else mcp_servers
    results: list[SoftwareStatus] = []
    for spec in CATALOG:
        if category and spec.category != category:
            continue
        evidence: list[str] = []
        version = location = None
        if spec.registry:
            pattern = re.compile(spec.registry, re.IGNORECASE)
            for name, ver, loc in programs:
                if pattern.search(name):
                    evidence.append(f"installé : {name}" + (f" ({ver})" if ver else ""))
                    version, location = version or ver, location or loc
        for exe in spec.executables:
            path = which(exe)
            if path:
                evidence.append(f"exécutable : {path}")
                location = location or os.path.dirname(path)
                break
        server = next((s for s in servers if s.casefold() in {m.casefold() for m in spec.mcp_names}), None)
        if server:
            evidence.append(f"serveur MCP déclaré : {server}")
        native = spec.native
        detected = bool(evidence) or native
        if native and not evidence:
            evidence.append("composant d'Academic Writer")
        status = "native" if native else ("mcp_server" if server else "none")
        if only_detected and not detected:
            continue
        results.append(SoftwareStatus(
            id=spec.id, name=spec.name, category=spec.category, category_label=CATEGORIES[spec.category],
            detected=detected, version=version, location=location, evidence=evidence[:4], license=spec.license,
            cost=spec.cost, integration_methods=list(spec.methods), academic_writer_integration=status,
            industrial_safety=list(INDUSTRIAL_RULES) if spec.industrial else [], free_alternative=spec.free_alternative))
    notices = [
        "« none » : Academic Writer n'exécute rien dans ce logiciel ; il peut préparer données, scripts ou fichiers "
        "d'échange que l'utilisateur lance lui-même. Ne jamais annoncer un calcul « fait dans » ce logiciel.",
        "Les calculs d'Academic Writer sont faits par SymPy / NumPy et présentés comme tels.",
    ]
    if any(s.industrial_safety and s.detected for s in results):
        notices.append("Logiciel d'automatisme industriel détecté : règles de sécurité industrielle applicables.")
    return SoftwareReport(platform=sys.platform, detected_count=sum(s.detected for s in results), software=results,
                          mcp_servers=servers, notices=notices)
