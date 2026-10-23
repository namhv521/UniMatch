"""Bounded public GitHub snapshots; repository usage is never personal mastery."""
import ast
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse

import requests

from src.data_pipeline.normalization import normalize_mentions

MAX_BODY = 4 * 1024 * 1024
MAX_FILE = 512 * 1024
MAX_FILES_PER_REPO = 12
EXCLUDED = {'vendor', 'vendors', 'node_modules', 'third_party', 'third-party', 'venv', '.venv', 'dist', 'build'}
SCOPE = 'Public repository/topic evidence only; not authorship, personal proficiency, capacity or outcomes.'


def digest(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_source_path(path):
    if (not isinstance(path, str) or not path or '\\' in path or ':' in path or '\x00' in path
            or path.startswith('/') or any(p in ('', '.', '..') for p in path.split('/'))):
        raise ValueError('unsafe_source_path')
    return path


def public_fetch(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in {'api.github.com', 'raw.githubusercontent.com'}
            or parsed.username or parsed.password or parsed.port not in (None,443)):
        raise ValueError('public_github_url_required')
    with requests.get(url, timeout=(15, 45), stream=True, allow_redirects=False,
                      headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'UniMatch-source-audit/1.0'}) as response:
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total > MAX_BODY:
                raise ValueError('github_response_size_bound')
            chunks.append(chunk)
        return response.status_code, b''.join(chunks), dict(response.headers)


def enumerate_repos(username, fetch):
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})', username):
        raise ValueError('invalid_github_username')
    prefix = f'https://api.github.com/users/{username}/repos?'
    url = prefix+'per_page=100&page=1&type=owner&sort=full_name'
    repositories, seen, visited = [], set(), set()
    for _ in range(100):
        if url in visited or not url.startswith(prefix):
            raise ValueError('unsafe_or_cyclic_pagination')
        visited.add(url)
        status, body, headers = fetch(url)
        if status != 200:
            raise ValueError(f'repository_enumeration_failed_http_{status}')
        page = json.loads(body)
        if not isinstance(page, list):
            raise ValueError('repository_listing_not_list')
        for row in page:
            if row['id'] in seen:
                raise ValueError('duplicate_repository_listing')
            seen.add(row['id']); repositories.append(row)
        links = headers.get('Link', headers.get('link', ''))
        following = re.search(r'<([^>]+)>;\s*rel="next"', links)
        if not following:
            return sorted(repositories, key=lambda row: row.get('full_name', row.get('name', '')))
        url = following.group(1)
    raise ValueError('repository_pagination_bound')


def extract_mentions(text, *, kind, taxonomy, fork=False, template=False, path=''):
    if fork or template or any(part.lower() in EXCLUDED for part in PurePosixPath(path).parts):
        return []
    if not isinstance(text,str) or not text:
        return []
    regions = []
    if kind == 'code_import':
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return []
        lines = text.splitlines(keepends=True)
        starts = [0]
        for line in lines: starts.append(starts[-1]+len(line))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # AST columns are UTF-8 byte offsets, not Python character offsets.
                start = starts[node.lineno-1]+len(lines[node.lineno-1].encode()[:node.col_offset].decode())
                end = starts[node.end_lineno-1]+len(lines[node.end_lineno-1].encode()[:node.end_col_offset].decode())
                modules=[item.name for item in node.names] if isinstance(node,ast.Import) else [node.module or '']
                for module in modules:
                    root=module.split('.')[0]
                    match=re.search(r'(?<![\w.])'+re.escape(module)+r'(?![\w.])',text[start:end]) if root else None
                    if match:regions.append((start+match.start(),start+match.start()+len(root)))
    elif kind == 'dependency' and path.lower().endswith('package.json'):
        try: payload=json.loads(text)
        except ValueError:return []
        for section in ('dependencies','devDependencies','peerDependencies','optionalDependencies'):
            for package in payload.get(section,{}):
                for match in re.finditer(re.escape(json.dumps(package)),text):
                    regions.append((match.start()+1,match.end()-1))
    else:
        offset=0
        for line in text.splitlines(keepends=True):
            # URL/badge labels and source instructions are not evidence of repository use.
            if not re.search(r'ignore.*instruction|system prompt|developer message|claim expertise|!\[|<img|https?://|\b(?:not|never|without)\b|doesn.t',line,re.I):
                if kind=='dependency':
                    package=re.match(r'\s*([A-Za-z0-9_.-]+)(?:\s*(?:[<>=!~;\[\r\n]|$))',line)
                    if package:regions.append((offset+package.start(1),offset+package.end(1)))
                else:regions.append((offset,offset+len(line)))
            offset+=len(line)
    matches=[]
    for start,end in regions:
        for item in normalize_mentions(text[start:end],taxonomy):
            if kind in {'dependency','code_import'} and (item['start']!=0 or item['end']!=end-start):
                continue
            item={**item,'start':start+item['start'],'end':start+item['end']}
            item.pop('evidence_type',None)
            item['evidence_class']='documentation_mention' if kind=='readme' else kind
            matches.append(item)
    return matches


