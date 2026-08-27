# Mobile_view

Vue mobile autonome, servie à `/<base>/mobile/`. Modules ES recopiés tels quels
par le déploiement Pages ; aucune étape de build, aucun impact sur
`public/index.html`.

- `index.html` — coquille et chargement des modules
- `mobile.css` — jetons du système visuel et mise en page
- `js/thresholds.js` — seuils, depuis `meta.rules` complété par `rules.normalized.json`
- `js/hour-verdict.js` — portage de `fable/window_policy.py`, vérifié par test
- `js/engine-assessment.js` — priorité aux évaluations horaires publiées par le moteur
- `js/chart.js` — frise 72 h et vue tableau
- `js/decision.js`, `js/spot.js`, `js/carte.js` — les trois écrans
- `js/app.js` — chargement, routage par fragment, navigation basse

Documentation et limites : [`docs/MOBILE-VIEW.md`](../../docs/MOBILE-VIEW.md).
