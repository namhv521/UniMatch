import { cp, mkdir, rm } from "node:fs/promises";

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await Promise.all(["index.html", "style.css", "app.js", "visualization.js", "student-cohorts.js", "home-scene.js", "scene-engine.js", "matching-scene.js", "scene-layout.js", "assets"].map((file) => cp(file, `dist/${file}`, { recursive: true })));
await mkdir("dist/vendor", { recursive: true });
await cp("node_modules/three/build", "dist/vendor/three", { recursive: true });
await cp("node_modules/three/LICENSE", "dist/vendor/three/LICENSE.txt");
await cp("node_modules/three/examples/jsm/controls/OrbitControls.js", "dist/vendor/OrbitControls.js");
console.log("Built frontend/dist with homepage scene and self-hosted fonts");
