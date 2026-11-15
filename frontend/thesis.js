import { confidenceLabel, requireSession } from './portal.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {student: 'Hồ sơ khóa luận', faculty: 'Duyệt sinh viên hướng dẫn', dean: 'Phân công khóa luận'};
const statusNames = {pending: 'Chờ phản hồi', accepted: 'Đã nhận', rejected: 'Đã từ chối', withdrawn: 'Đã rút'};
const skillNames = {strong: 'Điểm mạnh', demonstrated: 'Có tín hiệu từ bài làm', self_reported: 'Tự đánh giá', unassessed: 'Chưa đủ tín hiệu'};
const levels = ['Chưa biết', 'Cơ bản', 'Khá', 'Tốt', 'Thành thạo'];
const orientations = {exploring: 'Chưa có định hướng', idea: 'Có ý tưởng, đang cân nhắc', defined: 'Đã có đề tài cụ thể'};
const majors = {it: 'Công nghệ thông tin', cs: 'Khoa học máy tính', other: 'Khác'};
const prompts = {
  'AI / Học máy': 'Giảng viên nào có công trình về trí tuệ nhân tạo và học máy?',
  'AI Agent / RAG': 'Giảng viên nào có hướng nghiên cứu về AI Agent, LLM hoặc RAG?',
  'Computer Vision': 'Giảng viên nào hướng dẫn đề tài thị giác máy tính và nhận diện đối tượng?',
  'Phát triển Web': 'Giảng viên nào phù hợp với đề tài phát triển web và hệ thống backend?',
  'Ứng dụng di động': 'Giảng viên nào có chuyên môn về phát triển ứng dụng di động?',
  'Data / BI': 'Giảng viên nào phù hợp với đề tài phân tích dữ liệu và BI?',
  'Game / VR': 'Giảng viên nào có hướng nghiên cứu game, đồ họa hoặc thực tế ảo?',
};
const errors = {
  semester_not_configured: 'Chưa mở kỳ đăng ký. Liên hệ khoa để biết lịch mở kỳ.',
  advisor_account_unassigned: 'Tài khoản giảng viên chưa được gán danh mục cho kỳ này. Liên hệ khoa để kiểm tra.',
  semester_published: 'Kỳ này đã công bố kết quả. Tải lại trang để xem.',
  verified_artifacts_not_ready: 'Chưa tải được danh mục giảng viên. Vui lòng thử lại.',
  verified_advisor_knowledge_not_ready: 'Trợ lý chưa tải được nguồn giảng viên. Vui lòng thử lại.',
  assessment_incomplete: 'Hãy hoàn thành tất cả câu khảo sát và trắc nghiệm.',
  assessment_required: 'Hãy lưu khảo sát và trắc nghiệm trước.',
  accepted_request_locked: 'Giảng viên đã nhận hướng dẫn. Nguyện vọng này đã được giữ chỗ.',
  request_already_rejected: 'Giảng viên đã từ chối yêu cầu này. Hãy chọn giảng viên khác.',
  pending_request_required: 'Yêu cầu đã thay đổi. Tải lại trang để xem trạng thái mới.',
  include_accepted_advisors: 'Danh sách phân công cần gồm tất cả giảng viên đã nhận sinh viên.',
  invalid_advisor_selection: 'Chọn tối đa ba giảng viên khác nhau và xếp theo thứ tự ưu tiên.',
  invalid_topic_description: 'Mô tả đề tài cần dài tối đa 2.000 ký tự.',
  invalid_registration_count: 'Cần từ 1 đến 1.000 sinh viên đã đăng ký để tạo phương án.',
  stale_or_infeasible_proposal: 'Phương án đã thay đổi hoặc không khả thi. Hãy tạo lại trước khi công bố.',
  role_required: 'Tài khoản hiện tại không có quyền thực hiện thao tác này.',
};

let user, state, catalog = [], rankings = [], catalogError = '', rankingError = '', selected, previousQuestion;
const content = $('thesis-content');
const notice = $('thesis-status');
const percent = score => (score * 100).toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + '%';
const advisorName = id => catalog.find(advisor => advisor.advisor_id === id)?.advisor_name ?? id;
const options = (values, selected) => values.map((value, index) => `<option value="${index}" ${index === selected ? 'selected' : ''}>${esc(value)}</option>`).join('');

