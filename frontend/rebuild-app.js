import { confidenceLabel, requireSession } from "./portal.js";
let confidenceThreshold = 70;
import { balancedQuotas } from "./student-cohorts.js";
import { mountReplay } from "./allocation-replay.js";

const $ = (id) => document.getElementById(id);
const escape = (value = "") => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const labels = { ppo: "PPO", dqn: "DQN", hungarian: "Hungarian", greedy: "Greedy", random: "Random" };
const state = { bootstrap: null, base: "", selected: new Set(), cohort: null, file: null, comparison: null, recommendation: null, algorithm: "ppo", busy: false, revision: 0, quotaVerified: false };
let stop = () => {};
let previewedWorkbook;

function nameStudent(id) { return state.cohort?.students?.find((s) => s.student_id === id)?.student_name || id; }
function nameAdvisor(id) { return state.bootstrap?.advisors?.find((a) => a.advisor_id === id)?.advisor_name || id; }
function score(value) { return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "Chưa biết"; }
function number(value, digits = 2) { return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("vi-VN", { maximumFractionDigits: digits }) : "—"; }
function warningText(value) { return typeof value === "string" ? value : value?.message || JSON.stringify(value); }
function warnings(values = []) { return values.length ? `<ul class="help">${values.map((w) => `<li>${escape(warningText(w))}</li>`).join("")}</ul>` : ""; }
function selectedIds() { return [...state.selected].sort(); }
function message(text, kind = "info") { $("message").hidden = !text; $("message").className = `status-banner ${kind}`; $("message").textContent = text; }
function errorMessage(error) { return error.name === "AbortError" ? "Dịch vụ phản hồi quá lâu. Kiểm tra tiến trình local rồi thử lại." : error.message || "Không thể hoàn tất yêu cầu. Hãy thử lại."; }

function renderXaiExplanation(exp) {
  if (!exp || typeof exp !== "object") return `<p class="help">Không có dữ liệu phân rã chi tiết.</p>`;
  const entries = [];
  if (typeof exp.score === "number") entries.push(["Điểm tổng hợp E4", exp.score.toFixed(4)]);
  if (exp.components && typeof exp.components === "object") {
    for (const [k, v] of Object.entries(exp.components)) {
      if (typeof v === "number") entries.push([`Thành phần ${k}`, v.toFixed(4)]);
    }
  }
  for (const [k, v] of Object.entries(exp)) {
    if (["score", "components", "matched_terms", "matched_tags", "shared_concepts"].includes(k)) continue;
    if (typeof v === "number") entries.push([k.replaceAll("_", " "), number(v, 4)]);
    else if (typeof v === "boolean") entries.push([k.replaceAll("_", " "), v ? "Có" : "Không"]);
    else if (typeof v === "string" && v.length <= 80) entries.push([k.replaceAll("_", " "), v]);
  }
  const chips = [
    ...(Array.isArray(exp.matched_terms) ? exp.matched_terms : []),
    ...(Array.isArray(exp.matched_tags) ? exp.matched_tags : []),
    ...(Array.isArray(exp.shared_concepts) ? exp.shared_concepts.map(c => typeof c === "string" ? c : c?.tag || "") : []),
  ].filter(Boolean);
  return `<div class="xai-breakdown">
    ${entries.length ? `<div class="xai-kv-grid">${entries.slice(0, 8).map(([k, v]) => `<div class="xai-kv"><span>${escape(k)}</span><strong>${escape(v)}</strong></div>`).join("")}</div>` : ""}
    ${chips.length ? `<div class="skill-chip-group">${chips.slice(0, 10).map(t => `<span class="skill-chip verified">${escape(t)}</span>`).join("")}</div>` : ""}
  </div>`;
}

