<!-- Fichier généré par scripts/generate_docs.py : ne pas modifier à la main. -->

# Fournisseurs exclus ou non automatisés

Aucun de ces services n'est interrogé automatiquement. Ceux marqués `manual_link` sont proposés comme liens à ouvrir par l'utilisateur.

| Fournisseur | Statut | Raison | Traitement |
|---|---|---|---|
| BASE (Bielefeld) | `UNVERIFIED_EXCLUDED` | refus « Access denied for IP address » ; accès API sur autorisation par adresse IP | excluded |
| RePEc / IDEAS | `UNAVAILABLE` | non intégré ; pas d'API publique de recherche | manual_link |
| OAPEN Library | `UNAVAILABLE` | HTTP 403 pour les requêtes automatisées ; — | manual_link |
| Gallica / BnF | `UNAVAILABLE` | HTTP 403 (SRU) depuis ce poste ; — | manual_link |
| DART-Europe | `UNAVAILABLE` | pages web uniquement ; pas d'API | manual_link |
| eLIBRARY.RU / РИНЦ | `UNAVAILABLE` | lien de recherche (via Яндекс) ; aucune extraction ; pas d'API publique | manual_link |
| КиберЛенинка | `UNVERIFIED_EXCLUDED` | lien de recherche ; aucune extraction ; pas d'API officielle documentée | manual_link |
| РГБ (dont Электронная библиотека диссертаций) | `UNAVAILABLE` | lien de recherche ; pas d'API publique | manual_link |
| РНБ | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |
| НЭБ | `UNVERIFIED_EXCLUDED` | non intégré ; API sur demande (conditions non vérifiées) | manual_link |
| ГПНТБ России | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |
| ВИНИТИ РАН | `PAID_EXCLUDED` | non intégré ; accès sur abonnement | excluded |
| Федеральная электронная медицинская библиотека | `UNAVAILABLE` | non intégré ; pas d'API publique | manual_link |

Fournisseurs d'IA payants (Anthropic, OpenAI) : présents mais **désactivés par défaut** (mode connecté + clé + consentement écrit du projet) ; jamais obligatoires.
