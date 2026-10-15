// Bounded floor layouts keep the full cohort visible, including 154 x 38.
export function cohortLayout(students = [], advisors = []) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(students.length * .65)));
  const rows = Math.ceil(students.length / columns);
  const advisorColumns = Math.max(1, Math.ceil(Math.sqrt(advisors.length)));
  const advisorRows = Math.ceil(advisors.length / advisorColumns);
  return {
    students: students.map((student, i) => ({ ...student, position: [-6.7 + (i % columns) * 4.2 / columns, .28, (Math.floor(i / columns) - (rows - 1) / 2) * 7.4 / Math.max(rows, 1)] })),
    advisors: advisors.map((advisor, i) => ({ ...advisor, position: [1.7 + (i % advisorColumns) * 5.5 / advisorColumns, .2, (Math.floor(i / advisorColumns) - (advisorRows - 1) / 2) * 7.4 / Math.max(advisorRows, 1)] })),
  };
}

export function assignmentLoads(assignments = []) {
  const loads = {};
  for (const item of assignments) loads[item.advisor_id] = (loads[item.advisor_id] || 0) + 1;
  return loads;
}
