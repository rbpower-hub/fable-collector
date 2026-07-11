# Changelog

## 2.9.0 — 2026-07-11
- **Recommandations d’activités marines** : nouveau moteur `fable.recommendations` exécuté après le reader et limité aux fenêtres Family GO validées.
- **Profils de pêche restaurés et structurés** : `fishing_profiles.yaml` décrit espèces, techniques, montages, appâts, profondeurs et horaires par spot et saison.
- **Seuils par activité** : `activity_profiles.yaml` permet de filtrer pêche au fond, micro-jig, traîne côtière, mouillage abrité et baignade familiale avec des règles plus spécifiques que la navigation générale.
- **Soleil et lune exploités** : lever/coucher, phase et illumination sont publiés dans les recommandations ; le bonus lunaire reste plafonné et ne peut jamais neutraliser un NO-GO.
- **Board enrichi** : ajout du composant « Que faire sur l’eau ? » alimenté par `recommendations.json`.
- **Workflow étendu** : génération et publication automatiques des recommandations dans GitHub Pages.
- **Documentation complète** : README, architecture, runbook et guide dédié aux recommandations mis à jour.
- **Tests de sécurité** : vérification qu’aucune recommandation n’est créée hors Family GO et qu’un seuil d’activité dépassé élimine l’activité.

## 2.8.5 — 2026-07-09
- **Collecte planifiée durcie** : le workflow tente maintenant `3` créneaux par heure, mais ne relance une vraie collecte que si le déploiement live a réellement vieilli.
- **Anti-faux positifs de healthcheck** : le seuil healthcheck reste à `95 min`, mais on réduit fortement les trous de scheduler GitHub qui faisaient partir des emails “run failed”.
- **Logique testée côté Python** : `fable.healthcheck` expose désormais le calcul d’âge live et la décision `should_collect_live`, couverts par des tests ciblés.

## 2.8.4 — 2026-07-08
- **Diagnostic composite par étape** : le panneau des avertissements détaille maintenant séparément `Étape 1`, `Étape 2` et l’`Alignement` pour Pantelleria beta.
- **Raisons de blocage plus lisibles** : chaque étape affiche désormais sa première cause bloquante, avec horodatage lisible, au lieu d’un simple No-GO global.
- **Rendu expert stabilisé** : la vue `Info...` et la section `Avertissements` utilisent le même formateur de dates pour éviter les erreurs d’affichage sur les routes composites.

## 2.8.3 — 2026-07-08
- **Double validation visuelle par étape** : les fenêtres composites Pantelleria affichent maintenant `Étape 1 GO`, `Étape 2 GO` et `GO composite` directement dans le board.
- **Carte corridor plus explicite** : au clic sur une fenêtre composite, la carte et le détail rappellent désormais la validation de chaque segment avec temps, distance et statut visuel.
- **Métadonnées offshore conservées** : le backend publie désormais aussi la confiance et la fenêtre du second segment pour mieux distinguer le relais de la fenêtre finale.

## 2.8.2 — 2026-07-07
- **Relais Kelibia simplifié** : l’itinéraire recommandé depuis Gammarth vers Kelibia ne passe plus par `Ras Fartass`.
- **Route produit réalignée usage réel** : le trajet composite vers Pantelleria suit désormais `Gammarth → El Haouaria → Kelibia → Pantelleria`.
- **Validation composite cohérente** : le contrôle backend et les tests utilisent maintenant `El Haouaria` comme point de passage météo du relais.

## 2.8.1 — 2026-07-07
- **Fallback Pantelleria réaligné** : la configuration front embarquée reflète maintenant le vrai statut `composite_beta` actif, même avant chargement des fichiers normalisés.
- **Corridor composite plus lisible** : la carte affiche désormais un badge dédié par étape pour les routes multi-legs, avec durée et distance de chaque segment.
- **Carte fenêtre enrichie** : le détail d’une fenêtre composite affiche maintenant `Étape 1` / `Étape 2` avec distances et temps de transit, en plus du résumé global.

## 2.8.0 — 2026-07-07
- **Pantelleria passe en composite beta actif** : le moteur publie maintenant des fenêtres beta pour Pantelleria quand le transfert `Gammarth → Kelibia` puis la fenêtre `Kelibia → Pantelleria` s’alignent dans le forecast.
- **Transfert vers Kelibia validé séparément** : le backend contrôle désormais le segment de convoyage via les checkpoints configurés (`Ras Fartass`, `El Haouaria`) avant d’autoriser la suite du plan.
- **Fenêtres composites conservatrices** : Pantelleria ne passe plus sur un simple spot final favorable ; il faut désormais une séquence compatible entre le relais et la sortie offshore.
- **UI alignée produit** : les routes beta continuent d’être exclues du faux debug standard, et les cartes de fenêtres affichent maintenant le pré-transfert composite.

