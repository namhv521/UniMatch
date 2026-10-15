import { MatchingScene } from "./matching-scene.js";
import { createReplay, normalizeBenchmark, replayStateAt, preferredDataset, compatibleModels } from "./visualization.js";
import { advisorMatches, advisorQuery, balancedQuotas, canAllocate } from "./student-cohorts.js";
import { createHomeScene } from "./home-scene.js";

const app = document.querySelector("#app");
const state = {
  session: null,
  catalog: null,
  health: null,
  dataset: null,
  simulation: null,
  simulationMode: null,
  resultsSummary: null,
  mode: "semantic",
  route: location.hash.slice(1) || "/",
  busy: false,
  error: "",
  replay: createReplay(0),
  playing: false,
  speed: 1,
  cohort: {
    advisors: null,
    selected: new Set(),
    search: "",
    file: null,
    preview: null,
    result: null,
    busy: "",
    error: "",
  },
};
let scene = null;
let playTimer = null;
let sceneObserver = null;
let disposeHomeScene = null;

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));

function unwrap(payload) {
  return payload?.data ?? payload ?? {};
}

async function api(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401 && !path.startsWith("/auth/")) {
    clearPrivateState();
    navigate("/login");
  }
  if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || payload?.message || `Yêu cầu thất bại (${response.status}).`);
  return unwrap(payload);
}

const routeLabels = { "/": "Trang chủ", "/matching": "Ghép cặp", "/students": "Nhập sinh viên", "/results": "Kết quả" };

function navigate(route) {
  location.hash = route;
}

function header() {
  return `<header class="topbar ${state.route === "/" ? "landing-topbar" : ""}">
    <a class="brand" href="#/" aria-label="UniMatch — Trang chủ"><span>Uni</span>Match</a>
    <nav aria-label="Điều hướng chính">
      ${Object.entries(routeLabels).map(([route, label]) => `<a href="#${route}" ${state.route === route ? 'aria-current="page"' : ""}>${label}</a>`).join("")}
    </nav>
    <button class="account-button" id="logout" type="button" aria-label="Đăng xuất" title="Đăng xuất">${escapeHtml((state.session?.display_name || state.session?.email || "●")[0].toUpperCase())}</button>
  </header>`;
}

function status(message, kind = "info") {
  return `<div class="status ${kind}" role="${kind === "error" ? "alert" : "status"}">${escapeHtml(message)}</div>`;
}

function loginView() {
  return `<main id="main" class="login-shell">
    <section class="login-story">
      <a class="brand large" href="#/login"><span>Uni</span>Match</a>
      <div>
        <p class="section-tag">Hệ thống hỗ trợ khóa luận</p>
        <h1>Ghép cặp phù hợp,<br>hiểu từng quyết định</h1>
        <p>Kết nối sinh viên với giảng viên dựa trên nội dung đề tài, năng lực nghiên cứu và hạn mức hướng dẫn.</p>
      </div>
      <div class="mini-network" aria-hidden="true">
        <span class="dot s1">SV01</span><span class="dot s2">SV02</span><span class="dot s3">SV03</span>
        <i class="line l1"></i><i class="line l2"></i><i class="line l3"></i>
        <span class="dot advisor a1">GV-A</span><span class="dot advisor a2">GV-B</span>
      </div>
    </section>
    <section class="login-form-wrap">
      <form id="login-form" class="login-form">
        <h2>Đăng nhập</h2>
        <p>Đăng nhập để sử dụng dữ liệu và lưu vết lần chạy.</p>
        ${state.error ? status(state.error, "error") : ""}
        <label>Email<input name="email" type="email" autocomplete="username" required placeholder="nhap@email.edu.vn"></label>
        <label>Mật khẩu<input name="password" type="password" autocomplete="current-password" required minlength="1" placeholder="Nhập mật khẩu"></label>
        <button class="button primary wide" type="submit" ${state.busy ? "disabled" : ""}>${state.busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
        <a class="text-link" href="#/matching">Xem mẫu mô phỏng</a>
      </form>
    </section>
  </main>`;
}

function baselineRows() {
  const rows = normalizeBenchmark(state.resultsSummary || {}).summary.filter((item) => ["random", "greedy", "hungarian"].includes(item.algorithm.toLowerCase()));
  if (!rows.length) return `<p>Chưa có benchmark đã xác minh.</p>`;
  const maximum = Math.max(...rows.map((item) => item.mean || 0), 0.000001);
  return rows.map((item) => {
    const value = Number(item.mean);
    return `<div class="bar-row"><span>${escapeHtml(item.algorithm)}</span><i style="--value:${Math.min(100, value / maximum * 100)}%"></i><b>${value.toFixed(4)}</b></div>`;
  }).join("");
}

