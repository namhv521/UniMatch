# UniMatch — Vận hành Phase 3

Phase 3 tạo snapshot nguồn đã duyệt. Các lệnh không thay DB hoặc website đang triển khai. Tất cả raw, staging, gold và review có PII nằm trong `data_rebuild/v1/`, được gitignore.

## Chuẩn bị và staging

Từ repository, cài runtime riêng trong môi trường Python của dự án nếu chưa có: `python -m pip install -r requirements-rebuild.txt`. Kiểm tra gate Phase 1/2 trước; công cụ tự từ chối predecessor artifact bị thay đổi. Không dùng lại dữ liệu 215 hồ sơ làm chuẩn.

```powershell
python scripts/reconcile_sources.py --semester-id pilot-next-term
python -m pytest tests/rebuild -q
```

Khi chưa có approval, CLI trả gate `blocked`; đây là kết quả dự kiến. `pilot-next-term` chỉ là ID draft hiện tại. Học kỳ thật cần ID do coordinator đặt, không được suy ra từ ngày chạy hay luận văn cũ.

## Review và phê duyệt

1. Rà toàn bộ hồ sơ và evidence; giữ hash record/source, phân biệt đúng trường với chỉ có chuỗi trùng trong tài liệu. Quarantine mâu thuẫn và nguồn không đủ rõ.
2. Đề xuất sửa dùng `needs_review`; chỉ sử dụng canonical evidence. Replay bằng `--agent-proposals`, giữ raw và run trước nguyên vẹn.
3. Gói bằng chứng cho owner được khóa hash. Phê duyệt phải có thật và được ghi nhận cùng nguyên văn, reviewer, thời điểm, package manifest hash và phạm vi. Không chạy script để tự tạo một sự đồng ý chưa có.
4. Kiểm tra source/span/semantic cho từng tag trong CSV. Mẫu số là `(output_column, tag)` riêng biệt; giữ mọi occurrence/ref. Rubric đã được owner duyệt là passed/total. Trường hợp pending hoặc không tag có score null. Đây là chất lượng bằng chứng, không phải mastery/probability.
5. Mẫu extraction giữ snapshot giá trị parser trước sửa. Nhãn agent được owner chấp nhận phải ghi `owner_ratified_agent_report`, không đổi thành nhãn người dùng tự chấm. Thiếu kết luận ghi `uncertain`. Findings mới có thể HOLD record, không tự bổ sung phạm vi approval.

Hàm `finalize_rebuild_phase3.py` tiêu thụ receipt và assessments đã có; nó không cấp authority mới. Đợt hiện tại có thể tái tạo bằng:

```powershell
python scripts/finalize_rebuild_phase3.py `
  --authority data_rebuild/v1/review/phase3_acceptance/owner_acceptance.json `
  --eligibility data_rebuild/v1/review/phase3_acceptance/eligibility.jsonl `
  --quality data_rebuild/v1/review/phase3_acceptance/tag_verdicts.jsonl `
  --sample-advisory data_rebuild/v1/review/phase3_acceptance/pdf_sample_advisory.jsonl
```

Mỗi lần chạy tạo run mới, không ghi đè lịch sử. Receipt phải gắn với đúng gói đã được owner xem; dữ liệu/hash thay đổi thì approval cũ không còn đủ hiệu lực. Với nguồn hoặc taxonomy mới của học kỳ sau, tạo staging, review và receipt mới. Không sửa hash trong receipt để ép chạy tiếp.

## Kiểm tra và bàn giao

Đọc `reports/phase3_gate.json`: chỉ chuyển Phase 4 khi `status=verified`, `can_start_phase4=true`, không còn blocker. Gate trung tâm xác minh package, exact record hashes, canonical normalization/ref/span, quality score và quyết định theo eligibility; đường gọi trực tiếp cũng chịu cùng kiểm tra.

Đối soát các artifact trong chính thư mục `phase3_runs/<run_id>/` với `manifest.json`. CSV gold phải valid, approved và không trùng ID trong semester; mọi record chưa nhận phải có mặt trong staging/quarantine. Snapshot manifest lưu ID, nguồn Phase 1/2, hash config và nguyên byte input review. Downstream phải đọc immutable run này, không trộn file `latest` của các run khác nhau.

Hồ sơ giảng viên approved chỉ là profile đã rà nguồn. `active_for_semester`, eligibility, capacity, proficiency, preference và outcome chưa có chứng cứ vẫn thiếu. Chọn roster và chia quota cho một lần phân bổ là bước vận hành học kỳ riêng; không tự chọn giảng viên thay coordinator.

Kết quả đợt nghiệm thu và giới hạn accuracy nằm trong [báo cáo Phase 3](rebuild_phase3_quality_report.md).
