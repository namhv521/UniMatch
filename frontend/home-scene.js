import { THREE, createStage, person, arc } from './scene-engine.js';

// An illustrative academic network; never presented as a real allocation.
export function createHomeScene(canvas, control) {
  if (!canvas) return () => {};
  const pulses = [], profiles = [], rings = [];
  let stage, targetX = 0, targetY = 0, paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
  stage = createStage(canvas, { home: true, animate(time, dt) {
    stage.root.rotation.y += (targetX - stage.root.rotation.y) * Math.min(dt * 3, 1);
    stage.root.rotation.x += (targetY - stage.root.rotation.x) * Math.min(dt * 3, 1);
    profiles.forEach((profile, i) => { profile.position.y = profile.userData.base + Math.sin(time * .8 + i) * .14; });
    rings.forEach((ring, i) => { ring.rotation.z = time * (i % 2 ? -.06 : .045); });
    pulses.forEach(({ mesh, curve }, i) => mesh.position.copy(curve.getPoint((time * .18 + i * .17) % 1)));
  }});
  if (!stage) { control.hidden = true; canvas.parentElement.dataset.fallback = 'true'; return () => {}; }
  const { root } = stage;
  // Two orbital campuses made from physical rings, luminous paths, and human figures.
  const blue = new THREE.MeshStandardMaterial({ color: 0x258fff, metalness: .65, roughness: .2 });
  const silver = new THREE.MeshStandardMaterial({ color: 0xccefff, metalness: .6, roughness: .24 });
  for (let side = 0; side < 2; side++) {
    const center = side ? 2.8 : -2.8;
    const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(2.25, 2.4, .22, 64), side ? silver : blue);
    pedestal.position.set(center, -1.8, 0); root.add(pedestal);
    for (let j = 0; j < 2; j++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(2.5 + j * .36, .025, 8, 100), side ? silver : blue);
      ring.position.set(center, .7, 0); ring.rotation.set(Math.PI / 2.6 + j * .35, side ? .5 : -.5, 0); root.add(ring); rings.push(ring);
    }
    for (let i = 0; i < 7; i++) {
      const angle = i / 7 * Math.PI * 2;
      const profile = person(side ? 0xb9eaff : 0x378fff, i === 0 ? 2.25 : 1.45);
      profile.position.set(center + Math.cos(angle) * 1.6, -.7 + Math.sin(angle) * 1.2, Math.sin(angle) * 1.7);
      profile.userData.base = profile.position.y; root.add(profile); profiles.push(profile);
    }
  }
  for (let i = 0; i < 7; i++) {
    const from = profiles[i].position.clone(); from.y += .6;
    const to = profiles[i + 7].position.clone(); to.y += .6;
    const curve = arc(from.toArray(), to.toArray(), 1 + i * .13);
    const line = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, .013, 5, false), new THREE.MeshBasicMaterial({ color: i % 2 ? 0x74dfff : 0xffffff, transparent: true, opacity: .4 })); root.add(line);
    const pulse = new THREE.Mesh(new THREE.SphereGeometry(.075, 10, 8), new THREE.MeshBasicMaterial({ color: 0xc6f9ff })); root.add(pulse); pulses.push({ mesh: pulse, curve });
  }
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(.46, 1), new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: .4, roughness: .12 }));
  core.position.y = 1.2; root.add(core);
  const points = new Float32Array(150 * 3);
  for (let i = 0; i < 150; i++) { points[i * 3] = Math.sin(i * 23.7) * 10; points[i * 3 + 1] = Math.cos(i * 7.3) * 5; points[i * 3 + 2] = Math.sin(i * 11.4) * 7; }
  const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.BufferAttribute(points, 3));
  root.add(new THREE.Points(geometry, new THREE.PointsMaterial({ color: 0xa6dcff, size: .026, transparent: true, opacity: .5 })));
  const pointer = event => { const bounds = canvas.getBoundingClientRect(); targetX = (event.clientX - bounds.left - bounds.width / 2) / bounds.width * .45; targetY = (event.clientY - bounds.top - bounds.height / 2) / bounds.height * .15; };
  const leave = () => { targetX = 0; targetY = 0; };
  const sync = (manual = false) => { stage.pause(paused, manual); control?.setAttribute('aria-pressed', String(paused)); if (control) control.textContent = paused ? 'Bật chuyển động' : 'Dừng chuyển động'; };
  const toggle = () => { paused = !paused; sync(true); };
  canvas.addEventListener('pointermove', pointer); canvas.addEventListener('pointerleave', leave); control?.addEventListener('click', toggle);
  stage.draw(); sync();
  return () => { canvas.removeEventListener('pointermove', pointer); canvas.removeEventListener('pointerleave', leave); control?.removeEventListener('click', toggle); stage.dispose(); };
}
