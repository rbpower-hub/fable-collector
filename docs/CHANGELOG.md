# Changelog

## Non publié
- **Inversion de sécurité corrigée sur le palier prudent** : `hour_ok_for_phase` étant écrit en `if / elif`, la branche prudent remplaçait la branche famille au lieu de s'y ajouter, et sautait la matrice `tp_matrix`. À `Hs = 0,40 m`, une heure refusée par le palier famille pour mer courte était repêchée par le palier prudent et publiée en GO PRUDENT, avec la règle qui l'interdisait rangée dans ses `cautions`. Le palier prudent applique désormais les règles de vague du palier standard en plus des siennes. L'élargissement voulu de l'enveloppe de vent est conservé.
- **Board Expert filtrable par port** : la carte « Que faire sur l'eau ? » rendait toutes les recommandations du fichier, sans notion de port sélectionné. Cliquer un port dans le tableau Expert ne changeait rien, et avec une seule recommandation le panneau semblait figé. Le tableau émet désormais `fable:spot-selected`, le board s'y accroche, affiche un bandeau avec le port retenu et un bouton pour revenir à tous les ports.
- **Vues Famille et Simple d'accord sur les compteurs** : la Vue Famille ne lisait que les fenêtres de catégorie `family`. Un long trajet placé hors des heures familiales lui était invisible, et la journée affichait « 0 créneaux long trajet » pendant que la Vue Simple en annonçait quatre pour la même date. Les compteurs et l'état de la journée lisent désormais le même jeu de catégories, et les créneaux hors horaires sont mentionnés au lieu d'être passés sous silence. La liste des choix reste familiale.
- **Vue Simple : les activités suivent la fenêtre dépliée** : la section était toujours calculée sur la meilleure fenêtre de la journée. Déplier Ras Fartass laissait donc les activités sur Gammarth, et la carte semblait figée alors qu'elle répondait à une autre question. Déplier une fenêtre change désormais la section, replier la ramène à la meilleure du jour, et changer de journée oublie la sélection.
- **Suite visuelle déterministe** : les scénarios construisaient leur fenêtre à « maintenant + 60 minutes ». Passé 23:00 heure de Tunis, cette fenêtre tombait le lendemain, la journée sélectionnée se retrouvait vide et les sept jobs échouaient, uniquement à cause de l'heure à laquelle la CI tournait. Le fixture et l'horloge de la page sont désormais figés sur le même instant.
- **Vue Simple, compteur cohérent** : l'en-tête « Fenêtres de navigation » annonçait 7 options là où la carte du jour en annonçait 2, sur la même journée. `navigationWindowCounts` calcule `family = total − longTrip` et suppose une liste déjà filtrée sur la catégorie famille ; la liste passée contenait aussi les créneaux hors horaires. L'en-tête utilise désormais `navigationWindowBreakdown` et détaille famille, hors horaires, watch et long trajet.
- **Vue Simple, les FAMILY GO ne disparaissent plus** : la liste est coupée à cinq lignes, en ordre chronologique. Une journée portant cinq créneaux hors horaires à 05:00 puis deux fenêtres FAMILY GO à 11:00 n'affichait aucune fenêtre familiale. Les lignes sont ordonnées par utilité — famille, prudent, hors horaires, watch, long trajet — puis par heure.
- **Vue Simple, le port est nommé** : chaque activité conseillée indique la destination et son créneau. La section ne disait pas à quoi elle se rapportait.
- **Fenêtres familiales rétablies dans le board** : le plafond de recommandations était dépensé dans l'ordre chronologique de la journée, donc une fenêtre hors horaires à 05:00 passait devant une fenêtre famille à 11:00. Sur quatorze fenêtres côtières, le plafond de 5 ne gardait que des créneaux nocturnes et jetait les deux seules fenêtres famille du lundi. Le budget est désormais réparti par jour, par catégorie (famille avant hors horaires) et par destination, et les valeurs par défaut passent à 12 recommandations dont 4 par journée.
- **Créneau réduit par activité** : les seuils portaient sur le maximum de la fenêtre, donc une seule heure hors limite écartait l'activité pour toute la fenêtre. Le moteur cherche maintenant la plus longue plage contiguë où l'activité tient et la propose sur son propre créneau, à condition d'atteindre une durée minimale (2 h par défaut). Le créneau reste strictement inclus dans la fenêtre Family GO validée : rien n'est créé, seul ce qui était déjà validé est découpé. Score et justifications sont recalculés sur le créneau.
- **Couverture visuelle de la section activités** : aucun scénario ne peuplait `recommendations`, la section n'était donc jamais rendue par la suite visuelle. Un septième scénario, mobile hors horaires, vérifie que l'activité s'affiche et que la raison du blocage nocturne est visible.
- **Aucune baignade nocturne** : une fenêtre hors horaires peut être parfaite au sens météo et courir en pleine nuit. Le moteur proposait une baignade familiale et du paddle à une heure du matin, à 100/100. Baignade, masque et tuba, paddle et observation nature déclarent maintenant `requires_daylight` et sont écartées, avec la raison affichée, quand la fenêtre est majoritairement nocturne. La pêche au lever du jour reste légitime et n'est pas concernée.
- **Vue Simple : activités hors horaires visibles** : la section filtrait sur la catégorie `family`, alors que `window_detect` ne distingue `family` de `off_hours` que par la lumière du jour, à seuils météo identiques. Une journée dont les seules fenêtres sont hors horaires affichait « aucune activité compatible » alors que le moteur en avait calculé pour ces fenêtres précisément. Le garde-fou est passé de la vue au moteur, par activité.
- **Vue Simple : raisons de blocage** : quand aucune activité ne passe, la section nomme les activités principales écartées et la limite qui les bloque, au lieu du seul message générique.
- **Quatre nouvelles activités** : masque et tuba, paddle ou kayak, observation nature, et pêche au leurre souple. Cette dernière comble un trou du pack : la technique `soft-lure` existait sans activité correspondante, donc un port dont la saison ne listait que le leurre souple ne recevait aucune activité de pêche.
- **Réserves de confort sur toutes les activités** : les neuf déclarent un bloc `comfort`. Ce sont des pénalités de classement et des réserves affichées, jamais des blocages.
- **Vent de terre distingué du vent de mer** : `offshore_share` est calculé sur le secteur opposé et non comme le complément de `onshore_share`, un vent parallèle à la côte n'étant ni l'un ni l'autre. Le vent de mer pénalise la baignade et la pêche, le vent de terre pénalise le paddle et le kayak, et le conseil de fenêtre nomme désormais la dérive vers le large au lieu de ne vanter que l'eau lissée.
- **Rang principal et secondaire** : une activité tolérante obtenait mécaniquement un meilleur score qu'une activité exigeante, le score pénalisant le rapport valeur/limite. L'observation nature passait devant la pêche un jour parfait. Les activités secondaires sont maintenant classées après toutes les principales, et une fenêtre servie uniquement par une secondaire publie quand même la raison du blocage des principales.
- **Contenu nature sourcé** : El Haouaria au printemps et Ghar el Melh en hiver, chacun avec sa référence publique affichée dans le board. Aucun port sans source n'a de contenu.
- **Compteur d'options unifié** : les Vues Simple, Famille et Expert annonçaient 49, 4 et 2 options pour la même journée. Une option est désormais une fenêtre famille, les créneaux hors horaires et watch sont comptés à part, et les longs trajets sont comptés par route et non par heure de départ.
- **Fenêtre validée sans activité** : le moteur publie `no_activity` avec les activités les plus proches d'être acceptées et la limite qui les bloque. La carte dit « rafales 35 km/h pour une limite de 28 km/h » au lieu de « aucune activité spécialisée ».
- **Classement départageable** : le tri se fait sur le score non plafonné ; deux activités dont les bonus dépassaient 100 sortaient à égalité parfaite et leur ordre était arbitraire.
- **Libellé de journée en Vue Expert** : le board annonçait « Activités du lundi » au-dessus de cartes de toutes les journées, puisque le filtre par jour ne s'applique qu'en mode famille.
- **Créneaux corrigés** : une fenêtre est classée sur les moments qu’elle *recouvre* et non sur son instant de départ ; une sortie 15:00→19:00 couvrant un coucher à 18:54 n’est plus étiquetée « journée ».
- **Marée mesurée** : lorsque `sea_level_height_msl` est disponible, le bonus lunaire est remplacé par le marnage réellement observé sur la fenêtre ; la phase de lune ne sert plus que de repli.
- **Lune au-dessus de l’horizon** : `moonrise`/`moonset` déterminent si la lune est visible pendant la fenêtre, au lieu de supposer qu’une pleine lune éclaire toute la nuit.
- **Conseils de confort** : UV, ressenti, vent de mer / vent de terre et pluie produisent des conseils bilingues. Ils ne bloquent jamais une activité ; la sécurité reste entièrement du ressort du moteur de fenêtres.
- **Justifications chiffrées** : chaque activité affiche la valeur mesurée face à sa limite (« vent 10 km/h pour une limite de 18 km/h ») au lieu d’un score nu.
- **Raisons de NO-GO affichées** : le premier bloqueur connu du moteur est publié et rendu dans le board, au lieu de sept lignes identiques « aucune fenêtre validée ». Le lieu n’est cité que s’il diffère de la destination.
- **Répartition sur les jours** : le plafond de recommandations est appliqué en tourniquet par jour ; une journée riche n’efface plus les deux suivantes.
- **Température d’eau et niveau de la mer** : appel Open-Meteo distinct et strictement facultatif, isolé de la chaîne de repli des modèles de vagues pour ne jamais compromettre la sécurité.
- **Vocabulaire lisible** : les identifiants du Knowledge Pack (`micro_jig_5_12_g`) et les nombres décimaux sont formatés selon la langue affichée.
- **Vue Simple expérimentale** : nouveau mode mobile volontaire centré sur la décision, la meilleure destination, la fenêtre de sortie et un aperçu de trois jours, sans modifier la décision de sécurité Python.
- **Visualisation opérationnelle** : frise horaire GO / prudent / NO-GO et graphiques vent/houle avec limites Family, plages min–max, tendances et heure limite de retour.
- **Accessibilité** : français, anglais et arabe RTL, navigation clavier, focus visibles, contraste forcé, réduction des animations et adaptations de 320 px au bureau.
- **Adoption réversible** : entrée « Essayer la Vue Simple », préférence locale au navigateur et accès durable aux Vues Famille et Expert.
- **Faux échecs de collecte corrigés** : `schedule_guard` dispose de 10 minutes au lieu de 3 afin que la préparation parfois lente d’un runner GitHub ne l’annule plus avant le checkout.
- **Healthcheck plus robuste** : budget de 12 minutes pour couvrir le provisionnement, les accès réseau et les cinq tentatives de confirmation sans supprimer l’échec final en cas de panne persistante.
- **Diagnostic d’exploitation** : le runbook distingue désormais une panne réelle de production d’un job que GitHub Actions n’a jamais attribué à un runner.

