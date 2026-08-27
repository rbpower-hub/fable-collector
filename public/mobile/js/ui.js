/** Fabriques DOM partagees. Aucun emoji : les icones sont des SVG en trait. */

const SVG_NS = 'http://www.w3.org/2000/svg';

export function h(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, String(value));
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

const PATHS = {
  compass: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M15.5 8.5 13.8 13.8 8.5 15.5l1.7-5.3z'],
  chart: ['M3 16.5 8 10l4 4 3.5-5.5L21 14', 'M3 20h18'],
  map: ['M9 4 3 6.5v13L9 17l6 3 6-2.5v-13L15 7z', 'M9 4v13', 'M15 7v13'],
  warning: ['M12 9v5', 'M12 17.5v.5', 'M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'],
  check: ['M4.5 12.5 9.5 17.5 19.5 7'],
  block: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M6.5 6.5l11 11'],
  clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3 2'],
  back: ['M15 5l-7 7 7 7'],
  chevronDown: ['M6 9l6 6 6-6'],
  chevronRight: ['M9 5l7 7-7 7'],
};

export function icon(name, { size = 20, stroke = 'currentColor', width = 1.9 } = {}) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.style.stroke = stroke;
  svg.style.strokeWidth = String(width);
  svg.style.strokeLinecap = 'round';
  svg.style.strokeLinejoin = 'round';
  svg.style.flex = '0 0 auto';
  for (const d of PATHS[name] ?? []) {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', d);
    svg.append(path);
  }
  return svg;
}

export const STATE_LABEL = { go: 'GO', prudent: 'PRUDENCE', nogo: 'NO-GO' };
export const STATE_ICON = { go: 'check', prudent: 'warning', nogo: 'block' };
export const STATE_VAR = { go: 'var(--go)', prudent: 'var(--prudent)', nogo: 'var(--nogo)' };

export function stateBadge(state) {
  return h('span', { class: `fb-badge fb-badge--${state}` }, [
    icon(STATE_ICON[state], { size: 13, width: 2.2 }),
    h('span', { text: STATE_LABEL[state] }),
  ]);
}

export function card(title, note, children) {
  const head = h('div', { class: 'fb-card__head' }, [
    h('span', { class: 'fb-card__title', text: title }),
    note ? h('span', { class: 'fb-card__note', text: note }) : null,
  ]);
  return h('div', { class: 'fb-card' }, [title ? head : null, ...[].concat(children)]);
}

export function metric(label, value, unit) {
  return h('div', { class: 'fb-metric' }, [
    h('span', { class: 'fb-metric__label', text: label }),
    h('span', { class: 'fb-metric__value' }, [
      h('b', { text: value }),
      unit ? h('span', { text: ` ${unit}` }) : null,
    ]),
  ]);
}

export function tile(label, value, note) {
  return h('div', { class: 'fb-tile' }, [
    h('span', { class: 'fb-tile__label', text: label }),
    h('span', { class: 'fb-tile__value', text: value }),
    note ? h('span', { class: 'fb-tile__note', text: note }) : null,
  ]);
}

export function checkRow({ label, value, ratio, exceeded }) {
  const fill = h('div', { class: 'fb-check__fill' });
  fill.style.width = `${Math.min(100, Math.max(0, ratio * 100)).toFixed(0)}%`;
  fill.style.background = exceeded ? 'var(--nogo)' : 'var(--go)';
  return h('div', {}, [
    h('div', { class: 'fb-check__head' }, [
      h('span', { class: 'fb-check__label', text: label }),
      h('span', { class: 'fb-check__value', text: value }),
      h('span', {
        class: `fb-check__tag fb-check__tag--${exceeded ? 'ko' : 'ok'}`,
        text: exceeded ? 'DÉPASSÉ' : 'OK',
      }),
    ]),
    h('div', { class: 'fb-check__track' }, [fill]),
  ]);
}
