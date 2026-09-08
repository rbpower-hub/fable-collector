import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../../public/mobile/js/data.js', import.meta.url), 'utf8');
let sequence = 0;
async function dataModule(fetch) {
  globalThis.window = {FABLEData: {fetch}};
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}#${++sequence}`);
}

test('mobile can recover a rejected spot request without reloading the page', async () => {
  let online = false;
  const data = await dataModule(async () => {
    if (!online) throw new Error('offline');
    return new Response('{"version":2}');
  });
  await assert.rejects(data.loadSpot('port.json'), /offline/);
  online = true;
  assert.equal((await data.loadSpot('port.json')).version, 2);
});

test('a refresh drops successful cached payloads and loads the next generation', async () => {
  let version = 1;
  const data = await dataModule(async () => new Response(JSON.stringify({version})));
  assert.equal((await data.loadSpot('port.json')).version, 1);
  version = 2;
  data.clearCache();
  assert.equal((await data.loadSpot('port.json')).version, 2);
});

test('optional missing assessment is retried on the next request', async () => {
  let available = false;
  const data = await dataModule(async () => available
    ? new Response('{"hours":[1]}') : new Response('', {status:404}));
  assert.equal(await data.loadHourlyAssessment({path:'hours.json'}), null);
  available = true;
  assert.deepEqual(await data.loadHourlyAssessment({path:'hours.json'}), {hours:[1]});
});
