import test from "node:test";
import assert from "node:assert/strict";

import {
  clamp,
  createReplay,
  normalizeBenchmark,
  projectPoint,
  replayStateAt,
} from "./visualization.js";

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
