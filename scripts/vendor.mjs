import { mkdir, copyFile } from 'node:fs/promises';
await mkdir('static/vendor', { recursive: true });
await copyFile('node_modules/hash-wasm/dist/sha256.umd.min.js', 'static/vendor/sha256.umd.min.js');
await copyFile('node_modules/hash-wasm/LICENSE', 'static/vendor/hash-wasm.LICENSE');
console.log('Vendored hash-wasm SHA-256 and its license.');
