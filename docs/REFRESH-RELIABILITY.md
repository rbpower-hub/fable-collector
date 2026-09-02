# Fiabilité de la collecte et des données publiées

## Diagnostic

Le bandeau `Données périmées` provient de la fraîcheur publiée, tandis qu’un
workflow rouge peut aussi échouer avant l’exécution de FABLE. Le healthcheck
serveur lance maintenant la récupération dès 75 minutes afin de garder une
marge avant la limite publique de 95 minutes.

GitHub peut retarder ou supprimer des événements planifiés sans mettre le
workflow en erreur. Une seule matinée a ainsi présenté plus de trois heures
entre deux déclenchements pourtant configurés trois fois par heure. Le
collecteur dispose maintenant de douze occasions décalées par heure ; son
garde-fou n'autorise toujours une vraie collecte que lorsque les données ont
au moins 35 minutes. Le healthcheck possède quatre occasions par heure au lieu
d'une seule.

Lorsqu’une collecte est nécessaire, le build et le déploiement utilisaient
chacun le groupe de concurrence `pages` avec `cancel-in-progress: true`.

Si une collecte ou la propagation GitHub Pages dépassait l’intervalle avant le déclenchement suivant, le nouveau run pouvait annuler le run actif. Pendant une période lente, cette logique pouvait répéter les annulations et empêcher la production d’être rafraîchie.

## Correctif

Le groupe de concurrence est maintenant défini au niveau du workflow avec :

```yaml
concurrency:
  group: fable-pages-refresh
  cancel-in-progress: false
```

Une collecte déjà lancée doit donc terminer. Les déclenchements suivants attendent au lieu d’annuler la production en cours.

Les jobs `schedule_guard` et `health` disposent respectivement de 10 et 12
minutes. Les anciennes limites de 3 et 8 minutes pouvaient expirer pendant la
préparation d’un runner hébergé ou avant la fin des cinq contrôles confirmant
une panne. Cette marge ne masque pas une erreur applicative : les commandes et
leurs délais réseau restent bornés, et le job final échoue toujours après cinq
contrôles négatifs.

## Ce qui ne change pas

- la cadence publiée reste 60 minutes ;
- le seuil client de données périmées reste géré indépendamment par le board ;
- le healthcheck serveur déclenche une récupération à 75 minutes ;
- le board continue à neutraliser tous les GO lorsque les données sont périmées ;
- aucun seuil météo n’est modifié par ce correctif.

## Contrôle attendu après fusion

La fusion déclenche immédiatement `Collect & Deploy`. Après le déploiement, `status.json` doit recevoir un nouvel horodatage, le bandeau rouge doit disparaître, et le prochain Healthcheck doit repasser au vert. Si le statut reste ancien après une collecte terminée, il faudra alors examiner le job `Deploy to GitHub Pages` ou la propagation Pages, et non le calcul Family GO.

Une annotation `The job was not acquired by Runner ... after multiple
attempts` vient de GitHub Actions : le job n’a obtenu aucun runner et aucune
étape du dépôt n’a démarré. Ce cas externe ne peut pas être corrigé dans le
code ; une relance est requise.
