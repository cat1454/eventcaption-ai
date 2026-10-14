# Ràng buộc nghiệm thu model và bàn giao

Nguồn quy định: [architecture](../reference/architecture.md), [evaluation](../reference/evaluation.md), [handoff](../reference/handoff.md), [schema event-caption/1](../../src/eventcaption_ai/contracts/event-caption-v1.schema.json).

## Contract và tính đúng theo thời gian

- Chỉ mô tả khoảng sự kiện đã quan sát, không dự báo. Mỗi output chỉ dùng frame/evidence không vượt source cutoff; không truyền toàn video cho model.
- EMIT tạo event/version mới; REVISE/WITHDRAW tham chiếu current previous-record ID, cùng event và tăng version. WAIT chỉ ghi trace, không phát caption.
- Giữ ledger append-only và replay/gap checking. Withdrawal giữ interval/status trước đó và lý do; không xóa lịch sử. Evidence ID không đổi timestamp.
- Event đang diễn ra có end_ms=null; khi kết thúc, start_ms <= end_ms <= cutoff. Hoàn tất/che khuất không phải lý do độc lập để withdraw.
- Không bịa commit probabilities, sửa keyword hoặc repair output để chứng nhận semantic correctness.

## Chất lượng nghiên cứu

| Tiêu chí | Mức yêu cầu |
|---|---|
| Unsupported-caption rate | Giảm tương đối >=20% so với periodic baseline tương ứng |
| Event coverage | >=80% và giảm không quá 5 điểm phần trăm so với baseline |
| iPhone 16 Pro p95 first-correct-display | <=5.000 ms tính từ đủ bằng chứng |

- Khóa rubric ngữ nghĩa, event matching, time tolerance, split và quy trình chọn model trước main experiments. Chọn trên dev, đóng băng rồi mở final test một lần.
- Tính mọi phiên bản caption đã công bố; sửa đúng sau đó không xóa lỗi trước. Báo missing events riêng; latency trên sự kiện có caption không chứng minh coverage.
- Baseline error bằng 0 làm relative reduction không xác định; không báo đạt 20% theo phép chia không hợp lệ.
- Báo duplicate, revision đúng/sai, withdrawal không có căn cứ, interval accuracy và bất định clustered theo video/source. Giữ phán xét từng reviewer và adjudication.
- Numerical accepted từ calculator chỉ xác nhận ngưỡng trên đầu vào cung cấp. Test/mock/fixture hoặc JSON đúng không chứng nhận chất lượng model.

## Feasibility và nghiệm thu thiết bị

- Trước main training, cùng nhóm iOS kiểm tra size/runtime, preprocessing, tokenizer/template, frame ordering/timestamp, context bounds và B layer/token pooling/shape/dtype/value parity.
- Ghi device/iOS, Mac/Xcode, runtime, checkpoint revision, processor và quantization. Không tuyên bố export/parity đã đạt nếu chưa có đo thực.
- Nghiệm thu cần video replay và camera run ít nhất 10 phút. Log capture/arrival, sufficient evidence, enqueue/inference completion, record ID, render time, memory, thermal và errors; thiết lập mapping clock nguồn sang display.
- Đo first-correct-display thực tế. Generation latency, desktop timing và Python consumer không thay thế ứng dụng trên iPhone.
- AI bàn giao model/adapter, cấu hình/revision, preprocessing/memory, contract, reference inference và kết quả có provenance. Nhóm ứng dụng sở hữu camera/rendering/runtime; repo này không thêm UI.
- Nếu chất lượng hoặc thiết bị không đạt, báo rõ chưa hoàn thiện theo mục tiêu. Không tự hạ chuẩn, chọn lại bằng final test hay thay on-device bằng server.
