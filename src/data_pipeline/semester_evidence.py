"""Locate semester candidates; publication years and folder names are not labels."""
import re


TERM=re.compile(r'(?<![\d.])20(?:2[0-9])\.[123](?![\d.])')
CONTEXT=re.compile(r'(?:học\s*k[ỳì]|hoc\s*ky|semester|mã\s*(?:lớp|học\s*phần)|năm\s*học)',re.IGNORECASE)


def term_evidence(text):
    evidence=[]
    for match in TERM.finditer(text):
        start=max(0,match.start()-100)
        context=text[start:match.start()]
        # A dot-separated number in a citation/version is not an academic code.
        if not CONTEXT.search(context):
            continue
        evidence.append({'candidate_term':match.group(),'start':match.start(),'end':match.end(),
                         'quote':text[match.start():match.end()],
                         'context_start':start,'context':text[start:min(len(text),match.end()+50)]})
    terms=sorted({r['candidate_term'] for r in evidence})
    return {'candidate_terms':terms,'evidence':evidence,
            'status':'ambiguous' if len(terms)>1 else ('candidate' if terms else 'unknown'),
            'review_status':'pending','approved_semester_id':None,
            'limitation':'Academic code is source evidence only; requires record-level review and prediction-time availability.'}
