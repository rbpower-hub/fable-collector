(function () {
  const pending = new Map();
  const nativeFetch = window.fetch.bind(window);

  async function request(url) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      try {
        const response = await nativeFetch(url, {cache: 'no-store', signal: controller.signal});
        if (!response.ok) {
          if (attempt === 0 && [408, 429, 500, 502, 503, 504].includes(response.status)) continue;
          return response;
        }
        const body = await response.text();
        JSON.parse(body);
        return new Response(body, {status: response.status, headers: response.headers});
      } catch (error) {
        if (attempt === 1) throw error;
      } finally {
        clearTimeout(timer);
      }
    }
  }

  async function fetchData(path) {
    const url = new URL(path, document.baseURI);
    const key = url.href;
    if (!pending.has(key)) {
      url.searchParams.set('_fable', String(Date.now()));
      const promise = request(url.href);
      pending.set(key, promise);
      const clear = () => { if (pending.get(key) === promise) pending.delete(key); };
      promise.then(() => setTimeout(clear, 2000), clear);
    }
    return (await pending.get(key)).clone();
  }

  window.FABLEData = {fetch: fetchData};
})();
