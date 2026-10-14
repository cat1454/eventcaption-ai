# Review bản sửa tiếp theo của phiên 05

Ngày: 2026-10-10. Review code hiện tại sau báo cáo sửa `docs/antigravity-stage05-review.md`.

## Kết quả đã xác nhận

Chạy `.venv-drive-check\Scripts\python.exe -m pytest tests/test_coordinator_dispatch.py -q`: **8 passed in 3.18s**. Bộ test bao gồm tiến trình con chết bằng `os._exit`, khóa khi tiến trình khác còn sống, metadata log bị sửa và retry checkpoint cuối.

Khóa OS đã thay khóa tồn tại file; nhánh idempotent retry đã chuyển trước kiểm tra completed. Replay đã kiểm tra session/assignment/annotator, cutoff và checkpoint hash. Các trường hợp lỗi cụ thể của review trước đã có cải thiện và kiểm tra tương ứng. Chưa chạy lại toàn bộ suite hoặc kiểm chứng nội dung video trong lượt này.

## Lỗi còn lại: replay chưa thực sự tái tính operation từ payload

Trong `src/eventcaption_ai/dispatch.py`, `_read_and_verify_log()`:

- EMIT tìm operation đã ghi bằng **action và text** rồi dùng chính operation đó làm kết quả replay.
- REVISE/WITHDRAW tìm bằng previous_record_id và action rồi cũng dùng operation đã ghi.
- Biến `expected_recomputed_ops` chứa các operation lấy từ log; phần đối chiếu cuối chỉ so sánh **độ dài**, chưa so nội dung đầy đủ.

Vì vậy việc kiểm tra payload hợp lệ riêng và snapshot khớp operation chưa chứng minh operation được tạo từ payload đó.

### Tái hiện 1 — submit hợp lệ xong không resume được

Trong một checkpoint 1.000 ms, submit hai EMIT có cùng text `A hand moves a cup`, start_ms lần lượt 100 và 200, evidence hợp lệ ở 500 ms. Submit thành công và tạo hai event khác ID.

Khi resume, cả hai quyết định đều được ghép với operation đầu tiên do cùng text. Kết quả: `Log entry 0 duplicate event ID 'ev_A_001_1000'`.

Hai sự kiện khác nhau có thể có cùng caption; hợp đồng không yêu cầu text duy nhất. Không sửa bằng cách cấm trùng text.

### Tái hiện 2 — payload và operation khác interval vẫn được chấp nhận

Sau một EMIT start_ms=100 hợp lệ, trong log giả đổi riêng `submission_payload.decisions[0].start_ms` thành 300; operation và snapshot giữ start_ms=100. Cả hai giá trị đều nằm trước cutoff nên validator riêng lẻ đều hợp lệ.

Resume vẫn được chấp nhận. Báo cáo “tái tính và đối chiếu toàn bộ operations với payload” chưa đúng với implementation.

Các probe dùng file giả trong thư mục tạm; không chỉnh log hoặc media nghiên cứu.

## Cách sửa và điều kiện nghiệm thu

1. Dùng chung một hàm chuyển trạng thái thuần cho submit và replay: nhận trạng thái trước, session/assignment, cutoff, evidence và danh sách quyết định; tạo operation theo đúng thứ tự cùng quy tắc ID/version.
2. Không dùng text để định danh/ghép sự kiện. EMIT xác định ID từ quy tắc tạo ID; REVISE/WITHDRAW dùng previous_record_id và trạng thái trước.
3. Replay tái tạo operation từ payload và đối chiếu **toàn bộ nội dung** với log, rồi đối chiếu snapshot. Kiểm tra evidence_registry ở entry nhất quán với payload sau áp dụng cùng quy tắc mặc định.
4. Bổ sung test: hai EMIT cùng text, sửa riêng interval/text/evidence của payload hoặc operation, sửa REVISE/WITHDRAW nhưng vẫn để từng phần hợp lệ riêng. Các trường hợp bất nhất phải bị từ chối trước cấp media tiếp theo.
5. Giữ test hồi quy đã có cho lock, retry/crash, media độc lập, không reset log và path isolation. Việc số test giảm 9 xuống 8 không chứng minh thiếu kiểm tra, nhưng không nên bỏ các tình huống fault injection trước đó chỉ vì thay bộ test.

Đây vẫn là lỗi chặn nghiệm thu replay. Không mở rộng thêm tính năng để xử lý review này.

## Lưu bằng chứng phiên sửa

Báo cáo mới vẫn sử dụng thư mục `runs/pilot-selection-05/`. Từ bản sửa tiếp theo, dùng thư mục hoặc tên biên nhận mới, gắn hash code và lệnh kiểm tra để phân biệt các lần chạy; không ghi đè bằng chứng cũ. Nếu bản trước đã bị ghi đè, ghi rõ việc đó, không tự tái tạo như log lịch sử gốc.

## Lời giao việc cho Antigravity

> Đọc `docs/antigravity-stage05-followup-review.md`. Chỉ tập trung sửa replay bằng hàm chuyển trạng thái dùng chung với submit, đối chiếu đầy đủ payload/evidence/operations/snapshot và xử lý nhiều sự kiện có cùng text. Tái hiện rồi kiểm tra hai lỗi đã nêu cùng các test hồi quy. Ghi bằng chứng ở đường dẫn mới, gắn hash code; giữ artifact trước. Không tự chứng nhận cohort/nhãn, không chạy GPU hoặc thêm UI. Báo kết quả cụ thể của từng tình huống.
