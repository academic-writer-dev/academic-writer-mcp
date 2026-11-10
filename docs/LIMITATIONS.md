# Limites connues

## Recherche documentaire
- Sources russes : КиберЛенинка par OAI-PMH (métadonnées, sans année ni résumé ; pas de recherche distante :
  moissonner les revues utiles) ; eLIBRARY, РГБ, НЭБ, РНБ, ГПНТБ, ВИНИТИ : pas d'API autorisée → liens manuels ;
  РГБ / НЭБ / УрФУ injoignables depuis l'adresse IP actuelle (à retester sans VPN).
- Asie / Amériques / Afrique : J-STAGE, NDL, OSTI, Érudit, AJOL, SciELO = notices et liens (lecture sur le site) ;
  NDL Search répond parfois lentement (attente maximale 30 s, sans bloquer les autres bases) ; CiNii, Research
  Data Australia (robots.txt), Library of Congress (403), DPLA et Trove (clé), Redalyc : non intégrés.
- BASE (refus par IP), OAPEN et Gallica (HTTP 403), DART-Europe (pas d'API) : non intégrés.
- OpenAlex sans clé : budget gratuit partagé par adresse IP.
- OECD : requêtes de données refusées au client automatisé (HTTP 403) ; IMF et DDB : non intégrés.
- Retirés le 2026-11-10 car non opérationnels : Semantic Scholar (quota saturé), CORE et Europeana (clé non obtenue),
  Unpaywall (adresse non configurée) ; liste complète et raisons : excluded_paid_providers.md.
- Pertinence par mots-clés : des résultats hors sujet peuvent subsister ; des résultats pertinents peuvent être écartés.

## Documents et OCR
- Une confiance OCR élevée ne garantit pas l'exactitude (ex. « м/с » lu « M/c » à 93 %).
- Formules en image et schémas : non interprétés (texte seulement).
- Similarité : comparaison avec les documents du PROJET seulement ; reformulations non détectées ; aucun accès à
  une base anti-plagiat (aucune n'est gratuite et autorisée).

## Calcul
- `validate_calculations` lit les calculs écrits en ligne ; les tableaux de calcul et les formules en image ne sont
  pas relus.
- `solve_problem` exige les formules (elles ne sont jamais choisies à la place de l'utilisateur ou du cours).
- Pas de bibliothèque de calcul spécialisée par métier (béton armé, engrenages ISO 6336…) : formules à fournir.

## Logiciels
- Seuls Python, Excel, Octave, R, Scilab, CalculiX et Maxima peuvent être lancés (s'ils sont installés) ; les autres
  logiciels sont détectés et documentés, sans exécution.

## Présentations
- Pas d'images générées ni recherchées (photographies, icônes, schémas techniques).
- Contrôle visuel automatisé limité aux chevauchements, débordements et contrastes ; l'esthétique reste à juger
  sur les aperçus.

## Normes
- Catalogue volontairement limité (27 normes connues avec certitude, éditions au 2026-11) ; les autres sont
  « non vérifiées ».

## Rédaction
- Qualité rédactionnelle dépendante du moteur (assistant MCP, modèle local ou fournisseur autorisé) ; le serveur
  encadre et contrôle, il ne remplace pas l'encadrement scientifique.
