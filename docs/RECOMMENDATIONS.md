# Recommandations d’activités et de pêche

## Objectif

La couche de recommandations répond à la question **« Que faire sur l’eau ? »** après validation d’une fenêtre de navigation par le moteur Family GO.

Elle ne remplace pas le moteur de sécurité et ne crée jamais de fenêtre. Son entrée principale est `public/windows.json`.

## Principe de sécurité

Ordre impératif des décisions :

1. collecte et validation des données météo/marine ;
2. détection d’une fenêtre Family GO ;
3. vérification des seuils propres à chaque activité ;
4. classement des activités restantes ;
5. enrichissement avec saison, pêche, soleil et lune.

Si une destination ne possède aucune fenêtre Family GO, elle apparaît dans `no_go` et aucune activité n’est proposée.

## Fichiers de configuration

### `fishing_profiles.yaml`

Structure générale :

```yaml
version: 2
status: indicative_local_profiles
profiles:
  gammarth-port:
    display_name: "Gammarth"
    confidence: initial_local_profile
    depths_m: [4, 18]
    seasons:
      summer:
        species: [pageot, dorade_royale, oblade]
        techniques: [bottom_drift, micro_jig]
        rigs: [carolina_leger, paternoster_leger]
        baits: [ver, crevette, calamar, leurre_souple]
        depths_m: [6, 18]
        preferred_periods: [sunrise, sunset]
```

Champs :

- `confidence` : maturité du profil, sans lien avec la confiance météo ;
- `species` : espèces saisonnières indicatives ;
- `techniques` : techniques pertinentes ;
- `rigs` : montages conseillés ;
- `baits` : appâts ou leurres ;
- `depths_m` : profondeur indicative ;
- `preferred_periods` : `sunrise`, `sunset` ou autres périodes futures.

Un profil de pêche absent n’empêche pas les activités non liées à la pêche. Il élimine les activités portant `requires_fishing_profile: true`.

### `activity_profiles.yaml`

Structure générale :

```yaml
version: 1
status: initial_tunable
ranking:
  max_per_window: 3
  max_total: 5
  preferred_period_bonus: 7
  lunar_max_bonus: 5
activities:
  bottom_fishing:
    icon: "🎣"
    label_fr: "Pêche au fond"
    label_en: "Bottom fishing"
    requires_fishing_profile: true
    lunar_sensitive: true
    safety:
      max_wind_kmh: 18
      max_gust_kmh: 28
      max_hs_m: 0.45
      min_tp_s: 3.2
      min_visibility_km: 5
```

Les seuils d’activité sont appliqués **après** la validation Family GO. Une activité peut donc être refusée dans une fenêtre pourtant navigable.

## Calcul des métriques

Pour chaque fenêtre, le moteur extrait du JSON du spot :

- vent maximal ;
- rafale maximale ;
- Hs maximale ;
- Tp minimale ;
- visibilité minimale ;
- nombre d’heures échantillonnées.

Ces métriques représentent les conditions les plus défavorables de la fenêtre pour l’activité.

## Classement

Le score part de 100 et diminue à mesure que les conditions se rapprochent des limites de l’activité.

Une activité est éliminée si :

- le vent, les rafales ou Hs dépassent le maximum ;
- Tp descend sous le minimum ;
- la visibilité descend sous le minimum ;
- un profil de pêche requis est absent.

Des bonus limités peuvent ensuite être ajoutés :

- correspondance avec une période préférentielle du profil saisonnier ;
- signal lunaire secondaire lorsque `lunar_sensitive: true`.

Le score final est plafonné à 100.

## Soleil et lune

Les données sont lues dans le bloc `daily` du JSON du spot :

- `sunrise` ;
- `sunset` ;
- `moonrise` ;
- `moonset` ;
- `moon_phase`.

Le moteur convertit `moon_phase` en libellé et en illumination approximative. L’illumination ne constitue pas une preuve de présence ou d’activité des poissons. Elle sert uniquement de signal faible de classement.

## Format de sortie

`public/recommendations.json` :

```json
{
  "generated_at": "2026-07-11T00:00:00+00:00",
  "version": 1,
  "safety_policy": "recommendations_only_inside_validated_family_go_windows",
  "recommendations": [
    {
      "dest_slug": "gammarth-port.json",
      "dest_name": "Gammarth (port)",
      "start": "2026-07-11T08:00:00+01:00",
      "end": "2026-07-11T12:00:00+01:00",
      "season": "summer",
      "metrics": {},
      "astronomy": {},
      "fishing": {},
      "activities": []
    }
  ],
  "no_go": []
}
```

### `recommendations[]`

Chaque entrée correspond à une fenêtre validée et contient :

- destination et horaire ;
- confiance héritée de la fenêtre ;
- métriques utilisées ;
- données astronomiques ;
- profil de pêche saisonnier ;
- activités classées.

### `no_go[]`

Destinations sans fenêtre validée. Le moteur n’y publie aucune activité.

## Board

`public/activity-board.js` charge `recommendations.json` et ajoute au dashboard une carte **« Que faire sur l’eau ? »**.

Le composant est informatif : la source de vérité reste le JSON généré par le backend. Une erreur d’affichage ne doit pas modifier les décisions de sécurité.

## Ajustement progressif

Les profils initiaux doivent être améliorés à partir de :

- journaux de sorties ;
- observations par spot, saison et profondeur ;
- résultats par technique et appât ;
- retours sur les faux positifs et faux négatifs ;
- réglementation tunisienne et restrictions locales.

Les changements doivent rester réversibles, testés et documentés dans `docs/CHANGELOG.md`.

## Limites

- Le moteur ne prédit pas une capture.
- Les espèces et appâts sont indicatifs.
- Les profils ne remplacent pas les cartes marines, avis locaux ou règles de pêche.
- Le calendrier lunaire est un facteur secondaire.
- Une recommandation ne vaut que pour la fenêtre et les données qui l’ont produite.
