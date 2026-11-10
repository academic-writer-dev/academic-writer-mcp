<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Fournisseurs exclus ou non automatisés

Aucun de ces services n'est interrogé automatiquement. Ceux marqués `manual_link` sont proposés comme liens à ouvrir par l'utilisateur.

| Fournisseur | Statut | Raison | Traitement |
|---|---|---|---|
| BASE (Bielefeld) | `UNVERIFIED_EXCLUDED` | refus « Access denied for IP address » ; accès API sur autorisation par adresse IP | excluded |
| RePEc / IDEAS | `UNAVAILABLE` | non intégré ; pas d'API publique de recherche | manual_link |
| OECD Data (SDMX) | `UNAVAILABLE` | liste des jeux accessible ; requêtes de données refusées au client automatisé (HTTP 403) ; aucune | manual_link |
| OAPEN Library | `UNAVAILABLE` | HTTP 403 pour les requêtes automatisées ; — | manual_link |
| Gallica / BnF | `UNAVAILABLE` | HTTP 403 (SRU) depuis ce poste ; — | manual_link |
| DART-Europe | `UNAVAILABLE` | pages web uniquement ; pas d'API | manual_link |
| CiNii Research (NII) | `UNAVAILABLE` | recherche interdite aux robots (robots.txt) ; ses notices passent par NDL Search ; — | manual_link |
| engrXiv (prépublications d'ingénierie) | `UNAVAILABLE` | API OSF interdite aux robots (robots.txt) ; — | manual_link |
| Library of Congress | `UNAVAILABLE` | HTTP 403 au client automatisé (non contourné) ; — | manual_link |
| Redalyc | `UNAVAILABLE` | OAI-PMH sans résultat ; revues souvent présentes dans DOAJ et OpenAlex ; — | manual_link |
| Research Data Australia | `UNAVAILABLE` | API sous /registry/, interdite aux robots (robots.txt) ; — | manual_link |
| eLIBRARY.RU / РИНЦ | `UNAVAILABLE` | lien de recherche (via Яндекс) ; aucune extraction ; pas d'API publique | manual_link |
| РГБ (dont Электронная библиотека диссертаций) | `UNAVAILABLE` | lien de recherche ; pas d'API publique | manual_link |
| РНБ | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |
| НЭБ | `UNVERIFIED_EXCLUDED` | non intégré ; API sur demande (conditions non vérifiées) | manual_link |
| ГПНТБ России | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |
| ВИНИТИ РАН | `PAID_EXCLUDED` | non intégré ; accès sur abonnement | excluded |
| Федеральная электронная медицинская библиотека | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |

Fournisseurs d'IA payants (Anthropic, OpenAI) : présents mais **désactivés par défaut** (mode connecté + clé + consentement écrit du projet) ; jamais obligatoires.
