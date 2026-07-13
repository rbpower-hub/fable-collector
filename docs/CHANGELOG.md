# Changelog

## 3.1.0 — 2026-07-13
- **Pantelleria en aller simple offshore** : Kélibia→Pantelleria et Pantelleria→Kélibia sont évaluées comme deux traversées indépendantes.
- **Séjour multi-jours** : aucun retour à Gammarth le même jour n’est exigé ; le pré-positionnement Gammarth↔Kélibia reste une opération séparée.
- **`windows.json` v4** : ajout de `trip_mode: one_way_multi_day`, `direction: outbound|return` et `same_day_round_trip_required: false`.
- **Offshore strict** : seules les limites Family strictes sont utilisées ; aucun mode prudent offshore dans cette version.
- **Navigation sans loisirs** : les traversées sont publiées sous `navigation_only` et ne génèrent aucune recommandation automatique de baignade, mouillage ou pêche.
- **Port Knowledge** : nouvel endpoint `port-knowledge.json` avec distances configurées, hypothèses de vitesse, temps de transit, politiques de retour et statut des abris.
- **Shelter Intelligence v1** : aucun bonus d’abri sans coordonnées, secteurs de protection, fetch positif et validation terrain explicite.
- **Knowledge Pack v3** : nouveaux schémas `port_navigation`, `shelter_intelligence` et `offshore_one_way` ; Pantelleria devient un profil de navigation sans profil de pêche local.
- **Dashboard** : nouvelle carte « Routes & abris » avec distinction côtier / offshore one-way.
- **Exploitation** : la CI conserve désormais un rapport JUnit téléchargeable pour faciliter le diagnostic des régressions.
- **Tests** : couverture des directions aller/retour, de l’absence d’aller-retour le même jour, de Port Knowledge et de l’exclusion des activités pendant la traversée.

## 3.0.1 — 2026-07-13
- **Hotfix `route_origin`** : les valeurs JSON `null` ne sont plus transformées en faux relais `none`.
- **Ports standards restaurés** : suppression du message erroné « Port relais introuvable dans la configuration ».
- **Diagnostics rétablis** : Ghar El Melh et les autres ports reçoivent de nouveau leurs vraies causes météo, durée, lumière ou confiance.
- **Route Pantelleria protégée** : le dispatch composite n’est plus rejeté prématurément sur la distance directe depuis Gammarth.

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
- **Carte corridor plus explicite** : la carte et le détail rappellent désormais la validation de chaque segment avec temps, distance et statut visuel.
- **Métadonnées offshore conservées** : le backend publie désormais aussi la confiance et la fenêtre du second segment.

## 2.8.2 — 2026-07-07
- **Relais Kelibia simplifié** : l’itinéraire recommandé depuis Gammarth vers Kelibia ne passe plus par `Ras Fartass`.
- **Route produit réalignée** : le trajet composite vers Pantelleria suit `Gammarth → El Haouaria → Kelibia → Pantelleria`.
- **Validation composite cohérente** : le contrôle backend et les tests utilisent El Haouaria comme point de passage météo.

## 2.8.1 — 2026-07-07
- **Fallback Pantelleria réaligné** : la configuration front embarquée reflète le statut beta actif.
- **Corridor composite plus lisible** : la carte affiche un badge dédié par étape.
- **Carte fenêtre enrichie** : le détail affiche les distances et temps de transit.

## 2.8.0 — 2026-07-07
- **Pantelleria composite beta** : première validation séquentielle transfert + fenêtre offshore.
- **Transfert vers Kelibia validé séparément** : contrôle des checkpoints configurés.
- **Fenêtres composites conservatrices** : séquence complète obligatoire dans cette ancienne logique.

## 2.7.0 — 2026-07-07
- **Kelibia réintégrée comme port relais**.
- **Itinéraires mer configurables** avec `route_origin` et `route_points`.
- **Route Gammarth → Kelibia** corrigée visuellement via El Haouaria.
- **Fondation du moteur composite**.

## 2.6.1 — 2026-07-07
- **Hotfix CI pytest** : exécution via `python -m pytest -q`.
- **Import `fable` fiabilisé**.
- **Version interne réalignée**.
