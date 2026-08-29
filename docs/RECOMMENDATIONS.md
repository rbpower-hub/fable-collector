# Recommandations d’activités et de pêche

## Objectif

La couche de recommandations répond à la question **« Que faire sur l’eau ? »** après validation d’une fenêtre par le moteur Family GO.

Elle ne remplace pas le moteur de sécurité et ne crée jamais de fenêtre. Son entrée principale est `public/windows.json`.

## Ordre impératif des décisions

1. collecte et validation des données météo et marine ;
2. détection d’une fenêtre Family GO ;
3. chargement et validation du Knowledge Pack ;
4. vérification des seuils propres à chaque activité ;
5. classement des activités restantes ;
6. enrichissement avec saison, espèces, techniques, soleil et lune.

Si une destination ne possède aucune fenêtre Family GO, elle apparaît dans `no_go` et aucune activité n’est proposée.

L’entrée `no_go` reprend le premier bloqueur déjà connu du moteur
(`diagnostics.first_blocker`) : la cause, la phase du trajet, et le lieu
seulement lorsqu’il diffère de la destination. Sur un trajet direct, « à
El Haouaria » pour El Haouaria n’apprend rien ; sur une route par étapes,
« à Kelibia » pour Pantelleria est l’information utile.

## Sources de connaissance

### Source principale : `knowledge/`

Le Knowledge Pack versionné contient :

```text
knowledge/
  manifest.yaml
  fish/*.yaml
  techniques/*.yaml
  ports/*.yaml
  activities/*.yaml
```

Le moteur `fable.knowledge` vérifie les identifiants et les références croisées. Une espèce ou une technique inconnue bloque la génération et donc le déploiement.

Voir [KNOWLEDGE-PACK.md](KNOWLEDGE-PACK.md) pour le schéma détaillé.

### Compatibilité transitoire

La migration reste progressive :

- un port présent dans `knowledge/ports/` utilise le nouveau modèle structuré ;
- un port non encore migré utilise temporairement `fishing_profiles.yaml` ;
- si le dossier `knowledge/` est absent, `activity_profiles.yaml` et `fishing_profiles.yaml` restent les sources actives.

Cette compatibilité évite de supprimer les profils existants pendant la migration port par port.

## Calcul des métriques

Pour chaque fenêtre, le moteur extrait du JSON du spot :

- vent maximal ;
- rafale maximale ;
- Hs maximale ;
- Tp minimale ;
- visibilité minimale ;
- nombre d’heures échantillonnées ;
- indice UV maximal ;
- température ressentie et température de l’air maximales ;
- cumul de précipitations ;
- température de surface de la mer, si disponible ;
- `onshore_share` : part des heures où le vent souffle depuis un secteur onshore du spot.

Ces métriques représentent les conditions les plus défavorables de la fenêtre pour l’activité.

Les cinq premières décident. Les suivantes ne servent qu’au classement et aux
conseils de confort : aucune d’elles ne peut refuser une activité ni en autoriser
une que les seuils ont écartée.

## Sélection des activités

Une activité est éliminée si :

- un profil de pêche requis est absent ;
- aucune technique structurée du port ne correspond à l’activité, lorsque ces références sont disponibles ;
- le vent, les rafales ou Hs dépassent le maximum ;
- Tp descend sous le minimum ;
- la visibilité descend sous le minimum.

Une fenêtre Family GO peut donc rester navigable alors qu’une activité particulière est refusée.

## Classement

Le score part de 100 et diminue à mesure que les conditions se rapprochent des limites de l’activité.

Chaque pénalité est publiée en clair, avec la valeur mesurée face à la limite de
l’activité : « vent 10 km/h pour une limite de 18 km/h ». Un score nu n’était pas
vérifiable par l’utilisateur.

Des bonus limités peuvent être ajoutés :

- correspondance avec une période préférentielle du profil saisonnier ;
- signal lunaire ou marégraphique secondaire lorsque `lunar_sensitive: true`.

Le classement se fait sur le score **non plafonné** (`rank_score`), l'affichage
sur le score plafonné (`score`). Sans cette distinction, deux activités dont les
bonus dépassent 100 sortaient toutes les deux à 100,0 et leur ordre devenait
arbitraire.

Le score affiché est plafonné à 100. Ni la lune ni la marée ne peuvent compenser un dépassement de seuil ou un NO-GO.

### Créneaux d’une fenêtre

Une fenêtre est rattachée aux moments qu’elle **recouvre**, pas à celui de son
instant de départ. Une bande de 90 minutes autour du lever et du coucher définit
`sunrise` et `sunset` ; le reste est `day` ou `night`. Une fenêtre peut donc
porter plusieurs créneaux à la fois.

