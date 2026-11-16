import { confidenceLabel, requireSession } from './portal.js';
import { mountReplay } from './allocation-replay.js';

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
  invalid_contact: 'Nhập số điện thoại hợp lệ để giảng viên có thể liên hệ.',
  invalid_email: 'Nhập địa chỉ email liên hệ hợp lệ.',
  invalid_registration_count: 'Cần từ 1 đến 1.000 sinh viên đã đăng ký để tạo phương án.',
  stale_manual_assignment: 'Bản phân công thủ công đã thay đổi. Tải lại trang rồi chỉnh tiếp.',
  invalid_manual_assignment: 'Có sinh viên hoặc giảng viên không hợp lệ. Tải lại danh sách rồi thử lại.',
  incomplete_manual_assignment: 'Hãy tải lại trang và lưu đủ phân công cho mọi sinh viên trước khi công bố.',
  stale_or_infeasible_proposal: 'Phương án đã thay đổi hoặc không khả thi. Hãy tạo lại trước khi công bố.',
  role_required: 'Tài khoản hiện tại không có quyền thực hiện thao tác này.',
  invalid_roster_csv: 'Không đọc được CSV. Hãy lưu lại dưới dạng CSV UTF-8.',
  invalid_roster_headers: 'CSV cần các cột student_id, name, email. Có thể thêm phone, topic và skills.',
  invalid_roster_row: 'Dòng CSV có dữ liệu thiếu hoặc sai định dạng.',
  duplicate_roster_identity: 'Mã sinh viên hoặc email bị trùng trong CSV.',
  roster_limit: 'Danh sách hỗ trợ tối đa 500 sinh viên mỗi kỳ.',
  semester_roster_required: 'Hãy nhập danh sách CSV của kỳ.',
  not_in_semester_roster: 'Email đăng nhập chưa có trong danh sách khóa luận của kỳ.',
  preferences_closed: 'Trưởng khoa đã khóa nộp nguyện vọng.',
  close_preferences_first: 'Hãy khóa nộp nguyện vọng trước khi chạy mô hình.',
  matching_models_unavailable: 'Server chưa nạp đủ checkpoint PPO và DQN.',
  matching_model_contract_mismatch: 'Checkpoint đang phục vụ chưa khớp cấu hình suy luận.',
  publication_algorithm_required: 'Chọn phương án PPO hoặc DQN trước khi công bố.',
  semester_not_published: 'Kỳ này chưa có danh sách đã công bố.',
};

let user, state, catalog = [], rankings = [], catalogError = '', rankingError = '', selected, previousQuestion, saving = false;
let stopReplay = () => {};
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
  if (!response.ok) {
    const detail = result.detail;
    const message = errors[detail?.code ?? detail] || 'Không hoàn tất được thao tác. Vui lòng thử lại.';
    throw new Error(detail?.row ? `Dòng ${detail.row}. ${message}` : message);
  }
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

function contactFields() {
  return `<fieldset><legend>Thông tin liên hệ</legend>
    <p class="help">Sau khi trưởng khoa công bố, các giảng viên bạn đã chọn sẽ thấy email và số điện thoại này.</p>
    <label>Email liên hệ <input type="email" name="contact_email" autocomplete="email" maxlength="254" required value="${esc(state.contact.email)}"></label>
    <label>Số điện thoại <input type="tel" name="contact_phone" autocomplete="tel" maxlength="24" required value="${esc(state.contact.phone)}"></label>
  </fieldset>`;
}

