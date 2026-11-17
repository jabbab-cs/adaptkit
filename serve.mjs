// Tiny static file server for trying the AdaptKit examples (no dependencies).
// Serves the adaptkit folder, so the examples can load js/, policies/ and spec/.
//   node serve.mjs                          -> http://localhost:5173/examples/
//   PowerShell: $env:HOST='0.0.0.0'; node serve.mjs   (to test from a phone on the same Wi-Fi)

import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { extname, join, normalize, resolve, sep, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)));
const PORT = Number(process.env.PORT) || 5173;
const HOST = process.env.HOST || '127.0.0.1';
const DEFAULT_PAGE = '/examples/';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function send(res, status, text, headers = {}) {
  res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store', ...headers });
  res.end(text);
}

const server = createServer(async (req, res) => {
  if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Method not allowed', { Allow: 'GET, HEAD' });

  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  } catch {
    return send(res, 400, 'Bad request');
  }
  if (pathname === '/') return send(res, 302, 'Redirecting', { Location: DEFAULT_PAGE });
  if (pathname.includes('\0')) return send(res, 400, 'Bad request');

  // Path-traversal protection: resolve inside ROOT and refuse anything outside it,
  // plus hidden files/folders such as .claude or .git.
  const filePath = resolve(ROOT, '.' + normalize(pathname));
  if (filePath !== ROOT && !filePath.startsWith(ROOT + sep)) return send(res, 403, 'Forbidden');
  if (filePath.slice(ROOT.length).split(sep).some((part) => part.startsWith('.'))) return send(res, 403, 'Forbidden');

  let target = filePath;
  try {
    let info = await stat(target);
    if (info.isDirectory()) {
      if (!pathname.endsWith('/')) return send(res, 301, 'Moved', { Location: pathname + '/' });
      target = join(target, 'index.html');
      info = await stat(target);
    }
    const type = MIME[extname(target).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': info.size, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    if (req.method === 'HEAD') return res.end();
    createReadStream(target).on('error', () => res.destroy()).pipe(res);
  } catch {
    send(res, 404, 'Not found');
  }
});

server.listen(PORT, HOST, () => {
  const shown = HOST === '0.0.0.0' ? 'localhost' : HOST;
  console.log(`AdaptKit examples: http://${shown}:${PORT}${DEFAULT_PAGE}`);
  console.log(`Clinic demo with researcher panel: http://${shown}:${PORT}/examples/clinic/?researcher=1`);
  console.log(`Serving ${ROOT}`);
});