async function api(path = '', body) {
  const response = await fetch(path.startsWith('/api/') ? path : '/api/thesis' + path,
    body === undefined ? {cache: 'no-store'} : {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (response.status === 401) {
    location.replace('./login.html');
    throw new Error('Phiên đăng nhập đã hết hạn.');
  }
  const result = await response.json();
  if (!response.ok) throw new Error(errors[result.detail] || 'Không hoàn tất được thao tác. Vui lòng thử lại.');
  return result;
}

function skillList(skills) {
  return `<ul class="thesis-skills">${skills.map(skill => `<li>
    <strong>${esc(skill.label)}</strong><span>${esc(skillNames[skill.status])} · ${skill.correct}/${skill.total} câu đúng</span>
  </li>`).join('')}</ul>`;
}

function assessmentForm(profile) {
  const latest = profile?.version === state.assessment_version ? profile : null;
  return `<form data-action="assessment">
    <div class="profile-fields">
      <label>Chuyên ngành <select name="major"><option value="">Chọn nếu muốn</option>${Object.entries(majors).map(([key, label]) =>
        `<option value="${key}" ${latest?.major === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <label>Bạn đã định hướng đề tài đến đâu? <select name="orientation" required><option value="">Chọn trạng thái</option>
        ${Object.entries(orientations).map(([key, label]) => `<option value="${key}" ${latest?.orientation === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
    </div>
    <fieldset>
      <legend>Vai trò bạn quan tâm</legend>
      <p class="help">Chọn các vai trò muốn đánh giá. Mỗi vai trò có 5 câu hỏi riêng.</p>
      <div class="track-picker">${state.assessment.map(role => `<label class="advisor-option">
        <input type="checkbox" name="roles" value="${esc(role.id)}" ${latest?.roles.includes(role.id) ? 'checked' : ''}>
        <span>${esc(role.label)}</span></label>`).join('')}</div>
    </fieldset>
    <p class="help" data-role-count aria-live="polite"></p>
    ${state.assessment.map(role => {
      const chosen = latest?.roles.includes(role.id);
      return `<fieldset data-track="${esc(role.id)}" ${chosen ? '' : 'hidden disabled'}>
        <legend>${esc(role.label)}</legend>
        <label>Mức tự đánh giá <select name="survey-${esc(role.id)}" required><option value="">Chọn mức</option>${options(levels, latest?.survey[role.id])}</select></label>
        <p class="help">Công cụ đã dùng · tùy chọn</p>
        <div class="track-tools">${role.tools.map(tool => `<label class="advisor-option"><input type="checkbox" name="tools-${esc(role.id)}" value="${esc(tool)}"
          ${latest?.tools[role.id]?.includes(tool) ? 'checked' : ''}><span>${esc(tool)}</span></label>`).join('')}</div>
        ${role.questions.map((q, i) => `<label>${i + 1}. ${esc(q.prompt)} <select name="answer-${esc(role.id)}-${i}" required><option value="">Chọn đáp án</option>${options(q.options, latest?.answers[role.id]?.[i])}</select></label>`).join('')}
      </fieldset>`;
    }).join('')}
    <button class="primary" ${latest?.roles.length ? '' : 'disabled'}>${profile ? 'Cập nhật hồ sơ' : 'Lưu và đăng ký khóa luận'}</button>
  </form>`;
}

function topicField() {
  return `<label class="topic-field">Mô tả đề tài muốn làm <span class="help">Tùy chọn</span>
    <textarea name="topic_description" rows="4" maxlength="2000" aria-describedby="topic-guidance"
      placeholder="Bạn muốn giải quyết vấn đề gì? Dự kiến làm sản phẩm hoặc nghiên cứu nào?">${esc(state.topic_description)}</textarea>
  </label><p id="topic-guidance" class="help">Bạn có thể bổ sung sau. Giảng viên dùng mô tả này để cân nhắc nhận bạn vào nhóm hướng dẫn.</p>`;
}

function studentView() {
  const profile = state.profile;
  const accepted = state.requests.some(r => r.status === 'accepted');
  const pending = state.requests.filter(r => r.status === 'pending').sort((a, b) => a.rank - b.rank);
  const canChoose = profile && !accepted && !state.published;
  const available = catalog.filter(a => !state.requests.some(r => r.advisor_id === a.advisor_id && r.status === 'rejected'));
  return `<section class="work-section">
    <h2>Khảo sát và trắc nghiệm</h2>
    ${profile ? skillList(profile.skills) : '<p>Chọn vai trò bạn quan tâm, tự đánh giá và làm trắc nghiệm trước khi xem gợi ý giảng viên.</p>'}
    ${profile ? '<p class="help">Kết quả sơ bộ kết hợp tự đánh giá với số câu trả lời đúng của từng vai trò.</p>' : ''}
    ${state.published ? '' : profile ? `<details><summary>Cập nhật vai trò và làm lại bài đánh giá</summary>${assessmentForm(profile)}</details>` : assessmentForm(profile)}
  </section>
  <section class="work-section">
    <h2>Giảng viên phù hợp</h2>
    ${rankingError ? `<p class="status-error">${esc(rankingError)}</p>` : rankings.length ?
      `<ol class="thesis-match-list">${rankings.map(r => `<li><strong>${esc(r.advisor_name)}</strong> <span>· ${percent(r.score)}</span></li>`).join('')}</ol>
      <p class="help">Gợi ý đối chiếu hướng bạn chọn và tín hiệu kỹ năng với chuyên môn trong danh mục giảng viên.</p>` :
      `<p>${profile ? 'Chưa tìm thấy giảng viên có điểm phù hợp dương từ hồ sơ này. Bạn có thể tra cứu với trợ lý hoặc xem danh mục bên dưới.' : 'Gợi ý xuất hiện sau khi bạn lưu bài làm.'}</p>`}
  </section>
  <section class="work-section">
    <h2>Nguyện vọng hướng dẫn</h2>
    ${canChoose ? '<p class="help">Chọn từ một đến ba giảng viên. Khi một giảng viên nhận hướng dẫn, các nguyện vọng còn chờ sẽ được rút.</p>' : ''}
    ${state.assignment ? `<p><strong>Giảng viên được phân công:</strong> ${esc(state.assignment.advisor_name)}</p>` : ''}
    ${state.requests.length ? `<ul class="thesis-skills">${[...state.requests].sort((a, b) => (a.rank ?? 4) - (b.rank ?? 4)).map(r => `<li><strong>${r.rank ? `Ưu tiên ${r.rank} · ` : ''}${esc(advisorName(r.advisor_id))}</strong><span>${statusNames[r.status]}</span></li>`).join('')}</ul>` : '<p>Bạn chưa gửi nguyện vọng hướng dẫn.</p>'}
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${canChoose && available.length ? `<form data-action="choice">
      <div class="preference-fields">${[0, 1, 2].map(index => `<label>Ưu tiên ${index + 1}
        <select name="advisor_id" ${index === 0 ? 'required' : ''}><option value="">${index ? 'Không chọn' : 'Chọn giảng viên'}</option>
        ${available.map(a => `<option value="${esc(a.advisor_id)}" ${a.advisor_id === pending[index]?.advisor_id ? 'selected' : ''}>${esc(a.advisor_name)}</option>`).join('')}
        </select></label>`).join('')}</div>
      ${topicField()}
      <button class="primary">${pending.length ? 'Cập nhật nguyện vọng' : 'Gửi nguyện vọng'}</button>
    </form>` : ''}
    ${accepted && !state.published ? `<form data-action="topic">${topicField()}<button class="secondary">Lưu mô tả đề tài</button></form>` : ''}
    ${state.published && state.topic_description ? `<h3>Mô tả đề tài đã lưu</h3><p class="topic-description">${esc(state.topic_description)}</p>` : ''}
    ${canChoose && pending.length ? '<form data-action="withdraw"><button class="secondary">Rút các nguyện vọng đang chờ</button></form>' : ''}
    ${canChoose && !available.length && !catalogError ? '<p>Danh mục hiện chưa còn giảng viên để chọn.</p>' : ''}
  </section>`;
}

function facultyView() {
  const accepted = state.requests.filter(r => r.status === 'accepted').length;
  return `<section class="work-section">
    <h2>Nguyện vọng gửi cho bạn</h2>
    <p><strong>${state.student_count}</strong> sinh viên đã đăng ký khóa luận trong kỳ. <strong>${accepted}</strong> sinh viên đã được bạn nhận trước khi chia số chỗ còn lại.</p>
    ${state.requests.length ? state.requests.map(r => `<article class="thesis-applicant">
      <h3>${esc(r.name)}</h3><p>${r.rank ? `Ưu tiên ${r.rank} · ` : ''}${statusNames[r.status]}</p>
      ${skillList(r.skills.filter(s => s.status !== 'unassessed'))}
      ${r.status !== 'rejected' ? `<h4>Đề tài dự kiến</h4><p class="topic-description">${r.topic_description ? esc(r.topic_description) : 'Sinh viên chưa bổ sung mô tả đề tài.'}</p>` : ''}
      ${r.status === 'pending' && !state.published ? `<form data-action="decision" data-student="${esc(r.user_id)}" class="thesis-actions">
        <button class="primary" value="accepted">Nhận hướng dẫn</button>
        <button class="secondary" value="rejected">Từ chối</button>
      </form>` : ''}
    </article>`).join('') : '<p>Sinh viên chọn bạn sẽ xuất hiện tại đây.</p>'}
    ${state.published ? `<h2>Nhóm đã công bố</h2>${state.assignments.length ?
      `<ul>${state.assignments.map(r => `<li>${esc(r.student_name)}</li>`).join('')}</ul>` : '<p>Chưa có sinh viên được phân công cho bạn.</p>'}` : ''}
  </section>`;
}

function deanView() {
  const proposal = state.proposal;
  return `<section class="work-section">
    <h2>Ngưỡng tin tưởng</h2>
    <p>Cặp đạt từ <strong>${state.threshold}%</strong> được đánh dấu xanh. Cặp dưới ngưỡng hoặc thiếu dữ liệu hiện màu vàng để bạn rà soát.</p>
    <p class="help">Ngưỡng áp dụng cho điểm phù hợp của cặp. Điểm này chưa được hiệu chuẩn thành xác suất hướng dẫn thành công.</p>
    ${state.published ? '' : `<form data-action="threshold" class="thesis-actions">
      <label for="confidence-threshold">Ngưỡng (%)</label><input type="number" id="confidence-threshold" name="threshold" min="0" max="100" step="1" required value="${state.threshold}">
      <button class="secondary">Lưu ngưỡng</button>
    </form>`}
  </section>
  <section class="work-section">
    <h2>${state.published ? 'Kết quả đã công bố' : 'Phương án phân công'}</h2>
    <p><strong>${state.student_count}</strong> sinh viên đã đăng ký. Chỉ tiêu bằng số sinh viên đã nhận cộng số chỗ chia đều từ phần còn lại.</p>
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${!state.published && catalog.length ? `<form data-action="proposal">
      <fieldset><legend>Giảng viên tham gia phân công</legend><div class="thesis-roster">
      ${catalog.map(a => {
        const required = state.accepted_advisors.includes(a.advisor_id);
        return `<label class="advisor-option"><input type="checkbox" name="advisor_id" value="${esc(a.advisor_id)}" ${required || selected.has(a.advisor_id) ? 'checked' : ''} ${required ? 'disabled' : ''}>
        <span>${esc(a.advisor_name)}${required ? '<small>Đã nhận sinh viên</small>' : ''}</span></label>`;
      }).join('')}
      </div></fieldset><button class="primary" ${state.student_count ? '' : 'disabled'}>Tạo phương án</button>
    </form>` : ''}
    ${proposal ? tables(proposal) : '<p>Phương án xuất hiện sau khi bạn chọn giảng viên và chạy phân công.</p>'}
    ${proposal?.status === 'feasible' && !state.published ? `<form data-action="publish" class="thesis-actions thesis-publish">
      <label class="confirmation"><input type="checkbox" required> Tôi đã rà soát phương án. Công bố sẽ khóa thay đổi trong kỳ này.</label>
      <button class="primary">Công bố phân công</button>
    </form>` : ''}
  </section>`;
}

function tables(proposal) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="Chỉ tiêu hướng dẫn"><table>
    <caption>Chỉ tiêu hướng dẫn theo giảng viên</caption>
    <thead><tr><th scope="col">Giảng viên</th><th scope="col">Đã nhận</th><th scope="col">Chia thêm</th><th scope="col">Tổng</th></tr></thead>
    <tbody>${proposal.quotas.map(q => `<tr><th scope="row">${esc(q.advisor_name)}</th><td>${q.accepted}</td><td>${q.remaining}</td><td>${q.total}</td></tr>`).join('')}</tbody></table></div>
    ${proposal.status !== 'feasible' ? '<p class="status-error">Không thể phân công đủ với chỉ tiêu và các quyết định hiện tại. Hãy kiểm tra danh sách giảng viên tham gia.</p>' :
    `<div class="table-scroll" tabindex="0" role="region" aria-label="Kết quả phân công"><table><caption>Cặp sinh viên và giảng viên</caption>
      <thead><tr><th scope="col">Sinh viên</th><th scope="col">Giảng viên</th><th scope="col">Điểm phù hợp</th><th scope="col">Theo ngưỡng</th></tr></thead>
      <tbody>${proposal.assignments.map(r => `<tr><th scope="row">${esc(r.student_name)}</th><td>${esc(r.advisor_name)}${r.accepted ? '<small>Đã nhận hướng dẫn</small>' : ''}</td>
      <td>${r.score == null ? '—' : percent(r.score)}</td><td>${confidenceLabel(r.score, state.threshold)}</td></tr>`).join('')}</tbody></table></div>`}`;
}

async function refresh() {
  content.setAttribute('aria-busy', 'true');
  try {
    state = await api();
    $('thesis-period').textContent = `${state.semester.startsWith('demo-') ? 'Kỳ thử nghiệm ' : 'Kỳ '}${state.semester}${state.published ? ' · Đã công bố' : ''}`;
    const load = [
      user.role === 'faculty' ? Promise.resolve([]) : api('/catalog'),
      user.role === 'student' && state.profile ? api('/recommendations') : Promise.resolve([]),
    ];
    const [advisors, recommended] = await Promise.allSettled(load);
    catalog = advisors.value ?? [];
    catalogError = advisors.reason?.message ?? '';
    rankings = recommended.value ?? [];
    rankingError = recommended.reason?.message ?? '';
    selected ??= new Set(state.proposal?.quotas.map(q => q.advisor_id) ?? catalog.map(a => a.advisor_id));
    content.innerHTML = {student: studentView, faculty: facultyView, dean: deanView}[user.role]();
    const assessment = content.querySelector('[data-action="assessment"]');
    if (assessment) updateTracks(assessment);
    $('fill-skill-question').hidden = !state.profile?.skills.some(s => s.status !== 'unassessed');
  } finally {
    content.setAttribute('aria-busy', 'false');
  }
}

function showStatus(message, error = false, focus = false) {
  notice.textContent = message;
  notice.classList.toggle('status-error', error);
  if (focus) notice.focus();
}

function updateTracks(form) {
  const roles = new Set(new FormData(form).getAll('roles'));
  for (const fieldset of form.querySelectorAll('[data-track]')) {
    fieldset.hidden = fieldset.disabled = !roles.has(fieldset.dataset.track);
  }
  form.querySelector('[data-role-count]').textContent = roles.size
    ? `Đã chọn ${roles.size} vai trò · ${roles.size * 5} câu hỏi.` : 'Chọn ít nhất một vai trò để mở câu hỏi.';
  form.querySelector('button[type="submit"], button.primary').disabled = !roles.size;
}

content.addEventListener('change', event => {
  const input = event.target;
  if (input.name === 'roles') updateTracks(input.form);
  if (input.matches('[data-action="proposal"] input')) {
    if (input.checked) selected.add(input.value);
    else selected.delete(input.value);
  }
});

content.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const action = form.dataset.action;
  const data = new FormData(form);
  let payload;
  if (action === 'assessment') {
    const roles = data.getAll('roles');
    payload = {version: state.assessment_version, roles, major: data.get('major'), orientation: data.get('orientation'),
      survey: {}, answers: {}, tools: {}};
    for (const skill of state.assessment.filter(role => roles.includes(role.id))) {
      payload.survey[skill.id] = Number(data.get('survey-' + skill.id));
      payload.answers[skill.id] = skill.questions.map((_, i) => Number(data.get(`answer-${skill.id}-${i}`)));
      payload.tools[skill.id] = data.getAll('tools-' + skill.id);
    }
  } else if (action === 'choice') {
    const inputs = data.getAll('advisor_id');
    const ids = inputs.filter(Boolean);
    if (ids.length !== new Set(ids).size || ids.some((id, index) => id !== inputs[index])) {
      showStatus('Chọn các giảng viên khác nhau theo thứ tự, từ ưu tiên 1 và không bỏ trống ở giữa.', true, true);
      return;
    }
    payload = {advisor_ids: ids, topic_description: data.get('topic_description')};
  } else if (action === 'withdraw') payload = {advisor_ids: []};
  else if (action === 'topic') payload = {topic_description: data.get('topic_description')};
  else if (action === 'decision') payload = {decision: event.submitter.value, user_id: form.dataset.student};
  else if (action === 'threshold') payload = {threshold: Number(data.get('threshold'))};
  else if (action === 'proposal') payload = {advisor_ids: [...new Set([...selected, ...state.accepted_advisors])]};
  else if (action === 'publish') payload = {id: state.proposal.id};
  const buttons = [...content.querySelectorAll('button:not(:disabled)')];
  buttons.forEach(button => { button.disabled = true; });
  showStatus(action === 'proposal' ? 'Đang tính phương án…' : 'Đang lưu…', false, true);
  try {
    await api('/' + (action === 'withdraw' ? 'choice' : action), payload);
    await refresh();
    const messages = {assessment: 'Đã lưu kết quả đánh giá.', choice: 'Đã lưu nguyện vọng theo thứ tự ưu tiên.', withdraw: 'Đã rút các nguyện vọng đang chờ.',
      topic: 'Đã lưu mô tả đề tài.',
      decision: 'Đã lưu quyết định.', threshold: 'Đã lưu ngưỡng.', publish: 'Đã công bố kết quả phân công.',
      proposal: state.proposal?.status === 'feasible' ? 'Phương án đã sẵn sàng để rà soát.' : 'Chưa có phương án khả thi.'};
    showStatus(messages[action]);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    buttons.forEach(button => { button.disabled = false; });
  }
});

$('fill-skill-question').addEventListener('click', () => {
  const labels = state.profile.skills.filter(s => s.status !== 'unassessed').map(s => s.label);
  $('thesis-question').value = `Giảng viên nào phù hợp với các kỹ năng ${labels.join(', ')}?`;
  $('thesis-question').focus();
});

for (const [label, question] of Object.entries(prompts)) {
  const button = document.createElement('button');
  button.className = 'secondary';
  button.type = 'button';
  button.textContent = label;
  button.addEventListener('click', () => {
    $('thesis-question').value = question;
    $('thesis-question').focus();
  });
  $('thesis-chat-prompts').append(button);
}

$('thesis-chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = $('thesis-question');
  const question = input.value.trim();
  if (!question) return;
  const button = event.submitter;
  const status = $('thesis-chat-status');
  button.disabled = true;
  status.textContent = 'Đang tìm thông tin giảng viên…';
  try {
    const reply = await api('/api/rebuild/assistant', {question, ...(previousQuestion && {previous_question: previousQuestion})});
    if (['topic_match', 'advisor_profile'].includes(reply.intent) && !reply.follow_up) previousQuestion = question;
    const entry = document.createElement('article');
    const heading = document.createElement('h3');
    heading.textContent = question;
    const answer = document.createElement('p');
    answer.textContent = reply.answer;
    entry.append(heading, answer);
    if (reply.rankings?.length) {
      const matches = document.createElement('ol');
      for (const ranking of reply.rankings) {
        const item = document.createElement('li');
        item.textContent = ranking.advisor_name + (typeof ranking.score === 'number' ? ' · ' + percent(ranking.score) : '');
        matches.append(item);
      }
      entry.append(matches);
    }
    const sources = document.createElement('ul');
    for (const citation of reply.citations ?? []) {
      let url;
      try { url = new URL(citation.url || citation.source_url); } catch { continue; }
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) continue;
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = citation.title || 'Nguồn tham khảo';
      item.append(link);
      sources.append(item);
    }
    if (sources.children.length) entry.append(sources);
    $('thesis-chat-history').prepend(entry);
    if (input.value.trim() === question) input.value = '';
    status.textContent = 'Trợ lý đã phản hồi.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

user = await requireSession();
if (user) {
  $('thesis-title').textContent = titles[user.role];
  document.querySelectorAll('[data-dean]').forEach(link => { link.hidden = user.role !== 'dean'; });
  $('thesis-chat').hidden = user.role !== 'student';
  try {
    await refresh();
    showStatus('');
  } catch (error) {
    showStatus(error.message, true);
  }
}
