# FABLE Fish Intelligence v1

## Objectif

Fish Intelligence enrichit les profils d’espèces et de techniques sans modifier la décision de sécurité. Les données ne sont utilisées qu’après validation d’une fenêtre **Family GO**.

## Principe de décision

```text
Météo et mer
   └──► fenêtre Family GO validée
            └──► activité compatible
                     └──► profil saisonnier du port
                              └──► Fish Intelligence indicative
```

Aucune plage d’hameçon, aucun appât, aucun leurre et aucun signal lunaire ne peut créer une fenêtre GO ou neutraliser un NO-GO.

## Schéma des espèces

Chaque fichier `knowledge/fish/<id>.yaml` peut contenir :

```yaml
id: pageot
status: indicative_local_validation_required
taxonomy:
  status: common_name_to_confirm_locally
habitats: [sable, roche, herbier_mixte]
depths_m: [6, 30]
preferred_periods: [sunrise, sunset]
targeting:
  technique_ids: [bottom-fishing, light-jigging]
  natural_baits: [ver, crevette, calamar]
  artificial_lures: [micro_jig_10_25_g]
  presentations: [derive_lente, fond_leger]
  terminal_tackle:
    hook_sizes:
      system: common_numbering
      range: ["#6", "#2"]
    leader_mm: [0.22, 0.30]
    sinker_g: [20, 60]
    guidance_status: indicative_starting_range
validation:
  local_validation_required: true
  taxonomic_validation_required: true
  regulatory_check_required: true
```

## Schéma des techniques

Les techniques portent les montages et plages générales de matériel :

```yaml
id: bottom-fishing
gear:
  rigs: [paternoster, carolina_leger, montage_coulissant, tate_fond]
  sinker_g: [15, 80]
  leader_mm: [0.20, 0.40]
  hook_styles: [circle, chinu, aberdeen]
  hook_sizes:
    system: common_numbering
    range: ["#10", "1/0"]
presentation:
  - poser_ou_deriver_lentement_pres_du_fond
  - adapter_le_plomb_a_la_derive
```

## Statut des données

Les réglages sont des **plages de départ**, pas des prescriptions. Ils doivent être adaptés à :

- la taille réelle des poissons ;
- la profondeur et la dérive ;
- le courant et la nature du fond ;
- la réglementation applicable ;
- les observations locales et les retours de sorties.

Les noms locaux ambigus (`bonitot`, `merlan`, `moustelle`, `sar`, etc.) restent explicitement marqués comme nécessitant une validation taxonomique. Aucune identification scientifique n’est forcée.

## Validation bloquante

`fable.knowledge` vérifie notamment :

- les références des techniques depuis les espèces ;
- la présence d’un bloc `targeting` pour chaque espèce du schéma v2 ;
- la présence du matériel terminal ;
- la structure des plages numériques ;
- la structure des tailles d’hameçons ;
- le maintien de `local_validation_required: true`.

Une incohérence bloque la génération au lieu de publier une recommandation partielle.

## Sorties publiques

Lorsque le pack v2 est actif :

- `recommendations.json` passe en version `3` ;
- `species_details[].targeting` publie les appâts, leurres et réglages indicatifs ;
- `technique_details[].gear` publie les montages et plages générales ;
- `knowledge.json` publie le schéma, les politiques et un résumé de validation.

## Affichage du board

La carte « Que faire sur l’eau ? » affiche pour l’espèce prioritaire :

- appâts et leurres ;
- montage principal ;
- plage indicative d’hameçons ;
- diamètre indicatif du bas de ligne ;
- plage indicative de plomb lorsque disponible.

Le badge **indicatif** rappelle que ces données doivent être validées et ajustées avant utilisation.
