export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export function preferredDataset(datasets, dataLoaded) {
  return (dataLoaded && datasets.find(item => item.id === "real-train")?.id)
    || datasets.find(item => item.id.startsWith("sample-"))?.id || "sample-3x2";
}

export function compatibleModels(models, datasetId) {
  const selected = new Map();
  for (const model of models) {
    if (model.available === false || model.status === "invalid" || model.smoke
      || !model.supported_datasets?.includes(datasetId)) continue;
    const key = `${model.algorithm}:${model.seed}:${model.research === true}`;
    const previous = selected.get(key);
    if (!previous || (model.completed_timesteps || 0) > (previous.completed_timesteps || 0)
      || (model.completed_timesteps === previous.completed_timesteps && model.id < previous.id)) selected.set(key, model);
  }
  return [...selected.values()];
}

export function normalizeBenchmark(report = {}) {
  return {
    summary: (report.summary || []).map((item) => ({
      algorithm: item.algorithm,
      seedCount: item.seed_count,
      mean: item.metrics?.mean_compatibility?.mean,
      std: item.metrics?.mean_compatibility?.std,
      quotaViolations: item.metrics?.quota_violations?.mean,
      invalidProposals: item.metrics?.invalid_proposals?.mean,
    })),
    rows: (report.rows || []).map((item) => ({
      algorithm: item.algorithm,
      seed: item.seed,
      mean: item.metrics?.mean_compatibility,
      quotaViolations: item.metrics?.quota_violations,
    })),
  };
}

export function projectPoint(point, view) {
  const cosYaw = Math.cos(view.yaw);
  const sinYaw = Math.sin(view.yaw);
  const rotatedX = point.x * cosYaw + point.z * sinYaw;
  const rotatedZ = -point.x * sinYaw + point.z * cosYaw;
  const cosPitch = Math.cos(view.pitch);
  const sinPitch = Math.sin(view.pitch);
  const screenY = point.y * cosPitch - rotatedZ * sinPitch;
  return {
    x: view.width / 2 + rotatedX * view.zoom,
    y: view.height / 2 + screenY * view.zoom,
    depth: rotatedZ,
  };
}

export function replayStateAt(events = [], index = 0) {
  const applied = events.slice(0, clamp(index, 0, events.length));
  const assignments = [];
  const invalid = [];
  let loads = {};
  for (const event of applied) {
    if (event.invalid_proposal) invalid.push(event);
    else if (event.student_id && event.advisor_id) {
      const previous = assignments.findIndex((item) => item.student_id === event.student_id);
      if (previous >= 0) assignments.splice(previous, 1);
      assignments.push({
        student_id: event.student_id,
        advisor_id: event.advisor_id,
        fallback: Boolean(event.fallback),
      });
    }
    if (event.loads_after) {
      loads = { ...event.loads_after };
      if (event.advisor_id && Number.isInteger(event.advisor_index)) {
        loads[event.advisor_id] = event.loads_after[event.advisor_index];
      }
    }
  }
  return { assignments, invalid, loads, current: applied.at(-1) ?? null };
}

export function createReplay(length = 0) {
  let index = 0;
  return {
    get index() { return index; },
    next() { index = clamp(index + 1, 0, length); return index; },
    previous() { index = clamp(index - 1, 0, length); return index; },
    seek(value) { index = clamp(Number(value) || 0, 0, length); return index; },
    reset() { index = 0; return index; },
  };
}

const color = {
  student: "#0866f5",
  advisor: "#0aa89b",
  edge: "#0aa89b",
  candidate: "#7890b0",
  invalid: "#d97706",
  grid: "#d9e4f2",
  text: "#08205f",
};

function circle(context, point, radius, fill) {
  const gradient = context.createRadialGradient(point.x - radius / 3, point.y - radius / 3, 2, point.x, point.y, radius);
  gradient.addColorStop(0, "#ffffff");
  gradient.addColorStop(0.18, fill);
  gradient.addColorStop(1, "#063a9d");
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(point.x, point.y, radius, 0, Math.PI * 2);
  context.fill();
}

function label(context, text, x, y, align = "left") {
  context.font = "600 12px system-ui, sans-serif";
  context.textAlign = align;
  context.fillStyle = color.text;
  context.fillText(text, x, y);
}

