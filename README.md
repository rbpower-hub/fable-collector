# fable-collector

[![Collect & Deploy](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/collect.yml)
[![Healthcheck](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml)
[![CI](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/ci.yml)

Collecteur **horaire** de météo marine (Open-Meteo : ECMWF/ICON/GFS + Marine) pour les
spots côtiers tunisiens, avec **détection de fenêtres de sortie « Family GO »**
(phases Transit – Mouillage – Transit, 4 à 6 h) depuis le port d'attache.

Publie sur **GitHub Pages** des JSON par spot (48–72 h), un index, les règles
normalisées, un statut de fraîcheur et les fenêtres détectées — consommés par **FABLE AI**.

> *English summary* — Hourly marine-weather collector for Tunisian coastal spots
> (Open-Meteo forecast + marine APIs), publishing per-spot JSON feeds on GitHub
> Pages and detecting safe 4–6 h family boating windows (Transit–Anchor–Transit
> phase model) from the configured home port. Fully config-driven and
> deployable for any port by editing `sites.yaml`.

---

## Endpoints publiés

| Ressource | URL |
|---|---|
| Landing / dashboard | https://rbpower-hub.github.io/fable-collector/ |
| Index des spots | https://rbpower-hub.github.io/fable-collector/index.json |
| Spot (ex. Gammarth) | https://rbpower-hub.github.io/fable-collector/gammarth-port.json |
| Fenêtres Family GO | https://rbpower-hub.github.io/fable-collector/windows.json |
| Règles normalisées | https://rbpower-hub.github.io/fable-collector/rules.normalized.json |
| Sites normalisés | https://rbpower-hub.github.io/fable-collector/sites.normalized.json |
| Statut (humain) | https://rbpower-hub.github.io/fable-collector/status.html |
| Statut (machine) | https://rbpower-hub.github.io/fable-collector/status.json |
| Inventaire fichiers | https://rbpower-hub.github.io/fable-collector/catalog.json |

Spots actuels : Gammarth (port, home) · Sidi Bou Saïd · Ghar el Melh · Ras Fartass · El Haouaria.

---

## Architecture (v2)

```
sites.yaml + rules.yaml          (configuration, source de vérité unique)
        │
        ▼
fable/preflight  ──►  validation + rules.normalized.json + sites.normalized.json
fable/collect    ──►  Open-Meteo (multi-modèles, fallbacks) ──► public/<slug>.json + index.json
fable/windows    ──►  détection fenêtres 4–6 h ──► public/windows.json
fable/publish    ──►  catalog.json + status.json/html + windows.md + contrôles finaux
        │
        ▼
GitHub Pages  ◄──  .github/workflows/collect.yml (cron horaire + keepalive)
                   .github/workflows/healthcheck.yml (surveillance externe /6 h)
                   .github/workflows/ci.yml (ruff + pytest)
```

Détails : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
Audit et corrections v2 : [`docs/AUDIT-2026-07.md`](docs/AUDIT-2026-07.md) ·
Mise en production : [`docs/DEPLOY.md`](docs/DEPLOY.md) ·
Exploitation : [`docs/RUNBOOK.md`](docs/RUNBOOK.md)

---

## Deployer pour un autre port

Tout est dans `sites.yaml` (schéma v2) :

```yaml
version: 2
tz: Africa/Tunis
home: mon-port          # slug du port d'attache
sites:
  - name: "Mon Port"
    lat: 36.00000
    lon: 10.00000
    onshore_sectors: [[30, 150]]   # secteurs vent d'affalement (degrés)
```

`onshore_sectors` supporte le wrap-around (`[[330, 360], [0, 70]]`).
L'ancien format v1 (liste simple) reste accepté.

## Exécution locale

```bash
SETUP-LOCAL.bat
python -m fable.preflight        # valide la config
python collect.py                # collecte -> public/*.json
python reader.py                 # fenêtres -> public/windows.json
python -m fable.publish          # statut + contrôles
```

Variables d'env utiles : `FABLE_TZ`, `FABLE_WINDOW_HOURS` (48), `FABLE_START_ISO`,
`FABLE_ONLY_SITES` (CSV de slugs), `FABLE_MODEL_ORDER`, `FABLE_HTTP_TIMEOUT_S`,
`FABLE_HTTP_RETRIES`, `LOG_LEVEL`.

## Tests

```bash
CHECK-LOCAL.bat
```

`SETUP-LOCAL.bat` crée `.venv`, installe les dépendances runtime + dev
(`requirements.txt`, `requirements-dev.txt`), puis `CHECK-LOCAL.bat` exécute
`fable.preflight`, `ruff check .` et `pytest -q`.

41 tests hors-ligne (fixtures d'API enregistrées + scénarios synthétiques
calme/tempête/orage) — aucun appel réseau nécessaire après installation.

---

## Sécurité des décisions

Le détecteur applique **worst-value-wins** entre modèles — vent ET vagues :
Hs retenue = la plus haute des modèles, Tp retenue = la plus courte (mer la
plus raide). Seuils stricts par phase (transit vs mouillage abrité),
overrides durs (orage, rafales ≥ 30 km/h, visibilité < 5 km, mers
courtes/raides).

**Confiance multi-modèles (v2.1)** : la houle est collectée sur plusieurs
modèles Open-Meteo Marine — MFWAM 0.08° (primaire), GFS-Wave 0.25° et
ECMWF WAM 0.25° en parallèle. « High » exige ≥ 2 modèles de houle concordants
(écart Hs < 0,2 m sur chaque heure) en plus de l'accord vent ; avec une seule
source de houle la confiance reste plafonnée à « Medium » (comportement v1).
En cas d'échec marine, le spot est publié **sans données de vagues**
(`meta.debug.marine_error`) : heures non-éligibles Family, jamais de données
fabriquées.

© 2025-2026 RB Power Consulting — Tous droits réservés. Voir [LICENSE](LICENSE).
