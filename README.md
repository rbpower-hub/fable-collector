# fable-collector

[![Collect & Deploy](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml)
[![Healthcheck](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml)
[![CI](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml)

Collecteur **horaire** de météo marine pour les spots côtiers tunisiens, avec :

- prévisions Open-Meteo multi-modèles pour le vent et la mer ;
- détection conservatrice des fenêtres **Family GO** de 4 à 6 heures ;
- validation des phases Transit – Mouillage – Transit depuis le port d’attache ;
- recommandations d’activités marines et de pêche uniquement dans les fenêtres déjà validées ;
- **Knowledge Pack** indépendant pour les espèces, techniques, ports et activités ;
- publication automatique du tableau de bord et des données sur GitHub Pages.

> *English summary* — Hourly marine-weather collector for Tunisian coastal spots, publishing safe 4–6 hour Family GO windows and ranked marine/fishing activities. Recommendations are downstream of the safety engine. A versioned Knowledge Pack stores domain knowledge separately from the Python decision engine.

---

## Endpoints publiés

| Ressource | URL |
|---|---|
| Tableau de bord | https://rbpower-hub.github.io/fable-collector/ |
| Index des spots | https://rbpower-hub.github.io/fable-collector/index.json |
| Spot, exemple Gammarth | https://rbpower-hub.github.io/fable-collector/gammarth-port.json |
| Fenêtres Family GO | https://rbpower-hub.github.io/fable-collector/windows.json |
| Activités recommandées | https://rbpower-hub.github.io/fable-collector/recommendations.json |
| Catalogue Knowledge Pack | https://rbpower-hub.github.io/fable-collector/knowledge.json |
| Règles normalisées | https://rbpower-hub.github.io/fable-collector/rules.normalized.json |
| Sites normalisés | https://rbpower-hub.github.io/fable-collector/sites.normalized.json |
| Statut humain | https://rbpower-hub.github.io/fable-collector/status.html |
| Statut machine | https://rbpower-hub.github.io/fable-collector/status.json |
| Inventaire des fichiers | https://rbpower-hub.github.io/fable-collector/catalog.json |

Spots configurés : **Gammarth**, **Sidi Bou Saïd**, **Ghar el Melh**, **Ras Fartass**, **El Haouaria**, **Kélibia** et **Pantelleria beta**. Korbous reste exclu par la politique actuelle.

---

## Architecture

```text
sites.yaml + rules.yaml
knowledge/
  fish/ + techniques/ + ports/ + activities/
legacy fallback: fishing_profiles.yaml + activity_profiles.yaml
        │
        ▼
fable.preflight          validation des règles et sites
        │
fable.collect            météo, mer, soleil et lune par spot
        │
fable.windows            fenêtres Family GO 4–6 h
        │
fable.knowledge          chargement et validation du Knowledge Pack
        │
fable.recommendations    activités, techniques, espèces et appâts
        │
fable.publish            catalogue, statut et contrôles finaux
        │
        ▼
GitHub Pages              board + JSON publics
```

Le moteur de recommandations consomme `windows.json` **après** la décision de sécurité. Le Knowledge Pack ne peut pas autoriser une sortie refusée par le moteur Family GO.

Documentation détaillée :

- [Architecture](docs/ARCHITECTURE.md)
- [Knowledge Pack](docs/KNOWLEDGE-PACK.md)
- [Recommandations d’activités et de pêche](docs/RECOMMENDATIONS.md)
- [Déploiement](docs/DEPLOY.md)
- [Runbook d’exploitation](docs/RUNBOOK.md)
- [Changelog](docs/CHANGELOG.md)
- [Audit v2](docs/AUDIT-2026-07.md)

---

## Configurer les ports de navigation

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

## Configurer le Knowledge Pack

La connaissance métier est organisée dans des fichiers YAML indépendants :

```text
knowledge/
  manifest.yaml
  fish/pageot.yaml
  techniques/bottom-fishing.yaml
  ports/gammarth-port.yaml
  activities/bottom-fishing.yaml
```

Un profil de port référence des identifiants structurés :

```yaml
id: gammarth-port
confidence: medium
fishing:
  seasons:
    summer:
      species: [pageot, dorade-royale, oblade]
      techniques: [bottom-fishing, light-jigging]
      baits: [ver, crevette]
      depths_m: [6, 18]
      preferred_periods: [sunrise, sunset]
```

Le chargeur bloque les références inconnues et publie `knowledge.json` pour indiquer la version et les identifiants réellement chargés.

La migration est progressive : Gammarth utilise le nouveau modèle structuré ; les autres ports conservent temporairement le fallback `fishing_profiles.yaml` jusqu’à leur migration et validation.

## Configurer les activités

Chaque fichier `knowledge/activities/<id>.yaml` contient les seuils propres à l’usage. Une activité est éliminée si ses seuils sont dépassés, même lorsque la fenêtre générale est Family GO.

Le classement utilise principalement l’état de mer, le vent et l’horaire saisonnier. La lune reste un signal secondaire plafonné.

Les espèces, profondeurs, techniques et appâts sont des **indications opérationnelles à affiner** selon les observations locales et la réglementation tunisienne applicable.

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
- `knowledge.json` lorsque le Knowledge Pack est actif ;
- `status.json` et `status.html` ;
- `catalog.json`.

Variables d’environnement utiles : `FABLE_TZ`, `FABLE_WINDOW_HOURS`, `FABLE_START_ISO`, `FABLE_ONLY_SITES`, `FABLE_MODEL_ORDER`, `FABLE_HTTP_TIMEOUT_S`, `FABLE_HTTP_RETRIES`, `FABLE_ASTRAL_FALLBACK` et `LOG_LEVEL`.

## Tests

```bash
CHECK-LOCAL.bat
```

Le contrôle local exécute le preflight, Ruff et Pytest. Les tests couvrent notamment les scénarios calme, tempête, orage, modèles dégradés, routes composites, recommandations d’activités et validation des références du Knowledge Pack.

---

## Sécurité des décisions

Le détecteur applique **worst-value-wins** entre modèles pour le vent et les vagues : Hs retenue = valeur la plus haute ; Tp retenue = période la plus courte. Les données marine absentes ne sont jamais inventées.

Le classement des activités applique ensuite quatre principes :

1. aucune recommandation sans fenêtre Family GO validée ;
2. les seuils particuliers de l’activité peuvent encore la refuser ;
3. une référence Knowledge Pack invalide bloque la génération ;
4. le signal lunaire est un bonus limité et ne neutralise jamais un NO-GO.

© 2025-2026 RB Power Consulting — Tous droits réservés. Voir [LICENSE](LICENSE).
