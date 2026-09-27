import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const algorithms = {exact_hungarian:'Tối ưu chính xác (Hungarian)',greedy:'Tham lam (Greedy)',spa:'Ghép ổn định (SPA)',random:'Ngẫu nhiên',maskable_ppo:'Maskable PPO'};
const number = value => Number.isFinite(value) ? value.toLocaleString('vi-VN',{maximumFractionDigits:3}) : 'Chưa có';
async function request(path, options) {
  let response;
  try { response = await fetch('/api/v1/'+path, options); }
  catch { throw new Error('Không kết nối được máy chủ. Kiểm tra dịch vụ rồi thử lại.'); }
  let data;
  try { data = await response.json(); }
  catch { throw new Error('Máy chủ trả về dữ liệu không hợp lệ. Kiểm tra dịch vụ rồi thử lại.'); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Yêu cầu chưa hợp lệ. Kiểm tra hạn mức rồi thử lại.');
  return data;
}

function App() {
  const [health,setHealth] = useState(null), [faculty,setFaculty] = useState([]);
  const [loading,setLoading] = useState(true), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const [algorithm,setAlgorithm] = useState('exact_hungarian'), [cohort,setCohort] = useState('val'), [quota,setQuota] = useState('');
  const [result,setResult] = useState(null), [search,setSearch] = useState('');
  async function refresh() {
    setLoading(true); setError(''); setResult(null); setFaculty([]); setHealth(null);
    try {
      const status = await request('health'); setHealth(status);
      if(status.data_loaded) {
        const people = await request('faculty'); setFaculty(people.advisors);
        setAlgorithm(current => status.available_models.includes(current) ? current : status.available_models[0] || '');
      }
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(()=>{refresh();},[]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const output = await request('allocate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cohort_type:cohort,algorithm,...(quota ? {quota_override:Number(quota)} : {})})});
      setResult({...output,cohort_type:cohort});
    } catch(e) { setError(e.message); }
    finally { setBusy(false); }
  }
  const rows = result?.assignments.filter(row=>[row.student_name,row.student_id,row.thesis_title,row.advisor_name].some(value=>String(value||'').toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')))) || [];
  return <>
    <a className="skip" href="#workspace">Đến khu vực phân bổ</a>
    <header><div className="brand">FIT-NEU <span>Nghiên cứu phân bổ hướng dẫn</span></div><div className="connection" role="status">{loading?'Đang kết nối…':health?.data_loaded?'Dữ liệu đã nạp':'Chưa sẵn sàng'}</div></header>
    <main id="workspace">
      <div className="page-title"><div><h1>Phân bổ giảng viên hướng dẫn</h1><p>Đối chiếu chuyên môn đề tài và hạn mức hướng dẫn.</p></div><button className="secondary" onClick={refresh} disabled={loading||busy}>Tải lại dữ liệu</button></div>
      {error && <div className="notice error" role="alert"><strong>Chưa thể hoàn tất yêu cầu.</strong> {error}</div>}
      {!loading && !health?.data_loaded && <div className="notice" role="status">Dữ liệu chưa sẵn sàng. Hoàn tất trích xuất và kiểm duyệt dữ liệu, sau đó chọn “Tải lại dữ liệu”.</div>}
      {(health?.partial_data || result?.partial_data) && <div className="notice" role="status"><strong>Dữ liệu đang hoàn thiện.</strong> Kết quả chỉ dùng kiểm tra vận hành, chưa dùng kết luận nghiên cứu.</div>}
      <form onSubmit={submit} className="controls" aria-label="Thiết lập phân bổ">
        <fieldset disabled={!health?.data_loaded||loading||busy}>
          <label>Nhóm sinh viên<select value={cohort} onChange={e=>setCohort(e.target.value)}><option value="val">Tập kiểm định (validation)</option><option value="train">Tập huấn luyện (train)</option></select></label>
          <label>Thuật toán<select value={algorithm} onChange={e=>setAlgorithm(e.target.value)}>{(health?.available_models || ['exact_hungarian']).map(key=><option key={key} value={key}>{algorithms[key]||key}</option>)}</select></label>
          <label>Hạn mức mỗi giảng viên<input type="number" min="1" step="1" placeholder="Tự động theo nhóm" value={quota} onChange={e=>setQuota(e.target.value)} aria-describedby="quota-help"/></label>
          <button type="submit">{busy?'Đang phân bổ…':'Chạy phân bổ'}</button>
        </fieldset>
        <p id="quota-help" className="hint">Để trống hạn mức để dùng cấu hình dữ liệu. Tập kiểm tra cuối cùng được khóa trong giai đoạn lựa chọn mô hình.</p>
      </form>
      <div className="workspace" aria-busy={busy}>
        <section className="results" aria-labelledby="result-title">
          <div className="section-title"><h2 id="result-title">Kết quả phân bổ</h2>{result && <span>{result.assignments.length} sinh viên</span>}</div>
          {!result ? <div className="empty" role="status"><h3>{busy?'Đang tính phương án phân bổ':'Chưa có phương án phân bổ'}</h3><p>{busy?'Kết quả và tải hướng dẫn sẽ xuất hiện khi hoàn tất.':'Chọn nhóm sinh viên và thuật toán, sau đó chạy phân bổ để xem kết quả.'}</p></div> : <>
            <p className="result-caption">{algorithms[result.algorithm] || result.algorithm} · {result.cohort_type==='val'?'Tập kiểm định':'Tập huấn luyện'}</p>
            <dl className="metrics"><div><dt>Tương thích trung bình</dt><dd>{number(result.metrics.mean_compatibility)}</dd></div><div><dt>Vượt hạn mức</dt><dd>{number(result.metrics.quota_violations)}</dd></div><div><dt>Tỷ lệ so với tối ưu</dt><dd>{number(result.metrics.optimality_ratio)}</dd></div><div><dt>Phương sai tải</dt><dd>{number(result.metrics.load_variance)}</dd></div></dl>
            <label className="search">Tìm trong kết quả<input type="search" placeholder="Tên, mã sinh viên, đề tài hoặc giảng viên" value={search} onChange={e=>setSearch(e.target.value)}/></label>
            <div className="table-scroll" tabIndex="0" role="region" aria-label="Bảng phân bổ, có thể cuộn ngang"><table><caption>{rows.length} / {result.assignments.length} phân bổ</caption><thead><tr><th scope="col">Sinh viên / Đề tài</th><th scope="col">Giảng viên</th><th scope="col" className="numeric">Tương thích</th></tr></thead><tbody>{rows.map((row,index)=><tr key={`${row.student_id}-${index}`}><td><strong>{row.student_name || 'Chưa có tên'}</strong><span className="student-id">{row.student_id || 'Chưa có mã'}</span><p>{row.thesis_title || 'Chưa có tiêu đề'}</p></td><td>{row.advisor_name}</td><td className="numeric">{number(row.compatibility_score)}</td></tr>)}</tbody></table>{!rows.length && <p className="no-matches">Không có kết quả phù hợp. Thử từ khóa khác.</p>}</div>
          </>}
        </section>
        <aside aria-labelledby="faculty-title"><div className="section-title"><h2 id="faculty-title">Tải hướng dẫn</h2><span>{faculty.length} giảng viên</span></div><p className="hint">{result?'Số sinh viên đã phân bổ / hạn mức.':'Tải được cập nhật sau mỗi lần phân bổ.'}</p><ul className="faculty">{faculty.map(advisor=>{const state=result?.advisor_loads[advisor.advisor_name]; const load=state?.current_load ?? 0; const capacity=state?.quota; return <li key={advisor.advisor_id}><div><strong>{advisor.advisor_name}</strong><span>{result ? `${load} / ${capacity}` : 'Chưa phân bổ'}</span></div><p>{advisor.primary_field || advisor.academic_title || 'Chưa xác định lĩnh vực'}</p>{result && <><meter min="0" max={Math.max(capacity || 0,load,1)} value={load} aria-label={`Tải của ${advisor.advisor_name}: ${load} trên ${capacity}`}/>{load>=capacity && <small>{load>capacity?'Vượt hạn mức':'Đã đủ hạn mức'}</small>}</>}</li>;})}</ul>{!faculty.length && <p className="empty-faculty">Danh sách giảng viên xuất hiện khi dữ liệu sẵn sàng.</p>}</aside>
      </div>
      <footer>Nguồn hồ sơ: tài liệu khóa luận và FIT-NEU. Điểm tương thích phản ánh nội dung chuyên môn, không phải đánh giá chất lượng sinh viên.</footer>
    </main>
  </>;
}
createRoot(document.getElementById('root')).render(<App/>);
