"""Freeze advisory reviews and a source-bound Phase 4 owner evidence report."""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.reconcile import _digest
from src.evaluation.rebuild_ranking import ranking_metrics
from src.evaluation.rebuild_review import combine_advisory_reviews, map_advisory_labels
from src.features.rebuild_experiments import _load_snapshot, run_experiments
from src.features.rebuild_features import FeaturePipeline


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def prepare(output, packet, destination, primary_paths, crosscheck_paths):
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'inputs').mkdir()
    collections = []
    for paths in (primary_paths, crosscheck_paths):
        rows = []
        for path in paths:
            data = path.read_bytes()
            target = destination/'inputs'/path.name
            if target.exists():
                raise ValueError('duplicate_review_input_filename')
            target.write_bytes(data)
            rows += [json.loads(line) for line in data.decode('utf-8-sig').splitlines() if line.strip()]
        collections.append(rows)
    primary, crosschecks = collections
    # Verify both opinions against the actual source packet before combining.
    map_advisory_labels(packet, primary)
    check_index = {r['pair_id']: r for r in crosschecks}
    if len(check_index) != len(crosschecks):
        raise ValueError('duplicate_crosscheck_pair')
    if set(check_index)-{r['pair_id'] for r in primary}:
        raise ValueError('unknown_crosscheck_pair')
    map_advisory_labels(packet, [check_index.get(r['pair_id'], r) for r in primary])
    proposals, agreement = combine_advisory_reviews(primary, crosschecks)
    mapped = map_advisory_labels(packet, proposals)
    proposal_path = destination/'combined_proposals.jsonl'
    proposal_path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in proposals), encoding='utf-8')
    write_json(destination/'crosscheck_audit.json', agreement)
    gate = run_experiments(output, labels_file=proposal_path, review_packet=packet)
    run = Path(gate['run_dir'])
    read = lambda name: json.loads((run/name).read_text(encoding='utf-8'))
    metrics = read('reports/ranking_metrics.json')['metrics']
    labels = [json.loads(line) for line in (run/'review/labels.jsonl').read_text(encoding='utf-8').splitlines()]
    comparison = [name for name in ('E0', 'E1', 'E4', 'E4_calibrated_proposal') if name in metrics]
    common = set.intersection(*[{s for s, q in metrics[name]['per_query'].items() if q['status']=='evaluated'} for name in comparison])
    common_metrics = {name: ranking_metrics({s: metrics[name]['per_query'][s]['ranked_top_k'] for s in sorted(common)}, labels)
                      for name in comparison}
    # Advisory choice on identical queries; ties prefer the simpler title baseline.
    selected = max(comparison, key=lambda name: (common_metrics[name]['ndcg_at_5'], common_metrics[name]['mrr_at_5'], -comparison.index(name))) if common else None
    calibration = read('reports/hybrid_calibration.json')
    students, advisors, snapshot = _load_snapshot(output)
    contract = {'status': 'proposal_pending_owner_approval', 'selected_proposal': selected,
                'selection_scope': 'Agent-advisory validation; common fully judged queries only.',
                'comparison_queries': sorted(common), 'comparison_metrics': common_metrics,
                'e4_calibrated_weights': calibration.get('weights'), 'source_snapshot': gate['phase3_snapshot'],
                'expected_full_matrix_shape': [len(students), len(advisors)], 'matrix_generated': False,
                'test_used_for_selection': False, 'owner_approval': None,
                'limitations': ['No confirmed semester chronology or future-term validation.',
                    'Agent opinions require owner/domain ratification.',
                    'No approved abstracts/publication summaries or confirmed preferences in this validation set.',
                    'Missing advisor features remain unavailable; no automatic eligibility or capacity inference.']}
    write_json(destination/'feature_selection_proposal.json', contract)
    student_index, advisor_index = {r['student_id']:r for r in students}, {r['advisor_id']:r for r in advisors}
    identities = sorted({str(r[k]) for r in students+advisors for k in ('student_id','student_name','advisor_id','advisor_name') if r.get(k)})
    pipe = FeaturePipeline.load(run/'transformer', known_identities=identities)
    calibrated_pipe = (FeaturePipeline.load(run/'transformer_calibrated_proposal', known_identities=identities)
                       if (run/'transformer_calibrated_proposal').exists() else None)
    pairs = {r['pair_id']:r for r in (json.loads(line) for line in (packet/'blinded_pairs.jsonl').read_text(encoding='utf-8').splitlines())}
    bindings = json.loads((packet/'pair_bindings.json').read_text(encoding='utf-8'))
    explanations = []
    lines = ['# Phase 4 — Báo cáo bằng chứng chờ chủ sở hữu duyệt', '',
             f"Run: `{gate['run_id']}`. Snapshot P3: `{snapshot['snapshot_sha256']}`.", '',
             '**Chưa nghiệm thu P4. Toàn bộ nhãn dưới đây là đề xuất của agent, không phải kết quả hướng dẫn thực tế.**', '',
             f"Train/validation/test: 135/29/30; test chưa chấm điểm, chưa dùng chọn đặc trưng. Có {len(proposals)} cặp validation.", '',
             f"Kiểm tra chéo có hệ thống {agreement['sampled_pairs']} cặp; đồng ý tuyệt đối {agreement['exact_agreement']:.1%}; "
             f"{len(agreement['disputed_pairs'])} cặp bất đồng giữ uncertain, chờ người duyệt. Mẫu này không đại diện ngẫu nhiên cho toàn bộ dữ liệu.", '',
             f"Nhãn ban đầu: {dict(Counter(str(r['grade']) for r in primary))}. Sau kiểm tra chéo: {dict(Counter(str(r['grade']) for r in proposals))}.", '',
             '## So sánh đề xuất', '', '| Biến thể | NDCG@5 | MRR@5 | Số query đánh giá /29 |', '|---|---:|---:|---:|']
    fmt = lambda x: f'{x:.4f}' if x is not None else 'unknown'
    for name, value in metrics.items():
        lines.append(f"| {name} | {fmt(value['ndcg_at_5'])} | {fmt(value['mrr_at_5'])} | {value['evaluated_queries']}/29 |")
    lines += ['', 'Không so sánh trực tiếp các điểm trung bình trên tập query khác nhau. IDCG chỉ trên pool đã có nhãn; đây chưa phải đánh giá đầy đủ 35 giảng viên.', '',
              f"Đề xuất kỹ thuật: **{selected or 'chưa đủ bằng chứng'}** trên {len(common)} query chung của E0/E1/E4/E4 calibrated.",
              f"Trọng số E4 đề xuất từ validation: `{calibration.get('weights')}`.", '',
              '| Biến thể | NDCG@5 trên query chung | MRR@5 trên query chung |', '|---|---:|---:|']
    for name, value in common_metrics.items():
        lines.append(f"| {name} | {fmt(value['ndcg_at_5'])} | {fmt(value['mrr_at_5'])} |")
    lines += ['', '## Giới hạn và điều kiện nghiệm thu', '',
              'Chủ sở hữu cần duyệt nhãn/bất đồng và lựa chọn feature contract. Sau đó tạo ma trận đầy đủ 194×35, kèm mask, thứ tự index và SHA; kiểm tra gate trước khi P5. Không thay website hiện hành.', '',
              'Chỉ có tiêu đề đề tài trong tập validation; không tự điền abstract, công bố, trình độ, nguyện vọng, quota hoặc cam kết hướng dẫn.',
              'Confidence E3 là tỷ lệ chứng cứ hợp lệ, không phải trình độ. Chức danh hoặc tên không phải feature. Dữ liệu liên hệ đã loại khỏi text.',
              'Hungarian chỉ mô phỏng chẩn đoán trên catalog, không phải phân bổ học kỳ được xác nhận.', '',
              '## Toàn bộ nhận xét và nguồn', '',
              'Grade 3: phù hợp cụ thể; 2: lĩnh vực/phương pháp rõ; 1: liên quan rộng/giảng dạy; 0: bằng chứng khác chủ đề; uncertain: chưa kết luận. Không gán 0 vì thiếu nguồn.', '']
    for number, proposal in enumerate(proposals, 1):
        key = proposal['pair_id']; pair = pairs[key]; binding = bindings[key]
        student, advisor = student_index[binding['student_id']], advisor_index[binding['advisor_id']]
        explanation = pipe.explain_pair(student, advisor)
        if calibrated_pipe:
            explanation['E4_calibrated_proposal'] = calibrated_pipe.explain_pair(student, advisor)['E4']
        explanations.append({'pair_id':key, 'explanation':explanation})
        lines += [f"### {number:03d} — {key[:16]} — grade {proposal['grade']}", '',
                  f"Đề tài: {pair['student_title']}", '',
                  f"Nguồn SV: `{student['source_file']}`; trang `{student.get('source_page', '')}`; SHA `{pair['student_source_sha256']}`; evidence refs: `{student.get('skill_evidence_refs', '')}`.", '',
                  f"Nguồn GV: {pair['advisor_source_url']}; SHA `{pair['advisor_source_sha256']}`.", '',
                  'Profile đã duyệt: '+pair['advisor_profile'], '',
                  'Phân loại nguồn research/teaching: '+json.dumps(pair['advisor_profile_sections'], ensure_ascii=False), '',
                  'Trích SV: '+json.dumps(proposal.get('student_evidence', []), ensure_ascii=False), '',
                  'Trích GV: '+json.dumps(proposal.get('advisor_evidence', []), ensure_ascii=False), '',
                  f"Nhận xét ({proposal['reviewer']}): {proposal['reason']}", '']
        if 'crosscheck' in proposal:
            check = proposal['crosscheck']
            lines += [f"Kiểm tra chéo: grade ban đầu {check['primary_grade']}; grade độc lập {check['independent']['grade']}; {check['independent']['reason']}", '']
        lines += ['Điểm thành phần (unknown được giữ trống): '+json.dumps({name:value['score'] for name,value in explanation.items()}, ensure_ascii=False), '']
    (destination/'owner_evidence_report.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(destination/'pair_explanations.json', explanations)
    write_json(destination/'manifest.json', {'status':'pending_owner_review', 'run_id':gate['run_id'],
        'run_manifest_sha256':_digest(run/'manifest.json'), 'packet_manifest_sha256':_digest(packet/'packet_manifest.json'),
        'script_sha256':_digest(Path(__file__)), 'created_at':datetime.now(timezone.utc).isoformat(),
        'artifacts':[{'path':p.relative_to(destination).as_posix(), 'sha256':_digest(p)} for p in sorted(destination.rglob('*')) if p.is_file()]})
    return {'run_id':gate['run_id'], 'bundle':str(destination), 'selection_proposal':selected,
            'common_queries':len(common), 'agreement':agreement, 'gate':gate['status']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--primary', action='append', type=Path, required=True)
    parser.add_argument('--crosscheck', action='append', type=Path, default=[])
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.packet, args.destination, args.primary, args.crosscheck), ensure_ascii=True))
