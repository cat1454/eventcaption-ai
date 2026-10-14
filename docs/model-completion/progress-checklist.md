# Checklist tiến độ và bằng chứng

Theo dõi công việc hiện hành tại **[bảng stage S0–S7](stages.md)**. File này giữ snapshot nền và mẫu ghi bằng chứng; không duy trì một bộ số đếm stage thứ hai. Khi có kết quả, cập nhật stage liên quan và thêm lịch sử vào status.

Snapshot khởi tạo: 14/10/2026, Asia/Bangkok, theo mục “Replacement recruitment intake checked” trong [status](../status.md). Đây là mốc tham chiếu, không phải trạng thái sống hoặc receipt phê duyệt. Đọc status mới hơn trước mỗi quyết định.

## Mốc hiện tại

| Hạng mục | Trạng thái tại snapshot | Điều kiện hoàn thành / phụ trách theo vai trò |
|---|---|---|
| Quyền nguồn coursework Drive hiện có | PASS trong phạm vi nội bộ đã xác nhận | Coordinator kế thừa quyết định; không hỏi lại giấy tờ đã đóng |
| Content F01/C04 và O01 46–76s | Đã được người dùng chấp nhận | Không lặp lại review; không suy ra split/labels PASS |
| Cohort train thay thế | PENDING, chưa gán split | Coordinator xử lý F06–P08/P09, C08 proposal và source/session grouping; O01 vẫn chưa rõ source/session |
| Exposure/protocol/handoff | Chưa mở | Coordinator + người Pass 1 xác minh từng clip và cách ly hai máy thực tế |
| Nhãn nghiên cứu được chấp nhận | 0 | Annotator/reviewer hoàn tất hai pass và nghiệm thu đúng schema |
| Ngân sách lịch sử | UNKNOWN | Người phụ trách run đối soát ledger; 0 GPU ở các pass CPU vừa báo cáo không suy ra số dư study |
| Kích thước/recipe/iOS feasibility | Chưa xác thực/khóa | Nhóm AI và iOS cung cấp bằng chứng trước main training |
| Chất lượng model/mobile readiness | Chưa được chứng minh | Nhóm đánh giá thực hiện [acceptance](acceptance.md) |

F01/C04/C07 không tự được đưa vào train hoặc chuyển split. Chấp nhận quyền nguồn không giải quyết split. C08 assistant KEEP không tự thành human acceptance. Giữ exposure Mạnh/O01 và assistant đã ghi; không suy người khác chưa phơi nhiễm. Không mở lại B02/B03 đã bỏ qua hoặc tuyển lại sáu nguồn chỉ để lặp thủ tục.

## Checklist chuyển bước

- [ ] Dữ liệu đủ điều kiện theo [data-gates](data-gates.md), nhãn được chấp nhận và có evidence cụ thể.
- [ ] Pilot/run có gate và ngân sách theo [training-gates](training-gates.md).
- [ ] Feasibility iOS và recipe/rubric đã khóa trước main training.
- [ ] So sánh/ablation và lựa chọn trên dev được lưu cùng raw traces.
- [ ] Final test và thiết bị được đo theo [acceptance](acceptance.md).
- [ ] Artifact, giới hạn và kết quả âm tính được bàn giao với provenance.

Chỉ đánh dấu khi liên kết được bằng chứng và người chịu trách nhiệm thực tế. Vai trò trong bảng không phải phân công danh tính. Không tạo thêm vòng xin phép nếu quyết định hợp lệ đã có trong phiên/phạm vi hiện tại.

## Mẫu cập nhật ngắn

```text
Mốc / công việc:
Đã làm và phạm vi kết luận:
Bằng chứng: đường dẫn, hash nếu cần, đầu vào/config liên quan
Kiểm tra: lệnh/phạm vi, kết quả; chưa chạy thì ghi chưa chạy
Gate: đã đạt / chờ / không đạt / chưa biết; căn cứ
Người thực hiện / chấp nhận: danh tính thực hoặc chưa phân công
Blocker còn lại và đúng một bước tiếp theo:
Supersedes: tham chiếu quyết định cũ và phạm vi thay thế, nếu có
```

Thêm cập nhật có ngày vào status khi có kết quả mới; không viết lại lịch sử để xóa blocker/lỗi. Bằng chứng chi tiết nằm ở output mới, không nhúng toàn log hoặc media vào tài liệu. Mẫu bàn giao không thay thế gate receipt hiện có.
