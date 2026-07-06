# Mise en production — v2.0.0

## 1. Pousser le code

Depuis un clone local du dépôt :

```bash
git clone https://github.com/rbpower-hub/fable-collector.git
cd fable-collector
git checkout -b v2-pro

# Remplacer le contenu par l'arborescence v2 livrée (tout sauf .git),
# y compris la SUPPRESSION de : main.py, healthcheck.yml (racine),
# ras-fartass.json (racine), stats/, scripts/, .github/workflows/pages.yml.
# Puis :
git add -A
git commit -m "v2.0.0 — refonte professionnelle (audit 2026-07)"
git push -u origin v2-pro
```

Ouvrir une PR et merger dans `main` (la CI ruff+pytest doit passer), ou
pousser directement sur `main` si tu préfères.

## 2. Réactiver les workflows (IMPORTANT)

GitHub a désactivé les crons pour inactivité (cause de la panne de déc. 2025) :

1. Onglet **Actions** → si un bandeau propose *« Enable workflows »*, cliquer.
2. Vérifier que les 3 workflows apparaissent : *Collect & Deploy*,
   *Healthcheck*, *CI*.
3. Lancer **Collect & Deploy ▸ Run workflow** (main) une première fois à la
   main et vérifier le run vert.

## 2bis. Vérifier les modèles de houle (30 s, une fois)

```bash
python tools/probe_marine_models.py --lat 36.9203 --lon 10.2846
```

Les trois modèles (`meteofrance_wave`, `ncep_gfswave025`, `ecmwf_wam025`)
doivent renvoyer des points Hs. Si l'un échoue (nom changé côté Open-Meteo),
ajuster `http.marine_model_order` dans `rules.yaml` — le pipeline fonctionne
de toute façon (fallback + parallèles best-effort), seul « High » exige
2 modèles valides.

## 3. Vérifier la production

Quelques minutes après le run :

- https://rbpower-hub.github.io/fable-collector/status.html → ✅ FRAIS
- https://rbpower-hub.github.io/fable-collector/windows.json → destinations
  = spots uniquement (pas de catalog.json / rules.normalized.json)
- https://rbpower-hub.github.io/fable-collector/sites.normalized.json → nouveau
- Onglet Actions : *Healthcheck* → Run workflow → vert.

## 4. Ce qui tourne ensuite tout seul

| Workflow | Cadence | Rôle |
|---|---|---|
| Collect & Deploy | chaque heure (:07) | collecte + Pages |
| Collect & Deploy / keepalive | dimanche 03:23 UTC | commit vide anti-désactivation |
| Healthcheck | toutes les 6 h (:41) | surveille la prod, ouvre une issue si stale |
| CI | à chaque push/PR | ruff + pytest |

## 5. Points de configuration

- **Pages** : Settings → Pages → Source = *GitHub Actions* (déjà le cas si
  l'ancien pages.yml déployait).
- **Issues** : laisser activées (le healthcheck alerte par issue, label
  `healthcheck`).
- Ajouter un spot / changer de port : éditer `sites.yaml`, push — c'est tout.
- Ajuster des seuils : `rules.yaml` (validés par preflight à chaque run).
