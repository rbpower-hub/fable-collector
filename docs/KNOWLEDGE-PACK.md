# FABLE Knowledge Pack

## Objectif

Le dossier `knowledge/` sépare la connaissance métier du moteur Python. Il permet d’enrichir progressivement les espèces, techniques, ports et activités sans modifier la logique de sécurité Family GO.

Le Knowledge Pack n’autorise jamais une sortie. Il est chargé uniquement par la couche de recommandations, après génération de `windows.json`.

## Structure

```text
knowledge/
  manifest.yaml
  fish/
    pageot.yaml
    sar.yaml
  techniques/
    bottom-fishing.yaml
    light-jigging.yaml
  ports/
    gammarth-port.yaml
  activities/
    family-swim.yaml
    bottom-fishing.yaml
```

Chaque fichier possède un identifiant stable `id`. Cet identifiant doit être identique au nom du fichier sans l’extension `.yaml`.

## Manifest

`knowledge/manifest.yaml` définit la version du pack et les paramètres généraux de classement :

```yaml
version: 1
status: initial_tunable
ranking:
  max_per_window: 3
  max_total: 5
  preferred_period_bonus: 7
  lunar_max_bonus: 5
policy:
  safety_gate: family_go_required
  lunar_role: secondary_ranking_only
```

## Espèces

Exemple `knowledge/fish/pageot.yaml` :

```yaml
id: pageot
label_fr: Pageot
label_en: Common pandora
status: indicative_local_validation_required
habitats: [sable, roche, herbier_mixte]
depths_m: [6, 30]
preferred_periods: [sunrise, sunset]
```

Les informations sont indicatives. Elles ne garantissent ni présence ni capture. Les appellations locales ambiguës doivent porter un statut explicite de validation taxonomique.

## Techniques

Exemple `knowledge/techniques/light-jigging.yaml` :

```yaml
id: light-jigging
label_fr: Micro-jig / jig léger
label_en: Micro-jig / light jigging
family: jigging
suitable_habitats: [roche, tombant, cassure]
gear:
  lure_weight_g: [7, 50]
```

Les valeurs de matériel sont des plages de départ. Le courant, la dérive, la profondeur et les conditions réelles restent prioritaires.

## Ports et zones

Un fichier de port associe les saisons à des identifiants d’espèces et de techniques :

```yaml
id: gammarth-port
confidence: medium
depths_m: [4, 20]
habitats: [sable, roche, herbier_mixte]
zones: []
fishing:
  seasons:
    summer:
      species: [pageot, dorade-royale, oblade]
      techniques: [bottom-fishing, light-jigging]
      baits: [ver, crevette]
      depths_m: [6, 18]
      preferred_periods: [sunrise, sunset]
```

Le champ `zones` est réservé aux futures zones validées. Aucune coordonnée GPS ne doit être ajoutée sans contrôle terrain, contrôle cartographique et vérification de la sécurité de navigation.

## Activités

Une activité décrit ses seuils propres, appliqués après Family GO :

```yaml
id: bottom-fishing
requires_fishing_profile: true
lunar_sensitive: true
techniques: [bottom-fishing]
safety:
  max_wind_kmh: 18
  max_gust_kmh: 28
  max_hs_m: 0.45
  min_tp_s: 3.5
  min_visibility_km: 6
```

Une activité peut donc être refusée même si la fenêtre générale est navigable.

## Validation

`fable.knowledge.load_knowledge_pack()` bloque notamment :

- un identifiant différent du nom du fichier ;
- un identifiant dupliqué ;
- une espèce inconnue référencée par un port ;
- une technique inconnue référencée par un port ou une activité ;
- une structure YAML invalide.

Lorsque le pack est présent, les erreurs sont bloquantes pour la génération des recommandations et donc pour le déploiement.

## Compatibilité progressive

La migration est volontairement progressive :

- les ports présents dans `knowledge/ports/` utilisent le nouveau modèle structuré ;
- les autres ports continuent temporairement à utiliser `fishing_profiles.yaml` ;
- `activity_profiles.yaml` reste disponible comme fallback lorsque le Knowledge Pack est absent.

Après migration complète et validation en production, les anciens fichiers pourront être dépréciés dans une version ultérieure.

## Sorties publiques

Le pipeline publie :

- `recommendations.json`, version 2 lorsque le Knowledge Pack est actif ;
- `knowledge.json`, catalogue public contenant la version, le statut, les comptes et les identifiants chargés.

Le catalogue public n’est pas une preuve de validité scientifique. Il sert à contrôler ce que le moteur a effectivement chargé.

## Règles de contribution

1. Utiliser des identifiants stables en minuscules avec tirets.
2. Marquer clairement toute donnée indicative ou à valider.
3. Ne pas ajouter de coordonnées ou de recommandations réglementaires non vérifiées.
4. Ajouter ou adapter les tests lors de toute évolution du schéma.
5. Conserver la règle : météo et sécurité avant activité, activité avant signal lunaire.
