# Runbook d'exploitation

Runbook court pour l'exploitation quotidienne de `fable-collector`.

## Avant un push

Sur le poste local :

```bash
SETUP-LOCAL.bat
CHECK-LOCAL.bat
```

Attendu :
- `fable.preflight` termine sans erreur
- `ruff check .` est vert
- `pytest -q` est vert

## Apres un push

Verifier en priorite :
- onglet **Actions** : `Collect & Deploy`, `CI`, `Healthcheck`
- `status.html` : statut frais
- `windows.json` : seulement des spots dans les destinations
- un spot critique, par exemple `gammarth-port.json`

URLs utiles :
- `https://rbpower-hub.github.io/fable-collector/status.html`
- `https://rbpower-hub.github.io/fable-collector/status.json`
- `https://rbpower-hub.github.io/fable-collector/windows.json`
- `https://rbpower-hub.github.io/fable-collector/gammarth-port.json`

## Si `CI` echoue

1. Lire d'abord l'etape qui casse : `ruff`, `pytest`, ou installation.
2. Rejouer localement : `CHECK-LOCAL.bat`
3. Corriger, puis repusher.

Notes :
- un warning GitHub Actions sur Node 20 dans un ancien run n'est pas bloquant
- le signal important est l'etat du run le plus recent

## Si `Collect & Deploy` echoue

1. Verifier si l'erreur vient de :
- `preflight` : probleme de `sites.yaml` ou `rules.yaml`
- `collect` : API Open-Meteo ou modele indisponible
- `reader` : regression de schema dans `public/*.json`
- `publish` : controle final ou fichier manquant

2. Si l'erreur mentionne les modeles de houle, tester localement :

```bash
py tools/probe_marine_models.py --lat 36.9203 --lon 10.2846
```

3. Si un modele a change cote Open-Meteo :
- ajuster `http.marine_model_order` dans `rules.yaml`
- repusher

## Si `Healthcheck` passe au rouge

1. Ouvrir l'issue `healthcheck` creee par GitHub Actions
2. Regarder `status.json` :
- `generated_at`
- `stale_after`
- `missing_spots`
3. Verifier si le dernier `Collect & Deploy` a bien tourne
4. Si le cron semble bloque, lancer `Collect & Deploy` a la main depuis `Actions`

## Incidents les plus probables

- **Cron GitHub inactif** : relancer le workflow, verifier que le repo reste actif
- **Open-Meteo indisponible** : attendre puis relancer ; le fallback couvre deja une partie des cas
- **Regression config** : revenir au dernier `sites.yaml` ou `rules.yaml` valide
- **Spot manquant** : verifier le slug, les coordonnees, puis refaire `preflight`

## Definition de succes

Le systeme est considere sain si :
- le dernier `Collect & Deploy` est vert
- le dernier `CI` est vert
- `status.html` affiche un statut frais
- `windows.json` et au moins un spot live sont coherents
