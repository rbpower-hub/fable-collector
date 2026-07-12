# Architecture — fable-collector v3 groundwork

## Vue d’ensemble

```text
                     GitHub Actions — collect.yml
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
          preflight          collect             reader
      validation config   météo + marine      Family GO
              │                 │                  │
              └─────────────────┴──────────┬───────┘
                                           ▼
                                      knowledge
                             validation du pack métier
                                           │
                                           ▼
                                   recommendations
                              activités + pêche + astro
                                           │
                                           ▼
                                        publish
                               catalogue + statut + checks
                                           │
                                           ▼
                                       public/
                                           │
                                           ▼
                                     GitHub Pages
```

Le workflow `healthcheck.yml` surveille indépendamment le déploiement GitHub Pages et signale un site trop ancien ou incomplet.

## Sources de configuration

| Fichier | Responsabilité |
|---|---|
| `sites.yaml` | Ports météo/navigation, coordonnées, port d’attache, routes, vitesses et exposition au vent |
| `rules.yaml` | Seuils Family GO, règles de transit/mouillage, confiance et sources météo |
| `knowledge/manifest.yaml` | Version, statut, politiques et paramètres de classement du Knowledge Pack |
| `knowledge/fish/*.yaml` | Espèces et attributs structurés |
| `knowledge/techniques/*.yaml` | Techniques, familles et indications de matériel |
| `knowledge/ports/*.yaml` | Connaissance locale par port, saison et futures zones validées |
| `knowledge/activities/*.yaml` | Activités et seuils propres à chaque usage |
| `fishing_profiles.yaml` | Fallback transitoire et rollback des profils historiques |
| `activity_profiles.yaml` | Fallback lorsque le Knowledge Pack est absent |

La navigation reste séparée de la connaissance métier : `sites.yaml` décide où et comment évaluer un trajet ; `knowledge/ports/` décrit les usages et profils locaux associés.

## Modules

| Module | Rôle | Entrées | Sorties |
|---|---|---|---|
| `fable.config` | Chargement, validation et normalisation des règles et des sites | YAML | `SitesConfig`, règles normalisées |
| `fable.openmeteo` | Client HTTP, modèles, retries et fallbacks | réseau | payloads météo et marine |
| `fable.astro` | Lever/coucher du soleil et de la lune, phase lunaire, fallback Astral | payload + coordonnées | bloc `daily` enrichi |
| `fable.collect` | Collecte, alignement temporel, modèles parallèles et écriture atomique | config + réseau | `public/<slug>.json`, `index.json` |
| `fable.windows` | Worst-value-wins, évaluation par phase et détection des fenêtres | spots JSON + règles | `windows.json` |
| `fable.knowledge` | Charge les catégories, vérifie les IDs et les références croisées | `knowledge/` | `KnowledgePack` validé |
| `fable.recommendations` | Filtrage et classement des activités dans les fenêtres validées | fenêtres + spots + pack | `recommendations.json`, `knowledge.json` |
| `fable.preflight` | Validation avant collecte et exports normalisés | YAML | `rules.normalized.json`, `sites.normalized.json` |
| `fable.status` | Catalogue, statut, fraîcheur et résumé des fenêtres | `public/` | fichiers de statut |
| `fable.publish` | Contrôles finaux et préparation de GitHub Pages | `public/` | code retour |
| `fable.healthcheck` | Contrôle externe du site publié | HTTPS | état de santé |

## Flux par spot

1. `fetch_forecast` tente les modèles météo configurés jusqu’à obtenir des séries de vent exploitables.
2. `fable.astro` complète `sunrise`, `sunset`, `moonrise`, `moonset` et `moon_phase`.
3. `fetch_marine` collecte Hs, Tp et la houle avec fallbacks.
4. Les modèles parallèles sont alignés pour mesurer le désaccord inter-modèles.
5. Le collecteur publie un JSON par spot sans inventer les données marine manquantes.
6. Le reader évalue les heures et construit les fenêtres Family GO.
7. `fable.knowledge` charge et valide le pack métier. Une référence inconnue est bloquante.
8. Le moteur de recommandations calcule les métriques de chaque fenêtre acceptée et classe les activités compatibles.
9. Le pipeline publie `recommendations.json` et le catalogue `knowledge.json`.

## Validation du Knowledge Pack

Le chargeur contrôle notamment :

- correspondance entre `id` et nom de fichier ;
- unicité des identifiants ;
- références d’espèces depuis les ports ;
- références de techniques depuis les ports et activités ;
- structure YAML des saisons.

La production utilise le mode strict. Une incohérence empêche la génération des recommandations et bloque le déploiement, plutôt que de publier silencieusement une connaissance partielle.

## Couverture régionale et fallback

```text
Port présent dans knowledge/ports/
        └──► modèle structuré Knowledge Pack

Port absent de knowledge/ports/
        └──► fallback fishing_profiles.yaml s’il existe
               └──► sinon aucune recommandation de pêche ciblée
```

Les ports tunisiens Gammarth, Sidi Bou Saïd, Ghar El Melh, Ras Fartass, El Haouaria et Kélibia sont migrés dans le pack structuré. Le fallback historique reste conservé pour compatibilité et rollback, mais n’est plus la source principale de ces six profils.

Pantelleria reste volontairement absente du Knowledge Pack métier. Sa route composite offshore beta nécessite une validation séparée avant d’ajouter un profil d’espèces, des techniques ou des zones.

## Détection Family GO

- Fenêtres de 4 à 6 heures selon la structure `Transit – Mouillage – Transit`.
- Validation au départ, sur la destination et au retour.
- Veto absolu pour les orages et refus conservateur en cas de données critiques manquantes.
- Worst-value-wins : vent/rafales maximaux, Hs maximale et Tp minimale entre modèles.
- Règles spécifiques au mouillage abrité sans assouplissement du transit.
- Confiance plafonnée lorsque le nombre de modèles ou de sources de houle est insuffisant.

## Couche de recommandations

```text
NO-GO / absence de fenêtre
        └──► aucune recommandation

Family GO validé
        └──► Knowledge Pack valide
                 └──► filtres propres à l’activité
                          └──► classement des activités restantes
```

Le score prend en compte la marge sous les seuils, la disponibilité d’un profil saisonnier, les techniques compatibles, la période solaire et un signal lunaire secondaire plafonné.

## Rendu du board

Le workflow produit `recommendations.json`, puis charge `public/activity-board.js` dans l’artefact GitHub Pages. `knowledge.json` permet de contrôler la version, le statut et les identifiants métier effectivement chargés.

## Décisions figées

- Les recommandations ne doivent jamais contourner `windows.json`.
- La lune ne crée aucune fenêtre et ne neutralise aucun blocage.
- Les zones GPS restent vides jusqu’à validation terrain, cartographique et nautique.
- Les connaissances métier sont indicatives et doivent conserver un statut de validation explicite.
- `sites.yaml` reste la source de vérité de la navigation ; le Knowledge Pack ne doit pas dupliquer les routes météo.