## 2.7.0 — 2026-07-07
- **Kelibia réintégrée comme port relais** : la collecte et les exports normalisés incluent désormais `kelibia`, en plus de Pantelleria beta.
- **Itinéraires mer configurables** : `sites.yaml` accepte maintenant `route_origin` et `route_points` pour préparer des routes multi-legs sans tracer de ligne à travers les terres.
- **Route Gammarth → Kelibia corrigée visuellement** : la carte suit maintenant une route mer via Ras Fartass puis El Haouaria, au lieu de couper le Cap Bon.
- **Pantelleria preview en 2 segments** : l’aperçu affiche désormais `Gammarth → Kelibia → Pantelleria`, avec distance et durée totales, tout en gardant le moteur GO offshore désactivé.
- **Fondation pour le futur GO composite** : les métadonnées de route sont publiées par le backend et prêtes pour la prochaine phase de validation segment par segment.

## 2.6.1 — 2026-07-07
- **Hotfix CI pytest** : le workflow exécute désormais `python -m pytest -q`, aligné sur le check local.
- **Import `fable` fiabilisé** : la CI lance `python -m pytest -q`, aligné sur le check local, ce qui évite les erreurs `ModuleNotFoundError: No module named 'fable'`.
- **Version interne réalignée** : `fable.__version__` reflète enfin la version publiée courante.

## 2.6.0 — 2026-07-07
- **Pantelleria beta publiée proprement** : la destination existe maintenant dans `sites.yaml`, est collectée, publiée dans les fichiers normalisés et visible dans le board.
- **Beta offshore assumée côté produit** : Pantelleria est marquée `beta`, `offshore_beta` et `windows_enabled: false`, pour éviter de présenter de faux `GO` avant le vrai moteur offshore.
- **Carte + corridor enrichis** : cliquer Pantelleria sur la carte ou dans le radar ouvre un aperçu de route avec distance, durée estimée et note produit, même sans fenêtre GO.
- **Radar et infobulles clarifiés** : badge beta, pays, note de route et message explicite “moteur GO pas encore actif”.
- **Reader debug protégé** : `reasons-debug.js` et le dashboard n’essaient plus d’évaluer les routes beta offshore comme des spots Family standards.

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
- **Houle multi-modèles** (Open-Meteo Marine `models=`) : MFWAM 0.08° primaire avec fallback GFS-Wave 0.25° → ECMWF WAM 0.25° → défaut ; modèles parallèles publiés sous `marine_models.*` alignés sur l'axe commun.
- **Confiance “High” débloquée** : exige ≥ 2 modèles de houle concordants (écart Hs inter-modèles < 0,2 m sur chaque heure) + accord vent. Une seule source de houle → cap Medium conservé (régression testée).
- **Worst-value-wins étendu aux vagues** : Hs = max des modèles, Tp = min (mer la plus raide gagne) → un modèle pessimiste suffit à bloquer une heure.
- `meta.sources.marine_open_meteo` : `model_used`, `model_order`, `parallel_models` ; debug : `marine_models_count`, `marine_parallel_attempts`.
- `rules.yaml` : `http.marine_model_order`, `http.marine_parallel_models`, `confidence.high.min_wave_sources` (défaut 2). Ordres de modèles lus depuis `rules.yaml` sauf override env.
- `windows.json` : `confidence_details.min_wave_sources_per_hour` et `.max_hs_spread_m`.
- Nouvel outil `tools/probe_marine_models.py` (vérification live des noms de modèles avant mise en prod).
- 48 tests (7 nouveaux). Schéma rétro-compatible (ajouts uniquement).

## 2.0.0 — 2026-07-05
Refonte professionnelle complète — voir `docs/AUDIT-2026-07.md` : cron horaire + keepalive anti-désactivation, healthcheck externe avec issue GitHub, statut à fraîcheur côté client, reader immunisé contre les non-spots, dégradation gracieuse marine, fenêtres bornées 4–6 h, seuils unifiés, `sites.yaml` v2 multi-port, package `fable/` testé (41 tests), CI ruff+pytest.
