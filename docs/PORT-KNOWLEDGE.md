# FABLE 3.1 — Port Knowledge et offshore aller simple

## Objectif

FABLE sépare désormais deux types de trajet :

- **sortie côtière familiale** : départ, temps sur zone et retour dans la même fenêtre ;
- **traversée offshore multi-jours** : aller simple et retour simple évalués indépendamment.

Cette distinction évite d’imposer à Pantelleria un retour à Gammarth le jour même.

## Pantelleria

La traversée météo principale est évaluée entre le port relais de **Kélibia** et **Pantelleria** :

```text
outbound : Kélibia → Pantelleria
return   : Pantelleria → Kélibia
```

Les deux directions sont publiées séparément dans `windows.json` avec :

```json
{
  "trip_mode": "one_way_multi_day",
  "direction": "outbound",
  "same_day_round_trip_required": false,
  "return_window_required": false
}
```

Le pré-positionnement `Gammarth ↔ Kélibia` reste une étape opérationnelle séparée. Une fenêtre offshore ne signifie pas automatiquement que le transfert depuis ou vers Gammarth est validé au même moment.

## Seuils offshore

La première version utilise uniquement les règles Family strictes :

- aucun mode Family GO prudent offshore ;
- contrôle du vent, des rafales, de la visibilité, de Hs et de Tp aux deux extrémités ;
- pire valeur entre modèles ;
- passage entièrement compris dans la plage de lumière pour être classé `family` ;
- vérifications opérationnelles supplémentaires obligatoires avant départ.

Ces vérifications supplémentaires comprennent notamment carburant, réserve, communications, formalités Tunisie–Italie, équipement de sécurité, autonomie, personnes à bord et bulletins maritimes officiels.

## Endpoint Port Knowledge

`port-knowledge.json` publie pour chaque destination :

- origine de route ;
- distance calculée depuis les coordonnées et points de route configurés ;
- hypothèse de vitesse ;
- temps de transit rapide et conservateur ;
- type de trajet ;
- politique de retour ;
- abris renseignés et statut de validation ;
- indicateur `display_eligible` pour l’interface.

Les distances sont des calculs géométriques issus de `sites.yaml`. Elles ne remplacent pas une route nautique validée.

## Affichage conditionnel du dashboard

La carte **« Routes & abris validés »** suit une politique stricte :

```text
display_eligible = route_validated OR validated_shelter_count > 0
```

Conséquences :

- une route simplement calculée depuis la configuration n’est pas affichée ;
- un abri `pending` ou `field_check_required` n’est pas affiché ;
- le script `port-knowledge.js` n’est même pas chargé par le navigateur lorsqu’aucune donnée n’est éligible ;
- les données techniques non validées restent disponibles dans le JSON pour le développement et les contrôles internes.

Cette règle évite de surcharger l’utilisateur avec des distances ou des abris encore provisoires.

## Correction du corridor El Haouaria–Kélibia

Le tracé initial utilisait un seul segment entre le waypoint El Haouaria et Kélibia. Cette corde traversait visuellement le cap Bon et sous-estimait le trajet réellement navigable.

Le corridor est maintenant décrit par six points successifs :

1. El Haouaria — au large ;
2. Cap Bon nord — au large ;
3. Cap Bon nord-est — au large ;
4. Cap Bon est — au large ;
5. Dar Allouche — au large ;
6. approche Kélibia par le large.

Avec les coordonnées configurées :

- ancien tronçon El Haouaria→Kélibia : environ **13,6 NM** ;
- nouveau tronçon maritime : environ **19,1 NM** ;
- ancien trajet Gammarth→Kélibia : environ **49,3 NM** ;
- nouveau trajet configuré : environ **54,9 NM** ;
- transit indicatif à 18–24 nd : environ **2,29 à 3,05 h**.

Le corridor reste un tracé cartographique indicatif. Il doit être confirmé sur une carte nautique officielle, avec vérification des hauts-fonds, zones réglementées, installations de pêche et conditions du jour.

## Intelligence des abris

Un abri peut avoir les statuts suivants :

- `pending` ;
- `field_check_required` ;
- `validated` ;
- `rejected`.

Un abri `validated` doit obligatoirement comprendre :

- des coordonnées ;
- les secteurs de vent contre lesquels il protège ;
- un fetch maximal positif ;
- une validation locale explicite.

Tant qu’aucune fiche ne satisfait ces conditions :

```text
bonus_enabled = false
```

Les seuils standards continuent donc de s’appliquer.

## Données initiales

Les profils de navigation initiaux concernent :

- Gammarth ;
- Sidi Bou Saïd ;
- Ghar El Melh ;
- Ras Fartass ;
- Pantelleria.

Les fiches d’abri restent vides. C’est volontaire : aucune coordonnée ou protection locale n’est publiée sans validation terrain.

## Prochaine validation terrain

Pour chaque zone candidate, il faudra relever :

1. coordonnées GPS ;
2. profondeur et nature du fond ;
3. secteurs réellement protégés ;
4. fetch approximatif ;
5. accès et obstacles ;
6. confort observé selon vent et houle ;
7. aptitude à une halte familiale ;
8. date, auteur et niveau de confiance de la validation.
