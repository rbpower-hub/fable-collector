import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import {freshnessState} from '../../public/js/navigation-verdicts.js';

const patch = readFileSync(new URL('../../fable/dashboard_patch.py', import.meta.url), 'utf8');
const helpers = patch.match(/_NEW_FRESHNESS_HELPERS = """([\s\S]*?)"""/)[1];
const now = new Date('2026-09-08T12:00:00Z');
const clock = class extends Date { static now() { return now.getTime(); } };
const window = {};
vm.runInNewContext(helpers, {window, Date:clock});

for (const age of [30, 100, 240, 361]) {
  test(`expert and family agree on freshness at ${age} minutes`, () => {
    const generated = now.getTime() - age * 60000;
    const status = {
      generated_at: new Date(generated).toISOString(), cadence_minutes:60,
      refresh_due_after: new Date(generated + 95 * 60000).toISOString(),
      stale_after: new Date(generated + 360 * 60000).toISOString(),
    };
    const expert = window.FABLEFreshness.freshnessState(status);
    const family = freshnessState(status, now);
    assert.equal(expert.fresh, family.fresh);
    assert.equal(expert.delayed, family.delayed);
    assert.equal(expert.fresh, age <= 360);
  });
}
