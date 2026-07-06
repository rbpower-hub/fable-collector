# Changelog

## 2.5.0 — 2026-07-06
- **Durée de traversée pilotée par une hypothèse bateau** : le board n’utilise plus une durée fixe identique pour toutes les routes, mais une estimation calculée depuis la distance et `transit_speed_kts`.
- **Hypothèse de vitesse explicite dans l’UI** : le résumé corridor affiche maintenant la fourchette retenue en nœuds, pour pouvoir l’ajuster facilement au bateau réel.
- **`sites.yaml` enrichi** avec `defaults.transit_speed_kts`, publié dans `sites.normalized.json` pour garder la logique de durée côté config.
- **Ras Fartass réaligné produit** : avec le profil par défaut actuel, la traversée affichée retombe dans un ordre de grandeur cohérent avec un semi-rigide rapide.
- **Pantelleria évaluée** : ajout pur de destination possible plus tard, mais le moteur reste aujourd’hui orienté sortie home→destination Family Day et n’implémente pas encore de vrai corridor offshore.

## 2.4.0 — 2026-07-06
- **Carte découplée des coordonnées météo** : `sites.yaml` accepte désormais `map_lat` / `map_lon` pour garder une position visuelle exacte sans bouger le point de collecte.
- **Position précise restaurée pour Gammarth** et anciennes positions carte réinjectées dans la configuration des spots actuels.
- **`sites.normalized.json` enrichi** avec les coordonnées de carte publiées par le backend pour éviter tout nouveau décalage côté UI.
- **Carte et radar plus interactifs** : cliquer un spot ou la ligne radar ouvre directement le corridor correspondant quand une fenêtre existe.
- **Résumé corridor sous la carte** : la vue garde un rappel lisible du trajet sélectionné, des durées de transit et de la phase mouillage.

## 2.3.0 — 2026-07-06
- **Version dédiée corridor + carte** pour garder un rollback simple après la phase board `2.2.0`.
- **`rules.normalized.json` enrichi** avec `family.corridor.leg_structure_hours`, pour publier les durées transit aller, mouillage et retour au lieu de les recoder côté UI.
- **Carte pilotée par `sites.normalized.json`** pour le cadrage initial et le reset, y compris quand la liste de spots évolue.
- **Corridor piloté par `rules.normalized.json`** : résumé transit, badge de durée et animation aller/retour suivent la règle active publiée par le backend.
- **Liens bruts simplifiés** : les icônes des spots ne dépendent plus d'une liste de fichiers codée en dur.

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