Le classement précédent lisait l’heure de départ à deux heures près : une sortie
15:00→19:00 couvrant un coucher à 18:54 sortait en `day` et perdait son bonus,
tandis qu’une fenêtre démarrant à 20:00, en pleine nuit, sortait en `sunset`.

### Marée réelle avant phase de lune

Si `sea_level_height_msl` est présent sur la fenêtre, le bonus est calculé sur le
**marnage mesuré** : l’écart entre le niveau le plus haut et le plus bas de la
fenêtre, rapporté à `ranking.tide_range_full_bonus_m` (0,25 m par défaut sur la
côte tunisienne). Le sens du courant, montant ou descendant, est publié avec.

La phase de lune n’intervient qu’en repli, quand aucune donnée de marée n’est
disponible. Elle est alors pondérée par `moon_above_horizon`, calculé depuis
`moonrise` et `moonset` : une pleine lune sous l’horizon n’éclaire rien.

## Fenêtre validée sans activité

Une fenêtre peut être Family GO et ne recevoir aucune activité : le moteur de
fenêtres autorise des rafales jusqu'à 30 km/h, alors qu'une escale côtière
s'arrête à 28 et une baignade familiale à 22. Une seule heure en fin de créneau
suffit à écarter toutes les activités, puisque les seuils portent sur le
maximum de la fenêtre.

Ces fenêtres sont publiées dans `no_activity`, avec les deux activités les plus
proches d'être acceptées et, pour chacune, la limite qui bloque et sa valeur :

```json
{
  "dest_name": "Gammarth (port)",
  "start": "2026-08-31T08:00:00+01:00",
  "closest": [
    {"label_fr": "Escale côtière abritée", "reason_fr": "rafales 35 km/h pour une limite de 28 km/h"}
  ]
}
```

Quand plusieurs limites sont dépassées, celle retenue est le dépassement
**relatif le plus large** : c'est la contrainte qui décide réellement, les
autres tomberaient d'elles-mêmes si on la levait.

Le board affiche ce détail sous la carte de repli, à la place du seul message
« aucune activité spécialisée ne passe ses propres limites de confort ».

## Compter les options

Trois vues posaient la même question et donnaient trois réponses : 49, 4 et 2
pour le même lundi. Une seule définition fait foi désormais :

- **une option** est une fenêtre de catégorie `family` ;
- les créneaux `off_hours` et `watch` sont comptés à part et gardent leur propre
  mention ;
- les longs trajets sont comptés **par route**, pas par heure de départ : un
  aller Kelibia→Pantelleria proposé à quinze heures différentes reste une route.

`navigationWindowCounts` et `navigationWindowBreakdown` partagent la même
règle, et `tests/js/navigation-windows.test.mjs` épingle l'égalité entre les
deux sur une journée mixte.

## Catalogue d'activités

Neuf activités, dont quatre ajoutées à la phase contenu.

| Activité | Vent | Rafales | Hs | Rang |
|---|---|---|---|---|
| Escale côtière abritée | 18 | 28 | 0,35 | principal |
| Baignade familiale | 14 | 22 | 0,25 | principal |
| Masque et tuba | 13 | 20 | 0,20 | principal |
| Paddle ou kayak | 15 | 23 | 0,30 | principal |
| Pêche au fond légère | 18 | 28 | 0,45 | principal |
| Micro-jig / jig léger | 16 | 26 | 0,40 | principal |
| Traîne côtière | 20 | 28 | 0,50 | principal |
| Pêche au leurre souple | 17 | 27 | 0,40 | principal |
| Observation nature | 20 | 28 | 0,45 | **secondaire** |

`soft-lure` existait comme technique dans le pack sans activité correspondante.
Un port dont la saison ne listait que le leurre souple ne recevait donc aucune
activité de pêche, ce qui était le cas d'El Haouaria au printemps et en été.

### Rang principal et secondaire

Le score pénalise le rapport entre la valeur mesurée et la limite de
l'activité. Une activité tolérante obtient donc mécaniquement un meilleur score
qu'une activité exigeante dans les mêmes conditions : son rapport est plus
petit. Sans correctif, l'observation nature passerait devant la pêche un jour
parfait.

Une activité peut déclarer `tier: secondary`. Le classement place toutes les
principales avant toutes les secondaires, quel que soit le score. Et une fenêtre
où seule une activité secondaire passe reste traitée comme une fenêtre sans
activité principale : elle publie `blocked_primary` avec les activités écartées
et la limite qui les bloque.

### Répartition du plafond

`ranking.max_total` limite le nombre de recommandations publiées, et
`max_per_day` le nombre par journée. La façon de dépenser ce budget compte
autant que sa taille.

Le tri à l'intérieur d'une journée était chronologique. Une fenêtre hors
horaires à 05:00 passait donc devant une fenêtre famille à 11:00 du seul fait
de l'heure, et le plafond effaçait ensuite les fenêtres familiales. Sur le feed
du 29 août, sur quatorze fenêtres côtières, le plafond de 5 ne gardait que
cinq créneaux nocturnes et une fenêtre du surlendemain : **les deux seules
fenêtres famille du lundi étaient jetées**.

