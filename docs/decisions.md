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

## Points ouverts
- **Licence PyMuPDF (AGPL-3.0)** : à trancher avant distribution (licence commerciale Artifex,
  publication AGPL, ou alternative pypdf/pdfplumber). PyMuPDF sera isolé derrière une interface.
- **Correction linguistique** : LanguageTool (LGPL, nécessite Java) à évaluer en Phase 5.
