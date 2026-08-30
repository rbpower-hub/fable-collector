import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

/* activity-board.js appelle refresh() au chargement : on neutralise fetch et
   setInterval pour n'exercer que les fonctions de formatage. */
const source = await readFile(new URL('../../public/activity-board.js', import.meta.url), 'utf8');
const sandbox = {
  window: {addEventListener() {}, dispatchEvent() {}, CustomEvent: class {}},
  document: {
    documentElement: {lang: 'fr'},
    addEventListener() {},
    getElementById: () => null,
    querySelector: () => null,
    createElement: () => ({setAttribute() {}, appendChild() {}, style: {}}),
    head: {appendChild() {}},
    body: {appendChild() {}},
  },
  localStorage: {getItem: () => 'fr'},
  fetch: () => Promise.reject(new Error('offline')),
  setInterval: () => 0,
  CustomEvent: class {constructor(type, init) {this.type = type; Object.assign(this, init);}},
  Intl,
};
sandbox.globalThis = sandbox;
vm.runInNewContext(source, sandbox);
const board = sandbox.window.FABLEActivityBoard;

test('les identifiants du pack deviennent lisibles', () => {
  assert.equal(board.humanize('micro_jig_5_12_g'), 'micro jig 5–12 g');
  assert.equal(board.humanize('petit_leurre_souple'), 'petit leurre souple');
  assert.equal(board.humanize('fond_tres_leger'), 'fond tres leger');
  assert.equal(board.humanize('crevette'), 'crevette');
});

test('un identifiant vide ou absent ne casse rien', () => {
  assert.equal(board.humanize(null), '');
  assert.equal(board.humanize(undefined), '');
});

test('les intervalles numeriques suivent la locale', () => {
  // 0.18 mm doit s'ecrire 0,18 mm en francais.
  assert.equal(board.pair([0.18, 0.25], ' mm'), '0,18–0,25 mm');
  assert.equal(board.pair([5, 25], ' g'), '5–25 g');
  assert.equal(board.pair(['#10', '#6']), '#10–#6');
  assert.equal(board.pair([4], ' m'), '');
  assert.equal(board.pair(null), '');
});

test('le filtre par port se pose et se retire', () => {
  /* Le board rendait toutes les recommandations du fichier : cliquer un port
     dans le tableau Expert ne changeait rien. Il ecoute desormais la selection. */
  assert.equal(typeof board.setPortFilter, 'function');
  // Sans payload charge, l'appel ne doit pas jeter : la vue est simplement
  // rendue au prochain rafraichissement.
  assert.doesNotThrow(() => board.setPortFilter('ras-fartass.json'));
  assert.doesNotThrow(() => board.setPortFilter(''));
});
