function searchable(value = "") {
  return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("vi");
}

export function balancedQuotas(studentCount, advisorIds) {
  if (!advisorIds.length) return [];
  const base = Math.floor(studentCount / advisorIds.length);
  const remainder = studentCount % advisorIds.length;
  return advisorIds.map((id, index) => ({ id, quota: base + (index < remainder ? 1 : 0) }));
}

export function advisorMatches(advisor, query) {
  const term = searchable(query.trim());
  return !term || searchable(`${advisor.name} ${advisor.primary_field || ""}`).includes(term);
}

export function advisorQuery(advisorIds) {
  const params = new URLSearchParams();
  advisorIds.forEach((id) => params.append("advisor_ids", id));
  return params.toString();
}

export function canAllocate({ file, studentCount, selectedCount, busy }) {
  return Boolean(file && studentCount > 0 && selectedCount > 0 && !busy);
}
