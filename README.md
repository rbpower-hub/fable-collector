# fable-collector

[![Collect & Deploy](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml)
[![Healthcheck](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml)
[![CI](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml)

Collecteur **horaire** de météo marine pour les spots côtiers tunisiens, avec :

- prévisions Open-Meteo multi-modèles pour le vent et la mer ;
- détection conservatrice des fenêtres **Family GO** ;
- niveau intermédiaire **Family GO prudent**, clairement signalé et soumis aux mêmes vétos absolus ;
- durée minimale adaptative de 3 à 6 heures selon le transit et le temps minimal sur zone ;
- plage d’utilisation liée au lever et au coucher du soleil lorsque ces données sont disponibles ;
- validation des phases Transit – Mouillage – Transit depuis le port d’attache ;
- diagnostics backend détaillés pour chaque destination bloquée ;
- recommandations d’activités marines et de pêche uniquement dans les fenêtres déjà validées ;
- aide Fish Intelligence indicative : espèces, techniques, appâts/leurres, montages et matériel de départ ;
- publication automatique du tableau de bord et des données sur GitHub Pages.

> *English summary* — Hourly marine-weather collector for Tunisian coastal spots, publishing conservative Family GO windows, an explicitly labelled prudent tier, backend blocker diagnostics and ranked marine/fishing activities. Prudent windows never override hard vetoes. Recommendations remain downstream of the navigation-safety engine.

---

## Endpoints publiés

| Ressource | URL |
|---|---|
| Tableau de bord | https://rbpower-hub.github.io/fable-collector/ |
| Index des spots | https://rbpower-hub.github.io/fable-collector/index.json |
| Spot, exemple Gammarth | https://rbpower-hub.github.io/fable-collector/gammarth-port.json |
| Fenêtres, niveaux et diagnostics | https://rbpower-hub.github.io/fable-collector/windows.json |
| Activités recommandées | https://rbpower-hub.github.io/fable-collector/recommendations.json |
| Catalogue du Knowledge Pack | https://rbpower-hub.github.io/fable-collector/knowledge.json |
| Règles normalisées | https://rbpower-hub.github.io/fable-collector/rules.normalized.json |
| Sites normalisés | https://rbpower-hub.github.io/fable-collector/sites.normalized.json |
| Statut humain | https://rbpower-hub.github.io/fable-collector/status.html |
| Statut machine | https://rbpower-hub.github.io/fable-collector/status.json |
| Inventaire des fichiers | https://rbpower-hub.github.io/fable-collector/catalog.json |

`windows.json` version 3 publie pour chaque destination la durée requise, les fenêtres standard ou prudentes et, en cas de blocage, `diagnostics.first_blocker` ainsi que `diagnostics.near_miss`.

`knowledge.json` est produit pendant `Collect & Deploy` dès que le Knowledge Pack est actif dans `main`. Avec le schéma Fish Intelligence v1, `knowledge.json` est en version 2 et `recommendations.json` en version 3.

Spots configurés : **Gammarth**, **Sidi Bou Saïd**, **Ghar el Melh**, **Ras Fartass**, **El Haouaria**, **Kélibia** et **Pantelleria beta**. Korbous reste exclu par la politique actuelle.

---

## Architecture

```text
sites.yaml + rules.yaml
knowledge/ + fishing_profiles.yaml
        │
        ▼
fable.preflight          validation + exports normalisés
        │
fable.collect            météo, mer, soleil et lune par spot
        │
fable.window_models      chargement des spots + worst-value-wins
        │
fable.window_policy      vétos, Family, prudent, lumière et diagnostics
        │
fable.window_detect      durée adaptative + routes + windows.json v3
        │
fable.knowledge          validation des profils et du matériel indicatif
        │
fable.recommendations    activités + Fish Intelligence + astro
        │
fable.publish            catalogue, statut et contrôles finaux
        │
        ▼
GitHub Pages              board + JSON publics
```

Le moteur de recommandations consomme `windows.json` **après** la décision de sécurité. Il ne peut pas autoriser une sortie refusée par le moteur Family GO.

Documentation détaillée :

- [Architecture](docs/ARCHITECTURE.md)
- [Family GO prudent et diagnostics](docs/FAMILY-GO-PRUDENT.md)
- [Knowledge Pack](docs/KNOWLEDGE-PACK.md)
- [Fish Intelligence v1](docs/FISH-INTELLIGENCE.md)
- [Recommandations d’activités et de pêche](docs/RECOMMENDATIONS.md)
- [Déploiement](docs/DEPLOY.md)
- [Runbook d’exploitation](docs/RUNBOOK.md)
- [Changelog](docs/CHANGELOG.md)
- [Audit v2](docs/AUDIT-2026-07.md)

---

## Niveaux de décision

### Family GO

Le niveau standard conserve les seuils familiaux historiques et la logique Transit – Mouillage – Transit.

### Family GO prudent

Le niveau prudent est évalué seulement après l’échec du niveau standard. Il impose simultanément :

- vent `≤ 22 km/h` ;
- rafales `< 28 km/h` ;
- `Hs ≤ 0,40 m` ;
- `Tp ≥ 3,5 s` ;
- vent non onshore ;
- confiance au moins `Medium` ;
- fenêtre entièrement comprise dans la plage de lumière sécurisée.

Le board l’affiche en orange avec un avertissement de confort réduit. Il ne s’agit pas d’un mode Expert.

### NO-GO et vétos absolus

Le niveau prudent ne modifie jamais les vétos absolus, notamment l’orage, la visibilité inférieure à 5 km, les rafales à partir de 30 km/h, le vent soutenu à partir de 25 km/h, une mer courte et raide classée dure ou les données indispensables manquantes.

---

## Durée adaptative et lumière

Pour une destination courte, FABLE peut valider une fenêtre de trois heures. Pour une destination plus éloignée, la durée requise est calculée à partir du scénario lent de transit aller-retour et d’au moins 1,5 heure sur zone.

```text
durée requise = ceil(2 × transit lent + 1,5 h sur zone)
```

La durée reste plafonnée à six heures dans le moteur Family actuel. Si le trajet exige davantage, `windows.json` publie un blocage de durée explicite.

Quand les données astronomiques sont disponibles, la plage Family commence trente minutes après le lever du soleil et se termine une heure avant le coucher. Les horaires fixes de `family_hours_local` restent le mécanisme de repli.

---

## Diagnostics des blocages

La section **Avertissements** ne recalcule plus les règles dans le navigateur. Elle utilise le diagnostic Python publié avec la même logique que `windows.json` :

- départ depuis Gammarth ;
- phases à destination ;
- retour à Gammarth ;
- vent, rafales, direction, visibilité, Hs et Tp ;
- pire valeur entre modèles ;
- durée requise, lumière et confiance.

Un blocage pour Ghar El Melh peut donc indiquer que les conditions locales sont acceptables mais que le **retour à Gammarth** est refusé, avec l’heure, la métrique et la raison correspondantes.

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

`onshore_sectors` supporte le wrap-around, par exemple `[[330, 360], [0, 70]]`.

Une tolérance de mouillage n’est activée que si `shelter_bonus_radius_km` est explicitement supérieur à zéro et que le vent n’est pas onshore. Les ports actuels restent sans tolérance tant qu’un abri n’est pas validé.

## Configurer le Knowledge Pack

Le dossier `knowledge/` porte les connaissances métier réutilisables :

```text
knowledge/
├── manifest.yaml
├── fish/
├── techniques/
├── ports/
└── activities/
```

Les identifiants référencés par les ports, espèces et activités sont validés avant génération. Une référence inconnue bloque le build du pack afin d’éviter des recommandations silencieusement incomplètes.

La base régionale structurée couvre actuellement :

- **6 ports tunisiens** : Gammarth, Sidi Bou Saïd, Ghar El Melh, Ras Fartass, El Haouaria et Kélibia ;
- **11 profils d’espèces ou groupes locaux** ;
- **4 techniques** ;
- **5 activités marines**.

Le schéma Fish Intelligence v1 ajoute pour chaque espèce les techniques, appâts, leurres, présentations et plages indicatives de matériel. Pantelleria reste volontairement sans profil de pêche dans le Knowledge Pack.

Les champs `zones` restent vides tant que les coordonnées ne sont pas validées sur le terrain et contrôlées du point de vue de la navigation.

---

## Exécution locale

```bash
SETUP-LOCAL.bat
python -m fable.preflight
python collect.py
python reader.py
python -m fable.recommendations
python -m fable.publish
```

Les sorties principales sont écrites dans `public/` :

- `<spot>.json` ;
- `windows.json` ;
- `recommendations.json` ;
- `knowledge.json` lorsque le pack est actif ;
- `status.json` et `status.html` ;
- `catalog.json`.

Variables d’environnement utiles : `FABLE_TZ`, `FABLE_WINDOW_HOURS`, `FABLE_START_ISO`, `FABLE_ONLY_SITES`, `FABLE_MODEL_ORDER`, `FABLE_HTTP_TIMEOUT_S`, `FABLE_HTTP_RETRIES`, `FABLE_ASTRAL_FALLBACK` et `LOG_LEVEL`.

## Tests

```bash
CHECK-LOCAL.bat
```

Le contrôle local exécute le preflight, Ruff et Pytest. Les tests couvrent notamment les scénarios calme, tempête, orage, modèles dégradés, routes composites, GO prudent, blocage du retour, durée adaptative, plage solaire, abri conditionnel, recommandations, Knowledge Pack et Fish Intelligence.

---

## Sécurité des décisions

Le détecteur applique **worst-value-wins** entre modèles pour le vent et les vagues : Hs retenue = valeur la plus haute ; Tp retenue = période la plus courte. Les données marine absentes ne sont jamais inventées.

Le classement des activités applique ensuite quatre principes :

1. aucune recommandation sans fenêtre Family GO standard ou prudente validée par le backend ;
2. les seuils particuliers de l’activité peuvent encore la refuser ;
3. le signal lunaire est un bonus limité et ne neutralise jamais un NO-GO ;
4. les plages de matériel sont indicatives et imposent une vérification locale et réglementaire avant la sortie.

© 2025-2026 RB Power Consulting — Tous droits réservés. Voir [LICENSE](LICENSE).
