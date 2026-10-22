"""Local SQLite candidate sandbox. Never connects to or authorizes production."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


COMPATIBILITY_KEYS = ('state_contract','taxonomy_feature_order_sha256','feature_contract_sha256',
                      'quota_policy_version','reward_weights')


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def content_sha256(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _file_sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def _read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _checkpoint_files(directory):
    directory=Path(directory).resolve()
    if not directory.is_dir(): raise ValueError('checkpoint_directory_required')
    files={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink(): raise ValueError('checkpoint_links_forbidden')
        if path.is_file():
            if not path.resolve().is_relative_to(directory): raise ValueError('checkpoint_path_escape')
            files[path.relative_to(directory).as_posix()]=_file_sha(path)
    if 'metadata.json' not in files: raise ValueError('checkpoint_metadata_required')
    metadata=_read(directory/'metadata.json')
    if not isinstance(metadata.get('contract'),dict): raise ValueError('checkpoint_contract_required')
    if 'checksums.json' in files:
        native=_read(directory/'checksums.json')
        if not isinstance(native,dict) or not native: raise ValueError('checkpoint_checksums_invalid')
        for name,expected in native.items():
            if name not in files or files[name]!=expected: raise ValueError('checkpoint_native_hash_mismatch')
    elif 'state_sha256' in metadata:
        if files.get('state.pt')!=metadata['state_sha256']: raise ValueError('checkpoint_native_hash_mismatch')
        declared=metadata.get('manifest_sha256')
        if declared!=content_sha256({k:v for k,v in metadata.items() if k!='manifest_sha256'}):
            raise ValueError('checkpoint_metadata_hash_mismatch')
    else: raise ValueError('checkpoint_native_checksums_required')
    return files,metadata


def checkpoint_digest(directory):
    """Bind checkpoint bytes, including native JSON checksums, without loading code."""
    return content_sha256(_checkpoint_files(directory)[0])


class CandidateRegistry:
    def __init__(self,sqlite_path,*,compatible_contract,scope='research_sandbox'):
        if scope not in {'research_sandbox','technical_drill'}: raise ValueError('sandbox_scope_required')
        if not isinstance(compatible_contract,dict) or any(k not in compatible_contract for k in COMPATIBILITY_KEYS):
            raise ValueError('compatible_contract_required')
        self.path=Path(sqlite_path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.compatible_contract=json.loads(_json(compatible_contract));self.scope=scope
        with self._transaction() as db:
            db.executescript('''
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidates(candidate_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals(candidate_id TEXT NOT NULL,receipt_sha TEXT NOT NULL,action TEXT NOT NULL,
                    receipt TEXT NOT NULL,PRIMARY KEY(candidate_id,receipt_sha,action));
                CREATE TABLE IF NOT EXISTS active(id INTEGER PRIMARY KEY CHECK(id=1),candidate_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assignment_batches(batch_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit(event_id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_batches_update BEFORE UPDATE ON assignment_batches
                    BEGIN SELECT RAISE(ABORT,'immutable_assignment_batch'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_batches_delete BEFORE DELETE ON assignment_batches
                    BEGIN SELECT RAISE(ABORT,'immutable_assignment_batch'); END;
            ''')
            expected=_json({'scope':scope,'compatible_contract':self.compatible_contract})
            old=db.execute('SELECT payload FROM settings WHERE id=1').fetchone()
            if old and old[0]!=expected: raise ValueError('registry_scope_or_compatible_contract_mismatch')
            db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(expected,))

    @contextmanager
    def _transaction(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        try:
            db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
            yield db
            if db.in_transaction: db.commit()
        except BaseException:
            if db.in_transaction: db.rollback()
            raise
        finally: db.close()

    def _compatible(self,contract):
        if any(contract.get(k)!=self.compatible_contract[k] for k in COMPATIBILITY_KEYS):
            raise ValueError('incompatible_candidate_contract')

    def _gate(self,paths,hashes,checkpoint_sha,contract_sha):
        if not {'gate','evaluation'}<=set(paths): raise ValueError('evaluation_gate_and_report_required')
        gate=_read(paths['gate'])
        if (gate.get('status')!='verified' or gate.get('can_promote_candidate') is not True
                or gate.get('scope')!=self.scope
                or gate.get('checks',{}).get('safety_passed') is not True
                or gate.get('checks',{}).get('frozen_evaluation_passed') is not True
                or any(value is not True for value in gate.get('checks',{}).values())
                or gate.get('checkpoint_sha256')!=checkpoint_sha or gate.get('contract_sha256')!=contract_sha
                or gate.get('frozen_evaluation_sha256')!=hashes['evaluation']):
            raise ValueError('evaluation_gate_not_verified_or_bound')

    def _event(self,db,action,payload):
        db.execute('INSERT INTO audit(action,payload) VALUES(?,?)',(action,_json({**payload,
            'scope':self.scope,'operational_authorization':False,'production':False,
            'recorded_at':datetime.now(timezone.utc).isoformat()})))

    def _candidate(self,db,key):
        row=db.execute('SELECT payload FROM candidates WHERE candidate_id=?',(key,)).fetchone()
        if not row: raise ValueError('unknown_candidate')
        return json.loads(row[0])

    def _verify(self,item):
        self._compatible(item['contract'])
        if (item.get('scope')!=self.scope or item.get('operational_authorization') is not False
                or item.get('production') is not False or item['contract_sha256']!=content_sha256(item['contract'])):
            raise ValueError('candidate_scope_or_contract_modified')
        files,metadata=_checkpoint_files(item['checkpoint_dir'])
        if (files!=item['checkpoint_files'] or metadata['contract']!=item['contract']
                or content_sha256(files)!=item['checkpoint_sha256']): raise ValueError('checkpoint_modified')
        if any(_file_sha(path)!=item['evaluation_sha256'][name] for name,path in item['evaluation_paths'].items()):
            raise ValueError('evaluation_report_modified')
        self._gate(item['evaluation_paths'],item['evaluation_sha256'],item['checkpoint_sha256'],item['contract_sha256'])
        identity={k:item[k] for k in ('contract','checkpoint_files','evaluation_sha256')}
        if content_sha256(identity)!=item['candidate_id']: raise ValueError('candidate_identity_modified')

    def register(self,checkpoint_dir,contract,evaluation_reports):
        self._compatible(contract)
        if not isinstance(evaluation_reports,dict) or not {'gate','evaluation'}<=set(evaluation_reports):
            raise ValueError('evaluation_gate_and_report_required')
        files,metadata=_checkpoint_files(checkpoint_dir)
        if metadata['contract']!=contract: raise ValueError('checkpoint_contract_mismatch')
        paths={name:str(Path(path).resolve()) for name,path in evaluation_reports.items()}
        hashes={name:_file_sha(path) for name,path in paths.items()}
        csha=content_sha256(contract);checkpoint_sha=content_sha256(files)
        self._gate(paths,hashes,checkpoint_sha,csha)
        identity={'contract':contract,'checkpoint_files':files,'evaluation_sha256':hashes}
        key=content_sha256(identity)
        item={**identity,'candidate_id':key,'checkpoint_dir':str(Path(checkpoint_dir).resolve()),
              'checkpoint_sha256':checkpoint_sha,'contract_sha256':csha,'evaluation_paths':paths,
              'scope':self.scope,'operational_authorization':False,'production':False}
        with self._transaction() as db:
            row=db.execute('SELECT payload FROM candidates WHERE candidate_id=?',(key,)).fetchone()
            if row: self._verify(json.loads(row[0]));return key
            self._verify(item)
            db.execute('INSERT INTO candidates VALUES(?,?)',(key,_json(item)))
            self._event(db,'register',{'candidate_id':key})
        return key

    def get_candidate(self,key):
        with self._transaction() as db: return self._candidate(db,key)

    def _authority(self,receipt,kind):
        if (not isinstance(receipt,dict) or receipt.get('kind')!=kind or receipt.get('decision')!='approve'
                or receipt.get('scope')!=self.scope or not str(receipt.get('approval_quote','')).strip()):
            raise ValueError('explicit_authority_receipt_required')
        if self.scope=='technical_drill':
            valid=receipt.get('authorization_source')=='automated_test_fixture' and receipt.get('reviewer')=='phase6-drill'
        else:
            valid=receipt.get('authorization_source')=='explicit_user_message' and str(receipt.get('reviewer','')).startswith('owner:')
        if not valid: raise ValueError('invalid_receipt_authority_for_scope')

    def _bound_receipt(self,item,receipt,kind):
        self._authority(receipt,kind)
        if (receipt.get('candidate_id')!=item['candidate_id'] or receipt.get('contract_sha256')!=item['contract_sha256']
                or receipt.get('evaluation_sha256')!=item['evaluation_sha256']):
            raise ValueError('approval_receipt_binding_mismatch')

    def _stored_approval(self,db,item,*,promotion_only=False):
        query='SELECT receipt_sha,action,receipt FROM approvals WHERE candidate_id=?'
        if promotion_only: query+=" AND action='promote'"
        row=db.execute(query+' ORDER BY rowid DESC LIMIT 1',(item['candidate_id'],)).fetchone()
        if not row: raise ValueError('rollback_requires_prior_approval' if promotion_only else 'active_candidate_has_no_approval')
        receipt=json.loads(row[2])
        if content_sha256(receipt)!=row[0]: raise ValueError('stored_approval_hash_mismatch')
        self._bound_receipt(item,receipt,'sandbox_candidate_rollback' if row[1]=='rollback' else 'sandbox_candidate_promotion')

    def _select(self,key,receipt,rollback):
        kind='sandbox_candidate_rollback' if rollback else 'sandbox_candidate_promotion'
        self._authority(receipt,kind)
        with self._transaction() as db:
            item=self._candidate(db,key);self._verify(item)
            self._bound_receipt(item,receipt,kind)
            if rollback: self._stored_approval(db,item,promotion_only=True)
            prior=db.execute('SELECT candidate_id FROM active WHERE id=1').fetchone()
            receipt_sha=content_sha256(receipt);action='rollback' if rollback else 'promote'
            db.execute('INSERT OR IGNORE INTO approvals VALUES(?,?,?,?)',(key,receipt_sha,action,_json(receipt)))
            db.execute('INSERT INTO active VALUES(1,?) ON CONFLICT(id) DO UPDATE SET candidate_id=excluded.candidate_id',(key,))
            self._event(db,action,{'candidate_id':key,'previous_candidate_id':prior[0] if prior else None,'receipt_sha256':receipt_sha})
            return item

    def promote(self,candidate_id,receipt): return self._select(candidate_id,receipt,False)

    def rollback(self,candidate_id,receipt): return self._select(candidate_id,receipt,True)

    def active(self):
        with self._transaction() as db:
            row=db.execute('SELECT candidate_id FROM active WHERE id=1').fetchone()
            if not row: return None
            item=self._candidate(db,row[0]);self._verify(item)
            self._stored_approval(db,item)
            return item

    def record_assignments(self,batch_id,assignments,*,source,owner_receipt):
        if (not isinstance(batch_id,str) or not batch_id.strip() or not isinstance(assignments,list) or not assignments
                or not isinstance(source,dict) or not source): raise ValueError('invalid_assignment_batch')
        students=[]
        for row in assignments:
            if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('student_id','advisor_id')):
                raise ValueError('invalid_assignment_rows')
            students.append(row['student_id'])
        if len(set(students))!=len(students): raise ValueError('duplicate_assignment_student')
        body={'batch_id':batch_id,'assignments':assignments,'source':source};digest=content_sha256(body)
        with self._transaction() as db:
            previous=db.execute('SELECT payload FROM assignment_batches WHERE batch_id=?',(batch_id,)).fetchone()
            if previous:
                item=json.loads(previous[0])
                self._validate_batch(item)
                if item['batch_sha256']!=digest or item['owner_receipt']!=owner_receipt: raise ValueError('immutable_assignment_batch')
                return item
            self._authority(owner_receipt,'sandbox_assignment_approval')
            if owner_receipt.get('batch_sha256')!=digest or owner_receipt.get('source_sha256')!=content_sha256(source):
                raise ValueError('assignment_receipt_binding_mismatch')
            item={**body,'batch_sha256':digest,'owner_receipt':owner_receipt,'owner_receipt_sha256':content_sha256(owner_receipt),
                  'scope':self.scope,'operational_authorization':False,'production':False}
            db.execute('INSERT INTO assignment_batches VALUES(?,?)',(batch_id,_json(item)))
            self._event(db,'approve_assignments',{'batch_id':batch_id,'batch_sha256':digest})
            return item

    def get_assignments(self,batch_id):
        with self._transaction() as db:
            row=db.execute('SELECT payload FROM assignment_batches WHERE batch_id=?',(batch_id,)).fetchone()
            if not row: raise ValueError('unknown_assignment_batch')
            item=json.loads(row[0])
            self._validate_batch(item)
            return item

    def _validate_batch(self,item):
        body={k:item[k] for k in ('batch_id','assignments','source')}
        if (content_sha256(body)!=item['batch_sha256'] or content_sha256(item['owner_receipt'])!=item['owner_receipt_sha256']
                or item['owner_receipt'].get('batch_sha256')!=item['batch_sha256']
                or item['owner_receipt'].get('source_sha256')!=content_sha256(item['source'])
                or item.get('scope')!=self.scope or item.get('operational_authorization') is not False
                or item.get('production') is not False): raise ValueError('assignment_batch_hash_mismatch')
        self._authority(item['owner_receipt'],'sandbox_assignment_approval')

    def audit(self):
        with self._transaction() as db:
            return [{'event_id':i,'action':a,**json.loads(p)} for i,a,p in db.execute('SELECT event_id,action,payload FROM audit ORDER BY event_id')]
