# Température d’eau et niveau de la mer

## Pourquoi un appel séparé

`sea_surface_temperature` et `sea_level_height_msl` viennent de l’API marine
Open-Meteo, comme la houle. Ils sont pourtant récupérés par une **requête
distincte**, et c’est délibéré.

La chaîne de repli des modèles de vagues porte la sécurité :
`meteofrance_wave` → `ncep_gfswave025` → `ecmwf_wam025`. Ces modèles n’exposent
pas la SST. Ajouter la SST à la requête de houle ferait échouer le modèle
interrogé, la chaîne passerait au suivant, et un spot pourrait se retrouver
évalué sur un modèle de repli — ou sans houle du tout — à cause d’une variable de
confort.

Deux appels, deux responsabilités : la houle ne dépend d’aucune variable
facultative.

## Contrat

`fable.openmeteo.fetch_ocean()` est strictement facultatif :

- il ne lève jamais ;
- il ne bloque jamais la publication ;
- il respecte le budget temps du site (`site_deadline`) et ne part pas si le
  budget est dépassé ;
- il renvoie `{"hourly": {}, "_error": ...}` en cas d’échec, de réponse
  inattendue, ou de séries entièrement nulles ;
- aucune de ses variables n’entre dans une règle de sécurité.

Le pilotage se fait par `FABLE_INCLUDE_OCEAN` (`1` par défaut). Mettre `0`
désactive l’appel sans autre effet.

## Alignement sur l’axe horaire

`fable.collect.attach_on_axis()` aligne les séries facultatives sur l’axe horaire
déjà construit par la collecte principale. Les heures absentes deviennent `None`.

Une lacune est normale et ne doit jamais bloquer une publication : ces variables
ne participant à aucune règle, un trou se traduit par un conseil en moins, pas
par une fenêtre perdue.

## Sorties

Dans le JSON du spot :

- `ocean` : les séries découpées sur la fenêtre publiée ;
- `hourly.sea_surface_temperature` et `hourly.sea_level_height_msl` : les mêmes
  valeurs alignées sur l’axe horaire commun ;
- `debug.ocean_keys_attached` : les clés effectivement rattachées ;
- `debug.ocean_error` : la raison, quand l’appel n’a rien ramené.

## Usage en aval

- **Marée** : `sea_level_height_msl` fournit le marnage mesuré sur une fenêtre,
  qui remplace la phase de lune dans le bonus de classement. Voir
  [RECOMMENDATIONS.md](RECOMMENDATIONS.md).
- **SST** : alimente un conseil de confort (eau fraîche) et servira aux activités
  de baignade et de snorkeling de la phase contenu.

## Vérification

```bash
python -m pytest tests/test_ocean_variables.py -q
```

Les tests couvrent la forme de l’URL (absence de `models=`), le succès, quatre
modes d’échec, le respect du budget et l’alignement avec trous.
