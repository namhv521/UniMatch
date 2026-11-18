"""Turnkey 1-command launcher for UniMatch Thesis Defense Demo Mode.

Usage:
    python scripts/run_demo.py                 # Start on http://127.0.0.1:8767
    python scripts/run_demo.py --reset         # Reset & re-seed fresh demo state
    python scripts/run_demo.py --port 8877     # Custom port
    python scripts/run_demo.py --check-only    # Seed & self-check without blocking
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv_safe(env_path: Path) -> None:
    """Load optional LLM keys from .env without overriding explicit process env."""
    if not env_path.is_file():
        return
    allowed_prefixes = ('UNIMATCH_LLM_', 'UNIMATCH_OPENROUTER_', 'GEMINI_', 'OPENAI_')
    for raw_line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key.startswith(allowed_prefixes) and value and key not in os.environ:
            os.environ[key] = value


def ensure_frontend_dist() -> Path:
    dist_dir = ROOT / 'frontend' / 'dist'
    thesis_src = ROOT / 'frontend' / 'thesis.js'
    thesis_dist = dist_dir / 'thesis.js'
    needs_build = not thesis_dist.is_file() or (
        thesis_src.is_file() and thesis_src.stat().st_mtime > thesis_dist.stat().st_mtime
    )
    if needs_build:
        node = shutil.which('node')
        if node and (ROOT / 'frontend' / 'build.mjs').is_file():
            print('[UniMatch Demo] Building frontend/dist ...', flush=True)
            subprocess.run([node, str(ROOT / 'frontend' / 'build.mjs')], check=True)
    return dist_dir if dist_dir.is_dir() else (ROOT / 'frontend')


def load_matching_backend(runtime_dir: Path):
    import torch

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    outputs_dir = ROOT / 'outputs'
    strict_bundle = outputs_dir / 'semester_rl_20261111_trusted_year_github'
    if strict_bundle.is_dir():
        from src.serving.semester_catalog import load_catalog

        print('[UniMatch Demo] Loading 17 NEU advisors + 6 Strict RL checkpoints (V1-V3 x PPO/DQN)...', flush=True)
        return load_catalog(outputs_dir, runtime_dir / 'proposals')

    from src.serving.rebuild_service import RebuildService

    print('[UniMatch Demo] Strict bundle not found; falling back to data_rebuild/v1 service...', flush=True)
    service = RebuildService.from_artifacts(ROOT / 'data_rebuild' / 'v1', runtime_dir=runtime_dir / 'proposals')
    return service, None


def _build_answers(roles: list[str], *, miss_last: bool = False) -> tuple[dict, dict, dict]:
    from backend.app.thesis_tracks import TRACKS

    survey = {}
    answers = {}
    tools = {}
    for idx, role in enumerate(roles):
        track = TRACKS[role]
        survey[role] = 4 if idx == 0 else 3
        q_ans = [q[2] for q in track['questions']]
        if miss_last and idx > 0 and q_ans:
            q_ans[-1] = (q_ans[-1] + 1) % len(track['questions'][-1][1])
        answers[role] = q_ans
        tools[role] = list(track['tools'][:3])
    return survey, answers, tools


def seed_demo_workspace(app, *, semester: str, origin: str) -> None:
    from fastapi.testclient import TestClient

    from backend.app.email_auth import insert_account, password_hash

    advisor_ids = list(app.state.rebuild_get_service().advisor_ids)
    lam_id = 'fit_89870b78c68a271f49b9' if 'fit_89870b78c68a271f49b9' in advisor_ids else advisor_ids[0]
    viet_id = 'fit_5a04416402925947eef7' if 'fit_5a04416402925947eef7' in advisor_ids else advisor_ids[min(1, len(advisor_ids) - 1)]
    tuan_id = 'fit_255f7819d1e13c7da6ea' if 'fit_255f7819d1e13c7da6ea' in advisor_ids else advisor_ids[min(2, len(advisor_ids) - 1)]
    thang_id = 'fit_992239a385b6475451e8' if 'fit_992239a385b6475451e8' in advisor_ids else advisor_ids[min(3, len(advisor_ids) - 1)]
    thai_id = 'fit_67f78a8b9fc135b6e24d' if 'fit_67f78a8b9fc135b6e24d' in advisor_ids else advisor_ids[min(4, len(advisor_ids) - 1)]
    thu_id = 'fit_d15a8b345373db65a531' if 'fit_d15a8b345373db65a531' in advisor_ids else advisor_ids[min(5, len(advisor_ids) - 1)]

    demo_accounts = [
        {
            'email': 'hvn@st.neu.edu.vn',
            'name': 'Hoàng Văn Nam',
            'role': 'student',
            'badge': 'Sinh viên NEU',
            'label': '🎓 SV Hoàng Văn Nam (hvn@st.neu.edu.vn)',
        },
        {
            'email': 'sv1@demo.unimatch.edu.vn',
            'name': 'Nguyễn Minh Anh',
            'role': 'student',
            'badge': 'Sinh viên (Đã khảo sát)',
            'label': '📝 SV Nguyễn Minh Anh (Đã chuẩn hóa)',
        },
        {
            'email': 'advisor.hvn@neu.edu.vn',
            'name': 'ThS. Nguyễn Hùng Việt',
            'role': 'faculty',
            'advisor_id': viet_id,
            'badge': 'Giảng viên (advisor.hvn)',
            'label': '👨‍🏫 GV advisor.hvn@neu.edu.vn',
        },
        {
            'email': 'lam.px@demo.unimatch.edu.vn',
            'name': 'TS. Phạm Xuân Lâm',
            'role': 'faculty',
            'advisor_id': lam_id,
            'badge': 'Giảng viên (RL / Gợi ý)',
            'label': '👨‍🏫 GV TS. Phạm Xuân Lâm',
        },
        {
            'email': 'advisors.lead@neu.edu.vn',
            'name': 'Ban Chủ nhiệm Khoa CNTT',
            'role': 'dean',
            'badge': 'Trưởng khoa (advisors.lead)',
            'label': '🏛️ Trưởng khoa (advisors.lead@neu.edu.vn)',
        },
    ]
    app.state.demo_accounts = demo_accounts

    with app.state.portal_store.connect() as db:
        already_seeded = db.execute(
            'SELECT 1 FROM thesis_semesters WHERE semester=?',
            (semester,),
        ).fetchone()
        if already_seeded:
            return

        pw_hash = password_hash('UniMatch-Demo-2026!')
        for item in demo_accounts:
            insert_account(
                db,
                item['email'],
                item['name'],
                pw_hash,
                role=item['role'],
                advisor_id=item.get('advisor_id'),
                advisor_semester=semester if item['role'] in ('faculty', 'dean') else None,
            )
        extra_students = [
            ('sv2@demo.unimatch.edu.vn', 'Trần Quốc Bảo'),
            ('sv3@demo.unimatch.edu.vn', 'Lê Hoàng Nam'),
            ('sv4@demo.unimatch.edu.vn', 'Phạm Thu Hà'),
            ('sv5@demo.unimatch.edu.vn', 'Vũ Đức Minh'),
            ('sv6@demo.unimatch.edu.vn', 'Đỗ Khánh Linh'),
            ('sv7@demo.unimatch.edu.vn', 'Hoàng Gia Huy'),
            ('sv8@demo.unimatch.edu.vn', 'Bùi Phương Thảo'),
        ]
        for email, name in extra_students:
            insert_account(db, email, name, pw_hash, role='student')
        insert_account(db, 'dean@demo.unimatch.edu.vn', 'Ban Chủ nhiệm Khoa CNTT', pw_hash, role='dean', advisor_semester=semester)
        insert_account(db, 'viet.nh@demo.unimatch.edu.vn', 'ThS. Nguyễn Hùng Việt', pw_hash, role='faculty', advisor_id=viet_id, advisor_semester=semester)

    headers = {'Origin': origin}

    def client_for(email: str, name: str) -> TestClient:
        c = TestClient(app, base_url=origin)
        token = app.state.portal_store.create_session('email', email, name)
        c.cookies.set('unimatch_session', token)
        return c

    # 1. Dean uploads semester roster CSV (8 students)
    roster_csv = '\n'.join([
        'student_id,name,email,phone,topic,skills',
        '11220101,Nguyễn Minh Anh,sv1@demo.unimatch.edu.vn,0912345101,Trợ lý tư vấn học vụ dùng RAG và LLM,Python;FastAPI;PyTorch;RAG',
        '11220102,Hoàng Văn Nam,hvn@st.neu.edu.vn,0912345102,Hệ thống thương mại điện tử thông minh,React;TypeScript;FastAPI;PostgreSQL',
        '11220103,Lê Hoàng Nam,sv3@demo.unimatch.edu.vn,0912345103,Hệ thống gợi ý lộ trình học tập cá nhân hóa bằng RL,Python;PyTorch;React;MongoDB',
        '11220104,Phạm Thu Hà,sv4@demo.unimatch.edu.vn,0912345104,Phân tích cảm xúc bình luận thương mại điện tử tiếng Việt,Python;Hugging Face;SQL;Scikit-learn',
        '11220105,Vũ Đức Minh,sv5@demo.unimatch.edu.vn,0912345105,Nhận diện phương tiện giao thông thời gian thực với Computer Vision,Python;PyTorch;OpenCV;YOLO',
        '11220106,Đỗ Khánh Linh,sv6@demo.unimatch.edu.vn,0912345106,Kiến trúc Microservices cho nền tảng đặt lịch dịch vụ số,TypeScript;Next.js;FastAPI;PostgreSQL;Redis',
        '11220107,Hoàng Gia Huy,sv7@demo.unimatch.edu.vn,0912345107,Phân tích dữ liệu BI đánh giá mức độ chuyển đổi số doanh nghiệp SME,SQL;Python;Power BI;Quantitative Analysis',
        '11220108,Bùi Phương Thảo,sv8@demo.unimatch.edu.vn,0912345108,Ứng dụng học máy dự báo chuỗi thời gian nhu cầu kho vận,Python;Scikit-learn;SQL;Time Series',
    ])
    dean_client = client_for('advisors.lead@neu.edu.vn', 'Ban Chủ nhiệm Khoa CNTT')
    res = dean_client.post('/api/thesis/roster', json={'csv_text': roster_csv}, headers=headers)
    if res.status_code != 200:
        raise RuntimeError(f'Failed to seed demo roster: {res.status_code} {res.text}')

    # 2. Seed student assessments, colloquial->academic normalizations, contacts, and preferences
    student_seeds = [
        {
            'email': 'sv1@demo.unimatch.edu.vn',
            'name': 'Nguyễn Minh Anh',
            'phone': '0912345101',
            'roles': ['nlp', 'machine_learning', 'backend_development'],
            'raw_title': 'Làm con bot chat AI tư vấn khóa luận cho sinh viên trường mình dùng RAG với LLM',
            'raw_description': (
                'Em tính code một con chatbot hỏi đáp quy chế với gợi ý thầy cô hướng dẫn cho sv đỡ bị lạc đề. '
                'Backend em xài python fastapi với postgres, phần AI em nhúng embedding kết hợp RAG chống bịa đặt '
                'và chặn mấy câu hỏi linh tinh ngoài lề.'
            ),
            'raw_background': 'Đã làm đồ án môn NLP với Python, FastAPI, Hugging Face và React cơ bản.',
            'advisors': [viet_id, lam_id, tuan_id],
        },
        {
            'email': 'sv3@demo.unimatch.edu.vn',
            'name': 'Lê Hoàng Nam',
            'phone': '0912345103',
            'roles': ['machine_learning', 'full_stack_development'],
            'raw_title': 'Web gợi ý khóa học thông minh cho sinh viên bằng thuật toán học tăng cường RL',
            'raw_description': (
                'Em muốn build web fullstack dùng React với FastAPI và MongoDB, bên dưới chạy mô hình reinforcement '
                'learning kết hợp hệ thống gợi ý để cá nhân hóa lộ trình học tập cho từng bạn sinh viên.'
            ),
            'raw_background': 'Nắm vững Python, PyTorch, React và thiết kế REST API.',
            'advisors': [lam_id, viet_id],
        },
        {
            'email': 'sv4@demo.unimatch.edu.vn',
            'name': 'Phạm Thu Hà',
            'phone': '0912345104',
            'roles': ['nlp', 'machine_learning'],
            'raw_title': 'Phân loại review khách hàng trên sàn shopee tiki bằng PhoBERT',
            'raw_description': (
                'Em định cào dữ liệu bình luận tiếng Việt trên sàn thương mại điện tử rồi fine-tune mô hình BERT '
                'để phân tích cảm xúc tích cực tiêu cực và trích xuất khía cạnh sản phẩm.'
            ),
            'raw_background': 'Đã học Xử lý ngôn ngữ tự nhiên, Học máy, Python và SQL.',
            'advisors': [tuan_id, viet_id],
        },
        {
            'email': 'sv5@demo.unimatch.edu.vn',
            'name': 'Vũ Đức Minh',
            'phone': '0912345105',
            'roles': ['computer_vision', 'machine_learning'],
            'raw_title': 'Nhận diện xe cộ và đếm lưu lượng giao thông qua camera bằng YOLO',
            'raw_description': (
                'Em muốn làm hệ thống đọc video camera giao thông thời gian thực dùng YOLO với OpenCV trên PyTorch, '
                'có trang web hiển thị thống kê mật độ xe theo khung giờ.'
            ),
            'raw_background': 'Có kinh nghiệm xử lý ảnh với OpenCV, PyTorch và FastAPI.',
            'advisors': [thang_id, viet_id],
        },
        {
            'email': 'sv6@demo.unimatch.edu.vn',
            'name': 'Đỗ Khánh Linh',
            'phone': '0912345106',
            'roles': ['full_stack_development', 'backend_development'],
            'raw_title': 'Xây web đặt lịch khám và quản lý dịch vụ theo kiến trúc microservices',
            'raw_description': (
                'Em tính thiết kế hệ thống web fullstack dùng Next.js, FastAPI, PostgreSQL và Redis cache để chống '
                'trùng lịch đặt chỗ khi nhiều người bấm cùng lúc.'
            ),
            'raw_background': 'Thực tập Backend 4 tháng với TypeScript, Python FastAPI, Docker và PostgreSQL.',
            'advisors': [thai_id, lam_id],
        },
        {
            'email': 'sv7@demo.unimatch.edu.vn',
            'name': 'Hoàng Gia Huy',
            'phone': '0912345107',
            'roles': ['machine_learning', 'frontend_development'],
            'raw_title': 'Phân tích dữ liệu khảo sát mức độ chuyển đổi số của doanh nghiệp vừa và nhỏ',
            'raw_description': (
                'Em muốn thu thập bảng hỏi khảo sát các doanh nghiệp SME, chạy phân tích định lượng hồi quy và '
                'làm dashboard trực quan hóa các chỉ số chuyển đổi số.'
            ),
            'raw_background': 'Thành thạo SQL, Python phân tích dữ liệu và thiết kế biểu mẫu khảo sát.',
            'advisors': [thu_id, tuan_id],
        },
    ]

    for seed in student_seeds:
        sc = client_for(seed['email'], seed['name'])
        survey, answers, tools = _build_answers(seed['roles'])
        r_assess = sc.post(
            '/api/thesis/assessment',
            json={
                'version': 'roles-v2',
                'orientation': 'defined',
                'major': 'it',
                'roles': seed['roles'],
                'tools': tools,
                'survey': survey,
                'answers': answers,
            },
            headers=headers,
        )
        if r_assess.status_code != 200:
            raise RuntimeError(f"Assessment seed failed for {seed['email']}: {r_assess.text}")

        r_norm = sc.post(
            '/api/thesis/normalize',
            json={
                'raw_title': seed['raw_title'],
                'raw_description': seed['raw_description'],
                'raw_background': seed['raw_background'],
                'apply_to_topic': True,
            },
            headers=headers,
        )
        if r_norm.status_code != 200:
            raise RuntimeError(f"Normalize seed failed for {seed['email']}: {r_norm.text}")

        r_choice = sc.post(
            '/api/thesis/choice',
            json={
                'advisor_ids': seed['advisors'],
                'contact': {'email': seed['email'], 'phone': seed['phone']},
            },
            headers=headers,
        )
        if r_choice.status_code != 200:
            raise RuntimeError(f"Choice seed failed for {seed['email']}: {r_choice.text}")

    # 3. Faculty TS. Phạm Xuân Lâm pre-accepts Lê Hoàng Nam (sv3) so Dean's optimization demonstrates hard fixed constraints + pending preferences
    lam_client = client_for('lam.px@demo.unimatch.edu.vn', 'TS. Phạm Xuân Lâm')
    lam_ws = lam_client.get('/api/thesis').json()
    for req in lam_ws.get('requests', []):
        if req.get('name') == 'Lê Hoàng Nam':
            lam_client.post(
                '/api/thesis/decision',
                json={'user_id': req['user_id'], 'decision': 'accepted'},
                headers=headers,
            )
            break


def build_demo_app(*, host: str = '127.0.0.1', port: int = 8767, reset: bool = False):
    runtime_dir = ROOT / 'data_rebuild' / 'runtime' / 'demo_defense'
    if reset and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    _load_dotenv_safe(ROOT / '.env')
    db_path = runtime_dir / 'portal.sqlite3'
    origin = f'http://{host}:{port}'
    semester = os.environ.get('UNIMATCH_THESIS_SEMESTER', '2026.1').strip() or '2026.1'

    os.environ['UNIMATCH_DATABASE_URL'] = str(db_path)
    os.environ['UNIMATCH_AUTH_DB'] = str(db_path)
    os.environ['UNIMATCH_PUBLIC_ORIGIN'] = origin
    os.environ['UNIMATCH_THESIS_SEMESTER'] = semester
    os.environ['UNIMATCH_DEPLOYMENT'] = 'local'
    os.environ['UNIMATCH_DEMO_MODE'] = '1'

    dist_dir = ensure_frontend_dist()
    service, assistant = load_matching_backend(runtime_dir)

    from backend.app.rebuild_assistant_api import create_app

    app = create_app(
        service=service,
        assistant=assistant,
        token='demo-defense-local-token',
        frontend_dir=dist_dir,
    )
    seed_demo_workspace(app, semester=semester, origin=origin)
    return app, origin, semester, db_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Launch UniMatch Thesis Defense Demo Mode.')
    parser.add_argument('--host', default='127.0.0.1', help='Loopback host to bind (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8767, help='Port to bind (default: 8767)')
    parser.add_argument('--reset', action='store_true', help='Reset SQLite demo database before starting')
    parser.add_argument('--open-browser', action='store_true', help='Open browser automatically')
    parser.add_argument('--check-only', action='store_true', help='Seed, run self-diagnostics, and exit')
    args = parser.parse_args()

    app, origin, semester, db_path = build_demo_app(host=args.host, port=args.port, reset=args.reset)

    if args.check_only:
        from fastapi.testclient import TestClient

        client = TestClient(app, base_url=origin)
        health = client.get('/health').json()
        auth_cfg = client.get('/api/auth/config').json()
        switch = client.post(
            '/api/auth/demo-switch',
            json={'email': 'sv1@demo.unimatch.edu.vn'},
            headers={'Origin': origin},
        )
        ws = client.get('/api/thesis').json()
        recs = client.get('/api/thesis/recommendations').json()
        cat = client.get('/api/thesis/catalog').json()
        print(json.dumps({
            'status': 'DEMO_CHECK_OK',
            'origin': origin,
            'semester': semester,
            'db_path': str(db_path),
            'health_status': health.get('status'),
            'demo_accounts': len(auth_cfg.get('demo_accounts', [])),
            'sv1_recommendations': len(recs) if isinstance(recs, list) else 0,
            'sv1_has_dossier': bool(ws.get('dossier')),
            'catalog_advisors': len(cat) if isinstance(cat, list) else 0,
        }, ensure_ascii=False, indent=2))
        return 0

    banner = f"""