function importErrorText(code) {
  const workbookErrors = {
    request_size_limit: "Tệp vượt giới hạn dung lượng.",
    invalid_workbook: "Không đọc được Excel. Kiểm tra định dạng .xlsx, macro hoặc liên kết ngoài.",
    workbook_name_column_required: "Thêm cột Họ và tên ở hàng đầu tiên.",
    workbook_name_required: "Nhập tên sinh viên hoặc bỏ dòng nếu dòng này không dùng.",
    duplicate_workbook_column: "Giữ một cột cho mỗi trường dữ liệu.",
    workbook_text_required: "Đặt ô ở định dạng Văn bản và nhập lại giá trị.",
    workbook_formula_or_error: "Thay công thức hoặc lỗi Excel bằng giá trị văn bản.",
    workbook_sheet_limit: "Workbook có quá nhiều sheet.",
    workbook_column_limit: "Sheet có quá nhiều cột. Giữ tối đa 64 cột.",
  };
  if (workbookErrors[code]) return workbookErrors[code];
  return ({ header_contract: "Tiêu đề cột chưa đúng mẫu. Tải CSV mẫu và giữ nguyên các tên cột.", row_width: "Số ô trong dòng không khớp tiêu đề. Kiểm tra dấu phẩy và dấu ngoặc kép.", file_size_limit: "Tệp vượt giới hạn dung lượng.", row_count_limit: "Tệp vượt số hồ sơ cho phép. Hãy chia thành các đợt nhỏ hơn.", malformed_csv: "Cấu trúc CSV chưa hợp lệ. Hãy lưu lại theo mẫu CSV UTF-8.", empty_dataset: "Tệp chưa có hồ sơ sinh viên.", duplicate_identity: "Mã sinh viên bị trùng trong tệp.", unknown_taxonomy_tag: "Nhãn chưa có trong danh mục được duyệt.", taxonomy_group_mismatch: "Nhãn không thuộc nhóm dữ liệu của cột này.", tag_evidence_required: "Nhãn cần loại bằng chứng, tham chiếu nguồn và chất lượng bằng chứng.", unsupported_eligibility_flags_require_explicit_policy: "Điều kiện phân công chưa có chính sách xác nhận; hãy để trống trường này.", thesis_terms_do_not_prove_proficiency: "Thuật ngữ trong đề tài chưa chứng minh mức thành thạo cá nhân." })[code] || "Giá trị chưa đúng định dạng hoặc thiếu thông tin bắt buộc. Kiểm tra ô theo mẫu.";
}

function updateControls() {
  const ready = Boolean(state.bootstrap) && !state.busy;
  const cohortReady = ready && state.cohort?.valid && state.selected.size > 0;
  for (const id of ["template", "csv-file", "advisor-search", "select-all", "clear-selection"]) $(id).disabled = !ready;
  $("advisor-list").disabled = !ready;
  $("validate").disabled = !ready || !state.file;
  $("confirm-import").hidden = !previewedWorkbook;
  $("confirm-import").disabled = !ready || !previewedWorkbook;
  $("export-workbook").hidden = !state.cohort?.cohort_id || !/\.xlsx$/i.test(state.file?.name || "");
  $("export-workbook").disabled = !ready || $("export-workbook").hidden;
  $("confirm-policy").disabled = !cohortReady || !state.quotaVerified;
  $("recommend").disabled = !cohortReady;
  $("compare").disabled = !cohortReady || !state.quotaVerified || !$("confirm-policy").checked;
  $("checkpoint-version").disabled = !ready;
  $("export-json").disabled = !state.comparison || state.busy;
  $("export-csv").disabled = !currentResult()?.assignments?.length || state.busy;
}
function busy(value, text = "") { state.busy = value; document.body.setAttribute("aria-busy", String(value)); updateControls(); if (text) message(text); }

async function api(path, body, { blob = false, binary = false } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(`${state.base}/api/rebuild${path}`, { method: body === undefined ? "GET" : "POST", headers: { ...(body === undefined ? {} : { "Content-Type": binary ? "application/octet-stream" : "application/json" }) }, ...(body === undefined ? {} : { body: binary ? body : JSON.stringify(body) }), signal: controller.signal, credentials: "same-origin", redirect: "error" });
    if (response.ok && blob) return response.blob();
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) { location.replace("./login.html"); throw new Error("Phiên đăng nhập đã hết hạn."); }
      if (response.status === 403) throw new Error("Không có quyền thực hiện thao tác này.");
      throw new Error(typeof payload.detail === "string" ? payload.detail : payload.error?.message || payload.message || `Dịch vụ trả lỗi ${response.status}. Kiểm tra dữ liệu và thử lại.`);
    }
    return payload.data ?? payload;
  } finally { clearTimeout(timeout); }
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function clearResults() {
  stop(); state.comparison = null; state.recommendation = null;
  $("comparison-result").className = "empty-state"; $("comparison-result").textContent = "Chưa có phân bổ cho hồ sơ và danh sách giảng viên hiện tại.";
  $("allocation-panel").hidden = true; $("recommendation-result").className = "empty-state"; $("recommendation-result").textContent = "Chọn “Xem Top-K & Giải thích XAI” để lấy khuyến nghị cho danh sách hiện tại."; renderReplay(); updateControls();
}

