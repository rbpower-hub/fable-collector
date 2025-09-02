# FABLE Collector (free, GitHub Pages ready)

Collecte **horaire** Open‑Meteo (ECMWF + ICON) pour le vent/rafales/direction + **Marine** (Hs/Tp).
Publie des **JSON** par spot dans `public/` et déploie sur **GitHub Pages** via Actions.

## Utilisation rapide
1. Crée un dépôt GitHub (ex. `fable-collector`), puis téléverse tout ce dossier.
2. Active **Pages**: *Settings → Pages → Deploy from a branch* → branche `gh-pages`, dossier `/ (root)`.
3. Le workflow `FABLE Collector` tourne **toutes les 6 h** et à la demande (*Run workflow*).  
   Les fichiers sont publiés sur Pages : `https://<user>.github.io/fable-collector/<slug>.json`

### Config
- Édite `sites.yaml` pour ajuster **spots** et **rayon Shelter Bonus**.
- Par défaut, horizon = **48 h** (modifiable via variable d'environnement `HORIZON_HOURS`).
