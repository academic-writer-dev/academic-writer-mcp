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
| `core` | FREE_API_KEY | https://core.ac.uk/services/api (inscription) | Agrégateur de dépôts en libre accès |
| `semantic_scholar` | FREE_API_KEY | Formulaire du site (adresse institutionnelle exigée) | Lève le quota public saturé |
| `anthropic`, `openai` | PAID_EXCLUDED | — | Fournisseurs payants : facultatifs, désactivés par défaut |

Unpaywall n'a pas de clé : il exige une adresse e-mail dans chaque requête (`unpaywall_email` dans config.toml).

Aucun service ne demande de moyen de paiement ; aucune mise à niveau payante n'est déclenchée.
