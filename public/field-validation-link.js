/* Add a discreet field-validation entry point to the FABLE dashboard. */
(function () {
  function addLink() {
    if (document.getElementById('fieldValidationLink')) return;
    const link = document.createElement('a');
    link.id = 'fieldValidationLink';
    link.href = './field-log.html';
    link.className = 'field-validation-link';
    link.textContent = '📝 Journal';
    link.title = 'Journal de sortie et validation terrain';
    link.setAttribute('aria-label', 'Ouvrir le journal de sortie et de validation terrain');

    const tools = document.querySelector('.hdr-tools') || document.querySelector('.app-header');
    if (tools) tools.appendChild(link);

    if (!document.getElementById('field-validation-link-styles')) {
      const style = document.createElement('style');
      style.id = 'field-validation-link-styles';
      style.textContent = `
        .field-validation-link{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:6px 10px;border:1px solid var(--br);border-radius:999px;background:var(--pill-bg);color:var(--fg)!important;text-decoration:none;font-weight:850;font-size:.84rem;white-space:nowrap}
        .field-validation-link:hover{border-color:var(--accent);color:var(--accent)!important}
        body.kiosk-mode .field-validation-link{display:none}
        @media(max-width:640px){.field-validation-link{padding:7px 9px;font-size:0}.field-validation-link::before{content:'📝';font-size:1rem}}
      `;
      document.head.appendChild(style);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addLink, {once:true});
  else addLink();
})();