## 3.3.0 — 2026-07-15
- **Horizon 72 h** : la collecte planifiée couvre désormais trois jours complets par défaut.
- **Vue Famille trois jours** : Aujourd’hui, Demain et J+2 sont regroupés dans trois cartes responsive, horizontales sur mobile et en colonnes sur PC.
- **Kélibia multi-jours** : Gammarth→Kélibia et Kélibia→Gammarth sont évalués comme deux trajets indépendants ; aucun retour le jour même n’est imposé.
- **Planificateur longue distance** : les premiers aller et retour compatibles sont rapprochés pour Kélibia et Pantelleria, avec alerte explicite si aucun retour n’existe dans les 72 h.
- **`windows.json` v5** : généralisation de `trip_mode: one_way_multi_day` et `route_kind` aux trajets longs côtiers et offshore.
- **Sécurité inchangée** : chaque jambe applique les règles Family strictes ; un aller validé ne valide jamais implicitement le retour ou l’ensemble du séjour.
- **Compatibilité** : les champs offshore Pantelleria historiques sont conservés pour les consommateurs existants.

## 3.2.0 — 2026-07-15
- **Vue Famille par défaut** : interface décisionnelle distincte de la Vue Expert historique, sans suppression des données avancées.
- **Quatre onglets responsive** : `Aujourd’hui`, `Activités`, `Carte` et `Détails` pour réduire le défilement et hiérarchiser les informations.
- **Résumé immédiat** : prochaine destination Family GO, horaire, niveau standard/prudent, confiance, nombre d’options et fraîcheur des données.
- **NO-GO lisible** : lorsqu’aucune sortie n’est validée, la synthèse reprend directement le meilleur diagnostic backend disponible.
- **Radar et données brutes déplacés** : ils restent disponibles dans `Détails` et dans la Vue Expert, mais ne chargent plus l’écran principal familial.
- **Carte secondaire** : la carte n’occupe plus l’ouverture du board en Vue Famille ; elle possède son propre onglet et conserve les interactions existantes.
- **Mobile first** : outils du header défilables, navigation compacte, cartes sans scroll interne et grille adaptée aux petits écrans.
- **Préférences persistantes** : mémorisation locale du mode Famille/Expert et du dernier onglet utilisé.
- **Sécurité inchangée** : la vue consomme exclusivement `windows.json`, `recommendations.json` et les diagnostics déjà décidés par le backend.

