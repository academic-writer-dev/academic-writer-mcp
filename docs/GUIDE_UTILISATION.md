# Guide d'utilisation (simple)

Le serveur s'utilise **en parlant à Claude** (Claude Desktop, Claude Code ou VS Code) : on écrit ce qu'on veut en
français, en russe ou en anglais, et Claude appelle les bons outils du serveur. Il n'y a aucune commande à taper.

## Avant de commencer

1. Claude doit être ouvert après l'installation (voir [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md)).
2. Vérification : écrire « **Ping le serveur academic-writer** ». Réponse attendue : le serveur répond avec sa version.
3. Pour chercher dans les bibliothèques, le mode connecté doit être actif (déjà fait sur ce poste).

## Le parcours type (TP, TD, mémoire de licence, master, doctorat)

| Étape | Ce qu'on écrit à Claude (exemples) |
|---|---|
| 1. Créer le projet | « Crée un projet *Mémoire de master* intitulé *Dimensionnement d'un réducteur à engrenages*, en français. » |
| 2. Donner les consignes | « Importe les consignes `C:\Users\…\Documents\consignes.pdf` dans le projet. » puis « Analyse les consignes. » |
| 3. Profil du professeur (facultatif) | « Crée le profil du professeur Martin : plan imposé Introduction, État de l'art, Modélisation, Conclusion ; Times New Roman 12 ; références APA. » |
| 4. Dossier de recherche | « Fais le dossier de recherche sur le thème *dimensionnement d'un réducteur à engrenages* (cherche aussi en anglais). » → fichier Word avec les sources réelles, les consignes, le plan et les normes |
| 5. Choisir les sources | « Enregistre les sources 1, 3 et 5 du dossier. » |
| 6. Plan | « Crée le plan », puis « Valide le plan ». |
| 7. Rédaction | « Rédige l'introduction en citant les sources enregistrées. » Relire, puis « Accepte cette version » ou demander une correction. |
| 8. Calculs | « Vérifie les calculs de la section 3. » ou « Résous ce problème avec les formules du cours : … » |
| 9. Contrôle final | « Fais l'audit qualité final. » → calculs, sources, consignes, normes internationales, longueur |
| 10. Document final | « Exporte le document en Word et en PDF. » → mise en forme du professeur appliquée automatiquement |
| 11. Présentation | « Prépare la présentation de soutenance en 12 diapositives, style sobre, avec les questions possibles du jury. » |

## Recherches seules

- « Trouve des articles sur la fatigue des engrenages » : le domaine est reconnu tout seul (génie mécanique
  prioritaire) ; 27 bases sont interrogées (dépôts russophones pour une recherche en cyrillique).
- « Cherche seulement en génie mécanique : … » (recherche stricte) ; « … sans spécialisation » (recherche générale).
- « Cherche dans AJOL / SciELO / J-STAGE / КиберЛенинка : … » pour une région précise.
- « Quelle est la valeur de la constante d'Avogadro ? » (NIST) ; « PIB de la France en 2021 » (Banque mondiale, Eurostat).
- « Ce DOI a-t-il été rétracté ? » (Crossref).

## Guides de rédaction

- « Trouve des guides pour rédiger un compte rendu de TP » ; « … un mémoire de master, en russe » ; « … un projet
  de cours de Детали машин ». Le serveur cherche les méthodiques des universités (УрФУ, БНТУ, ТГУ Тольятти), les
  manuels ouverts et les guides publiés. Les consignes de votre établissement priment toujours.
- Une fois par mois : « Mets à jour les manuels ouverts » (≈ 2 minutes).

## Contrôler un document déjà écrit

« Importe `rapport.docx` », puis : « Contrôle la mise en forme selon les consignes », « Contrôle les normes de
présentation », « Vérifie les calculs », « Vérifie les références », « Compare avec la version précédente ».

## Règles que le serveur applique toujours

- Aucune référence, donnée ou citation inventée ; une source n'est citée qu'après avoir été enregistrée.
- Les consignes du professeur passent avant tout (mise en forme, plan, longueur, style des références).
- Les documents originaux ne sont jamais modifiés (copies dans le dossier `exports` du projet).
- Les textes intégraux ne sont téléchargés que s'ils sont en libre accès légal.

## Où sont les fichiers ?

Dossier des données : `D:\AcademicWriter-Data\projects\<projet>\exports` (dossiers de recherche, documents Word et
PDF, rapports de contrôle). Sauvegarde : « Fais une sauvegarde complète. »
