# Changelog

## 2.2.0 — 2026-07-06
- **Version dédiée board** pour l’évolution UI, afin de pouvoir revenir facilement à la version précédente si besoin.
- **Board branché sur `sites.normalized.json`** : spots, port principal et métadonnées de site ne sont plus figés dans le HTML.
- **Board branché sur `rules.normalized.json`** : heures Family et fenêtre mini ne reposent plus sur des constantes locales du board.
- **Confiance enrichie dans l’UI** : affichage des sources, modèles utilisés, nombre minimal de sources de houle et spread Hs.
- **Santé live enrichie** : statut du board basé sur `stale_after`, `build_ok`, `missing_spots` et `collector_version`.
- **Nettoyage produit du faux mode Expert** : l’UI ne présente plus `EXPERT GO` comme une capacité backend active.
- **Avertissements debug alignés** sur les règles et sites publiés, au lieu d’une duplication locale dans `reasons-debug.js`.

## 2.1.0 — 2026-07-05
- **Houle multi-modèles** (Open-Meteo Marine `models=`) : MFWAM 0.08°
  primaire avec fallback GFS-Wave 0.25° → ECMWF WAM 0.25° → défaut ;
  modèles parallèles publiés sous `marine_models.*` alignés sur l'axe commun.
- **Confiance « High » débloquée** : exige ≥ 2 modèles de houle concordants
  (écart Hs inter-modèles < 0,2 m sur chaque heure) + accord vent. Une seule
  source de houle ⇒ cap Medium conservé (régression testée).
- **Worst-value-wins étendu aux vagues** : Hs = max des modèles, Tp = min
  (mer la plus raide gagne) ⇒ un modèle pessimiste suffit à bloquer une heure.
- `meta.sources.marine_open_meteo` : `model_used`, `model_order`,
  `parallel_models` ; debug : `marine_models_count`, `marine_parallel_attempts`.
- `rules.yaml` : `http.marine_model_order`, `http.marine_parallel_models`,
  `confidence.high.min_wave_sources` (défaut 2). Ordres de modèles lus depuis
  rules.yaml sauf override env.
- `windows.json` : `confidence_details.min_wave_sources_per_hour` et
  `.max_hs_spread_m`.
- Nouvel outil `tools/probe_marine_models.py` (vérification live des noms de
  modèles avant mise en prod).
- 48 tests (7 nouveaux). Schéma rétro-compatible (ajouts uniquement).

## 2.0.0 — 2026-07-05
Refonte professionnelle complète — voir docs/AUDIT-2026-07.md :
cron horaire + keepalive anti-désactivation, healthcheck externe avec issue
GitHub, statut à fraîcheur côté client, reader immunisé contre les non-spots,
dégradation gracieuse marine, fenêtres bornées 4–6 h, seuils unifiés,
sites.yaml v2 multi-port, package fable/ testé (41 tests), CI ruff+pytest.
