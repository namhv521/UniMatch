import { balancedQuotas } from "./student-cohorts.js";

const $ = (id) => document.getElementById(id);
const escape = (value = "") => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const labels = { ppo: "PPO", dqn: "DQN", hungarian: "Hungarian · baseline" };
const state = { bootstrap: null, base: "", token: "", selected: new Set(), cohort: null, file: null, comparison: null, recommendation: null, algorithm: "ppo", busy: false, step: 0, playing: false, revision: 0, quotaVerified: false };
let timer;

function tokenRead() { try { return sessionStorage.getItem("unimatch-rebuild-token") || ""; } catch { return ""; } }
function tokenSave(value) { try { if (value) sessionStorage.setItem("unimatch-rebuild-token", value); else sessionStorage.removeItem("unimatch-rebuild-token"); } catch { /* Memory-only access remains available. */ } }
function nameStudent(id) { return state.cohort?.students?.find((s) => s.student_id === id)?.student_name || id; }
function nameAdvisor(id) { return state.bootstrap?.advisors?.find((a) => a.advisor_id === id)?.advisor_name || id; }
function score(value) { return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "Chưa biết"; }
function number(value, digits = 2) { return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("vi-VN", { maximumFractionDigits: digits }) : "—"; }
function warningText(value) { return typeof value === "string" ? value : value?.message || JSON.stringify(value); }
function warnings(values = []) { return values.length ? `<ul class="help">${values.map((w) => `<li>${escape(warningText(w))}</li>`).join("")}</ul>` : ""; }
function selectedIds() { return [...state.selected].sort(); }
function message(text, kind = "info") { $("message").hidden = !text; $("message").className = kind; $("message").textContent = text; }
function errorMessage(error) { return error.name === "AbortError" ? "Dịch vụ phản hồi quá lâu. Kiểm tra tiến trình local rồi thử lại." : error.message || "Không thể hoàn tất yêu cầu. Hãy thử lại."; }
function importErrorText(code) {
  return ({ header_contract: "Tiêu đề cột chưa đúng mẫu. Tải CSV mẫu và giữ nguyên các tên cột.", row_width: "Số ô trong dòng không khớp tiêu đề. Kiểm tra dấu phẩy và dấu ngoặc kép.", file_size_limit: "File vượt giới hạn dung lượng.", row_count_limit: "File vượt số hồ sơ cho phép. Hãy chia thành các đợt nhỏ hơn.", malformed_csv: "Cấu trúc CSV chưa hợp lệ. Hãy lưu lại theo mẫu CSV UTF-8.", empty_dataset: "File chưa có hồ sơ sinh viên.", duplicate_identity: "Mã sinh viên bị trùng trong file.", unknown_taxonomy_tag: "Nhãn chưa có trong danh mục được duyệt.", taxonomy_group_mismatch: "Nhãn không thuộc nhóm dữ liệu của cột này.", tag_evidence_required: "Nhãn cần loại bằng chứng, tham chiếu nguồn và chất lượng bằng chứng.", unsupported_eligibility_flags_require_explicit_policy: "Điều kiện phân công chưa có chính sách xác nhận; hãy để trống trường này.", thesis_terms_do_not_prove_proficiency: "Thuật ngữ trong đề tài chưa chứng minh mức thành thạo cá nhân." })[code] || "Giá trị chưa đúng định dạng hoặc thiếu thông tin bắt buộc. Kiểm tra ô theo mẫu.";
}

function updateControls() {
  const ready = Boolean(state.bootstrap) && !state.busy;
  const cohortReady = ready && state.cohort?.valid && state.selected.size > 0;
  $("connect").disabled = state.busy;
  $("disconnect").disabled = state.busy;
  $("api-base").disabled = state.busy;
  $("access-token").disabled = state.busy;
  for (const id of ["template", "csv-file", "advisor-template", "advisor-csv-file", "advisor-search", "select-all", "clear-selection"]) $(id).disabled = !ready;
  $("advisor-validate").disabled = !ready || !$("advisor-csv-file").files.length;
  $("advisor-list").disabled = !ready;
  $("validate").disabled = !ready || !state.file;
  $("confirm-policy").disabled = !cohortReady || !state.quotaVerified;
  $("recommend").disabled = !cohortReady;
  $("compare").disabled = !cohortReady || !state.quotaVerified || !$("confirm-policy").checked;
  $("export-json").disabled = !state.comparison || state.busy;
  $("export-csv").disabled = !currentResult()?.assignments?.length || state.busy;
  const assistantReady = ready && state.bootstrap?.assistant_ready === true;
  $("assistant-question").disabled = !assistantReady;
  $("ask").disabled = !assistantReady;
  $("assistant-status").textContent = state.bootstrap?.assistant_ready === true ? "Tra cứu chỉ đọc, có dẫn nguồn." : "Tra cứu chưa bật trong phiên bản này.";
}
function busy(value, text = "") { state.busy = value; document.body.setAttribute("aria-busy", String(value)); updateControls(); if (text) message(text); }

