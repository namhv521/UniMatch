const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
const percent = value => value == null ? 'Chưa có điểm' :
  (value * 100).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + '%';
const reasons = {
  outside: 'Ngoài danh sách tham gia',
  fixed: 'Sinh viên đã được giảng viên khác nhận',
  rejected: 'Giảng viên đã từ chối',
  full: 'Hết chỗ',
  future: 'Giữ chỗ để đảm bảo phân đủ các sinh viên còn lại',
};

export function mountReplay(root, {runs, quotas = [], studentName, advisorName, initial}) {
  const available = Object.entries(runs || {}).filter(([, run]) => run?.trace?.length);
  if (!available.length) {
    root.innerHTML = '<p class="empty-state">Chưa có dữ liệu từng bước. Hãy chạy phân công để xem phát lại 3D &amp; 2D.</p>';
    return () => {};
  }
  const runMap = new Map(available);
  let algorithm = runMap.has(initial) ? initial : available[0][0];
  let step = 0;
  let timer;
  let scene3d = null;
  let show3d = true;
  let destroyed = false;

  root.innerHTML = `
    <p class="help">Quan sát trực quan quá trình gán từng sinh viên trên sân khấu 3D khuôn viên kết hợp bảng kiểm tra ràng buộc 2D theo thời gian thực.</p>
    <div class="allocation-player-controls">
      ${available.length > 1 ? `<label>Phương án mô hình <select data-replay-model>${available.map(([key]) =>
        `<option value="${escape(key)}" ${key === algorithm ? 'selected' : ''}>${escape(key.toUpperCase())}</option>`).join('')}</select></label>` : ''}
      <label>Đi tới bước <select data-replay-step></select></label>
      <label class="allocation-speed">Tốc độ <select data-replay-speed><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
      <div class="allocation-player-buttons">
        <button type="button" class="secondary" data-replay-action="previous">◀ Bước trước</button>
        <button type="button" class="primary" data-replay-action="play">▶ Phát</button>
        <button type="button" class="secondary" data-replay-action="next">Bước tiếp ▶</button>
        <button type="button" class="secondary" data-replay-toggle3d>Ẩn cảnh 3D</button>
      </div>
    </div>
    <div class="replay-stage-3d" data-stage-3d>
      <canvas data-replay-canvas aria-label="Sân khấu mô phỏng phân công 3D"></canvas>
      <div class="replay-stage-bar">
        <span data-stage-caption>Mô phỏng 3D khuôn viên: nhân vật sinh viên di chuyển tới trạm giảng viên được chọn ở mỗi bước.</span>
        <button type="button" class="secondary" data-replay-motion style="min-height:30px;padding:3px 10px;font-size:.76rem" hidden>Tạm dừng 3D</button>
      </div>
    </div>
    <div class="allocation-progress">
      <progress data-replay-progress aria-label="Số sinh viên đã phân"></progress>
      <output data-replay-count aria-live="off"></output>
    </div>
    <div data-replay-body></div>`;

  const find = selector => root.querySelector(selector);
  const jump = find('[data-replay-step]');
  const previous = find('[data-replay-action="previous"]');
  const next = find('[data-replay-action="next"]');
  const play = find('[data-replay-action="play"]');
  const toggle3dBtn = find('[data-replay-toggle3d]');
  const stage3dBox = find('[data-stage-3d]');
  const canvas3d = find('[data-replay-canvas]');
  const motionBtn = find('[data-replay-motion]');
  const progress = find('[data-replay-progress]');
  const speed = find('[data-replay-speed]');
  const body = find('[data-replay-body]');
  const quotaByAdvisor = new Map(quotas.map(q => [q.advisor_id, q]));
  const number = value => Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 4});

  function stopPlayback() {
    clearInterval(timer);
    timer = undefined;
    if (play) play.textContent = '▶ Phát';
  }

  function setOptions() {
    const trace = runMap.get(algorithm).trace;
    jump.replaceChildren(
      new Option('0 · Chuẩn bị chỉ tiêu ban đầu', '0'),
      ...trace.map((row, i) => new Option(`${i + 1} · ${studentName(row.student_id)}`, String(i + 1))),
      new Option(`${trace.length + 1} · Tổng kết hoàn tất`, String(trace.length + 1)),
    );
  }

  function sync3d() {
    if (!scene3d || !show3d) return;
    const run = runMap.get(algorithm);
    const {trace} = run;
    const first = trace[0] || {};
    const registry = first.advisor_registry ?? first.advisor_ids ?? [];
    const capacities = first.capacities ?? [];
    const names = registry.map(id => advisorName(id));
    const final = step > trace.length;
    const decision = step && !final ? { ...trace[step - 1], capacities } : (final && trace.length ? { ...trace.at(-1), capacities } : null);
    scene3d.update(decision, registry, names, step, capacities);
  }

  // Lazy mount 3D scene if supported
  (async () => {
    try {
      const {createCampus} = await import('./campus-scene.js');
      if (destroyed || !canvas3d?.isConnected) return;
      scene3d = createCampus(canvas3d, { replay: true });
      if (!scene3d) {
        stage3dBox.hidden = true;
        toggle3dBtn.hidden = true;
        return;
      }
      motionBtn.hidden = false;
      motionBtn.textContent = scene3d.paused ? 'Bật chuyển động 3D' : 'Tạm dừng 3D';
      motionBtn.addEventListener('click', () => {
        motionBtn.textContent = scene3d.toggle() ? 'Bật chuyển động 3D' : 'Tạm dừng 3D';
      });
      sync3d();
    } catch {
      if (stage3dBox) stage3dBox.hidden = true;
      if (toggle3dBtn) toggle3dBtn.hidden = true;
    }
  })();

  toggle3dBtn?.addEventListener('click', () => {
    show3d = !show3d;
    stage3dBox.hidden = !show3d;
    toggle3dBtn.textContent = show3d ? 'Ẩn cảnh 3D' : 'Hiện cảnh 3D';
    if (show3d) sync3d();
  });

  function draw() {
    const run = runMap.get(algorithm);
    const {trace} = run;
    const final = step > trace.length;
    const decision = step && !final ? trace[step - 1] : null;
    const first = trace[0];
    const registry = first.advisor_registry ?? first.advisor_ids ?? [];
    const capacities = first.capacities ?? [];
    const end = trace.at(-1);
    const completed = Math.min(step, trace.length);
    const loads = decision?.loads_after ?? (final ? end.loads_after : registry.map(() => 0));
    const before = decision?.loads_before ?? registry.map(() => 0);
    const considered = registry.map((id, i) => ({id, i, limit: capacities[i] ?? 0, quota: quotaByAdvisor.get(id)}))
      .filter(row => row.limit > 0 || row.quota);
    const allowed = decision?.pre_action_mask?.filter(Boolean).length ?? 0;
    const chosenBefore = decision ? before[registry.indexOf(decision.advisor_id)] : 0;
    const chosenCapacity = decision ? capacities[registry.indexOf(decision.advisor_id)] : 0;
    progress.max = trace.length;
    progress.value = completed;
    jump.value = String(step);
    previous.disabled = step === 0;
    next.disabled = final;
    find('[data-replay-count]').textContent = `Đã phân ${completed}/${trace.length} SV · còn ${trace.length - completed}`;
    const detailsOpen = body.querySelector('details[data-options]')?.open;
    const metrics = run.metrics ?? {};
    const policy = decision?.policy_output;
    const policyLabel = {masked_policy_probability: 'Xác suất chọn (PPO)', q_value_not_probability: 'Giá trị Q (DQN)'}[policy?.kind];
    const remaining = considered.reduce((sum, row) => sum + row.limit - (loads[row.i] ?? 0), 0);
    const stage = decision ? `<h3>Bước ${step} · ${escape(studentName(decision.student_id))}</h3>
      <p class="allocation-chosen">Đề xuất ghép với: <strong>${escape(advisorName(decision.advisor_id))}</strong></p>
      <dl class="allocation-facts">
        <div><dt>Điểm tương thích E4</dt><dd>${percent(decision.score_known ? decision.score : null)}</dd></div>
        <div><dt>Phương án hợp lệ</dt><dd>${allowed} giảng viên</dd></div>
        <div><dt>Số suất trống của GV</dt><dd>${chosenCapacity - chosenBefore} → ${chosenCapacity - chosenBefore - 1}</dd></div>
      </dl>
      <p class="help">${decision.fixed ? '✓ Cặp đã được giảng viên nhận hướng dẫn trước khi chạy tối ưu.' :
        decision.policy_output?.kind === 'quota_only_random' ? 'Ghép theo các suất khả thi còn lại (hồ sơ chưa có đặc trưng điểm).' :
        'Action mask đảm bảo không vượt chỉ tiêu và không làm bế tắc các sinh viên kế tiếp.'}
        ${decision.preference_known ? ` · Có trọng số nguyện vọng (${percent(decision.preference)}).` : ''}</p>` :
      final ? `<h3>Tổng kết hoàn tất (${escape(algorithm.toUpperCase())})</h3><p>Đã phân công đủ <strong>${completed}</strong> sinh viên · còn dư ${remaining} chỗ.
        ${metrics.constraint_violations === 0 ? '✓ Kiểm chứng 0 vi phạm ràng buộc chỉ tiêu.' : ''}</p>` :
      `<h3>Trạng thái chuẩn bị trước phân công</h3><p><strong>${trace.length}</strong> sinh viên trong hàng đợi · tổng <strong>${remaining}</strong> chỗ hướng dẫn khả dụng.</p>`;

    body.innerHTML = `${stage}
      <div class="table-scroll" tabindex="0" role="region" aria-label="${decision ? 'Số chỗ trước và sau bước' : 'Chỉ tiêu theo giảng viên'}">
        <table><caption>${decision ? 'Biến động chỉ tiêu ở bước hiện tại' : 'Phân bổ chỉ tiêu hướng dẫn'}</caption>
          <thead><tr><th scope="col">Giảng viên</th><th scope="col">Chỉ tiêu tổng</th>
            ${decision ? '<th scope="col">Trống trước bước</th>' : quotas.length ? '<th scope="col">Đã nhận trước</th><th scope="col">Chia thêm</th>' : ''}
            <th scope="col">${step === 0 ? 'Trống ban đầu' : 'Trống sau bước'}</th></tr></thead>
          <tbody>${considered.map(({id, i, limit, quota}) => `<tr ${id === decision?.advisor_id ? 'class="allocation-selected"' : ''}>
            <th scope="row">${escape(advisorName(id))}</th><td>${limit}</td>
            ${decision ? `<td>${limit - (before[i] ?? 0)}</td>` : quotas.length ? `<td>${quota?.accepted ?? 0}</td><td>${quota?.remaining ?? limit}</td>` : ''}
            <td>${limit - (loads[i] ?? 0)}</td></tr>`).join('')}</tbody></table>
      </div>
      ${decision ? `<details class="xai-details-panel" data-options ${detailsOpen ? 'open' : ''}><summary>Giải thích lựa chọn &amp; ràng buộc Action Mask ở bước này</summary>
        <div class="table-scroll" tabindex="0" role="region" aria-label="Lựa chọn ở bước hiện tại"><table>
          <thead><tr><th scope="col">Giảng viên</th><th scope="col">Điểm E4</th><th scope="col">Trạng thái hợp lệ</th>
            ${policyLabel ? `<th scope="col">${policyLabel}</th>` : ''}</tr></thead>
          <tbody>${considered.map(({id, i, limit}) => {
            const eligible = decision.pre_action_mask?.[i];
            const reason = reasons[decision.blocked_reasons?.[i]] ??
              ((before[i] ?? 0) >= limit ? reasons.full : 'Bị ràng buộc ở bước này');
            const candidateScore = decision.candidate_scores?.[i] ?? (id === decision.advisor_id && decision.score_known ? decision.score : null);
            return `<tr ${id === decision.advisor_id ? 'class="allocation-selected"' : ''}><th scope="row">${escape(advisorName(id))}</th><td>${percent(candidateScore)}</td>
              <td>${id === decision.advisor_id ? '✓ Được chọn' : eligible ? 'Khả thi' : reason}</td>
              ${policyLabel ? `<td>${eligible && Number.isFinite(policy.values?.[i]) ?
                (policy.kind === 'masked_policy_probability' ? percent(policy.values[i]) : number(policy.values[i])) : '—'}</td>` : ''}</tr>`;
          }).join('')}</tbody></table></div></details>
        ${decision.reward_components ? `<details class="xai-details-panel"><summary>Phân rã hàm phần thưởng (Step Reward Breakdown)</summary>
          <div class="xai-breakdown"><div class="xai-kv-grid">
            <div class="xai-kv"><span>Độ tương thích (Score)</span><strong>${number(decision.reward_components.score)}</strong></div>
            <div class="xai-kv"><span>Thưởng nguyện vọng</span><strong>${number(decision.reward_components.preference)}</strong></div>
            <div class="xai-kv"><span>Cân bằng tải (Fairness)</span><strong>${number(decision.reward_components.fairness)}</strong></div>
            <div class="xai-kv"><span>Hoàn tất đợt (Terminal)</span><strong>${number(decision.reward_components.terminal_completion)}</strong></div>
          </div></div></details>` : ''}` : ''}`;
    sync3d();
  }

  function seek(offset) {
    stopPlayback();
    step = offset;
    draw();
  }
  jump.addEventListener('change', () => seek(Number(jump.value)));
  previous.addEventListener('click', () => seek(step - 1));
  next.addEventListener('click', () => seek(step + 1));
  find('[data-replay-model]')?.addEventListener('change', event => {
    algorithm = event.target.value;
    setOptions();
    seek(0);
  });
  function start() {
    const length = runMap.get(algorithm).trace.length;
    if (step > length) seek(0);
    play.textContent = '⏸ Tạm dừng';
    timer = setInterval(() => {
      if (!root.isConnected) { stopPlayback(); return; }
      step++;
      draw();
      if (step > length) stopPlayback();
    }, 1500 / Number(speed.value));
  }
  play.addEventListener('click', () => {
    if (timer !== undefined) stopPlayback();
    else start();
  });
  speed.addEventListener('change', () => { if (timer !== undefined) { stopPlayback(); start(); } });
  setOptions();
  draw();
  return () => {
    destroyed = true;
    stopPlayback();
    if (scene3d) {
      scene3d.destroy();
      scene3d = null;
    }
  };
}
