import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";

const root = join(process.cwd(), "dist");
const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

createServer((request, response) => {
  const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
  const relative = normalize(decodeURIComponent(pathname)).replace(/^(\.\.(\/|\\|$))+/, "");
  let target = join(root, relative);
  if (!target.startsWith(root) || !existsSync(target) || statSync(target).isDirectory()) {
    target = join(root, "index.html");
  }
  response.setHeader("Content-Type", types[extname(target)] ?? "application/octet-stream");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'");
  response.setHeader("Cache-Control", target.endsWith("index.html") ? "no-cache" : "public, max-age=31536000, immutable");
  createReadStream(target).pipe(response);
}).listen(8080, "0.0.0.0");
