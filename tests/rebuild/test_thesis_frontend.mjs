import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

function element(extra = {}) {
  return {innerHTML: '', textContent: '', value: '', hidden: false, disabled: false, isConnected: true,
    handlers: {}, classList: {toggle() {}, contains() {return false;}},
    addEventListener(name, handler) {this.handlers[name] = handler;},
    setAttribute() {}, querySelector() {return null;}, querySelectorAll() {return [];},
    contains() {return false;}, append() {}, focus() {}, ...extra};
}

const elements = new Map();
const get = id => elements.get(id) ?? (elements.set(id, element()), elements.get(id));
const context = {console, URL, URLSearchParams, Set, Map, Object, Number, Date, JSON,
  document: {getElementById: get, createElement: element, querySelectorAll: () => [], activeElement: null, hidden: false},
  addEventListener() {}, setInterval() {}, location: {replace() {}},
  requireSession: async () => null, confidenceLabel: () => '', mountReplay: () => () => {},
  FormData: class {constructor(form) {this.values = form.values;} get(key) {return this.values[key];}},
  fetch: async () => ({ok: true, status: 200, json: async () => context.latest})};
const thesisSource = (await readFile(new URL('../../frontend/thesis.js', import.meta.url), 'utf8')).replace(/^import .*;\r?\n/gm, '');
await vm.runInNewContext(`(async () => {${thesisSource}
  globalThis.test = {studentView, facultyView, filteredFacultyRequests, deanRosterRows, manualAllocation,
    rememberManualDraft, pollWorkspace,
    state(value) {state = value;}, user(value) {user = value;},
    catalog(value) {catalog = value;}, facultyFilter(search, status) {facultySearch = search; facultyStatus = status;},
    rosterFilter(search, status) {rosterSearch = search; rosterStatus = status;},
    rankings(value) {rankings = value;}, studentDirty(value) {studentDirty = value;}};
})();`, context);
const api = context.test;
const content = get('thesis-content');
const advisors = [{advisor_id: 'a', advisor_name: 'Giảng viên A'}, {advisor_id: 'b', advisor_name: 'Giảng viên B'}];
api.catalog(advisors);
const roster = [{student_id: 'reason', name: 'Sinh viên', user_id: 'u1', submitted: false, incomplete_reasons: ['Chưa nộp khảo sát']}];
const dean = {roster_loaded: true, roster_preview: roster, student_count: 1, preferences_closed: false,
  manual: null, manual_quotas: [{advisor_id: 'a', total: 1}], accepted_assignments: {}, proposal: null, published: false};
api.state(dean);
const selects = [{name: 'reason', value: 'b'}];
const form = {querySelector: () => ({value: 'Đổi theo đề nghị'}), querySelectorAll: () => selects};
content.querySelector = selector => selector === '[data-action="manual"]' ? form : null;
api.rememberManualDraft();
api.state({...dean, threshold: 61});
assert.match(api.manualAllocation(), /value="b" selected/);
assert.match(api.manualAllocation(), /Đổi theo đề nghị/);
content.querySelector = () => null;

const faculty = {advisor_name: 'A', student_count: 2, published: true,
  teaching_load: {accepted: 1, assigned: 1, quota: 1}, registered_students: [], assignments: [],
  requests: [{name: 'An', status: 'pending', skills: [], topic_description: 'Web', user_id: 'u1'},
    {name: 'Bình', status: 'accepted', skills: [], topic_description: 'AI', user_id: 'u2'}]};
api.state(faculty);
api.facultyFilter('bình', 'accepted');
assert.equal(api.filteredFacultyRequests().length, 1);
assert.match(api.facultyView(), /1 đã nhận · 1 đã phân công chính thức/);
assert.match(api.facultyView(), /Xuất danh sách nhóm CSV/);
api.state({...dean, roster_preview: [...roster, {...roster[0], student_id: 'S2', incomplete_reasons: []}]});
api.rosterFilter('', 'incomplete');
assert.equal(api.deanRosterRows().length, 1);

