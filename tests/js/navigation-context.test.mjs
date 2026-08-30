import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../../public/navigation-context.js', import.meta.url), 'utf8');

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.get(key) || null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

function loadContext({localStorage = new MemoryStorage(), sessionStorage = new MemoryStorage()} = {}) {
  const listeners = new Map();
  class CustomEvent {
    constructor(type, init = {}) { this.type = type; this.detail = init.detail; }
  }
  const window = {
    localStorage,
    sessionStorage,
    CustomEvent,
    addEventListener(type, handler) {
      const handlers = listeners.get(type) || [];
      handlers.push(handler);
      listeners.set(type, handlers);
    },
    dispatchEvent(event) {
      (listeners.get(event.type) || []).forEach((handler) => handler(event));
    },
  };
  vm.runInNewContext(source, {window, Intl, Date});
  return {context:window.FABLENavigationContext, localStorage, sessionStorage};
}

const selected = {
  slug:'ras-fartass.json',
  start:'2026-08-30T08:00:00+01:00',
  end:'2026-08-30T12:00:00+01:00',
  direction:'outbound',
};
const windows = {
  windows:[{
    dest_slug:'ras-fartass.json',
    windows:[{
      start:selected.start,
      end:selected.end,
      direction:selected.direction,
    }],
  }],
};

test('une fenêtre choisie fixe ensemble le jour et le port', () => {
  const {context} = loadContext();
  context.selectWindow(selected, {source:'test'});
  assert.deepEqual(JSON.parse(JSON.stringify(context.get())), {
    day:'2026-08-30', port:'ras-fartass.json', window:selected,
  });
});

test('un rafraîchissement conserve uniquement la fenêtre exacte encore publiée', () => {
  const {context} = loadContext();
  context.selectWindow(selected);
  context.reconcile(windows, {validDays:['2026-08-30'], defaultDay:'2026-08-30'});
  assert.equal(context.windowIdentity(context.get().window), context.windowIdentity(selected));

  const changed = structuredClone(windows);
  changed.windows[0].windows[0].end = '2026-08-30T11:00:00+01:00';
  context.reconcile(changed, {validDays:['2026-08-30'], defaultDay:'2026-08-30'});
  assert.equal(context.get().window, null);
  assert.equal(context.get().port, 'ras-fartass.json');
});

test('changer de jour ou de port invalide une fenêtre incompatible', () => {
  const {context} = loadContext();
  context.selectWindow(selected);
  context.setDay('2026-08-31');
  assert.equal(context.get().window, null);
  assert.equal(context.get().port, 'ras-fartass.json');

  context.selectWindow(selected);
  context.setPort('ghar-el-melh.json');
  assert.equal(context.get().window, null);
  assert.equal(context.get().port, 'ghar-el-melh.json');
});

test('la fenêtre survit à un rechargement de page puis est revalidée par windows.json', () => {
  const storage = {localStorage:new MemoryStorage(), sessionStorage:new MemoryStorage()};
  loadContext(storage).context.selectWindow(selected);
  const reloaded = loadContext(storage).context;
  assert.equal(reloaded.windowIdentity(reloaded.get().window), reloaded.windowIdentity(selected));
  reloaded.reconcile(windows, {validDays:['2026-08-30'], defaultDay:'2026-08-30'});
  assert.equal(reloaded.windowIdentity(reloaded.get().window), reloaded.windowIdentity(selected));
});

test('sans windows.json exploitable aucune fenêtre ne reste présentée comme valide', () => {
  const {context} = loadContext();
  context.selectWindow(selected);
  context.reconcile(null, {validDays:['2026-08-30'], defaultDay:'2026-08-30'});
  assert.equal(context.get().window, null);
  assert.equal(context.get().port, 'ras-fartass.json');
});

test('les directions implicites aller et retour restent distinctes', () => {
  const {context} = loadContext();
  const outbound = {...selected, direction:'outbound'};
  context.selectWindow(outbound);
  context.reconcile({
    windows:[{
      dest_slug:selected.slug,
      long_trip_one_way:{outbound:[{start:selected.start, end:selected.end}]},
    }],
  }, {validDays:['2026-08-30'], defaultDay:'2026-08-30'});
  assert.equal(context.windowIdentity(context.get().window), context.windowIdentity(outbound));
});

test('une fenêtre temporelle malformée ne devient jamais active', () => {
  const {context} = loadContext();
  context.setPort('ras-fartass.json');
  context.selectWindow({...selected, end:'date-invalide'});
  assert.equal(context.get().window, null);
  assert.equal(context.get().port, 'ras-fartass.json');
});