## 3.1.2 — 2026-07-14
- **Affichage offshore one-way corrigé** : la carte Pantelleria ne cumule plus le pré-positionnement Gammarth→Kélibia avec la traversée Kélibia→Pantelleria.
- **Traversée isolée** : Pantelleria affiche uniquement environ 76 km / 41 NM / 1 h 45–2 h 15.
- **Pré-positionnement séparé** : Gammarth→Kélibia reste consultable indépendamment en sélectionnant Kélibia.
- **Aucune modification sécurité** : les seuils et décisions météo restent inchangés.

## 3.1.1 — 2026-07-14
- **Interface premium allégée** : la carte « Routes & abris » n’est chargée dans le navigateur que lorsqu’au moins une route ou un abri possède une validation explicite.
- **Données non validées masquées** : les calculs internes restent disponibles dans `port-knowledge.json`, mais ne sont plus présentés à l’utilisateur final.
- **Corridor cap Bon corrigé** : remplacement de la corde El Haouaria→Kélibia qui traversait visuellement la péninsule par six points maritimes au large du cap et de sa côte orientale.
- **Distance Kélibia recalculée** : le trajet configuré Gammarth→Kélibia passe d’environ 49,3 NM à 54,9 NM ; le tronçon maritime depuis le point El Haouaria configuré jusqu’à Kélibia passe d’environ 13,6 NM à 19,1 NM.
- **Temps de transit révisé** : environ 2,29 à 3,05 h pour Gammarth→Kélibia avec l’hypothèse 18–24 nd.
- **Sécurité** : le nouveau tracé reste indicatif et doit être confirmé sur cartes nautiques officielles avant navigation.
- **Tests** : contrôle des six waypoints, de la nouvelle distance et de l’absence d’affichage sans validation.

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
