# Ràng buộc hoàn thiện model

Bộ tài liệu cho agent và nhóm AI. Chỉ áp dụng phần dữ liệu, model, reference inference, đánh giá và bàn giao AI; không mở rộng sang backend/frontend/UI. Caption đầu ra bằng tiếng Anh. Forecasting và suy luận nhân quả qua can thiệp nằm ngoài nghiệm thu.

## Đọc theo công việc

**Xem tiến độ tại [Lộ trình S0–S7](stages.md): ưu tiên demo policy đã học trên PC ở S3, sau đó hoàn thiện nghiên cứu và iPhone.** Mỗi stage có checklist, bằng chứng, blocker và bước tiếp theo.

Đọc [plan](../plan.md) và [status](../status.md) trước theo [AGENTS.md](../../AGENTS.md). Sau đó chọn tài liệu tương ứng; không nạp cả bộ vào mọi tác vụ.

| Công việc | Tài liệu bắt buộc cho bước đó |
|---|---|
| Xem stage hiện tại và mốc demo tiếp theo | [stages](stages.md) |
| Cách làm việc, giảm đọc lặp, bàn giao | [agent-workflow](agent-workflow.md) |
| Tuyển nguồn, chia split, prefix, nhãn | [data-gates](data-gates.md) |
| Pilot tài nguyên, recipe, training/resume, dev inference | [training-gates](training-gates.md) |
| Contract, đánh giá cuối, bàn giao thiết bị | [acceptance](acceptance.md) |
| Xác định blocker và ghi nhận tiến độ | [progress-checklist](progress-checklist.md) |

## Cách sử dụng ràng buộc

- Tài liệu này diễn giải yêu cầu hiện có; không tự mở gate, thay đổi schema hoặc cấp quyền chạy thí nghiệm.
- Quy tắc nghiên cứu nằm ở tài liệu chuyên môn được liên kết. Quyết định cập nhật trong status chỉ thay thế đúng phạm vi được nêu; không dùng một PASS để suy ra mọi bước đã PASS.
- Nếu có mâu thuẫn thực sự chưa được giải quyết, chỉ giữ bước phụ thuộc ở trạng thái chờ và nêu rõ hai nguồn. Tiếp tục phần độc lập đã được phép.
- Không biến quá trình hoàn thiện thành vòng sửa báo cáo vô hạn: dùng bằng chứng đã chấp nhận nếu đầu vào/phạm vi không đổi. Không thêm yêu cầu hội đồng hay chữ ký học thuật ngoài quy trình hiện có.

## Trình tự hoàn thiện

1. Chốt nguồn/split, protocol, cách ly và nhãn được con người chấp nhận.
2. Đối soát ngân sách; thực hiện feasibility dữ liệu/tài nguyên/thiết bị trong gate tương ứng.
3. Chọn kích thước SmolVLM2 trên dev và khả năng thiết bị; khóa recipe, rubric và cách đánh giá trước main training.
4. Huấn luyện, so sánh baseline/A/B và ablation trong ngân sách được phân bổ.
5. Chọn trên dev, đóng băng cấu hình rồi đánh giá final test một lần; đo thực tế trên iPhone 16 Pro.
6. Bàn giao artifact và báo cáo bằng chứng. Nếu mục tiêu không đạt, ghi không đạt.

Các bước chuẩn bị tài liệu có thể làm song song với việc chờ dữ liệu; điều này không cho phép dispatch prefix, nhận nhãn hay chạy model khi gate tương ứng chưa mở.
