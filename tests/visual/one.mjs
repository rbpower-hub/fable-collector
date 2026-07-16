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
await fs.writeFile(generatedPath, source);
await import(`${pathToFileURL(generatedPath).href}?case=${encodeURIComponent(requested)}&run=${Date.now()}`);
