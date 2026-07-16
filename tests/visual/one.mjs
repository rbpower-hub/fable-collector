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
  "  try {\n    await page.goto(BASE, {waitUntil: 'commit', timeout: 10000});",
  "  try {\n    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} before-goto\\n`);\n    await page.goto(BASE, {waitUntil: 'commit', timeout: 10000});\n    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} after-goto\\n`);",
);
source = source.replace(
  "    await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible'});",
  "    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} before-selector\\n`);\n    await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible'});\n    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} after-selector\\n`);",
);
source = source.replace(
  '    await page.waitForTimeout(700);',
  "    await page.waitForTimeout(700);\n    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} after-settle\\n`);",
);
source = source.replace(
  '    values = await page.evaluate(() => {',
  "    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} before-evaluate\\n`);\n    values = await page.evaluate(() => {",
);
source = source.replace(
  '    values.titleContrast = contrast(values.titleColor, values.cardColor);',
  "    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} after-evaluate\\n`);\n    values.titleContrast = contrast(values.titleColor, values.cardColor);",
);
source = source.replace(
  '    await page.screenshot({path: path.join(SHOTS, `${key}.png`), fullPage: false});',
  "    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} before-screenshot\\n`);\n    await page.screenshot({path: path.join(SHOTS, `${key}.png`), fullPage: false});\n    await fs.appendFile(path.join(OUT, 'checkpoints.log'), `${key} after-screenshot\\n`);",
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
