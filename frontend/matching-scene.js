import { THREE, createStage, person, textSprite, arc, disposeTree } from './scene-engine.js';
import { cohortLayout, assignmentLoads } from './scene-layout.js';
import { replayStateAt, MatchingScene as CanvasScene } from './visualization.js';

export class MatchingScene {
  constructor(canvas) {
    this.canvas = canvas; this.data = null; this.index = 0; this.transition = 1;
    this.people = new Map(); this.advisors = new Map(); this.routes = [];
    this.stage = createStage(canvas, { interactive: true, animate: (time, dt) => this.animate(time, dt) });
    if (!this.stage) { this.fallback = new CanvasScene(canvas); return; }
    const grid = new THREE.GridHelper(17, 34, 0x2a6086, 0x163957); this.stage.root.add(grid);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 13), new THREE.MeshStandardMaterial({ color: 0x092846, roughness: .5, metalness: .35 }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -.02; this.stage.root.add(floor);
    this.profiles = new THREE.Group(); this.connections = new THREE.Group(); this.stage.root.add(this.profiles, this.connections);
    const a = textSprite('SINH VIÊN CHỜ PHÂN BỔ', '#a6ceff', .65); a.position.set(-4.7, .15, 5.1);
    const b = textSprite('GIẢNG VIÊN · HẠN MỨC', '#86f2da', .65); b.position.set(4, .15, 5.1); this.stage.root.add(a, b);
    this.click = event => {
      const rect = canvas.getBoundingClientRect();
      const pointer = new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
      const ray = new THREE.Raycaster(); ray.setFromCamera(pointer, this.stage.camera);
      const hit = ray.intersectObjects([...this.advisors.values()].map(value => value.tower), false)[0];
      if (!hit) return;
      const advisor = hit.object.userData.advisor;
      const detail = document.querySelector('#scene-selection');
      if (detail) detail.textContent = `${advisor.label || advisor.id}: ${this.loads?.[advisor.id] || 0}/${advisor.capacity} sinh viên. ${advisor.expertise || ''}`;
    };
    this.key = event => {
      if (!['ArrowLeft', 'ArrowRight', '+', '-', '='].includes(event.key)) return;
      event.preventDefault();
      if (event.key.startsWith('Arrow')) this.stage.root.rotation.y += event.key === 'ArrowLeft' ? -.1 : .1;
      else this.stage.camera.position.multiplyScalar(event.key === '-' ? 1.08 : .92);
      this.stage.draw();
    };
    canvas.addEventListener('click', this.click); canvas.addEventListener('keydown', this.key);
    this.stage.controls.saveState();
  }
  setData(data, index = 0) {
    if (this.fallback) { this.fallback.setData(data, index); return; }
    const changed = this.data?.students !== data.students || this.data?.advisors !== data.advisors;
    const sequential = !changed && index === this.index + 1;
    this.data = data; this.index = index;
    if (changed) this.buildProfiles();
    const state = replayStateAt(data.events, index);
    this.loads = assignmentLoads(state.assignments);
    const assignments = new Map(state.assignments.map(item => [item.student_id, item]));
    const slots = {};
    for (const [id, profile] of this.people) {
      const assignment = assignments.get(id), advisor = this.advisors.get(assignment?.advisor_id);
      profile.from = profile.mesh.position.clone(); profile.target = profile.origin.clone();
      if (advisor) {
        const slot = slots[assignment.advisor_id] || 0; slots[assignment.advisor_id] = slot + 1;
        profile.target.copy(advisor.position).add(new THREE.Vector3(Math.cos(slot * 2.4) * (.32 + Math.floor(slot / 8) * .17), .15, Math.sin(slot * 2.4) * (.32 + Math.floor(slot / 8) * .17)));
      }
      if (!sequential || id !== state.current?.student_id || this.stage.reduced.matches) profile.mesh.position.copy(profile.target);
      profile.mesh.traverse(object => { if (object.material?.color) object.material.color.setHex(assignment ? 0x5ce5bf : 0x65aaff); });
    }
    this.transition = sequential && !this.stage.reduced.matches ? 0 : 1;
    for (const [id, advisor] of this.advisors) {
      const load = this.loads[id] || 0, capacity = Number(advisor.data.capacity) || 1;
      const height = .08 + Math.min(load / capacity, 1) * 1.6;
      advisor.fill.scale.y = height; advisor.fill.position.y = height / 2 + .06;
      if (advisor.label && advisor.load === load) continue;
      advisor.load = load;
      if (advisor.label) { advisor.label.parent.remove(advisor.label); disposeTree(advisor.label); }
      advisor.label = textSprite(`${advisor.data.label || id} · ${load}/${capacity}`, load >= capacity ? '#ffd18a' : '#bcf7e7', data.advisors.length > 12 ? .22 : .4);
      advisor.label.position.copy(advisor.position).add(new THREE.Vector3(0, 2.35, 0)); this.profiles.add(advisor.label);
    }
    disposeTree(this.connections); this.connections.clear(); this.routes = [];
    // Only the active route is drawn; complete assignments remain visible as people at their advisor.
    const current = state.current;
    if (current?.advisor_id && this.people.has(current.student_id) && this.advisors.has(current.advisor_id)) {
      const profile = this.people.get(current.student_id), advisor = this.advisors.get(current.advisor_id);
      const curve = arc(profile.origin.toArray(), advisor.position.clone().add(new THREE.Vector3(0, 1.9, 0)).toArray(), 3);
      const color = current.invalid_proposal || current.fallback ? 0xffb654 : 0x7cf2df;
      this.connections.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 56, .025, 6, false), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .7 })));
      const pulse = new THREE.Mesh(new THREE.SphereGeometry(.11, 12, 8), new THREE.MeshBasicMaterial({ color })); this.connections.add(pulse); this.routes.push({ pulse, curve });
    }
    this.canvas.dataset.assigned = String(state.assignments.length);
    const progress = document.querySelector('#scene-progress');
    if (progress) progress.textContent = `${state.assignments.length}/${data.students.length} sinh viên đã tìm được người hướng dẫn`;
    this.draw();
  }
  buildProfiles() {
    disposeTree(this.profiles); this.profiles.clear(); this.people.clear(); this.advisors.clear();
    const layout = cohortLayout(this.data.students, this.data.advisors);
    const scale = this.data.students.length > 50 ? .34 : this.data.students.length > 12 ? .55 : .9;
    for (const student of layout.students) {
      const mesh = person(0x65aaff, scale); mesh.position.set(...student.position); this.profiles.add(mesh);
      this.people.set(student.id, { mesh, origin: mesh.position.clone(), target: mesh.position.clone(), from: mesh.position.clone() });
      if (layout.students.length <= 12) { const text = textSprite(student.label || student.id, '#c3dfff', .28); text.position.set(student.position[0], 1.25, student.position[2]); this.profiles.add(text); }
    }
    for (const advisor of layout.advisors) {
      const position = new THREE.Vector3(...advisor.position);
      const tower = new THREE.Mesh(new THREE.CylinderGeometry(.3, .36, 1.8, 20, 1, true), new THREE.MeshStandardMaterial({ color: 0x7de9da, transparent: true, opacity: .18, metalness: .4, roughness: .15, side: THREE.DoubleSide }));
      tower.position.copy(position).add(new THREE.Vector3(0, .75, 0)); tower.userData.advisor = advisor;
      const fill = new THREE.Mesh(new THREE.CylinderGeometry(.26, .29, 1, 20), new THREE.MeshStandardMaterial({ color: 0x29cca6, metalness: .45, roughness: .2 }));
      const group = new THREE.Group(); group.position.copy(position); group.add(fill);
      const guide = person(0xc4fff1, .65); guide.position.y = 1.7; group.add(guide);
      this.profiles.add(tower, group);
      this.advisors.set(advisor.id, { data: advisor, position, tower, fill, label: null });
    }
  }
  animate(time, dt) {
    this.transition = Math.min(1, this.transition + dt * 1.7);
    for (const profile of this.people.values()) {
      if (this.transition >= 1) continue;
      const t = 1 - Math.pow(1 - this.transition, 3);
      profile.mesh.position.lerpVectors(profile.from, profile.target, t);
      profile.mesh.position.y += Math.sin(t * Math.PI) * 1.2;
    }
    for (const { pulse, curve } of this.routes) pulse.position.copy(curve.getPoint((time * .5) % 1));
  }
  draw() { this.fallback ? this.fallback.draw() : this.stage?.draw(); }
  resetView() { if (this.fallback) this.fallback.resetView(); else { this.stage.root.rotation.set(0, 0, 0); this.stage.reset(); } }
  dispose() { this.canvas.removeEventListener('click', this.click); this.canvas.removeEventListener('keydown', this.key); this.stage?.dispose(); this.fallback?.dispose(); }
}
