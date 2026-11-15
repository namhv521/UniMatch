"""Email account registration, activation and shared portal sessions."""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

EMAIL = re.compile(r'[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}')
PASSWORD_HASH = re.compile(r'[0-9a-f]{32}:[0-9a-f]{64}')
DIGEST = re.compile(r'[0-9a-f]{64}')
PASSWORD_WORKERS = threading.BoundedSemaphore(2)


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


def seed_accounts(store):
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
                    or (role == 'faculty') != bool(advisor_id and semester)):
                raise ValueError('invalid_email_account_seed')
            existing = db.execute('SELECT role,advisor_id,advisor_semester FROM email_accounts WHERE email=?',
                                  (email,)).fetchone()
            if existing:
                if (existing['role'], existing['advisor_id'], existing['advisor_semester']) != (role, advisor_id, semester):
                    raise ValueError('email_account_seed_role_conflict')
                continue
            insert_account(db, email, name, encoded, role=role, activation=activation, advisor_id=advisor_id,
                           advisor_semester=semester)


def install_email_auth(router, store, check_origin, set_session_cookie):
    from .portal import AuthStartRateLimiter, hashed
    limiter = AuthStartRateLimiter(12, 60)
    seed_accounts(store)

    def perform(action, payload):
        email = normalized_email(payload.get('email'))
        password = valid_password(payload.get('password'), new=action == 'register')
        if action == 'register':
            name = payload.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
                raise HTTPException(422, 'invalid_name')
            name = name.strip()
            encoded = password_hash(password)
            with store.connect() as db:
                if insert_account(db, email, name, encoded) is None:
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
        if action not in ('register', 'login', 'activate'):
            raise HTTPException(404, 'unknown_email_auth_action')
        check_origin(request)
        client_ip = request.client.host if request.client else 'unknown'
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
