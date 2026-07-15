/* FABLE installability and theme-color synchronization — no service worker. */
(function () {
  const THEME_COLORS = {dark: '#0b1020', nautical: '#0077b6'};

  function applyThemeColor() {
    const theme = document.documentElement.getAttribute('data-theme') || 'nautical';
    const color = THEME_COLORS[theme] || THEME_COLORS.nautical;
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = color;
  }

  function start() {
    applyThemeColor();
    const observer = new MutationObserver(applyThemeColor);
    observer.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
