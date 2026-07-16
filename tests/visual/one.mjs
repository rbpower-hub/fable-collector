import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const requested = process.env.FABLE_VISUAL_CASE;
if (!requested) throw new Error('FABLE_VISUAL_CASE is required');

const sourcePath = path.resolve('tests/visual/focused.mjs');
const generatedPath = path.resolve('tests/visual/.focused-one.generated.mjs');
let source = await fs.readFile(sourcePath, 'utf8');
const signature = '  for (const scenario of scenarios) {';
const replacement = `  for (const scenario of scenarios.filter((item) => \`${'${item.device}__${item.state}__${item.locale}__${item.theme}'}\` === ${JSON.stringify(requested)})) {`;
if (!source.includes(signature)) throw new Error('Focused visual runner signature changed');
source = source.replace(signature, replacement);
source = source.replace(
  "page.on('console', (message) => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });",
  "page.on('console', (message) => { if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) errors.push(`console: ${message.text()}`); });",
);
source = source.replace(
  'const result = await execute(browser, scenario);',
  `const timeoutKey = \`${'${devices[scenario.device].id}__${scenario.state}__${scenario.locale}__${scenario.theme}'}\`;
    const result = await Promise.race([
      execute(browser, scenario),
      new Promise((resolve) => setTimeout(() => resolve({
        key: timeoutKey,
        scenario,
        device: devices[scenario.device],
        values: null,
        failures: ['visual scenario exceeded 20 seconds'],
        passed: false,
      }), 20000)),
    ]);`,
);
source = source.replace(
  'if (failed.length) process.exitCode = 1;',
  'process.exit(failed.length ? 1 : 0);',
);
await fs.writeFile(generatedPath, source);
await import(`${pathToFileURL(generatedPath).href}?case=${encodeURIComponent(requested)}&run=${Date.now()}`);