function studentView() {
  const profile = state.profile;
  const accepted = state.requests.some(r => r.status === 'accepted');
  const pending = state.requests.filter(r => r.status === 'pending').sort((a, b) => a.rank - b.rank);
  const canChoose = profile && state.in_roster && !accepted && !state.published && !state.preferences_closed;
  const available = catalog.filter(a => !state.requests.some(r => r.advisor_id === a.advisor_id && r.status === 'rejected'));
  return `<section class="work-section">
    <h2>Khảo sát và trắc nghiệm</h2>
    ${profile ? skillList(profile.skills) : '<p>Chọn vai trò bạn quan tâm, tự đánh giá và làm trắc nghiệm trước khi xem gợi ý giảng viên.</p>'}
    ${profile ? '<p class="help">Kết quả sơ bộ kết hợp tự đánh giá với số câu trả lời đúng của từng vai trò.</p>' : ''}
    ${state.published || state.preferences_closed ? '' : profile ? `<details><summary>Cập nhật vai trò và làm lại bài đánh giá</summary>${assessmentForm(profile)}</details>` : assessmentForm(profile)}
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
    ${state.preferences_closed ? '<p>Trưởng khoa đã khóa nộp và sửa nguyện vọng.</p>' : !state.in_roster ? '<p>Email đăng nhập của bạn chưa có trong danh sách khóa luận kỳ này.</p>' : ''}
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
      ${contactFields()}
      <button class="primary">${pending.length ? 'Cập nhật nguyện vọng' : 'Gửi nguyện vọng'}</button>
    </form>` : ''}
    ${accepted && !state.published && !state.preferences_closed ? `<form data-action="topic">${topicField()}<button class="secondary">Lưu mô tả đề tài</button></form>` : ''}
    ${(accepted || state.published || state.preferences_closed) && state.requests.some(r => r.rank) ? `<details><summary>Cập nhật thông tin liên hệ</summary>
      <form data-action="contact">${contactFields()}<button class="secondary">Lưu thông tin liên hệ</button></form></details>` : ''}
    ${state.published && state.topic_description ? `<h3>Mô tả đề tài đã lưu</h3><p class="topic-description">${esc(state.topic_description)}</p>` : ''}
    ${canChoose && pending.length ? '<form data-action="withdraw"><button class="secondary">Rút các nguyện vọng đang chờ</button></form>' : ''}
    ${canChoose && !available.length && !catalogError ? '<p>Danh mục hiện chưa còn giảng viên để chọn.</p>' : ''}
  </section>`;
}

function facultyView() {
  const accepted = state.requests.filter(r => r.status === 'accepted').length;
  const pending = state.requests.filter(r => r.status === 'pending').length;
  return `<section class="work-section">
    <h2>Nguyện vọng gửi cho ${esc(state.advisor_name || 'bạn')}</h2>
    <p><strong>${state.student_count}</strong> sinh viên đã đăng ký khóa luận trong kỳ. <strong>${accepted}</strong> sinh viên đã được bạn nhận trước khi chia số chỗ còn lại.</p>
    ${!state.published ? `<p><strong>${pending}</strong> nguyện vọng đang chờ bạn duyệt.</p>` : ''}
    ${state.requests.length ? state.requests.map(r => `<article class="thesis-applicant">
      <h3>${esc(r.name)}</h3><p>${r.rank ? `Ưu tiên ${r.rank} · ` : ''}${statusNames[r.status]}</p>
      ${skillList(r.skills.filter(s => s.status !== 'unassessed'))}
      ${r.status !== 'rejected' ? `<h4>Đề tài dự kiến</h4><p class="topic-description">${r.topic_description ? esc(r.topic_description) : 'Sinh viên chưa bổ sung mô tả đề tài.'}</p>` : ''}
      ${r.status === 'pending' && !state.published ? `<form data-action="decision" data-student="${esc(r.user_id)}" class="thesis-actions">
        <button class="primary" value="accepted">Nhận hướng dẫn</button>
        <button class="secondary" value="rejected">Từ chối</button>
      </form>` : ''}
    </article>`).join('') : '<p>Sinh viên chọn bạn sẽ xuất hiện tại đây.</p>'}
    ${state.published ? `<h2>Nhóm đã công bố</h2>${contactTable(state.assignments.map(r => ({...r, name: r.student_name})),
      'Chưa có sinh viên được phân công cho bạn.')}` : ''}
  </section>
  ${state.published ? `<section class="work-section"><h2>Sinh viên đã đăng ký bạn hướng dẫn</h2>
    ${contactTable(state.registered_students, 'Chưa có sinh viên đăng ký bạn hướng dẫn trong kỳ này.')}
    </section>` : ''}`;
}

function contactTable(rows, empty) {
  return rows.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="Thông tin liên hệ sinh viên">
    <table><thead><tr><th scope="col">Họ tên</th><th scope="col">Email</th><th scope="col">Số điện thoại</th></tr></thead>
    <tbody>${rows.map(row => `<tr><th scope="row">${esc(row.name)}</th>
      <td>${esc(row.email || 'Chưa cung cấp')}</td><td>${esc(row.phone || 'Chưa cung cấp')}</td></tr>`).join('')}
    </tbody></table></div>` : `<p>${empty}</p>`;
}

