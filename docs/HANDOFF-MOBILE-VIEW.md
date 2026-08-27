# Dossier de passation — Mobile_view

Document autonome. Il contient tout ce qu'il faut pour reprendre
l'implémentation sans accès à la conversation d'origine.

- **Dépôt** : `rbpower-hub/fable-collector`
- **Branche** : `feat/mobile-view`, commit `d997eaf`, 22 fichiers, 3351 lignes
- **Patch** : `mobile-view.patch` (`git am`)
- **État** : écrit, testé, **non poussé, non fusionné, non déployé**
- **Données de référence** : run collector 3.3.0 du 27/08/2026 12:31 Africa/Tunis

---

## 1. Ce qu'il faut savoir avant de toucher au code

### 1.1 Le tableau de bord actuel n'a pas de sources modulaires

`public/js/app.js` **n'existe pas dans le dépôt**. Il est produit au moment du
déploiement par `fable/dashboard_modules.py`, qui extrait par expression
régulière le `main()` inline de `public/index.html` (81 ko), puis
`fable/dashboard_patch.py` applique une dizaine de correctifs par
recherche-remplacement de chaînes littérales sur le HTML.

Conséquence : **ne pas greffer de nouvel écran dans `public/index.html`**.
Chaque ajout rapproche ces regex de la rupture. Mobile_view vit à côté, en
modules ES recopiés tels quels.

### 1.2 Le déploiement ne demande aucune configuration

`.github/workflows/collect.yml` téléverse `public/` en entier vers Pages
(`actions/upload-pages-artifact` avec `path: public`). Un dossier
`public/mobile/` sort donc à `/fable-collector/mobile/` sans rien changer au
workflow. Le collecteur tourne à `7,27,47 * * * *`.

### 1.3 Le piège des deux schémas de règles

**C'est le point le plus important du dossier.**

`fable.window_models.Thresholds.from_rules` lit le schéma **plat** de
`rules.yaml` :

```yaml
wind: {family_max_kmh: 22, nogo_min_kmh: 25, onshore_degrade_kmh: 22}
sea:  {family_max_hs_m: 0.5, nogo_min_hs_m: 0.8}
overrides: {gusts_hard_nogo_kmh: 30, squall_delta_kmh: 17, visibility_km_min: 5}
tp_matrix: {transit: {hs_lt_0_4_family_tp_s: 3.0, hs_0_4_0_5_family_tp_s: 4.2}}
prudent: {enabled: true, wind_max_kmh: 23, gust_max_kmh: 28, hs_max_m: 0.4, tp_min_s: 3.3}
```

`public/rules.normalized.json` est un schéma **v2 imbriqué**
(`family.thresholds.wind.family_max_kmh`, …) que `from_rules` **ne sait pas
lire**. Lui passer ce fichier ne lève aucune erreur : chaque `dget` échoue et
retombe sur la valeur par défaut écrite en dur dans le code, qui n'est pas
celle de `rules.yaml`.

| Seuil | `rules.yaml` | Défaut du code si mauvais schéma |
|---|---|---|
| `wind_family_max` | 22 km/h | **20 km/h** |
| `tp_min_at_lt04` | 3,0 s | **3,2 s** |
| `tp_min_at_04_05` | 4,2 s | **4,5 s** |
| `prudent_wind_max` | 23 km/h | **22 km/h** |
| `prudent_tp_min` | 3,3 s | **3,5 s** |

Cette erreur a été commise pendant le développement : le moteur a répondu
72 heures de NO-GO sur Gammarth, ce qui semblait plausible. Elle n'a été
détectée qu'en comparant les chaînes de raisons (`Tp<3.2@Hs<0.4` au lieu de
`Tp<3.0@Hs<0.4`).

Aucun appel en production ne fait cette erreur aujourd'hui
(`window_detect.py` et `windows.py` reçoivent `rules.yaml`). Le garde-fou est
`tests/test_mobile_view_parity.py::test_normalized_rules_are_not_readable_by_the_engine`.

