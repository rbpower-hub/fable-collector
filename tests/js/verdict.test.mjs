import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

import {computeVerdict} from '../../public/js/verdict.js';

const fixture = JSON.parse(await readFile(new URL('../fixtures/ui/verdict-cases.json', import.meta.url)));
const now = new Date(fixture.now);

function payload(windows, status = fixture.freshStatus) {
  return {windows, status, rules: fixture.rules, now};
}

test('STALE has priority over otherwise valid windows', () => {
  const verdict = computeVerdict(payload(fixture.goToday, fixture.staleStatus));
  assert.equal(verdict.state, 'STALE');
});

test('NO_DATA distinguishes an unavailable windows payload', () => {
  const verdict = computeVerdict(payload(null));
  assert.equal(verdict.state, 'NO_DATA');
});

test('GO_TODAY selects a coastal family window and excludes beta offshore', () => {
  const verdict = computeVerdict(payload(fixture.goToday));
  assert.equal(verdict.state, 'GO_TODAY');
  assert.equal(verdict.spot.dest_slug, 'sidi-bou-said.json');
});

test('GO_SOON reports the next future family window', () => {
  const verdict = computeVerdict(payload(fixture.goSoon));
  assert.equal(verdict.state, 'GO_SOON');
  assert.equal(verdict.spot.dest_slug, 'ghar-el-melh.json');
});

test('NO_GO keeps the nearest backend blocker', () => {
  const verdict = computeVerdict(payload(fixture.noGo));
  assert.equal(verdict.state, 'NO_GO');
  assert.equal(verdict.args.reason_fr, 'Vent trop fort');
});