async function connect() {
  busy(true, "Đang tải danh mục giảng viên và mô hình…");
  try {
    state.base = "";
    state.bootstrap = await api("/bootstrap");
    const versions = state.bootstrap.checkpoint_versions || [];
    $("checkpoint-field").hidden = !versions.length;
    $("checkpoint-version").replaceChildren(...versions.map(v => new Option(`${v} · vòng cuối`, v)));
    if (versions.includes("V3")) $("checkpoint-version").value = "V3";
    const descriptions = {
      hungarian: "Giải bài toán phân công tuyến tính toàn cục, tối đa hóa tổng điểm tương thích dưới ràng buộc chỉ tiêu.",
      ppo: "Chính sách học tăng cường (Proximal Policy Optimization) có Action Mask, chọn giảng viên theo phân phối xác suất đã học.",
      dqn: "Mạng giá trị Q (Masked Double DQN) ước lượng phần thưởng dài hạn cho từng lựa chọn giảng viên hợp lệ.",
      greedy: "Baseline tham lam chọn tuần tự cặp có điểm cao nhất còn khả thi.",
      random: "Baseline chọn ngẫu nhiên có kiểm soát seed trên các suất hợp lệ."
    };
    const availableModels = new Set((state.bootstrap.algorithms || []).map(model => model.id));
    $("model-status").innerHTML = Object.entries(descriptions)
      .filter(([id]) => availableModels.has(id) || id === "hungarian")
      .map(([id, description]) => `<div class="model-row"><b>${labels[id]}</b><small>${description}</small></div>`)
      .join("");
    renderAdvisors(); renderQuota(); message("");
  } catch(error) {
    message(errorMessage(error), "error");
  }
  finally { busy(false); }
}

function renderAdvisors() {
  const query = $("advisor-search").value.trim().toLocaleLowerCase("vi-VN");
  const advisors = state.bootstrap?.advisors || [];
  $("selection-count").textContent = `${state.selected.size} đã chọn`;
  const filtered = advisors.filter((a) => `${a.advisor_name} ${a.advisor_id}`.toLocaleLowerCase("vi-VN").includes(query));
  $("advisor-list").innerHTML = `<legend class="sr-only">Chọn giảng viên tham gia</legend>${filtered.map((a) => `<label class="advisor-option ${a.scorable ? "" : "unavailable"}"><input type="checkbox" data-advisor="${escape(a.advisor_id)}" ${state.selected.has(a.advisor_id) ? "checked" : ""} ${!a.scorable ? "disabled" : ""}><span><b>${escape(a.advisor_name || "Giảng viên chưa có tên")}</b>${a.scorable ? "" : "<small>Chưa có tín hiệu phù hợp để phân bổ</small>"}</span></label>`).join("") || `<p class="empty-state">${state.bootstrap ? "Không có giảng viên khớp tìm kiếm." : "Đang tải danh mục giảng viên…"}</p>`}`;
}

function renderQuota() {
  const count = state.cohort?.valid ? state.cohort.row_count : 0; const ids = selectedIds();
  if (!count || !ids.length) { $("quota-preview").textContent = "Nhập hồ sơ hợp lệ và chọn giảng viên để xem dự kiến chỉ tiêu."; return; }
  const quotas = balancedQuotas(count, ids);
  $("quota-preview").innerHTML = `<strong>${count} sinh viên · ${ids.length} giảng viên · tổng ${count} chỗ</strong><div class="quota-list">${quotas.map((q) => `<span>${escape(nameAdvisor(q.id))}: <b>${q.quota}</b></span>`).join("")}</div><p class="help">Phần dư được chia theo thứ tự mã giảng viên chuẩn.</p>`;
}

