import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

process.chdir(fileURLToPath(new URL('.', import.meta.url)));

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
const files = [
  "index.html", "landing.html", "login.html", "dashboard.html", "rebuild.html",
  "portal.css", "portal.js", "campus-scene.js", "nested-research.js",
  "rebuild-app.js", "student-cohorts.js", "allocation-replay.js", "thesis.html", "thesis.js", "assets",
];
await Promise.all(files.map((file) => cp(file, `dist/${file}`, { recursive: true })));
await mkdir("dist/vendor", { recursive: true });
await cp("node_modules/three/build", "dist/vendor/three", { recursive: true });
await cp("node_modules/three/LICENSE", "dist/vendor/three/LICENSE.txt");
console.log("Built frontend/dist with portal pages, 3D scene and self-hosted fonts");