Trois règles corrigent cela :

- **par jour** : chaque journée de l'horizon garde une place, un jour chargé
  n'efface plus les suivants ;
- **par mérite** : dans une journée, les fenêtres `family` passent avant
  `off_hours`, puis `watch`, et à catégorie égale le meilleur score l'emporte ;
- **par destination** : une première passe sert une fenêtre par port, la
  meilleure, avant qu'un port n'en reçoive une seconde. Sinon deux fenêtres du
  même port consommaient le budget de la journée.

Les valeurs par défaut passent à `max_total: 12` et `max_per_day: 4`. Cinq
était trop court pour sept destinations sur trois jours.

### Créneau réduit par activité

Les seuils d'une activité portaient sur le **maximum de la fenêtre**. Une seule
heure hors limite écartait donc l'activité pour toute la fenêtre. C'est ce qui
vidait la journée du 31 août : une fenêtre 08:00→13:00 dont la dernière heure
montait à 35 km/h de rafales ne proposait rien, alors que 08:00→12:00 était
parfait.

Le moteur cherche désormais, pour chaque activité, la **plus longue plage
contiguë** de la fenêtre où ses seuils tiennent, et la lumière du jour si elle
la requiert. Trois issues :

- la plage couvre toute la fenêtre : comportement inchangé ;
- la plage est plus courte mais atteint `min_duration_h` (défaut
  `ranking.min_activity_hours`, 2 h) : l'activité est proposée sur **son**
  créneau ;
- la plage est trop courte : l'activité est écartée, avec sa raison, comme
  avant.

Le créneau est **strictement inclus** dans la fenêtre Family GO validée. Le
moteur ne crée jamais de temps navigable : il découpe seulement celui qui a déjà
été validé. La sécurité reste inchangée.

Deux conséquences importantes :

- le score et les justifications sont calculés **sur le créneau**, pas sur la
  fenêtre. Afficher « vent 8 km/h » en s'appuyant sur des heures qui ne font pas
  partie du créneau proposé serait un mensonge ;
- les créneaux préférentiels et la part de jour sont recalculés sur le créneau,
  donc les bonus de période suivent.

Chaque activité publie son bloc `slot` :

```json
{"partial": true, "start": "...T08:00:00+01:00", "end": "...T12:00:00+01:00",
 "hours": 4, "window_hours": 5}
```

Le board et la Vue Simple affichent ces bornes sur la ligne de l'activité quand
`partial` vaut vrai, sinon l'horaire de la fenêtre suffit.

### Lumière du jour

`family` et `off_hours` sortent des **mêmes seuils météo** : `window_detect`
écrit `category = "family" if evaluation["daylight"] else "off_hours"`. La seule
différence est la lumière.

Une fenêtre hors horaires peut donc être parfaite au sens météo et courir en
pleine nuit. Le moteur proposait ainsi une baignade familiale et du paddle sur
une fenêtre 01:00→07:00, à 100/100.

Une activité déclare `requires_daylight: true` et, optionnellement,
`min_daylight_share` (0,5 par défaut). Le moteur calcule la part de la fenêtre
comprise entre le lever et le coucher, et écarte l'activité en dessous, avec la
raison publiée : « fenêtre de nuit (20 % de jour seulement, jour de 05:49 à
18:47) ».

La contrainte est portée par l'activité, pas par la vue. Baignade, masque et
tuba, paddle et observation nature la déclarent. Les quatre activités de pêche
ne la déclarent pas : une sortie au lever du jour est légitime.

### Vent de terre et vent de mer

`onshore_share` et `offshore_share` sont calculés séparément, à partir des
secteurs onshore du site et de leur opposé à 180°. Ce n'est pas
`1 - onshore_share` : un vent parallèle à la côte n'appartient à aucun des deux,
et la distinction compte pour une petite embarcation.

Les deux vents ne jouent pas dans le même sens selon l'activité :

- pour la baignade, le masque et tuba et la pêche, le **vent de mer** brasse le
  fond et trouble l'eau ; il pénalise via `comfort.max_onshore_share` ;
- pour le paddle et le kayak, le **vent de terre** est le piège classique : mer
  plate et engageante au départ, retour impossible ensuite. Il pénalise via
  `comfort.max_offshore_share`.

Le conseil de fenêtre sur le vent de terre nomme les deux faces, l'eau lissée et
la dérive vers le large. Le taire serait trompeur : c'est exactement la
situation où la mer paraît la plus engageante.

Ces pénalités restent des réserves de confort. Aucune ne retire une activité, et
le moteur de fenêtres ne modélise pas la dérive : il reste seul juge d'un GO.

