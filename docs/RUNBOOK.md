# Runbook d’exploitation

Runbook opérationnel pour `fable-collector` et la couche de recommandations d’activités.

## Avant un push

Sur le poste local :

```bash
SETUP-LOCAL.bat
CHECK-LOCAL.bat
```

Attendu :

- `fable.preflight` termine sans erreur ;
- `ruff check .` est vert ;
- `pytest -q` est vert.

Pour tester la chaîne complète :

```bash
python collect.py
python reader.py
python -m fable.recommendations
python -m fable.publish
```

Vérifier que `public/recommendations.json` est produit même lorsqu’aucune activité n’est recommandée.

## Après un push

Vérifier en priorité :

- onglet **Actions** : `CI`, `Collect & Deploy`, `Healthcheck` ;
- `status.html` : statut frais ;
- `windows.json` : fenêtres cohérentes ;
- `recommendations.json` : recommandations uniquement pour des fenêtres présentes dans `windows.json` ;
- le board : présence de la section **Que faire sur l’eau ?** ;
- un spot critique, par exemple `gammarth-port.json`.

URLs utiles :

- `https://rbpower-hub.github.io/fable-collector/`
- `https://rbpower-hub.github.io/fable-collector/status.html`
- `https://rbpower-hub.github.io/fable-collector/status.json`
- `https://rbpower-hub.github.io/fable-collector/windows.json`
- `https://rbpower-hub.github.io/fable-collector/recommendations.json`
- `https://rbpower-hub.github.io/fable-collector/gammarth-port.json`

## Contrôle rapide des recommandations

Pour chaque entrée de `recommendations.json` :

1. le couple `dest_slug` + `start/end` doit exister dans `windows.json` ;
2. la liste `activities` doit être vide si les seuils propres aux activités sont dépassés ;
3. les données `fishing` doivent correspondre au spot et à la saison ;
4. `astronomy` peut être partiellement vide, sans casser le classement ;
5. `lunar_bonus` doit rester secondaire et ne jamais être la justification unique d’une activité.

## Modifier les profils de pêche

Éditer `fishing_profiles.yaml` pour ajuster :

- espèces ;
- techniques ;
- montages ;
- appâts ;
- profondeurs ;
- périodes préférentielles.

Après modification :

```bash
python -m pytest -q tests/test_recommendations.py
python -m fable.recommendations
```

Ne pas présenter les profils comme une garantie de capture. Vérifier périodiquement leur cohérence avec les observations locales et la réglementation tunisienne.

## Modifier les seuils d’activité

Éditer `activity_profiles.yaml`. Les seuils d’activité doivent rester égaux ou plus prudents que l’usage réel visé.

Exemples de contrôles :

- baignade familiale plus stricte que simple navigation ;
- mouillage abrité conditionné à une zone réellement sous le vent ;
- pêche au fond ou micro-jig refusés si la dérive et la mer rendent la pratique inadaptée ;
- visibilité minimale conservée pour la traîne côtière.

## Si CI échoue

1. Identifier l’étape : installation, Ruff ou Pytest.
2. Rejouer `CHECK-LOCAL.bat`.
3. Pour la couche activités, lancer spécifiquement :

```bash
python -m pytest -q tests/test_recommendations.py
```

4. Corriger puis repusher.

## Si Collect & Deploy échoue

Identifier l’étape :

- `preflight` : problème de `sites.yaml` ou `rules.yaml` ;
- `collect` : API Open-Meteo, modèle ou données astronomiques ;
- `reader` : régression dans les spots ou `windows.json` ;
- `recommendations` : YAML invalide, fichier spot absent ou régression du moteur ;
- `publish` : contrôle final ou fichier manquant.

Si les modèles de houle sont en cause :

```bash
py tools/probe_marine_models.py --lat 36.9203 --lon 10.2846
```

Si `recommendations.json` est absent :

1. vérifier que `windows.json` existe et est lisible ;
2. valider `fishing_profiles.yaml` et `activity_profiles.yaml` avec PyYAML ;
3. exécuter `python -m fable.recommendations` ;
4. inspecter la sortie et les erreurs du workflow.

## Si le board n’affiche pas les activités

1. ouvrir directement `recommendations.json` ;
2. vérifier que `public/activity-board.js` est présent dans `catalog.json` ;
3. vérifier dans l’artefact Pages que le script est injecté avant `</body>` ;
4. vider le cache navigateur ;
5. confirmer qu’au moins une fenêtre Family GO contient une activité compatible.

Une section vide peut être normale lorsque toutes les activités sont filtrées.

## Si Healthcheck passe au rouge

1. ouvrir l’issue créée par GitHub Actions ;
2. examiner `generated_at`, `stale_after` et `missing_spots` dans `status.json` ;
3. vérifier le dernier run `Collect & Deploy` ;
4. relancer manuellement le workflow si le cron semble bloqué.

## Incidents probables

- **Cron GitHub inactif** : relancer le workflow et vérifier l’activité du dépôt.
- **Open-Meteo indisponible** : relancer ; les fallbacks couvrent une partie des cas.
- **Données marine absentes** : aucune fenêtre ne doit être fabriquée.
- **Profil YAML invalide** : corriger l’indentation ou le type des champs.
- **Recommandation incohérente** : vérifier d’abord la fenêtre source, puis les seuils et le profil saisonnier.
- **Spot manquant** : contrôler slug, coordonnées et sortie du preflight.

## Définition de succès

Le système est sain si :

- `CI` et `Collect & Deploy` sont verts ;
- `status.html` affiche des données fraîches ;
- `windows.json` reste cohérent avec les spots ;
- `recommendations.json` est publié ;
- aucune recommandation n’existe hors d’une fenêtre validée ;
- le board affiche correctement les activités disponibles ou un état vide explicite.
