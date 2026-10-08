import { createReplay, MatchingScene, normalizeBenchmark, replayStateAt } from "./visualization.js";

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
};
let scene = null;
let playTimer = null;

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
  if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || payload?.message || `Yêu cầu thất bại (${response.status}).`);
  return unwrap(payload);
}

const routeLabels = { "/": "Trang chủ", "/matching": "Ghép cặp", "/results": "Kết quả" };

function navigate(route) {
  location.hash = route;
}

function header() {
  return `<header class="topbar">
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
  const models = state.catalog?.models || [];
  return `${header()}<main id="main" class="page home-page">
    ${state.error ? status(state.error, "error") : ""}
    <section class="hero">
      <div>
        <p class="section-tag">Ghép cặp có bằng chứng</p>
        <h1>Tìm giảng viên phù hợp với đề tài của bạn</h1>
        <p>So sánh độ tương đồng, phân bổ theo hạn mức và khám phá cách từng thuật toán ra quyết định.</p>
        <button class="button primary" data-route="/matching">Bắt đầu ghép cặp</button>
      </div>
      <dl class="overview">
        <div><dt>Dữ liệu</dt><dd>${datasets.length || "—"}</dd><small>tập có thể chọn</small></div>
        <div><dt>Checkpoint</dt><dd>${models.filter((model) => model.status !== "invalid" && !model.smoke).length || "—"}</dd><small>chỉ nghiên cứu · chưa promote</small></div>
        <div><dt>Phiên</dt><dd>${state.session ? "Có" : "Mẫu"}</dd><small>${state.session ? "đã xác thực" : "chưa đăng nhập"}</small></div>
      </dl>
    </section>
    <section class="method-grid" aria-labelledby="method-title">
      <h2 id="method-title" class="sr-only">Ba phương pháp ghép cặp</h2>
      <article><span class="method-icon">⌕</span><h3>Semantic</h3><p>Biểu diễn nội dung đề tài và hồ sơ bằng vector ngữ nghĩa, rồi xếp hạng theo độ tương đồng.</p></article>
      <article><span class="method-icon">⚙</span><h3>Model đã train</h3><p>Chỉ bật khi catalog xác nhận có artifact non-RL tương thích với dữ liệu đang chọn.</p></article>
      <article><span class="method-icon">⌘</span><h3>Reinforcement Learning</h3><p>Xem từng hành động ghép cặp, hạn mức và fallback từ trace do API trả về.</p></article>
      <article class="baseline-card"><h3>Kết quả baseline</h3><p>${state.resultsSummary ? `${escapeHtml(state.resultsSummary.students)} SV · ${escapeHtml(state.resultsSummary.advisors)} GV · ${escapeHtml(state.resultsSummary.split)}` : "Chưa có báo cáo"}</p><div class="bars">${baselineRows()}</div><small>Độ tương thích trung bình; không phải xác suất.</small></article>
    </section>
    <section class="evidence-note"><strong>Đọc kết quả đúng ngữ cảnh.</strong><span>Metric baseline và trạng thái checkpoint RL là hai loại bằng chứng khác nhau; RL chưa benchmark sẽ hiển thị “Chưa đánh giá”.</span></section>
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
    : { ...model, id: model.id || model.algorithm, name: model.name || `${model.algorithm} · seed ${model.seed ?? "—"} · ${model.research ? "nghiên cứu" : "mẫu"}` });
}

function supportsDataset(model, datasetId) {
  const supported = model.supported_datasets || model.supports_datasets || model.datasets;
  return model.available !== false && model.status !== "invalid" && !model.smoke && (!Array.isArray(supported) || supported.includes(datasetId));
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
  return dataset.name || dataset.label || labels[dataset.id] || dataset.id;
}

function selectedDatasetId() {
  return document.querySelector("#dataset-select")?.value || normalizeDatasets()[0]?.id || "sample-3x2";
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
  const datasetId = datasets.some((item) => item.id === state.dataset?.id) ? state.dataset.id : datasets[0]?.id;
  const algorithms = state.mode === "semantic"
    ? [{ id: "greedy", name: "Greedy" }, { id: "hungarian", name: "Hungarian" }, { id: "random", name: "Random" }]
    : normalizeModels().filter((model) => supportsDataset(model, datasetId));
  return `<label>Dữ liệu<select id="dataset-select">${datasets.map((item) => `<option value="${escapeHtml(item.id)}" ${item.id === datasetId ? "selected" : ""}>${escapeHtml(datasetLabel(item))}</option>`).join("")}</select></label>
    <label>${state.mode === "rl" ? "Model / checkpoint" : "Thuật toán"}<select id="algorithm-select" ${state.mode === "non_rl" ? "disabled" : ""}>${algorithms.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.algorithm || item.id)}</option>`).join("")}</select></label>
    <label>Seed<input id="seed-input" type="number" value="${state.mode === "rl" ? (algorithms[0]?.seed ?? 42) : 42}" min="0" max="2147483647" ${state.mode === "rl" ? "disabled" : ""}></label>
    <button class="button primary" id="simulate" ${state.busy || state.mode === "non_rl" || !algorithms.length || (datasetId?.startsWith("real-") && state.health?.data_loaded !== true) ? "disabled" : ""}>${state.busy ? "Đang mô phỏng…" : "Bắt đầu mô phỏng"}</button>
    ${state.catalog?.quality?.ready === false ? `<p class="control-warning">Dữ liệu là subset đã kiểm tra; hạn mức GV chỉ là giả định thực nghiệm, chưa đủ điều kiện triển khai thực tế.</p>` : ""}
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
    <div><dt>Trạng thái</dt><dd>${escapeHtml(event.student_id || "—")} đang chờ</dd></div>
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
      <article class="viewport-card"><header><h2>Mô phỏng 3D</h2><span class="sample-badge">${state.dataset?.sample ? "Mẫu minh họa" : "Dữ liệu từ API"}</span></header>
        <canvas id="matching-canvas" tabindex="0" aria-label="Mô phỏng 3D. Kéo để xoay, cuộn để thu phóng, dùng phím mũi tên trái phải để đổi góc nhìn."></canvas>
        <div class="legend"><span class="candidate">Ứng viên</span><span class="matched">Đã ghép</span><span class="invalid">Không hợp lệ / fallback</span></div>
        <div class="playback">
          <button id="play" type="button" aria-label="${state.playing ? "Tạm dừng" : "Phát"}">${state.playing ? "Ⅱ" : "▶"}</button>
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