function homeView() {
  const datasets = state.catalog?.datasets || [];
  const train = datasets.find(item => item.id === "real-train")?.students;
  const arrow = `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  return `${header()}<main id="main" class="home-page landing-page">
    ${state.error ? status(state.error, "error") : ""}
    <section class="landing-hero" aria-labelledby="home-title">
      <div class="landing-copy">
        <h1 id="home-title">Năng lực gặp<br><span>đúng người<br>đồng hành.</span></h1>
        <p>Từ năng lực bạn đang có đến người hướng dẫn phù hợp. UniMatch giúp tìm điểm giao chuyên môn và phân bổ khóa luận theo hạn mức rõ ràng.</p>
        <div class="landing-actions"><a class="landing-primary" href="#/students">Phân bổ đợt sinh viên ${arrow}</a><a class="landing-secondary" href="#/matching">Khám phá mô phỏng ${arrow}</a></div>
        <p class="landing-helper">Chưa có đề tài? Bắt đầu bằng kỹ năng đã học và dự án đã làm.</p>
        <div class="landing-data"><span class="connection-dot" aria-hidden="true"></span><span>${state.health?.data_loaded ? `${escapeHtml(train ?? "—")} hồ sơ train · ${escapeHtml(state.health?.total_advisors ?? "—")} giảng viên` : "Chưa nhận được trạng thái dữ liệu"}</span><a href="#/results">Xem nguồn dữ liệu ${arrow}</a></div>
      </div>
      <div class="connection-stage">
        <div class="stage-heading"><span>Không gian chuyên môn</span><span class="stage-live">Trải nghiệm 3D tương tác</span></div>
        <canvas id="home-network" aria-hidden="true"></canvas>
        <div class="profile-label profile-student"><span class="profile-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="m3 8 9-5 9 5-9 5-9-5Zm4 3v6c3 3 7 3 10 0v-6M21 8v8" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg></span><span><small>Năng lực sinh viên</small><strong>Python · Dữ liệu · Tư duy</strong></span></div>
        <div class="profile-label profile-advisor"><span class="profile-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4V4Zm9 3a3 3 0 0 1 3-3h5v14h-5a3 3 0 0 0-3 3" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg></span><span><small>Chuyên môn hướng dẫn</small><strong>Học máy · Hệ thống thông tin</strong></span></div>
        <div class="stage-footer"><span>Minh họa · <i></i>Sinh viên <i></i>Giảng viên</span><button id="network-motion" type="button" aria-pressed="false">Dừng chuyển động</button></div>
      </div>
    </section>
    <section class="landing-workflow" aria-labelledby="workflow-title">
      <div class="workflow-intro"><h2 id="workflow-title">Một hành trình.<br> Những lựa chọn có cơ sở.</h2><p>Để chuyên môn gặp đúng cơ hội.</p></div>
      <ol><li><span>Khảo sát năng lực</span><p>Nhập Excel những kỹ năng đã có. Không cần đặt trước tên đề tài.</p></li><li><span>Kết nối chuyên môn</span><p>Chọn giảng viên tham gia. So khớp nội dung trong hạn mức của đợt.</p></li><li><span>Rà soát phương án</span><p>Xem điểm, tải và từng cặp ghép trước khi đưa ra quyết định.</p></li></ol>
    </section>
    <section class="landing-evidence" aria-labelledby="evidence-title"><div><h2 id="evidence-title">Thấy cách hệ thống<br>đi đến một kết quả.</h2><p>Khám phá ghép cặp theo TF-IDF, tối ưu Hungarian và các policy học tăng cường. Mỗi lượt chạy lưu thuật toán, dữ liệu và dấu vết quyết định để bạn đối chiếu.</p><a href="#/matching">Mở không gian mô phỏng ${arrow}</a><small>Điểm tương thích không phải xác suất. Các model RL hiện vẫn ở chế độ nghiên cứu, chưa promote.</small></div><div class="landing-benchmark"><h3>Đối chiếu baseline</h3><p>${state.resultsSummary ? `${escapeHtml(state.resultsSummary.students)} SV · ${escapeHtml(state.resultsSummary.advisors)} GV · ${escapeHtml(state.resultsSummary.split)}` : "Chưa tải được báo cáo"}</p><div class="bars">${baselineRows()}</div><a href="#/results">Đọc kết quả và điều kiện đánh giá ${arrow}</a></div></section>
    <footer class="landing-footer"><a class="brand" href="#/">UniMatch</a><span>Hỗ trợ phân bổ khóa luận · Quyết định cuối thuộc người điều phối</span><a href="#/students">Bắt đầu đợt phân bổ ${arrow}</a></footer>
  </main>`;
}

function normalizeDatasets() {
  const raw = state.catalog?.datasets || [];
  const datasets = Array.isArray(raw) ? raw : Object.entries(raw).map(([id, value]) => ({ id, ...(typeof value === "object" ? value : { name: value }) }));
  if (datasets.length) return datasets.map((item) => typeof item === "string" ? { id: item, name: item } : item);
  return [
    { id: "sample-2x2", name: "Mẫu: 2 SV · 2 GV", sample: true },
    { id: "sample-3x2", name: "Mẫu: 3 SV · 2 GV", sample: true },
  ];
}

function normalizeModels() {
  const raw = state.catalog?.models || [];
  const models = Array.isArray(raw) ? raw : Object.entries(raw).map(([id, value]) => ({ id, ...(typeof value === "object" ? value : { name: value }) }));
  return models.map((model) => typeof model === "string"
    ? { id: model, name: model, available: true }
    : { ...model, id: model.id || model.algorithm, name: model.name || `${model.algorithm} · seed ${model.seed ?? "—"} · ${Number(model.completed_timesteps || 0).toLocaleString("vi-VN")} bước · ${model.research ? "nghiên cứu" : "mẫu"}` });
}

function modelMode(model) {
  return model?.mode || model?.simulation_mode || (model?.research === true ? "rl_research" : "rl");
}

function datasetLabel(dataset) {
  const labels = {
    "sample-2x2": "Mẫu: 2 SV · 2 GV",
    "sample-3x2": "Mẫu: 3 SV · 2 GV",
    "real-train": "Dữ liệu đầy đủ · train",
    "real-validation": "Dữ liệu đầy đủ · validation",
  };
  return dataset.name || dataset.label || `${labels[dataset.id] || dataset.id}${dataset.students != null ? ` · ${dataset.students} SV · ${dataset.advisors} GV` : ""}`;
}

function selectedDatasetId() {
  return document.querySelector("#dataset-select")?.value || preferredDataset(normalizeDatasets(), state.health?.data_loaded === true);
}

function selectedAlgorithm() {
  return document.querySelector("#algorithm-select")?.value || (state.mode === "rl" ? normalizeModels()[0]?.id : "hungarian");
}

function modeCards() {
  const modes = [
    ["semantic", "Semantic", "Xếp hạng theo độ tương đồng", "SV01: NLP → GV-A", "Điểm là độ tương thích, không phải xác suất."],
    ["non_rl", "Đã train · chưa dùng RL", "So sánh đặc trưng đã học", "Model scorer → ghép theo hạn mức", "Chưa có artifact model được catalog xác nhận."],
    ["rl", "Đã train + RL", "Chọn hành động theo trạng thái", "SV01 → GV-A → cập nhật hạn mức", "Replay action, invalid proposal và fallback từ API."],
  ];
  return modes.map(([id, title, subtitle, sample, note], index) => `<button class="mode-card ${state.mode === id ? "selected" : ""}" data-mode="${id}" type="button" ${id === "non_rl" ? "disabled" : ""}>
    <span class="radio-dot"></span><span><b>${index + 1}. ${title}</b><small>${subtitle}</small><code>${sample}</code><em>${note}</em></span>
  </button>`).join("");
}

function controlOptions() {
  const datasets = normalizeDatasets();
  const datasetId = datasets.some((item) => item.id === state.dataset?.id) ? state.dataset.id : preferredDataset(datasets, state.health?.data_loaded === true);
  const algorithms = state.mode === "semantic"
    ? [{ id: "hungarian", name: "Hungarian" }, { id: "greedy", name: "Greedy" }, { id: "random", name: "Random" }]
    : compatibleModels(normalizeModels(), datasetId);
  return `<label>Dữ liệu<select id="dataset-select">${datasets.map((item) => `<option value="${escapeHtml(item.id)}" ${item.id === datasetId ? "selected" : ""}>${escapeHtml(datasetLabel(item))}</option>`).join("")}</select></label>
    <label>${state.mode === "rl" ? "Model / checkpoint" : "Thuật toán"}<select id="algorithm-select" ${state.mode === "non_rl" ? "disabled" : ""}>${algorithms.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.algorithm || item.id)}</option>`).join("")}</select></label>
    <label>Seed<input id="seed-input" type="number" value="${state.mode === "rl" ? (algorithms[0]?.seed ?? 42) : 42}" min="0" max="2147483647" ${state.mode === "rl" ? "disabled" : ""}></label>
    <button class="button primary" id="simulate" ${state.busy || state.mode === "non_rl" || !algorithms.length || (datasetId?.startsWith("real-") && state.health?.data_loaded !== true) ? "disabled" : ""}>${state.busy ? "Đang mô phỏng…" : "Bắt đầu mô phỏng"}</button>
    ${state.catalog?.quality?.ready === false ? `<p class="control-warning">Dữ liệu là subset đã kiểm tra; hạn mức GV chỉ là giả định thực nghiệm, chưa đủ điều kiện triển khai thực tế.</p>` : ""}
    ${state.mode === "rl" && !algorithms.length ? `<p class="control-warning">Chưa có checkpoint tương thích bộ dữ liệu này. Chọn Semantic để ghép cặp ngay hoặc cập nhật sau khi training hoàn tất.</p>` : ""}
    ${state.mode === "rl" && algorithms.some((model) => modelMode(model) === "rl_research") ? `<p class="control-warning">Có model nghiên cứu chưa promote. Kết quả sẽ được gắn nhãn thử nghiệm.</p>` : ""}`;
}

