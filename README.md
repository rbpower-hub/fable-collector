# fable-collector

[![Healthcheck](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/healthcheck.yml)
[![Build & Pages](https://github.com/rbpower-hub/fable-collector/actions/workflows/pages.yml/badge.svg)](https://github.com/rbpower-hub/fable-collector/actions/workflows/pages.yml)

Collecteur **horaire** Open-Meteo (ECMWF/ICON) pour le vent/rafales/direction + **Open-Meteo Marine** (Hs/Tp).  
Publie des **JSON** par spot (48–72 h), un **index**, des **règles normalisées** et un **status** sur GitHub Pages — utilisé par **FABLE AI**.

- **Site Pages :** https://rbpower-hub.github.io/fable-collector/  
- **Index JSON :** https://rbpower-hub.github.io/fable-collector/index.json  
- **Règles normalisées :** https://rbpower-hub.github.io/fable-collector/rules.normalized.json  
- **Status :** https://rbpower-hub.github.io/fable-collector/status.html  

---

## Endpoints de données (principaux)

- **Gammarth (home)** : https://rbpower-hub.github.io/fable-collector/gammarth-port.json  
- **Sidi Bou Saïd** : https://rbpower-hub.github.io/fable-collector/sidi-bou-said.json  
- **Ghar el Melh** : https://rbpower-hub.github.io/fable-collector/ghar-el-melh.json  
- **Ras Fartass** : https://rbpower-hub.github.io/fable-collector/ras-fartass.json  
- **El Haouaria** : https://rbpower-hub.github.io/fable-collector/el-haouaria.json  

> Si un spot manque, FABLE signale « pas d’endpoint dédié » et continue avec les autres.

---

## Workflows

- **`pages.yml`** — collecte, génération des JSON, `index.json`, `status.json/html`, et **déploiement** GitHub Pages.  
- **`healthcheck.yml`** — vérifie la **présence** et la **fraîcheur** des fichiers; déclenche (optionnel) une **alerte e-mail** si KO (configurer les *secrets* SMTP).

---

## Utilisation rapide

1) Crée le dépôt **fable-collector** et active **Pages** :  
   *Settings → Pages → Deploy from a branch* → branche `gh-pages` (ou via Actions `deploy-pages`).  
2) Renseigne tes spots dans `sites.yaml` (nom, lat, lon, `shelter_bonus_radius_km`).  
3) Le workflow **Build & Deploy Pages (fable-collector)** tourne automatiquement (horaires paramétrés) et à la demande (*Run workflow*).  
4) Les données sont disponibles sous :  
   `https://<user>.github.io/fable-collector/<slug>.json`

---

## Lancer manuellement (dispatch)

Dans **Actions ▸ Build & Deploy Pages (fable-collector) ▸ Run workflow** :

- `tz` : `Africa/Tunis`  
- `local_hours_csv` : `00,06,12,18`  
- `force` : `true` pour ignorer le filtre horaire  
- `window_hours` : `48`  
- `start_iso` / `only_sites` : **optionnels**

---

## Schéma minimal des fichiers publiés

```text
public/
├─ index.html                  # Landing (carte de liens + badge d’état)
├─ index.json                  # Catalogue des JSON (chemins + tailles + dates)
├─ status.html                 # Page humaine de statut (fraîcheur)
├─ status.json                 # Statut machine-readable
├─ rules.normalized.json       # Règles FABLE normalisées (collector/reader)
├─ gammarth-port.json
├─ sidi-bou-said.json
├─ ghar-el-melh.json
├─ ras-fartass.json
├─ el-haouaria.json
└─ windows.json                # (optionnel) sorties du reader (fenêtres détectées)

## Format JSON

{
  "meta": {
    "name": "Gammarth (port)",
    "slug": "gammarth-port.json",
    "tz": "Africa/Tunis",
    "lat": 36.9203,
    "lon": 10.2846,
    "sources": ["open-meteo:ecmwf", "open-meteo:marine"]
  },
  "hourly": {
    "time": ["2025-09-12T00:00", "2025-09-12T01:00", "..."],
    "wind_speed_10m": [..km/h..],
    "wind_gusts_10m": [..km/h..],
    "wind_direction_10m": [..deg..],
    "weather_code": [..wmo..],
    "visibility": [..m or km..],    // le reader convertit en km si nécessaire
    "hs": [..m..],                  // alias: wave_height
    "tp": [..s..]                   // alias: wave_period
  }
}

