# Profils disciplinaires

Academic Writer adapte ses vérifications et ses gabarits à la discipline grâce à des
**profils** au format YAML.

## Profils intégrés (17)

| Identifiant | Discipline | Parent | Risque |
|---|---|---|---|
| `generaliste` | Socle commun (règles, normes générales) | — | normal |
| `genie_mecanique` | Génie mécanique, RDM, TMM | generaliste | normal |
| `fabrication_mecanique` | Fabrication, usinage, métrologie | genie_mecanique | normal |
| `maintenance_industrielle` | Maintenance, fiabilité | genie_mecanique | normal |
| `automatisation` | Automatique, API, régulation | generaliste | normal |
| `informatique` | Informatique, génie logiciel | generaliste | normal |
| `electronique` | Électronique, électrotechnique | generaliste | normal |
| `genie_civil` | Génie civil, structures | generaliste | normal |
| `mathematiques` | Mathématiques | generaliste | normal |
| `physique` | Physique | generaliste | normal |
| `chimie` | Chimie | generaliste | normal |
| `biologie` | Biologie | generaliste | normal |
| `medecine` | Médecine, santé | generaliste | **élevé** |
| `droit` | Droit | generaliste | **élevé** |
| `economie` | Économie | generaliste | normal |
| `gestion` | Gestion, management | generaliste | normal |
| `sciences_humaines` | Sciences humaines et sociales | generaliste | normal |

Pour les profils à risque élevé, chaque gabarit et chaque affectation affiche un
avertissement imposant la validation par un professionnel qualifié.

## Conventions de présentation

| Code | Référentiel | Exemples |
|---|---|---|
| `ru` | ГОСТ / ЕСКД | ГОСТ 7.32-2017, ГОСТ 2.105-2019, ГОСТ Р 7.0.11-2011, ГОСТ Р 7.0.100-2018 |
| `fr` | NF / EN | NF Z 41-006, NF EN 16271, NF EN 13460, NF ISO 690 |
| `intl` | ISO / IEC / revues | ISO 7144, ISO 690, ANSI/NISO Z39.18, IMRaD |

Par défaut, la convention suit la langue du projet (ru → `ru`, fr → `fr`, en → `intl`).
On la change avec `set_project_domain(..., convention="ru")`.
**Les normes citées sont indicatives : vérifiez toujours l'édition en vigueur.** Les
consignes de votre établissement priment sur les gabarits.

## Créer ou modifier un profil

Placez un fichier `.yaml` dans `D:\AcademicWriter-Data\profiles\` (soit `<data_dir>\profiles`),
puis appelez l'outil `reload_domain_profiles`. Un profil portant le même `id` qu'un profil
intégré le remplace. Un profil invalide est ignoré et signalé dans `load_errors`.

```yaml
id: tmm                        # minuscules, chiffres, _
parent: genie_mecanique        # hérite terminologie, règles, normes, méthodologie
names: {fr: "Théorie des mécanismes", ru: "Теория механизмов и машин", en: "Theory of machines"}
keywords:                      # détection ; « * » = préfixe (flexions), casse/accents ignorés
  ru: ["синтез* механизм*", "кулачков*", "маховик*"]
  fr: ["came*", "volant d'inertie"]
terminology:
  - {id: cam, fr: "came", ru: "кулачок", en: "cam"}
document_sections:             # par type de document, famille ou "*" (tous)
  projet:
    - {id: synthesis, after: analysis, title: {fr: "Synthèse du mécanisme", ru: "Синтез механизма", en: "Mechanism synthesis"}}
validation_rules:
  - {id: flywheel, severity: warning, description: {fr: "Coefficient d'irrégularité justifié.", ru: "Обоснован коэффициент неравномерности.", en: "Justified speed fluctuation coefficient."}}
standards:
  - {code: "ГОСТ 2.770-68", convention: ru, title: {fr: "Symboles de cinématique", ru: "Элементы кинематики", en: "Kinematic symbols"}}
```

Règles de fusion avec le parent : les listes (terminologie, règles, normes, calculs,
sections) sont fusionnées par identifiant, et l'enfant l'emporte. Les mots-clés ne sont
**pas** hérités, pour garder une détection spécifique. Un enfant d'un profil à risque
élevé reste à risque élevé.

Conseil : mettez toujours les textes entre guillemets. En YAML compact, une virgule non
protégée coupe la valeur.

## Identification du domaine

`identify_domain` calcule un score transparent à partir des mots-clés trouvés dans les
documents du projet, et renvoie les termes trouvés et un niveau de confiance (élevée,
moyenne, faible, indéterminée). **C'est une suggestion** : l'utilisateur confirme avec
`set_project_domain`.