async function verifyQuota() {
  if (!state.cohort?.valid || !state.selected.size) return;
  const revision = state.revision;
  try {
    const value = await api("/quotas", { student_count: state.cohort.row_count, advisor_ids: selectedIds() });
    if (revision !== state.revision) return;
    const local = balancedQuotas(state.cohort.row_count, selectedIds());
    if (value.total_capacity !== state.cohort.row_count || local.some((q) => value.quotas.find((r) => r.advisor_id === q.id)?.capacity !== q.quota)) throw new Error("Chỉ tiêu dịch vụ không khớp bản xem trước. Hãy tải lại danh mục.");
    state.quotaVerified = true;
    if (value.warnings?.length) message(value.warnings.map(warningText).join(" "));
  } catch (error) { if (revision !== state.revision) return; state.quotaVerified = false; $("confirm-policy").checked = false; message(errorMessage(error), "error"); }
  finally { if (revision === state.revision) updateControls(); }
}

function renderImport(value) {
  const errors = value.errors || [];
  $("import-result").className = "";
  const errorRows = errors.map((r) => `<tr><td>${escape(r.row)}</td><td>${escape(r.column)}</td><td>${escape(importErrorText(r.code))}<details class="xai-details-panel"><summary>Mã kiểm tra</summary><code>${escape(r.code || r.message)}</code></details></td></tr>`).join("");
  const studentRows = (value.students || []).slice(0, 10).map((s) => `<tr><td>${escape(s.student_name || s.student_id)}<small>${escape(s.student_id)}</small></td><td>${escape(s.thesis_title)}</td></tr>`).join("");
  const table = errors.length
    ? `<table><caption>Lỗi theo từng dòng</caption><thead><tr><th>Dòng</th><th>Cột</th><th>Vấn đề</th></tr></thead><tbody>${errorRows}</tbody></table>`
    : `<table><caption>Xem trước hồ sơ đã nhập</caption><thead><tr><th>Sinh viên</th><th>Đề tài</th></tr></thead><tbody>${studentRows}</tbody></table>`;
  const title = value.valid ? `${value.row_count} hồ sơ hợp lệ` : `${errors.length} lỗi cần sửa trước khi tiếp tục`;
  $("import-result").innerHTML = `<p class="${value.valid ? "status-good" : "status-error"}"><strong>${escape(title)}</strong></p>${warnings(value.warnings)}<div class="table-scroll">${table}</div>${!errors.length && value.row_count > 10 ? `<p class="help">Hiển thị 10/${value.row_count} hồ sơ.</p>` : ""}`;
}

async function importStudents(event, confirm = false) {
  event.preventDefault();
  if (state.busy || !state.file || (confirm && previewedWorkbook !== state.file)) return;
  previewedWorkbook = null;
  busy(true, confirm ? "Đang lưu danh sách…" : "Đang kiểm tra danh sách…"); state.cohort = null; state.quotaVerified = false; clearResults();
  try {
    const limit = state.bootstrap?.limits?.max_csv_bytes || 10 * 1024 * 1024;
    if (state.file.size > limit) throw new Error(`Tệp vượt giới hạn ${Math.round(limit / 1024 / 1024)} MB.`);
    const workbook = /\.xlsx$/i.test(state.file.name);
    let value;
    if (workbook) {
      value = await api(`/students/workbook?confirm=${confirm}`, state.file, { binary: true });
      if (value.valid && !confirm) previewedWorkbook = state.file;
    } else {
      let csvText;
      try { csvText = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await state.file.arrayBuffer()); }
      catch { throw new Error("CSV chưa phải UTF-8 hợp lệ. Hãy lưu lại tệp theo định dạng CSV UTF-8 rồi thử lại."); }
      value = await api("/students/validate", { csv_text: csvText });
    }
    state.cohort = value.cohort_id ? value : null;
    renderImport(value);
    state.revision++; $("confirm-policy").checked = false; renderQuota();
    message(!value.valid ? "Sửa các dòng báo lỗi rồi chọn lại tệp." : previewedWorkbook ? "Kiểm tra danh sách rồi bấm Xác nhận danh sách." : "Danh sách đã được lưu. Chọn giảng viên để kiểm tra chỉ tiêu.", value.valid ? "success" : "error");
    if (state.cohort) await verifyQuota();
  } catch (error) { message(errorMessage(error), "error"); $("import-result").textContent = "Chưa có hồ sơ hợp lệ cho lần nhập này."; }
  finally { busy(false); }
}