function sceneData() {
  const dataset = state.dataset || {};
  const simulation = state.simulation || {};
  return {
    students: dataset.students || [],
    advisors: dataset.advisors || [],
    events: simulation.events || [],
  };
}

function currentEventPanel() {
  const events = state.simulation?.events || [];
  const replayState = replayStateAt(events, state.replay.index);
  const event = replayState.current;
  if (!event) return `<div class="empty-state"><strong>Chưa có bước mô phỏng</strong><span>Chọn dữ liệu, thuật toán rồi bắt đầu. Canvas vẫn có thể xoay và thu phóng khi dữ liệu đã tải.</span></div>`;
  const flags = [event.invalid_proposal && "Đề xuất không hợp lệ", event.fallback && "Đã fallback"].filter(Boolean);
  return `<dl class="event-details">
    <div><dt>Bước</dt><dd>${escapeHtml(state.replay.index)}</dd></div>
    <div><dt>Sinh viên</dt><dd>${escapeHtml(event.student_id || "—")}</dd></div>
    <div><dt>Hành động</dt><dd>${escapeHtml(event.advisor_id ? `Chọn ${event.advisor_id}` : "Không chọn")}</dd></div>
    <div><dt>Điểm</dt><dd>${event.score == null ? "Chưa có" : Number(event.score).toFixed(4)}</dd></div>
    ${state.simulationMode?.startsWith("rl") ? `<div><dt>Reward</dt><dd>${event.reward == null ? "Chưa có" : escapeHtml(event.reward)}</dd></div>` : ""}
  </dl>${flags.length ? `<div class="warning"><strong>${flags.join(" · ")}</strong><span>${escapeHtml(event.explanation || "Backend đã ghi nhận trạng thái này trong trace.")}</span></div>` : `<p class="explanation">${escapeHtml(event.explanation || "API chưa cung cấp lời giải thích cho bước này.")}</p>`}`;
}

function resultsTable() {
  const simulation = state.simulation;
  if (!simulation) return `<div class="empty-state compact">Chưa có lần chạy trong phiên này.</div>`;
  const assignments = simulation.assignments || [];
  if (!assignments.length) return `<div class="empty-state compact">API không trả về cặp ghép nào.</div>`;
  return `<div class="table-scroll"><table><thead><tr><th>Sinh viên</th><th>Giảng viên</th><th>Điểm tương thích</th><th>Ghi chú</th></tr></thead><tbody>${assignments.map((item) => { const score = item.score ?? item.compatibility_score; return `<tr><td>${escapeHtml(item.student_id || item.student?.id)}</td><td>${escapeHtml(item.advisor_id || item.advisor?.id)}</td><td>${score == null ? "—" : Number(score).toFixed(4)}</td><td>${item.fallback ? "Fallback được ghi nhận" : "Theo thuật toán đã chọn"}</td></tr>`; }).join("")}</tbody></table></div>`;
}

