# fable-collector

[![Collect & Deploy](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml)
[![Healthcheck](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml)
[![CI](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml)

Collecteur **horaire** de météo marine pour les spots côtiers tunisiens et les traversées offshore configurées, avec :

- prévisions Open-Meteo multi-modèles pour le vent et la mer ;
- détection conservatrice des fenêtres **Family GO** ;
- horizon opérationnel de **72 heures** présenté sur trois journées dans la Vue Famille ;
- niveau intermédiaire **Family GO prudent**, clairement signalé et soumis aux mêmes vétos absolus ;
- durée minimale adaptative de 3 à 6 heures pour les sorties côtières ;
- plage d’utilisation liée au lever et au coucher du soleil ;
- validation des phases Transit – Mouillage – Transit depuis le port d’attache ;
- diagnostics backend détaillés pour chaque destination bloquée ;
- traversées **Pantelleria aller simple et retour simple** évaluées indépendamment depuis Kélibia ;
- trajets **Gammarth↔Kélibia** évalués eux aussi en aller et retour indépendants pour les séjours multi-jours ;
- Port Knowledge : routes, distances, temps de transit, politique de retour et statut des abris ;
- recommandations d’activités et de pêche uniquement dans les sorties côtières compatibles ;
- aide Fish Intelligence indicative : espèces, techniques, appâts/leurres, montages et matériel de départ ;
- publication automatique du tableau de bord et des données sur GitHub Pages.

> *English summary* — Hourly marine-weather collector with a 72-hour, three-day family planner. Short coastal outings keep same-window return validation; Gammarth↔Kelibia and Kelibia↔Pantelleria publish independent outbound and return legs for multi-day planning.

---

## Endpoints publiés

| Ressource | URL |
|---|---|
| Tableau de bord | https://rbpower-hub.github.io/fable-collector/ |
| Index des spots | https://rbpower-hub.github.io/fable-collector/index.json |
| Spot, exemple Gammarth | https://rbpower-hub.github.io/fable-collector/gammarth-port.json |
| Fenêtres, niveaux et diagnostics | https://rbpower-hub.github.io/fable-collector/windows.json |
| Activités recommandées | https://rbpower-hub.github.io/fable-collector/recommendations.json |
| Routes, transits et abris | https://rbpower-hub.github.io/fable-collector/port-knowledge.json |
| Catalogue du Knowledge Pack | https://rbpower-hub.github.io/fable-collector/knowledge.json |
| Règles normalisées | https://rbpower-hub.github.io/fable-collector/rules.normalized.json |
| Sites normalisés | https://rbpower-hub.github.io/fable-collector/sites.normalized.json |
| Statut humain | https://rbpower-hub.github.io/fable-collector/status.html |
| Statut machine | https://rbpower-hub.github.io/fable-collector/status.json |
| Inventaire des fichiers | https://rbpower-hub.github.io/fable-collector/catalog.json |

`windows.json` version 5 publie les fenêtres côtières standard/prudentes, leurs diagnostics et les trajets longs directionnels `outbound` / `return`.

`recommendations.json` sépare les activités de loisir des objets `navigation_only`. Une traversée offshore ne produit aucune recommandation automatique de baignade, mouillage ou pêche.

`knowledge.json` version 3 expose Fish Intelligence, Port Knowledge, Shelter Intelligence et la politique offshore one-way.

Spots configurés : **Gammarth**, **Sidi Bou Saïd**, **Ghar el Melh**, **Ras Fartass**, **El Haouaria**, **Kélibia** et **Pantelleria beta**. Korbous reste exclu par la politique actuelle.

---

## Architecture

```text
sites.yaml + rules.yaml
knowledge/ + fishing_profiles.yaml
        │
        ▼
fable.preflight                  validation + exports normalisés
        │
fable.collect                    météo, mer, soleil et lune par spot
        │
fable.window_models              chargement + worst-value-wins
        │
fable.window_policy              vétos, Family, prudent, lumière
        │
fable.window_detect              sorties côtières + diagnostics
        │
fable.offshore                   traversées directionnelles Kélibia↔Pantelleria
        │
fable.recommendations            activités + Fish Intelligence
        │
fable.offshore_recommendations   séparation navigation / loisirs
        │
fable.port_knowledge             routes, transits, abris et politiques de retour
        │
fable.publish                    catalogue, statut et contrôles finaux
        │
        ▼
GitHub Pages                      board + JSON publics
```

Le moteur d’activités consomme `windows.json` **après** la décision de sécurité. Il ne peut pas créer une fenêtre ni neutraliser un NO-GO.

Documentation détaillée :

- [Architecture](docs/ARCHITECTURE.md)
- [Family GO prudent et diagnostics](docs/FAMILY-GO-PRUDENT.md)
- [Port Knowledge et offshore aller simple](docs/PORT-KNOWLEDGE.md)
- [Knowledge Pack](docs/KNOWLEDGE-PACK.md)
- [Fish Intelligence v1](docs/FISH-INTELLIGENCE.md)
- [Recommandations d’activités et de pêche](docs/RECOMMENDATIONS.md)
- [Déploiement](docs/DEPLOY.md)
- [Runbook d’exploitation](docs/RUNBOOK.md)
- [Changelog](docs/CHANGELOG.md)
- [Audit v2](docs/AUDIT-2026-07.md)

---

## Deux logiques de trajet

### Sorties côtières familiales

Gammarth, Sidi Bou Saïd, Ghar El Melh, Ras Fartass et El Haouaria utilisent la logique :

```text
départ → transit aller → temps sur zone → transit retour
```

Le départ et le retour doivent appartenir à la même fenêtre validée.

### Kélibia — trajet long multi-jours

Kélibia utilise deux jambes indépendantes sur l’horizon de 72 heures :

```text
outbound : Gammarth → Kélibia
return   : Kélibia → Gammarth
```

Le board présente l’aller et le premier retour compatible séparément. L’absence de retour validé dans l’horizon est affichée explicitement et n’est jamais interprétée comme un GO complet du voyage.

### Pantelleria — offshore multi-jours

Pantelleria utilise :

```text
outbound : Kélibia → Pantelleria
return   : Pantelleria → Kélibia
```

Les deux directions sont évaluées indépendamment. Les sorties peuvent être séparées par plusieurs jours et **aucun retour à Gammarth le jour même n’est exigé**.

Le pré-positionnement `Gammarth ↔ Kélibia` reste une opération distincte, désormais publiée avec ses propres fenêtres aller et retour.

La première version offshore :

- utilise uniquement les seuils Family stricts ;
- n’active pas le mode prudent ;
- contrôle les conditions aux deux extrémités pendant toute la traversée ;
- publie les fenêtres comme `navigation_only` ;
- exige une vérification indépendante des formalités, équipements, communications, autonomie et bulletins maritimes officiels.

---

## Family GO prudent

Le niveau prudent est évalué seulement après l’échec du niveau standard. Il impose simultanément :

- vent `≤ 22 km/h` ;
- rafales `< 28 km/h` ;
- `Hs ≤ 0,40 m` ;
- `Tp ≥ 3,5 s` ;
- vent non onshore ;
- confiance au moins `Medium` ;
- fenêtre entièrement comprise dans la plage de lumière sécurisée.

Il ne modifie jamais les vétos absolus, notamment l’orage, la visibilité inférieure à 5 km, les rafales à partir de 30 km/h, le vent soutenu à partir de 25 km/h, une mer courte et raide classée dure ou les données indispensables manquantes.

---

## Durée adaptative et lumière

Pour une destination côtière courte, FABLE peut valider une fenêtre de trois heures. Pour une destination plus éloignée :

```text
durée requise = ceil(2 × transit lent + 1,5 h sur zone)
```

La durée reste plafonnée à six heures dans le moteur Family côtier.

Quand les données astronomiques sont disponibles, la plage Family commence trente minutes après le lever du soleil et se termine une heure avant le coucher. Les horaires fixes restent le mécanisme de repli.

---

## Port Knowledge et abris

`port-knowledge.json` publie pour chaque port :

- l’origine de route ;
- la distance calculée depuis `sites.yaml` ;
- l’hypothèse de vitesse ;
- les temps rapide et conservateur ;
- le type de trajet ;
- la politique de retour ;
- les abris et leur statut de validation.

Les distances calculées ne remplacent pas une route nautique validée.

Un abri ne peut activer une tolérance que si sa fiche possède :

- des coordonnées validées ;
- des secteurs de protection ;
- un fetch maximal positif ;
- le statut `validated`.

Les profils actuels conservent `shelters: []`. Aucun bonus d’abri n’est donc actif tant que les données terrain ne sont pas confirmées.

---

## Diagnostics des blocages

La section **Avertissements** utilise directement la décision Python publiée dans `windows.json` :

- départ depuis Gammarth ou le port origine ;
- phases à destination ;
- retour pour les sorties côtières ;
- arrivée pour une traversée offshore ;
- vent, rafales, direction, visibilité, Hs et Tp ;
- pire valeur entre modèles ;
- durée, lumière et confiance.

---

## Configurer les ports

Les positions, routes et hypothèses de navigation restent dans `sites.yaml` :

```yaml
version: 2
tz: Africa/Tunis
home: gammarth-port
sites:
  - name: "Mon Port"
    lat: 36.00000
    lon: 10.00000
    transit_speed_kts: {min: 16, max: 24}
    onshore_sectors: [[30, 150]]
```

Pantelleria utilise notamment :

```yaml
route_origin: kelibia
route_kind: offshore_one_way_beta
```

`onshore_sectors` supporte le wrap-around, par exemple `[[330, 360], [0, 70]]`.

---

## Knowledge Pack

Le dossier `knowledge/` porte les connaissances métier réutilisables :

```text
knowledge/
├── manifest.yaml
├── fish/
├── techniques/
├── ports/
└── activities/
```

La base comprend :

- **6 ports tunisiens** avec profils saisonniers ;
- **Pantelleria** comme profil de navigation offshore sans profil de pêche local ;
- **11 profils d’espèces ou groupes locaux** ;
- **4 techniques** ;
- **5 activités marines**.

Les identifiants croisés sont validés avant génération. Une référence incohérente bloque le build.

---

## Exécution locale

```bash
SETUP-LOCAL.bat
python -m fable.preflight
python collect.py
python reader.py
python -m fable.recommendations
python -m fable.offshore_recommendations
python -m fable.port_knowledge
python -m fable.publish
```

Les sorties principales sont écrites dans `public/` :

- `<spot>.json` ;
- `windows.json` ;
- `recommendations.json` ;
- `port-knowledge.json` ;
- `knowledge.json` ;
- `status.json` et `status.html` ;
- `catalog.json`.

## Tests

```bash
CHECK-LOCAL.bat
```

La CI exécute Ruff et Pytest et conserve un rapport JUnit téléchargeable. Les tests couvrent les vétos, le GO prudent, les diagnostics, les routes côtières, les traversées offshore aller/retour, l’absence d’aller-retour le même jour, les abris non validés, Port Knowledge, les recommandations et Fish Intelligence.

---

## Sécurité des décisions

Le détecteur applique **worst-value-wins** entre modèles : Hs retenue = valeur la plus haute ; Tp retenue = période la plus courte. Les données marines absentes ne sont jamais inventées.

Les principes restent :

1. aucune activité sans fenêtre côtière validée ;
2. une traversée offshore reste `navigation_only` ;
3. les seuils particuliers d’une activité peuvent encore la refuser ;
4. la lune ne neutralise jamais un NO-GO ;
5. aucun abri non validé ne relâche un seuil ;
6. les réglages de matériel restent indicatifs et nécessitent une vérification locale et réglementaire.

© 2025-2026 RB Power Consulting — Tous droits réservés. Voir [LICENSE](LICENSE).