========================================================================
  UNIMATCH — CHẾ ĐỘ DEMO BẢO VỆ KHÓA LUẬN (END-TO-END)
========================================================================
  Trang chủ Portal : {origin}/landing.html
  Đăng nhập nhanh  : {origin}/login.html
  Không gian KLTN  : {origin}/thesis.html
  Sân khấu 3D/RL   : {origin}/rebuild.html
  Học kỳ Demo      : {semester}
  Cơ sở dữ liệu    : {db_path}
------------------------------------------------------------------------
  Tài khoản Demo 1-Click (Mật khẩu dự phòng: UniMatch-Demo-2026!):
    1. sv1@demo.unimatch.edu.vn     — SV Nguyễn Minh Anh (Đã chuẩn hóa hồ sơ)
    2. sv2@demo.unimatch.edu.vn     — SV Trần Quốc Bảo (Trải nghiệm khảo sát mới)
    3. lam.px@demo.unimatch.edu.vn  — GV TS. Phạm Xuân Lâm (RL / Hệ gợi ý)
    4. viet.nh@demo.unimatch.edu.vn — GV ThS. Nguyễn Hùng Việt (NLP / LLM)
    5. dean@demo.unimatch.edu.vn    — Ban Chủ nhiệm Khoa (Điều phối PPO/DQN/Hungarian)
========================================================================
"""
    print(banner, flush=True)
    if args.open_browser:
        webbrowser.open(f'{origin}/login.html')

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, access_log=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
