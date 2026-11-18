"""Email account registration, activation and shared portal sessions."""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

EMAIL = re.compile(r'[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}')
PASSWORD_HASH = re.compile(r'[0-9a-f]{32}:[0-9a-f]{64}')
DIGEST = re.compile(r'[0-9a-f]{64}')
PASSWORD_WORKERS = threading.BoundedSemaphore(2)


DEFAULT_HVN_ADVISOR_ID = 'fit_5a04416402925947eef7'


def staff_role_for_email(email: str | None) -> dict | None:
    if not email or not isinstance(email, str):
        return None
    norm = email.strip().lower()
    custom_raw = os.environ.get('UNIMATCH_STAFF_EMAILS', '').strip()
    if custom_raw:
        try:
            custom = json.loads(custom_raw)
            if isinstance(custom, dict) and norm in custom and isinstance(custom[norm], dict):
                entry = custom[norm]
                if entry.get('role') in ('dean', 'faculty', 'student'):
                    return {
                        'role': entry['role'],
                        'advisor_id': entry.get('advisor_id'),
                    }
        except ValueError:
            pass
    if norm == 'advisors.lead@neu.edu.vn':
        return {'role': 'dean', 'advisor_id': None}
    if norm == 'advisor.hvn@neu.edu.vn':
        return {
            'role': 'faculty',
            'advisor_id': os.environ.get('UNIMATCH_HVN_ADVISOR_ID', DEFAULT_HVN_ADVISOR_ID).strip() or DEFAULT_HVN_ADVISOR_ID,
        }
    return None


def normalized_email(value):
    email = value.strip().lower() if isinstance(value, str) else ''
    if len(email) > 254 or not EMAIL.fullmatch(email):
        raise HTTPException(422, 'invalid_email')
    return email


def valid_password(password, *, new=False):
    if not isinstance(password, str) or not (12 if new else 1) <= len(password) <= 128:
        raise HTTPException(422, 'invalid_password')
    return password


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024**2, dklen=32)
    return f'{salt.hex()}:{digest.hex()}'


def matches(password, encoded):
    return hmac.compare_digest(password_hash(password, bytes.fromhex(encoded.split(':')[0])), encoded)


def insert_account(db, email, name, encoded, *, role='student', activation=None, advisor_id=None, advisor_semester=None):
    from .portal import hashed
    user_id = hashed('email:' + email)
    db.execute("INSERT INTO users(id,provider,subject,name) VALUES (?,'email',?,?) ON CONFLICT(id) DO NOTHING",
               (user_id, email, name))
    return db.execute('INSERT INTO email_accounts VALUES (?,?,?,?,?,?,?) '
                      'ON CONFLICT(email) DO NOTHING RETURNING role',
                      (email, user_id, encoded, activation, role, advisor_id, advisor_semester)).fetchone()


def issue_password_reset(store, email):
    code = secrets.token_urlsafe(12)
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM email_accounts WHERE email=?', (email,)).fetchone():
            return None
        db.execute('INSERT INTO email_password_resets(email,token_hash,expires) VALUES (?,?,?) '
                   'ON CONFLICT(email) DO UPDATE SET token_hash=excluded.token_hash,expires=excluded.expires',
                   (email, hashlib.sha256(code.encode()).hexdigest(), time.time() + 1800))
    return code


def repair_canonical_staff_roles(store):
    """Ensure canonical NEU dean & faculty accounts always hold their intended roles in DB."""
    default_adv = os.environ.get('UNIMATCH_HVN_ADVISOR_ID', DEFAULT_HVN_ADVISOR_ID).strip() or DEFAULT_HVN_ADVISOR_ID
    with store.connect() as db:
        db.execute(
            "UPDATE email_accounts SET role='dean', advisor_id=NULL WHERE email=?",
            ('advisors.lead@neu.edu.vn',),
        )
        db.execute(
            "UPDATE email_accounts SET role='faculty', advisor_id=COALESCE(advisor_id, ?) WHERE email=?",
            (default_adv, 'advisor.hvn@neu.edu.vn'),
        )
        db.execute(
            "UPDATE email_accounts SET role='student', advisor_id=NULL WHERE email=?",
            ('hvn@st.neu.edu.vn',),
        )


def seed_accounts(store):
    repair_canonical_staff_roles(store)
    entries = json.loads(os.environ.get('UNIMATCH_EMAIL_ACCOUNT_SEED', '[]') or '[]')
    if not isinstance(entries, list):
        raise ValueError('invalid_email_account_seed')
    if not entries:
        return
    with store.connect() as db:
        for entry in entries:
            email = normalized_email(entry['email'])
            name, role = entry['name'], entry['role']
            encoded, activation = entry['password_hash'], entry['activation_hash']
            advisor_id, semester = entry.get('advisor_id'), entry.get('advisor_semester')
            if (role not in ('student', 'faculty', 'dean') or not isinstance(name, str) or not 1 <= len(name) <= 160
                    or not PASSWORD_HASH.fullmatch(encoded) or not DIGEST.fullmatch(activation)
                    or (role == 'faculty') != bool(advisor_id)):
                raise ValueError('invalid_email_account_seed')
            existing = db.execute('SELECT role,advisor_id,advisor_semester FROM email_accounts WHERE email=?',
                                  (email,)).fetchone()
            if existing:
                if existing['role'] != role or (role == 'faculty' and existing['advisor_id'] != advisor_id):
                    db.execute(
                        'UPDATE email_accounts SET role=?, advisor_id=?, advisor_semester=COALESCE(?, advisor_semester) WHERE email=?',
                        (role, advisor_id if role == 'faculty' else None, semester, email),
                    )
                continue
            insert_account(db, email, name, encoded, role=role, activation=activation, advisor_id=advisor_id,
                           advisor_semester=semester)
    repair_canonical_staff_roles(store)