async function api(path, body, { blob = false } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(`${state.base}/api/rebuild${path}`, { method: body === undefined ? "GET" : "POST", headers: { Authorization: `Bearer ${state.token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: controller.signal, credentials: "same-origin", redirect: "error" });
    if (response.ok && blob) return response.blob();
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) throw new Error("Không có quyền truy cập. Kiểm tra token của dịch vụ local.");
      throw new Error(typeof payload.detail === "string" ? payload.detail : payload.error?.message || payload.message || `Dịch vụ trả lỗi ${response.status}. Kiểm tra dữ liệu và thử lại.`);
    }
    return payload.data ?? payload;
  } finally { clearTimeout(timeout); }
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function jsonDetails(value) { return `<pre>${escape(JSON.stringify(value ?? {}, null, 2))}</pre>`; }

function clearResults() {
  stop(); state.comparison = null; state.recommendation = null; state.step = 0;
  $("comparison-result").className = "empty-state"; $("comparison-result").textContent = "Chưa có phân bổ cho hồ sơ và danh sách giảng viên hiện tại.";
  $("allocation-panel").hidden = true; $("recommendation-result").className = "empty-state"; $("recommendation-result").textContent = "Chọn “Xem top-K phù hợp” để lấy khuyến nghị cho danh sách hiện tại."; renderReplay(); updateControls();
}

async function connect(event) {
  event.preventDefault(); busy(true, "Đang kiểm tra kết nối và tải danh mục…");
  state.bootstrap = null; state.cohort = null; state.selected.clear(); state.quotaVerified = false; clearResults();
  try {
    const address = new URL($("api-base").value);
    if (!["http:", "https:"].includes(address.protocol) || address.username || address.password || address.search || address.hash) throw new Error("Địa chỉ dịch vụ phải là HTTP/HTTPS, không chứa token hoặc thông tin đăng nhập.");
    if (!["127.0.0.1", "localhost", "[::1]", "::1"].includes(address.hostname)) throw new Error("Chỉ kết nối dịch vụ local tại localhost, 127.0.0.1 hoặc ::1.");
    state.base = address.href.replace(/\/api\/rebuild\/?$/, "").replace(/\/$/, "");
    state.token = $("access-token").value.trim();
    if (state.token.length < 16) throw new Error("Access token cần ít nhất 16 ký tự.");
    state.bootstrap = await api("/bootstrap"); tokenSave(state.token);
    $("assistant-result").className = "empty-state";
    $("assistant-result").textContent = state.bootstrap.assistant_ready === true
      ? "Nhập câu hỏi hoặc chủ đề để tra cứu nguồn đã kiểm chứng. Tra cứu theo quy tắc và điểm phù hợp; không dùng mô hình ngôn ngữ sinh câu trả lời."
      : "Tra cứu chưa bật trong phiên bản này.";
    $("connection-status").textContent = `Đã kết nối · ${state.bootstrap.advisors.length} hồ sơ giảng viên · dữ liệu phiên bản được hiển thị bên cạnh.`;
    $("template-fields").textContent = (state.bootstrap.template_headers?.students || []).join(", ");
    $("version-detail").textContent = JSON.stringify(state.bootstrap.versions || {}, null, 2);
    $("model-status").innerHTML = (state.bootstrap.algorithms || []).map((a) => {
      const model = state.bootstrap.versions?.models?.[a.id];
      const details = model ? `<small>${number(model.checkpoint_steps, 0)} bước · seed ${escape(model.seed)} · checkpoint nghiên cứu</small>${model.checkpoint_sha256 ? `<details><summary>Phiên bản checkpoint</summary>${jsonDetails(model)}</details>` : ""}` : "";
      return `<div class="model-row"><span><b>${escape(labels[a.id] || a.id)}</b>${details}${a.reason ? `<small>${escape(a.reason)}</small>` : ""}</span><span class="${a.ready ? "status-good" : "status-warn"}">${a.ready ? "Sẵn sàng" : "Chưa khả dụng"}</span></div>`;
    }).join("") || "Chưa có thông tin mô hình.";
    renderAdvisors(); renderQuota(); message("Đã kết nối. Tải CSV mẫu hoặc chọn file hồ sơ sinh viên.", "success");
  } catch (error) { $("connection-status").textContent = "Chưa kết nối. Kiểm tra địa chỉ, token và tiến trình API local."; message(errorMessage(error), "error"); renderAdvisors(); }
  finally { busy(false); }
}

function renderAdvisors() {
  const query = $("advisor-search").value.trim().toLocaleLowerCase("vi-VN");
  const advisors = state.bootstrap?.advisors || [];
  $("selection-count").textContent = `${state.selected.size} đã chọn`;
  const filtered = advisors.filter((a) => `${a.advisor_name} ${a.advisor_id}`.toLocaleLowerCase("vi-VN").includes(query));
  $("advisor-list").innerHTML = `<legend class="sr-only">Chọn giảng viên tham gia</legend>${filtered.map((a) => `<label class="advisor-option ${a.scorable ? "" : "unavailable"}"><input type="checkbox" data-advisor="${escape(a.advisor_id)}" ${state.selected.has(a.advisor_id) ? "checked" : ""} ${!a.scorable ? "disabled" : ""}><span><b>${escape(a.advisor_name || a.advisor_id)}</b><small>${a.scorable ? escape(a.advisor_id) : "Chưa có tín hiệu phù hợp để phân bổ"}</small>${(a.warnings || []).map((w) => `<small>${escape(warningText(w))}</small>`).join("")}</span></label>`).join("") || `<p class="empty-state">${state.bootstrap ? "Không có giảng viên khớp tìm kiếm." : "Kết nối dịch vụ để tải danh mục đã được kiểm chứng."}</p>`}`;
}

function renderQuota() {
  const count = state.cohort?.valid ? state.cohort.row_count : 0; const ids = selectedIds();
  if (!count || !ids.length) { $("quota-preview").textContent = "Nhập hồ sơ hợp lệ và chọn giảng viên để xem quota."; return; }
  const quotas = balancedQuotas(count, ids);
  $("quota-preview").innerHTML = `<strong>${count} sinh viên · ${ids.length} giảng viên · tổng ${count} chỗ</strong><div class="quota-list">${quotas.map((q) => `<span>${escape(nameAdvisor(q.id))}: <b>${q.quota}</b></span>`).join("")}</div><p class="help">Phần dư được chia theo thứ tự mã giảng viên chuẩn. Quota này chỉ có hiệu lực cho danh sách đang chọn.</p>`;
}

async function verifyQuota() {
  if (!state.cohort?.valid || !state.selected.size) return;
  const revision = state.revision;
  try {
    const value = await api("/quotas", { student_count: state.cohort.row_count, advisor_ids: selectedIds() });
    if (revision !== state.revision) return;
    const local = balancedQuotas(state.cohort.row_count, selectedIds());
    if (value.total_capacity !== state.cohort.row_count || local.some((q) => value.quotas.find((r) => r.advisor_id === q.id)?.capacity !== q.quota)) throw new Error("Quota dịch vụ không khớp preview. Hãy tải lại danh mục trước khi phân bổ.");
    state.quotaVerified = true;
    if (value.warnings?.length) message(value.warnings.map(warningText).join(" "));
  } catch (error) { if (revision !== state.revision) return; state.quotaVerified = false; $("confirm-policy").checked = false; message(errorMessage(error), "error"); }
  finally { if (revision === state.revision) updateControls(); }
}

function renderImport(value) {
  const errors = value.errors || [];
  $("import-result").className = "";
  const errorRows = errors.map((r) => `<tr><td>${escape(r.row)}</td><td>${escape(r.column)}</td><td>${escape(importErrorText(r.code))}<details><summary>Mã kiểm tra</summary>${escape(r.code || r.message)}</details></td></tr>`).join("");
  const studentRows = (value.students || []).slice(0, 10).map((s) => `<tr><td>${escape(s.student_name || s.student_id)}<small>${escape(s.student_id)}</small></td><td>${escape(s.thesis_title)}</td></tr>`).join("");
  const table = errors.length
    ? `<table><caption>Lỗi CSV theo từng dòng</caption><thead><tr><th>Dòng</th><th>Cột</th><th>Vấn đề</th></tr></thead><tbody>${errorRows}</tbody></table>`
    : `<table><caption>Xem trước hồ sơ đã nhập</caption><thead><tr><th>Sinh viên</th><th>Đề tài</th></tr></thead><tbody>${studentRows}</tbody></table>`;
  const title = value.valid ? `${value.row_count} hồ sơ hợp lệ` : `${errors.length} lỗi cần sửa trước khi tiếp tục`;
  $("import-result").innerHTML = `<p class="${value.valid ? "status-good" : "status-error"}"><strong>${escape(title)}</strong></p>${warnings(value.warnings)}<div class="table-scroll">${table}</div>${!errors.length && value.row_count > 10 ? `<p class="help">Hiển thị 10/${value.row_count} hồ sơ.</p>` : ""}`;
}

async function validateAdvisorCsv(event) {
  event.preventDefault();
  const file = $("advisor-csv-file").files[0]; if (!file) return;
  busy(true, "Đang kiểm tra CSV giảng viên và hợp đồng mô hình…");
  try {
    if (file.size > (state.bootstrap?.limits?.max_csv_bytes || 10 * 1024 * 1024)) throw new Error("File vượt giới hạn dung lượng. Hãy chia nhỏ file trước khi kiểm tra.");
    let csvText;
    try { csvText = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer()); }
    catch { throw new Error("CSV chưa phải UTF-8 hợp lệ. Hãy lưu lại file theo định dạng CSV UTF-8 rồi thử lại."); }
    const value = await api("/advisors/validate", { csv_text: csvText });
    const errors = value.errors || [];
    $("advisor-import-result").className = "";
    $("advisor-import-result").innerHTML = `<p class="${value.valid ? "status-good" : "status-error"}"><strong>${value.valid ? `${number(value.row_count, 0)} hồ sơ đúng mẫu` : `${number(errors.length, 0)} lỗi cần sửa`}</strong></p><p>${value.requires_rebuild ? "Dữ liệu thay đổi: cần rebuild và kiểm chứng mô hình trước khi dùng." : value.inference_compatible ? "Dữ liệu tương thích với hợp đồng suy luận hiện tại." : "Chưa xác nhận tương thích với mô hình hiện tại."}</p>${warnings(value.warnings)}${errors.length ? `<div class="table-scroll"><table><caption>Lỗi CSV giảng viên</caption><thead><tr><th>Dòng</th><th>Cột</th><th>Vấn đề</th></tr></thead><tbody>${errors.map((r) => `<tr><td>${escape(r.row)}</td><td>${escape(r.column || r.field)}</td><td>${escape(importErrorText(r.code))}<details><summary>Mã kiểm tra</summary>${escape(r.code || r.message)}</details></td></tr>`).join("")}</tbody></table></div>` : ""}<p class="help">Lần kiểm tra không thay danh mục, quota hoặc checkpoint đang sử dụng.</p>`;
    if (value.rows?.length) {
      const details = document.createElement("details");
      details.innerHTML = `<summary>Kết quả theo từng hồ sơ</summary><div class="table-scroll"><table><thead><tr><th>Dòng</th><th>Giảng viên</th><th>Kết luận</th><th>Mã kiểm tra</th></tr></thead><tbody>${value.rows.map((r) => `<tr><td>${escape(r.row)}</td><td>${escape(r.advisor_name || r.advisor_id)}</td><td>${r.requires_rebuild ? "Cần rebuild" : r.inference_compatible ? "Tương thích" : "Chưa xác nhận"}</td><td>${escape((r.reason_codes || []).join(", "))}</td></tr>`).join("")}</tbody></table></div>`;
      $("advisor-import-result").append(details);
    }
    message(value.valid ? "Đã kiểm tra CSV giảng viên. Xem kết luận tương thích trước khi sử dụng." : "CSV giảng viên còn lỗi. Kiểm tra từng dòng và tải lại file.", value.valid ? "success" : "error");
  } catch (error) { $("advisor-import-result").textContent = "Chưa có kết quả kiểm tra hợp lệ cho lần nhập này."; message(errorMessage(error), "error"); }
  finally { busy(false); }
}

async function importStudents(event) {
  event.preventDefault(); if (!state.file) return;
  busy(true, "Đang kiểm tra cấu trúc và bằng chứng trong CSV…"); state.cohort = null; state.quotaVerified = false; clearResults();
  try {
    const limit = state.bootstrap?.limits?.max_csv_bytes || 10 * 1024 * 1024;
    if (state.file.size > limit) throw new Error(`File vượt giới hạn ${Math.round(limit / 1024 / 1024)} MB. Hãy chia nhỏ cohort.`);
    let csvText;
    try { csvText = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await state.file.arrayBuffer()); }
    catch { throw new Error("CSV chưa phải UTF-8 hợp lệ. Hãy lưu lại file theo định dạng CSV UTF-8 rồi thử lại."); }
    const value = await api("/students/validate", { csv_text: csvText }); state.cohort = value; renderImport(value);
    state.revision++; $("confirm-policy").checked = false; renderQuota();
    message(value.valid ? "Hồ sơ đã hợp lệ. Chọn giảng viên và kiểm tra quota để tiếp tục." : "Sửa các dòng báo lỗi rồi chọn lại CSV.", value.valid ? "success" : "error");
    if (value.valid) await verifyQuota();
  } catch (error) { message(errorMessage(error), "error"); $("import-result").textContent = "Chưa có hồ sơ hợp lệ cho lần nhập này."; }
  finally { busy(false); }
}

async function recommend() {
  busy(true, "Đang tính khuyến nghị top-K từ dữ liệu đã kiểm chứng…");
  try {
    const value = await api("/recommend", { cohort_id: state.cohort.cohort_id, advisor_ids: selectedIds(), top_k: Number($("top-k").value) }); state.recommendation = value;
    $("recommendation-result").className = "";
    $("recommendation-result").innerHTML = (value.rankings || []).map((row) => `<article class="recommendation-person"><h3>${escape(nameStudent(row.student_id))}</h3><p class="help">${escape(row.student_id)}</p>${row.recommendations?.length ? `<ol class="recommendation-list">${row.recommendations.map((r) => `<li><div><strong>${escape(r.advisor_name || nameAdvisor(r.advisor_id))}</strong><span class="score-label">${score(r.score)}</span></div><details><summary>Giải thích mức phù hợp</summary>${jsonDetails(r.explanation)}</details></li>`).join("")}</ol>` : `<p class="help">Chưa đủ tín hiệu để xếp hạng trong danh sách đã chọn.</p>`}</article>`).join("") || "Chưa có khuyến nghị đủ bằng chứng.";
    message("Đã tính top-K. Đây là khuyến nghị riêng từng hồ sơ, chưa áp dụng quota toàn cohort.", "success");
  } catch (error) { message(errorMessage(error), "error"); }
  finally { busy(false); }
}

async function compare() {
  if (!$("confirm-policy").checked) return;
  busy(true, "Đang chạy PPO, DQN và Hungarian trên cùng cohort…"); stop();
  try {
    state.comparison = await api("/compare", { cohort_id: state.cohort.cohort_id, advisor_ids: selectedIds(), coordinator_confirmed: true });
    const entries = Object.entries(state.comparison.results || {}); const preferred = ["ppo", "dqn", "hungarian"].find((key) => state.comparison.results[key]?.trace?.length);
    state.algorithm = preferred || entries[0]?.[0] || "hungarian"; state.step = 0;
    $("comparison-result").className = "table-scroll";
    $("comparison-result").innerHTML = `<table><caption>Kết quả từng thuật toán</caption><thead><tr><th>Thuật toán</th><th>Trạng thái</th><th class="number">Điểm mục tiêu</th><th class="number">Phù hợp trung bình</th><th class="number">Chênh tải chuẩn hóa</th><th class="number">Thời gian (giây)</th><th class="number">Phân bổ đủ</th><th class="number">Vi phạm quota</th></tr></thead><tbody>${["ppo", "dqn", "hungarian"].filter((id) => state.comparison.results[id]).map((id) => { const r = state.comparison.results[id]; return `<tr><td><strong>${escape(labels[id])}</strong></td><td>${escape(r.status === "feasible" ? "Hợp lệ" : r.status === "infeasible" ? "Không khả thi" : r.status)}${r.diagnostics || r.diagnostic ? `<details><summary>Chi tiết</summary>${jsonDetails(r.diagnostics || r.diagnostic)}</details>` : ""}</td><td class="number">${number(r.metrics?.objective, 3)}</td><td class="number">${number(r.metrics?.mean_compatibility, 3)}</td><td class="number">${number(r.metrics?.normalized_load_imbalance, 3)}</td><td class="number">${number(r.elapsed_seconds, 4)}</td><td class="number">${typeof r.metrics?.coverage === "number" ? `${number(r.metrics.coverage * 100)}%` : "—"}</td><td class="number">${number(r.metrics?.constraint_violations, 0)}</td></tr>`; }).join("")}</tbody></table>${warnings(state.comparison.warnings)}<p class="help">Phù hợp trung bình là điểm đặc trưng của các cặp đã phân bổ. Chênh tải chuẩn hóa là chênh lệch lớn nhất giữa tỷ lệ tải/quota của các giảng viên (thấp hơn là cân bằng hơn). Các chỉ số phục vụ so sánh cùng đầu vào, chưa phải độ chính xác hoặc kết quả hướng dẫn thực tế.</p>`;
    $("result-algorithm").innerHTML = entries.map(([key]) => `<option value="${escape(key)}" ${key === state.algorithm ? "selected" : ""}>${escape(labels[key] || key)}</option>`).join("");
    $("allocation-panel").hidden = !entries.length; $("run-metadata").textContent = JSON.stringify({ run_id: state.comparison.run_id, versions: state.comparison.versions, policy: state.comparison.policy }, null, 2);
    renderAssignments(); renderReplay(); message("Đã hoàn tất so sánh. Mở bảng phân bổ hoặc phát lại từng quyết định.", "success");
  } catch (error) { message(errorMessage(error), "error"); }
  finally { busy(false); }
}

function currentResult() { return state.comparison?.results?.[state.algorithm]; }
function renderAssignments() {
  const rows = currentResult()?.assignments || [];
  $("assignments-table").innerHTML = rows.length ? `<table><caption>Đề xuất phân bổ · ${escape(labels[state.algorithm] || state.algorithm)}</caption><thead><tr><th>Sinh viên</th><th>Giảng viên</th><th class="number">Điểm phù hợp</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${escape(nameStudent(r.student_id))}<small>${escape(r.student_id)}</small></td><td>${escape(nameAdvisor(r.advisor_id))}</td><td class="number">${score(r.score ?? currentResult().trace?.find((t) => t.student_id === r.student_id)?.score)}</td></tr>`).join("")}</tbody></table>` : `<p class="empty-state">Thuật toán chưa tạo được phân bổ hợp lệ. Xem chẩn đoán ở bảng so sánh.</p>`; updateControls();
}

function stop() { clearInterval(timer); state.playing = false; if ($("play")) $("play").textContent = "Phát"; }
function renderReplay() {
  const trace = currentResult()?.trace || []; state.step = Math.max(0, Math.min(state.step, trace.length));
  $("step-count").textContent = `${state.step} / ${trace.length} bước`;
  $("previous-step").disabled = state.step === 0; $("next-step").disabled = !trace.length || state.step >= trace.length;
  $("play").disabled = !trace.length; $("reset-replay").disabled = !trace.length;
  const decision = trace[state.step - 1];
  $("current-decision").className = decision ? "" : "empty-state";
  $("current-decision").innerHTML = decision ? `<strong>${escape(nameStudent(decision.student_id))}</strong> → <strong>${escape(nameAdvisor(decision.advisor_id))}</strong><p class="help">Điểm phù hợp ${score(decision.score_known ? decision.score : null)} · reward ${number(decision.total_reward, 4)} · ${decision.pre_action_mask?.filter(Boolean).length ?? "—"} lựa chọn hợp lệ trước bước này.</p><details><summary>Điểm thành phần và đầu ra mô hình</summary>${jsonDetails({ reward: decision.reward_components, preference: decision.preference_known ? decision.preference : "Chưa biết", policy_output: decision.policy_output || { status: "Không có đầu ra policy/Q được cung cấp" } })}</details>` : trace.length ? "Bắt đầu phát để xem sinh viên, lựa chọn hợp lệ và tải giảng viên ở từng bước." : "Trace sẽ xuất hiện sau lần phân bổ đầu tiên.";
  const registry = decision?.advisor_registry || trace[0]?.advisor_registry || []; const capacities = decision?.capacities || trace[0]?.capacities || []; const loads = decision?.loads_after || registry.map(() => 0);
  $("load-chart").innerHTML = registry.map((id, i) => capacities[i] > 0 ? `<div class="load-row"><span>${escape(nameAdvisor(id))}</span><b>${loads[i] || 0}/${capacities[i]}</b><progress value="${loads[i] || 0}" max="${capacities[i]}" aria-label="Tải ${escape(nameAdvisor(id))}"></progress></div>` : "").join("");
  $("trace-table").innerHTML = trace.length ? `<table><caption>Trace quyết định thực · ${escape(labels[state.algorithm] || state.algorithm)}</caption><thead><tr><th>Bước</th><th>Sinh viên</th><th>Giảng viên</th><th class="number">Điểm</th><th class="number">Reward</th><th>Trạng thái</th></tr></thead><tbody>${trace.map((r, i) => `<tr ${i + 1 === state.step ? 'aria-current="step"' : ""}><td>${i + 1}</td><td>${escape(nameStudent(r.student_id))}</td><td>${escape(nameAdvisor(r.advisor_id))}</td><td class="number">${score(r.score_known ? r.score : null)}</td><td class="number">${number(r.total_reward, 4)}</td><td>${i < state.step ? "Đã phát" : "Chưa phát"}</td></tr>`).join("")}</tbody></table>` : "";
}
function play() {
  if (state.playing) { stop(); return; }
  const trace = currentResult()?.trace || []; if (!trace.length) return;
  if (state.step >= trace.length) state.step = 0;
  state.playing = true; $("play").textContent = "Tạm dừng";
  timer = setInterval(() => { state.step++; renderReplay(); if (state.step >= trace.length) stop(); }, 1000 / Number($("replay-speed").value));
}

function csvCell(value) { let text = String(value ?? ""); if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`; return `"${text.replaceAll('"', '""')}"`; }
function exportCsv() {
  const rows = currentResult()?.assignments || [];
  const values = [["student_id", "student_name", "advisor_id", "advisor_name", "score", "algorithm"], ...rows.map((r) => [r.student_id, nameStudent(r.student_id), r.advisor_id, nameAdvisor(r.advisor_id), r.score ?? currentResult().trace?.find((t) => t.student_id === r.student_id)?.score ?? "", state.algorithm])];
  download(new Blob(["\uFEFF", values.map((row) => row.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }), `unimatch-${state.algorithm}-allocation.csv`);
}

async function ask(event) {
  event.preventDefault(); if (state.bootstrap?.assistant_ready !== true) return;
  busy(true, "Đang tra cứu nguồn đã kiểm chứng…");
  try {
    const value = await api("/assistant", { question: $("assistant-question").value, cohort_id: state.cohort?.cohort_id || null, advisor_ids: selectedIds(), top_k: Number($("top-k").value) });
    $("assistant-result").className = "";
    $("assistant-result").textContent = value.answer || value.message || "Dịch vụ chưa trả câu trả lời có nguồn.";
    if (value.mode === "deterministic_read_only") {
      const disclosure = document.createElement("p"); disclosure.className = "help";
      disclosure.textContent = "Tra cứu theo quy tắc và điểm phù hợp; không dùng mô hình ngôn ngữ sinh câu trả lời.";
      $("assistant-result").append(disclosure);
    }
    if (value.citations?.length) {
      const list = document.createElement("ul");
      for (const citation of value.citations) {
        const item = document.createElement("li"); const url = citation.url || citation.source_url;
        let valid = false; try { const parsed = new URL(url); valid = ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password; } catch { /* No unsafe citation link. */ }
        if (valid) { const link = document.createElement("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = citation.title || citation.advisor_name || "Nguồn chính thức"; item.append(link); }
        else item.textContent = citation.title || "Nguồn chưa có URL";
        if (citation.snippet) item.append(document.createTextNode(` — ${citation.snippet}`));
        const sourceHash = citation.source_sha256; const retrievedAt = citation.retrieved_at || citation.crawled_at;
        if (sourceHash || retrievedAt) {
          const details = document.createElement("details"); const summary = document.createElement("summary"); const metadata = document.createElement("pre");
          summary.textContent = "Dấu vết nguồn";
          metadata.textContent = [retrievedAt ? `Lấy nguồn: ${retrievedAt}` : "", sourceHash ? `SHA-256: ${sourceHash}` : ""].filter(Boolean).join("\n");
          details.append(summary, metadata); item.append(details);
        }
        list.append(item);
      }
      $("assistant-result").append(list);
    }
    message("Đã tra cứu. Kiểm tra trích dẫn và giới hạn dữ liệu trong câu trả lời.", "success");
  } catch (error) { message(errorMessage(error), "error"); }
  finally { busy(false); }
}

$("api-base").value = location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:8000";
$("access-token").value = tokenRead();
$("connect-form").addEventListener("submit", connect);
$("disconnect").addEventListener("click", () => { tokenSave(""); state.token = ""; $("access-token").value = ""; state.bootstrap = null; state.cohort = null; state.selected.clear(); state.file = null; state.quotaVerified = false; $("csv-file").value = ""; $("advisor-csv-file").value = ""; $("advisor-import-result").textContent = "Đã xóa dữ liệu trong phiên."; $("file-info").textContent = "Chưa chọn file."; $("assistant-question").value = ""; clearResults(); renderAdvisors(); renderQuota(); $("import-result").textContent = "Đã xóa dữ liệu trong phiên."; $("model-status").textContent = "Chưa kết nối."; $("version-detail").textContent = "Chưa có metadata."; $("assistant-result").textContent = "Chưa kết nối."; $("connection-status").textContent = "Đã xóa token. Nhập lại khi muốn kết nối."; updateControls(); });
$("template").addEventListener("click", async () => { busy(true); try { download(await api("/templates/students.csv", undefined, { blob: true }), "unimatch-students-template.csv"); } catch (e) { message(errorMessage(e), "error"); } finally { busy(false); } });
$("csv-file").addEventListener("change", () => { state.file = $("csv-file").files[0] || null; state.cohort = null; state.quotaVerified = false; state.revision++; $("file-info").textContent = state.file ? `${state.file.name} · ${number(state.file.size / 1024)} KB` : "Chưa chọn file."; $("confirm-policy").checked = false; $("import-result").textContent = "Chọn “Kiểm tra hồ sơ” để kiểm tra file mới."; clearResults(); renderQuota(); updateControls(); });
$("import-form").addEventListener("submit", importStudents);
$("advisor-csv-file").addEventListener("change", () => { $("advisor-import-result").textContent = "Chọn kiểm tra để xác minh file mới. Danh mục hiện tại chưa thay đổi."; updateControls(); });
$("advisor-import-form").addEventListener("submit", validateAdvisorCsv);
$("advisor-template").addEventListener("click", async () => { busy(true); try { download(await api("/templates/advisors.csv", undefined, { blob: true }), "unimatch-advisors-template.csv"); } catch (error) { message(errorMessage(error), "error"); } finally { busy(false); } });
$("advisor-search").addEventListener("input", renderAdvisors);
$("advisor-list").addEventListener("change", (event) => { const id = event.target.dataset.advisor; if (!id) return; if (event.target.checked) state.selected.add(id); else state.selected.delete(id); selectionChanged(); });
function selectionChanged() { state.revision++; state.quotaVerified = false; $("confirm-policy").checked = false; clearResults(); renderAdvisors(); renderQuota(); updateControls(); void verifyQuota(); }
$("select-all").addEventListener("click", () => { state.selected = new Set(state.bootstrap.advisors.filter((a) => a.scorable).map((a) => a.advisor_id)); selectionChanged(); });
$("clear-selection").addEventListener("click", () => { state.selected.clear(); selectionChanged(); });
$("confirm-policy").addEventListener("change", updateControls);
$("recommend").addEventListener("click", recommend); $("compare").addEventListener("click", compare);
$("result-algorithm").addEventListener("change", () => { stop(); state.algorithm = $("result-algorithm").value; state.step = 0; renderAssignments(); renderReplay(); });
$("previous-step").addEventListener("click", () => { stop(); state.step--; renderReplay(); });
$("next-step").addEventListener("click", () => { stop(); state.step++; renderReplay(); });
$("reset-replay").addEventListener("click", () => { stop(); state.step = 0; renderReplay(); });
$("play").addEventListener("click", play); $("replay-speed").addEventListener("change", () => { if (state.playing) { stop(); play(); } });
$("export-json").addEventListener("click", () => download(new Blob([JSON.stringify(state.comparison, null, 2)], { type: "application/json" }), "unimatch-comparison.json"));
$("export-csv").addEventListener("click", exportCsv); $("assistant-form").addEventListener("submit", ask);
updateControls(); renderReplay();
if ($("access-token").value) void connect(new Event("submit"));