**Source à utiliser côté front** : `meta.rules` de chaque spot, qui est le
schéma plat republié par le collecteur avec son digest
(`45099c633b16`). Il ne publie pas `prudent`, `combined.short_steep`,
`family.window_hours` ni `adaptive_window` : ceux-là viennent de
`rules.normalized.json`. `public/mobile/js/thresholds.js` fusionne les deux
dans cet ordre et ne retombe sur une constante que si aucun fichier ne la
porte.

---

## 2. Contrats de données

Tous les fichiers sont en même origine, un niveau au-dessus de `mobile/`.

### `index.json`
```json
{"generated_at": "2026-08-27T12:31:09+01:00", "tz": "Africa/Tunis",
 "collector_version": "3.3.0", "home": "gammarth-port",
 "window": {"start_local": "...", "end_local": "...", "hours": 72},
 "spots": [{"slug": "gammarth-port", "name": "Gammarth (port)",
            "points": 72, "path": "gammarth-port.json"}]}
```

### `<slug>.json`
```
meta.rules            schéma plat + digest       <- source des seuils
meta.tz, lat, lon, onshore_sectors, shelter_bonus_radius_km
hourly.time[72]       "2026-08-27T12:00"         heure locale, sans offset
hourly.wind_speed_10m, wind_gusts_10m, wind_direction_10m, weather_code,
       visibility (m), temperature_2m, uv_index, hs (m), tp (s)
models.<source>.hourly.{wind_speed_10m, wind_gusts_10m, wind_direction_10m,
                        weather_code, visibility}
marine_models.<source>.hourly.{wave_height, wave_period}
daily.{sunrise, sunset, moonrise, moonset, moon_phase}
```

Deux modèles de vent (`icon_seamless`, `gfs_seamless`), trois de vagues
(`meteofrance_wave`, `ncep_gfswave025`, `ecmwf_wam025`). Les valeurs de
`marine_models` peuvent être `null` — `ecmwf_wam025` n'a pas de houle
secondaire.

### `sites.normalized.json`
```json
{"version": 2, "home": "gammarth-port",
 "sites": [{"slug": "...", "name": "...", "lat": …, "lon": …,
            "map_lat": …, "map_lon": …,
            "transit_speed_kts": {"min": 16, "max": 24},
            "route_origin": null, "route_points": [{"lat":…, "lon":…, "name":"…"}],
            "onshore_sectors": [[30, 150]], "route_kind": "standard",
            "route_note": null, "beta": false, "path": "…json"}]}
```

`map_lat`/`map_lon` sont les coordonnées d'affichage, distinctes de
`lat`/`lon` qui servent à la collecte. Utiliser `map_*` sur la carte.

### `windows.json`
```json
{"windows": [{"dest_slug": "kelibia.json", "dest_name": "Kelibia",
              "required_hours": 4, "windows": [], "watch_windows": [],
              "diagnostics": {"status": "blocked",
                "first_blocker": {"location_name": "Kelibia", "phase": "transit",
                  "time": "2026-08-27T12:00:00+01:00",
                  "reasons": ["rafales>=30"],
                  "reason_fr": "rafales trop fortes (31 km/h)",
                  "metrics": {…}}}}]}
```

**À afficher tel quel.** C'est le verdict du moteur, il fait autorité sur
tout calcul côté client.

---

## 3. Le portage du verdict horaire

### Pourquoi il existe

Le JSON publié n'expose **aucun verdict heure par heure**. `windows.json` ne
donne que les fenêtres agrégées et leur premier bloqueur. Pour dessiner une
bande de verdict sur 72 h, il a fallu porter la politique côté client.

`public/mobile/js/hour-verdict.js` (206 lignes) reproduit
`fable/window_policy.py` pour la phase `transit`, hors mouillage abrité :
`hard_reasons`, `standard_wave_reasons`, `hour_ok_for_phase`, et
`worst_metrics_at_hour` de `window_models.py`.