def install_email_auth(router, store, check_origin, set_session_cookie, authenticated):
    from .portal import AuthStartRateLimiter, client_address, hashed
    limiter = AuthStartRateLimiter(12, 60)
    seed_accounts(store)

    def perform(action, payload):
        email = normalized_email(payload.get('email'))
        if action == 'reset':
            code = payload.get('reset_code')
            if not isinstance(code, str) or not 1 <= len(code) <= 128:
                raise HTTPException(401, 'invalid_reset_code')
            new_password = valid_password(payload.get('new_password'), new=True)
            updated = password_hash(new_password)
            with store.connect() as db:
                reset = db.execute('DELETE FROM email_password_resets WHERE email=? AND token_hash=? AND expires>? '
                                   'RETURNING email',
                                   (email, hashlib.sha256(code.encode()).hexdigest(), time.time())).fetchone()
                if reset is None:
                    raise HTTPException(401, 'invalid_reset_code')
                account = db.execute('SELECT user_id FROM email_accounts WHERE email=?', (email,)).fetchone()
                db.execute('UPDATE email_accounts SET password_hash=?,activation_hash=NULL WHERE email=?',
                           (updated, email))
                db.execute('DELETE FROM sessions WHERE user_id=?', (account['user_id'],))
                user = db.execute('SELECT name FROM users WHERE id=?', (account['user_id'],)).fetchone()
            return set_session_cookie(JSONResponse({'ok': True}), store.create_session('email', email, user['name']))
        password = valid_password(payload.get('password'), new=action == 'register')
        if action == 'register':
            name = payload.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
                raise HTTPException(422, 'invalid_name')
            name = name.strip()
            encoded = password_hash(password)
            staff = staff_role_for_email(email)
            assigned_role = staff['role'] if staff else 'student'
            assigned_advisor = staff['advisor_id'] if staff else None
            with store.connect() as db:
                if insert_account(db, email, name, encoded, role=assigned_role, advisor_id=assigned_advisor) is None:
                    raise HTTPException(409, 'email_unavailable')
        else:
            with store.connect() as db:
                account = db.execute('SELECT e.password_hash,e.activation_hash,u.name FROM email_accounts e '
                                     'JOIN users u ON e.user_id=u.id WHERE e.email=?', (email,)).fetchone()
            encoded = account['password_hash'] if account else '0' * 32 + ':' + '0' * 64
            if not matches(password, encoded) or not account:
                raise HTTPException(401, 'invalid_credentials')
            name = account['name']
            activation_hash = account['activation_hash']
            if activation_hash:
                if action != 'activate':
                    raise HTTPException(409, 'activation_required')
                code = payload.get('activation_code')
                if not isinstance(code, str) or len(code) > 128 or not hmac.compare_digest(hashed(code.strip()), activation_hash):
                    raise HTTPException(401, 'invalid_activation')
                new_password = valid_password(payload.get('new_password'), new=True)
                updated = password_hash(new_password)
                with store.connect() as db:
                    if db.execute('UPDATE email_accounts SET password_hash=?,activation_hash=NULL '
                                  'WHERE email=? AND activation_hash=? RETURNING email',
                                  (updated, email, activation_hash)).fetchone() is None:
                        raise HTTPException(409, 'activation_used')
            elif action == 'activate':
                raise HTTPException(409, 'activation_used')
        return set_session_cookie(JSONResponse({'ok': True}), store.create_session('email', email, name))

    def bounded(action, payload):
        if not PASSWORD_WORKERS.acquire(blocking=False):
            raise HTTPException(429, 'email_auth_rate_limited')
        try:
            return perform(action, payload)
        finally:
            PASSWORD_WORKERS.release()

    @router.post('/api/auth/email/{action}')
    async def email_auth(action: str, request: Request):
        if action not in ('register', 'login', 'activate', 'reset'):
            raise HTTPException(404, 'unknown_email_auth_action')
        check_origin(request)
        client_ip = client_address(request)
        if not limiter.allow(client_ip):
            raise HTTPException(429, 'email_auth_rate_limited')
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                raise HTTPException(413, 'request_size_limit')
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'invalid_json') from None
        if not isinstance(payload, dict):
            raise HTTPException(400, 'invalid_json')
        return await run_in_threadpool(bounded, action, payload)

    recovery_limiter = AuthStartRateLimiter(5, 60)

    @router.post('/api/auth/recovery-code')
    async def recovery_code(request: Request):
        check_origin(request)
        user = authenticated(request)
        if user['role'] != 'dean':
            raise HTTPException(403, 'role_required')
        client_ip = client_address(request)
        if not recovery_limiter.allow(client_ip):
            raise HTTPException(429, 'email_auth_rate_limited')
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                raise HTTPException(413, 'request_size_limit')
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'invalid_json') from None
        if not isinstance(payload, dict):
            raise HTTPException(400, 'invalid_json')
        email = normalized_email(payload.get('email'))
        code = await run_in_threadpool(issue_password_reset, store, email)
        if code is None:
            raise HTTPException(404, 'email_account_not_found')
        return JSONResponse({'email': email, 'code': code, 'expires_in': 1800},
                            headers={'Cache-Control': 'private, no-store'})
