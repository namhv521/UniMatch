const section = document.createElement('section');
section.className = 'work-section';
section.setAttribute('aria-labelledby', 'nested-title');
section.innerHTML = `<h2 id="nested-title">RL hai cấp · V1–V3, R1–R4</h2>
<p><strong>Phản hồi mô phỏng.</strong> R2 tạo nguyện vọng theo độ tương đồng chuyên môn; R3 giả lập tăng một chỉ tiêu; R4 giữ nguyên R3. Kết quả chưa chứng minh hiệu quả với phản hồi người thật.</p>
<p>Mỗi round thêm 32.768 bước; bốn round dùng tổng ngân sách 131.072 bước/version cho mỗi thuật toán. Điểm là utility trung bình/sinh viên, không phải phần trăm chính xác. Giữ bản trước khi candidate giảm điểm trên kỳ hiện tại hoặc holdout kỳ cũ.</p>
<p id="nested-status" role="status">Đang tải kết quả…</p><div id="nested-results"></div>`;
document.querySelector('main').insertBefore(section, document.querySelector('.dashboard-actions'));
const status = section.querySelector('#nested-status');
try {
  const response = await fetch('./assets/nested-rl/results.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('Không tải được kết quả RL hai cấp.');
  const data = await response.json();
  if (data.scope !== 'simulated_feedback_not_human') throw new Error('Nguồn kết quả chưa được nhận diện.');
  status.textContent = `${data.status === 'completed' ? 'Đã hoàn tất' : 'Đang huấn luyện'} · ${data.results.length}/24 lượt fit · một seed · validation, chưa chấm test mới.`;
  if (data.results.length) {
    const image = document.createElement('img');
    image.src = './assets/nested-rl/round-comparison.png';
    image.alt = 'Điểm validation của PPO và DQN qua bốn round, chia theo V1, V2, V3; phản hồi mô phỏng.';
    image.style.cssText = 'width:100%;height:auto';
    section.querySelector('#nested-results').append(image);
    const steps = document.createElement('img');
    steps.src = './assets/nested-rl/step-curves.png';
    steps.alt = 'Mười hai panel validation theo bước train của từng version và round; đường chấm là parent.';
    steps.loading = 'lazy';
    steps.style.cssText = 'width:100%;height:auto';
    section.querySelector('#nested-results').append(steps);
    const zoom = document.createElement('p');
    for (const [label, path] of [['Mở biểu đồ so sánh round', image.src], ['Mở biểu đồ theo step', steps.src]]) {
      const link = document.createElement('a');
      link.href = path; link.target = '_blank'; link.rel = 'noopener'; link.textContent = label;
      link.style.cssText = 'display:inline-block;padding:12px 16px 12px 0';
      zoom.append(link);
    }
    section.querySelector('#nested-results').append(zoom);
    const scroll = document.createElement('div');
    scroll.className = 'table-scroll';
    scroll.tabIndex = 0;
    scroll.setAttribute('aria-label', 'Bảng so sánh round, có thể cuộn ngang');
    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    for (const name of ['Version', 'Round', 'Model', 'Bước thêm', 'Điểm trước', 'Điểm sau', 'Chênh lệch', 'Quyết định']) {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = name; head.append(th);
    }
    const body = table.createTBody();
    const number = x => x == null ? '—' : Number(x).toFixed(6);
    for (const row of data.results) {
      const tr = body.insertRow();
      const decision = { accepted: 'Giữ bản mới', rejected: 'Giữ bản trước', inconclusive: 'Chưa đủ bằng chứng' }[row.decision] || row.decision;
      for (const value of [row.version, row.round, row.algorithm.toUpperCase(), row.steps_added,
        number(row.parent_score), number(row.candidate_score), number(row.delta), decision]) {
        tr.insertCell().textContent = value;
      }
    }
    scroll.append(table); section.querySelector('#nested-results').append(scroll);
  }
} catch (error) { status.textContent = error.message; }