const student = {semester: 'demo', profile: {skills: []}, assessment: [], in_roster: true,
  preferences_closed: true, published: false, requests: [], contact: {email: '', phone: ''}};
api.state(student);
api.user({role: 'student'});
api.rankings([{advisor_name: 'A', score: .6, basis: {topic_tags: ['web']}, explanation: {}}]);
assert.match(api.studentView(), /cùng hướng và công cụ có thể cho cùng gợi ý/);
context.latest = {...student, requests: [{advisor_id: 'a', status: 'accepted', rank: 1}]};
// The dean draft is deliberately dirty above; use a fresh module for polling.
const pollingContext = {...context, test: undefined};
pollingContext.latest = context.latest;
pollingContext.fetch = async () => ({ok: true, status: 200, json: async () => pollingContext.latest});
await vm.runInNewContext(`(async () => {${thesisSource}
  globalThis.test = {set(value) {user = {role:'student'}; state = value;}, pollWorkspace,
    dirty(value) {studentDirty = value;}};
})();`, pollingContext);
pollingContext.test.set(student);
await pollingContext.test.pollWorkspace();
assert.match(get('thesis-status').textContent, /Giảng viên đã nhận/);
pollingContext.latest = {...student, published: true, assignment: {advisor_id: 'a', advisor_name: 'A'}};
await pollingContext.test.pollWorkspace();
assert.match(get('thesis-status').textContent, /công bố kết quả/);
pollingContext.test.dirty(true);
const before = content.innerHTML;
const studentStatus = element();
content.querySelector = selector => selector === '[data-student-status]' ? studentStatus : null;
pollingContext.latest = {...student, published: false};
await pollingContext.test.pollWorkspace();
assert.equal(content.innerHTML, before);
assert.match(get('thesis-status').textContent, /thu hồi danh sách/);
assert.match(studentStatus.innerHTML, /chưa gửi nguyện vọng/);
const submitButton = element({dataset: {}});
content.querySelectorAll = selector => selector === 'form[data-action]'
  ? [{dataset: {action: 'choice'}, querySelectorAll: () => [submitButton]}] : [];
pollingContext.latest = {...student, preferences_closed: true, requests: [{advisor_id: 'a', status: 'pending', rank: 1}]};
await pollingContext.test.pollWorkspace();
assert.equal(submitButton.disabled, true);
pollingContext.latest = {...student, preferences_closed: false};
await pollingContext.test.pollWorkspace();
assert.equal(submitButton.disabled, false);

const loginElements = new Map();
const loginGet = id => loginElements.get(id) ?? (loginElements.set(id, element()), loginElements.get(id));
const authForm = loginGet('email-auth-form');
authForm.elements = Object.fromEntries(['name', 'password', 'activation_code', 'new_password', 'reset_code']
  .map(key => [key, element()]));
const loginContext = {console, URL, URLSearchParams,
  document: {getElementById: loginGet, querySelectorAll: () => []},
  location: {search: '', replace() {}},
  fetch: async path => path === '/api/auth/me' ? {ok: false}
    : {ok: true, json: async () => ({providers: {}})}};
const portalSource = await readFile(new URL('../../frontend/portal.js', import.meta.url), 'utf8');
await vm.runInNewContext(`(async () => {${portalSource.slice(0, portalSource.indexOf('async function training()')).replaceAll('export ', '')}
  await login();
})();`, loginContext);
loginGet('email-forgot').handlers.click();
assert.equal(loginGet('email-password-field').hidden, true);
assert.equal(authForm.elements.password.required, false);
assert.equal(authForm.elements.reset_code.required, true);
assert.equal(authForm.elements.new_password.required, true);
assert.equal(authForm.elements.password.disabled, true);
assert.equal(loginGet('email-auth-submit').textContent, 'Đặt lại mật khẩu');
loginGet('login-tab').handlers.click();
assert.equal(authForm.elements.password.required, true);
assert.equal(authForm.elements.reset_code.required, false);
assert.equal(authForm.elements.reset_code.disabled, true);
assert.equal(authForm.elements.new_password.disabled, true);

console.log('Frontend checks passed: manual draft, role filters, status polling, survey explanation and password reset form.');