function matchingView() {
  const events = state.simulation?.events || [];
  return `${header()}<main id="main" class="page matching-page">
    <section class="page-heading"><div><h1>Ghép cặp & mô phỏng thuật toán</h1><p>Quan sát từng quyết định từ dữ liệu và trace thật do API trả về.</p></div><ol class="steps"><li class="active">Chọn dữ liệu</li><li>Chọn chế độ</li><li>Mô phỏng</li><li>Xem kết quả</li></ol></section>
    ${state.error ? status(state.error, "error") : ""}
    <section class="mode-grid" aria-label="Chọn chế độ">${modeCards()}</section>
    <section class="control-bar">${controlOptions()}</section>
    <section class="simulation-layout">
      <article class="viewport-card"><header><h2>Không gian phân bổ 3D</h2><span class="sample-badge">${state.dataset?.sample ? "Mẫu minh họa" : "Dữ liệu từ API"}</span></header>
        <canvas id="matching-canvas" tabindex="0" aria-label="Mô phỏng 3D. Kéo để xoay, cuộn để thu phóng, dùng phím mũi tên trái phải để đổi góc nhìn."></canvas>
        <div class="scene-narration"><strong id="scene-progress">Quan sát sinh viên đến với người hướng dẫn</strong><span id="scene-selection">Kéo để xoay · Cuộn để zoom · Chọn cột giảng viên để xem tải</span></div><div class="legend"><span class="candidate">Sinh viên đang chờ</span><span class="matched">Đã ghép</span><span class="invalid">Không hợp lệ / fallback</span></div>
        <div class="playback">
          <button id="play" type="button" aria-label="${state.playing ? "Tạm dừng" : "Phát"}">${state.playing ? "Tạm dừng" : "Phát"}</button>
          <button id="previous" type="button">‹ Bước trước</button><button id="next" type="button">Bước tiếp ›</button>
          <button id="reset-replay" type="button">Đặt lại</button><button id="reset-view" type="button">Góc nhìn mặc định</button>
          <label class="speed-label">Tốc độ<select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label>
          <input id="timeline" type="range" min="0" max="${events.length}" value="${state.replay.index}" aria-label="Dòng thời gian mô phỏng">
          <output id="step-count">Bước ${state.replay.index}/${events.length}</output>
        </div>
      </article>
      <aside class="explanation-card"><div class="tab-title">Vì sao chọn cặp này?</div><div id="event-panel">${currentEventPanel()}</div></aside>
    </section>
    <section class="results-card"><header><div><h2>Kết quả đã chạy</h2><p>${escapeHtml(state.simulation?.provenance?.protocol || "Chỉ so sánh metric khi cùng dataset, split và protocol.")}</p></div>${state.simulation ? `<span class="run-badge">${escapeHtml(state.simulation.model_version || state.simulation.data_version || "Lần chạy hiện tại")}</span>` : ""}</header>${resultsTable()}</section>
    <div class="evidence-banner ${state.simulationMode === "rl_research" || state.simulation?.experimental ? "research" : ""}"><strong>${state.simulationMode === "rl_research" || state.simulation?.experimental ? "Model nghiên cứu chưa promote." : state.mode === "rl" ? "Checkpoint đã train không đồng nghĩa đã benchmark." : "Điểm semantic không phải xác suất ghép đúng."}</strong><span>${escapeHtml(state.simulation?.banner || (state.simulationMode === "rl_research" ? "Kết quả real38 cần qua đánh giá và promotion gate trước khi dùng vận hành." : "Sample 3D là minh họa; số liệu kết quả chỉ lấy từ API."))}</span></div>
  </main>`;
}

function selectedCohortAdvisors() {
  return (state.cohort.advisors || []).filter((advisor) => state.cohort.selected.has(advisor.id));
}

