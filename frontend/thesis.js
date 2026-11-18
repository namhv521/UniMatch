import { confidenceLabel, requireSession } from './portal.js';
import { mountReplay } from './allocation-replay.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles = {student: 'Hồ sơ & Lộ trình Khóa luận', faculty: 'Xét duyệt & Đồng hành Hướng dẫn', dean: 'Điều phối & Phân công Khóa luận'};
const roleBadges = {student: 'Sinh viên', faculty: 'Giảng viên hướng dẫn', dean: 'Trưởng khoa / Điều phối'};
const statusNames = {pending: 'Chờ phản hồi', accepted: 'Đã nhận', rejected: 'Đã từ chối', withdrawn: 'Đã rút'};
const milestoneStatusNames = {pending: 'Chưa nộp', submitted: 'Đã nộp · Chờ duyệt', revision_requested: 'Cần chỉnh sửa', approved: 'Đã duyệt'};
const outcomeNames = {excellent: 'Hoàn thành xuất sắc', satisfactory: 'Hoàn thành đạt yêu cầu', needs_improvement: 'Cần cải thiện'};
const skillNames = {strong: 'Điểm mạnh', demonstrated: 'Có tín hiệu từ bài làm', self_reported: 'Tự đánh giá', unassessed: 'Chưa đủ tín hiệu'};
const levels = ['Chưa biết', 'Cơ bản', 'Khá', 'Tốt', 'Thành thạo'];
const orientations = {exploring: 'Chưa có định hướng', idea: 'Có ý tưởng, đang cân nhắc', defined: 'Đã có đề tài cụ thể'};
const majors = {it: 'Công nghệ thông tin', cs: 'Khoa học máy tính', other: 'Khác'};

const prompts = {
  '✨ Hồ sơ của em hợp ai?': 'Dựa trên bài làm và hồ sơ của em thì hợp với giảng viên nào nhất?',
  'AI / Học máy': 'Giảng viên nào có công trình về trí tuệ nhân tạo và học máy?',
  'LLM / RAG Agent': 'Giảng viên nào có hướng nghiên cứu về LLM, AI Agent hoặc RAG?',
  'Computer Vision': 'Giảng viên nào hướng dẫn đề tài thị giác máy tính và nhận diện đối tượng?',
  'Web Full-stack': 'Giảng viên nào phù hợp với đề tài phát triển ứng dụng web và kiến trúc microservices?',
  'Hệ thống thông tin & BA': 'Giảng viên nào chuyên về hệ thống thông tin quản lý, chuyển đổi số và phân tích nghiệp vụ?',
  'So sánh 2 Giảng viên': 'So sánh chuyên môn giữa TS PHẠM XUÂN LÂM và ThS. NGUYỄN HÙNG VIỆT',
  '🛡️ Thử Guardrail (Ngoài lề)': 'Hôm nay thời tiết thế nào và dự đoán giá vàng ngày mai?',
};

const errors = {
  semester_not_configured: 'Chưa mở kỳ đăng ký. Liên hệ khoa để biết lịch mở kỳ.',
  advisor_account_unassigned: 'Tài khoản giảng viên chưa được gán danh mục cho kỳ này. Liên hệ khoa để kiểm tra.',
  semester_published: 'Kỳ này đã công bố kết quả. Tải lại trang để xem.',
  verified_artifacts_not_ready: 'Chưa tải được danh mục giảng viên. Vui lòng thử lại.',
  verified_advisor_knowledge_not_ready: 'Trợ lý chưa tải được nguồn giảng viên. Vui lòng thử lại.',
  assessment_incomplete: 'Hãy hoàn thành tất cả câu khảo sát và trắc nghiệm.',
  assessment_required: 'Hãy lưu khảo sát và trắc nghiệm kỹ năng trước.',
  accepted_request_locked: 'Giảng viên đã nhận hướng dẫn. Nguyện vọng này đã được giữ chỗ.',
  request_already_rejected: 'Giảng viên đã từ chối yêu cầu này. Hãy chọn giảng viên khác.',
  pending_request_required: 'Yêu cầu đã thay đổi. Tải lại trang để xem trạng thái mới.',
  include_accepted_advisors: 'Danh sách phân công cần gồm tất cả giảng viên đã nhận sinh viên.',
  invalid_advisor_selection: 'Chọn tối đa ba giảng viên khác nhau và xếp theo thứ tự ưu tiên.',
  invalid_topic_description: 'Mô tả đề tài cần dài tối đa 2.000 ký tự.',
  invalid_contact: 'Nhập số điện thoại hợp lệ để giảng viên có thể liên hệ.',
  invalid_manual_reason: 'Lý do điều chỉnh cần dài tối đa 2.000 ký tự.',
  manual_exception_reason_required: 'Bản thủ công có ngoại lệ. Hãy bổ sung lý do, lưu bản nháp rồi công bố lại.',
  invalid_email: 'Nhập địa chỉ email liên hệ hợp lệ.',
  email_account_not_found: 'Không tìm thấy tài khoản email này.',
  invalid_reset_code: 'Mã khôi phục không hợp lệ hoặc đã hết hạn.',
  email_auth_rate_limited: 'Đã cấp quá nhiều mã. Vui lòng đợi một phút rồi thử lại.',
  invalid_registration_count: 'Cần từ 1 đến 1.000 sinh viên đã đăng ký để tạo phương án.',
  stale_manual_assignment: 'Bản phân công thủ công đã thay đổi. Tải lại trang rồi chỉnh tiếp.',
  invalid_manual_assignment: 'Có sinh viên hoặc giảng viên không hợp lệ. Tải lại danh sách rồi thử lại.',
  incomplete_manual_assignment: 'Hãy tải lại trang và lưu đủ phân công cho mọi sinh viên trước khi công bố.',
  stale_or_infeasible_proposal: 'Phương án đã thay đổi hoặc không khả thi. Hãy tạo lại trước khi công bố.',
  role_required: 'Tài khoản hiện tại không có quyền thực hiện thao tác này.',
  invalid_roster_csv: 'Không đọc được CSV. Hãy lưu lại dưới dạng CSV UTF-8.',
  invalid_roster_headers: 'CSV cần các cột student_id, name, email. Có thể thêm phone, topic, skills, enrollment_code.',
  invalid_roster_row: 'Dòng CSV có dữ liệu thiếu hoặc sai định dạng.',
  duplicate_roster_identity: 'Mã sinh viên hoặc email bị trùng trong CSV.',
  roster_limit: 'Danh sách hỗ trợ tối đa 500 sinh viên mỗi kỳ.',
  semester_roster_required: 'Hãy nhập danh sách CSV của kỳ.',
  not_in_semester_roster: 'Tài khoản của bạn chưa có hoặc chưa xác minh trong danh sách khóa luận của kỳ.',
  invalid_enrollment_code: 'Mã xác minh ghi danh hoặc mã sinh viên chưa khớp với danh sách của khoa.',
  preferences_closed: 'Trưởng khoa đã khóa nộp nguyện vọng.',
  close_preferences_first: 'Hãy khóa nộp nguyện vọng trước khi chạy mô hình.',
  matching_models_unavailable: 'Server chưa nạp đủ checkpoint PPO và DQN.',
  matching_model_contract_mismatch: 'Checkpoint đang phục vụ chưa khớp cấu hình suy luận.',
  publication_algorithm_required: 'Chọn phương án (Hungarian, PPO hoặc DQN) trước khi công bố.',
  semester_not_published: 'Kỳ này chưa có danh sách đã công bố.',
  invalid_advisor_skills_csv: 'Tệp CSV kỹ năng giảng viên không hợp lệ. Hãy tải tệp mẫu hiện tại để chỉnh sửa.',
  invalid_advisor_skills_headers: 'Tiêu đề cột CSV kỹ năng giảng viên chưa đúng chuẩn.',
  invalid_advisor_skills_row: 'Có mã giảng viên không thuộc danh mục đang phục vụ.',
  insufficient_custom_quota: 'Tổng chỉ tiêu tùy chỉnh phải đủ cho toàn bộ sinh viên và không thấp hơn số đã nhận.',
  invalid_custom_quota: 'Chỉ tiêu tùy chỉnh không hợp lệ.',
  invalid_submission_url: 'Liên kết bài nộp cần bắt đầu bằng https:// hoặc http://.',
  milestone_content_required: 'Hãy nhập nội dung tóm tắt hoặc liên kết tài liệu cho mốc này.',
};

let user, state, catalog = [], rankings = [], catalogError = '', rankingError = '', selected, previousQuestion, saving = false;
let facultySearch = '', facultyStatus = 'all', rosterSearch = '', rosterStatus = 'all', advisorDirSearch = '';
let recoveryCodeInfo = null;
let studentDirty = false;
let stopReplay = () => {};

const content = $('thesis-content');
const notice = $('thesis-status');
const percent = score => (score * 100).toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + '%';
const advisorName = id => catalog.find(advisor => advisor.advisor_id === id)?.advisor_name ?? id;
const initials = name => String(name || 'GV').replace(/^(?:PGS\.?\s*|GS\.?\s*|TS\.?\s*|ThS\.?\s*|CN\.?\s*)+/i, '')
  .trim().split(/\s+/).slice(-2).map(w => w[0] || '').join('').toUpperCase() || 'GV';
const options = (values, selectedIndex) => values.map((value, index) => `<option value="${index}" ${index === selectedIndex ? 'selected' : ''}>${esc(value)}</option>`).join('');

function pushToast(text, isError = false) {
  const stack = $('toast-stack');
  if (!stack || !text || typeof document.createElement !== 'function') return;
  const item = document.createElement('div');
  item.className = `toast-item${isError ? ' error' : ''}`;
  item.textContent = text;
  stack.append(item);
  if (typeof setTimeout === 'function') {
    setTimeout(() => { if (item.remove) item.remove(); }, 3800);
  }
}

async function confirmDialog(title, message, confirmLabel = 'Xác nhận') {
  const dialog = $('confirm-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return true;
  $('confirm-dialog-title').textContent = title;
  $('confirm-dialog-message').textContent = message;
  $('confirm-dialog-accept').textContent = confirmLabel;
  dialog.showModal();
  return new Promise(resolve => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true });
  });
}

