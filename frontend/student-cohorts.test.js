import test from "node:test";
import assert from "node:assert/strict";

import { advisorMatches, advisorQuery, balancedQuotas, canAllocate } from "./student-cohorts.js";

test("balancedQuotas gives 38 students to four advisors as 10, 10, 9, 9", () => {
  assert.deepEqual(
    balancedQuotas(38, ["gv-1", "gv-2", "gv-3", "gv-4"]),
    [
      { id: "gv-1", quota: 10 },
      { id: "gv-2", quota: 10 },
      { id: "gv-3", quota: 9 },
      { id: "gv-4", quota: 9 },
    ],
  );
});

test("advisorMatches finds an advisor without requiring accents or matching case", () => {
  const advisor = { name: "TS PHẠM MINH HOÀN", primary_field: "Học máy" };

  assert.equal(advisorMatches(advisor, "pham minh hoan"), true);
  assert.equal(advisorMatches(advisor, "HOC MAY"), true);
  assert.equal(advisorMatches(advisor, "an toan thong tin"), false);
});

test("advisorQuery repeats only checked advisor ids", () => {
  assert.equal(
    advisorQuery(["cnhem7mt88q70afoezx19kwk", "gv 2"]),
    "advisor_ids=cnhem7mt88q70afoezx19kwk&advisor_ids=gv+2",
  );
});

test("canAllocate requires a valid preview, a file and at least one advisor", () => {
  const ready = { file: { name: "students.xlsx" }, studentCount: 38, selectedCount: 4, busy: false };

  assert.equal(canAllocate(ready), true);
  assert.equal(canAllocate({ ...ready, file: null }), false);
  assert.equal(canAllocate({ ...ready, studentCount: 0 }), false);
  assert.equal(canAllocate({ ...ready, selectedCount: 0 }), false);
  assert.equal(canAllocate({ ...ready, busy: true }), false);
});
