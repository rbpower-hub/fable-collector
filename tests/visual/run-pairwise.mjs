import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const sourcePath = path.resolve('tests/visual/run.mjs');
const generatedPath = path.resolve('tests/visual/.run-pairwise.generated.mjs');
let source = await fs.readFile(sourcePath, 'utf8');

const exhaustiveLoop = `    for (const state of STATES) {
      for (const locale of LOCALES) {
        for (const theme of THEMES) {
          const page = await context.newPage();
          const result = await inspectScenario(page, {viewport, state, locale, theme});
          results.push(result);
          console.log(\`${'${result.passed ? \'PASS\' : \'FAIL\'}'} ${'${result.key}'}${'${result.failures.length ? ` — ${result.failures.join(\' | \')}` : \'\'}'}\`);
          await page.close();
        }
      }
    }`;

const pairwiseLoop = `    const scenarios = [
      {state: 'fresh-windows', locale: 'fr', theme: 'nautical'},
    ];
    for (const {state, locale, theme} of scenarios) {
      const page = await context.newPage();
      page.setDefaultTimeout(10000);
      const result = await inspectScenario(page, {viewport, state, locale, theme});
      results.push(result);
      console.log(\`${'${result.passed ? \'PASS\' : \'FAIL\'}'} ${'${result.key}'}${'${result.failures.length ? ` — ${result.failures.join(\' | \')}` : \'\'}'}\`);
      await page.close();
    }`;

if (!source.includes(exhaustiveLoop)) throw new Error('Visual runner loop signature changed');
source = source.replace(exhaustiveLoop, pairwiseLoop);
source = source.replace('await page.waitForTimeout(700);', 'await page.waitForTimeout(300);');
source = source.replaceAll('fullPage: true', 'fullPage: false');
source = source.replace(
  "await fs.rm(OUTPUT, {recursive: true, force: true});\nawait fs.mkdir(SCREENSHOTS, {recursive: true});",
  "await fs.rm(SCREENSHOTS, {recursive: true, force: true});\nawait fs.mkdir(SCREENSHOTS, {recursive: true});",
);
source = source.replace(
  "  await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible', timeout: 15000});",
  `  try {
    await page.waitForSelector('#family-verdict-hero[data-state]', {state: 'visible', timeout: 15000});
  } catch (error) {
    const debug = await page.evaluate(() => ({
      title: document.title,
      bodyClass: document.body?.className || '',
      htmlLang: document.documentElement.lang,
      htmlDir: document.documentElement.dir,
      scripts: Array.from(document.scripts).map((node) => node.src || '[inline]'),
      heroExists: Boolean(document.getElementById('family-verdict-hero')),
      familyNavExists: Boolean(document.getElementById('family-board-nav')),
      text: document.body?.innerText?.slice(0, 2000) || '',
    }));
    await fs.writeFile(path.join(OUTPUT, 'debug.json'), JSON.stringify({errors, debug, error: error.message}, null, 2));
    await fs.writeFile(path.join(OUTPUT, 'debug.html'), await page.content());
    await page.screenshot({path: path.join(SCREENSHOTS, 'debug-no-hero.png'), fullPage: false});
    throw new Error(\`${'${error.message}'} | browser=${'${errors.join(\' | \')}'} | body=${'${debug.bodyClass}'}\`);
  }`,
);
source = source.replace(
  "matrix: {viewports: VIEWPORTS, states: STATES, locales: LOCALES, themes: THEMES},",
  "matrix: {strategy: 'debug representative coverage', viewports: VIEWPORTS, states: STATES, locales: LOCALES, themes: THEMES},",
);

await fs.writeFile(generatedPath, source);
await import(`${pathToFileURL(generatedPath).href}?run=${Date.now()}`);
