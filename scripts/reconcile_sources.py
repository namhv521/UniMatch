"""Stage reconciled records; gold release requires explicit bound review decisions."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.reconcile import stage_sources


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--semester-id', default='pilot-next-term',
                        help='Technical draft ID for the owner-defined next-semester pilot; not an official academic code/date.')
    parser.add_argument('--review-decisions', type=Path)
    parser.add_argument('--sample-reviews', type=Path)
    parser.add_argument('--taxonomy-approval', type=Path)
    parser.add_argument('--agent-proposals', type=Path)
    parser.add_argument('--owner-acceptance', type=Path)
    parser.add_argument('--quality-assessments', type=Path)
    parser.add_argument('--eligibility', type=Path)
    args = parser.parse_args()
    report = stage_sources(args.output, semester_id=args.semester_id, decisions_file=args.review_decisions,
                           sample_reviews_file=args.sample_reviews, taxonomy_approval_file=args.taxonomy_approval,
                           proposals_file=args.agent_proposals, owner_acceptance_file=args.owner_acceptance,
                           quality_assessments_file=args.quality_assessments, eligibility_file=args.eligibility)
    print(json.dumps(report, ensure_ascii=True))
    raise SystemExit(0 if report['status'] == 'verified' else 2)