function warningList(warnings = []) {
  return warnings.length ? `<ul class="cohort-warnings">${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : "";
}

function advisorChecklist() {
  if (state.cohort.busy === "advisors") return `<div class="empty-state compact">Đang tải danh sách giảng viên…</div>`;
  const advisors = state.cohort.advisors || [];
  if (!advisors.length) return `<div class="empty-state compact">Chưa có danh sách giảng viên.</div>`;
  const visibleCount = advisors.filter((advisor) => advisorMatches(advisor, state.cohort.search)).length;
  return `<div class="advisor-checklist">${advisors.map((advisor) => `<label ${advisorMatches(advisor, state.cohort.search) ? "" : "hidden"}>
    <input type="checkbox" name="advisor" value="${escapeHtml(advisor.id)}" ${state.cohort.selected.has(advisor.id) ? "checked" : ""} ${state.cohort.busy ? "disabled" : ""}>
    <span><strong>${escapeHtml(advisor.name)}</strong><small>${escapeHtml(advisor.primary_field || "Chưa có lĩnh vực chính")}</small></span>
  </label>`).join("")}</div><div id="advisor-search-empty" class="empty-state compact" ${visibleCount ? "hidden" : ""}>Không tìm thấy giảng viên phù hợp.</div>`;
}

function quotaPreview() {
  const advisors = selectedCohortAdvisors();
  const studentCount = Number(state.cohort.preview?.student_count || 0);
  if (!studentCount || !advisors.length) return `<div class="empty-state compact">Tải file hợp lệ và tích giảng viên tham gia để xem quota.</div>`;
  const quotas = balancedQuotas(studentCount, advisors.map((advisor) => advisor.id));
  return `<div class="quota-summary"><p><strong>${studentCount} sinh viên</strong> chia cho <strong>${advisors.length} giảng viên</strong>. Chênh lệch tối đa 1 sinh viên.</p>
    <div class="quota-list">${quotas.map(({ id, quota }) => {
      const advisor = advisors.find((item) => item.id === id);
      return `<span><b>${escapeHtml(advisor?.name || id)}</b>${quota} SV</span>`;
    }).join("")}</div>
  </div>`;
}

function surveyDetails(survey) {
  if (!survey) return "";
  const labels = { class_name: "Lớp / khóa", major: "Ngành", project_experience: "Dự án và phần việc", project_links: "Minh chứng", preferred_fields: "Muốn tìm hiểu", learning_goals: "Muốn học thêm" };
  const context = Object.entries(survey.context || {}).filter(([, value]) => value);
  const levels = Object.entries(survey.skill_levels || {});
  return `<details><summary>Thông tin khảo sát</summary>
    ${levels.length ? `<p>Mức tự đánh giá (1–3): ${levels.map(([skill, level]) => `${escapeHtml(skill)}: ${escapeHtml(level)}`).join("; ")}. Chưa dùng mức này để tính điểm.</p>` : ""}
    ${context.map(([key, value]) => `<p><strong>${escapeHtml(labels[key] || key)}:</strong> ${escapeHtml(value)}</p>`).join("")}
  </details>`;
}

function cohortPreviewTable() {
  const students = state.cohort.preview?.students || [];
  if (!students.length) return "";
  return `<section class="results-card cohort-table"><header><div><h2>Xem trước ${students.length} sinh viên</h2><p>Kiểm tra mã, họ tên và kỹ năng đã chuẩn hóa trước khi phân bổ.</p></div></header>
    ${warningList(state.cohort.preview.warnings || [])}
    <div class="table-scroll"><table><thead><tr><th>Mã SV</th><th>Họ tên</th><th>Đề tài (tùy chọn)</th><th>Kỹ năng đã khai</th></tr></thead><tbody>${students.map((student) => `<tr>
      <td>${escapeHtml(student.student_id)}</td><td>${escapeHtml(student.student_name)}</td><td>${escapeHtml(student.thesis_title || "—")}</td>
      <td><div class="skill-list">${(student.skills || []).map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div>${surveyDetails(student.survey)}</td>
    </tr>`).join("")}</tbody></table></div>
  </section>`;
}

function cohortResult() {
  const result = state.cohort.result;
  if (!result) return "";
  const advisors = result.advisors || [];
  const assignments = result.assignments || [];
  return `<section class="cohort-result" aria-labelledby="cohort-result-title">
    <div class="result-heading"><div><h2 id="cohort-result-title">Kết quả phân bổ</h2><p>${escapeHtml(result.algorithm || "hungarian-balanced-v1")} · ${assignments.length} sinh viên</p></div><span class="run-badge">Đã lưu lần chạy</span></div>
    ${warningList(result.warnings || [])}
    <div class="advisor-loads">${advisors.map((advisor) => `<article><strong>${escapeHtml(advisor.name)}</strong><span>${escapeHtml(advisor.assigned)} / ${escapeHtml(advisor.quota)} sinh viên</span></article>`).join("")}</div>
    <div class="table-scroll"><table><thead><tr><th>Sinh viên</th><th>Giảng viên hướng dẫn</th><th>Điểm matching</th><th>Kỹ năng</th></tr></thead><tbody>${assignments.map((assignment) => `<tr>
      <td><strong>${escapeHtml(assignment.student_name)}</strong><small>${escapeHtml(assignment.student_id)}</small></td>
      <td>${escapeHtml(assignment.advisor_name)}</td><td>${assignment.score == null ? "—" : Number(assignment.score).toFixed(4)}</td>
      <td><div class="skill-list">${(assignment.skills || []).map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}</div></td>
    </tr>`).join("")}</tbody></table></div>
  </section>`;
}

function studentsView() {
  const studentCount = Number(state.cohort.preview?.student_count || 0);
  const selectedCount = state.cohort.selected.size;
  const allocationReady = canAllocate({ file: state.cohort.file, studentCount, selectedCount, busy: Boolean(state.cohort.busy) });
  return `${header()}<main id="main" class="page students-page">
    <section class="page-heading cohort-heading"><div><h1>Nhập sinh viên theo kỳ</h1><p>Khảo sát kỹ năng và framework đã sử dụng. Sinh viên chưa cần có đề tài để được phân bổ giảng viên.</p></div>
      <a class="button secondary template-link" href="/api/v1/student-cohorts/template" download>Tải file Excel mẫu</a>
    </section>
    ${state.cohort.error ? status(state.cohort.error, "error") : ""}
    <section class="cohort-layout">
      <article class="cohort-panel upload-panel">
        <div><h2>1. Tải danh sách sinh viên</h2><p>Điền sheet KhaoSat trong file mẫu: mã, họ tên và ít nhất một kỹ năng đã học hoặc đã dùng. Đề tài và mô tả có thể để trống. File SinhVien mẫu cũ vẫn được hỗ trợ.</p><p>Mức độ tự đánh giá, dự án và nguyện vọng được lưu riêng; kỹ năng muốn học thêm chưa được tính là kỹ năng hiện có.</p></div>
        <label class="file-drop" for="student-file"><span>${state.cohort.file ? escapeHtml(state.cohort.file.name) : "Chọn file .xlsx"}</span><small>Tối đa 5 MiB · 1.000 sinh viên</small></label>
        <input class="sr-only" id="student-file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ${state.cohort.busy ? "disabled" : ""}>
        ${state.cohort.busy === "preview" ? status("Đang kiểm tra dữ liệu trong file…") : state.cohort.preview ? status(`${studentCount} sinh viên hợp lệ. Bạn có thể chọn giảng viên và phân bổ.`) : ""}
      </article>
      <article class="cohort-panel advisor-panel">
        <div class="advisor-panel-heading"><div><h2>2. Chọn giảng viên hướng dẫn</h2><p><strong>${selectedCount}</strong> giảng viên được chọn cho kỳ này.</p></div>
          <div class="advisor-actions"><button id="select-all-advisors" class="text-button" type="button" ${state.cohort.busy ? "disabled" : ""}>Chọn tất cả</button><button id="clear-advisors" class="text-button" type="button" ${state.cohort.busy ? "disabled" : ""}>Bỏ chọn</button></div>
        </div>
        <label class="advisor-search">Tìm giảng viên<input id="advisor-search" type="search" value="${escapeHtml(state.cohort.search)}" placeholder="Ví dụ: Phạm Minh Hoàn" ${state.cohort.busy ? "disabled" : ""}></label>
        ${advisorChecklist()}
      </article>
    </section>
    <section class="cohort-panel quota-panel"><div><h2>3. Quota dự kiến</h2><p>Quota được chia đều trên đúng danh sách giảng viên đã tích.</p></div>${quotaPreview()}
      <button class="button primary allocate-button" id="allocate-cohort" type="button" ${allocationReady ? "" : "disabled"}>${state.cohort.busy === "allocate" ? "Đang phân bổ…" : "Phân bổ theo kỹ năng"}</button>
    </section>
    ${cohortPreviewTable()}
    ${cohortResult()}
  </main>`;
}

function checkpointInventory() {
  const models = compatibleModels(normalizeModels(), "real-train");
  if (!models.length) return `<div class="empty-state compact">Chưa có checkpoint phù hợp dữ liệu hiện tại. Semantic vẫn sử dụng được.</div>`;
  return `<div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>Seed</th><th>Bước đã train</th><th>Ngân sách yêu cầu</th><th>Trạng thái</th></tr></thead><tbody>${models.map(model => `<tr><td>${escapeHtml(model.algorithm)}</td><td>${escapeHtml(model.seed ?? "—")}</td><td>${Number(model.completed_timesteps || 0).toLocaleString("vi-VN")}</td><td>${model.requested_timesteps == null ? "—" : Number(model.requested_timesteps).toLocaleString("vi-VN")}</td><td>Nghiên cứu · chưa promote</td></tr>`).join("")}</tbody></table></div>`;
}

function resultsView() {
  const metrics = state.simulation?.metrics || {};
  const report = normalizeBenchmark(state.resultsSummary || {});
  const summaryTable = report.summary.length ? `<div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>Số seed đánh giá</th><th>Tương thích TB</th><th>Độ lệch chuẩn</th><th>Vi phạm hạn mức</th></tr></thead><tbody>${report.summary.map((item) => `<tr><td>${escapeHtml(item.algorithm)}</td><td>${item.seedCount ?? "—"}${item.seedCount < (state.resultsSummary?.seeds?.length || 5) ? " · chưa đủ seed" : ""}</td><td>${item.mean == null ? "—" : Number(item.mean).toFixed(4)}</td><td>${item.std == null ? "—" : Number(item.std).toFixed(4)}</td><td>${item.quotaViolations ?? "—"}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty-state compact">Chưa có benchmark tổng hợp cùng protocol.</div>`;
  const reportRows = report.rows.length ? `<details class="report-rows"><summary>Xem ${report.rows.length} hàng đánh giá theo seed</summary><div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>Seed</th><th>Tương thích</th><th>Vi phạm hạn mức</th></tr></thead><tbody>${report.rows.map((item) => `<tr><td>${escapeHtml(item.algorithm)}</td><td>${item.seed}</td><td>${item.mean == null ? "—" : Number(item.mean).toFixed(4)}</td><td>${item.quotaViolations ?? "—"}</td></tr>`).join("")}</tbody></table></div></details>` : "";
  return `${header()}<main id="main" class="page results-page">${state.error ? status(state.error, "error") : ""}<section class="page-heading"><div><p class="section-tag">Phiên hiện tại</p><h1>Kết quả ghép cặp</h1><p>Metadata và kết quả gần nhất trong phiên trình duyệt này.</p></div><button class="button secondary" id="refresh-data" ${state.busy ? "disabled" : ""}>${state.busy ? "Đang cập nhật…" : "Cập nhật dữ liệu / kết quả"}</button></section>
    <section class="metric-grid">${["mean_compatibility", "quota_violations", "invalid_proposals"].map((key) => `<article><span>${({ mean_compatibility: "Độ tương thích TB", quota_violations: "Vi phạm hạn mức", invalid_proposals: "Đề xuất không hợp lệ" })[key]}</span><strong>${metrics[key] == null ? "Chưa đánh giá" : key === "mean_compatibility" ? Number(metrics[key]).toFixed(4) : escapeHtml(metrics[key])}</strong></article>`).join("")}</section>
    <section class="results-card"><header><div><h2>Danh sách cặp ghép</h2><p>${escapeHtml(state.simulation?.data_version || "Chưa có dữ liệu lần chạy.")}</p></div></header>${resultsTable()}</section>
    <section class="results-card benchmark-report"><header><div><h2>Benchmark cùng protocol</h2><p>${escapeHtml(state.resultsSummary?.scope || "Chỉ hiển thị báo cáo backend đã công bố.")} · ${escapeHtml(state.resultsSummary?.split || "chưa xác định split")}</p></div><span class="run-badge">${state.resultsSummary?.selected_engine ? `Engine: ${escapeHtml(state.resultsSummary.selected_engine)}` : "Chưa chọn engine"}</span></header><p class="benchmark-context">${state.resultsSummary?.students ?? "—"} SV · ${state.resultsSummary?.advisors ?? "—"} GV · Cập nhật báo cáo: ${escapeHtml(state.resultsSummary?.created_at ? new Date(state.resultsSummary.created_at).toLocaleString("vi-VN") : "Chưa có")}<br>Kết quả đang được bổ sung. Các checkpoint có thể có ngân sách huấn luyện khác nhau; số seed đủ không đồng nghĩa đã train đủ ngân sách.</p>${summaryTable}${reportRows}</section>
    <section class="results-card"><header><div><h2>Checkpoint cho dữ liệu hiện tại</h2><p>Cập nhật để nhận checkpoint vừa hoàn tất; chỉ hiển thị bản có nhiều bước nhất cho mỗi thuật toán và seed.</p></div></header>${checkpointInventory()}</section>
    <section class="provenance"><h2>Nguồn và trạng thái</h2><pre>${escapeHtml(JSON.stringify(state.simulation?.provenance || { status: "Chưa có lần chạy" }, null, 2))}</pre></section>
  </main>`;
}

function render() {
  disposeHomeScene?.();
  disposeHomeScene = null;
  sceneObserver?.disconnect();
  scene?.dispose();
  scene = null;
  if (state.route === "/login" || !state.session) app.innerHTML = loginView();
  else if (state.route === "/matching") app.innerHTML = matchingView();
  else if (state.route === "/students") app.innerHTML = studentsView();
  else if (state.route === "/results") app.innerHTML = resultsView();
  else app.innerHTML = homeView();
  bindEvents();
  if (state.route === "/matching") setupScene();
  if (state.session && state.route === "/") disposeHomeScene = createHomeScene(document.querySelector("#home-network"), document.querySelector("#network-motion"));
}

function updateReplay(index) {
  state.replay.seek(index);
  scene?.setData(sceneData(), state.replay.index);
  const timeline = document.querySelector("#timeline");
  if (timeline) timeline.value = state.replay.index;
  const count = document.querySelector("#step-count");
  if (count) count.textContent = `Bước ${state.replay.index}/${state.simulation?.events?.length || 0}`;
  const panel = document.querySelector("#event-panel");
  if (panel) panel.innerHTML = currentEventPanel();
}

function stopPlayback() {
  state.playing = false;
  clearInterval(playTimer);
  playTimer = null;
}

function togglePlayback() {
  if (state.playing) { stopPlayback(); render(); return; }
  if (!state.simulation?.events?.length) return;
  state.playing = true;
  render();
  playTimer = setInterval(() => {
    if (state.replay.index >= state.simulation.events.length) {
      stopPlayback(); render(); return;
    }
    updateReplay(state.replay.next());
  }, 900 / state.speed);
}

function setupScene() {
  const canvas = document.querySelector("#matching-canvas");
  if (!canvas) return;
  scene = new MatchingScene(canvas);
  scene.setData(sceneData(), state.replay.index);
  sceneObserver = new ResizeObserver(() => scene?.draw());
  sceneObserver.observe(canvas);
}

async function loadDataset(id) {
  state.error = "";
  try {
    state.dataset = await api(`/datasets/${encodeURIComponent(id)}`);
  } catch (error) {
    state.dataset = null;
    state.error = error.message;
  }
}

async function loadResults() {
  try { state.resultsSummary = await api("/results/summary"); }
  catch (error) { state.resultsSummary = null; state.error = error.message; }
}

async function simulate() {
  const dataset = selectedDatasetId();
  const selectedId = selectedAlgorithm();
  const selectedModel = normalizeModels().find((model) => model.id === selectedId);
  const algorithm = state.mode === "rl" ? selectedModel?.algorithm : selectedId;
  const requestMode = state.mode === "rl" ? modelMode(selectedModel) : state.mode;
  const seed = state.mode === "rl" ? selectedModel?.seed : Number(document.querySelector("#seed-input")?.value || 42);
  state.busy = true; state.error = ""; render();
  try {
    if (!state.dataset || state.dataset.id !== dataset) await loadDataset(dataset);
    if (!state.dataset) throw new Error(state.error || "Không tải được dữ liệu.");
    state.simulation = await api("/simulate", { method: "POST", body: JSON.stringify({ mode: requestMode, algorithm, dataset, seed }) });
    state.simulationMode = requestMode;
    state.replay = createReplay(state.simulation.events?.length || 0);
  } catch (error) {
    state.simulation = null;
    state.simulationMode = null;
    state.error = error.message;
  } finally {
    state.busy = false; render();
  }
}

function clearPrivateState() {
  state.session = null;
  state.catalog = null;
  state.dataset = null;
  state.simulation = null;
  state.simulationMode = null;
  state.resultsSummary = null;
  state.cohort = { advisors: null, selected: new Set(), search: "", file: null, preview: null, result: null, busy: "", error: "" };
}

async function loadCohortAdvisors() {
  state.cohort.busy = "advisors";
  state.cohort.error = "";
  if (state.route === "/students") render();
  try {
    const payload = await api("/student-cohorts/advisors");
    state.cohort.advisors = (payload.advisors || []).map((advisor) => ({ ...advisor, id: String(advisor.id) }));
  } catch (error) {
    state.cohort.advisors = [];
    if (state.session) state.cohort.error = error.message;
  } finally {
    state.cohort.busy = "";
  }
}

async function previewStudentFile(file) {
  state.cohort.file = file;
  state.cohort.preview = null;
  state.cohort.result = null;
  state.cohort.error = "";
  state.cohort.busy = "preview";
  render();
  try {
    state.cohort.preview = await api("/student-cohorts/preview", {
      method: "POST",
      headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      body: file,
    });
  } catch (error) {
    if (state.session) state.cohort.error = error.message;
  } finally {
    state.cohort.busy = "";
    render();
  }
}

async function allocateCohort() {
  const advisorIds = selectedCohortAdvisors().map((advisor) => advisor.id);
  if (!canAllocate({ file: state.cohort.file, studentCount: state.cohort.preview?.student_count, selectedCount: advisorIds.length, busy: Boolean(state.cohort.busy) })) return;
  state.cohort.busy = "allocate";
  state.cohort.error = "";
  state.cohort.result = null;
  render();
  try {
    state.cohort.result = await api(`/student-cohorts/allocate?${advisorQuery(advisorIds)}`, {
      method: "POST",
      headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      body: state.cohort.file,
    });
  } catch (error) {
    if (state.session) state.cohort.error = error.message;
  } finally {
    state.cohort.busy = "";
    render();
  }
}

function bindEvents() {
  document.querySelector("#refresh-data")?.addEventListener("click", async () => {
    state.busy = true; state.error = ""; render();
    try {
      state.health = await api("/health");
      state.catalog = await api("/catalog");
      await loadResults();
    } catch (error) { state.error = error.message; }
    finally { state.busy = false; render(); }
  });
  document.querySelectorAll("[data-route]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.route)));
  document.querySelector("#login-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    state.busy = true; state.error = ""; render();
    try { await api("/auth/login", { method: "POST", body: JSON.stringify(body) }); await initializeSession(); navigate("/"); }
    catch (error) { state.error = error.message; }
    finally { state.busy = false; render(); }
  });
  document.querySelector("#logout")?.addEventListener("click", async () => {
    try { await api("/auth/logout", { method: "POST" }); }
    catch (error) { state.error = error.message; render(); return; }
    clearPrivateState(); navigate("/login");
  });
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
    stopPlayback(); state.mode = button.dataset.mode; state.simulation = null; state.simulationMode = null; state.replay = createReplay(0); render();
  }));
  document.querySelector("#dataset-select")?.addEventListener("change", async (event) => {
    const datasetId = event.target.value;
    stopPlayback(); state.busy = true; render(); await loadDataset(datasetId); state.simulation = null; state.simulationMode = null; state.replay = createReplay(0); state.busy = false; render();
  });
  document.querySelector("#simulate")?.addEventListener("click", simulate);
  document.querySelector("#algorithm-select")?.addEventListener("change", (event) => {
    if (state.mode === "rl") document.querySelector("#seed-input").value = normalizeModels().find((model) => model.id === event.target.value)?.seed ?? "";
  });
  document.querySelector("#play")?.addEventListener("click", togglePlayback);
  document.querySelector("#previous")?.addEventListener("click", () => updateReplay(state.replay.previous()));
  document.querySelector("#next")?.addEventListener("click", () => updateReplay(state.replay.next()));
  document.querySelector("#reset-replay")?.addEventListener("click", () => { stopPlayback(); updateReplay(state.replay.reset()); });
  document.querySelector("#reset-view")?.addEventListener("click", () => scene?.resetView());
  document.querySelector("#timeline")?.addEventListener("input", (event) => { stopPlayback(); updateReplay(event.target.value); });
  document.querySelector("#speed")?.addEventListener("change", (event) => { state.speed = Number(event.target.value); if (state.playing) { stopPlayback(); togglePlayback(); } });
  document.querySelector("#student-file")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) previewStudentFile(file);
  });
  document.querySelector(".advisor-checklist")?.addEventListener("change", (event) => {
    if (event.target.name !== "advisor") return;
    if (event.target.checked) state.cohort.selected.add(event.target.value);
    else state.cohort.selected.delete(event.target.value);
    state.cohort.result = null;
    render();
  });
  document.querySelector("#select-all-advisors")?.addEventListener("click", () => {
    state.cohort.selected = new Set((state.cohort.advisors || []).map((advisor) => advisor.id));
    state.cohort.result = null;
    render();
  });
  document.querySelector("#clear-advisors")?.addEventListener("click", () => {
    state.cohort.selected.clear();
    state.cohort.result = null;
    render();
  });
  document.querySelector("#advisor-search")?.addEventListener("input", (event) => {
    state.cohort.search = event.target.value;
    let visibleCount = 0;
    document.querySelectorAll(".advisor-checklist label").forEach((label) => {
      const advisor = (state.cohort.advisors || []).find((item) => item.id === label.querySelector("input")?.value);
      label.hidden = !advisor || !advisorMatches(advisor, state.cohort.search);
      if (!label.hidden) visibleCount += 1;
    });
    const empty = document.querySelector("#advisor-search-empty");
    if (empty) empty.hidden = visibleCount > 0;
  });
  document.querySelector("#allocate-cohort")?.addEventListener("click", allocateCohort);
}

async function initializeSession() {
  try { state.health = await api("/health"); } catch { state.health = null; }
  try {
    const session = await api("/auth/session");
    state.session = session.authenticated === false ? null : (session.user || session);
  } catch { state.session = null; }
  try { state.catalog = await api("/catalog"); } catch (error) { if (state.session) state.error = error.message; }
  if (state.route === "/matching" && state.catalog) await loadDataset(preferredDataset(normalizeDatasets(), state.health?.data_loaded === true));
  if (state.route === "/students" && state.session) await loadCohortAdvisors();
  if (state.session) await loadResults();
}

window.addEventListener("hashchange", async () => {
  stopPlayback(); state.route = location.hash.slice(1) || "/";
  if (state.route === "/results" && state.session) await loadResults();
  if (state.route === "/matching" && state.session && !state.dataset) await loadDataset(preferredDataset(normalizeDatasets(), state.health?.data_loaded === true));
  if (state.route === "/students" && state.session && !state.cohort.advisors) await loadCohortAdvisors();
  render();
});

app.innerHTML = `<main class="loading-screen"><div class="spinner" aria-hidden="true"></div><p>Đang kiểm tra phiên và danh mục dữ liệu…</p></main>`;
initializeSession().finally(render);
