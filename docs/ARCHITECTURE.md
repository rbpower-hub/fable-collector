# Architecture — fable-collector v2.9

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
| `sites.yaml` | Ports, coordonnées, port d’attache, routes, vitesses et exposition au vent |
| `rules.yaml` | Seuils Family GO, règles de transit/mouillage, confiance et sources météo |
| `fishing_profiles.yaml` | Espèces, techniques, montages, appâts, profondeurs et périodes par spot/saison |
| `activity_profiles.yaml` | Seuils propres à chaque activité et paramètres de classement |

Les deux fichiers de profils sont volontairement séparés de `sites.yaml` afin de ne pas mélanger la géographie/navigation avec les connaissances métier de pêche.

## Modules

| Module | Rôle | Entrées | Sorties |
|---|---|---|---|
| `fable.config` | Chargement, validation et normalisation des règles et des sites | YAML | `SitesConfig`, règles normalisées |
| `fable.openmeteo` | Client HTTP, modèles, retries et fallbacks | réseau | payloads météo et marine |
| `fable.astro` | Lever/coucher du soleil et de la lune, phase lunaire, fallback Astral | payload + coordonnées | bloc `daily` enrichi |
| `fable.collect` | Collecte, alignement temporel, modèles parallèles et écriture atomique | config + réseau | `public/<slug>.json`, `index.json` |
| `fable.windows` | Worst-value-wins, évaluation par phase et détection des fenêtres | spots JSON + règles | `windows.json` |
| `fable.recommendations` | Filtrage et classement des activités dans les fenêtres validées | fenêtres + spots + profils | `recommendations.json` |
| `fable.preflight` | Validation avant collecte et exports normalisés | YAML | `rules.normalized.json`, `sites.normalized.json` |
| `fable.status` | Catalogue, statut, fraîcheur et résumé des fenêtres | `public/` | fichiers de statut |
| `fable.publish` | Contrôles finaux et préparation de GitHub Pages | `public/` | code retour |
| `fable.healthcheck` | Contrôle externe du site publié | HTTPS | état de santé |

## Flux par spot

1. `fetch_forecast` tente les modèles météo configurés jusqu’à obtenir des séries de vent exploitables.
2. `fable.astro` complète `sunrise`, `sunset`, `moonrise`, `moonset` et `moon_phase`. L’endpoint astronomy peut être désactivé ; Astral reste le fallback local.
3. `fetch_marine` collecte Hs, Tp et la houle avec fallback MFWAM, GFS-Wave, ECMWF WAM puis modèle par défaut.
4. Les modèles parallèles sont alignés sur un axe horaire commun pour mesurer le désaccord inter-modèles.
5. Le collecteur publie un JSON par spot. Une absence de données marine reste une absence : aucune interpolation de sécurité n’est fabriquée.
6. Le reader évalue les heures et construit les fenêtres Family GO.
7. Le moteur de recommandations lit les fenêtres acceptées, calcule les métriques de la fenêtre et classe les activités compatibles.

## Détection Family GO

- Fenêtres de 4 à 6 heures selon la structure `Transit – Mouillage – Transit`.
- Validation au départ, sur la destination et au retour.
- Veto absolu pour les orages et refus conservateur en cas de données critiques manquantes.
- Worst-value-wins : vent/rafales maximaux, Hs maximale et Tp minimale entre modèles.
- Règles spécifiques au mouillage abrité sans assouplissement du transit.
- Confiance plafonnée lorsque le nombre de modèles ou de sources de houle est insuffisant.

## Couche de recommandations

La couche de recommandations est **strictement descendante** :

```text
NO-GO / absence de fenêtre
        └──► aucune recommandation

Family GO validé
        └──► filtres propres à l’activité
                 └──► classement des activités restantes
```

Le score prend en compte :

- marge sous les seuils de vent, rafales, Hs, Tp et visibilité ;
- présence d’un profil de pêche lorsque l’activité l’exige ;
- adéquation de la saison et de la période solaire ;
- signal lunaire secondaire, plafonné par configuration.

La lune ne crée aucune fenêtre et ne peut neutraliser aucun blocage de sécurité.

## Rendu du board

Le workflow produit `recommendations.json`, puis charge `public/activity-board.js` dans l’artefact GitHub Pages. Le composant ajoute la section **« Que faire sur l’eau ? »** sans modifier le moteur principal du dashboard.

## Décisions figées

- La clé historique `ecmwf` du payload contient le modèle météo primaire réellement retenu ; son nom exact reste disponible dans les métadonnées.
- `index.json` référence les spots ; `catalog.json` inventorie les fichiers publiés.
- Les profils de pêche sont indicatifs et doivent être affinés sans compromettre la priorité des règles de navigation.
- Les recommandations ne doivent jamais être calculées directement à partir d’une météo brute en contournant `windows.json`.