async function recommend() {
  busy(true, "Đang tính khuyến nghị Top-K và phân rã XAI…");
  try {
    const value = await api("/recommend", { cohort_id: state.cohort.cohort_id, advisor_ids: selectedIds(), top_k: Number($("top-k").value) }); state.recommendation = value;
    $("recommendation-result").className = "";
    $("recommendation-result").innerHTML = (value.rankings || []).map((row) => `<article class="recommendation-person">
      <h3>${escape(nameStudent(row.student_id))}</h3>
      <p class="help">Mã hồ sơ: ${escape(row.student_id)}</p>
      ${row.recommendations?.length ? `<ol class="recommendation-list">${row.recommendations.map((r) => `<li>
        <div><strong>${escape(r.advisor_name || nameAdvisor(r.advisor_id))}</strong><span class="score-label">E4: ${score(r.score)}</span></div>
        <details class="xai-details-panel"><summary>Giải thích mức phù hợp (XAI Breakdown)</summary>${renderXaiExplanation(r.explanation)}</details>
      </li>`).join("")}</ol>` : `<p class="help">Chưa đủ tín hiệu để xếp hạng trong danh sách đã chọn.</p>`}
    </article>`).join("") || "Chưa có khuyến nghị đủ bằng chứng.";
    message("Đã tính Top-K kèm giải thích XAI trực quan.", "success");
  } catch (error) { message(errorMessage(error), "error"); }
  finally { busy(false); }
}

async function compare() {
  if (!$("confirm-policy").checked) return;
  busy(true, "Đang chạy đối chiếu 5 thuật toán trên cùng danh sách…"); stop();
  try {
    const version = $("checkpoint-version").value;
    state.comparison = await api("/compare", { cohort_id: state.cohort.cohort_id, advisor_ids: selectedIds(), coordinator_confirmed: true, ...(version ? { checkpoint_version: version } : {}) });
    const entries = Object.entries(state.comparison.results || {}); const preferred = ["hungarian", "ppo", "dqn"].find((key) => state.comparison.results[key]?.trace?.length);
    state.algorithm = preferred || entries[0]?.[0] || "hungarian";
    $("comparison-result").className = "comparison-content";
    $("comparison-result").innerHTML = `<div class="comparison-cards">${entries.map(([id]) => {
      const r = state.comparison.results[id];
      return `<article class="comparison-model" data-model="${escape(id)}">
        <h3>${escape(labels[id] || id)}</h3>
        <p>${id==='ppo'?'Chính sách RL (PPO)':id==='dqn'?'Giá trị Q (DQN)':id==='hungarian'?'Tối ưu toàn cục':id==='greedy'?'Tham lam tuần tự':'Ngẫu nhiên có seed'}</p>
        <span class="metric">${number(r?.metrics?.mean_compatibility, 3)}</span>
        <p>Tương thích TB${r?.metrics?.scored_students !== undefined ? ` · ${number(r.metrics.scored_students, 0)} SV có điểm` : ""}</p>
        <meter min="0" max="1" value="${Number(r?.metrics?.mean_compatibility ?? 0)}" aria-label="Điểm tương thích trung bình" ${r?.metrics?.mean_compatibility == null ? "hidden" : ""}></meter>
        <p class="${r?.status==='feasible'?'status-good':'status-warn'}"><strong>${r?.status==='feasible'?'✓ Phân bổ hợp lệ':'Chưa khả thi'}</strong></p>
      </article>`;
    }).join('')}</div>
    <div class="table-scroll"><table><caption>Bảng đối chiếu chỉ số các phương pháp</caption><thead><tr><th>Thuật toán</th><th>Trạng thái</th><th class="number">Hàm mục tiêu</th><th class="number">Tương thích TB</th><th class="number">Chênh tải chuẩn hóa</th><th class="number">Thời gian (giây)</th><th class="number">Bao phủ</th><th class="number">Vi phạm</th></tr></thead><tbody>${entries.map(([id]) => {
      const r = state.comparison.results[id];
      return `<tr><td><strong>${escape(labels[id] || id)}</strong></td><td>${escape(r.status === "feasible" ? "Hợp lệ" : r.status === "infeasible" ? "Không khả thi" : r.status)}${r.diagnostics || r.diagnostic ? `<details class="xai-details-panel"><summary>Chẩn đoán</summary>${renderXaiExplanation(r.diagnostics || r.diagnostic)}</details>` : ""}</td><td class="number">${number(r.metrics?.objective, 3)}</td><td class="number">${number(r.metrics?.mean_compatibility, 3)}</td><td class="number">${number(r.metrics?.normalized_load_imbalance, 3)}</td><td class="number">${number(r.elapsed_seconds, 4)}</td><td class="number">${typeof r.metrics?.coverage === "number" ? `${number(r.metrics.coverage * 100)}%` : "—"}</td><td class="number">${number(r.metrics?.constraint_violations, 0)}</td></tr>`;
    }).join("")}</tbody></table></div>${warnings(state.comparison.warnings)}`;
    $("result-algorithm").innerHTML = entries.map(([key]) => `<option value="${escape(key)}" ${key === state.algorithm ? "selected" : ""}>${escape(labels[key] || key)}</option>`).join("");
    $("allocation-panel").hidden = !entries.length;
    $("student-comparison-id").replaceChildren(...state.cohort.students.map(
      s => new Option(`${s.student_name || s.student_id} · ${s.student_id}`, s.student_id)));
    renderStudentComparison();
    renderAssignments(); renderReplay(); message("Đã hoàn tất đối chiếu. Xem bảng kết quả hoặc phát lại mô phỏng 3D/2D bên dưới.", "success");
  } catch (error) { message(errorMessage(error), "error"); }
  finally { busy(false); }
}