**Le moteur Python reste la référence. Toute divergence est un bug du
portage, jamais une règle nouvelle.**

### Ordre d'évaluation

```
1. hard_reasons  ->  si non vide : NO-GO (veto)
     données manquantes · orages (codes 95/96/99) · visibilité < 5 km
     rafales >= 30 · vent >= 25 · grain (rafale-vent >= 17 sur un modèle)
     Hs > 0,80 · mer courte et creuse dure (Hs >= 0,6 et Tp <= 5,0)
2. familyReasons ->  si vide : GO
     onshore et vent > 22 · vent >= 22
     Hs >= 0,50 · (Hs < 0,4 et Tp < 3,0) · (0,4 <= Hs < 0,5 et Tp < 4,2)
     mer courte et creuse (Hs >= 0,5 et Tp <= 6,0)
3. prudentReasons -> si vide : PRUDENCE, sinon NO-GO
     tout secteur onshore · vent > 23 · rafales >= 28 · Hs > 0,4 · Tp < 3,3
```

Les scénarios sont évalués **au pire cas sur tous les modèles** : une seule
source de vagues sous le seuil de période suffit à disqualifier l'heure.

### Protocole de vérification — à relancer après toute modification

```bash
# 1. table de référence synthétique, un cas par branche de règle
python tools/make_mobile_fixture.py
python -m pytest tests/test_mobile_view_parity.py      # côté moteur
node --test tests/js/mobile-hour-verdict.test.mjs      # côté vue mobile

# 2. comparaison sur données réelles
python tools/compare_hour_verdicts.py <dossier_public> > engine.json
# puis classifySeries() sur les mêmes JSON et diff des deux séquences
```

`tools/compare_hour_verdicts.py` fait tourner le vrai moteur sur les JSON
publiés et sort un tableau `{slug: [état par heure]}`.

**Résultat de référence, run du 27/08/2026 : 504 heures identiques sur 504**
(7 spots × 72 h). C'est le seuil à tenir.

### Ce que le portage ne fait pas

`hour_ok_for_phase` juge une heure. Le détecteur de fenêtres du moteur
(`window_detect.py`) fait bien plus : validation du corridor par
échantillonnage, phases transit/mouillage/retour, lumière du jour
astronomique, seuil de confiance, hystérésis, fenêtres `watch`. Mobile_view
n'en reproduit **rien**. Les plages GO continues qu'elle calcule sont un
repère de lecture, pas un verdict de fenêtre.

---

## 4. Système visuel

Jetons dans `public/mobile/mobile.css`, mesurés sur la surface carte
`#0d1626`.

| Rôle | Valeur | Contraste |
|---|---|---|
| Plan de page | `#060c15` | — |
| Surface carte | `#0d1626` | — |
| Encart | `#131f33` | — |
| Encre primaire | `#eaf1fa` | 15,9:1 |
| Encre secondaire | `#9db1c8` | 8,2:1 |
| Encre discrète | `#6d829b` | 4,6:1 |
| Accent (chrome seul) | `#35c1e8` | 8,6:1 |
| Vent soutenu | `#3987e5` | 5,0:1 |
| Rafales | `#d95926` | 4,7:1 |
| Houle Hs | `#199e70` | 5,3:1 |
| GO | `#0ca30c` | 5,4:1 |
| Prudence | `#fab219` | 9,9:1 |
| No-go | `#d03b3b` | 3,8:1 |

Palette de séries validée toutes paires : pire écart daltonien ΔE 9,4
(deutan), pire écart vision normale ΔE 20,9. Une quatrième série casse la
garantie — passer en petits multiples.

Typographie : IBM Plex Sans pour le texte, IBM Plex Mono pour les chiffres et
les heures. `tabular-nums` uniquement dans les colonnes de tableau et sur les
graduations, jamais sur une grande valeur isolée.

### Trois règles non négociables