function formatRichText(text) {
  return esc(text).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(\[\d+\])`/g, '<strong>$1</strong>');
}

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
  if (!skills?.length) return '<p class="help">Chưa có nhóm kỹ năng được đánh giá.</p>';
  return `<ul class="thesis-skills">${skills.map(skill => `<li>
    <strong>${esc(skill.label)}</strong>
    <span><span class="thesis-confidence ${skill.status === 'strong' ? 'thesis-confidence-high' : skill.status === 'demonstrated' ? 'thesis-confidence-review' : 'thesis-confidence-low'}">${esc(skillNames[skill.status])}</span> · ${skill.correct}/${skill.total} câu đúng</span>
  </li>`).join('')}</ul>`;
}

function assessmentForm(profile) {
  const latest = profile?.version === state.assessment_version ? profile : null;
  return `<form data-action="assessment">
    <div class="profile-fields">
      <label>Chuyên ngành đào tạo <select name="major"><option value="">Chọn nếu muốn</option>${Object.entries(majors).map(([key, label]) =>
        `<option value="${key}" ${latest?.major === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <label>Mức độ định hình đề tài hiện tại <select name="orientation" required><option value="">Chọn trạng thái</option>
        ${Object.entries(orientations).map(([key, label]) => `<option value="${key}" ${latest?.orientation === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
    </div>
    <fieldset>
      <legend>Chọn hướng chuyên môn bạn quan tâm</legend>
      <p class="help">Chọn từ 1 hướng trở lên. Mỗi hướng gồm mức tự đánh giá, công cụ thực hành và 5 câu trắc nghiệm tình huống.</p>
      <div class="track-picker">${state.assessment.map(role => `<label class="advisor-option">
        <input type="checkbox" name="roles" value="${esc(role.id)}" ${latest?.roles?.includes(role.id) ? 'checked' : ''}>
        <span><b>${esc(role.label)}</b></span></label>`).join('')}</div>
    </fieldset>
    <p class="help" data-role-count aria-live="polite"></p>
    ${state.assessment.map(role => {
      const chosen = latest?.roles?.includes(role.id);
      return `<fieldset data-track="${esc(role.id)}" ${chosen ? '' : 'hidden disabled'}>
        <legend>${esc(role.label)}</legend>
        <label>Mức độ tự đánh giá năng lực <select name="survey-${esc(role.id)}" required><option value="">Chọn mức độ</option>${options(levels, latest?.survey?.[role.id])}</select></label>
        <p class="help">Công cụ &amp; công nghệ đã từng sử dụng · tùy chọn</p>
        <div class="track-tools">${(role.tools || []).map(tool => `<label class="advisor-option"><input type="checkbox" name="tools-${esc(role.id)}" value="${esc(tool)}"
          ${latest?.tools?.[role.id]?.includes(tool) ? 'checked' : ''}><span>${esc(tool)}</span></label>`).join('')}</div>
        ${role.questions.map((q, i) => `<div class="quiz-question-card">
          <p class="quiz-question-title">Câu ${i + 1}/5 · ${esc(q.prompt)}</p>
          <div class="quiz-options-grid">
            ${q.options.map((opt, optIdx) => `<label class="quiz-choice-card">
              <input type="radio" name="answer-${esc(role.id)}-${i}" value="${optIdx}" ${latest?.answers?.[role.id]?.[i] === optIdx ? 'checked' : ''} required>
              <span>${esc(opt)}</span>
            </label>`).join('')}
          </div>
        </div>`).join('')}
      </fieldset>`;
    }).join('')}
    <button class="primary" ${latest?.roles?.length ? '' : 'disabled'}>${profile ? 'Cập nhật bài đánh giá kỹ năng' : 'Lưu bài đánh giá & ghi danh kỳ học'}</button>
  </form>`;
}

function dossierSection() {
  const profile = state.profile;
  const dossier = state.dossier;
  const locked = state.published || state.preferences_closed;
  if (!profile) {
    return `<section id="section-dossier" class="work-section">
      <h2>2. Chuẩn hóa Hồ sơ &amp; Giọng văn Học thuật</h2>
      <p class="empty-state">Hoàn thành phần <strong>Khảo sát &amp; Trắc nghiệm</strong> phía trên trước để mở công cụ chuẩn hóa ý tưởng đề tài sang văn phong học thuật.</p>
    </section>`;
  }
  return `<section id="section-dossier" class="work-section">
    <div class="section-heading">
      <div>
        <h2>2. Chuẩn hóa Giọng văn &amp; Hồ sơ Học thuật</h2>
        <p>Bạn có thể viết tự nhiên bằng lời của mình (kể cả câu rời rạc, viết tắt, văn nói). Hệ thống sẽ chuẩn hóa thành hồ sơ đề cương mạch lạc và trích xuất bộ nhãn kỹ năng chuẩn trước khi gửi giảng viên.</p>
      </div>
      ${!locked ? `<button type="button" class="secondary" data-fill-colloquial-sample>✍️ Thử đoạn văn nói mẫu</button>` : ''}
    </div>

    ${dossier ? `<div class="dossier-diff-grid">
      <div class="dossier-box">
        <div class="dossier-box-header">
          <strong>Nội dung sinh viên nhập gốc</strong>
          <span class="dossier-badge raw">Văn bản thô</span>
        </div>
        ${dossier.raw_title ? `<p><strong>Ý tưởng ban đầu:</strong> ${esc(dossier.raw_title)}</p>` : ''}
        <p>${esc(dossier.raw_description || 'Chưa nhập mô tả tự do (tổng hợp từ bài khảo sát).')}</p>
        ${dossier.raw_background ? `<p class="help"><strong>Kinh nghiệm thêm:</strong> ${esc(dossier.raw_background)}</p>` : ''}
      </div>
      <div class="dossier-box standardized">
        <div class="dossier-box-header">
          <strong>Hồ sơ Học thuật Chuẩn (Gửi Giảng viên &amp; Bộ giải)</strong>
          <span class="dossier-badge">✓ ${dossier.normalizer_mode === 'llm_grounded' ? 'LLM + Taxonomy Chuẩn hóa' : 'Chuẩn hóa Học thuật'}</span>
        </div>
        <h3 style="margin:4px 0 8px">${esc(dossier.formal_title)}</h3>
        <p style="color:var(--ink);margin:0 0 8px">${esc(dossier.formal_summary)}</p>
        <p class="help" style="margin:0 0 8px"><strong>Phương pháp &amp; phạm vi:</strong> ${esc(dossier.methodology_scope)}</p>
        <div class="skill-chip-group">
          ${(dossier.normalized_skills || []).map(s => `<span class="skill-chip ${s.source?.startsWith('verified') ? 'verified' : s.source?.startsWith('extracted') ? 'extracted' : ''}">${esc(s.label)}</span>`).join('')}
        </div>
        ${(dossier.tone_notes || []).length ? `<p class="help" style="margin-top:10px">💡 ${esc(dossier.tone_notes.join(' '))}</p>` : ''}
      </div>
    </div>` : ''}

    ${!locked ? `<details ${dossier ? '' : 'open'} class="xai-details-panel" style="margin-top:16px">
      <summary>${dossier ? 'Chỉnh sửa & chuẩn hóa lại mô tả đề tài / kinh nghiệm' : 'Nhập ý tưởng thô để chuẩn hóa sang hồ sơ học thuật'}</summary>
      <form data-action="normalize" style="margin-top:14px;display:grid;gap:12px">
        <label class="topic-field">Ý tưởng hoặc tên nháp đề tài <span class="help">(Tùy chọn · có thể viết ngắn gọn)</span>
          <input name="raw_title" maxlength="300" value="${esc(dossier?.raw_title ?? '')}" placeholder="VD: làm cái web bán sách có tích hợp con bot tư vấn rag...">
        </label>
        <label class="topic-field">Mô tả mong muốn, bài toán hoặc công nghệ bằng lời của bạn
          <textarea name="raw_description" rows="4" maxlength="2000" placeholder="VD: dạ em muốn làm một cái web thương mại điện tử bằng python fastapi với reactjs, có con chatbot tư vấn sách theo kiểu rag mà em chưa rành phần triển khai docker lắm...">${esc(dossier?.raw_description ?? state.topic_description ?? '')}</textarea>
        </label>
        <label class="topic-field">Kinh nghiệm, môn học hoặc dự án nhỏ đã từng làm <span class="help">(Tùy chọn)</span>
          <input name="raw_background" maxlength="1000" value="${esc(dossier?.raw_background ?? '')}" placeholder="VD: đã học lập trình python, cơ sở dữ liệu postgres, từng làm bài tập lớn phân loại văn bản">
        </label>
        <div class="thesis-actions">
          <button class="primary">✨ Chuẩn hóa giọng văn &amp; Lưu hồ sơ học thuật</button>
        </div>
      </form>
    </details>` : ''}
  </section>`;
}

function topicField() {
  const defaultTopic = state.dossier
    ? `${state.dossier.formal_title} — ${state.dossier.formal_summary}`
    : (state.topic_description || '');
  return `<label class="topic-field">Tóm tắt đề tài gửi kèm nguyện vọng <span class="help">(Tự động đồng bộ từ Hồ sơ Học thuật Chuẩn hoặc tùy chỉnh thêm)</span>
    <textarea name="topic_description" rows="3" maxlength="2000" aria-describedby="topic-guidance"
      placeholder="Nội dung đề tài chuẩn hóa gửi tới giảng viên xét duyệt...">${esc(state.topic_description || defaultTopic)}</textarea>
  </label><p id="topic-guidance" class="help">Giảng viên sẽ xem cả Hồ sơ Học thuật Chuẩn hóa và điểm tương thích E4 của bạn.</p>`;
}

function contactFields() {
  return `<fieldset><legend>Thông tin liên hệ học vụ</legend>
    <p class="help">Sau khi trưởng khoa công bố, giảng viên hướng dẫn của bạn sẽ dùng email và số điện thoại này để trao đổi.</p>
    <div class="profile-fields" style="margin-bottom:0">
      <label>Email liên hệ <input type="email" name="contact_email" autocomplete="email" maxlength="254" required value="${esc(state.contact?.email ?? '')}"></label>
      <label>Số điện thoại <input type="tel" name="contact_phone" autocomplete="tel" maxlength="24" required value="${esc(state.contact?.phone ?? '')}" placeholder="0912 345 678"></label>
    </div>
  </fieldset>`;
}

function studentStatus() {
  const requests = state.requests ?? [];
  const accepted = requests.some(r => r.status === 'accepted');
  return `${state.preferences_closed ? '<p><strong>Trạng thái kỳ:</strong> Trưởng khoa đã khóa nộp và sửa nguyện vọng.</p>' : !state.in_roster ? '<p class="status-warn"><strong>Lưu ý:</strong> Tài khoản của bạn chưa xác minh hoặc chưa nằm trong danh sách khóa luận kỳ này.</p>' : ''}
    ${accepted && !state.published ? '<p class="status-good"><strong>✓ Giảng viên đã nhận hướng dẫn; cặp hướng dẫn chính thức chờ trưởng khoa công bố.</strong></p>' : ''}
    ${state.published ? '<p class="status-good"><strong>✓ Kết quả phân công đã được trưởng khoa công bố chính thức.</strong></p>' : ''}
    ${state.assignment ? `<p style="font-size:1.05rem;color:var(--ink)"><strong>Giảng viên hướng dẫn chính thức:</strong> ${esc(state.assignment.advisor_name)}</p>` : ''}
    ${requests.length ? `<ul class="thesis-skills">${[...requests].sort((a, b) => (a.rank ?? 4) - (b.rank ?? 4)).map(r => `<li><strong>${r.rank ? `Ưu tiên ${r.rank} · ` : ''}${esc(advisorName(r.advisor_id))}</strong><span class="thesis-confidence ${r.status === 'accepted' ? 'thesis-confidence-high' : r.status === 'pending' ? 'thesis-confidence-review' : 'thesis-confidence-low'}">${statusNames[r.status]}</span></li>`).join('')}</ul>` : '<p>Bạn chưa gửi nguyện vọng hướng dẫn.</p>'}`;
}

function studentMilestonesSection() {
  if (!state.published || !state.assignment) return '';
  const milestones = state.milestones || [];
  const outcome = state.outcome;
  return `<section class="work-section">
    <div class="section-heading">
      <div>
        <h2>Không gian Thực hiện Khóa luận cùng ${esc(state.assignment.advisor_name)}</h2>
        <p>Cập nhật tên đề tài chính thức, nộp báo cáo qua 3 mốc tiến độ và nhận phản hồi trực tiếp từ giảng viên hướng dẫn.</p>
      </div>
      ${outcome ? `<span class="thesis-confidence thesis-confidence-high">Đánh giá cuối kỳ: ${esc(outcomeNames[outcome.rating] || outcome.rating)}</span>` : ''}
    </div>
    ${outcome?.summary_note ? `<p class="status-banner"><strong>Nhận xét tổng kết của giảng viên:</strong> ${esc(outcome.summary_note)}</p>` : ''}
    <div class="milestone-timeline">
      ${milestones.map((m, idx) => `<article class="milestone-card" data-status="${esc(m.status)}">
        <div class="applicant-header">
          <strong>Mốc ${idx + 1} · ${esc(m.label)}</strong>
          <span class="thesis-confidence ${m.status === 'approved' ? 'thesis-confidence-high' : m.status === 'submitted' ? 'thesis-confidence-review' : 'thesis-confidence-low'}">${esc(milestoneStatusNames[m.status] || m.status)}</span>
        </div>
        ${m.advisor_feedback ? `<p style="color:var(--ink);margin:0"><strong>Phản hồi GV:</strong> ${esc(m.advisor_feedback)}</p>` : ''}
        <form data-action="milestone" style="display:grid;gap:8px;margin-top:4px">
          <input type="hidden" name="milestone_key" value="${esc(m.key)}">
          ${idx === 0 ? `<label style="font-size:.84rem">Tên đề tài chính thức
            <input name="official_title" maxlength="300" value="${esc(m.official_title || state.dossier?.formal_title || '')}" placeholder="Tên đề tài thống nhất với giảng viên"></label>` : ''}
          <label style="font-size:.84rem">Liên kết tài liệu / mã nguồn (Google Docs, GitHub, PDF)
            <input name="submission_url" type="url" maxlength="500" value="${esc(m.submission_url || '')}" placeholder="https://..."></label>
          <label style="font-size:.84rem">Tóm tắt nội dung đã hoàn thành
            <textarea name="submission_note" rows="2" maxlength="2000" placeholder="Nêu ngắn gọn kết quả đạt được hoặc câu hỏi cần giảng viên góp ý...">${esc(m.submission_note || '')}</textarea></label>
          <button class="${m.status === 'approved' ? 'secondary' : 'primary'}">${m.status === 'pending' ? 'Nộp mốc này' : 'Cập nhật bài nộp'}</button>
        </form>
      </article>`).join('')}
    </div>
  </section>`;
}

function advisorDirectoryCards(canChoose) {
  if (!catalog.length) return '';
  const q = advisorDirSearch.trim().toLocaleLowerCase('vi');
  const filtered = catalog.filter(a => {
    const text = `${a.advisor_name} ${a.summary || ''} ${(a.display_skills || []).join(' ')}`.toLocaleLowerCase('vi');
    return text.includes(q);
  });
  return `<details class="xai-details-panel" style="margin-top:18px" ${rankings.length ? '' : 'open'}>
    <summary>Danh bạ toàn bộ Giảng viên &amp; Ma trận Kỹ năng (${catalog.length} giảng viên)</summary>
    <div class="profile-fields" style="margin-top:12px">
      <label>Tìm theo tên giảng viên, chủ đề hoặc công nghệ
        <input type="search" data-advisor-dir-search value="${esc(advisorDirSearch)}" placeholder="VD: NLP, Computer Vision, Java, Hệ thống thông tin, Python...">
      </label>
    </div>
    <div class="advisor-directory-grid" data-advisor-dir-grid>
      ${filtered.map(a => advisorCardHtml(a, canChoose)).join('') || '<p class="help">Không tìm thấy giảng viên khớp từ khóa.</p>'}
    </div>
  </details>`;
}

function advisorCardHtml(a, canChoose) {
  const skills = a.display_skills || [];
  const rejected = (state.requests || []).some(r => r.advisor_id === a.advisor_id && r.status === 'rejected');
  return `<article class="advisor-card">
    <div>
      <div class="advisor-card-top">
        <div style="display:flex;gap:10px;align-items:center">
          <span class="advisor-avatar" aria-hidden="true">${esc(initials(a.advisor_name))}</span>
          <div>
            <h3>${esc(a.advisor_name)}</h3>
            <p class="advisor-meta">${esc(a.academic_title || 'Giảng viên')} · ${esc(a.department || 'Khoa CNTT')}</p>
          </div>
        </div>
        ${typeof a.accepted_count === 'number' ? `<span class="agent-tag">Đã nhận ${a.accepted_count} · Chờ ${a.pending_count ?? 0}</span>` : ''}
      </div>
      ${a.summary ? `<p class="advisor-summary">${esc(a.summary)}</p>` : ''}
      ${skills.length ? `<div class="skill-chip-group">${skills.slice(0, 7).map(s => `<span class="skill-chip">${esc(s)}</span>`).join('')}</div>` : ''}
    </div>
    <div class="advisor-card-footer">
      <div class="advisor-links">
        ${a.source_url ? `<a href="${esc(a.source_url)}" target="_blank" rel="noopener">Hồ sơ Khoa ↗</a>` : ''}
        ${a.scholar_url ? `<a href="${esc(a.scholar_url)}" target="_blank" rel="noopener">Scholar ↗</a>` : ''}
        ${a.github_url ? `<a href="${esc(a.github_url)}" target="_blank" rel="noopener">GitHub ↗</a>` : ''}
      </div>
      ${canChoose && !rejected ? `<div class="quick-pref-btns">
        <button type="button" class="secondary" data-pick-pref="0" data-advisor-pick="${esc(a.advisor_id)}">+ Ưu tiên 1</button>
        <button type="button" class="secondary" data-pick-pref="1" data-advisor-pick="${esc(a.advisor_id)}">+ ƯT 2</button>
      </div>` : rejected ? '<span class="agent-tag blocked">Đã từ chối</span>' : ''}
    </div>
  </article>`;
}

function studentView() {
  const profile = state.profile;
  const requests = state.requests || [];
  const accepted = requests.some(r => r.status === 'accepted');
  const pending = requests.filter(r => r.status === 'pending').sort((a, b) => a.rank - b.rank);
  const canChoose = profile && state.in_roster && !accepted && !state.published && !state.preferences_closed;
  const available = catalog.filter(a => !requests.some(r => r.advisor_id === a.advisor_id && r.status === 'rejected'));

  const step1Done = Boolean(profile);
  const step2Done = Boolean(state.dossier);
  const step3Done = requests.some(r => ['pending', 'accepted'].includes(r.status));
  const step4Done = Boolean(state.published && state.assignment);

  return `<div class="step-ribbon" aria-label="Tiến độ đăng ký khóa luận">
    <div class="step-pill ${step1Done ? 'done' : 'active'}"><span class="step-num">${step1Done ? '✓' : '1'}</span><div><strong>Khảo sát kỹ năng</strong></div></div>
    <div class="step-pill ${step2Done ? 'done' : step1Done ? 'active' : ''}"><span class="step-num">${step2Done ? '✓' : '2'}</span><div><strong>Chuẩn hóa hồ sơ</strong></div></div>
    <div class="step-pill ${step3Done ? 'done' : step2Done ? 'active' : ''}"><span class="step-num">${step3Done ? '✓' : '3'}</span><div><strong>Gửi nguyện vọng</strong></div></div>
    <div class="step-pill ${step4Done ? 'done' : ''}"><span class="step-num">${step4Done ? '✓' : '4'}</span><div><strong>Thực hiện khóa luận</strong></div></div>
  </div>

  ${state.enrollment_verification_required ? `<section class="work-section" style="border-color:#f59e0b">
    <h2>Xác minh mã ghi danh học kỳ</h2>
    <p>Email của bạn có trong danh sách kỳ học nhưng cần xác nhận mã ghi danh do Khoa cung cấp trước khi gửi nguyện vọng.</p>
    <form data-action="verify-enrollment" class="thesis-actions">
      <label>Mã sinh viên <input name="student_id" required maxlength="80" value="${esc(state.roster_student_id || '')}"></label>
      <label>Mã ghi danh kỳ học <input name="enrollment_code" required maxlength="64" placeholder="Nhập mã ghi danh"></label>
      <button class="primary">Xác minh tài khoản học vụ</button>
    </form>
  </section>` : ''}

  ${studentMilestonesSection()}

  <section id="section-assessment" class="work-section">
    <h2>1. Khảo sát và trắc nghiệm kỹ năng</h2>
    ${profile ? skillList(profile.skills) : '<p>Chọn hướng chuyên môn bạn quan tâm, tự đánh giá và hoàn thành các câu hỏi tình huống để mở gợi ý giảng viên.</p>'}
    ${profile ? '<p class="help">Mức tự đánh giá và số câu đúng mô tả tín hiệu kỹ năng, không trực tiếp cộng vào điểm tương thích. Gợi ý dùng hướng đã chọn; công cụ chỉ bổ sung khi bài làm có tín hiệu. Vì vậy cùng hướng và công cụ có thể cho cùng gợi ý dù số câu đúng khác nhau. Đây không phải bài thi đạt/rớt hay xác nhận năng lực.</p>' : ''}
    ${state.published || state.preferences_closed ? '' : profile ? `<details class="xai-details-panel"><summary>Cập nhật hướng quan tâm và làm lại bài đánh giá</summary>${assessmentForm(profile)}</details>` : assessmentForm(profile)}
  </section>

  ${dossierSection()}

  <section id="section-advisors" class="work-section">
    <h2>3. Giảng viên phù hợp &amp; Giải thích XAI</h2>
    ${rankingError ? `<p class="status-error">${esc(rankingError)}</p>` : rankings.length ?
      `<ol class="match-card-list">${rankings.map((r, idx) => {
        const directions = (r.basis?.topic_tags ?? []).map(id => state.assessment?.find(role => role.id === id)?.label ?? id);
        const terms = (r.basis?.matched_keywords ?? []).slice(0, 6);
        const reason = [`Hướng khớp: ${directions.join(', ') || 'chưa có'}`, terms.length ? `từ khóa khớp hồ sơ GV: ${terms.join(', ')}` : 'đối chiếu đặc trưng chuyên môn'].join(' · ');
        return `<li class="match-card">
          <div class="match-card-header">
            <div>
              <strong>#${idx + 1} · ${esc(r.advisor_name)}</strong>
              ${r.summary ? `<p class="help" style="margin:3px 0 0">${esc(r.summary)}</p>` : ''}
            </div>
            <span class="score-pill">Tương thích E4: ${percent(r.score)}</span>
          </div>
          <small class="help">${esc(reason)}</small>
          ${terms.length ? `<div class="skill-chip-group">${terms.map(t => `<span class="skill-chip verified">${esc(t)}</span>`).join('')}</div>` : ''}
          ${canChoose ? `<div class="quick-pref-btns">
            <button type="button" class="secondary" data-pick-pref="0" data-advisor-pick="${esc(r.advisor_id)}">Chọn làm Ưu tiên 1</button>
            <button type="button" class="secondary" data-pick-pref="1" data-advisor-pick="${esc(r.advisor_id)}">Chọn làm Ưu tiên 2</button>
            <button type="button" class="secondary" data-pick-pref="2" data-advisor-pick="${esc(r.advisor_id)}">Chọn làm Ưu tiên 3</button>
          </div>` : ''}
        </li>`;
      }).join('')}</ol>
      <p class="help" style="margin-top:12px">Điểm thể hiện mức độ tương thích nội dung nghiên cứu &amp; kỹ năng, không phải xác suất được nhận hướng dẫn.</p>` :
      `<p>${profile ? 'Chưa tìm thấy giảng viên có điểm tương thích dương từ hồ sơ hiện tại. Hãy chuẩn hóa thêm mô tả đề tài hoặc hỏi Trợ lý RAG bên dưới.' : 'Danh sách Top-5 gợi ý kèm giải thích XAI sẽ xuất hiện ngay sau khi bạn lưu bài đánh giá.'}</p>`}
    ${advisorDirectoryCards(canChoose)}
  </section>

  <section id="section-preferences" class="work-section">
    <h2>4. Nguyện vọng hướng dẫn khóa luận</h2>
    <div data-student-status role="status">${studentStatus()}</div>
    ${canChoose ? '<p class="help">Chọn từ 1 đến 3 giảng viên theo thứ tự ưu tiên. Khi một giảng viên đồng ý nhận hướng dẫn, các nguyện vọng đang chờ khác sẽ tự động rút.</p>' : ''}
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${canChoose && available.length ? `<form data-action="choice" id="student-choice-form">
      <div class="preference-fields">${[0, 1, 2].map(index => `<label>Nguyện vọng ưu tiên ${index + 1}
        <select name="advisor_id" data-pref-slot="${index}" ${index === 0 ? 'required' : ''}><option value="">${index ? 'Không chọn thêm' : '— Chọn giảng viên ưu tiên 1 —'}</option>
        ${available.map(a => `<option value="${esc(a.advisor_id)}" ${a.advisor_id === pending[index]?.advisor_id ? 'selected' : ''}>${esc(a.advisor_name)}</option>`).join('')}
        </select></label>`).join('')}</div>
      ${topicField()}
      ${contactFields()}
      <div class="thesis-actions">
        <button class="primary">${pending.length ? 'Cập nhật nguyện vọng ưu tiên' : 'Gửi nguyện vọng hướng dẫn'}</button>
      </div>
    </form>` : ''}
    ${accepted && !state.published && !state.preferences_closed ? `<form data-action="topic">${topicField()}<button class="secondary">Lưu cập nhật mô tả đề tài</button></form>` : ''}
    ${(accepted || state.published || state.preferences_closed) && requests.some(r => r.rank) ? `<details class="xai-details-panel"><summary>Cập nhật thông tin liên hệ</summary>
      <form data-action="contact">${contactFields()}<button class="secondary">Lưu thông tin liên hệ</button></form></details>` : ''}
    ${state.published && (state.dossier?.formal_title || state.topic_description) ? `<h3>Đề tài đã đăng ký</h3><p class="topic-description">${esc(state.dossier ? `${state.dossier.formal_title} — ${state.dossier.formal_summary}` : state.topic_description)}</p>` : ''}
    ${canChoose && pending.length ? '<form data-action="withdraw" style="margin-top:12px"><button class="danger-outline">Rút các nguyện vọng đang chờ</button></form>' : ''}
    ${canChoose && !available.length && !catalogError ? '<p>Danh mục hiện chưa còn giảng viên khả dụng để chọn.</p>' : ''}
  </section>`;
}

function filteredFacultyRequests() {
  return (state.requests || []).filter(r => (facultyStatus === 'all' || r.status === facultyStatus)
    && `${r.name} ${r.student_id ?? ''} ${r.topic_description ?? ''} ${r.dossier?.formal_title ?? ''} ${(r.skills || []).map(skill => skill.label).join(' ')}`.toLocaleLowerCase('vi')
      .includes(facultySearch.toLocaleLowerCase('vi')));
}

function updateFacultyRequests() {
  const rows = filteredFacultyRequests();
  content.querySelector('[data-faculty-list]').innerHTML = facultyApplicantRows(rows);
  content.querySelector('[data-faculty-count]').textContent = `${rows.length} / ${state.requests.length} nguyện vọng`;
}

function facultySemestersSection() {
  const sp = state.skill_profile;
  const semesters = state.my_semesters || [];
  return `<section class="work-section">
    <div class="section-heading">
      <div>
        <h2>Hồ sơ Giảng viên &amp; Các kỳ Phân công Hướng dẫn</h2>
        <p>${sp ? `${esc(sp.academic_title || 'Giảng viên')} · ${esc(sp.department || 'Khoa Công nghệ thông tin')} — ${esc(sp.summary || '')}` : `Giảng viên hướng dẫn: ${esc(state.advisor_name || '')}`}</p>
      </div>
      <span class="agent-tag passed">Kỳ đang trực: ${esc(state.semester)}</span>
    </div>
    ${(sp?.display_skills || []).length ? `<div class="skill-chip-group" style="margin-bottom:14px">${sp.display_skills.map(s => `<span class="skill-chip">${esc(s)}</span>`).join('')}</div>` : ''}
    ${semesters.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="Các kỳ hướng dẫn của giảng viên">
      <table>
        <thead><tr><th scope="col">Kỳ học</th><th scope="col">Trạng thái kỳ</th><th scope="col">Đăng ký / Đã nhận</th><th scope="col">Chỉ tiêu</th><th scope="col">Sinh viên được phân công hướng dẫn</th></tr></thead>
        <tbody>${semesters.map(sem => {
          const statusBadge = sem.published
            ? `<span class="thesis-confidence thesis-confidence-high">Đã công bố${sem.algorithm ? ` (${esc(sem.algorithm.toUpperCase())})` : ''}</span>`
            : sem.preferences_closed
              ? '<span class="thesis-confidence thesis-confidence-review">Đã khóa · Đang điều phối</span>'
              : '<span class="thesis-confidence thesis-confidence-low">Đang mở đăng ký</span>';
          const assignedHtml = sem.assigned_students?.length
            ? `<ul style="margin:0;padding-left:16px">${sem.assigned_students.map(st => `<li><strong>${esc(st.student_name)}</strong>${st.student_id ? ` (${esc(st.student_id)})` : ''}${st.email ? ` · ${esc(st.email)}` : ''}${st.phone ? ` · ${esc(st.phone)}` : ''}${st.topic ? `<small>Đề tài: ${esc(st.topic.slice(0, 90))}</small>` : ''}</li>`).join('')}</ul>`
            : sem.published ? '<span class="help">0 sinh viên trong đợt công bố này</span>' : '<span class="help">Chờ Trưởng khoa công bố phương án</span>';
          return `<tr>
            <th scope="row">${esc(sem.semester)}${sem.is_current ? '<small>Kỳ hiện tại</small>' : ''}</th>
            <td>${statusBadge}</td>
            <td><strong>${sem.registered_count}</strong> đăng ký · <strong>${sem.accepted_count}</strong> đã nhận</td>
            <td><strong>${sem.quota ?? '—'}</strong></td>
            <td>${assignedHtml}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    </div>` : ''}
  </section>`;
}

function facultyView() {
  const requests = state.requests || [];
  const accepted = requests.filter(r => r.status === 'accepted').length;
  const pending = requests.filter(r => r.status === 'pending').length;
  const filtered = filteredFacultyRequests();
  return `<div class="kpi-grid">
    <div class="kpi-card"><span>Đăng ký toàn kỳ</span><strong>${state.student_count}</strong><small>Sinh viên tham gia</small></div>
    <div class="kpi-card"><span>Chờ bạn xét duyệt</span><strong>${pending}</strong><small>Nguyện vọng đang chờ</small></div>
    <div class="kpi-card"><span>Đã chủ động nhận</span><strong>${state.teaching_load.accepted}</strong><small>Giữ chỗ trước phân bổ</small></div>
    <div class="kpi-card"><span>Nhóm chính thức</span><strong>${state.teaching_load.assigned} / ${state.teaching_load.quota ?? '—'}</strong><small>Đã phân công / Chỉ tiêu</small></div>
  </div>
  ${facultySemestersSection()}
  <section class="work-section">
    <h2>Sinh viên đăng ký nguyện vọng với ${esc(state.advisor_name || 'bạn')} (Kỳ ${esc(state.semester)})</h2>
    <p><strong>${state.student_count}</strong> sinh viên đã đăng ký khóa luận trong kỳ. <strong>${accepted}</strong> sinh viên đã được bạn nhận trước khi chia số chỗ còn lại.</p>
    <p><strong>Tải hướng dẫn:</strong> ${state.teaching_load.accepted} đã nhận · ${state.teaching_load.assigned} đã phân công chính thức · ${state.teaching_load.quota ?? 'Chưa chốt'} chỉ tiêu.</p>
    <div class="profile-fields faculty-filters">
      <label>Tìm theo tên, MSSV, đề tài hoặc kỹ năng<input type="search" data-faculty-search value="${esc(facultySearch)}" placeholder="Nhập tên sinh viên hoặc công nghệ..."></label>
      <label>Lọc theo trạng thái<select data-faculty-status><option value="all" ${facultyStatus === 'all' ? 'selected' : ''}>Tất cả trạng thái</option>
        ${[['pending','Chờ phản hồi'],['accepted','Đã nhận'],['rejected','Đã từ chối']].map(([value,label]) => `<option value="${value}" ${facultyStatus === value ? 'selected' : ''}>${label}</option>`).join('')}
      </select></label>
    </div>
    <p class="help" data-faculty-count>${filtered.length} / ${requests.length} nguyện vọng</p>
    <div data-faculty-list>${facultyApplicantRows(filtered)}</div>
    <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--line)">
      <div class="section-heading">
        <div>
          <h2>Nhóm sinh viên được phân công hướng dẫn chính thức (Kỳ ${esc(state.semester)})</h2>
          <p>${state.published ? 'Theo dõi liên hệ, duyệt 3 mốc tiến độ khóa luận và ghi nhận đánh giá cuối kỳ (tín hiệu R4 Continual RL).' : 'Danh sách sinh viên được phân công chính thức sẽ hiển thị tại đây ngay khi Trưởng khoa công bố phương án của kỳ học.'}</p>
        </div>
        ${state.published ? `<div class="export-actions">
          <a class="button secondary" href="/api/thesis/export" download>Xuất danh sách nhóm CSV</a>
          <a class="button primary" href="/api/thesis/export.xlsx" download>Xuất biểu mẫu Excel (.xlsx)</a>
        </div>` : ''}
      </div>
      ${state.published ? facultyAssignedWorkspace(state.assignments || []) : `<p class="empty-state">${accepted ? `Bạn đã chủ động nhận ${accepted} sinh viên — các chỗ này được giữ cố định khi Trưởng khoa chạy phân công và công bố.` : 'Kỳ học hiện chưa công bố danh sách phân công chính thức.'}</p>`}
    </div>
  </section>
  ${state.published ? `<section class="work-section"><h2>Danh sách liên hệ sinh viên đã từng đăng ký nguyện vọng</h2>
    ${contactTable(state.registered_students || [], 'Chưa có sinh viên đăng ký bạn hướng dẫn trong kỳ này.')}
    </section>` : ''}`;
}

function facultyApplicantRows(rows) {
  return rows.length ? rows.map(r => {
    const d = r.dossier;
    return `<article class="thesis-applicant">
      <div class="applicant-header">
        <div>
          <h3>${esc(r.name)}${r.student_id ? ` · <small style="display:inline">${esc(r.student_id)}</small>` : ''}</h3>
          <p class="help" style="margin:2px 0 0">${r.rank ? `Nguyện vọng ưu tiên ${r.rank} · ` : ''}${statusNames[r.status]}</p>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          ${typeof r.compatibility_score === 'number' ? `<span class="score-pill">Tương thích E4: ${percent(r.compatibility_score)}</span>` : ''}
          <span class="thesis-confidence ${r.status === 'accepted' ? 'thesis-confidence-high' : r.status === 'pending' ? 'thesis-confidence-review' : 'thesis-confidence-low'}">${statusNames[r.status]}</span>
        </div>
      </div>
      ${skillList((r.skills || []).filter(s => s.status !== 'unassessed'))}
      ${r.status !== 'rejected' ? (d ? `<div class="dossier-box standardized" style="margin-top:12px">
        <div class="dossier-box-header">
          <strong>Hồ sơ Đề tài Học thuật Chuẩn hóa</strong>
          <span class="dossier-badge">✓ Đã chuẩn hóa giọng văn</span>
        </div>
        <h4 style="margin:4px 0 6px">${esc(d.formal_title)}</h4>
        <p style="color:var(--ink);margin:0 0 6px">${esc(d.formal_summary)}</p>
        <p class="help" style="margin:0"><strong>Công nghệ &amp; phạm vi:</strong> ${esc(d.methodology_scope)}</p>
        ${(d.normalized_skills || []).length ? `<div class="skill-chip-group">${d.normalized_skills.slice(0, 8).map(s => `<span class="skill-chip">${esc(s.label)}</span>`).join('')}</div>` : ''}
      </div>` : `<div style="margin-top:10px"><h4 style="margin:0 0 4px">Đề tài dự kiến</h4><p class="topic-description" style="margin:0">${r.topic_description ? esc(r.topic_description) : 'Sinh viên chưa bổ sung mô tả đề tài.'}</p></div>`) : ''}
      ${r.status === 'pending' && !state.published ? `<form data-action="decision" data-student="${esc(r.user_id)}" data-student-name="${esc(r.name)}" class="thesis-actions" style="margin-top:14px">
        <button class="primary" value="accepted">✓ Nhận hướng dẫn</button>
        <button class="danger-outline" value="rejected">Từ chối</button>
      </form>` : ''}
    </article>`;
  }).join('') : '<p class="empty-state">Không có nguyện vọng nào khớp bộ lọc hiện tại.</p>';
}

function facultyAssignedWorkspace(assignments) {
  if (!assignments.length) return '<p class="empty-state">Chưa có sinh viên được phân công chính thức cho bạn.</p>';
  return assignments.map(student => {
    const milestones = student.milestones || [];
    const outcome = student.outcome;
    return `<article class="thesis-applicant" style="background:var(--white)">
      <div class="applicant-header">
        <div>
          <h3>${esc(student.student_name)}${student.student_id ? ` · ${esc(student.student_id)}` : ''}</h3>
          <p class="help" style="margin:2px 0 0">Email: ${esc(student.email || 'Chưa cung cấp')} · SĐT: ${esc(student.phone || 'Chưa cung cấp')}</p>
        </div>
        ${outcome ? `<span class="thesis-confidence thesis-confidence-high">${esc(outcomeNames[outcome.rating] || outcome.rating)}</span>` : ''}
      </div>
      ${student.dossier?.formal_title ? `<p style="color:var(--ink);margin:6px 0"><strong>Đề tài chuẩn hóa:</strong> ${esc(student.dossier.formal_title)}</p>` : ''}
      ${milestones.length ? `<details class="xai-details-panel" ${milestones.some(m => m.status === 'submitted') ? 'open' : ''}>
        <summary>Tiến độ 3 mốc khóa luận (${milestones.filter(m => m.status === 'approved').length}/3 đã duyệt)</summary>
        <div class="milestone-timeline">
          ${milestones.map(m => `<div class="milestone-card" data-status="${esc(m.status)}">
            <strong>${esc(m.label)}</strong>
            <span class="help">Trạng thái: <b>${esc(milestoneStatusNames[m.status] || m.status)}</b></span>
            ${m.official_title ? `<p style="margin:0;font-size:.86rem"><strong>Tên đề tài:</strong> ${esc(m.official_title)}</p>` : ''}
            ${m.submission_url ? `<a href="${esc(m.submission_url)}" target="_blank" rel="noopener">Mở tài liệu / mã nguồn đã nộp ↗</a>` : ''}
            ${m.submission_note ? `<p style="margin:0;font-size:.86rem;color:var(--ink)">${esc(m.submission_note)}</p>` : '<p class="help" style="margin:0">Sinh viên chưa gửi nội dung mốc này.</p>'}
            ${m.status !== 'pending' ? `<form data-action="milestone-review" style="display:grid;gap:8px">
              <input type="hidden" name="user_id" value="${esc(student.user_id)}">
              <input type="hidden" name="milestone_key" value="${esc(m.key)}">
              <input name="advisor_feedback" maxlength="1000" value="${esc(m.advisor_feedback || '')}" placeholder="Nhận xét góp ý cho sinh viên...">
              <div class="quick-pref-btns">
                <button class="primary" value="approved">✓ Duyệt mốc</button>
                <button class="secondary" value="revision_requested">Yêu cầu chỉnh sửa</button>
              </div>
            </form>` : ''}
          </div>`).join('')}
        </div>
      </details>` : ''}
      <details class="xai-details-panel">
        <summary>Đánh giá tổng kết hướng dẫn cuối kỳ (Phản hồi R4 Continual RL)</summary>
        <form data-action="outcome" style="display:grid;gap:10px;margin-top:10px">
          <input type="hidden" name="user_id" value="${esc(student.user_id)}">
          <div class="profile-fields" style="margin-bottom:0">
            <label>Mức độ hoàn thành khóa luận
              <select name="rating" required>
                <option value="excellent" ${outcome?.rating === 'excellent' ? 'selected' : ''}>Hoàn thành xuất sắc</option>
                <option value="satisfactory" ${!outcome || outcome?.rating === 'satisfactory' ? 'selected' : ''}>Hoàn thành đạt yêu cầu</option>
                <option value="needs_improvement" ${outcome?.rating === 'needs_improvement' ? 'selected' : ''}>Cần cải thiện thêm</option>
              </select>
            </label>
            <label>Kỹ năng thực tế đã vận dụng (phân cách bằng dấu ;)
              <input name="skills_applied" maxlength="500" value="${esc(outcome?.skills_applied || '')}" placeholder="VD: Python; FastAPI; Machine Learning">
            </label>
          </div>
          <label>Nhận xét tổng kết cuối kỳ
            <input name="summary_note" maxlength="1000" value="${esc(outcome?.summary_note || '')}" placeholder="Nhận xét chất lượng đề tài và thái độ làm việc...">
          </label>
          <div><button class="secondary">Lưu đánh giá cuối kỳ</button></div>
        </form>
      </details>
    </article>`;
  }).join('');
}

function contactTable(rows, empty) {
  return rows.length ? `<div class="table-scroll" tabindex="0" role="region" aria-label="Thông tin liên hệ sinh viên">
    <table><thead><tr><th scope="col">Họ tên</th><th scope="col">Email</th><th scope="col">Số điện thoại</th></tr></thead>
    <tbody>${rows.map(row => `<tr><th scope="row">${esc(row.name)}</th>
      <td>${esc(row.email || 'Chưa cung cấp')}</td><td>${esc(row.phone || 'Chưa cung cấp')}</td></tr>`).join('')}
    </tbody></table></div>` : `<p class="empty-state">${empty}</p>`;
}

let manualDirty = false;
let manualDraft = null;
let history = {items: [], next_before: null}, historyError = '';

function manualChoices(form) {
  return Object.fromEntries([...form.querySelectorAll('select')].filter(input => input.value).map(input => [input.name, input.value]));
}

function rememberManualDraft() {
  const form = content.querySelector('[data-action="manual"]');
  if (!form) return;
  manualDraft = {id: manualDraft ? manualDraft.id : state.manual?.id ?? null,
    assignments: manualChoices(form),
    reason: form.querySelector('textarea[name="reason"]').value};
  manualDirty = true;
  const publish = content.querySelector('[data-action="publish-manual"] button');
  if (publish) publish.disabled = true;
  updateManualReview();
}

function exceptionSummary(exceptions) {
  const changed = exceptions?.changed_accepted ?? [];
  const overloaded = exceptions?.over_quota ?? [];
  if (!changed.length && !overloaded.length) return '<p class="status-good">✓ Không có ngoại lệ so với cặp đã nhận và chỉ tiêu tham chiếu.</p>';
  return `<p class="status-warn"><strong>Cần ghi rõ lý do ngoại lệ trước khi công bố:</strong></p><ul>
    ${changed.map(row => `<li>${esc(row.student_id)}: đổi cặp đã nhận từ ${esc(advisorName(row.previous_advisor_id))} sang ${esc(advisorName(row.advisor_id))}.</li>`).join('')}
    ${overloaded.map(row => `<li>${esc(advisorName(row.advisor_id))}: ${row.assigned}/${row.total} sinh viên, vượt ${row.assigned - row.total} suất.</li>`).join('')}
  </ul>`;
}

function updateManualReview() {
  const root = $('manual-review');
  if (!root) return;
  const assignments = manualDraft?.assignments ?? Object.fromEntries((state.manual?.assignments ?? []).map(row => [row.student_id, row.advisor_id]));
  const quotas = state.manual_quotas ?? [];
  const loads = {};
  Object.values(assignments).forEach(id => { loads[id] = (loads[id] ?? 0) + 1; });
  const exceptions = {
    changed_accepted: (state.roster_preview || []).flatMap(row => {
      const previous = state.accepted_assignments?.[row.user_id];
      const next = assignments[row.student_id];
      return previous && next && previous !== next
        ? [{student_id: row.student_id, previous_advisor_id: previous, advisor_id: next}] : [];
    }),
    over_quota: quotas.filter(q => (loads[q.advisor_id] ?? 0) > q.total).map(q => ({...q, assigned: loads[q.advisor_id]})),
  };
  root.innerHTML = `<p>${manualDirty ? '<strong>Đang có thay đổi chưa lưu.</strong>' : 'Đang xem bản nháp đã lưu.'} Chỉ tiêu tham chiếu tính theo danh sách giảng viên của phương án tự động gần nhất.</p>
    ${exceptionSummary(exceptions)}<p class="help">${quotas.filter(q => q.total || loads[q.advisor_id]).map(q => `${esc(advisorName(q.advisor_id))}: ${loads[q.advisor_id] ?? 0}/${q.total}`).join(' · ')}</p>
    ${manualDirty ? '<button type="button" class="secondary" data-discard-manual>Hủy thay đổi chưa lưu</button>' : ''}`;
}

function historyRows(items) {
  const actions = {manual_save: 'Lưu bản thủ công', publish: 'Công bố chính thức', revoke: 'Thu hồi công bố'};
  return items.map(event => `<article class="thesis-applicant" data-history-event="${event.revision}">
    <div class="applicant-header">
      <h3>${esc(actions[event.action])} · Phiên bản #${event.revision}</h3>
      <span class="agent-tag">${esc(event.algorithm.toUpperCase())}</span>
    </div>
    <p class="help">${esc(event.actor_name)} · ${esc(new Date(event.created_at).toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh'}))}</p>
    <p>Ghi chú / Lý do: ${esc(event.reason || 'Không có ngoại lệ được ghi nhận.')}</p>
    <button type="button" class="secondary" data-history-detail="${event.revision}">Xem chi tiết snapshot đã lưu</button>
    <div data-history-snapshot="${event.revision}"></div>
  </article>`).join('');
}

function publicationHistory() {
  return `<section class="work-section" aria-labelledby="publication-history-title">
    <h2 id="publication-history-title">Nhật ký Phiên bản &amp; Lịch sử Công bố</h2>
    <p>Lưu bất biến người thực hiện, thời điểm, thuật toán và toàn bộ phương án tại mỗi lần lưu thủ công, công bố hoặc thu hồi.</p>
    <p data-history-status role="status" class="help">${esc(historyError)}</p>
    <div data-history-list>${historyRows(history.items) || '<p class="empty-state">Chưa có bản ghi lịch sử trong kỳ này.</p>'}</div>
    <button type="button" class="secondary" data-history-more ${history.next_before ? '' : 'hidden'}>Xem các phiên bản trước</button>
  </section>`;
}

function manualAllocation() {
  if (!state.roster_loaded || (state.published && state.published_algorithm !== 'manual')) return '';
  const manual = state.manual;
  const rows = manual?.assignments ?? [];
  const assigned = new Map(manualDraft ? Object.entries(manualDraft.assignments) : rows.map(row => [row.student_id, row.advisor_id]));
  const table = body => `<div class="table-scroll" tabindex="0" role="region" aria-label="Danh sách phân công thủ công">
    <table><thead><tr><th scope="col">Sinh viên</th><th scope="col">Giảng viên hướng dẫn chỉ định</th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
  return `<section class="work-section" aria-labelledby="manual-allocation-title">
    <h2 id="manual-allocation-title">Điều chỉnh &amp; Phân công Thủ công</h2>
    ${state.published ? table(rows.map(row => `<tr><th scope="row">${esc(row.student_name)} · ${esc(row.student_id)}</th><td>${esc(row.advisor_name)}</td></tr>`).join('')) :
      `<p>Cho phép điều chỉnh trực tiếp từng cặp sinh viên – giảng viên. Nếu vượt chỉ tiêu hoặc thay đổi cặp đã nhận trước, hệ thống yêu cầu ghi rõ lý do giải trình.</p>
      <p class="help">Đã gán ${rows.length}/${state.student_count} sinh viên.</p>
      <div id="manual-review" class="xai-details-panel" role="status"></div>
      ${catalog.length ? `<form data-action="manual">
        <div class="quick-pref-btns" style="margin-bottom:10px">
          ${Object.entries(state.proposal?.results ?? {}).filter(([, run]) => run.status === 'feasible')
            .map(([name]) => `<button type="button" class="secondary" data-copy-allocation="${esc(name)}">Sao chép từ ${esc(name.toUpperCase())}</button>`).join(' ')}
        </div>
        ${table((state.roster_preview || []).map(row => `<tr><th scope="row">${esc(row.name)} · ${esc(row.student_id)}</th><td>
          <select name="${esc(row.student_id)}" aria-label="Giảng viên hướng dẫn cho ${esc(row.name)} · ${esc(row.student_id)}">
            <option value="">Chưa phân công</option>
            ${catalog.map(a => `<option value="${esc(a.advisor_id)}"${assigned.get(row.student_id) === a.advisor_id ? ' selected' : ''}>${esc(a.advisor_name)}</option>`).join('')}
          </select></td></tr>`).join(''))}
        <label class="topic-field" style="margin-top:14px">Lý do điều chỉnh hoặc giải trình ngoại lệ
          <textarea name="reason" rows="3" maxlength="2000" placeholder="Nêu rõ căn cứ học vụ khi đổi cặp đã nhận hoặc vượt chỉ tiêu...">${esc(manualDraft?.reason ?? manual?.reason ?? '')}</textarea>
        </label>
        <div class="thesis-actions" style="margin-top:12px">
          <button class="secondary">Lưu bản nháp thủ công</button>
        </div>
      </form>` : '<p>Danh mục giảng viên chưa tải được.</p>'}
      ${state.preferences_closed && manual && rows.length === state.student_count ? `<form data-action="publish-manual" class="thesis-actions thesis-publish">
        <label class="confirmation"><input type="checkbox" required> Tôi xác nhận đã rà soát toàn bộ phương án phân công thủ công.</label>
        <button class="primary" ${manualDirty ? 'disabled' : ''}>Công bố bản thủ công</button>
      </form>` : ''}`}
  </section>`;
}

function deanRosterRows() {
  return (state.roster_preview || []).filter(row => (rosterStatus === 'all'
    || rosterStatus === 'incomplete' && row.incomplete_reasons.length || rosterStatus === 'submitted' && !row.incomplete_reasons.length)
    && `${row.student_id} ${row.name}`.toLocaleLowerCase('vi').includes(rosterSearch.toLocaleLowerCase('vi')));
}

function updateDeanRoster() {
  const rows = deanRosterRows();
  const target = content.querySelector('[data-roster-preview]');
  if (!target) return;
  target.innerHTML = rows.map(row => `<tr><th scope="row">${esc(row.student_id)}</th><td>${esc(row.name)}</td>
    <td>${row.normalized ? '<span class="dossier-badge">✓ Đã chuẩn hóa</span> · ' : ''}${esc(row.incomplete_reasons.join(' · ') || 'Đã hoàn tất đầy đủ')}</td></tr>`).join('');
  const count = content.querySelector('[data-roster-count]');
  if (count) count.textContent = `${rows.length} / ${state.roster_preview.length} sinh viên`;
}

function deanAdvisorSkillsSection() {
  const items = state.advisor_skills || catalog || [];
  if (!items.length) return '';
  const readyCount = items.filter(a => a.fairness_ready !== false && (a.skill_count ?? (a.display_skills || []).length) >= 3).length;
  return `<section class="work-section">
    <div class="section-heading">
      <div>
        <h2>Danh sách Giảng viên Khoa &amp; Ma trận Kỹ năng (${readyCount}/${items.length} đủ nhãn công bằng)</h2>
        <p>Theo dõi toàn bộ giảng viên hướng dẫn trong khoa, số nguyện vọng sinh viên đăng ký và ma trận kỹ năng phục vụ tính điểm tương thích E4.</p>
      </div>
      <a class="button secondary" href="/api/thesis/advisor-skills.csv" download>⬇ Tải CSV Kỹ năng GV đầy đủ</a>
    </div>
    <details class="xai-details-panel" open>
      <summary>Bảng tổng hợp ${items.length} giảng viên hướng dẫn &amp; cập nhật CSV kỹ năng</summary>
      <div class="table-scroll">
        <table>
          <thead><tr><th scope="col">Giảng viên</th><th scope="col">Tóm tắt chuyên môn</th><th scope="col">Các nhãn kỹ năng chuẩn hóa</th><th scope="col">Nguyện vọng SV</th><th scope="col">Số nhãn</th></tr></thead>
          <tbody>${items.map(a => `<tr>
            <th scope="row">${esc(a.advisor_name)}<small>${esc(a.academic_title || '')}${a.academic_title ? ' · ' : ''}${esc(a.advisor_id)}</small></th>
            <td>${esc(a.summary || '—')}</td>
            <td><div class="skill-chip-group" style="margin:0">${(a.display_skills || []).slice(0, 8).map(s => `<span class="skill-chip">${esc(s)}</span>`).join('')}</div></td>
            <td><strong>${a.accepted_count ?? 0}</strong> nhận · <strong>${a.pending_count ?? 0}</strong> chờ</td>
            <td><strong>${a.skill_count ?? (a.display_skills || []).length}</strong></td>
          </tr>`).join('')}</tbody>
        </table>
      </div>
      ${!state.published ? `<form data-action="advisor-skills" class="thesis-actions" style="margin-top:14px">
        <label for="advisor-skills-file">Cập nhật tệp CSV Kỹ năng Giảng viên (UTF-8)</label>
        <input id="advisor-skills-file" type="file" name="skills_csv_file" accept=".csv,text/csv" required>
        <button class="secondary">Lưu cập nhật Kỹ năng Giảng viên</button>
      </form>` : ''}
    </details>
  </section>`;
}

function deanView() {
  const proposal = state.proposal;
  const algNames = { ppo: 'PPO (Reinforcement Learning)', dqn: 'DQN (Deep Q-Network)', hungarian: 'Hungarian (Tối ưu toàn cục)', manual: 'Thủ công' };
  return `<div class="kpi-grid">
    <div class="kpi-card"><span>Sinh viên trong kỳ</span><strong>${state.roster_loaded ? state.student_count : state.student_count || 0}</strong><small>${state.roster_loaded ? 'Từ danh sách CSV chính thức' : 'Ghi danh trực tuyến'}</small></div>
    <div class="kpi-card"><span>Đã làm khảo sát</span><strong>${state.submitted_count ?? 0}</strong><small>Có hồ sơ đánh giá kỹ năng</small></div>
    <div class="kpi-card"><span>Đã chuẩn hóa đề tài</span><strong>${state.normalized_count ?? 0}</strong><small>Hồ sơ học thuật chuẩn</small></div>
    <div class="kpi-card"><span>Nguyện vọng chờ GV</span><strong>${state.pending_count ?? 0}</strong><small>${state.preferences_closed ? 'Đã khóa đăng ký' : 'Đang mở đăng ký'}</small></div>
  </div>
  <div class="dean-layout"><div class="dean-main">
  <section class="work-section"><h2>1. Danh sách sinh viên khóa luận của kỳ</h2>
    <p><strong>${state.roster_loaded ? state.student_count : 0}</strong> sinh viên trong CSV ·
      <strong>${state.roster_loaded ? state.submitted_count : 0}</strong> đã hoàn thành khảo sát kỹ năng trực tuyến.</p>
    ${state.roster_loaded ? `<details class="xai-details-panel"><summary>Rà soát tiến độ hoàn thiện hồ sơ của từng sinh viên</summary>
      <div class="profile-fields" style="margin-top:12px">
        <label>Tìm mã sinh viên hoặc họ tên<input type="search" data-roster-search value="${esc(rosterSearch)}"></label>
        <label>Trạng thái hồ sơ<select data-roster-status><option value="all" ${rosterStatus === 'all' ? 'selected' : ''}>Tất cả</option>
          <option value="incomplete" ${rosterStatus === 'incomplete' ? 'selected' : ''}>Chưa hoàn tất</option>
          <option value="submitted" ${rosterStatus === 'submitted' ? 'selected' : ''}>Đã hoàn tất</option>
        </select></label>
      </div><p class="help" data-roster-count></p><div class="table-scroll" tabindex="0" role="region" aria-label="Danh sách sinh viên đã nhập">
      <table><thead><tr><th scope="col">Mã sinh viên</th><th scope="col">Họ tên</th><th scope="col">Trạng thái hồ sơ trực tuyến</th></tr></thead>
      <tbody data-roster-preview>${deanRosterRows().map(row => `<tr><th scope="row">${esc(row.student_id)}</th><td>${esc(row.name)}</td>
        <td>${row.normalized ? '<span class="dossier-badge">✓ Đã chuẩn hóa</span> · ' : ''}${esc(row.incomplete_reasons.join(' · ') || 'Đã hoàn tất đầy đủ')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
    ${state.published ? '' : `<form data-action="roster" class="thesis-actions">
      <label for="thesis-roster-file">${state.roster_loaded ? 'Thay thế danh sách CSV học kỳ' : 'Tải lên danh sách CSV học kỳ'}</label>
      <input id="thesis-roster-file" type="file" name="csv_file" accept=".csv,text/csv" required>
      ${state.roster_loaded ? '<label class="confirmation"><input type="checkbox" required> Tôi xác nhận thay toàn bộ danh sách sinh viên hiện tại bằng tệp mới.</label>' : ''}
      <button class="primary">Lưu danh sách kỳ học</button>
    </form>
    <p class="help">Cột bắt buộc: <code>student_id, name, email</code>. Tùy chọn: <code>phone, topic, skills, enrollment_code</code>.
      <a href="data:text/csv;charset=utf-8,student_id%2Cname%2Cemail%2Cphone%2Ctopic%2Cskills%0A" download="unimatch-danh-sach-mau.csv">Tải CSV mẫu</a></p>`}
  </section>

  ${deanAdvisorSkillsSection()}

  <section class="work-section"><h2>2. Khóa nguyện vọng, Chọn giảng viên &amp; Chạy tối ưu</h2>
    <p>${state.preferences_closed ? '🔒 Đã khóa nộp nguyện vọng từ phía sinh viên.' : '🔓 Đang mở cho sinh viên nộp nguyện vọng.'}
      Hiện còn <strong>${state.pending_count}</strong> nguyện vọng đang chờ giảng viên phản hồi.</p>
    ${!state.published && state.roster_loaded ? `<form data-action="${state.preferences_closed ? 'reopen' : 'close'}">
      <button class="secondary">${state.preferences_closed ? 'Mở lại đăng ký nguyện vọng' : 'Khóa đăng ký nguyện vọng để chốt chỉ tiêu'}</button></form>` : ''}
    ${catalogError ? `<p class="status-error">${esc(catalogError)}</p>` : ''}
    ${!state.published && catalog.length ? `<form data-action="proposal">
      <fieldset><legend>Chọn giảng viên tham gia hướng dẫn học kỳ</legend>
      <div class="quick-pref-btns" style="margin-bottom:10px">
        <button type="button" class="secondary" data-dean-select-all>Chọn toàn bộ (${catalog.length})</button>
      </div>
      <div class="thesis-roster">
      ${catalog.map(a => {
        const required = (state.accepted_advisors || []).includes(a.advisor_id);
        return `<label class="advisor-option"><input type="checkbox" name="advisor_id" value="${esc(a.advisor_id)}" ${required || selected.has(a.advisor_id) ? 'checked' : ''} ${required ? 'disabled' : ''}>
        <span><b>${esc(a.advisor_name)}</b><small data-quota="${esc(a.advisor_id)}"></small></span></label>`;
      }).join('')}
      </div></fieldset><p class="help">${!state.roster_loaded && !state.student_count ? 'Hãy tải lên danh sách CSV sinh viên ở Mục 1 và Khóa đăng ký nguyện vọng để mở nút chạy phân công.' : 'Chỉ tiêu tự động = số sinh viên giảng viên đã chủ động nhận + phần chia cân bằng từ số sinh viên còn lại.'}</p>
      <button class="primary" ${(!state.roster_loaded && !state.student_count) || (state.roster_loaded && !state.preferences_closed) ? 'disabled' : ''}>Chốt chỉ tiêu &amp; Chạy đối chiếu mô hình (Hungarian · PPO · DQN)</button>
    </form>` : ''}
  </section>

  ${manualAllocation()}

  ${proposal?.results ? `<section class="work-section" aria-labelledby="semester-replay-title">
    <h2 id="semester-replay-title">Mô phỏng quá trình phân công (3D Khuôn viên &amp; 2D Ràng buộc)</h2>
    <div id="semester-replay"></div></section>` : ''}

  <section class="work-section">
    <div class="section-heading">
      <div>
        <h2>${state.published ? '3. Kết quả Phân công Chính thức Đã Công bố' : '3. Đối chiếu Phương án &amp; Công bố'}</h2>
        ${state.published_algorithm ? `<p>Phương án đang áp dụng: <strong>${esc(algNames[state.published_algorithm] || state.published_algorithm.toUpperCase())}</strong></p>` : ''}
      </div>
      ${state.published ? `<div class="export-actions">
        <a class="button secondary" href="/api/thesis/export" download>Xuất danh sách chính thức CSV</a>
        <a class="button primary" href="/api/thesis/export.xlsx" download>Xuất biểu mẫu Excel (.xlsx)</a>
        <a class="button secondary" href="/api/thesis/rl-export" download title="Xuất gói dữ liệu R2/R3/R4 ẩn danh cho vòng huấn luyện Continual RL kế tiếp">Xuất gói Continual RL (.json)</a>
      </div>` : ''}
    </div>
    ${proposal?.results ? comparison(proposal) : proposal ? tables(proposal) : '<p class="empty-state">Kết quả đối chiếu chi tiết giữa Hungarian, PPO và DQN sẽ hiển thị sau khi chạy phân công.</p>'}
    ${proposal?.results && proposal.status === 'feasible' && !state.published ? `<form data-action="publish" class="thesis-actions thesis-publish">
      <label>Chọn phương án công bố chính thức
        <select name="algorithm" required>
          <option value="">— Chọn thuật toán công bố —</option>
          ${Object.keys(proposal.results).map(alg => `<option value="${esc(alg)}">${esc(algNames[alg] || alg.toUpperCase())}</option>`).join('')}
        </select>
      </label>
      <label class="confirmation"><input type="checkbox" required> Tôi xác nhận đã rà soát chỉ tiêu, điểm tương thích và đồng ý công bố tới sinh viên &amp; giảng viên.</label>
      <button class="primary">Công bố kết quả phân công</button>
    </form>` : !proposal?.results && proposal?.status === 'feasible' && !state.published ? `<form data-action="publish" class="thesis-actions thesis-publish">
      <label class="confirmation"><input type="checkbox" required> Tôi đã rà soát phương án và đồng ý công bố chính thức.</label>
      <button class="primary">Công bố kết quả phân công</button>
    </form>` : ''}
    ${state.published ? `<form data-action="revoke" class="thesis-actions thesis-publish">
      <label class="confirmation"><input type="checkbox" required> Tạm ẩn kết quả đang công bố để điều chỉnh lại phương án.</label>
      <button class="danger-outline">Thu hồi công bố</button>
    </form>` : ''}
  </section>

  ${publicationHistory()}

  <section class="work-section" aria-labelledby="recovery-code-title">
    <h2 id="recovery-code-title">Cấp mã khôi phục mật khẩu tài khoản học vụ</h2>
    <p>Tạo mã khôi phục dùng một lần (hiệu lực 30 phút) cho sinh viên hoặc giảng viên đã xác minh danh tính.</p>
    <form data-action="recovery-code" class="thesis-actions">
      <label>Email tài khoản cần cấp lại<input name="email" type="email" autocomplete="off" maxlength="254" required placeholder="sinhvien@student.edu.vn"></label>
      <button class="secondary">Cấp mã khôi phục</button>
    </form>
    ${recoveryCodeInfo ? `<p class="status-banner" role="status">Mã một lần cho <strong>${esc(recoveryCodeInfo.email)}</strong>: <code>${esc(recoveryCodeInfo.code)}</code>
      <button type="button" class="secondary" data-copy-recovery style="margin-left:10px;min-height:32px;padding:4px 10px">Sao chép mã</button></p>` : ''}
  </section></div>

  <aside class="work-section dean-threshold" aria-labelledby="threshold-title">
    <h2 id="threshold-title">Ngưỡng tin tưởng E4</h2>
    <strong class="threshold-value">${state.threshold}%</strong>
    <p class="help">Đối chiếu điểm tương thích đặc trưng E4. Đây là độ tương đồng ngữ nghĩa &amp; kỹ năng, không phải xác suất thành công tuyệt đối.</p>
    ${state.published ? '' : `<form data-action="threshold">
      <label for="confidence-threshold">Ngưỡng đánh dấu (%)</label>
      <input type="number" id="confidence-threshold" name="threshold" min="0" max="100" step="1" required value="${state.threshold}">
      <button class="secondary">Lưu ngưỡng</button>
    </form>`}
    <ul class="confidence-key">
      <li><span class="thesis-confidence thesis-confidence-high">Đạt ngưỡng cao</span> Các mô hình đồng thuận vượt ngưỡng</li>
      <li><span class="thesis-confidence thesis-confidence-review">Cần rà soát</span> Đạt ngưỡng một phần hoặc dưới ngưỡng</li>
      <li><span class="thesis-confidence thesis-confidence-low">Thiếu đặc trưng</span> Chưa đủ dữ liệu tính điểm</li>
    </ul>
  </aside></div>`;
}

function updatePreviewQuotas() {
  const controls = [...content.querySelectorAll('[data-action="proposal"] input[name="advisor_id"]:checked')];
  const ids = controls.map(input => input.value).sort();
  const counts = state.accepted_counts || {};
  const remaining = Math.max(0, (state.student_count || 0) - Object.values(counts).reduce((sum, count) => sum + count, 0));
  const shares = new Map(ids.map((id, index) => [id, Math.floor(remaining / Math.max(1, ids.length)) + Number(index < remaining % Math.max(1, ids.length))]));
  for (const label of content.querySelectorAll('[data-quota]')) {
    const id = label.dataset.quota;
    const accepted = counts[id] ?? 0;
    const share = shares.get(id);
    label.textContent = share === undefined ? '' : `Đã nhận ${accepted} · Chia thêm ${share} · Chỉ tiêu ${accepted + share}`;
  }
  const run = content.querySelector('[data-action="proposal"] button[type="submit"], [data-action="proposal"] > button.primary');
  if (run) run.disabled = (!state.roster_loaded && !state.student_count) || (state.roster_loaded && !state.preferences_closed) || !ids.length;
  const publish = content.querySelector('[data-action="publish"] button');
  if (publish && state.proposal?.quotas) {
    const previous = state.proposal.quotas.map(q => q.advisor_id).sort();
    if (ids.length) publish.disabled = JSON.stringify(ids) !== JSON.stringify(previous);
  }
}

function renderDean() {
  stopReplay();
  content.innerHTML = deanView();
  updatePreviewQuotas();
  updateManualReview();
  updateDeanRoster();
  const player = $('semester-replay');
  if (!player || !state.proposal?.results) return;
  const {results, quotas} = state.proposal;
  const names = new Map(Object.values(results).flatMap(run => (run.assignments || []).map(row => [row.user_id, row.student_name])));
  const advisors = new Map((quotas || []).map(row => [row.advisor_id, row.advisor_name]));
  stopReplay = mountReplay(player, {runs: results, quotas, initial: state.published_algorithm || 'hungarian',
    studentName: id => names.get(id) ?? id, advisorName: id => advisors.get(id) ?? advisorName(id)});
}

function comparison(proposal) {
  const results = proposal.results || {};
  const modelKeys = Object.keys(results);
  const {ppo, dqn} = results;
  const hungarian = results.hungarian;
  if (proposal.status !== 'feasible') return '<p class="status-error">Không thể phân công đủ với danh sách và chỉ tiêu hiện tại. Hãy kiểm tra lại tập giảng viên tham gia.</p>';
  const byModelStudent = Object.fromEntries(modelKeys.map(k => [k, new Map((results[k].assignments || []).map(row => [row.user_id, row]))]));
  const byAdvisor = run => (run?.assignments || []).reduce((groups, row) => {
    if (!groups.has(row.advisor_id)) groups.set(row.advisor_id, []);
    groups.get(row.advisor_id).push(row);
    return groups;
  }, new Map());
  const groups = modelKeys.map(k => [k, byAdvisor(results[k])]);
  const score = value => value == null ? 'Chưa có điểm' : percent(value);
  const loadAndFit = rows => {
    const scores = rows.flatMap(row => row.score == null ? [] : [row.score]);
    return `<td><strong>${rows.length}</strong> SV<small>${score(scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null)}</small></td>`;
  };
  const baseRows = (hungarian || ppo).assignments || [];
  const sameRl = ppo && dqn ? ppo.assignments.filter(a => byModelStudent.dqn.get(a.user_id)?.advisor_id === a.advisor_id).length : 0;

  return `<p class="help">Checkpoint phục vụ: <strong>${esc(proposal.checkpoint || 'V3 Strict GitHub')}</strong> · PPO &amp; DQN đồng thuận giảng viên trên <strong>${sameRl}/${baseRows.length}</strong> sinh viên.</p>
    <div class="comparison-cards">
      ${modelKeys.map(k => {
        const r = results[k];
        return `<article class="comparison-model" data-model="${esc(k)}">
          <h3>${esc(k.toUpperCase())}</h3>
          <span class="metric">${score(r.metrics?.mean_compatibility)}</span>
          <p>Điểm tương thích E4 trung bình · ${r.metrics?.scored_students ?? 0} SV có điểm</p>
          <p class="status-good"><strong>Bao phủ ${percent(r.metrics?.coverage ?? 1)} · ${r.metrics?.constraint_violations ?? 0} vi phạm</strong></p>
        </article>`;
      }).join('')}
    </div>
    <div class="table-scroll" tabindex="0" role="region" aria-label="So sánh chỉ số mô hình"><table><caption>Tổng hợp chỉ số các thuật toán trên kỳ học</caption>
      <thead><tr><th scope="col">Thuật toán</th><th scope="col">Bao phủ</th><th scope="col">Điểm E4 trung bình</th>
        <th scope="col">SV có điểm</th><th scope="col">Vi phạm chỉ tiêu</th><th scope="col">Thời gian suy luận</th></tr></thead>
      <tbody>${modelKeys.map(name => {
        const run = results[name];
        return `<tr><th scope="row">${esc(name.toUpperCase())}</th>
        <td>${percent(run.metrics.coverage)}</td><td><strong>${score(run.metrics.mean_compatibility)}</strong></td><td>${run.metrics.scored_students}</td>
        <td>${run.metrics.constraint_violations}</td><td>${Number(run.elapsed_seconds).toFixed(3)} giây</td></tr>`;
      }).join('')}</tbody></table></div>

    <div class="table-scroll" tabindex="0" role="region" aria-label="Chuyên môn và chỉ tiêu"><table><caption>Phân bổ tải &amp; kỹ năng theo giảng viên</caption>
      <thead><tr><th scope="col">Giảng viên</th><th scope="col">Kỹ năng chuyên môn chuẩn hóa</th><th scope="col">Đã nhận</th>
        <th scope="col">Chỉ tiêu</th>${modelKeys.map(k => `<th scope="col">${esc(k.toUpperCase())} · Tải / E4</th>`).join('')}</tr></thead>
      <tbody>${proposal.quotas.map(q => `<tr><th scope="row">${esc(q.advisor_name)}</th><td>${esc((q.skills || []).slice(0, 6).join(', ') || 'Đầy đủ')}</td>
        <td>${q.accepted}</td><td><strong>${q.total}</strong></td>${groups.map(([, group]) => loadAndFit(group.get(q.advisor_id) ?? [])).join('')}</tr>`).join('')}</tbody></table></div>

    <div class="table-scroll" tabindex="0" role="region" aria-label="So sánh từng sinh viên"><table><caption>Đối chiếu phương án phân công từng sinh viên</caption>
      <thead><tr><th scope="col">Sinh viên &amp; Đề tài</th>${modelKeys.map(k => `<th scope="col">${esc(k.toUpperCase())}</th>`).join('')}<th scope="col">Đánh giá ngưỡng</th></tr></thead>
      <tbody>${baseRows.map(row => {
        const cells = modelKeys.map(k => byModelStudent[k].get(row.user_id));
        const hasAnyScore = cells.some(c => c?.score != null);
        const passCount = cells.filter(c => c?.score != null && c.score * 100 >= state.threshold - 1e-9).length;
        const tone = passCount === cells.length ? 'high' : hasAnyScore ? 'review' : 'low';
        const label = passCount === cells.length ? 'Đạt ngưỡng cao' : passCount > 0 ? `${passCount}/${cells.length} đạt ngưỡng` : hasAnyScore ? 'Dưới ngưỡng' : 'Thiếu đặc trưng';
        const uniqueAdvisors = new Set(cells.map(c => c?.advisor_id).filter(Boolean)).size;
        return `<tr>
          <th scope="row">${esc(row.student_name)}<small>${esc(row.student_id)} · ${row.accepted ? '✓ GV đã nhận trước' : row.submitted ? 'Đã nộp hồ sơ' : 'Từ CSV'}${row.formal_title ? ` · ${esc(row.formal_title.slice(0, 65))}` : ''}</small></th>
          ${cells.map(c => `<td><strong>${esc(c?.advisor_name ?? '—')}</strong><small>${score(c?.score)}</small></td>`).join('')}
          <td><span class="thesis-confidence thesis-confidence-${tone}">${esc(label)}</span>${uniqueAdvisors > 1 ? '<small>Khác giảng viên giữa các mô hình</small>' : '<small>✓ Đồng thuận giảng viên</small>'}</td>
        </tr>`;
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
    $('thesis-period').textContent = `${state.semester.startsWith('demo') ? 'Kỳ Demo Bảo vệ ' : 'Học kỳ '}${state.semester}${state.published ? ' · Đã công bố chính thức' : ' · Đang điều phối'}`;
    const load = [
      user.role === 'faculty' ? Promise.resolve([]) : api('/catalog'),
      user.role === 'student' && state.profile ? api('/recommendations') : Promise.resolve([]),
    ];
    const [advisors, recommended] = await Promise.allSettled(load);
    catalog = advisors.value ?? [];
    catalogError = advisors.reason?.message ?? '';
    rankings = recommended.value ?? [];
    rankingError = recommended.reason?.message ?? '';
    selected ??= new Set(state.proposal?.quotas?.map(q => q.advisor_id) ?? catalog.map(a => a.advisor_id));
    if (user.role === 'dean') {
      try { history = await api('/history'); historyError = ''; }
      catch (error) { historyError = error.message; }
    }
    if (user.role === 'dean') renderDean();
    else content.innerHTML = (user.role === 'student' ? studentView : facultyView)();
    const assessment = content.querySelector('[data-action="assessment"]');
    if (assessment) updateTracks(assessment);
    const fillBtn = $('fill-skill-question');
    if (fillBtn) fillBtn.hidden = !state.profile?.skills?.some(s => s.status !== 'unassessed');
  } finally {
    content.setAttribute('aria-busy', 'false');
  }
}

function showStatus(message, error = false, focus = false) {
  notice.textContent = message;
  notice.hidden = !message;
  notice.classList.toggle('status-error', error);
  if (focus && message && typeof notice.focus === 'function') {
    try { notice.focus({ preventScroll: true }); } catch { notice.focus(); }
  }
  if (message) pushToast(message, error);
}

function updateTracks(form) {
  const roles = new Set(new FormData(form).getAll('roles'));
  for (const fieldset of form.querySelectorAll('[data-track]')) {
    fieldset.hidden = fieldset.disabled = !roles.has(fieldset.dataset.track);
  }
  const counter = form.querySelector('[data-role-count]');
  if (counter) {
    counter.textContent = roles.size
      ? `Đã chọn ${roles.size} hướng chuyên môn · ${roles.size * 5} câu hỏi tình huống.` : 'Hãy chọn ít nhất 1 hướng chuyên môn để mở bộ câu hỏi.';
  }
  const submitBtn = form.querySelector('button[type="submit"], button.primary');
  if (submitBtn) submitBtn.disabled = !roles.size;
}

content.addEventListener('change', event => {
  const input = event.target;
  if (input.matches?.('[data-faculty-status]')) {
    facultyStatus = input.value;
    updateFacultyRequests();
  }
  if (input.matches?.('[data-roster-status]')) {
    rosterStatus = input.value;
    updateDeanRoster();
  }
  if (input.matches?.('[data-action="manual"] select')) {
    rememberManualDraft();
  }
  if (user?.role === 'student' && input.closest?.('form[data-action]')) studentDirty = true;
  if (input.name === 'roles') updateTracks(input.form);
  if (input.matches?.('[data-action="proposal"] input[name="advisor_id"]')) {
    if (input.checked) selected.add(input.value);
    else selected.delete(input.value);
    updatePreviewQuotas();
  }
});

content.addEventListener('input', event => {
  const target = event.target;
  if (user?.role === 'student' && target.closest?.('form[data-action]')) studentDirty = true;
  if (target.matches?.('[data-action="manual"] textarea')) rememberManualDraft();
  if (target.matches?.('[data-faculty-search]')) {
    facultySearch = target.value;
    updateFacultyRequests();
  }
  if (target.matches?.('[data-roster-search]')) {
    rosterSearch = target.value;
    updateDeanRoster();
  }
  if (target.matches?.('[data-advisor-dir-search]')) {
    advisorDirSearch = target.value;
    const grid = content.querySelector('[data-advisor-dir-grid]');
    if (grid) {
      const canChoose = Boolean(state.profile && state.in_roster && !state.published && !state.preferences_closed && !(state.requests || []).some(r => r.status === 'accepted'));
      const q = advisorDirSearch.trim().toLocaleLowerCase('vi');
      const filtered = catalog.filter(a => `${a.advisor_name} ${a.summary || ''} ${(a.display_skills || []).join(' ')}`.toLocaleLowerCase('vi').includes(q));
      grid.innerHTML = filtered.map(a => advisorCardHtml(a, canChoose)).join('') || '<p class="help">Không tìm thấy giảng viên khớp từ khóa.</p>';
    }
  }
});

content.addEventListener('click', async event => {
  if (event.target.closest?.('[data-fill-colloquial-sample]')) {
    const form = content.querySelector('form[data-action="normalize"]');
    if (form) {
      const det = form.closest('details');
      if (det) det.open = true;
      form.elements.raw_title.value = 'làm cái web bán sách online có con bot ai tư vấn rag';
      form.elements.raw_description.value = 'dạ thưa thầy cô em đang tính làm một cái web bán hàng sách trực tuyến bằng python fastapi với reactjs và lưu dữ liệu postgres, bên trong có tích hợp con bot tư vấn tự động kiểu rag để gợi ý sách cho khách mà em chưa rành phần triển khai docker lắm ạ';
      form.elements.raw_background.value = 'đã học python, sql cơ bản, từng làm web nhỏ với react';
      studentDirty = true;
      pushToast('Đã điền mẫu văn nói của sinh viên — bấm "Chuẩn hóa giọng văn" để xem kết quả!');
    }
    return;
  }
  const pickBtn = event.target.closest?.('[data-advisor-pick]');
  if (pickBtn) {
    const slot = Number(pickBtn.dataset.pickPref || 0);
    const aid = pickBtn.dataset.advisorPick;
    const selectEl = content.querySelector(`select[data-pref-slot="${slot}"]`);
    if (selectEl) {
      selectEl.value = aid;
      studentDirty = true;
      selectEl.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
      pushToast(`Đã điền ${advisorName(aid)} vào Nguyện vọng ưu tiên ${slot + 1}.`);
    }
    return;
  }
  if (event.target.closest?.('[data-dean-select-all]')) {
    catalog.forEach(a => selected.add(a.advisor_id));
    content.querySelectorAll('[data-action="proposal"] input[name="advisor_id"]').forEach(cb => { cb.checked = true; });
    updatePreviewQuotas();
    return;
  }
  if (event.target.closest?.('[data-copy-recovery]')) {
    try {
      await navigator.clipboard.writeText(recoveryCodeInfo.code);
      showStatus('Đã sao chép mã khôi phục. Hãy gửi qua kênh riêng.', false, true);
    } catch { showStatus('Trình duyệt không cho phép sao chép. Hãy chọn và sao chép mã.', true, true); }
    return;
  }
  if (event.target.closest?.('[data-discard-manual]')) {
    manualDraft = null;
    manualDirty = false;
    renderDean();
    return;
  }
  const historyButton = event.target.closest?.('[data-history-more], [data-history-detail]');
  if (historyButton) {
    historyButton.disabled = true;
    const status = content.querySelector('[data-history-status]');
    status.textContent = 'Đang tải lịch sử…';
    try {
      if (historyButton.hasAttribute('data-history-more')) {
        const page = await api('/history?before=' + history.next_before);
        history.items.push(...page.items);
        history.next_before = page.next_before;
        content.querySelector('[data-history-list]').insertAdjacentHTML('beforeend', historyRows(page.items));
        historyButton.hidden = !history.next_before;
      } else {
        const revision = historyButton.dataset.historyDetail;
        const entry = await api('/history/' + revision);
        content.querySelector(`[data-history-snapshot="${revision}"]`).innerHTML =
          `${exceptionSummary(entry.snapshot.exceptions)}<div class="table-scroll" tabindex="0" role="region" aria-label="Phương án lịch sử">
          <table><caption>Phương án phiên bản #${entry.revision} · ${esc(entry.proposal_id)}</caption>
          <thead><tr><th scope="col">Sinh viên</th><th scope="col">Giảng viên</th></tr></thead><tbody>
          ${entry.snapshot.assignments.map(row => `<tr><th scope="row">${esc(row.student_name)} · ${esc(row.student_id || '')}</th><td>${esc(row.advisor_name)}</td></tr>`).join('')}
          </tbody></table></div>`;
        historyButton.hidden = true;
      }
      status.textContent = '';
    } catch (error) { status.textContent = error.message; }
    finally { historyButton.disabled = false; }
    return;
  }
  const button = event.target.closest?.('[data-copy-allocation]');
  if (!button) return;
  const assignments = state.proposal.results[button.dataset.copyAllocation].assignments;
  const advisors = new Map(assignments.map(row => [row.student_id, row.advisor_id]));
  for (const select of button.form.querySelectorAll('select')) {
    select.value = advisors.get(select.name) ?? '';
  }
  rememberManualDraft();
});

addEventListener('beforeunload', event => {
  if (!manualDirty) return;
  event.preventDefault();
  event.returnValue = '';
});

content.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const action = form.dataset.action;
  if (manualDirty && ['roster', 'publish', 'publish-manual', 'revoke'].includes(action)) {
    showStatus('Bạn có phân công thủ công chưa lưu. Hãy lưu hoặc bỏ thay đổi trước khi tiếp tục.', true, true);
    return;
  }
  const submitterValue = event.submitter?.value;
  if (action === 'decision') {
    const sName = form.dataset.studentName || 'sinh viên này';
    const isAccept = submitterValue === 'accepted';
    const ok = await confirmDialog(
      isAccept ? 'Xác nhận Nhận hướng dẫn' : 'Xác nhận Từ chối nguyện vọng',
      isAccept
        ? `Bạn đồng ý nhận hướng dẫn ${sName}? Chỗ hướng dẫn này sẽ được giữ cố định và các nguyện vọng chờ khác của sinh viên sẽ tự động rút.`
        : `Bạn chắc chắn muốn từ chối nguyện vọng của ${sName}? Quyết định này không thể hoàn tác trong kỳ.`,
      isAccept ? 'Đồng ý nhận hướng dẫn' : 'Xác nhận từ chối',
    );
    if (!ok) return;
  }
  if (action === 'withdraw') {
    const ok = await confirmDialog('Rút nguyện vọng đang chờ', 'Bạn muốn rút toàn bộ nguyện vọng đang chờ phản hồi để chọn lại sau?', 'Rút nguyện vọng');
    if (!ok) return;
  }

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
  } else if (action === 'normalize') {
    payload = {
      raw_title: data.get('raw_title') || '',
      raw_description: data.get('raw_description') || '',
      raw_background: data.get('raw_background') || '',
      save: true,
    };
  } else if (action === 'verify-enrollment') {
    payload = {
      student_id: data.get('student_id') || '',
      enrollment_code: data.get('enrollment_code') || '',
    };
  } else if (action === 'choice') {
    const inputs = data.getAll('advisor_id');
    const ids = inputs.filter(Boolean);
    if (ids.length !== new Set(ids).size || ids.some((id, index) => id !== inputs[index])) {
      showStatus('Chọn các giảng viên khác nhau theo thứ tự liên tục từ Ưu tiên 1 (không bỏ trống ở giữa).', true, true);
      return;
    }
    payload = {advisor_ids: ids, topic_description: data.get('topic_description'), contact};
  } else if (action === 'withdraw') payload = {advisor_ids: []};
  else if (action === 'topic') payload = {topic_description: data.get('topic_description'), auto_normalize: true};
  else if (action === 'contact') payload = contact;
  else if (action === 'milestone') {
    payload = {
      milestone_key: data.get('milestone_key'),
      official_title: data.get('official_title') || '',
      submission_url: data.get('submission_url') || '',
      submission_note: data.get('submission_note') || '',
    };
  } else if (action === 'decision') payload = {decision: submitterValue, user_id: form.dataset.student};
  else if (action === 'milestone-review') {
    payload = {
      user_id: data.get('user_id'),
      milestone_key: data.get('milestone_key'),
      status: submitterValue,
      advisor_feedback: data.get('advisor_feedback') || '',
    };
  } else if (action === 'outcome') {
    payload = {
      user_id: data.get('user_id'),
      rating: data.get('rating'),
      skills_applied: data.get('skills_applied') || '',
      summary_note: data.get('summary_note') || '',
    };
  } else if (action === 'threshold') payload = {threshold: Number(data.get('threshold'))};
  else if (action === 'recovery-code') payload = {email: data.get('email')};
  else if (action === 'proposal') payload = {advisor_ids: [...new Set([...selected, ...(state.accepted_advisors || [])])]};
  else if (action === 'manual') payload = {id: manualDraft ? manualDraft.id : state.manual?.id ?? null,
    assignments: manualChoices(form), reason: form.querySelector('textarea[name="reason"]').value};
  else if (action === 'publish-manual') payload = {id: state.manual.id, algorithm: 'manual'};
  else if (action === 'publish') payload = {id: state.proposal.id, ...(data.get('algorithm') ? {algorithm: data.get('algorithm')} : {})};
  else if (action === 'roster') {
    const file = data.get('csv_file');
    if (!file?.size || file.size > 1024 * 1024) {
      showStatus('Chọn tệp CSV có nội dung và dung lượng tối đa 1 MB.', true, true);
      return;
    }
    try { payload = {csv_text: await file.text()}; }
    catch { showStatus('Không đọc được tệp CSV.', true, true); return; }
  } else if (action === 'advisor-skills') {
    const file = data.get('skills_csv_file');
    if (!file?.size || file.size > 512 * 1024) {
      showStatus('Chọn tệp CSV kỹ năng giảng viên hợp lệ (tối đa 512 KB).', true, true);
      return;
    }
    try { payload = {csv_text: await file.text()}; }
    catch { showStatus('Không đọc được tệp CSV kỹ năng.', true, true); return; }
  } else if (['close', 'reopen', 'revoke'].includes(action)) payload = {};

  const controls = [...content.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)')];
  saving = true;
  controls.forEach(control => { control.disabled = true; });
  showStatus(action === 'proposal' ? 'Đang chạy đối chiếu Hungarian, PPO & DQN…' : action === 'normalize' ? 'Đang chuẩn hóa giọng văn học thuật & kỹ năng…' : 'Đang lưu…', false, true);
  try {
    const result = await api(action === 'recovery-code' ? '/api/auth/recovery-code'
      : '/' + ({withdraw: 'choice', 'publish-manual': 'publish'}[action] ?? action), payload);
    if (action === 'recovery-code') recoveryCodeInfo = result;
    if (action === 'manual') { manualDirty = false; manualDraft = null; }
    if (user.role === 'student') studentDirty = false;
    await refresh();
    const messages = {
      assessment: 'Đã lưu kết quả đánh giá kỹ năng.',
      normalize: 'Đã chuẩn hóa giọng văn sang Hồ sơ Học thuật Chuẩn và cập nhật gợi ý!',
      'verify-enrollment': 'Đã xác minh mã ghi danh học kỳ thành công.',
      choice: 'Đã lưu nguyện vọng theo thứ tự ưu tiên.',
      withdraw: 'Đã rút các nguyện vọng đang chờ.',
      topic: 'Đã lưu và đồng bộ mô tả đề tài.',
      contact: 'Đã lưu thông tin liên hệ.',
      milestone: 'Đã gửi cập nhật mốc khóa luận tới giảng viên hướng dẫn.',
      roster: 'Đã lưu danh sách khóa luận của kỳ.',
      'advisor-skills': 'Đã cập nhật ma trận kỹ năng giảng viên cho kỳ học.',
      close: 'Đã khóa nộp nguyện vọng. Giảng viên vẫn có thể xét duyệt.',
      reopen: 'Đã mở lại nộp nguyện vọng.',
      revoke: 'Đã thu hồi công bố để điều chỉnh lại phương án.',
      decision: 'Đã lưu quyết định xét duyệt nguyện vọng.',
      'milestone-review': 'Đã lưu phản hồi duyệt mốc khóa luận.',
      outcome: 'Đã ghi nhận đánh giá cuối kỳ (tín hiệu R4 Continual RL).',
      threshold: 'Đã cập nhật ngưỡng tin tưởng.',
      publish: 'Đã công bố chính thức kết quả phân công khóa luận.',
      'recovery-code': 'Đã cấp mã khôi phục dùng một lần.',
      manual: 'Đã lưu bản nháp phân công thủ công.',
      'publish-manual': 'Đã công bố bản phân công thủ công.',
      proposal: state.proposal?.status === 'feasible' ? 'Đã hoàn tất đối chiếu Hungarian, PPO & DQN!' : 'Chưa tìm được phương án khả thi.',
    };
    showStatus(messages[action] || 'Thao tác hoàn tất.');
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    saving = false;
    controls.forEach(control => { if (control.isConnected) control.disabled = false; });
  }
});

$('workspace-refresh-btn')?.addEventListener('click', async () => {
  showStatus('Đang làm mới dữ liệu kỳ học…');
  try {
    await refresh();
    showStatus('Đã cập nhật dữ liệu mới nhất.');
  } catch (e) {
    showStatus(e.message, true);
  }
});

$('fill-skill-question')?.addEventListener('click', () => {
  const labels = (state.profile?.skills || []).filter(s => s.status !== 'unassessed').map(s => s.label);
  const titleHint = state.dossier?.formal_title ? ` và đề tài "${state.dossier.formal_title}"` : '';
  $('thesis-question').value = `Hồ sơ kỹ năng của em (${labels.join(', ')})${titleHint} hợp với giảng viên nào nhất?`;
  $('thesis-question').focus();
});

const promptContainer = $('thesis-chat-prompts');
if (promptContainer) {
  for (const [label, question] of Object.entries(prompts)) {
    const button = document.createElement('button');
    button.className = 'secondary';
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', () => {
      $('thesis-question').value = question;
      $('thesis-question').focus();
    });
    promptContainer.append(button);
  }
}

$('thesis-chat-form')?.addEventListener('submit', async event => {
  event.preventDefault();
  const input = $('thesis-question');
  const question = input.value.trim();
  if (!question) return;
  const button = event.submitter || event.target.querySelector('button');
  const status = $('thesis-chat-status');
  if (button) button.disabled = true;
  status.textContent = 'AI Agent đang kiểm tra Guardrails & truy xuất nguồn giảng viên…';
  try {
    const reply = await api('/api/thesis/agent', {question, ...(previousQuestion && {previous_question: previousQuestion})});
    const blocked = reply.guardrail?.status === 'blocked';
    if (!blocked && ['topic_match', 'advisor_profile', 'my_profile_fit'].includes(reply.intent)) {
      previousQuestion = question;
    }
    const entry = document.createElement('article');
    entry.className = `agent-turn${blocked ? ' blocked' : ''}`;

    const guardBadge = blocked
      ? `<span class="agent-tag blocked">🛡️ Guardrail chặn: ${esc(reply.guardrail?.rule || reply.intent)}</span>`
      : `<span class="agent-tag passed">✓ Guardrail hợp lệ</span>`;
    const toolTags = (reply.agent_tools || []).map(t => `<span class="agent-tag">⚙ ${esc(t)}</span>`).join('');

    let html = `<div class="agent-turn-head">
      <h3>Hỏi: ${esc(question)}</h3>
      <div class="agent-meta-tags">${guardBadge}${toolTags}</div>
    </div>
    <p>${formatRichText(reply.answer || '')}</p>`;

    if (reply.rankings?.length) {
      html += `<div class="skill-chip-group" style="margin-top:10px">${reply.rankings.map(r =>
        `<span class="skill-chip verified">${esc(r.advisor_name)}${typeof r.score === 'number' ? ` · ${percent(r.score)}` : ''}</span>`
      ).join('')}</div>`;
    }
    const safeCitations = (reply.citations || []).filter(c => {
      try {
        const u = new URL(c.url || c.source_url);
        return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password;
      } catch { return false; }
    });
    if (safeCitations.length) {
      html += `<details class="xai-details-panel" style="margin-top:10px"><summary>Nguồn công trình &amp; hồ sơ kiểm chứng (${safeCitations.length})</summary><ul style="margin:8px 0 0;padding-left:18px;font-size:.85rem">
        ${safeCitations.map((c, idx) => `<li><strong>[${idx + 1}]</strong> <a href="${esc(c.url || c.source_url)}" target="_blank" rel="noopener">${esc(c.title || 'Nguồn tham khảo')}</a>${c.snippet ? ` — <span class="help">${esc(c.snippet)}</span>` : ''}</li>`).join('')}
      </ul></details>`;
    }
    entry.innerHTML = html;
    $('thesis-chat-history').prepend(entry);
    if (input.value.trim() === question) input.value = '';
    status.textContent = blocked ? 'Đã từ chối câu hỏi ngoài phạm vi theo quy tắc Guardrail.' : 'Trợ lý RAG đã phản hồi kèm căn cứ kiểm chứng.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    if (button) button.disabled = false;
  }
});

user = await requireSession();
if (user) {
  $('thesis-title').textContent = titles[user.role];
  const badge = $('nav-role-badge');
  if (badge) {
    badge.hidden = false;
    badge.textContent = `${roleBadges[user.role] || user.role} · ${user.name}`;
  }
  const kicker = $('thesis-role-kicker');
  if (kicker) kicker.textContent = roleBadges[user.role] || 'Không gian học vụ';
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

async function pollWorkspace() {
  if (!state || document.hidden || saving || manualDirty || user.role !== 'student' && content.contains(document.activeElement)) return;
  const previous = state;
  try {
    const latest = await api();
    if (saving || manualDirty || state !== previous || user.role !== 'student' && content.contains(document.activeElement)
        || JSON.stringify(previous) === JSON.stringify(latest)) return;
    state = latest;
    $('thesis-period').textContent = `Kỳ ${latest.semester}${latest.published ? ' · Đã công bố' : ''}`;
    if (user.role === 'dean') {
      if (content.querySelector('input[type="file"]')?.files?.length) { state = previous; return; }
      renderDean();
    } else if (user.role === 'student') {
      const priorAccepted = (previous.requests || []).some(r => r.status === 'accepted');
      const accepted = (latest.requests || []).some(r => r.status === 'accepted');
      const changed = (latest.requests || []).find(r => (previous.requests || []).find(old => old.advisor_id === r.advisor_id)?.status !== r.status);
      const message = latest.published && !previous.published ? 'Trưởng khoa đã công bố kết quả phân công chính thức.'
        : !latest.published && previous.published ? 'Trưởng khoa đã thu hồi danh sách công bố để rà soát.'
        : latest.assignment && latest.assignment.advisor_id !== previous.assignment?.advisor_id ? 'Bạn đã có giảng viên hướng dẫn trong danh sách công bố.'
        : accepted && !priorAccepted ? 'Giảng viên đã nhận hướng dẫn. Chờ trưởng khoa công bố cặp chính thức.'
        : changed ? `Trạng thái nguyện vọng đã cập nhật: ${statusNames[changed.status]}.`
        : latest.preferences_closed && !previous.preferences_closed ? 'Trưởng khoa đã khóa kỳ đăng ký.' : '';
      if (studentDirty || content.contains(document.activeElement)) {
        const status = content.querySelector('[data-student-status]');
        if (status) status.innerHTML = studentStatus();
        for (const form of content.querySelectorAll('form[data-action]')) {
          const action = form.dataset.action;
          const locked = (latest.published || latest.preferences_closed) && !['contact', 'milestone'].includes(action)
            || accepted && ['choice', 'withdraw'].includes(action);
          for (const button of form.querySelectorAll('button')) {
            if (locked && !button.disabled) {button.dataset.pollLocked = 'true'; button.disabled = true;}
            else if (!locked && button.dataset.pollLocked) {delete button.dataset.pollLocked; button.disabled = false;}
          }
          if (!locked && action === 'assessment') updateTracks(form);
        }
      } else content.innerHTML = studentView();
      if (message) showStatus(message);
    } else {
      content.innerHTML = facultyView();
      if (latest.published && !previous.published) showStatus('Trưởng khoa đã công bố kết quả.');
      else if (!latest.published && previous.published) showStatus('Trưởng khoa đã thu hồi danh sách công bố.');
      else if ((latest.requests || []).some(r => r.status === 'pending'
        && !(previous.requests || []).some(old => old.user_id === r.user_id && old.status === 'pending'))) {
        showStatus('Bạn có nguyện vọng hướng dẫn mới.');
      }
    }
  } catch { /* Keep the last loaded view if polling fails. */ }
}
if (['student', 'faculty', 'dean'].includes(user?.role)) setInterval(pollWorkspace, 25000);
addEventListener('pagehide', () => stopReplay(), {once: true});
