# FABLE 3.2 — Vue Famille et Vue Expert

## Objectif

La Vue Famille répond d’abord à quatre questions :

1. peut-on sortir en famille ?
2. où aller ?
3. quand partir et revenir ?
4. que peut-on faire sur place ?

Les informations de contrôle, les flux bruts et le radar restent disponibles, mais ne sont plus placés au même niveau que la décision principale.

## Deux modes complémentaires

### Vue Famille

C’est le mode ouvert par défaut. Il utilise quatre onglets :

- **Aujourd’hui** : synthèse immédiate, fenêtres de navigation et causes NO-GO ;
- **Activités** : recommandations produites uniquement dans des fenêtres backend validées ;
- **Carte** : itinéraire et interaction cartographique à la demande ;
- **Détails** : radar des spots et données brutes repliées.

La préférence et le dernier onglet sont conservés dans le navigateur.

### Vue Expert

Elle conserve la présentation historique :

- carte visible immédiatement ;
- fenêtres, avertissements et radar simultanés ;
- accès complet aux informations techniques ;
- aucune donnée supprimée.

Le bouton du header permet de basculer entre les deux modes.

## Résumé de décision

Le résumé consomme les mêmes sorties que le reste du board :

```text
windows.json
recommendations.json
status.json
```

Lorsqu’une fenêtre côtière existe, il affiche :

- destination prioritaire ;
- horaire ;
- niveau Family standard ou prudent ;
- confiance ;
- nombre d’options disponibles ;
- date de mise à jour ;
- raccourcis vers la fenêtre, la carte et les activités.

Lorsqu’aucune fenêtre n’est validée, il reprend le diagnostic backend le plus utile. Il ne recalcule pas la météo dans le navigateur.

Les traversées `one_way_multi_day` sont comptées séparément comme fenêtres offshore et ne remplacent pas une sortie côtière Family GO.

## Responsive

Sur mobile :

- les outils du header défilent horizontalement ;
- la date de génération secondaire est masquée du header et reste visible dans la synthèse ;
- les onglets deviennent compacts ;
- les cartes sont empilées sans scroll interne ;
- la carte utilise une hauteur adaptée au viewport ;
- les activités sont affichées sur une seule colonne.

Sur ordinateur :

- l’onglet Aujourd’hui affiche Fenêtres et Avertissements sur deux colonnes ;
- la carte dispose de son propre espace large ;
- la Vue Expert conserve les trois colonnes historiques.

## Sécurité

La Vue Famille est une couche de présentation. Elle ne peut pas :

- créer une fenêtre ;
- transformer un NO-GO en GO ;
- modifier les seuils ;
- activer un abri non validé ;
- convertir une traversée offshore en sortie familiale.

La décision reste entièrement produite par le backend FABLE.