export class MatchingScene {
  constructor(canvas) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.yaw = -0.42;
    this.pitch = 0.35;
    this.zoom = 54;
    this.data = { students: [], advisors: [], events: [] };
    this.index = 0;
    this.drag = null;
    this.listeners = [];
    this.bindInput();
  }

  listen(target, type, handler, options) {
    if (!target) return;
    target.addEventListener(type, handler, options);
    this.listeners.push([target, type, handler, options]);
  }

  dispose() {
    for (const [target, type, handler, options] of this.listeners) target.removeEventListener?.(type, handler, options);
    this.listeners = [];
    this.drag = null;
  }

  bindInput() {
    this.listen(this.canvas, "pointerdown", (event) => {
      if (this.drag) return;
      this.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      this.canvas.setPointerCapture(event.pointerId);
    });
    this.listen(this.canvas, "pointermove", (event) => {
      if (!this.drag || event.pointerId !== this.drag.pointerId) return;
      this.yaw += (event.clientX - this.drag.x) * 0.008;
      this.pitch = clamp(this.pitch + (event.clientY - this.drag.y) * 0.005, -0.25, 0.85);
      this.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      this.draw();
    });
    const endDrag = (event = {}) => {
      if (this.drag && (event.pointerId == null || event.pointerId === this.drag.pointerId)) this.drag = null;
    };
    this.listen(this.canvas, "pointerup", endDrag);
    this.listen(this.canvas, "pointercancel", endDrag);
    this.listen(this.canvas, "lostpointercapture", endDrag);
    this.listen(this.canvas.ownerDocument?.defaultView, "blur", endDrag);
    this.listen(this.canvas, "wheel", (event) => {
      event.preventDefault();
      this.zoom = clamp(this.zoom - event.deltaY * 0.08, 28, 100);
      this.draw();
    }, { passive: false });
    this.listen(this.canvas, "keydown", (event) => {
      const moves = { ArrowLeft: -0.08, ArrowRight: 0.08 };
      if (moves[event.key]) {
        this.yaw += moves[event.key];
        this.draw();
      }
      if (event.key === "+" || event.key === "=") this.zoom = clamp(this.zoom + 5, 28, 100);
      if (event.key === "-") this.zoom = clamp(this.zoom - 5, 28, 100);
      this.draw();
    });
  }

  setData(data, index = 0) {
    this.data = data;
    this.index = index;
    this.draw();
  }

  resetView() {
    this.yaw = -0.42;
    this.pitch = 0.35;
    this.zoom = 54;
    this.draw();
  }

  point(value) {
    return projectPoint(value, {
      yaw: this.yaw,
      pitch: this.pitch,
      zoom: this.zoom,
      width: this.canvas.clientWidth,
      height: this.canvas.clientHeight,
    });
  }

  drawLine(from, to, kind = "candidate") {
    const context = this.context;
    context.strokeStyle = color[kind] ?? color.candidate;
    context.lineWidth = kind === "edge" ? 3 : 2;
    context.setLineDash(kind === "edge" ? [] : [7, 6]);
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.setLineDash([]);
  }

  draw() {
    const canvas = this.canvas;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(320, canvas.clientWidth);
    const height = Math.max(260, canvas.clientHeight);
    if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
      canvas.width = width * ratio;
      canvas.height = height * ratio;
    }
    const context = this.context;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    context.strokeStyle = color.grid;
    context.lineWidth = 1;
    for (let i = -5; i <= 5; i += 1) {
      const a = this.point({ x: i, y: 1.8, z: -3 });
      const b = this.point({ x: i, y: 1.8, z: 3 });
      const c = this.point({ x: -5, y: 1.8, z: i * 0.6 });
      const d = this.point({ x: 5, y: 1.8, z: i * 0.6 });
      context.beginPath(); context.moveTo(a.x, a.y); context.lineTo(b.x, b.y); context.stroke();
      context.beginPath(); context.moveTo(c.x, c.y); context.lineTo(d.x, d.y); context.stroke();
    }

    const studentPoints = new Map();
    const advisorPoints = new Map();
    this.data.students.forEach((student, index) => {
      studentPoints.set(student.id, this.point({ x: -3.2, y: index - (this.data.students.length - 1) / 2, z: -0.4 }));
    });
    this.data.advisors.forEach((advisor, index) => {
      advisorPoints.set(advisor.id, this.point({ x: 3.1, y: index * 1.7 - (this.data.advisors.length - 1) * 0.85, z: 0.4 }));
    });

    const state = replayStateAt(this.data.events, this.index);
    const assignedStudents = new Set(state.assignments.map((item) => item.student_id));
    state.assignments.forEach((assignment) => {
      const from = studentPoints.get(assignment.student_id);
      const to = advisorPoints.get(assignment.advisor_id);
      if (from && to) this.drawLine(from, to, assignment.fallback ? "invalid" : "edge");
    });
    const current = state.current;
    if (current?.student_id && current?.advisor_id && current.invalid_proposal) {
      const from = studentPoints.get(current.student_id);
      const to = advisorPoints.get(current.advisor_id);
      if (from && to) this.drawLine(from, to, "invalid");
    }
    const nextStudent = this.data.students.find((student) => !assignedStudents.has(student.id));
    if (nextStudent && this.data.advisors[0]) {
      this.drawLine(studentPoints.get(nextStudent.id), advisorPoints.get(this.data.advisors[0].id), "candidate");
    }

    this.data.students.forEach((student) => {
      const point = studentPoints.get(student.id);
      circle(context, point, 17, color.student);
      label(context, student.label || student.id, point.x - 24, point.y + 4, "right");
    });
    this.data.advisors.forEach((advisor) => {
      const point = advisorPoints.get(advisor.id);
      const load = state.loads[advisor.id] ?? 0;
      context.fillStyle = color.advisor;
      context.fillRect(point.x - 15, point.y - 25, 30, 48);
      context.beginPath(); context.ellipse(point.x, point.y - 25, 15, 7, 0, 0, Math.PI * 2); context.fill();
      context.beginPath(); context.ellipse(point.x, point.y + 23, 15, 7, 0, 0, Math.PI * 2); context.fill();
      label(context, advisor.label || advisor.id, point.x + 23, point.y + 4);
      label(context, `${load}/${advisor.capacity}`, point.x, point.y - 39, "center");
    });
  }
}
