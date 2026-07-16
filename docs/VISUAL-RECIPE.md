# Recette visuelle FABLE

La recette visuelle vérifie le board publié dans Chromium avec Playwright, à partir de données déterministes servies localement.

## Couverture stable

Le workflow `.github/workflows/visual-recipe.yml` exécute six scénarios représentatifs et indépendants :

- mobile 390×844, français, thème nautique, données fraîches avec fenêtres ;
- mobile 390×844, arabe RTL, thème nautique, `windows.json` absent ;
- tablette 768×1024, anglais, thème sombre, données périmées ;
- tablette 768×1024, français, thème sombre, données fraîches sans fenêtre ;
- PC 1440×900, arabe RTL, thème nautique, erreur de données marines ;
- PC 1440×900, français, thème sombre, données fraîches avec carte et Vue Expert.

## Contrôles

Chaque scénario contrôle le verdict attendu, la langue et la direction, le thème, l’absence de débordement horizontal, le contraste WCAG AA du hero et du badge, les messages d’erreur marine et les commandes propres au format. Les scénarios concernés ouvrent également les réglages mobiles, la carte et la Vue Expert.

## Artefacts

Chaque job dépose un artefact `fable-visual-*` contenant :

- `SUMMARY.md` ;
- `report.json` ;
- `run.log` et les points de contrôle ;
- les captures d’écran du scénario.

Les artefacts sont conservés pendant 14 jours.

## Exécution

La recette est déclenchée sur les pull requests qui modifient le dashboard, les assets publics, les sites ou les scripts visuels. Elle peut aussi être lancée manuellement avec `workflow_dispatch`.

Le workflow reconstruit `public/index.html` avec `fable.dashboard_patch`, remplace Leaflet distant par une copie locale, démarre un serveur HTTP local, puis exécute chaque scénario dans un job séparé afin qu’un défaut soit localisé sans bloquer les autres combinaisons.
