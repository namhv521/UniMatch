"""Start the local dashboard. Credentials must be set, or generated for local demo."""
import argparse
import os
import secrets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--local-demo', action='store_true')
    args = parser.parse_args()
    if args.host in ('127.0.0.1', 'localhost'):
        os.environ.setdefault('KLTN_COOKIE_SECURE', 'false')
    if args.local_demo:
        if args.host not in ('127.0.0.1', 'localhost'):
            parser.error('local demo binds to loopback only')
        os.environ.setdefault('KLTN_LOGIN_EMAIL', 'local@kltn.test')
        if not os.environ.get('KLTN_LOGIN_PASSWORD'):
            os.environ['KLTN_LOGIN_PASSWORD'] = secrets.token_urlsafe(18)
            print('Temporary local password:', os.environ['KLTN_LOGIN_PASSWORD'], flush=True)
        print('Local login:', os.environ['KLTN_LOGIN_EMAIL'], flush=True)
    if not os.environ.get('KLTN_LOGIN_EMAIL') or not os.environ.get('KLTN_LOGIN_PASSWORD'):
        parser.error('Set KLTN_LOGIN_EMAIL and KLTN_LOGIN_PASSWORD, or use --local-demo')
    import uvicorn
    uvicorn.run('backend.app.main:app', host=args.host, port=args.port, log_level='warning', access_log=False)


if __name__ == '__main__':
    main()
