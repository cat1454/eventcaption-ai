# Ràng buộc training và tài nguyên

Nguồn quy định và CLI: [plan](../plan.md), [training](../guides/training.md), [handoff](../reference/handoff.md). Không sao chép lệnh/config ví dụ rồi coi placeholder là recipe đã duyệt.

## Model và thiết kế nghiên cứu

- Họ SmolVLM2 đã chọn; kích thước chưa xác thực. Chọn bằng dev, pilot tài nguyên và khả năng iOS, không bằng final test.
- Giữ A: language-side LoRA học quyết định cùng caption/interval; B: captioner fine-tuned và decision head riêng. A có tooling không có nghĩa B hoặc chất lượng policy đã hoàn tất.
- Bắt đầu frozen vision encoder. Với trainer A hiện tại chỉ train LoRA A/B của các Linear được liệt kê chính xác dưới text_model; không tự mở vision/connector/embedding/lm_head hoặc full-weight training.
- Khóa revision, module targets, loss masking, hyperparameter và generation settings sau resource pilot, trước main training. Prompt/padding được mask; không silent truncation.
- Giữ baseline pretrained periodic, fine-tuned periodic, A/B và policy được chọn có/không memory. Ghép điều kiện captioner, input, generation và ngân sách để cô lập ảnh hưởng policy.
- Memory ban đầu 16 events / 16 KiB; bounded frame/context theo implementation. No-history vẫn khai báo active state tối thiểu để revise. Không cắt bằng chứng ngầm nhằm giảm token model.

## Gate trước khi chạy

| Pha | Bằng chứng bắt buộc |
|---|---|
| Pilot training A | Dữ liệu có quyền phù hợp, nhãn được chấp nhận, protocol/cách ly causal và ngân sách đối soát |
| Main training A | Toàn bộ pilot gate, iOS feasibility gồm B feature extraction/parity, recipe lock |
| Dev inference | Receipt dev riêng, dataset dev và quyền eval; tính ngân sách theo pilot/main của recipe |

Receipt phải bind đúng dataset hash, config hash và đường dẫn ledger đã đối soát; evidence có đường dẫn/hash thật. Receipt ghi quyết định, không tự chứng minh chất lượng hoặc xác thực người duyệt. Không tự đổi trạng thái gate khi chỉ mới tạo tài liệu.

## Ngân sách và bảo toàn run

- Một study ledger chung hoặc quota máy được phân bổ rõ: tổng 40 giờ; feasibility 4h, A 10h, B 10h, ablation 8h, final 4h, reserve 4h. Không coi còn đủ 40 giờ khi lịch sử chưa đối soát.
- Mỗi run tối đa 14.400 giây, gồm load/train/validation/inference. Dùng supervisor và reservation thật; reservation chưa đóng vẫn giữ chỗ. Không tự retry hoặc dùng nhiều ledger để tăng hạn mức.
- CLI training không tạo ledger mới. Real-model CPU invocation cũng dùng supervisor/ledger theo tooling hiện tại; synthetic unit tests là trường hợp riêng.
- Dùng checkpoint/revision đã cache; không tự tải model, fallback máy khác/server hoặc tiêu hết ngân sách còn lại. CI chỉ CPU/mock, không GPU/model download.
- Mỗi run và resume dùng đường dẫn chưa từng dùng; không ghi đè data/weights/results. Resume chỉ checkpoint hoàn chỉnh, cùng recipe và max_steps; recipe mới cần run được xem xét riêng.
- Giữ raw response, stdout/stderr, lỗi, loss append-only, checkpoint và định danh config/data/library. Không sửa JSON/keyword, giấu generation error hoặc chỉ giữ lần thành công.

## Kết luận hợp lệ

Dev compare hiện tại dùng accepted context kiểu teacher forcing. Action agreement, valid JSON hoặc loss giảm không thay thế autonomous sequential rollout và semantic review. Các metric chất lượng/display chưa đo phải để null/chưa đo, không tự bật quality_accepted.
