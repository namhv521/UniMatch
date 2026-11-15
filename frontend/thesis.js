import { confidenceLabel, requireSession } from './portal.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {student: 'Hồ sơ khóa luận', faculty: 'Duyệt sinh viên hướng dẫn', dean: 'Phân công khóa luận'};
const statusNames = {pending: 'Chờ phản hồi', accepted: 'Đã nhận', rejected: 'Đã từ chối', withdrawn: 'Đã rút'};
const skillNames = {strong: 'Điểm mạnh', demonstrated: 'Có tín hiệu từ bài làm', self_reported: 'Tự đánh giá', unassessed: 'Chưa đủ tín hiệu'};
const levels = ['Chưa từng làm', 'Đã tìm hiểu', 'Làm được có hướng dẫn', 'Làm được độc lập'];
const errors = {
  semester_not_configured: 'Chưa mở kỳ đăng ký. Liên hệ khoa để biết lịch mở kỳ.',
  semester_published: 'Kỳ này đã công bố kết quả. Tải lại trang để xem.',
  verified_artifacts_not_ready: 'Chưa tải được danh mục giảng viên. Vui lòng thử lại.',
  verified_advisor_knowledge_not_ready: 'Trợ lý chưa tải được nguồn giảng viên. Vui lòng thử lại.',
  assessment_incomplete: 'Hãy hoàn thành tất cả câu khảo sát và trắc nghiệm.',
  assessment_required: 'Hãy lưu khảo sát và trắc nghiệm trước.',
  accepted_request_locked: 'Giảng viên đã nhận hướng dẫn. Nguyện vọng này đã được giữ chỗ.',
  request_already_rejected: 'Giảng viên đã từ chối yêu cầu này. Hãy chọn giảng viên khác.',
  pending_request_required: 'Yêu cầu đã thay đổi. Tải lại trang để xem trạng thái mới.',
  include_accepted_advisors: 'Danh sách phân công cần gồm tất cả giảng viên đã nhận sinh viên.',
  invalid_advisor_selection: 'Hãy chọn ít nhất một giảng viên hợp lệ.',
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

function studentView() {
  const profile = state.profile;
  const latestAssessment = profile?.version === state.assessment_version ? profile : null;
  const current = state.requests.find(r => ['pending', 'accepted'].includes(r.status));
  const canChoose = profile && current?.status !== 'accepted' && !state.published;
  const available = catalog.filter(a => !state.requests.some(r => r.advisor_id === a.advisor_id && r.status === 'rejected'));
  const assessment = `<form data-action="assessment">
    ${state.assessment.map(skill => `<fieldset>
      <legend>${esc(skill.label)}</legend>
      <label>Mức tự đánh giá <select name="survey-${esc(skill.id)}" required><option value="">Chọn mức</option>${options(levels, latestAssessment?.survey[skill.id])}</select></label>
      ${skill.questions.map((q, i) => `<label>${esc(q.prompt)} <select name="answer-${esc(skill.id)}-${i}" required><option value="">Chọn đáp án</option>${options(q.options, latestAssessment?.answers[skill.id]?.[i])}</select></label>`).join('')}
    </fieldset>`).join('')}
    <button class="primary">${profile ? 'Cập nhật hồ sơ' : 'Lưu và đăng ký khóa luận'}</button>
  </form>`;
  return `<section class="work-section">
    <h2>Khảo sát và trắc nghiệm</h2>
    ${profile ? skillList(profile.skills) : '<p>Đánh giá bốn nhóm kỹ năng. Lưu bài làm để ghi danh kỳ này và nhận gợi ý giảng viên.</p>'}
    ${profile ? '<p class="help">Kết quả sơ bộ dựa trên tự đánh giá và hai câu trắc nghiệm mỗi nhóm.</p>' : ''}
    ${state.published ? '' : profile ? `<details><summary>Làm lại khảo sát và trắc nghiệm</summary>${assessment}</details>` : assessment}
  </section>
  <section class="work-section">
    <h2>Giảng viên phù hợp</h2>
    ${rankingError ? `<p class="status-error">${esc(rankingError)}</p>` : rankings.length ?
      `<ol class="thesis-match-list">${rankings.map(r => `<li><strong>${esc(r.advisor_name)}</strong> <span>· ${percent(r.score)}</span></li>`).join('')}</ol>
      <p class="help">Điểm phù hợp dựa vào tín hiệu kỹ năng và chuyên môn trong danh mục.</p>` :
      `<p>${profile ? 'Chưa tìm thấy giảng viên có điểm phù hợp dương từ hồ sơ này. Bạn có thể tra cứu với trợ lý hoặc xem danh mục bên dưới.' : 'Gợi ý xuất hiện sau khi bạn lưu bài làm.'}</p>`}
  </section>
  <section class="work-section">
    <h2>Nguyện vọng hướng dẫn</h2>
    ${state.assignment ? `<p><strong>Giảng viên được phân công:</strong> ${esc(state.assignment.advisor_name)}</p>` : ''}
    ${state.requests.length ? `<ul class="thesis-skills">${state.requests.map(r => `<li><strong>${esc(advisorName(r.advisor_id))}</strong><span>${statusNames[r.status]}</span></li>`).join('')}</ul>` : '<p>Bạn chưa gửi nguyện vọng hướng dẫn.</p>'}
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${canChoose && available.length ? `<form data-action="choice" class="thesis-actions">
      <label for="thesis-advisor-choice">Giảng viên mong muốn</label>
      <select id="thesis-advisor-choice" name="advisor_id" required><option value="">Chọn giảng viên</option>
        ${available.map(a => `<option value="${esc(a.advisor_id)}" ${a.advisor_id === current?.advisor_id ? 'selected' : ''}>${esc(a.advisor_name)}</option>`).join('')}
      </select>
      <button class="primary">${current ? 'Cập nhật nguyện vọng' : 'Gửi nguyện vọng'}</button>
    </form>` : ''}
    ${canChoose && current ? '<form data-action="withdraw"><button class="secondary">Rút nguyện vọng</button></form>' : ''}
    ${canChoose && !available.length && !catalogError ? '<p>Danh mục hiện chưa còn giảng viên để chọn.</p>' : ''}
  </section>`;
}

function facultyView() {
  const accepted = state.requests.filter(r => r.status === 'accepted').length;
  return `<section class="work-section">
    <h2>Nguyện vọng gửi cho bạn</h2>
    <p><strong>${state.student_count}</strong> sinh viên đã đăng ký khóa luận trong kỳ. <strong>${accepted}</strong> sinh viên đã được bạn nhận trước khi chia số chỗ còn lại.</p>
    ${state.requests.length ? state.requests.map(r => `<article class="thesis-applicant">
      <h3>${esc(r.name)}</h3><p>${statusNames[r.status]}</p>
      ${skillList(r.skills.filter(s => s.status !== 'unassessed'))}
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
    $('thesis-period').textContent = `Kỳ ${state.semester}${state.published ? ' · Đã công bố' : ''}`;
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

content.addEventListener('change', event => {
  const input = event.target;
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
    payload = {survey: {}, answers: {}};
    for (const skill of state.assessment) {
      payload.survey[skill.id] = Number(data.get('survey-' + skill.id));
      payload.answers[skill.id] = skill.questions.map((_, i) => Number(data.get(`answer-${skill.id}-${i}`)));
    }
  } else if (action === 'choice' || action === 'withdraw') payload = {advisor_id: data.get('advisor_id')};
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
    const messages = {assessment: 'Đã lưu kết quả đánh giá.', choice: 'Đã gửi nguyện vọng.', withdraw: 'Đã rút nguyện vọng.',
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
