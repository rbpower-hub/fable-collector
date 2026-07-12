# Recommandations d’activités et de pêche

## Objectif

La couche de recommandations répond à la question **« Que faire sur l’eau ? »** après validation d’une fenêtre par le moteur Family GO.

Elle ne remplace pas le moteur de sécurité et ne crée jamais de fenêtre. Son entrée principale est `public/windows.json`.

## Ordre impératif des décisions

1. collecte et validation des données météo et marine ;
2. détection d’une fenêtre Family GO ;
3. chargement et validation du Knowledge Pack ;
4. vérification des seuils propres à chaque activité ;
5. classement des activités restantes ;
6. enrichissement avec saison, espèces, techniques, soleil et lune.

Si une destination ne possède aucune fenêtre Family GO, elle apparaît dans `no_go` et aucune activité n’est proposée.

## Sources de connaissance

### Source principale : `knowledge/`

Le Knowledge Pack versionné contient :

```text
knowledge/
  manifest.yaml
  fish/*.yaml
  techniques/*.yaml
  ports/*.yaml
  activities/*.yaml
```

Le moteur `fable.knowledge` vérifie les identifiants et les références croisées. Une espèce ou une technique inconnue bloque la génération et donc le déploiement.

Voir [KNOWLEDGE-PACK.md](KNOWLEDGE-PACK.md) pour le schéma détaillé.

### Compatibilité transitoire

La migration reste progressive :

- un port présent dans `knowledge/ports/` utilise le nouveau modèle structuré ;
- un port non encore migré utilise temporairement `fishing_profiles.yaml` ;
- si le dossier `knowledge/` est absent, `activity_profiles.yaml` et `fishing_profiles.yaml` restent les sources actives.

Cette compatibilité évite de supprimer les profils existants pendant la migration port par port.

## Calcul des métriques

Pour chaque fenêtre, le moteur extrait du JSON du spot :

- vent maximal ;
- rafale maximale ;
- Hs maximale ;
- Tp minimale ;
- visibilité minimale ;
- nombre d’heures échantillonnées.

Ces métriques représentent les conditions les plus défavorables de la fenêtre pour l’activité.

## Sélection des activités

Une activité est éliminée si :

- un profil de pêche requis est absent ;
- aucune technique structurée du port ne correspond à l’activité, lorsque ces références sont disponibles ;
- le vent, les rafales ou Hs dépassent le maximum ;
- Tp descend sous le minimum ;
- la visibilité descend sous le minimum.

Une fenêtre Family GO peut donc rester navigable alors qu’une activité particulière est refusée.

## Classement

Le score part de 100 et diminue à mesure que les conditions se rapprochent des limites de l’activité.

Des bonus limités peuvent être ajoutés :

- correspondance avec une période préférentielle du profil saisonnier ;
- signal lunaire secondaire lorsque `lunar_sensitive: true`.

Le score final est plafonné à 100. La lune ne peut jamais compenser un dépassement de seuil ou un NO-GO.

## Soleil et lune

Les données sont lues dans le bloc `daily` du JSON du spot :

- `sunrise` ;
- `sunset` ;
- `moonrise` ;
- `moonset` ;
- `moon_phase`.

Le moteur convertit `moon_phase` en libellé et en illumination approximative. Cette information ne constitue pas une preuve de présence ou d’activité des poissons.

## Sorties publiques

### `recommendations.json`

La version de sortie passe à `2` lorsque le Knowledge Pack est actif :

```json
{
  "generated_at": "2026-07-12T08:00:00+00:00",
  "version": 2,
  "safety_policy": "recommendations_only_inside_validated_family_go_windows",
  "knowledge_pack": {
    "version": 1,
    "status": "initial_tunable",
    "counts": {
      "fish": 6,
      "techniques": 4,
      "ports": 1,
      "activities": 5
    }
  },
  "recommendations": [],
  "no_go": []
}
```

Chaque recommandation peut maintenant contenir :

- `species` : libellés lisibles ;
- `species_ids` : identifiants stables ;
- `species_details` : informations structurées ;
- `techniques` et `technique_ids` ;
- `technique_details` ;
- habitats et futures zones du port.

Les anciens champs lisibles sont conservés pour ne pas casser le board actuel.

### `knowledge.json`

Catalogue de contrôle public contenant :

- version et statut du pack ;
- nombre d’espèces, techniques, ports et activités ;
- liste des identifiants chargés ;
- avertissements éventuels en mode non strict.

Le pipeline de production utilise le mode strict : une incohérence bloque la génération.

## Board

`public/activity-board.js` charge `recommendations.json` et ajoute au dashboard une carte **« Que faire sur l’eau ? »**.

Le composant est informatif. La source de vérité reste le JSON généré par le backend. Une erreur d’affichage ne modifie jamais la décision de sécurité.

## Ajustement progressif

Le Knowledge Pack doit être amélioré à partir de :

- journaux de sorties ;
- observations par spot, saison et profondeur ;
- résultats par technique et appât ;
- retours sur les faux positifs et faux négatifs ;
- validation des appellations locales ;
- réglementation tunisienne et restrictions locales.

Les futures zones GPS ne doivent être ajoutées qu’après validation terrain, cartographique et nautique.

## Limites

- Le moteur ne prédit pas une capture.
- Les espèces, profondeurs, techniques et appâts restent indicatifs.
- Les profils ne remplacent pas les cartes marines, avis locaux ou règles de pêche.
- Le calendrier lunaire est un facteur secondaire.
- Une recommandation ne vaut que pour la fenêtre et les données qui l’ont produite.