let manualDirty = false;

function manualAllocation() {
  if (!state.roster_loaded || (state.published && state.published_algorithm !== 'manual')) return '';
  const manual = state.manual;
  const rows = manual?.assignments ?? [];
  const assigned = new Map(rows.map(row => [row.student_id, row.advisor_id]));
  const table = body => `<div class="table-scroll" tabindex="0" role="region" aria-label="Danh sách phân công thủ công">
    <table><thead><tr><th scope="col">Sinh viên</th><th scope="col">Giảng viên hướng dẫn</th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
  return `<section class="work-section" aria-labelledby="manual-allocation-title">
    <h2 id="manual-allocation-title">Phân công thủ công</h2>
    ${state.published ? table(rows.map(row => `<tr><th scope="row">${esc(row.student_name)} · ${esc(row.student_id)}</th><td>${esc(row.advisor_name)}</td></tr>`).join('')) :
      `<p>Chỉ định giảng viên trực tiếp cho từng sinh viên trong CSV. Lựa chọn thủ công có thể vượt chỉ tiêu và thay đổi quyết định nhận hướng dẫn trước đó.</p>
      <p class="help">Đã lưu ${rows.length}/${state.student_count} sinh viên. Khóa nguyện vọng và phân công đủ danh sách để công bố.</p>
      ${catalog.length ? `<form data-action="manual">
        ${manual ? '' : Object.entries(state.proposal?.results ?? {}).filter(([, run]) => run.status === 'feasible')
          .map(([name]) => `<button type="button" class="secondary" data-copy-allocation="${esc(name)}">Điền theo ${esc(name.toUpperCase())}</button>`).join(' ')}
        ${table(state.roster_preview.map(row => `<tr><th scope="row">${esc(row.name)} · ${esc(row.student_id)}</th><td>
          <select name="${esc(row.student_id)}" aria-label="Giảng viên hướng dẫn cho ${esc(row.name)} · ${esc(row.student_id)}">
            <option value="">Chưa phân công</option>
            ${catalog.map(a => `<option value="${esc(a.advisor_id)}"${assigned.get(row.student_id) === a.advisor_id ? ' selected' : ''}>${esc(a.advisor_name)}</option>`).join('')}
          </select></td></tr>`).join(''))}
        <button class="secondary">Lưu phân công thủ công</button>
      </form>` : '<p>Danh mục giảng viên chưa tải được.</p>'}
      ${state.preferences_closed && manual && rows.length === state.student_count ? `<form data-action="publish-manual" class="thesis-actions thesis-publish">
        <label class="confirmation"><input type="checkbox" required> Tôi đã rà soát bản phân công thủ công.</label>
        <button class="primary">Công bố bản thủ công</button>
      </form>` : ''}`}
  </section>`;
}

function deanView() {
  const proposal = state.proposal;
  return `<div class="dean-layout"><div class="dean-main">
  <section class="work-section"><h2>Danh sách khóa luận của kỳ</h2>
    <p><strong>${state.roster_loaded ? state.student_count : 0}</strong> sinh viên trong CSV ·
      <strong>${state.roster_loaded ? state.submitted_count : 0}</strong> đã điền hồ sơ trực tuyến.</p>
    ${state.roster_loaded ? `<details><summary>Xem danh sách đã nhập</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Danh sách sinh viên đã nhập">
      <table><thead><tr><th scope="col">Mã sinh viên</th><th scope="col">Họ tên</th><th scope="col">Hồ sơ trực tuyến</th></tr></thead>
      <tbody>${state.roster_preview.map(row => `<tr><th scope="row">${esc(row.student_id)}</th><td>${esc(row.name)}</td>
        <td>${row.submitted ? 'Đã nộp' : 'Chưa nộp'}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
    ${state.published ? '' : `<form data-action="roster" class="thesis-actions">
      <label for="thesis-roster-file">${state.roster_loaded ? 'Thay danh sách CSV' : 'Tải danh sách CSV'}</label>
      <input id="thesis-roster-file" type="file" name="csv_file" accept=".csv,text/csv" required>
      ${state.roster_loaded ? '<label class="confirmation"><input type="checkbox" required> Dùng tệp này để thay toàn bộ danh sách hiện tại.</label>' : ''}
      <button class="primary">Lưu danh sách</button>
    </form>
    <p class="help">Yêu cầu <code>student_id, name, email</code>. Có thể thêm <code>phone, topic, skills</code>.
      Dùng đúng email đăng nhập UniMatch để ghép hồ sơ. <a href="data:text/csv;charset=utf-8,student_id%2Cname%2Cemail%2Cphone%2Ctopic%2Cskills%0A" download="unimatch-danh-sach.csv">Tải CSV mẫu</a></p>`}
  </section>
  <section class="work-section"><h2>Nguyện vọng và chỉ tiêu</h2>
    <p>${state.preferences_closed ? 'Đã khóa nộp nguyện vọng.' : 'Đang mở nộp nguyện vọng.'}
      <strong>${state.pending_count}</strong> nguyện vọng đang chờ giảng viên quyết định.</p>
    ${!state.published && state.roster_loaded ? `<form data-action="${state.preferences_closed ? 'reopen' : 'close'}">
      <button class="secondary">${state.preferences_closed ? 'Mở lại nộp nguyện vọng' : 'Khóa nộp nguyện vọng'}</button></form>` : ''}
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${!state.published && state.roster_loaded && catalog.length ? `<form data-action="proposal">
      <fieldset><legend>Giảng viên tham gia phân công</legend><div class="thesis-roster">
      ${catalog.map(a => {
        const required = state.accepted_advisors.includes(a.advisor_id);
        return `<label class="advisor-option"><input type="checkbox" name="advisor_id" value="${esc(a.advisor_id)}" ${required || selected.has(a.advisor_id) ? 'checked' : ''} ${required ? 'disabled' : ''}>
        <span>${esc(a.advisor_name)}<small data-quota="${esc(a.advisor_id)}"></small></span></label>`;
      }).join('')}
      </div></fieldset><p class="help">Chỉ tiêu tổng bằng số đã nhận cộng số chỗ chia đều từ phần còn lại.</p>
      <button class="primary" ${state.preferences_closed ? '' : 'disabled'}>Chốt chỉ tiêu và chạy PPO / DQN</button>
    </form>` : ''}
  </section>
  ${manualAllocation()}
  ${proposal?.results ? `<section class="work-section" aria-labelledby="semester-replay-title">
    <h2 id="semester-replay-title">Phát lại quá trình phân công</h2>
    <div id="semester-replay"></div></section>` : ''}
  <section class="work-section"><h2>${state.published ? 'Kết quả đã công bố' : 'So sánh phương án phân công'}</h2>
    ${state.published_algorithm ? `<p>Phương án đang công bố · <strong>${esc(state.published_algorithm === 'manual' ? 'Thủ công' : state.published_algorithm.toUpperCase())}</strong></p>` : ''}
    ${proposal?.results ? comparison(proposal) : proposal ? tables(proposal) : '<p>So sánh sẽ xuất hiện sau khi chạy cả hai mô hình.</p>'}
    ${proposal?.results && proposal.status === 'feasible' && !state.published ? `<form data-action="publish" class="thesis-actions thesis-publish">
      <label>Phương án công bố <select name="algorithm" required><option value="">Chọn phương án</option><option value="ppo">PPO</option><option value="dqn">DQN</option></select></label>
      <label class="confirmation"><input type="checkbox" required> Tôi đã rà soát phương án và muốn gửi danh sách đến giảng viên.</label>
      <button class="primary">Công bố danh sách</button>
    </form>` : ''}
    ${state.published ? `<form data-action="revoke" class="thesis-publish">
      <label class="confirmation"><input type="checkbox" required> Ẩn danh sách đang công bố để sửa phương án.</label>
      <button class="secondary">Thu hồi công bố</button>
    </form>` : ''}
  </section></div>
  <aside class="work-section dean-threshold" aria-labelledby="threshold-title">
    <h2 id="threshold-title">Ngưỡng tin tưởng</h2>
    <strong class="threshold-value">${state.threshold}%</strong>
    <p class="help">So sánh điểm phù hợp E4 của phương án PPO và DQN. E4 là điểm tương thích, chưa được hiệu chuẩn thành xác suất.</p>
    ${state.published ? '' : `<form data-action="threshold">
      <label for="confidence-threshold">Ngưỡng (%)</label><input type="number" id="confidence-threshold" name="threshold" min="0" max="100" step="1" required value="${state.threshold}">
      <button class="secondary">Lưu ngưỡng</button>
    </form>`}
    <ul class="confidence-key"><li><span class="thesis-confidence thesis-confidence-high">Cao</span> Cả hai đạt</li>
      <li><span class="thesis-confidence thesis-confidence-review">Trung bình</span> Một phương án đạt</li>
      <li><span class="thesis-confidence thesis-confidence-low">Chưa đủ bằng chứng</span> Chưa có phương án đạt</li></ul>
  </aside></div>`;
}

function updatePreviewQuotas() {
  const controls = [...content.querySelectorAll('[data-action="proposal"] input[name="advisor_id"]:checked')];
  const ids = controls.map(input => input.value).sort();
  const counts = state.accepted_counts;
  const remaining = state.student_count - Object.values(counts).reduce((sum, count) => sum + count, 0);
  const shares = new Map(ids.map((id, index) => [id, Math.floor(remaining / ids.length) + Number(index < remaining % ids.length)]));
  for (const label of content.querySelectorAll('[data-quota]')) {
    const id = label.dataset.quota;
    const accepted = counts[id] ?? 0;
    const share = shares.get(id);
    label.textContent = share === undefined ? '' : `Đã nhận ${accepted} · Chia thêm ${share} · Tổng ${accepted + share}`;
  }
  const run = content.querySelector('[data-action="proposal"] button');
  if (run) run.disabled = !state.preferences_closed || !ids.length;
  const publish = content.querySelector('[data-action="publish"] button');
  if (publish) {
    const previous = state.proposal.quotas.map(q => q.advisor_id).sort();
    publish.disabled = JSON.stringify(ids) !== JSON.stringify(previous);
  }
}

function renderDean() {
  stopReplay();
  manualDirty = false;
  content.innerHTML = deanView();
  updatePreviewQuotas();
  const player = $('semester-replay');
  if (!player) return;
  const {results, quotas} = state.proposal;
  const names = new Map(Object.values(results).flatMap(run => run.assignments.map(row => [row.user_id, row.student_name])));
  const advisors = new Map(quotas.map(row => [row.advisor_id, row.advisor_name]));
  stopReplay = mountReplay(player, {runs: results, quotas, initial: state.published_algorithm,
    studentName: id => names.get(id) ?? id, advisorName: id => advisors.get(id) ?? advisorName(id)});
}

function comparison(proposal) {
  const {ppo, dqn} = proposal.results;
  if (proposal.status !== 'feasible') return '<p class="status-error">Không thể phân công đủ với danh sách và chỉ tiêu hiện tại. Kiểm tra các giảng viên tham gia và quyết định từ chối.</p>';
  const byStudent = new Map(dqn.assignments.map(row => [row.user_id, row]));
  const byAdvisor = run => run.assignments.reduce((groups, row) => {
    if (!groups.has(row.advisor_id)) groups.set(row.advisor_id, []);
    groups.get(row.advisor_id).push(row);
    return groups;
  }, new Map());
  const groups = [byAdvisor(ppo), byAdvisor(dqn)];
  const score = value => value == null ? 'Chưa có điểm' : percent(value);
  const loadAndFit = rows => {
    const scores = rows.flatMap(row => row.score == null ? [] : [row.score]);
    return `<td>${rows.length} sinh viên<small>${score(scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null)}</small></td>`;
  };
  const labels = ['Chưa đủ bằng chứng', 'Trung bình', 'Cao'];
  const tones = ['low', 'review', 'high'];
  const grades = ppo.assignments.map(a => {
    const other = byStudent.get(a.user_id);
    return Number(a.score != null && a.score * 100 >= state.threshold - 1e-9) +
      Number(other.score != null && other.score * 100 >= state.threshold - 1e-9);
  });
  const same = ppo.assignments.filter(a => byStudent.get(a.user_id).advisor_id === a.advisor_id).length;
  return `<p class="help">Checkpoint ${esc(proposal.checkpoint || 'đang phục vụ')} · Hai mô hình chọn cùng giảng viên cho ${same}/${ppo.assignments.length} sinh viên.
    Cao ${grades.filter(n => n === 2).length} · Trung bình ${grades.filter(n => n === 1).length} · Chưa đủ bằng chứng ${grades.filter(n => n === 0).length}.</p>
    <div class="table-scroll" tabindex="0" role="region" aria-label="So sánh chỉ số mô hình"><table><caption>Chỉ số PPO và DQN</caption>
      <thead><tr><th scope="col">Mô hình</th><th scope="col">Phân đủ</th><th scope="col">Điểm phù hợp trung bình</th>
        <th scope="col">Có điểm</th><th scope="col">Vi phạm chỉ tiêu</th><th scope="col">Thời gian</th></tr></thead>
      <tbody>${Object.entries(proposal.results).map(([name, run]) => `<tr><th scope="row">${name.toUpperCase()}</th>
        <td>${percent(run.metrics.coverage)}</td><td>${score(run.metrics.mean_compatibility)}</td><td>${run.metrics.scored_students}</td>
        <td>${run.metrics.constraint_violations}</td><td>${Number(run.elapsed_seconds).toFixed(2)} giây</td></tr>`).join('')}</tbody></table></div>
    <div class="table-scroll" tabindex="0" role="region" aria-label="Chuyên môn và chỉ tiêu"><table><caption>Chuyên môn và tải theo giảng viên</caption>
      <thead><tr><th scope="col">Giảng viên</th><th scope="col">Chủ đề và kỹ năng có trong hồ sơ</th><th scope="col">Đã nhận</th>
        <th scope="col">Chỉ tiêu</th><th scope="col">PPO · tải / E4</th><th scope="col">DQN · tải / E4</th></tr></thead>
      <tbody>${proposal.quotas.map(q => `<tr><th scope="row">${esc(q.advisor_name)}</th><td>${esc(q.skills.join(', ') || 'Chưa có nhãn')}</td>
        <td>${q.accepted}</td><td>${q.total}</td>${groups.map(group => loadAndFit(group.get(q.advisor_id) ?? [])).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="table-scroll" tabindex="0" role="region" aria-label="So sánh từng sinh viên"><table><caption>Đối chiếu từng sinh viên</caption>
      <thead><tr><th scope="col">Sinh viên</th><th scope="col">PPO</th><th scope="col">DQN</th><th scope="col">Mức tin tưởng</th></tr></thead>
      <tbody>${ppo.assignments.map((row, i) => {
        const other = byStudent.get(row.user_id);
        return `<tr><th scope="row">${esc(row.student_name)}<small>${esc(row.student_id)} · ${row.accepted ? 'Đã được nhận' : row.submitted ? 'Đã điền hồ sơ' : 'Từ CSV'}</small></th>
          <td>${esc(row.advisor_name)}<small>${score(row.score)}</small></td><td>${esc(other.advisor_name)}<small>${score(other.score)}</small></td>
          <td><span class="thesis-confidence thesis-confidence-${tones[grades[i]]}">${labels[grades[i]]}</span>${other.advisor_id !== row.advisor_id ? '<small>Khác giảng viên</small>' : ''}</td></tr>`;
      }).join('')}</tbody></table></div>`;
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
    if (user.role === 'dean') renderDean();
    else content.innerHTML = (user.role === 'student' ? studentView : facultyView)();
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
  if (input.matches('[data-action="manual"] select')) {
    manualDirty = true;
    const publish = content.querySelector('[data-action="publish-manual"] button');
    if (publish) publish.disabled = true;
  }
  if (input.name === 'roles') updateTracks(input.form);
  if (input.matches('[data-action="proposal"] input')) {
    if (input.checked) selected.add(input.value);
    else selected.delete(input.value);
    updatePreviewQuotas();
  }
});

content.addEventListener('click', event => {
  const button = event.target.closest('[data-copy-allocation]');
  if (!button) return;
  const assignments = state.proposal.results[button.dataset.copyAllocation].assignments;
  manualDirty = true;
  const advisors = new Map(assignments.map(row => [row.student_id, row.advisor_id]));
  for (const select of button.form.querySelectorAll('select')) {
    select.value = advisors.get(select.name) ?? '';
  }
});

content.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const action = form.dataset.action;
  const data = new FormData(form);
  const contact = {email: data.get('contact_email'), phone: data.get('contact_phone')};
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
    payload = {advisor_ids: ids, topic_description: data.get('topic_description'), contact};
  } else if (action === 'withdraw') payload = {advisor_ids: []};
  else if (action === 'topic') payload = {topic_description: data.get('topic_description')};
  else if (action === 'contact') payload = contact;
  else if (action === 'decision') payload = {decision: event.submitter.value, user_id: form.dataset.student};
  else if (action === 'threshold') payload = {threshold: Number(data.get('threshold'))};
  else if (action === 'proposal') payload = {advisor_ids: [...new Set([...selected, ...state.accepted_advisors])]};
  else if (action === 'manual') payload = {id: state.manual?.id ?? null,
    assignments: Object.fromEntries([...data].filter(([, advisor]) => advisor))};
  else if (action === 'publish-manual') payload = {id: state.manual.id, algorithm: 'manual'};
  else if (action === 'publish') payload = {id: state.proposal.id, algorithm: data.get('algorithm')};
  else if (action === 'roster') {
    const file = data.get('csv_file');
    if (!file?.size || file.size > 1024 * 1024) {
      showStatus('Chọn tệp CSV có nội dung và dung lượng tối đa 1 MB.', true, true);
      return;
    }
    try { payload = {csv_text: await file.text()}; }
    catch { showStatus('Không đọc được tệp CSV.', true, true); return; }
  } else if (['close', 'reopen', 'revoke'].includes(action)) payload = {};
  const buttons = [...content.querySelectorAll('button:not(:disabled)')];
  saving = true;
  buttons.forEach(button => { button.disabled = true; });
  showStatus(action === 'proposal' ? 'Đang tính phương án…' : 'Đang lưu…', false, true);
  try {
    await api('/' + ({withdraw: 'choice', 'publish-manual': 'publish'}[action] ?? action), payload);
    await refresh();
    const messages = {assessment: 'Đã lưu kết quả đánh giá.', choice: 'Đã lưu nguyện vọng theo thứ tự ưu tiên.', withdraw: 'Đã rút các nguyện vọng đang chờ.',
      topic: 'Đã lưu mô tả đề tài.',
      contact: 'Đã lưu thông tin liên hệ.',
      roster: 'Đã lưu danh sách khóa luận của kỳ.', close: 'Đã khóa nộp nguyện vọng. Giảng viên vẫn có thể duyệt.',
      reopen: 'Đã mở lại nộp nguyện vọng.', revoke: 'Đã thu hồi công bố. Có thể chỉnh và chạy lại.',
      decision: 'Đã lưu quyết định.', threshold: 'Đã lưu ngưỡng.', publish: 'Đã công bố kết quả phân công.',
      manual: 'Đã lưu phân công thủ công.', 'publish-manual': 'Đã công bố bản phân công thủ công.',
      proposal: state.proposal?.status === 'feasible' ? 'Phương án đã sẵn sàng để rà soát.' : 'Chưa có phương án khả thi.'};
    showStatus(messages[action]);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    saving = false;
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
  document.querySelectorAll('[data-student]').forEach(link => { link.hidden = user.role !== 'student'; });
  $('thesis-chat').hidden = user.role !== 'student';
  try {
    await refresh();
    showStatus('');
  } catch (error) {
    showStatus(error.message, true);
  }
}

if (['faculty', 'dean'].includes(user?.role)) {
  setInterval(async () => {
    if (!state || document.hidden || saving || manualDirty || content.contains(document.activeElement)) return;
    const previous = state;
    try {
      const latest = await api();
      if (saving || manualDirty || state !== previous || content.contains(document.activeElement)
          || JSON.stringify(previous) === JSON.stringify(latest)) return;
      state = latest;
      if (user.role === 'dean') {
        if (content.querySelector('input[type="file"]')?.files.length) { state = previous; return; }
        renderDean();
      } else {
        content.innerHTML = facultyView();
        if (latest.published && !previous.published) showStatus('Trưởng khoa đã công bố kết quả.');
        else if (!latest.published && previous.published) showStatus('Trưởng khoa đã thu hồi danh sách công bố.');
        else if (latest.requests.some(r => r.status === 'pending'
          && !previous.requests.some(old => old.user_id === r.user_id && old.status === 'pending'))) {
          showStatus('Bạn có nguyện vọng hướng dẫn mới.');
        }
      }
    } catch { /* Keep the last loaded faculty view if polling fails. */ }
  }, 30000);
}
addEventListener('pagehide', () => stopReplay(), {once: true});
