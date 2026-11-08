"""LanguageTool LOCAL : démarrage automatique du serveur et vérification de texte.

L'API publique de LanguageTool interdit les requêtes automatisées : seul un serveur local
(``languagetool_url`` limité à localhost) est utilisé. Requêtes en UTF-8 via la bibliothèque
standard (jamais via la ligne de commande, dont l'encodage sous Windows corrompt le cyrillique).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from academic_writer.core.config import Settings

logger = logging.getLogger("academic_writer.languagetool")

LT_LANGUAGES = {"fr": "fr", "ru": "ru-RU", "en": "en-US"}
_CHUNK = 8000
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_DETACHED = 0x00000008 if os.name == "nt" else 0


class LanguageToolError(RuntimeError):
    pass


class LTMatch(BaseModel):
    offset: int
    length: int
    text: str
    message: str
    replacements: list[str]
    rule_id: str
    issue_type: str | None
    category: str


class LTStatus(BaseModel):
    running: bool
    url: str
    installation: str | None
    java: str | None
    message: str


@dataclass
class LanguageToolServer:
    settings: Settings

    @property
    def url(self) -> str:
        return self.settings.languagetool_url

    # --- localisation ---------------------------------------------------------
    def installation_dir(self) -> Path | None:
        base = self.settings.languagetool_dir or self.settings.data_dir / "languagetool"
        if (base / "languagetool-server.jar").is_file():
            return base
        candidates = sorted(base.glob("LanguageTool-*/languagetool-server.jar")) if base.is_dir() else []
        return candidates[-1].parent if candidates else None

    def java_executable(self) -> Path | None:
        if self.settings.java_cmd and self.settings.java_cmd.is_file():
            return self.settings.java_cmd
        java_home = os.environ.get("JAVA_HOME")
        if java_home and (Path(java_home) / "bin" / "java.exe").is_file():
            return Path(java_home) / "bin" / "java.exe"
        found = shutil.which("java")
        if found:
            return Path(found)
        for root in (Path(r"C:\Program Files\Microsoft"), Path(r"C:\Program Files\Eclipse Adoptium"),
                     Path(r"C:\Program Files\Java")):
            if root.is_dir():
                matches = sorted(root.glob("*/bin/java.exe"))
                if matches:
                    return matches[-1]
        return None

    # --- cycle de vie ----------------------------------------------------------
    def is_running(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + "/v2/languages", timeout=2) as response:  # noqa: S310 (URL locale)
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def status(self) -> LTStatus:
        install, java = self.installation_dir(), self.java_executable()
        running = self.is_running()
        if running:
            message = "Serveur LanguageTool local actif."
        elif install is None:
            message = "LanguageTool non installé (dossier <data_dir>/languagetool)."
        elif java is None:
            message = "Java introuvable : installez Java 21 (winget install Microsoft.OpenJDK.21)."
        else:
            message = "Installé mais arrêté : il démarrera automatiquement à la première vérification."
        return LTStatus(running=running, url=self.url, installation=str(install) if install else None,
                        java=str(java) if java else None, message=message)

    def start(self, wait_seconds: int = 60) -> None:
        if self.is_running():
            return
        install, java = self.installation_dir(), self.java_executable()
        if install is None:
            raise LanguageToolError("LanguageTool n'est pas installé dans le dossier de données.")
        if java is None:
            raise LanguageToolError("Java est introuvable : installez Java 21 (winget install Microsoft.OpenJDK.21).")
        port = str(urllib.parse.urlparse(self.url).port or 8081)
        log = (self.settings.logs_dir / "languagetool.log").open("ab")
        process = subprocess.Popen(  # noqa: S603 (arguments fixes, sans shell)
            [str(java), "-Xmx1024m", "-cp", "languagetool-server.jar", "org.languagetool.server.HTTPServer",
             "--port", port],
            cwd=install, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED,
        )
        (install / "server.pid").write_text(str(process.pid), encoding="ascii")
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if self.is_running():
                logger.info("LanguageTool local démarré (pid %d)", process.pid)
                return
            if process.poll() is not None:
                raise LanguageToolError("Le serveur LanguageTool s'est arrêté au démarrage (voir logs/languagetool.log).")
            time.sleep(0.5)
        raise LanguageToolError(f"LanguageTool n'a pas démarré en {wait_seconds} s.")

    def stop(self) -> bool:
        install = self.installation_dir()
        pid_file = install / "server.pid" if install else None
        if not pid_file or not pid_file.exists():
            return False
        pid = int(pid_file.read_text(encoding="ascii").strip() or 0)
        pid_file.unlink(missing_ok=True)
        if pid <= 0:
            return False
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False,  # noqa: S603,S607
                       creationflags=_CREATE_NO_WINDOW)
        return True

    # --- vérification ----------------------------------------------------------
    def check(self, text: str, language: str) -> list[LTMatch]:
        """Vérifie un texte (découpé par paragraphes) ; démarre le serveur si nécessaire."""
        if language not in LT_LANGUAGES:
            raise LanguageToolError(f"Langue non prise en charge : {language}")
        self.start()
        matches: list[LTMatch] = []
        for start, chunk in _chunks(text):
            matches.extend(self._check_chunk(chunk, LT_LANGUAGES[language], start))
        return matches

    def _check_chunk(self, chunk: str, language: str, base: int) -> list[LTMatch]:
        data = urllib.parse.urlencode({"text": chunk, "language": language}).encode("utf-8")
        request = urllib.request.Request(self.url + "/v2/check", data=data, method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 (URL locale)
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise LanguageToolError(f"Erreur de LanguageTool : {exc}") from exc
        result: list[LTMatch] = []
        for match in payload.get("matches", []):
            offset, length = int(match["offset"]), int(match["length"])
            rule = match.get("rule", {})
            result.append(LTMatch(
                offset=base + offset, length=length, text=chunk[offset: offset + length],
                message=match.get("message", ""), replacements=[r["value"] for r in match.get("replacements", [])[:5]],
                rule_id=rule.get("id", ""), issue_type=rule.get("issueType"),
                category=(rule.get("category") or {}).get("id", ""),
            ))
        return result


def _chunks(text: str) -> list[tuple[int, str]]:
    """Découpe aux fins de paragraphe pour rester sous ~8000 caractères par requête."""
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + _CHUNK)
        if end < len(text):
            cut = text.rfind("\n\n", start, end)
            end = cut + 2 if cut > start else end
        chunks.append((start, text[start:end]))
        start = end
    return chunks
