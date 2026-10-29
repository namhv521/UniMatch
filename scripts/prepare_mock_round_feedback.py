"""Create isolated, explicitly simulated feedback bound to existing train cohorts."""
import argparse
import copy
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_four_round_research import read, write, VERSIONS
from src.rl.nested_learning import decode_problem
from src.evaluation.rebuild_benchmark import problem_payload
from src.data_pipeline.review_decisions import record_hash


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_mock(suites, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('new_mock_namespace_required')
    for version in VERSIONS:
        data = copy.deepcopy(read(Path(suites) / version / 'suite.json'))
        for index, kind in ((2, 'student_preference'), (3, 'advisor_feedback')):
            changes = []
            for p in data['train']:
                if index == 2:
                    for i, student in enumerate(p['student_ids']):
                        candidates = [j for j in range(len(p['advisor_ids']))
                                      if p['eligible'][i][j] and p['available'][i][j]
                                      and p['present'][j] and p['capacities'][j] > 0]
                        if not candidates:
                            continue
                        # Deliberately correlated mock, not an independent human
                        # preference label or evidence for real-world improvement.
                        j = max(candidates, key=lambda j: p['scores'][i][j])
                        for field, new in (('preferences', .8), ('preference_known', True)):
                            old = p[field][i][j]
                            if old != new:
                                changes.append(dict(student_id=student, advisor_id=p['advisor_ids'][j],
                                                    field=field, old=old, new=new))
                                p[field][i][j] = new
                else:
                    # One extra seat for a currently present advisor per cohort.
                    j = next(j for j in range(len(p['advisor_ids']))
                             if p['present'][j] and p['capacities'][j] > 0)
                    old = p['capacities'][j]
                    changes.append(dict(student_id=min(p['student_ids']), advisor_id=p['advisor_ids'][j],
                                        field='capacities', old=old, new=old + 1))
                    p['capacities'][j] += 1
            signal_id = f'MOCK-{version}-R{index}'
            source = output / version / f'R{index}-source.json'
            write(source, {'scope': 'simulated_feedback_not_human', 'signal_id': signal_id,
                           'available_at_is_simulated': True, 'changes': changes})
            spec = data['round']
            spec['signals'].append({'signal_id': signal_id, 'type': kind, 'source_path': str(source),
                'source_sha256': digest(source), 'available_at': spec['cutoff_timestamp'],
                'review_status': 'verified', 'provenance': 'simulated_not_human'})
            snapshot = read(spec['snapshot_path'])
            snapshot.update(training_problem_sha256=[record_hash(problem_payload(decode_problem(p))) for p in data['train']],
                            validation_problem_sha256=record_hash(problem_payload(decode_problem(data['validation']))),
                            signal_ids=[s['signal_id'] for s in spec['signals']],
                            applied_signal_source_sha256={signal_id: digest(source)})
            path = output / version / f'R{index}-snapshot.json'
            write(path, snapshot)
            spec.update(snapshot_path=str(path), snapshot_sha256=digest(path), round_index=index,
                        signal_state_sha256=record_hash([s['signal_id'] for s in spec['signals']]))
            data['experiment_scope'] = 'simulated_feedback_not_human'
            write(output / version / f'R{index}.json', data)
    write(output / 'manifest.json', {'scope': 'simulated_feedback_not_human',
        'generator': 'top_similarity_preference_0.8_and_one_extra_advisor_seat',
        'training_only': True, 'holdouts_modified': False, 'versions': list(VERSIONS)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suites', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare_mock(args.suites, args.output)