1. **Jamais de double axe.** Le vent en km/h et la houle en mètres sont deux
   tracés empilés qui partagent l'axe des heures. Deux échelles verticales sur
   un même tracé inventent une corrélation absente des données.
2. **Le verdict ne passe jamais par la seule couleur.** Rouge et vert sont à
   ΔE 4,1 en deutéranopie, donc indiscernables. GO est un aplat, Prudence une
   trame à 45°, No-go une trame à 135°. Légende et vue tableau obligatoires.
   Sur une application qui dit d'aller en mer ou non, ce n'est pas cosmétique.
3. **Aucun emoji dans l'interface.** Icônes SVG en trait sur grille 24,
   1,9–2 px, bouts arrondis. Les emoji rendent différemment sur iOS et Android
   et ne se recolorent pas. L'interface actuelle en compte plus de quinze.

Cibles tactiles à 44 px minimum, même quand la hauteur visible est de 30 px.

### Anatomie du graphique

`chart.js`, viewBox `0 0 334 166`, largeur fluide.

```
y=0    bande de verdict, hauteur 9 px, une cellule par heure
y=18   haut du tracé vent
y=106  ligne de base vent          échelle 0 -> max(40, pic arrondi)
y=116  haut du tracé houle
y=160  ligne de base houle         échelle 0 -> max(0,8 ; pic arrondi)
```

- Ligne de série 2 px, jointures et bouts arrondis
- Ruban vent → rafales : aire orange à 16 %, bornée par les deux courbes.
  C'est la pièce maîtresse : elle rend l'écart rafale/vent lisible d'un coup
  d'œil, et sa hauteur est l'indicateur de grain.
- Point de sélection r 4 avec anneau 2 px couleur de fond
- Grille et axes 1 px pleins, jamais en pointillés
- Seuils 1 px, tirets 3/3 — famille en ambre, veto en rouge
- Bandes de nuit `rgba(3,7,13,.6)` derrière les deux tracés
- Couche de saisie transparente sur toute la hauteur : le lecteur vise une
  heure, pas une courbe de 2 px

---

## 5. Inventaire de la branche

```
public/mobile/index.html          29   coquille, chargement des modules
public/mobile/mobile.css         451   jetons et mise en page
public/mobile/js/data.js          60   chargement des JSON, cache
public/mobile/js/thresholds.js   124   fusion des deux schémas de règles
public/mobile/js/hour-verdict.js 206   portage de window_policy.py
public/mobile/js/runs.js          68   plages continues, meilleur créneau par jour
public/mobile/js/format.js        90   formatage FR, traduction des raisons
public/mobile/js/ui.js           109   fabriques DOM, icônes SVG
public/mobile/js/chart.js        261   frise 72 h et vue tableau
public/mobile/js/decision.js     278   écran Décision
public/mobile/js/spot.js         202   écran Détail
public/mobile/js/carte.js        257   écran Carte, Leaflet
public/mobile/js/app.js          239   chargement, routage, navigation

tests/fixtures/mobile_hours.json 527   table de référence partagée
tests/js/mobile-hour-verdict.test.mjs  66
tests/test_mobile_view_parity.py       78
tools/compare_hour_verdicts.py         56
tools/make_mobile_fixture.py           99
docs/MOBILE-VIEW.md                   119
.github/workflows/ci.yml         +14   node --check des 11 modules
```

`carte.js` réutilise `public/js/map.js` (`distanceKm`) et
`public/js/corridor.js` (`pathDistanceKm`, `pointAlongPath`) au lieu d'en
refaire une copie.

Routage par fragment : `#/decision/<slug>`, `#/spot/<slug>/<AAAA-MM-JJ>`,
`#/carte/<slug>/<destination>`.

État des tests sur la branche : **195 pytest, 48 node, ruff propre**, et la
génération de `js/app.js` par `dashboard_patch` passe toujours.

---

## 6. Ce qui reste à faire

