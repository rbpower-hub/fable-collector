# Family GO prudent et diagnostics backend

## Objet

FABLE 3.0 ajoute un niveau intermédiaire **Family GO prudent** afin de proposer davantage de fenêtres réalistes sans modifier les vétos absolus de sécurité.

Le moteur conserve trois résultats distincts :

1. **Family GO** : conditions conformes aux seuils familiaux standards ;
2. **Family GO prudent** : conditions légèrement moins confortables, mais compatibles avec une sortie courte et surveillée sous des contraintes renforcées ;
3. **NO-GO** : au moins un critère obligatoire ou un veto dur est dépassé.

Le niveau prudent n’est jamais un mode expert et ne constitue pas une autorisation automatique de sortie. Le chef de bord reste responsable de la décision finale et doit vérifier les observations locales, les bulletins officiels, l’état réel de la mer, l’équipage et le bateau.

## Vétos durs inchangés

Le mode prudent ne peut pas neutraliser :

- un code météo d’orage `95`, `96` ou `99` ;
- une visibilité inférieure à `5 km` ;
- des rafales supérieures ou égales à `30 km/h` ;
- un vent soutenu supérieur ou égal à `25 km/h` ;
- un écart rafales–vent supérieur ou égal à `17 km/h` ;
- une hauteur significative `Hs > 0,8 m` ;
- une mer courte et raide classée comme veto dur ;
- des données de vent ou de vagues indispensables manquantes.

Le calcul conserve la règle **worst-value-wins** : vent, rafales et Hs les plus élevés ; Tp la plus courte parmi les modèles disponibles.

## Critères du Family GO prudent

Les paramètres initiaux sont configurés dans `rules.yaml` :

```yaml
prudent:
  enabled: true
  wind_max_kmh: 22
  gust_max_kmh: 28
  hs_max_m: 0.4
  tp_min_s: 3.5
  min_confidence: Medium
```

Une fenêtre prudente impose simultanément :

- vent maximal `≤ 22 km/h` ;
- rafales `< 28 km/h` ;
- `Hs ≤ 0,40 m` ;
- `Tp ≥ 3,5 s` ;
- vent non onshore sur le site concerné ;
- confiance au moins `Medium` ;
- totalité de la fenêtre dans la plage de lumière sécurisée ;
- départ, phases à destination et retour à Gammarth validés.

Le board affiche ces fenêtres en orange avec le badge **FAMILY GO PRUDENT** et un avertissement de confort réduit.

## Durée adaptative

La durée minimale n’est plus obligatoirement fixée à quatre heures pour tous les trajets.

Le calcul est :

```text
durée requise =
  2 × temps de transit au scénario lent
  + temps minimal sur zone
```

avec :

```yaml
adaptive_window:
  enabled: true
  absolute_min_hours: 3
  min_zone_hours: 1.5
```

La durée est arrondie à l’heure supérieure. Pour une destination proche, une fenêtre de trois heures peut donc être acceptée. Pour une destination éloignée, la durée requise augmente. Si elle dépasse la fenêtre maximale de six heures, FABLE publie un blocage explicite au lieu de créer une fenêtre irréaliste.

## Plage liée à la lumière

Lorsque `sunrise` et `sunset` sont disponibles dans le JSON du spot, FABLE utilise :

```yaml
daylight:
  use_astronomy: true
  start_after_sunrise_min: 30
  end_before_sunset_min: 60
```

La plage Family commence donc trente minutes après le lever du soleil et se termine une heure avant le coucher. En l’absence de données astronomiques, le moteur revient à `family_hours_local`.

Une fenêtre standard techniquement valide mais extérieure à cette plage peut rester publiée comme `off_hours`. Une fenêtre prudente est refusée hors de la plage de lumière sécurisée.

## Tolérance de mouillage abrité

Les seuils plus tolérants du mouillage ne sont appliqués que si :

- `shelter_bonus_radius_km` est strictement supérieur à zéro pour le site ;
- le vent n’est pas onshore ;
- la phase évaluée est réellement une phase `anchor`.

Tant qu’aucun abri n’est explicitement validé dans `sites.yaml`, le moteur applique les seuils standards. Le simple nom d’un port ou d’une baie ne suffit pas à activer la tolérance.

La prochaine amélioration géographique devra ajouter une validation plus précise du fetch et du secteur sous le vent avant de renseigner ces rayons.

## Diagnostics dans `windows.json`

Chaque destination publie désormais un objet `diagnostics`.

Exemple simplifié :

```json
{
  "dest_slug": "ghar-el-melh.json",
  "required_hours": 4,
  "windows": [],
  "diagnostics": {
    "status": "blocked",
    "summary_fr": "Retour bloqué à Gammarth : période de vague trop courte.",
    "first_blocker": {
      "stage": "return",
      "location_slug": "gammarth-port.json",
      "location_name": "Gammarth (port)",
      "phase": "transit",
      "time": "2026-07-14T15:00:00+01:00",
      "reasons": ["Tp<4.5@Hs0.4-0.5"],
      "reason_fr": "période de vague trop courte (4,1 s)",
      "metrics": {
        "max_speed": 16.0,
        "max_gust": 23.0,
        "hs": 0.44,
        "tp": 4.1
      }
    },
    "near_miss": {
      "validated_hours": 3,
      "required_hours": 4,
      "tier_attempted": "family"
    }
  }
}
```

Les étapes possibles comprennent notamment :

- `departure` ;
- `destination` ;
- `return` ;
- `daylight` ;
- `confidence` ;
- `duration` ;
- `data` ;
- étapes composites `transfer`, `offshore` ou `alignment`.

## Page « Avertissements »

Le composant `public/reasons-debug.js` ne recalcule plus une version simplifiée des règles dans le navigateur. Il lit directement les diagnostics publiés par le moteur Python.

Cela garantit que la raison affichée utilise :

- les mêmes modèles météo et marine ;
- les mêmes valeurs pessimistes ;
- les mêmes phases transit–mouillage–retour ;
- le contrôle du départ et du retour à Gammarth ;
- la période des vagues ;
- la durée adaptative et la lumière.

Pour Ghar El Melh, l’interface doit ainsi afficher le vrai lieu et la vraie phase du premier blocage, même lorsque la destination elle-même présente des conditions acceptables mais que le retour à Gammarth ne l’est pas.

## Champs d’une fenêtre prudente

```json
{
  "category": "family",
  "family_tier": "prudent",
  "cautions": ["vent>=20"],
  "caution_fr": "Confort réduit : fenêtre acceptée uniquement avec les limites prudentes..."
}
```

`category` reste `family` afin que la fenêtre apparaisse dans la vue simplifiée. `family_tier` permet au board, aux recommandations et aux futurs consommateurs de distinguer clairement le niveau prudent.

## Contrôles avant déploiement

La CI vérifie notamment :

- qu’une fenêtre prudente est explicitement étiquetée ;
- qu’un veto dur de rafales reste bloquant ;
- qu’un vent onshore interdit le mode prudent ;
- que le retour à Gammarth apparaît dans le diagnostic ;
- qu’un trajet court peut produire une durée minimale de trois heures ;
- que la plage solaire est respectée ;
- qu’une tolérance de mouillage ne s’active pas sans abri configuré.