def write_run(output_root, payload, *, raw, run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('invalid_run_id')
    root=Path(output_root).resolve();root.mkdir(parents=True,exist_ok=True)
    run=root/run_id;run.mkdir()  # Never overwrite a previously captured run.
    (run/'raw').mkdir()
    for sha,body in raw.items():
        if not re.fullmatch('[a-f0-9]{64}',sha) or digest(body)!=sha:raise ValueError('raw_hash_mismatch')
        (run/'raw'/f'{sha}.bin').write_bytes(body)
    for key in ('sources','repositories','evidence'):
        (run/f'{key}.jsonl').write_bytes(b''.join(canonical(row)+b'\n' for row in payload[key]))
    for key in ('supplements','owner_receipt'):
        (run/f'{key}.json').write_bytes(canonical(payload[key]))
    artifacts={f.relative_to(run).as_posix():digest(f.read_bytes()) for f in run.rglob('*') if f.is_file()}
    manifest={'schema_version':'github-advisor-sources/1.0','run_id':run_id,'captured_at':utc_now(),
              'artifacts':artifacts,'quality':payload['quality'],'scope':SCOPE}
    (run/'manifest.json').write_bytes(canonical(manifest))
    return run


def verify_run(run):
    run=Path(run).resolve();manifest=json.loads((run/'manifest.json').read_bytes())
    expected=set(manifest['artifacts'])|{'manifest.json'}
    if {f.relative_to(run).as_posix() for f in run.rglob('*') if f.is_file()}!=expected:
        raise ValueError('artifact_inventory_hash_mismatch')
    for name,sha in manifest['artifacts'].items():
        safe_source_path(name);path=run/name
        if path.is_symlink() or not path.resolve().is_relative_to(run) or digest(path.read_bytes())!=sha:
            raise ValueError('artifact_hash_mismatch')
    return manifest


def crawl_accounts(output_root, mappings, *, taxonomy, owner_receipt, fetch=None):
    """Enumerate every public owned repo; sample bounded reviewed-purpose files, not whole codebases."""
    fetch=fetch or public_fetch
    sources,raw,repositories,evidence,failures=[],{},[],[],[]
    def capture(url,*,kind,commit_sha=None,path=None,acceptable=(200,)):
        try: status,body,headers=fetch(url)
        except (requests.RequestException,ValueError) as exc:
            status,body,headers=0,str(type(exc).__name__).encode(),{}
        sha=digest(body);raw[sha]=body
        record={'source_id':f'src_{len(sources):06d}','url':url,'sha256':sha,'retrieved_at':utc_now(),
                'http_status':status,'kind':kind,'commit_sha':commit_sha,'path':path,'size_bytes':len(body)}
        sources.append(record)
        if status not in acceptable:failures.append({'source_id':record['source_id'],'http_status':status})
        return status,body,headers,record
    def add_evidence(text,source,repo,kind,path='',locator=None):
        for mention in extract_mentions(text,kind=kind,taxonomy=taxonomy,fork=repo['fork'],
                                        template=repo.get('is_template',False),path=path):
            left=text.rfind('\n',0,mention['start'])+1;right=text.find('\n',mention['end'])
            right=len(text) if right<0 else right
            excerpt=text[left:right]
            # Retain an exact bounded source excerpt, not an invented translation/summary.
            if len(excerpt)>500: excerpt=text[mention['start']:mention['end']];left=mention['start'];right=mention['end']
            item={**mention,'source_id':source['source_id'],'source_sha256':source['sha256'],'source_url':source['url'],
                  'advisor_id':repo['advisor_id'],'github_username':repo['github_username'],'repository':repo['full_name'],
                  'commit_sha':repo.get('commit_sha'),'path':path,'locator':locator or f'{path}:chars:{mention["start"]}:{mention["end"]}',
                  'offset_basis':'decoded UTF-8-sig source text' if path else 'decoded repository-list JSON field value',
                  'excerpt':excerpt,'excerpt_start':left,'excerpt_end':right,'scope':SCOPE}
            item['evidence_id']=digest(canonical(item));evidence.append(item)
    complete=True
    for username,advisor_id in sorted(mappings.items()):
        page_sources=[]
        def listing(url):
            status,body,headers,source=capture(url,kind='repository_listing');page_sources.append(source)
            return status,body,headers
        try: repos=enumerate_repos(username,listing)
        except (ValueError,KeyError,TypeError):complete=False;continue
        for entry in repos:
            if (entry.get('private') or entry.get('owner',{}).get('login','').lower()!=username.lower()
                    or entry.get('full_name')!=username+'/'+entry['name']):
                complete=False;continue
            repo={'advisor_id':advisor_id,'github_username':username,'full_name':entry['full_name'],
                  'fork':entry.get('fork',False),'archived':entry.get('archived',False),
                  'is_template':entry.get('is_template',False),'listed_size_kb':entry.get('size'),
                  'default_branch':entry.get('default_branch'),'status':'pending','files':[],'scope':SCOPE}
            repositories.append(repo)
            listing_source=next(s for s in page_sources if any(r['id']==entry['id'] for r in json.loads(raw[s['sha256']])))
            repo['listing_source_id']=listing_source['source_id']
            # Fork/template ownership alone does not establish contribution: preserve but exclude.
            if repo['fork'] or repo['is_template']:
                repo['status']='excluded_fork_or_template_without_verified_contribution';continue
            url=f'https://github.com/{repo["full_name"]}.git'
            try:
                result=subprocess.run(['git','-c','credential.helper=','ls-remote',url,'HEAD'],capture_output=True,
                                      timeout=45,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'},check=False)
                body=result.stdout
                if result.returncode or len(body)>65536:raise ValueError('git_head_unavailable')
                sha=digest(body);raw[sha]=body
                head={'source_id':f'src_{len(sources):06d}','url':url,'sha256':sha,'retrieved_at':utc_now(),
                      'http_status':None,'transport_status':0,'kind':'git_ls_remote_HEAD','size_bytes':len(body)}
                sources.append(head);repo['head_source_id']=head['source_id']
                if not body.strip():repo['status']='empty_repository';continue
                commit=body.decode().split()[0]
                if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('invalid_commit_sha')
                repo['commit_sha']=commit
            except (subprocess.SubprocessError,ValueError,OSError):
                repo['status']='head_failed';failures.append({'repository':repo['full_name'],'reason':'head_failed'});continue
            status,body,_,source=capture(f'https://api.github.com/repos/{repo["full_name"]}/git/trees/{commit}?recursive=1',
                                        kind='repository_tree',commit_sha=commit)
            if status!=200:repo['status']='tree_failed';continue
            tree=json.loads(body)
            if tree.get('truncated'):
                repo['status']='tree_truncated';failures.append({'repository':repo['full_name'],'reason':'tree_truncated'});continue
            # Metadata is evidence at its actual JSON field, not a made-up HTTP response.
            for field in ('name','description','language'):
                if entry.get(field):add_evidence(entry[field],listing_source,repo,
                    'language' if field=='language' else 'repository_metadata',locator=f'repositories[id={entry["id"]}].{field}')
            candidates=[];excluded=0
            for node in tree.get('tree',[]):
                if node.get('type')!='blob':continue
                path=safe_source_path(node['path']);parts=PurePosixPath(path).parts;name=parts[-1].lower()
                if any(p.lower() in EXCLUDED for p in parts):excluded+=1;continue
                kind=('self_description' if entry['name'].lower()==username.lower() else 'readme') if name.startswith('readme') else (
                    'dependency' if name.startswith('requirements') and name.endswith('.txt') or name in {'pyproject.toml','package.json','environment.yml','setup.py'} else
                    'code_import' if name.endswith('.py') else None)
                if kind:candidates.append((0 if 'readme' in kind or kind=='self_description' else 1 if kind=='dependency' else 2,len(parts),path,kind,node.get('size',0)))
            candidates.sort();repo['eligible_file_count']=len(candidates);repo['excluded_vendor_files']=excluded
            repo['unfetched_due_file_bound']=max(0,len(candidates)-MAX_FILES_PER_REPO)
            for _,_,path,kind,size in candidates[:MAX_FILES_PER_REPO]:
                if size>MAX_FILE:
                    repo['files'].append({'path':path,'status':'excluded_size_bound','size_bytes':size});continue
                url=f'https://raw.githubusercontent.com/{repo["full_name"]}/{commit}/'+quote(path,safe='/')
                status,body,_,source=capture(url,kind=kind,commit_sha=commit,path=path)
                repo['files'].append({'path':path,'status':status,'source_id':source['source_id'],'sha256':source['sha256']})
                if status==200:
                    try:text=body.decode('utf-8-sig')
                    except UnicodeDecodeError:continue
                    add_evidence(text,source,repo,kind,path)
            repo['status']='captured_bounded_files'
    supplements=[]
    for username,advisor_id in sorted(mappings.items()):
        items=[e for e in evidence if e['advisor_id']==advisor_id]
        snippets=list(dict.fromkeys(e['excerpt'] for e in items))
        tags={}
        for e in items:tags.setdefault(e['group'],set()).add(e['tag'])
        supplements.append({'advisor_id':advisor_id,'github_username':username,'identity_mapping':'owner_confirmed',
            'owner_receipt_sha256':digest(canonical(owner_receipt)),
            'research_description':'\n'.join(snippets),'tags':{k:sorted(v) for k,v in sorted(tags.items())},
            'evidence_refs':[e['evidence_id'] for e in items],'scope':SCOPE,'personal_proficiency':None,
            'review_status':'source_evidence_pending_quality_review'})
    quality={'enumeration_complete':complete,'repositories':len(repositories),'download_failures':failures,
             'repository_statuses':{status:sum(r['status']==status for r in repositories) for status in sorted({r['status'] for r in repositories})},
             'file_collection_policy':f'At most {MAX_FILES_PER_REPO} README/dependency/Python-import files per attributable repo; not full code audit.',
             'source_bytes_complete':not failures,'scope':SCOPE,'taxonomy_sha256':digest(canonical(taxonomy)),
             'owner_receipt_sha256':digest(canonical(owner_receipt)),
             'crawler_code_sha256':digest(Path(__file__).read_bytes()),
             'unattributed_fork_evidence':0}
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+os.urandom(4).hex()
    return write_run(output_root,{'sources':sources,'repositories':repositories,'evidence':evidence,
        'supplements':{'schema_version':'github-advisor-supplements/1.0','advisors':supplements,'scope':SCOPE},
        'owner_receipt':owner_receipt,'quality':quality},raw=raw,run_id=run_id)
