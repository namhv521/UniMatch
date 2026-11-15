const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
const percent = value => value == null ? 'Chưa có điểm' :
  (value * 100).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + '%';
const reasons = {outside: 'Ngoài danh sách tham gia', fixed: 'Sinh viên đã được giảng viên khác nhận',
  rejected: 'Giảng viên đã từ chối', full: 'Hết chỗ', future: 'Cần giữ chỗ để phân đủ các sinh viên còn lại'};

export function mountReplay(root, {runs, quotas = [], studentName, advisorName, initial}) {
  const available = Object.entries(runs).filter(([, run]) => run?.trace?.length);
  if (!available.length) {
    root.innerHTML = '<p class="empty-state">Chưa có dữ liệu từng bước. Chạy phân công để bắt đầu phát lại.</p>';
    return () => {};
  }
  const runMap = new Map(available);
  let algorithm = runMap.has(initial) ? initial : available[0][0];
  let step = 0;
  let timer;
  root.innerHTML = `
    <p class="help">Xem chỉ tiêu ban đầu, từng quyết định và tổng kết. Tiến độ và số chỗ lấy từ lần chạy đã lưu.</p>
    <div class="allocation-player-controls">
      ${available.length > 1 ? `<label>Phương án <select data-replay-model>${available.map(([key]) =>
        `<option value="${escape(key)}" ${key === algorithm ? 'selected' : ''}>${escape(key.toUpperCase())}</option>`).join('')}</select></label>` : ''}
      <label>Đi tới bước <select data-replay-step></select></label>
      <label class="allocation-speed">Tốc độ <select data-replay-speed><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
      <div class="allocation-player-buttons">
        <button type="button" class="secondary" data-replay-action="previous">Bước trước</button>
        <button type="button" class="primary" data-replay-action="play">Phát</button>
        <button type="button" class="secondary" data-replay-action="next">Bước tiếp</button>
      </div>
    </div>
    <div class="allocation-progress"><progress data-replay-progress aria-label="Số sinh viên đã phân"></progress>
      <output data-replay-count aria-live="off"></output></div>
    <div data-replay-body></div>`;

  const find = selector => root.querySelector(selector);
  const jump = find('[data-replay-step]');
  const previous = find('[data-replay-action="previous"]');
  const next = find('[data-replay-action="next"]');
  const play = find('[data-replay-action="play"]');
  const progress = find('[data-replay-progress]');
  const speed = find('[data-replay-speed]');
  const body = find('[data-replay-body]');
  const quotaByAdvisor = new Map(quotas.map(q => [q.advisor_id, q]));
  const number = value => Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 4});

  function stop() {
    clearInterval(timer);
    timer = undefined;
    play.textContent = 'Phát';
  }

  function setOptions() {
    const trace = runMap.get(algorithm).trace;
    jump.replaceChildren(new Option('Chuẩn bị · chỉ tiêu ban đầu', '0'),
      ...trace.map((row, i) => new Option(`${i + 1} · ${studentName(row.student_id)}`, String(i + 1))),
      new Option('Tổng kết phân công', String(trace.length + 1)));
  }

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
    find('[data-replay-count]').textContent = `Đã phân ${completed}/${trace.length} · còn ${trace.length - completed}`;
    const detailsOpen = body.querySelector('details[data-options]')?.open;
    const metrics = run.metrics ?? {};
    const policy = decision?.policy_output;
    const policyLabel = {masked_policy_probability: 'Xác suất chọn của PPO', q_value_not_probability: 'Giá trị Q của DQN'}[policy?.kind];
    const remaining = considered.reduce((sum, row) => sum + row.limit - (loads[row.i] ?? 0), 0);
    const stage = decision ? `<h3>Bước ${step} · ${escape(studentName(decision.student_id))}</h3>
      <p class="allocation-chosen">Đề xuất <strong>${escape(advisorName(decision.advisor_id))}</strong></p>
      <dl class="allocation-facts"><div><dt>Điểm phù hợp E4</dt><dd>${percent(decision.score_known ? decision.score : null)}</dd></div>
      <div><dt>Lựa chọn hợp lệ</dt><dd>${allowed}</dd></div><div><dt>Chỗ còn lại của giảng viên</dt>
        <dd>${chosenCapacity - chosenBefore} trước bước · ${chosenCapacity - chosenBefore - 1} sau bước</dd></div></dl>
      <p class="help">${decision.fixed ? 'Đây là cặp đã được giảng viên nhận trước khi chạy.' :
        decision.policy_output?.kind === 'quota_only_random' ? 'Hồ sơ này được ghép theo các chỗ khả thi còn lại.' :
        'Các lựa chọn hợp lệ đã được lọc theo chỉ tiêu và ràng buộc của cả danh sách.'}
        ${decision.preference_known ? `Có tín hiệu nguyện vọng cho cặp này (${percent(decision.preference)}).` : ''}</p>` :
      final ? `<h3>Tổng kết phân công</h3><p>${completed} sinh viên đã có đề xuất · ${remaining} chỗ còn lại.
        ${metrics.constraint_violations === 0 ? 'Kết quả được kiểm tra và không vi phạm ràng buộc.' : ''}</p>` :
      `<h3>Chỉ tiêu trước phân công</h3><p>${trace.length} sinh viên đang chờ phân công · ${remaining} chỗ trong đợt chạy.</p>`;
    body.innerHTML = `${stage}
      <div class="table-scroll" tabindex="0" role="region" aria-label="${decision ? 'Số chỗ trước và sau bước' : 'Chỉ tiêu theo giảng viên'}">
        <table><caption>${decision ? 'Thay đổi số chỗ ở bước này' : 'Số chỗ hướng dẫn theo giảng viên'}</caption>
          <thead><tr><th scope="col">Giảng viên</th><th scope="col">Chỉ tiêu</th>
            ${decision ? '<th scope="col">Còn trước bước</th>' : quotas.length ? '<th scope="col">Đã nhận trước</th><th scope="col">Chia thêm</th>' : ''}
            <th scope="col">${step === 0 ? 'Còn ban đầu' : 'Còn lại'}</th></tr></thead>
          <tbody>${considered.map(({id, i, limit, quota}) => `<tr ${id === decision?.advisor_id ? 'class="allocation-selected"' : ''}>
            <th scope="row">${escape(advisorName(id))}</th><td>${limit}</td>
            ${decision ? `<td>${limit - (before[i] ?? 0)}</td>` : quotas.length ? `<td>${quota?.accepted ?? 0}</td><td>${quota?.remaining ?? limit}</td>` : ''}
            <td>${limit - (loads[i] ?? 0)}</td></tr>`).join('')}</tbody></table>
      </div>
      ${decision ? `<details data-options ${detailsOpen ? 'open' : ''}><summary>Xem lựa chọn và ràng buộc ở bước này</summary>
        <div class="table-scroll" tabindex="0" role="region" aria-label="Lựa chọn ở bước hiện tại"><table>
          <thead><tr><th scope="col">Giảng viên</th><th scope="col">Điểm E4</th><th scope="col">Trạng thái</th>
            ${policyLabel ? `<th scope="col">${policyLabel}</th>` : ''}</tr></thead>
          <tbody>${considered.map(({id, i, limit}) => {
            const eligible = decision.pre_action_mask?.[i];
            const reason = reasons[decision.blocked_reasons?.[i]] ??
              ((before[i] ?? 0) >= limit ? reasons.full : 'Bị ràng buộc ở bước này');
            const candidateScore = decision.candidate_scores?.[i] ?? (id === decision.advisor_id && decision.score_known ? decision.score : null);
            return `<tr><th scope="row">${escape(advisorName(id))}</th><td>${percent(candidateScore)}</td>
              <td>${id === decision.advisor_id ? 'Được chọn' : eligible ? 'Có thể chọn' : reason}</td>
              ${policyLabel ? `<td>${eligible && Number.isFinite(policy.values?.[i]) ?
                (policy.kind === 'masked_policy_probability' ? percent(policy.values[i]) : number(policy.values[i])) : '—'}</td>` : ''}</tr>`;
          }).join('')}</tbody></table></div></details>
        ${decision.reward_components ? `<details><summary>Điểm thưởng của bước</summary><p>
          Phù hợp ${number(decision.reward_components.score)} · Nguyện vọng ${number(decision.reward_components.preference)} ·
          Cân bằng tải ${number(decision.reward_components.fairness)} · Hoàn thành ${number(decision.reward_components.terminal_completion)}.
        </p></details>` : ''}` : ''}`;
  }

  function seek(offset) {
    stop();
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
    play.textContent = 'Tạm dừng';
    timer = setInterval(() => {
      if (!root.isConnected) { stop(); return; }
      step++;
      draw();
      if (step > length) stop();
    }, 1600 / Number(speed.value));
  }
  play.addEventListener('click', () => {
    if (timer !== undefined) stop();
    else start();
  });
  speed.addEventListener('change', () => { if (timer !== undefined) { stop(); start(); } });
  setOptions();
  draw();
  return stop;
}
