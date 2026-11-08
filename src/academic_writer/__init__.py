"""Academic Writer MCP — serveur MCP local d'assistance à la rédaction académique."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("academic-writer")
except PackageNotFoundError:  # exécution depuis les sources sans installation
    __version__ = "0.0.0"


def main() -> None:
    """Point d'entrée de la commande `academic-writer` : lance le serveur MCP (stdio)."""
    from academic_writer.server.app import run

    run()
