# Mobile_view

Vue mobile autonome, publiée à `/<base>/mobile/`. Elle lit les mêmes JSON que
le tableau de bord actuel et ne modifie ni `public/index.html`, ni
`fable/dashboard_modules.py`, ni `fable/dashboard_patch.py`. Le job de
déploiement téléverse `public/` en entier : aucune étape de build à ajouter.

## Pourquoi une page séparée

Le tableau de bord actuel n'existe pas sous forme de sources modulaires :
`js/app.js` est extrait par expression régulière du `main()` inline de
`public/index.html` au moment du déploiement, puis une dizaine de correctifs
sont appliqués par recherche-remplacement de chaînes littérales. Greffer un
nouvel écran dans cet empilement le rendrait plus fragile. Mobile_view vit à
côté, en modules ES recopiés tels quels.

Les deux vues cohabitent donc en production. On compare, puis on bascule.

## Écrans

| Écran | Contenu |
|---|---|
| Décision | verdict courant, frise 72 h interactive, vue tableau, jours suivants |
| Détail | une journée heure par heure, trace des règles, accord des modèles, conditions |
| Carte | corridor Leaflet, spots colorés par verdict, secteur onshore, premier bloqueur |

La route est dans le fragment : `#/decision/<slug>`, `#/spot/<slug>/<AAAA-MM-JJ>`,
`#/carte/<slug>/<destination>`.

## Données lues

Toutes en même origine, un niveau au-dessus de `mobile/` :

- `index.json` — catalogue des spots, horizon, version du collecteur
- `<slug>.json` — horaires, modèles de vent, modèles de vagues, `meta.rules`
- `sites.normalized.json` — coordonnées, secteurs onshore, waypoints, vitesses
- `rules.normalized.json` — complément de seuils (voir plus bas)
- `windows.json` — fenêtres du moteur et premier bloqueur, affichés tels quels
- `status.json` — optionnel

## Les deux schémas de règles

C'est le piège principal de ce dépôt.

`fable.window_models.Thresholds.from_rules` lit le schéma **plat** de
`rules.yaml` : `wind.family_max_kmh`, `tp_matrix.transit.*`, `overrides.*`,
`sea.*`. `rules.normalized.json` est un schéma **v2 imbriqué** que `from_rules`
ne sait pas lire : lui passer ce fichier ferait retomber silencieusement tous
les seuils sur les valeurs par défaut du code, qui ne sont pas celles de
`rules.yaml` (par exemple `tp_min_at_lt04` 3,2 au lieu de 3,0 et
`wind_family_max` 20 au lieu de 22). Aucun appel en production ne fait cette
erreur aujourd'hui ; `tests/test_mobile_view_parity.py` la documente pour
qu'un futur branchement ne passe pas inaperçu.

Mobile_view lit donc `meta.rules` de chaque spot — c'est le schéma plat que le
collecteur republie avec son digest — et ne complète par
`rules.normalized.json` que ce que `meta.rules` ne publie pas : `prudent`,
`combined.short_steep`, `family.window_hours`, `adaptive_window`.

**Amélioration possible du collecteur** : publier `rules.yaml` complet en JSON
à côté des autres fichiers supprimerait cette fusion et donnerait au front une
source unique.

## Verdict horaire

`public/mobile/js/hour-verdict.js` est un portage direct de
`fable/window_policy.py` (`hard_reasons`, `standard_wave_reasons`,
`hour_ok_for_phase`) pour la phase `transit` hors mouillage abrité. Il existe
parce que le JSON publié n'expose pas de verdict heure par heure : `windows.json`
ne donne que les fenêtres agrégées et leur premier bloqueur.

**Le moteur reste la référence.** Depuis la publication des fichiers
`hourly/<slug>.json`, Mobile_view les utilise en priorité. Le portage JS reste
uniquement un repli compatible avec un run plus ancien ou incomplet.

Vérification :

```bash
# table de référence partagée
python tools/make_mobile_fixture.py
python -m pytest tests/test_mobile_view_parity.py
node --test tests/js/mobile-hour-verdict.test.mjs

# comparaison sur des données réelles
python tools/compare_hour_verdicts.py <dossier_public> > engine.json
```

Sur le run du 27/08/2026, les deux implémentations donnent le même état sur
les 504 heures publiées (7 spots × 72 h).

**Meilleure solution à terme** : exposer le verdict horaire dans le JSON
publié et supprimer ce portage.

## Système visuel

Les jetons sont dans `mobile.css`, mesurés sur la surface carte `#0d1626` :
encre primaire 15,9:1, secondaire 8,2:1, discrète 4,6:1 ; séries et statuts
tous au-dessus de 3:1.

Trois règles qui ne se négocient pas :

- **Jamais de double axe.** Le vent en km/h et la houle en mètres sont deux
  tracés empilés qui partagent l'axe des heures.
- **Le verdict ne passe jamais par la couleur seule.** Rouge et vert sont à
  ΔE 4,1 en deutéranopie, donc indiscernables : GO est un aplat, Prudence une
  trame à 45°, No-go une trame à 135°, et la légende plus la vue tableau
  restent obligatoires.
- **Aucun emoji dans l'interface.** Les icônes sont des SVG en trait sur
  grille 24, qui se recolorent et rendent pareil sur iOS et Android.

## Limites connues

- Le verdict de fenêtre affiché en tête vient des plages GO continues
  calculées côté client, pas du détecteur de fenêtres du moteur, qui valide en
  plus le corridor, le mouillage, la lumière du jour astronomique et la
  confiance. Quand `windows.json` porte une fenêtre validée pour la
  destination, elle est affichée telle quelle.
- L'écran Carte charge les tuiles OpenStreetMap et les assombrit par filtre
  CSS. Un fond nautique dédié serait meilleur en plein soleil.
- Pas encore d'internationalisation : la vue actuelle gère FR / EN / AR, celle-ci
  est en français seulement.
