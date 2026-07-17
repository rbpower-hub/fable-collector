# Incident de production — 17 juillet 2026

## Symptôme

Le tableau de bord FABLE ne s’affichait plus après l’activation du module expérimental `off-hours-refinements.js`.

## Cause

Le module observait l’ensemble du document avec un `MutationObserver` et réécrivait des éléments du DOM pendant ses propres callbacks. Cette boucle de mutations pouvait monopoliser le navigateur et empêcher le tableau de bord de terminer son rendu.

## Correctif

- suppression définitive du module récursif du dépôt et du bundle publié ;
- conservation de `day-selection.js`, qui assure le filtrage stable par journée ;
- suppression des tests liés au module retiré ;
- publication d’un marqueur `production-recovery.json` afin de confirmer la version restaurée.

Les raffinements hors horaires seront réintroduits ultérieurement sans observation globale du DOM.
