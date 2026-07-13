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
- abris renseignés et statut de validation.

Les distances sont des calculs géométriques issus de `sites.yaml`. Elles ne remplacent pas une route nautique validée.

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