function currentResult() { return state.comparison?.results?.[state.algorithm]; }
function renderStudentComparison() {
  const id = $("student-comparison-id").value;
  const rows = Object.entries(state.comparison?.results || {}).map(([algorithm, result]) => {
    const pair = result.assignments?.find(row => row.student_id === id);
    const point = pair?.score;
    return `<li><strong>${escape(labels[algorithm] || algorithm)}</strong><span>${escape(pair ? nameAdvisor(pair.advisor_id) : "Chưa có phân công")}</span><span class="score-label">${score(point)}</span></li>`;
  });
  $("student-comparison-chart").innerHTML = `<ul class="advisor-load-list">${rows.join("")}</ul>`;
}
function renderAssignments() {
  const rows = currentResult()?.assignments || [];
  const counts = new Map();
  for (const row of rows) counts.set(row.advisor_id, (counts.get(row.advisor_id) || 0) + 1);
  const capacities = state.comparison?.policy?.capacities || [];
  const advisorIds = currentResult()?.trace?.[0]?.advisor_ids || state.bootstrap?.advisors?.map(a => a.advisor_id) || [];
  $("advisor-load-chart").innerHTML = rows.length ? `<details class="xai-details-panel" open><summary>Phân bổ tải hướng dẫn theo giảng viên</summary><ul class="advisor-load-list">${advisorIds.map((id, index) => {
    const quota = Number(capacities[index] || 0);
    const count = counts.get(id) || 0;
    return quota ? `<li><strong>${escape(nameAdvisor(id))}</strong><meter min="0" max="${quota}" value="${count}" aria-label="${escape(nameAdvisor(id))}"></meter><span><b>${count}/${quota}</b> SV</span></li>` : "";
  }).join("")}</ul></details>` : "";
  $("assignments-table").innerHTML = rows.length ? `<table><caption>Đề xuất phân bổ · ${escape(labels[state.algorithm] || state.algorithm)} · Ngưỡng ${confidenceThreshold}%</caption><thead><tr><th>Sinh viên</th><th>Giảng viên</th><th class="number">Điểm E4</th><th>Đánh giá ngưỡng</th></tr></thead><tbody>${rows.map((r) => {
    const trace = currentResult().trace?.find(t => t.student_id === r.student_id);
    const pairScore = r.assignment_mode === "quota_only" ? null : r.score ?? (trace?.score_known ? trace.score : null);
    return `<tr><td><strong>${escape(nameStudent(r.student_id))}</strong><small>${escape(r.student_id)}</small></td><td>${escape(nameAdvisor(r.advisor_id))}${r.assignment_mode === "quota_only" ? "<small>Ghép theo chỉ tiêu còn lại</small>" : ""}</td><td class="number">${score(pairScore)}</td><td>${confidenceLabel(pairScore, confidenceThreshold)}</td></tr>`;
  }).join("")}</tbody></table>` : `<p class="empty-state">Thuật toán chưa tạo được phân bổ hợp lệ.</p>`; updateControls();
}