## Contenu nature des ports

Un port peut déclarer un bloc `nature`, saisonnier, publié avec la
recommandation et affiché sous l'activité.

Règle absolue : **rien n'y est écrit sans référence publique vérifiable**. Le
bloc porte ses `sources`, et le board affiche la première. Un port sans source
n'a pas de bloc nature, et sa carte reste vide plutôt que remplie d'une
observation inventée.

Deux ports sont sourcés à ce stade :

- **El Haouaria**, printemps : le Jbel El Haouaria est décrit par l'Association
  Les Amis des Oiseaux comme le principal point de concentration d'oiseaux de
  Tunisie pendant la migration de printemps.
- **Ghar el Melh**, hiver : lagune et delta de la Mejerda, site Ramsar de
  10 168 ha inscrit le 7 novembre 2007, hivernage et nidification d'oiseaux
  d'eau.

Les cinq autres ports n'ont pas encore de contenu nature sourcé. Pantelleria
n'en aura pas : sa politique est `navigation_only_no_leisure_recommendations`.

## Conseils de confort

`advisories()` produit des remarques bilingues à partir des métriques
secondaires : UV élevé, ressenti excessif, vent de mer, vent de terre favorable,
pluie, eau fraîche, marnage marqué. Les seuils sont lus dans
`knowledge/manifest.yaml` sous la clé `advisories`.

Ces conseils **n’ont aucun effet sur la sécurité**. Ils ne retirent pas une
activité, ne créent pas de fenêtre et ne modifient pas un verdict. Une activité
peut en plus déclarer un bloc `comfort` : il produit des réserves affichées sous
l’activité et une pénalité de score, jamais un refus.

## Soleil et lune

Les données sont lues dans le bloc `daily` du JSON du spot :

- `sunrise` ;
- `sunset` ;
- `moonrise` ;
- `moonset` ;
- `moon_phase`.

Le moteur convertit `moon_phase` en libellé et en illumination approximative. Cette information ne constitue pas une preuve de présence ou d’activité des poissons.

## Sorties publiques

### `recommendations.json`

La version de sortie passe à `2` lorsque le Knowledge Pack est actif :

```json
{
  "generated_at": "2026-07-12T08:00:00+00:00",
  "version": 2,
  "safety_policy": "recommendations_only_inside_validated_family_go_windows",
  "knowledge_pack": {
    "version": 1,
    "status": "initial_tunable",
    "counts": {
      "fish": 6,
      "techniques": 4,
      "ports": 1,
      "activities": 5
    }
  },
  "recommendations": [],
  "no_go": []
}
```

Chaque recommandation peut maintenant contenir :

- `species` : libellés lisibles ;
- `species_ids` : identifiants stables ;
- `species_details` : informations structurées ;
- `techniques` et `technique_ids` ;
- `technique_details` ;
- habitats et futures zones du port.

Les anciens champs lisibles sont conservés pour ne pas casser le board actuel.

### `knowledge.json`

Catalogue de contrôle public contenant :

- version et statut du pack ;
- nombre d’espèces, techniques, ports et activités ;
- liste des identifiants chargés ;
- avertissements éventuels en mode non strict.

Le pipeline de production utilise le mode strict : une incohérence bloque la génération.

## Board

`public/activity-board.js` charge `recommendations.json` et ajoute au dashboard une carte **« Que faire sur l’eau ? »**.

Le composant est informatif. La source de vérité reste le JSON généré par le backend. Une erreur d’affichage ne modifie jamais la décision de sécurité.

Il rend aussi la liste « Pourquoi les autres spots sont exclus », les conseils de
confort de la fenêtre et les réserves propres à chaque activité.

Les identifiants de vocabulaire libre du Knowledge Pack (`micro_jig_5_12_g`)
n’ont pas de libellé dédié : le board les rend lisibles à l’affichage. Le jour où
le pack publiera un libellé par appât et par leurre, il remplacera cette
transformation. Les nombres décimaux suivent la langue affichée : `0,18–0,25 mm`
en français.

## Ajustement progressif

Le Knowledge Pack doit être amélioré à partir de :

- journaux de sorties ;
- observations par spot, saison et profondeur ;
- résultats par technique et appât ;
- retours sur les faux positifs et faux négatifs ;
- validation des appellations locales ;
- réglementation tunisienne et restrictions locales.

Les futures zones GPS ne doivent être ajoutées qu’après validation terrain, cartographique et nautique.

## Limites

- Le moteur ne prédit pas une capture.
- Les espèces, profondeurs, techniques et appâts restent indicatifs.
- Les profils ne remplacent pas les cartes marines, avis locaux ou règles de pêche.
- Le calendrier lunaire est un facteur secondaire.
- Une recommandation ne vaut que pour la fenêtre et les données qui l’ont produite.
