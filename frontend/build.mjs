import { cp, mkdir, rm, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

process.chdir(fileURLToPath(new URL('.', import.meta.url)));

if (process.env.VERCEL === '1') {
  const backend = new URL(process.env.UNIMATCH_API_ORIGIN || '');
  const config = JSON.parse(await readFile('vercel.json', 'utf8'));
  if (backend.protocol !== 'https:' || backend.username || backend.password || backend.pathname !== '/' || backend.search || backend.hash ||
      !config.rewrites?.some(route => route.source === '/api/:path*' && route.destination === `${backend.origin}/api/:path*`)) {
    throw new Error('Set UNIMATCH_API_ORIGIN and align vercel.json with the verified production backend before deploying.');
  }
}

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await Promise.all(["login.html", "landing.html", "dashboard.html", "portal.css", "portal.js", "campus-scene.js", "index.html", "style.css", "app.js", "rebuild.html", "rebuild-app.js", "rebuild-style.css", "visualization.js", "student-cohorts.js", "home-scene.js", "scene-engine.js", "matching-scene.js", "scene-layout.js", "assets"].map((file) => cp(file, `dist/${file}`, { recursive: true })));
await mkdir("dist/vendor", { recursive: true });
await cp("node_modules/three/build", "dist/vendor/three", { recursive: true });
await cp("node_modules/three/LICENSE", "dist/vendor/three/LICENSE.txt");
await cp("node_modules/three/examples/jsm/controls/OrbitControls.js", "dist/vendor/OrbitControls.js");
console.log("Built frontend/dist with homepage scene and self-hosted fonts");
