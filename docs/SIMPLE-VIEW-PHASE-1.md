# Vue Simple — mémoire produit et Phase 1

Ce document conserve les décisions de conception de la nouvelle expérience afin
que les phases suivantes ne perdent pas le raisonnement validé avec les
utilisateurs. La Vue Simple est une couche isolée : elle ne remplace ni la Vue
Famille, ni la Vue Expert, et elle ne modifie aucune décision de sécurité du
backend.

## Principes validés

1. Répondre en premier à : puis-je sortir, quand, où et avec quel niveau de
   prudence ?
2. Présenter l'information dans l'ordre `Décision → fenêtre → conditions →
   alternatives → détails`.
3. Ne pas afficher les raisons du NO-GO par défaut. Le bouton « Pourquoi ? »
   ouvre une explication progressive, sans masquer l'accès aux diagnostics.
4. Toujours combiner icône, texte et couleur. Une couleur ou un emoji seuls ne
   portent jamais une information de sécurité.
5. Préférer une frise temporelle aux camemberts : les fenêtres sont des périodes,
   pas les parts d'un total.
6. Éviter une dépendance graphique lourde. HTML, CSS et SVG natif suffisent aux
   frises et mini-tendances prévues.
7. Conserver le mode actuel par défaut pendant le prototype et mémoriser le choix
   explicite de l'utilisateur.

## Phase 1 — prototype isolé

La première livraison comprend :

- un bouton `Vue Simple` indépendant des bascules Famille/Expert ;
- une grande carte de décision `SORTIE POSSIBLE`, `SORTIE PRUDENTE` ou
  `SORTIE DÉCONSEILLÉE` ;
- la meilleure destination et sa fenêtre horaire ;
- trois indicateurs compacts : confiance, nombre d'options et fraîcheur ;
- un aperçu vertical et tactile des trois prochains jours ;
- les raisons NO-GO repliées par défaut ;
- une navigation basse mobile vers décision, trois jours, carte et vues
  existantes ;
- la synchronisation sur l'événement `fable:dashboard-updated` déjà utilisé par
  la Vue Famille.

La Phase 1 consomme seulement `windows.json` et `status.json`. Elle ne modifie ni
leur schéma ni le moteur Python.

## Phases conservées pour la suite

### Phase 2 — visualisation

- frise horaire complète GO / Prudent / NO-GO ;
- mini-tendances du vent et de la houle ;
- vent, hauteur de houle et heure limite de retour comme indicateurs d'action ;
- états explicites pour chargement, données absentes et données périmées.

### Phase 3 — socle mobile et accessibilité intégré

- largeurs 320, 375, 390 et 430 px, puis tablette et bureau ;
- thèmes clair/sombre/nautique ;
- français, anglais et arabe/RTL ;
- navigation clavier, lecteur d'écran, grandes polices et réduction des
  animations ;
- textes longs, réseau lent, données manquantes et production périmée.

Le socle livré adapte explicitement la mise en page à 320 px, aux téléphones,
aux tablettes et au bureau. Il ajoute l'arabe tunisien avec direction RTL, les
indications de sélection accessibles, des focus clavier visibles, les contrastes
forcés et la réduction des animations. La prévision détaillée suit désormais la
destination sélectionnée. La matrice de validation manuelle sur appareils et
lecteurs d'écran reste à exécuter avant l'adoption générale.

### Phase 4 — adoption progressive amorcée

- proposer « Essayer la Vue Simple » sans la rendre immédiatement obligatoire ;
- recueillir les retours terrain ;
- envisager le mode Simple par défaut sur mobile seulement après validation ;
- garder durablement les accès Vue Famille et Vue Expert.

L'entrée porte désormais explicitement le libellé « Essayer la Vue Simple »
dans les trois langues et rejoint les réglages mobiles existants. Elle reste
volontaire, réversible et locale au navigateur. Aucun basculement automatique
du mode par défaut et aucune collecte de retour ne sont activés sans validation
terrain préalable.

## Critères de non-régression

- une décision Python ne peut jamais être transformée par l'interface ;
- un NO-GO reste un NO-GO, même lorsque ses raisons sont repliées ;
- la Vue Famille et la Vue Expert continuent de fonctionner sans la Vue Simple ;
- le choix du mode est local au navigateur ;
- toute information cachée par défaut reste accessible en une action explicite.

## Mobile UI V2 — verdicts de navigation unifiés

La V2 ne déduit plus sa décision à partir de sa propre copie des fenêtres. Le
module pur `public/js/navigation-verdicts.js` consomme la normalisation commune
de `navigation-windows.js` et publie, pour la journée sélectionnée, un état
unique parmi :

- `GO_FAMILY` et `GO_PRUDENT` pour les sorties familiales validées ;
- `OFF_HOURS` pour un créneau météo favorable hors horaires familiaux ;
- `TRAVEL_ONLY` pour une navigation longue distance, jamais assimilée à une
  sortie familiale locale ;
- `NO_GO`, `NO_DATA` ou `STALE` selon les données disponibles.

La journée sélectionnée est stricte : l'absence de fenêtre ce jour ne peut plus
être masquée par une fenêtre appartenant à un autre jour. La même sélection est
transmise aux vues Famille et Carte. Le mobile suit désormais la hiérarchie
`Décision → frise horaire → 3 jours → fenêtres de navigation → conditions`, avec
des styles distincts pour Family GO, Prudent, hors horaires et long trajet.
