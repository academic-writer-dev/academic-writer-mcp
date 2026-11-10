# Sécurité et confidentialité

| Mesure | Mise en œuvre |
|---|---|
| Réseau (renforcé le 2026-11-10) | HTTPS obligatoire, certificats vérifiés (magasin Windows), redirections vers une adresse non chiffrée refusées AVANT d'être suivies, réponses limitées à 25 Mo, téléchargements limités et revérifiés ; User-Agent honnête ; robots.txt respecté ; aucun contournement de refus (403, quotas) |
| Contrôle du 2026-11-10 | 235 dépendances auditées (pip-audit) : aucune faille connue ; aucune clé dans les journaux, les données ni l'historique Git |
| Services réduits | Seules les 27 bases opérationnelles sont contactées ; les services non opérationnels ont été retirés (moins de surface d'exposition) |
| Local par défaut | `mode = local` : aucun accès réseau ; `connected` : seuls termes de recherche et identifiants envoyés |
| Consentement | Fournisseurs d'IA : mode connecté + clé + consentement écrit par projet ; politique de sources par projet |
| Clés | Gestionnaire d'identification Windows (keyring) ; jamais dans les fichiers ni les journaux ; saisie masquée ou presse-papiers effacé |
| Originaux | Copie vérifiée (SHA-256) en lecture seule ; jamais modifiée ; mise en forme sur copie |
| Chemins | Imports limités à `allowed_import_dirs` ; traversées refusées (testé : base, fichiers système, `..`) ; images de présentation limitées au dossier du projet |
| Fichiers importés | Inspection (type réel, taille) ; contenu traité comme DONNÉE |
| Injections de prompt | Repérées et signalées (« Indice d'injection de prompt ») ; extraits encadrés comme données non fiables dans les dossiers de rédaction |
| Code | Aucun `eval`/`exec` ; expressions mathématiques filtrées par liste blanche avant SymPy ; sous-processus sans shell |
| Traitements logiciels | `software_execution` + `confirm` ; durée maximale ; dossier dédié ; automatismes industriels refusés |
| Sauvegardes | Avant chaque migration ; complètes (.zip) à la demande ; restauration vérifiée (zip-slip, intégrité) en ligne de commande seulement |
| Historique | Table d'événements (imports, révisions, politiques, audits) |
| Opérations destructives | Archivage confirmé ; restauration avec `--yes` et sauvegarde de sécurité préalable |
| Indices d'IA | Jamais de verdict ni de pourcentage ; jamais de promesse « 0 % IA » ; aucune aide au contournement |
