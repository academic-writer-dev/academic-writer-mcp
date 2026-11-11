<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Services retirés du serveur

Retirés le 2026-11-10 après test réel : ils ne sont plus ni interrogés, ni listés comme connectés. Ils pourront être rebranchés si leur situation change (clé gratuite obtenue, accès autorisé).

| Service | Raison du retrait |
|---|---|
| Semantic Scholar | quota public saturé : refus (HTTP 429) pour 9 recherches sur 9 ; clé réservée aux adresses institutionnelles |
| CORE | clé gratuite obligatoire, jamais obtenue (formulaire refusé à l'automatisation) |
| Europeana | clé gratuite obligatoire, jamais obtenue |
| Unpaywall | adresse e-mail obligatoire dans chaque requête : non configurée |
| BASE (Bielefeld) | accès refusé par adresse IP |
| OAPEN, Gallica, Library of Congress | HTTP 403 aux requêtes automatisées (jamais contourné) |
| OECD | requêtes de données refusées au client automatisé (HTTP 403) |
| CiNii Research, Research Data Australia, engrXiv | recherche interdite aux robots par robots.txt |
| DPLA, Trove, DDB | clé personnelle obligatoire, non obtenue |
| Redalyc | interface OAI-PMH sans résultat (revues présentes dans DOAJ et OpenAlex) |
| DART-Europe, RePEc, IMF | pas d'interface automatisée exploitable |
| eLIBRARY, РГБ, НЭБ, РНБ, ГПНТБ, ФЭМБ | pas d'API publique autorisée ; РГБ et НЭБ injoignables depuis le poste |
| ВИНИТИ РАН | accès payant |
| DOAB, OAPEN (livres en libre accès) | HTTP 403 aux requêtes automatisées (2026-11-11 ; jamais contourné) |
| Shodhganga (Inde), KoreaScience (Corée) | connexion refusée depuis le poste (délai de négociation TLS dépassé) |
| Garuda (Indonésie), КПИ et ХПИ (Ukraine) | adresse introuvable depuis le poste |
| ТПУ, БГУ, КФУ, Самарский университет, СФУ, ЮУрГУ | pas d'interface de recherche exploitable ou HTTP 403 |
| СПбГУ | dépôt joignable mais résultats sans rapport avec l'ingénierie |

Fournisseurs d'IA payants (Anthropic, OpenAI) : présents mais **désactivés par défaut** (mode connecté + clé + consentement écrit du projet) ; jamais obligatoires.
