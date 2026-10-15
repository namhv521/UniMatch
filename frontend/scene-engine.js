import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
export { THREE };

export function person(color = 0x56b6ff, scale = 1) {
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ color, roughness: .24, metalness: .25 });
  const head = new THREE.Mesh(new THREE.SphereGeometry(.13, 16, 12), material);
  head.position.y = .55;
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(.115, .22, 4, 12), material);
  body.position.y = .25;
  group.add(head, body);
  group.scale.setScalar(scale);
  return group;
}

export function textSprite(text, color = '#dbf3ff', size = 1.4) {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 96;
  const ctx = canvas.getContext('2d');
  ctx.font = '600 30px Manrope, sans-serif'; ctx.textAlign = 'center';
  ctx.fillStyle = color; ctx.fillText(text, 256, 58, 500);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false }));
  sprite.scale.set(size * 3, size * .56, 1);
  return sprite;
}

export function arc(from, to, height = 1.8) {
  const start = new THREE.Vector3(...from), end = new THREE.Vector3(...to);
  const middle = start.clone().lerp(end, .5); middle.y += height;
  return new THREE.QuadraticBezierCurve3(start, middle, end);
}

export function disposeTree(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (!material) continue;
      materials.add(material);
      if (material.map) textures.add(material.map);
    }
  });
  geometries.forEach(value => value.dispose()); materials.forEach(value => value.dispose()); textures.forEach(value => value.dispose());
}

export function createStage(canvas, { interactive = false, home = false, animate = () => {} } = {}) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' }); }
  catch { canvas.dataset.renderer = 'unavailable'; return null; }
  canvas.dataset.renderer = 'webgl';
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  renderer.setClearColor(0x061d38, home ? 0 : 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, .1, 100);
  camera.position.set(home ? 11 : 12, home ? 8 : 12, home ? 16 : 17); camera.lookAt(0, 0, 0);
  scene.add(new THREE.HemisphereLight(0xc3eeff, 0x153f6a, 3));
  const light = new THREE.DirectionalLight(0xffffff, 5); light.position.set(4, 8, 5); scene.add(light);
  const rim = new THREE.PointLight(0x32bfff, 65); rim.position.set(-3, 3, -3); scene.add(rim);
  const root = new THREE.Group(); scene.add(root);
  const controls = interactive ? new OrbitControls(camera, canvas) : null;
  if (controls) { controls.enableDamping = true; controls.minDistance = 9; controls.maxDistance = 38; controls.maxPolarAngle = Math.PI * .48; controls.target.set(0, .2, 0); }
  let frame = 0, visible = true, paused = false, dead = false, previous = 0, elapsed = 0, manualMotion = false;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  function draw() { if (dead) return; controls?.update(); renderer.render(scene, camera); }
  function tick(time) {
    frame = 0;
    if (dead || !visible || document.hidden) return;
    const dt = previous ? Math.min((time - previous) / 1000, .05) : 0; previous = time;
    if (!paused && (!reduced.matches || manualMotion)) { elapsed += dt; animate(elapsed, dt); }
    draw();
    if (!paused && (!reduced.matches || manualMotion)) frame = requestAnimationFrame(tick);
  }
  function sync() { canvas.parentElement.dataset.motion = paused || !visible || document.hidden || (reduced.matches && !manualMotion) ? "paused" : "running"; cancelAnimationFrame(frame); previous = 0; draw(); if (visible && !document.hidden && !paused && (!reduced.matches || manualMotion)) frame = requestAnimationFrame(tick); }
  const resize = () => { const { width, height } = canvas.getBoundingClientRect(); if (!width || !height) return; renderer.setSize(width, height, false); camera.aspect = width / height; camera.fov = camera.aspect < 1.1 ? 54 : 38; camera.updateProjectionMatrix(); draw(); };
  const observer = new ResizeObserver(resize); observer.observe(canvas);
  const intersection = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; sync(); }); intersection.observe(canvas);
  const lost = event => { event.preventDefault(); cancelAnimationFrame(frame); canvas.dataset.renderer = 'context-lost'; };
  const restored = () => { canvas.dataset.renderer = 'webgl'; resize(); sync(); };
  controls?.addEventListener('change', () => renderer.render(scene, camera));
  canvas.addEventListener('webglcontextlost', lost); canvas.addEventListener('webglcontextrestored', restored);
  reduced.addEventListener('change', sync); document.addEventListener('visibilitychange', sync);
  resize(); sync();
  return { scene, root, camera, controls, renderer, draw, reduced,
    pause(value, manual = false) { paused = value; manualMotion = manual && !value; sync(); },
    reset() { controls?.reset(); draw(); },
    dispose() { dead = true; cancelAnimationFrame(frame); observer.disconnect(); intersection.disconnect(); controls?.dispose(); disposeTree(scene); renderer.dispose(); canvas.removeEventListener('webglcontextlost', lost); canvas.removeEventListener('webglcontextrestored', restored); reduced.removeEventListener('change', sync); document.removeEventListener('visibilitychange', sync); },
  };
}
