"""Lot 6 : préparation des fichiers, lancement autorisé, résultats, verrous de sécurité."""

from pathlib import Path

import pytest

from academic_writer.core.errors import ValidationFailed
from academic_writer.core.models import DocumentType, Language
from academic_writer.core.software_jobs import _engine_exe
from academic_writer.server.services import Services

SCRIPT = """
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
t = np.linspace(0, 1, 11)
x = np.exp(-2 * t)
with open("resultats.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t", "x"])
    w.writerows([[round(a, 3), round(b, 6)] for a, b in zip(t, x)])
plt.plot(t, x)
plt.savefig("courbe.png")
print("x(1) =", round(float(x[-1]), 6))
"""


@pytest.fixture
def project(services: Services):
    return services.projects.create("Calculs", DocumentType.TP, Language.FR)


def test_locks(services: Services, project) -> None:
    job = services.software_jobs.prepare(project.id, "python", {"calcul.py": "print(1)"})
    with pytest.raises(ValidationFailed, match="software_execution"):
        services.software_jobs.run(project.id, job.job_id, confirm=True)
    services.settings.software_execution = True
    with pytest.raises(ValidationFailed, match="Confirmation"):
        services.software_jobs.run(project.id, job.job_id)
    with pytest.raises(ValidationFailed, match="automatisme industriel"):
        services.software_jobs.prepare(project.id, "tia_portal", {"x.scl": "x"})
    with pytest.raises(ValidationFailed, match="refusé"):
        services.software_jobs.prepare(project.id, "python", {"../evil.py": "x"})
    with pytest.raises(ValidationFailed, match="Extension"):
        services.software_jobs.prepare(project.id, "python", {"script.exe": "x"})


def test_python_job_real_run(services: Services, project) -> None:
    services.settings.software_execution = True
    job = services.software_jobs.prepare(project.id, "python", {"calcul.py": SCRIPT})
    result = services.software_jobs.run(project.id, job.job_id, confirm=True)
    assert result.status == "finished" and result.return_code == 0, result.stderr_tail
    assert "x(1) = 0.135335" in result.stdout_tail and result.executed_by.startswith("Python")
    assert result.tables[0]["rows"][0] == ["t", "x"] and result.images[0].endswith("courbe.png")
    log = (Path(job.folder) / "run-1.log").read_text(encoding="utf-8")
    assert '"return_code": 0' in log and services.software_jobs.get(project.id, job.job_id).status == "finished"


def test_python_job_timeout(services: Services, project) -> None:
    services.settings.software_execution = True
    job = services.software_jobs.prepare(project.id, "python", {"boucle.py": "import time\ntime.sleep(30)"})
    result = services.software_jobs.run(project.id, job.job_id, confirm=True, timeout_s=10)
    assert result.status == "failed" and "durée maximale" in result.stderr_tail


@pytest.mark.skipif(_engine_exe("excel") is None, reason="Microsoft Excel absent")
def test_excel_recalculation_real(services: Services, project) -> None:
    services.settings.software_execution = True
    job = services.software_jobs.prepare(project.id, "excel", {}, table={
        "header": ["Force (N)", "Allongement (mm)", "Raideur (N/mm)"],
        "rows": [["100", "0,5", "=A2/B2"], ["200", "1", "=A3/B3"]], "name": "essai.xlsx"})
    result = services.software_jobs.run(project.id, job.job_id, confirm=True, timeout_s=180)
    assert result.status == "finished", result.stdout_tail
    rows = result.tables[0]["sheets"][0]["rows"]
    assert rows[1][2] == pytest.approx(200.0) and rows[2][2] == pytest.approx(200.0)
    assert result.executed_by == "Microsoft Excel"