function renderReplay() {
  stop();
  stop = mountReplay($("allocation-player"), {
    runs: {[state.algorithm]: currentResult()}, studentName: nameStudent, advisorName: nameAdvisor,
  });
}

async function exportCsv() {
  const run = state.comparison?.run_id;
  const algorithm = state.algorithm;
  if (!run || state.busy) return;
  busy(true);
  try {
    const file = await api(`/runs/${encodeURIComponent(run)}/${encodeURIComponent(algorithm)}.csv`, undefined, { blob: true });
    download(file, `unimatch-${algorithm}-allocation.csv`);
  } catch (error) {
    message(errorMessage(error), "error");
  } finally {
    busy(false);
  }
}

$("template").addEventListener("click", async () => { busy(true); try { download(await api("/templates/students.csv", undefined, { blob: true }), "unimatch-students-template.csv"); } catch (e) { message(errorMessage(e), "error"); } finally { busy(false); } });
$("csv-file").addEventListener("change", () => { state.file = $("csv-file").files[0] || null; previewedWorkbook = null; state.cohort = null; state.quotaVerified = false; state.revision++; $("file-info").textContent = state.file ? `${state.file.name} · ${number(state.file.size / 1024)} KB` : "Chưa chọn tệp."; $("confirm-policy").checked = false; $("import-result").textContent = "Chọn “Kiểm tra hồ sơ” để kiểm tra tệp mới."; clearResults(); renderQuota(); updateControls(); });
$("import-form").addEventListener("submit", importStudents);
$("confirm-import").addEventListener("click", event => importStudents(event, true));
$("export-workbook").addEventListener("click", async () => {
  const id = state.cohort?.cohort_id;
  if (!id || state.busy) return;
  busy(true, "Đang tạo Excel chuẩn…");
  try {
    const file = await api(`/cohorts/${encodeURIComponent(id)}/students.xlsx`, undefined, { blob: true });
    download(file, "unimatch-sinh-vien.xlsx");
    message("Excel chuẩn đã sẵn sàng để nhập lại.", "success");
  } catch (error) {
    message(errorMessage(error), "error");
  } finally {
    busy(false);
  }
});
$("advisor-search").addEventListener("input", renderAdvisors);
$("advisor-list").addEventListener("change", (event) => { const id = event.target.dataset.advisor; if (!id) return; if (event.target.checked) state.selected.add(id); else state.selected.delete(id); selectionChanged(); });
function selectionChanged() { state.revision++; state.quotaVerified = false; $("confirm-policy").checked = false; clearResults(); renderAdvisors(); renderQuota(); updateControls(); void verifyQuota(); }
$("select-all").addEventListener("click", () => { state.selected = new Set(state.bootstrap.advisors.filter((a) => a.scorable).map((a) => a.advisor_id)); selectionChanged(); });
$("clear-selection").addEventListener("click", () => { state.selected.clear(); selectionChanged(); });
$("confirm-policy").addEventListener("change", updateControls);
$("recommend").addEventListener("click", recommend); $("compare").addEventListener("click", compare);
$("result-algorithm").addEventListener("change", () => { stop(); state.algorithm = $("result-algorithm").value; renderAssignments(); renderReplay(); });
$("student-comparison-id").addEventListener("change", renderStudentComparison);
$("checkpoint-version").addEventListener("change", clearResults);
$("export-json").addEventListener("click", () => download(new Blob([JSON.stringify(state.comparison, null, 2)], { type: "application/json" }), "unimatch-comparison.json"));
$("export-csv").addEventListener("click", exportCsv);
addEventListener("pagehide", () => stop(), {once: true});
updateControls(); renderReplay();
const user = await requireSession();
if (user?.role === 'dean') {
  $("user-greeting").textContent = `Trưởng khoa · ${user.name}`;
  try {
    const response = await fetch("/api/thesis", { cache: "no-store" });
    if (response.ok) confidenceThreshold = (await response.json()).threshold;
  } catch { /* Default threshold applies when term is not active */ }
  await connect();
} else if (user) location.replace("./thesis.html");
