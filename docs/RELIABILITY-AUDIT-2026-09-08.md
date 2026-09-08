# Audit de fraîcheur et de connexion — 8 septembre 2026

Base auditée : `7f52158eafe67f4683ee1777ef302311d992171f`, production 3.3.0.
La copie locale historique est en 2.8.5 : ne pas utiliser son GO-LIVE.bat pour publier ce correctif.
Le travail se trouve dans le checkout séparé `fable-audit`.

## Causes vérifiées

1. **Les déclenchements GitHub sont très espacés.** Le 8 septembre, les collectes
   planifiées démarrent à 00:27, 04:58, 09:23, 13:42 et 17:30 UTC, malgré un cron
   toutes les cinq minutes. Les exécutions examinées réussissent : ce n'est pas
   la preuve d'une panne Open-Meteo. GitHub documente les retards et pertes de
   déclenchements : https://docs.github.com/en/actions/how-tos/troubleshoot-workflows.
2. **Le secours partage le même ordonnanceur.** Le healthcheck 34256811171 ne
   commence qu'à 17:23 UTC et déclenche une collecte à 17:25 après confirmation.
   Le statut devient frais à 17:27. Une exécution verte peut donc masquer
   plusieurs heures de données anciennes avant sa réparation automatique.
3. **La vue mobile ne recharge jamais ses caches.** Les promesses rejetées y
   restent également mémorisées : une coupure initiale persiste jusqu'au rechargement.
4. **Les requêtes navigateur n'ont ni délai limite ni nouvelle tentative.**
   Plusieurs composants demandent les mêmes JSON séparément. Le parseur JSON du
   tableau principal pouvait rejeter hors du bloc de gestion d'erreur.
5. **Le code généré de la vue experte conserve 95 minutes comme limite absolue.**
   Les autres vues utilisent les échéances publiées, dont six heures pour la
   limite absolue. Le résultat dépendait de la vue et de l'ordre de chargement.
6. **Un statut neuf suffit au contrôle de santé**, même avec des fichiers de
   ports ou des fenêtres anciens.

Sources opérationnelles :
- https://github.com/rbpower-hub/fable-collector/actions/runs/34256811171
- https://github.com/rbpower-hub/fable-collector/actions/runs/34257030766
- https://rbpower-hub.github.io/fable-collector/status.json

## Correctifs préparés

- Client JSON commun : limite de 12 secondes par tentative, une nouvelle
  tentative sur erreur transitoire, lecture du corps incluse dans le délai,
  regroupement des demandes simultanées et cache partagé de deux secondes.
  Les réponses anciennes ne sont pas utilisées comme repli silencieux.
- Rafraîchissements principal et simple sans chevauchement, reprise au retour
  du réseau ; vue simple actualisée chaque minute même sans la carte.
- Vue mobile rechargée chaque minute et au retour sur l'onglet/réseau,
  caches réinitialisés, échecs non mémorisés, refus des verdicts périmés.
- Vue experte alignée sur les échéances de fraîcheur déjà publiées ; aucun
  allongement supplémentaire des seuils métier ou de fraîcheur.
- Contrôle de l'âge de chaque port et de windows.json, rejet des horodatages
  sans fuseau ou situés plus de cinq minutes dans le futur.
- Healthcheck en cours laissé terminer au lieu d'être annulé par le suivant.
- Déclencheur indépendant prêt : `python -m fable.watchdog --dispatch`.

## Supprimer la dépendance au cron GitHub

Augmenter encore la fréquence du cron GitHub ne garantit pas la collecte.
Installer le watchdog sur un hôte toujours allumé, extérieur à GitHub Actions.
Il lit la production, détecte les données âgées de plus de 75 minutes ou
incomplètes, et déclenche le workflow existant. Il évite une relance si une
collecte attend/tourne ou si une relance a déjà eu lieu depuis moins de dix minutes.
Le passage suivant confirme la production ; une demande acceptée n'est pas
considérée comme la preuve d'un déploiement réussi.

Pré-requis : Python 3.11+, accès HTTPS sortant, checkout courant à
`/opt/fable-collector`, utilisateur système `fable` pouvant le lire.
Le watchdog utilise uniquement la bibliothèque standard de Python.

Créer `/etc/fable-watchdog.env`, accès limité à root, contenant :

```text
FABLE_GITHUB_TOKEN=<jeton dédié au dépôt avec Actions: read and write>
FABLE_GITHUB_REPOSITORY=rbpower-hub/fable-collector
FABLE_BASE_URL=https://rbpower-hub.github.io/fable-collector
```

Ce secret reste sur le serveur. Ne jamais le mettre dans le board ou le dépôt.
Installer les deux fichiers `ops/fable-watchdog.*` dans `/etc/systemd/system/`,
puis exécuter sur cet hôte :

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now fable-watchdog.timer
sudo systemctl start fable-watchdog.service
sudo journalctl -u fable-watchdog.service -n 30
```

Vérification sans relance : `python -m fable.watchdog` (0 sain, 1 anomalie).
Avec `--dispatch`, 0 signifie sain, relance en cours ou demandée ; 2 signifie
échec de configuration/API. Le timer réessaie au passage suivant. Le suivi
d'erreurs du serveur doit surveiller ce service et son timer.

L'hôte et le jeton restent à configurer : aucun service externe n'a été activé
pendant cet audit. GitHub Pages et ses runners restent nécessaires au build
et au déploiement, même avec cet ordonnanceur indépendant.

## Publication et retour arrière

Validation locale : 294 tests Python, 89 tests JavaScript, Ruff, syntaxe de
tous les scripts et du module généré, sept scénarios visuels Playwright sur
Edge (mobile, tablette, bureau ; données fraîches, périmées, manquantes,
vides et erreur marine). Les scénarios visuels utilisent des données simulées.
Les tests réseau couvrent coupure/reprise, corps de réponse bloqué, 503, 404,
JSON invalide, demandes simultanées et récupération des caches mobiles.
Le contrôle réel de production a signalé 129–130 minutes d'ancienneté pendant
l'audit ; les correctifs locaux ne sont donc pas présentés comme déjà actifs.

Le correctif est livré dans la version 3.3.1 après autorisation de publication.
Valider le workflow CI, publier, puis vérifier une reprise après coupure réseau
sur les vues simple et mobile. Pour revenir en arrière, annuler le commit du
correctif et republier ; désactiver le timer externe avec
`sudo systemctl disable --now fable-watchdog.timer` si nécessaire.
