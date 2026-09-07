import { build } from 'esbuild';
import { copyFile, mkdir } from 'node:fs/promises';
await mkdir('dist/assets', { recursive: true });
await build({ entryPoints: ['src/app.jsx'], bundle: true, minify: true, outfile: 'dist/assets/app.js',
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'eof', target: ['es2020'] });
await copyFile('index.html', 'dist/index.html');
