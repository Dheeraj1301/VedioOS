import { readdir } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { execFileSync } from 'node:child_process';

const roots = ['scripts', 'static', 'tests'];
const extensions = new Set(['.js', '.mjs']);
const files = [];

async function collect(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await collect(path);
    } else if (extensions.has(extname(entry.name))) {
      files.push(path);
    }
  }
}

for (const root of roots) {
  await collect(root);
}

files.sort();
for (const file of files) {
  execFileSync(process.execPath, ['--check', file], { stdio: 'inherit' });
}

console.log(`JavaScript syntax verified for ${files.length} files.`);
