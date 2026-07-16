# Validation terrain FABLE

## Objectif

Comparer les décisions FABLE aux conditions réellement observées sur les sorties familiales, route par route, sans modifier automatiquement les règles de sécurité.

## Journal local

La page `public/field-log.html` :

- capture la prévision courante depuis `windows.json` et `status.json` ;
- associe la destination, la fenêtre, le niveau Family GO, la confiance et les diagnostics ;
- enregistre le type d’observation, l’équipage, le confort, l’état de mer, les mesures disponibles et les incidents ;
- conserve les données dans le navigateur sous `fable_field_logs_v1` ;
- exporte les observations en JSON et CSV ;
- réimporte un export JSON sans dupliquer les identifiants existants.

Aucune donnée n’est envoyée à un serveur par cette première version. Un export régulier est donc nécessaire pour éviter une perte lors d’un nettoyage du navigateur ou d’un changement d’appareil.

## Classes d’analyse

- **GO confirmé** : sortie effectuée, confort 4 ou 5, sans retour anticipé ni incident ;
- **GO à revoir** : sortie effectuée après un GO ou GO PRUDENT, avec confort 1 ou 2, retour anticipé ou incident ;
- **Observation conservatrice** : NO-GO comparé uniquement à une observation depuis le port ou la côte, avec mer calme ou peu agitée ;
- **NO-GO respecté** : sortie annulée conformément à la décision ;
- **Non concluant** : données insuffisantes ou situation ne correspondant pas aux classes précédentes.

Une sortie NO-GO ne doit jamais être effectuée dans le but de tester FABLE.

## Règles de calibration

1. Les veto orage, visibilité, rafales extrêmes, données essentielles manquantes et mer dangereuse ne sont jamais relâchés par le journal.
2. Aucun seuil n’est modifié automatiquement.
3. Une observation isolée sert à détecter un cas à examiner, pas à modifier une règle.
4. Première revue qualitative à partir de 10 observations par route.
5. Révision éventuelle des seuils de confort seulement après au moins 20 observations comparables sur la route et la saison concernées.
6. Toute proposition de modification doit être documentée, testée sur l’historique et soumise par pull request distincte.

## Indicateurs prioritaires

- taux de GO confirmés ;
- nombre de GO à revoir ;
- fréquence des retours anticipés ;
- confort moyen avec enfants ;
- écart entre vent, rafales ou vague prévus et observés ;
- résultats séparés par destination, saison et type de route ;
- distinction entre Family GO standard, GO PRUDENT et navigation offshore directionnelle.
