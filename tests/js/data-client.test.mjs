import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../../public/data-client.js', import.meta.url), 'utf8');

function client(fetch, timeout = 12000) {
  const window = {fetch};
  vm.runInNewContext(source, {
    window, document: {baseURI: 'https://example.test/fable/'},
    URL, Response, AbortController,
    setTimeout(callback, delay) {
      const timer = setTimeout(callback, delay === 12000 ? timeout : delay);
      if (delay !== 12000) timer.unref();
      return timer;
    },
    clearTimeout,
  });
  return window.FABLEData;
}

test('concurrent board requests share transport but can read their own bodies', async () => {
  let calls = 0;
  const data = client(async (url) => {
    calls += 1;
    assert.match(url, /status.json\?_fable=\d+/);
    return new Response('{"generated_at":"original"}');
  });
  const responses = await Promise.all([data.fetch('status.json'), data.fetch('status.json')]);
  assert.deepEqual(await responses[0].json(), await responses[1].json());
  assert.equal(calls, 1);
});

test('transient HTTP error retries and returns recovered data', async () => {
  let calls = 0;
  const data = client(async () => ++calls === 1
    ? new Response('unavailable', {status: 503}) : new Response('{"ok":true}'));
  assert.deepEqual(await (await data.fetch('windows.json')).json(), {ok: true});
  assert.equal(calls, 2);
});

test('a failed connection does not poison future attempts', async () => {
  let offline = true;
  const data = client(async () => {
    if (offline) throw new TypeError('offline');
    return new Response('{"ok":true}');
  });
  await assert.rejects(data.fetch('status.json'), /offline/);
  offline = false;
  assert.equal((await data.fetch('status.json')).ok, true);
});

test('hanging response body is aborted and the second attempt can recover', async () => {
  let calls = 0;
  const data = client(async (_url, {signal}) => {
    calls += 1;
    if (calls > 1) return new Response('{"ok":true}');
    return {ok: true, text: () => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('timeout')), {once:true});
    })};
  }, 5);
  assert.equal((await data.fetch('status.json')).ok, true);
  assert.equal(calls, 2);
});

test('permanent errors are not retried', async () => {
  let calls = 0;
  const data = client(async () => { calls += 1; return new Response('', {status:404}); });
  assert.equal((await data.fetch('missing.json')).status, 404);
  assert.equal(calls, 1);
});

test('invalid JSON is retried before reaching consumers', async () => {
  let calls = 0;
  const data = client(async () => new Response(++calls === 1 ? '<html>' : '{}'));
  assert.deepEqual(await (await data.fetch('status.json')).json(), {});
  assert.equal(calls, 2);
});
