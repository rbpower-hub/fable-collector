# Architecture — fable-collector v2

## Vue d'ensemble

```
                    ┌──────────────────────────────────────────────┐
                    │  GitHub Actions — collect.yml (cron horaire) │
                    └──────────────────────────────────────────────┘
                        │ 1          │ 2          │ 3          │ 4
                        ▼            ▼            ▼            ▼
                   preflight     collect       reader       publish
                   (valide       (Open-Meteo   (fenêtres    (catalog,
                    config,       multi-        Family GO)   status,
                    exporte       modèles)                   contrôles)
                    normalized)
                        │            │            │            │
                        └────────────┴─────┬──────┴────────────┘
                                           ▼
                                    public/  ──────►  GitHub Pages
                                           ▲
                    ┌──────────────────────┴───────────────────────┐
                    │ healthcheck.yml (cron /6h) — surveille le    │
                    │ site EN PRODUCTION, ouvre une issue si stale │
                    └──────────────────────────────────────────────┘
```

## Modules

| Module | Rôle | Entrées | Sorties |
|---|---|---|---|
| `fable.config` | Défauts + chargement/validation `rules.yaml`, `sites.yaml` (v1/v2), digest, normalisation | YAML | dicts, `SitesConfig` |
| `fable.openmeteo` | Client HTTP (urllib), URLs, retries, fallback modèles, dégradation marine | réseau | payloads bruts |
| `fable.astro` | Backfill daily : sunrise/sunset (forecast), lune (astronomy HTTP optionnel → Astral offline) | payload | payload enrichi |
| `fable.collect` | Orchestration par site : fetch → slice fenêtre → alignement axes → modèles parallèles → écriture atomique | config+réseau | `public/<slug>.json`, `index.json` |
| `fable.windows` | Chargement spots (par contenu), métriques worst-value-wins, éval par phase, détection 4-6 h, confiance | `public/*.json` | `windows.json` |
| `fable.status` | catalog, status (+`stale_after`), status.html (fraîcheur côté client), windows.md | `public/` | fichiers statut |
| `fable.preflight` | Gate de validation avant collecte + exports normalisés | YAML | `rules.normalized.json`, `sites.normalized.json` |
| `fable.publish` | Post-traitement + `final_check` (bloque le déploiement si incomplet) | `public/` | code retour |
| `fable.healthcheck` | Vérification du déploiement LIVE (indépendant du build) | HTTPS Pages | code retour |

## Flux de données par site

1. `fetch_forecast` : essaie `icon_seamless → gfs_seamless → ecmwf_ifs04 →
   default`, puis sans `models=`, puis jeu SAFE minimal. Premier payload avec
   du vent non-nul gagne (`_model_used`).
2. Backfill daily si nécessaire (sunrise/sunset via forecast ; lune via
   Astral offline par défaut — l'endpoint astronomy est coupé par
   `http.disable_astronomy_http: true` dans rules.yaml).
3. `fetch_marine` : Hs/Tp (+houle) avec chaîne de fallback de modèles
   (`meteofrance_wave` → `ncep_gfswave025` → `ecmwf_wam025` → défaut).
   **Ne lève jamais** : payload dégradé `_error` → spot publié wind-only.
3bis. `fetch_parallel_marine` : modèles de houle additionnels alignés sur
   l'axe commun → bloc `marine_models.*` (le primaire y est republié).
   Sert au calcul de l'écart inter-modèles (confiance).
4. Slicing sur la fenêtre locale demandée (48 h par défaut), par source.
5. `flatten_hourly_aligned` : axe commun = **intersection** des heures
   forecast/marine (union ordonnée si vide) → bloc `hourly` avec alias
   `hs`/`tp`.
6. Modèles parallèles : mêmes clés vent, alignés sur l'axe commun → bloc
   `models.*` (le primaire y est republié pour homogénéité).
7. Écriture atomique (`.tmp` + `replace`).

## Détection de fenêtres (reader)

- Phases par longueur L : `T A…A T` (L=4 → TAAT … L=6 → TAAAAT), bornées 4-6 h.
- Une heure est éligible si TOUTES les conditions passent pour sa phase :
  orage (WMO 95/96/99) = veto absolu ; visibilité ≥ 5 km ; vent onshore
  ≤ 22 km/h ; squall Δ(rafale-soutenu) < 17 (transit) / < 20 (mouillage) ;
  vent < 20 (family transit) / < 32 (mouillage) ; rafales < 30 / < 34 ;
  Hs/Tp selon matrice (assouplie au mouillage si Hs ≤ 0.35 m) ;
  clauses mers courtes/raides (Hs ≥ 0.5 & Tp ≤ 6 → refus ; Hs ≥ 0.6 & Tp ≤ 5
  → refus dur).
- Worst-value-wins entre modèles pour chaque heure ; départ ET retour
  validés au port d'attache en phase transit.
- Confiance : Low si < 2 modèles vent sur une heure ; High exige en plus
  ≥ 2 modèles de houle avec écart Hs inter-modèles < 0,2 m sur CHAQUE heure
  de la fenêtre ; **cap Medium** si une seule source de houle (conditionnel
  depuis v2.1 — l'écart Hs mesure désormais le désaccord entre modèles,
  pas la variation temporelle).

## Décisions figées (ne pas « corriger » sans réflexion)

- La clé payload `"ecmwf"` contient le **modèle primaire** (souvent ICON) —
  nom historique conservé pour ne pas casser FABLE AI. Le vrai modèle est
  dans `meta.sources.ecmwf_open_meteo.model_used`.
- `index.json` garde le schéma `spots` observé en production (pas `files` —
  c'est `catalog.json` qui liste les fichiers).
- Le collector n'interpole jamais les trous marine : données absentes =
  heures non-éligibles, par sécurité.