function resultsView() {
  const metrics = state.simulation?.metrics || {};
  const report = normalizeBenchmark(state.resultsSummary || {});
  const summaryTable = report.summary.length ? `<div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>Số seed</th><th>Tương thích TB</th><th>Độ lệch chuẩn</th><th>Vi phạm hạn mức</th></tr></thead><tbody>${report.summary.map((item) => `<tr><td>${escapeHtml(item.algorithm)}</td><td>${item.seedCount ?? "—"}</td><td>${item.mean == null ? "—" : Number(item.mean).toFixed(4)}</td><td>${item.std == null ? "—" : Number(item.std).toFixed(4)}</td><td>${item.quotaViolations ?? "—"}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty-state compact">Chưa có benchmark tổng hợp cùng protocol.</div>`;
  const reportRows = report.rows.length ? `<details class="report-rows"><summary>Xem ${report.rows.length} hàng đánh giá theo seed</summary><div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>Seed</th><th>Tương thích</th><th>Vi phạm hạn mức</th></tr></thead><tbody>${report.rows.map((item) => `<tr><td>${escapeHtml(item.algorithm)}</td><td>${item.seed}</td><td>${item.mean == null ? "—" : Number(item.mean).toFixed(4)}</td><td>${item.quotaViolations ?? "—"}</td></tr>`).join("")}</tbody></table></div></details>` : "";
  return `${header()}<main id="main" class="page results-page">${state.error ? status(state.error, "error") : ""}<section class="page-heading"><div><p class="section-tag">Phiên hiện tại</p><h1>Kết quả ghép cặp</h1><p>Metadata và kết quả gần nhất trong phiên trình duyệt này.</p></div><button class="button secondary" data-route="/matching">Quay lại mô phỏng</button></section>
    <section class="metric-grid">${["mean_compatibility", "quota_violations", "invalid_proposals"].map((key) => `<article><span>${({ mean_compatibility: "Độ tương thích TB", quota_violations: "Vi phạm hạn mức", invalid_proposals: "Đề xuất không hợp lệ" })[key]}</span><strong>${metrics[key] ?? "Chưa đánh giá"}</strong></article>`).join("")}</section>
    <section class="results-card"><header><div><h2>Danh sách cặp ghép</h2><p>${escapeHtml(state.simulation?.data_version || "Chưa có dữ liệu lần chạy.")}</p></div></header>${resultsTable()}</section>
    <section class="results-card benchmark-report"><header><div><h2>Benchmark cùng protocol</h2><p>${escapeHtml(state.resultsSummary?.scope || "Chỉ hiển thị báo cáo backend đã công bố.")} · ${escapeHtml(state.resultsSummary?.split || "chưa xác định split")}</p></div><span class="run-badge">${state.resultsSummary?.selected_engine ? `Engine: ${escapeHtml(state.resultsSummary.selected_engine)}` : "Chưa chọn engine"}</span></header>${summaryTable}${reportRows}</section>
    <section class="provenance"><h2>Nguồn và trạng thái</h2><pre>${escapeHtml(JSON.stringify(state.simulation?.provenance || { status: "Chưa có lần chạy" }, null, 2))}</pre></section>
  </main>`;
}

function render() {
  if (state.route === "/login" || !state.session) app.innerHTML = loginView();
  else if (state.route === "/matching") app.innerHTML = matchingView();
  else if (state.route === "/results") app.innerHTML = resultsView();
  else app.innerHTML = homeView();
  bindEvents();
  if (state.route === "/matching") setupScene();
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
  new ResizeObserver(() => scene?.draw()).observe(canvas);
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

function bindEvents() {
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
    state.session = null; state.catalog = null; state.simulation = null; state.simulationMode = null; navigate("/login");
  });
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
    stopPlayback(); state.mode = button.dataset.mode; state.simulation = null; state.simulationMode = null; state.replay = createReplay(0); render();
  }));
  document.querySelector("#dataset-select")?.addEventListener("change", async (event) => {
    const datasetId = event.target.value;
    state.busy = true; render(); await loadDataset(datasetId); state.simulation = null; state.simulationMode = null; state.replay = createReplay(0); state.busy = false; render();
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
}

async function initializeSession() {
  try { state.health = await api("/health"); } catch { state.health = null; }
  try {
    const session = await api("/auth/session");
    state.session = session.authenticated === false ? null : (session.user || session);
  } catch { state.session = null; }
  try { state.catalog = await api("/catalog"); } catch (error) { if (state.session) state.error = error.message; }
  if (state.route === "/matching" && state.catalog) await loadDataset(normalizeDatasets()[0]?.id || "sample-3x2");
  if (state.session) await loadResults();
}

window.addEventListener("hashchange", async () => {
  stopPlayback(); state.route = location.hash.slice(1) || "/";
  if (state.route === "/results" && state.session) await loadResults();
  render();
});

app.innerHTML = `<main class="loading-screen"><div class="spinner" aria-hidden="true"></div><p>Đang kiểm tra phiên và danh mục dữ liệu…</p></main>`;
initializeSession().finally(render);