Par ordre de valeur décroissante.

### 6.1 Côté collecteur — deux changements qui suppriment une classe de bugs

**Publier le verdict horaire.** Aujourd'hui la vue réimplémente
`window_policy.py` en JS parce que le JSON ne l'expose pas. Ajouter dans
`<slug>.json` un tableau de 72 états (`go` / `prudent` / `nogo`) avec les codes
de raison rendrait `hour-verdict.js` supprimable, et avec lui tout risque de
dérive entre deux implémentations d'une règle de sécurité.

**Publier `rules.yaml` complet en JSON.** Le schéma plat, tel quel, à côté des
autres fichiers. Supprime la fusion `meta.rules` + `rules.normalized.json` et
donne au front une source unique.

### 6.2 Côté vue

**Internationalisation.** La vue actuelle gère FR / EN / AR avec direction RTL
(`public/js/i18n.js`, `public/arabic-locale.js`). Mobile_view est en français
seulement. Toutes les chaînes sont en dur dans les modules ; il faut les
extraire avant d'en avoir des centaines.

**Utiliser la fenêtre du moteur quand elle existe.** `decision.js` accepte
déjà un paramètre `engineWindow` mais `app.js` lui passe `null`. Le brancher
sur `windows.json` : quand une fenêtre validée existe pour la destination,
elle doit primer sur les plages GO calculées côté client.

**Fond de carte nautique.** `carte.js` charge les tuiles OpenStreetMap et les
assombrit par filtre CSS `invert(1) hue-rotate(185deg)`. C'est un
détournement, pas un design. Un fond dédié serait bien meilleur en plein
soleil sur un pont.

**Sémantique de `tp_matrix` à confirmer.** `hs_lt_0_4_family_tp_s = 3.0` est
traité comme un **minimum** de période. C'est cohérent avec le comportement du
moteur, mais la convention n'est écrite nulle part. À confirmer par l'auteur
des règles avant d'en faire un critère affiché dans une trace « pourquoi
NO-GO ».

### 6.3 Hors périmètre de cette branche, mais réels

Ces deux défauts sont dans la **vue actuelle**, pas dans Mobile_view.

**Le layout desktop est cassé.** `simple-view.js` remplace la grille trois
colonnes de `index.html` sur tous les viewports, pas seulement sous 1100 px.
À 1440 px on obtient une colonne mobile de 780 px centrée dans du vide, et
**la carte Leaflet disparaît du DOM**. Le CSS desktop de `index.html` n'est
jamais utilisé.

**Le titre du verdict est chevauché.** `SORTIE DÉCONSEILLÉE` passe sous la
jauge de qualité sur mobile et desktop, et « Moyenne » se casse en
« Moyenn / e » dans le cercle. C'est un débordement, pas un choix.

---

## 7. Reprendre le travail

```bash
git checkout -b feat/mobile-view main
git am mobile-view.patch

# vérifier avant de toucher quoi que ce soit
python -m pytest -q
node --test tests/js/*.test.mjs
ruff check .

# servir en local : les JSON doivent être un niveau au-dessus de mobile/
cd public && python -m http.server 8000
# puis http://localhost:8000/mobile/
```

Un dossier `public/` peuplé s'obtient en récupérant le site déployé
(`https://rbpower-hub.github.io/fable-collector/`) ou en lançant
`python collect.py`.

### Règles de reprise

1. Toute modification de `hour-verdict.js` ou `thresholds.js` **doit** être
   suivie du protocole de vérification de la section 3. Ce sont des règles de
   sécurité en mer, pas de la présentation.
2. Ne pas modifier `public/index.html`, `dashboard_modules.py` ni
   `dashboard_patch.py`. Mobile_view est isolée par construction : si elle
   déplaît, supprimer `public/mobile/` suffit à revenir en arrière.
3. Ne pas introduire de quatrième série de données sans revalider la palette.
4. Ne pas remplacer les trames du verdict par des aplats de couleur.
