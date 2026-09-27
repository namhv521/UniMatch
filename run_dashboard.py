"""Run the local-only dashboard; incomplete data needs explicit smoke mode."""
import argparse
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    if args.allow_partial:
        os.environ['KLTN_ALLOW_PARTIAL'] = '1'
    import uvicorn
    uvicorn.run('backend.app.main:app', host='127.0.0.1', port=args.port)
