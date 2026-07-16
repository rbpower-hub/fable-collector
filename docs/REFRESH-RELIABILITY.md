# Fiabilité de la collecte et des données publiées

## Diagnostic

Le bandeau `Données périmées` et le Healthcheck rouge ne proviennent pas du moteur Family GO. Ils signifient que le `status.json` publié sur GitHub Pages a dépassé 95 minutes.

Le workflow interroge la production à 7, 27 et 47 minutes de chaque heure. Lorsqu’une collecte est nécessaire, le build et le déploiement utilisaient chacun le groupe de concurrence `pages` avec `cancel-in-progress: true`.

Si une collecte ou la propagation GitHub Pages dépassait l’intervalle avant le déclenchement suivant, le nouveau run pouvait annuler le run actif. Pendant une période lente, cette logique pouvait répéter les annulations et empêcher la production d’être rafraîchie.

## Correctif

Le groupe de concurrence est maintenant défini au niveau du workflow avec :

```yaml
concurrency:
  group: fable-pages-refresh
  cancel-in-progress: false
```

Une collecte déjà lancée doit donc terminer. Les déclenchements suivants attendent au lieu d’annuler la production en cours.

## Ce qui ne change pas

- la cadence publiée reste 60 minutes ;
- le seuil de données périmées reste 95 minutes ;
- le healthcheck reste bloquant au-delà de 95 minutes ;
- le board continue à neutraliser tous les GO lorsque les données sont périmées ;
- aucun seuil météo n’est modifié par ce correctif.

## Contrôle attendu après fusion

La fusion déclenche immédiatement `Collect & Deploy`. Après le déploiement, `status.json` doit recevoir un nouvel horodatage, le bandeau rouge doit disparaître, et le prochain Healthcheck doit repasser au vert. Si le statut reste ancien après une collecte terminée, il faudra alors examiner le job `Deploy to GitHub Pages` ou la propagation Pages, et non le calcul Family GO.
