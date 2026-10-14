# Review phiên 06 — đóng hai lỗi replay đã báo

Ngày: 2026-10-10. Đối chiếu báo cáo, code `src/eventcaption_ai/dispatch.py` và test hiện tại.

## Kết luận

Hai lỗi trong `docs/antigravity-stage05-followup-review.md` đã được sửa trong phạm vi kiểm tra này. Không phát hiện lỗi chặn mới trong phần thay đổi replay đã review. Có thể kết thúc vòng sửa hai lỗi này và chuyển sang chuẩn bị duyệt dữ liệu/protocol.

Đây là nghiệm thu bản sửa phần mềm trong phạm vi đã kiểm tra, không phải chứng nhận mọi tình huống crash, bảo mật triển khai, chất lượng model hoặc chấp nhận bộ nhãn.

## Bằng chứng kiểm tra độc lập

- SHA-256 engine thực tế khớp báo cáo phiên 06: `4b02c01fa5cad06f1c80cab13d65c57f7a372111841e677cfe3a897fca8a905a`.
- Submit và replay cùng gọi `apply_decisions_transition()`. ID sự kiện được tạo theo counter; không tìm sự kiện bằng caption text.
- Replay đối chiếu toàn bộ danh sách operation được tái tạo từ payload với operation trong log, kiểm tra registry của entry/payload và snapshot trạng thái.
- `.venv-drive-check\Scripts\python.exe -m pytest tests/test_coordinator_dispatch.py -q`: **10 passed in 3.38s**.
- `.venv-drive-check\Scripts\python.exe -m pytest -q`: **68 passed in 13.74s**.

Các test liên quan bao phủ hai EMIT cùng caption, payload-operation lệch interval/text/evidence, metadata log sai, giải phóng khóa khi tiến trình con chết, khóa tiến trình đang sống, retry cuối, không reset log và media bàn giao độc lập. Test dùng dữ liệu giả; không mở quyền dữ liệu và không dùng GPU.

## Việc làm tiếp, không mở thêm vòng refactor nếu chưa có lỗi cụ thể

1. **Giữ mốc phần mềm đã kiểm tra.** Giữ biên nhận phiên 06 và hash engine; đưa đủ module/test vào gói thay đổi mã nguồn khi bàn giao. Không giả định các file untracked đã có trong checkout khác; không kèm media/token/log riêng tư.
2. **Lập phiếu curator duyệt toàn đoạn.** Dẫn đúng source ID, mốc, link local và nhóm đề xuất của 30 clip. Ưu tiên P17–P20 mới, rồi các clip có chữ P02/P24/P25/P26. Ghi quyết định giữ/đổi mốc/thay/loại cùng người duyệt và lý do; không tự tạo chữ ký hay acceptance.
3. **Kiểm tra nhóm nguồn và quyền.** Xác minh nguồn trùng/bản dựng lại, quyền đánh giá và quyền huấn luyện với bằng chứng riêng. Giữ trạng thái pending khi chưa có thông tin; không thay cờ để vượt validator.
4. **Chốt protocol gán nhãn và phân tầng chữ.** Giữ draft cho tới khi có người duyệt; ghi rõ timeline clip, độ phân giải checkpoint, quy tắc occlusion/WAIT và xử lý chữ trên hình. Không đưa dữ liệu curator hoặc kết thúc video vào lượt prefix.
5. **Diễn tập vận hành bằng dữ liệu giả.** Điều phối và annotator dùng đúng ranh giới thư mục/quyền thực tế. Người gán nhãn chỉ nhận prefix được cấp; người đã xem full video không được làm lượt prefix như người chưa biết kết thúc. Quy trình phải ghi cách xử lý log ghi dở: dừng, bảo toàn bản gốc và bằng chứng, không tự truncate để tiếp tục.
6. **Chỉ bắt đầu gán nhãn thật khi các điều kiện liên quan đã có bằng chứng.** Human acceptance được ghi sau khi người thực hiện duyệt. Khả năng dispatcher chạy không tự mở cổng huấn luyện chính.

Feasibility iOS và ngân sách GPU vẫn theo `docs/plan.md`/`docs/handoff.md`; số dư GPU phải được đối chiếu lịch sử, không tạo ledger mới để giả định còn 40 giờ. Không chạy GPU hoặc huấn luyện từ kết luận review này.

## Lời giao việc tiếp cho Antigravity

> Hai lỗi replay đã được review và test lại, xem `docs/antigravity-stage06-review.md`. Giữ mốc code/hash phiên 06; không tiếp tục refactor khi chưa có lỗi cụ thể. Chuẩn bị phiếu curator duyệt 30 clip, bảng quyền/quan hệ nguồn, phiếu khóa protocol và hướng dẫn diễn tập dispatcher bằng dữ liệu giả với ranh giới truy cập thực tế. Đặt đầu ra ở đường dẫn mới; phân biệt tài liệu curator và gói prefix. Báo rõ mục nào cần người duyệt, không tự điền acceptance/quyền hoặc khởi chạy GPU. Mục tiêu tiếp theo là có bộ dữ liệu được duyệt và quy trình gán nhãn dùng được, không chỉ tăng số test.
