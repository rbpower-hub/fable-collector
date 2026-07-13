# Changelog

## 3.0.0 — 2026-07-13
- **Family GO prudent** : ajout d’un niveau intermédiaire clairement signalé, évalué seulement après l’échec du niveau Family standard.
- **Vétos durs inchangés** : orage, visibilité insuffisante, rafales ≥30 km/h, vent ≥25 km/h, mer dure courte/raide et données indispensables manquantes restent bloquants.
- **Limites prudentes initiales** : vent ≤22 km/h, rafales <28 km/h, Hs ≤0,40 m, Tp ≥3,5 s, vent non onshore et confiance au moins Medium.
- **Diagnostics backend** : chaque destination publie dans `windows.json` le premier blocage réel, son étape, son lieu, son heure, ses métriques et une explication FR/EN.
- **Near miss** : publication du nombre d’heures déjà validées par rapport à la durée requise.
- **Avertissements fiabilisés** : le board utilise désormais le diagnostic Python au lieu d’une réévaluation simplifiée dans le navigateur ; les blocages de départ et de retour à Gammarth deviennent visibles.
- **Durée adaptative** : plancher de 3 h pour les trajets courts et durée requise calculée depuis le transit lent aller-retour plus 1,5 h minimale sur zone.
- **Plage solaire** : lever/coucher du soleil utilisés avec marges quand disponibles ; repli sur les horaires fixes.
- **Abri conditionnel** : les tolérances de mouillage ne s’appliquent que si un rayon d’abri est explicitement configuré et que le vent n’est pas onshore.
- **Board et recommandations** : badge orange `FAMILY GO PRUDENT`, avertissement de confort réduit et propagation vers la carte des activités.
- **Architecture modulaire** : séparation en `window_models`, `window_policy` et `window_detect` avec API rétro-compatible dans `fable.windows`.
- **Documentation** : README mis à jour et nouveau guide `docs/FAMILY-GO-PRUDENT.md`.
- **Tests** : couverture du mode prudent, des vétos durs, du retour bloqué, de la durée adaptative, de la lumière et de l’abri.

## 2.10.0 — 2026-07-12
- **Knowledge Pack v2** : activation du schéma `fish_intelligence`, du matériel terminal et des métadonnées de validation.
- **Onze profils enrichis** : techniques compatibles, appâts naturels, leurres, présentations, plages d’hameçons, bas de ligne et plomb indicatifs.
- **Quatre techniques enrichies** : montages, configurations d’hameçons, grammages, diamètres et modes de présentation structurés.
- **Validation stricte** : références espèce→technique, plages numériques, structure des hameçons et maintien obligatoire de la validation locale.
- **Noms locaux protégés** : les appellations ambiguës restent marquées comme nécessitant une validation taxonomique ; aucune identification scientifique n’est forcée.
- **Sortie v3** : `recommendations.json` publie `species_details[].targeting` et `technique_details[].gear` ; `knowledge.json` expose le schéma et le résumé de validation.
- **Board Fish Intelligence** : affichage compact des appâts/leurres, montage, hameçons, bas de ligne et plomb pour l’espèce prioritaire, avec badge indicatif.
- **Sécurité inchangée** : les réglages restent en aval de Family GO et la lune ne neutralise jamais un NO-GO.
- **Documentation et tests** : nouveau guide `docs/FISH-INTELLIGENCE.md`, README mis à jour et tests de schéma/recommandations v3.

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
- **Transfert vers Kelibia validé séparément** : le backend contrôle désormais le segment de convoyage via les checkpoints configurés avant d’autoriser la suite du plan.
- **Fenêtres composites conservatrices** : Pantelleria ne passe plus sur un simple spot final favorable ; il faut une séquence compatible entre le relais et la sortie offshore.
- **UI alignée produit** : les cartes de fenêtres affichent le pré-transfert composite.

## 2.7.0 — 2026-07-07
- **Kelibia réintégrée comme port relais** : la collecte et les exports normalisés incluent désormais `kelibia`, en plus de Pantelleria beta.
- **Itinéraires mer configurables** : `sites.yaml` accepte `route_origin` et `route_points` pour préparer des routes multi-legs sans tracer de ligne à travers les terres.
- **Route Gammarth → Kelibia corrigée visuellement** : la carte suit une route mer via El Haouaria.
- **Pantelleria preview en 2 segments** : l’aperçu affiche `Gammarth → Kelibia → Pantelleria`, avec distance et durée totales.
- **Fondation pour le futur GO composite** : les métadonnées de route sont publiées par le backend.

## 2.6.1 — 2026-07-07
- **Hotfix CI pytest** : le workflow exécute désormais `python -m pytest -q`, aligné sur le check local.
- **Import `fable` fiabilisé** : l’appel par module évite les erreurs `ModuleNotFoundError`.
- **Version interne réalignée** : `fable.__version__` reflète la version publiée.

## 2.6.0 — 2026-07-07
- **Pantelleria beta publiée proprement** : la destination existe dans `sites.yaml`, est collectée et visible dans le board.
- **Beta offshore assumée côté produit** : Pantelleria reste clairement marquée beta.
- **Carte + corridor enrichis** : aperçu de route avec distance, durée estimée et note produit.
- **Radar et infobulles clarifiés** : badge beta, pays et note de route.
- **Reader debug protégé** : les routes beta offshore ne sont pas traitées comme des spots Family standards.

## 2.5.0 — 2026-07-06
- **Durée de traversée pilotée par une hypothèse bateau** : estimation depuis `transit_speed_kts`.
- **Hypothèse de vitesse explicite dans l’UI**.
- **`sites.yaml` enrichi** avec `defaults.transit_speed_kts`.
- **Ras Fartass réaligné produit**.
- **Pantelleria évaluée** comme future route offshore.

## 2.4.0 — 2026-07-06
- **Carte découplée des coordonnées météo** avec `map_lat` / `map_lon`.
- **Position précise restaurée pour Gammarth**.
- **`sites.normalized.json` enrichi**.
- **Carte et radar plus interactifs**.
- **Résumé corridor sous la carte**.

## 2.3.0 — 2026-07-06
- **Version dédiée corridor + carte**.
- **`rules.normalized.json` enrichi** avec les durées des phases.
- **Carte et corridor pilotés par les configurations normalisées**.
- **Liens bruts simplifiés**.

## 2.2.0 — 2026-07-06
- **Version dédiée board**.
- **Board branché sur `sites.normalized.json` et `rules.normalized.json`**.
- **Confiance enrichie dans l’UI**.
- **Santé live enrichie**.
- **Nettoyage du faux mode Expert**.
- **Avertissements alignés sur les règles et sites publiés**.

## 2.1.0 — 2026-07-05
- **Houle multi-modèles** avec fallbacks et modèles parallèles.
- **Confiance High** exigeant au moins deux modèles de houle concordants.
- **Worst-value-wins étendu aux vagues** : Hs maximale et Tp minimale.
- **Métadonnées de sources et de spreads publiées**.
- **Outil de vérification des modèles marine**.

## 2.0.0 — 2026-07-05
Refonte professionnelle complète — voir `docs/AUDIT-2026-07.md` : cron horaire, healthcheck externe, statut de fraîcheur, dégradation gracieuse marine, seuils unifiés, `sites.yaml` v2 multi-port, package `fable/` testé et CI Ruff + Pytest.
