# Clés d'API (toutes facultatives et gratuites)

Les clés sont enregistrées dans le **Gestionnaire d'identification Windows** (jamais dans un fichier, jamais
dans les journaux) :

```powershell
uv run academic-writer secrets set <service> --clipboard   # copier la clé avant, puis Entrée
uv run academic-writer secrets status                       # sources configurées, sans afficher les clés
uv run academic-writer secrets delete <service>
```

| Service | Statut | Obtention | Effet |
|---|---|---|---|
| `openalex` | FREE_API_KEY | https://openalex.org/settings/api (e-mail, gratuit) | Quota personnel (~1 000 requêtes/jour au lieu d'un budget partagé par adresse IP) |
| `google_books` | FREE_API_KEY | Console Google Cloud, API « Books » (sans facturation) | Recherche de livres |
| `anthropic`, `openai` | PAID_EXCLUDED | — | Fournisseurs payants : facultatifs, désactivés par défaut |

Semantic Scholar, CORE, Europeana et Unpaywall ont été retirés le 2026-11-10 (non opérationnels : voir excluded_paid_providers.md).

Aucun service ne demande de moyen de paiement ; aucune mise à niveau payante n'est déclenchée.
