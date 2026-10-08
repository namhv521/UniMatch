import { cp, mkdir, rm } from "node:fs/promises";

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await Promise.all(["index.html", "style.css", "app.js", "visualization.js"].map((file) => cp(file, `dist/${file}`)));
console.log("Built frontend/dist (4 files)");
