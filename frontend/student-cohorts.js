export function balancedQuotas(studentCount, advisorIds) {
  if (!advisorIds.length) return [];
  const base = Math.floor(studentCount / advisorIds.length);
  const remainder = studentCount % advisorIds.length;
  return advisorIds.map((id, index) => ({ id, quota: base + (index < remainder ? 1 : 0) }));
}
