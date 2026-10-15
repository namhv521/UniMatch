import test from "node:test";
import assert from "node:assert/strict";

import {
  clamp,
  createReplay,
  normalizeBenchmark,
  projectPoint,
  replayStateAt,
  preferredDataset,
  compatibleModels,
  MatchingScene,
} from "./visualization.js";

test("real data is preferred, with samples available when real data is unavailable", () => {
  const datasets = [{ id: "sample-2x2" }, { id: "real-train" }];
  assert.equal(preferredDataset(datasets, true), "real-train");
  assert.equal(preferredDataset(datasets, false), "sample-2x2");
  assert.equal(preferredDataset([], true), "sample-3x2");
});

test("checkpoint selection matches the backend highest-budget policy per algorithm and seed", () => {
  const model = { algorithm: "DQN", seed: 42, status: "unpromoted_research", supported_datasets: ["real-train"] };
  const models = [{ ...model, id: "small", completed_timesteps: 256 }, { ...model, id: "full", completed_timesteps: 2000000 },
    { ...model, id: "invalid", status: "invalid", completed_timesteps: 3000000 }];
  assert.deepEqual(compatibleModels(models, "real-train").map(item => item.id), ["full"]);
  assert.deepEqual(compatibleModels(models, "sample-2x2"), []);
});

test("projectPoint rotates, tilts and scales a 3D point", () => {
  const point = projectPoint({ x: 2, y: 1, z: 0 }, {
    yaw: Math.PI / 2,
    pitch: 0,
    zoom: 10,
    width: 200,
    height: 100,
  });

  assert.deepEqual(point, { x: 100, y: 60, depth: -2 });
});

test("normalizeBenchmark keeps summary evidence and compact report rows", () => {
  const output = normalizeBenchmark({
    summary: [{ algorithm: "Hungarian", seed_count: 5, metrics: { mean_compatibility: { mean: 0.1, std: 0 } } }],
    rows: [{ algorithm: "Hungarian", seed: 42, assignments: [1, 2], metrics: { mean_compatibility: 0.1, quota_violations: 0 } }],
  });
  assert.equal(output.summary[0].mean, 0.1);
  assert.deepEqual(output.rows[0], { algorithm: "Hungarian", seed: 42, mean: 0.1, quotaViolations: 0 });
});

test("replayStateAt derives assignments and loads from API events", () => {
  const events = [
    { student_id: "SV01", advisor_id: "GV-A", invalid_proposal: false, fallback: false, loads_after: { "GV-A": 1, "GV-B": 0 } },
    { student_id: "SV02", advisor_id: "GV-B", invalid_proposal: true, fallback: false, loads_after: { "GV-A": 1, "GV-B": 0 } },
    { student_id: "SV02", advisor_id: "GV-A", invalid_proposal: false, fallback: true, loads_after: { "GV-A": 2, "GV-B": 0 } },
  ];

  assert.deepEqual(replayStateAt(events, 1).assignments, [{ student_id: "SV01", advisor_id: "GV-A", fallback: false }]);
  assert.equal(replayStateAt(events, 2).invalid.length, 1);
  assert.deepEqual(replayStateAt(events, 3).loads, { "GV-A": 2, "GV-B": 0 });
});

test("replayStateAt maps indexed API loads to the current advisor id", () => {
  const state = replayStateAt([{ student_id: "SV01", advisor_id: "GV-A", advisor_index: 0, loads_after: [1, 0] }], 1);
  assert.equal(state.loads[0], 1);
  assert.equal(state.loads[1], 0);
  assert.equal(state.loads["GV-A"], 1);
});

test("createReplay clamps navigation and resets", () => {
  const replay = createReplay(3);
  replay.next();
  replay.next();
  replay.next();
  replay.next();
  assert.equal(replay.index, 3);
  replay.previous();
  assert.equal(replay.index, 2);
  replay.seek(-8);
  assert.equal(replay.index, 0);
  replay.seek(2);
  replay.reset();
  assert.equal(replay.index, 0);
  assert.equal(clamp(12, 0, 5), 5);
});

function inputSurface() {
  const handlers = new Map();
  const windowHandlers = new Map();
  return {
    handlers,
    windowHandlers,
    canvas: {
      ownerDocument: { defaultView: { addEventListener: (type, handler) => windowHandlers.set(type, handler) } },
      getContext: () => ({}),
      addEventListener: (type, handler) => handlers.set(type, handler),
      setPointerCapture: () => {},
    },
  };
}

test("canvas drag remains owned by the pointer that started it", () => {
  const { canvas, handlers } = inputSurface();
  const scene = new MatchingScene(canvas);
  scene.draw = () => {};
  handlers.get("pointerdown")({ pointerId: 1, clientX: 10, clientY: 10 });

  handlers.get("pointermove")({ pointerId: 2, clientX: 100, clientY: 100 });

  assert.equal(scene.yaw, -0.42);
  assert.equal(scene.pitch, 0.35);
});

test("interrupted canvas gestures stop dragging", () => {
  const { canvas, handlers, windowHandlers } = inputSurface();
  const scene = new MatchingScene(canvas);
  scene.draw = () => {};
  const interruptions = [
    () => handlers.get("pointercancel")?.({ pointerId: 1 }),
    () => handlers.get("lostpointercapture")?.({ pointerId: 1 }),
    () => windowHandlers.get("blur")?.(),
  ];

  for (const interrupt of interruptions) {
    handlers.get("pointerdown")({ pointerId: 1, clientX: 10, clientY: 10 });
    interrupt();
    handlers.get("pointermove")({ pointerId: 1, clientX: 100, clientY: 100 });
  }

  assert.equal(scene.yaw, -0.42);
  assert.equal(scene.pitch, 0.35);
});

import { cohortLayout, assignmentLoads } from './scene-layout.js';
test('full cohort layout stays inside a bounded 3D floor', () => {
  const students = Array.from({length:154}, (_,i) => ({id:`s${i}`}));
  const advisors = Array.from({length:38}, (_,i) => ({id:`a${i}`}));
  const layout = cohortLayout(students, advisors);
  assert.equal(layout.students.length,154); assert.equal(layout.advisors.length,38);
  const positions = new Set(layout.students.map(item => item.position.join(',')));
  assert.equal(positions.size,154);
  for (const item of [...layout.students,...layout.advisors]) assert.ok(item.position.every(value => Number.isFinite(value) && Math.abs(value) < 8));
});
test('replay seeking and invalid proposals never inflate 3D advisor loads', () => {
  const events = [{student_id:'s1',advisor_id:'a1'}, {student_id:'s2',advisor_id:'a1',invalid_proposal:true}, {student_id:'s1',advisor_id:'a2'}];
  assert.deepEqual(assignmentLoads(replayStateAt(events,3).assignments), {a2:1});
  assert.deepEqual(assignmentLoads(replayStateAt(events,1).assignments), {a1:1});
});
