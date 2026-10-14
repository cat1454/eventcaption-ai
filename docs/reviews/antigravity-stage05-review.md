# Review phiên 05 — kết quả kiểm tra và việc còn thiếu

Ngày: 2026-10-10. Đã đọc `src/eventcaption_ai/dispatch.py`, test tương ứng và báo cáo phiên 05. Đã chạy riêng test dispatcher và hai probe trên dữ liệu giả trong thư mục tạm. Không sửa media/log nghiên cứu, không chạy GPU. Chưa chạy lại toàn bộ test suite hoặc giải mã lại 311 prefix.

## Phần đã cải thiện

- Module đã chuyển vào `src/eventcaption_ai/dispatch.py`, test import package thay vì đường dẫn ổ H: trong runs.
- Không còn force-reset log; có kiểm tra tồn tại log/session và liên kết supersedes.
- Handoff dùng bản copy độc lập, có kiểm tra digest nguồn và bản copy; không còn hardlink như phiên 04.
- Queue/media có kiểm tra runtime, log có payload và evidence registry, có marker handoff và kiểm tra chồng lấn đường dẫn.
- Tái chạy `.venv-drive-check\Scripts\python.exe -m pytest tests/test_coordinator_dispatch.py -q`: **9 passed in 0.57s**. Đây là kết quả kiểm tra phần mềm, không phải chấp nhận cohort.

Chưa nghiệm thu khả năng khôi phục sau tiến trình bị tắt và khả năng xác minh đầy đủ log. Hai lỗi dưới đây được tái hiện độc lập.

## 1. Khóa không tự giải phóng khi tiến trình chết — cao

`SessionLock` dùng tạo file với `O_CREAT | O_EXCL`, chỉ xóa file trong `release()` qua `__exit__`. Khi kill tiến trình, mất điện hoặc gọi `os._exit`, cleanup không chạy. Lần resume sau chỉ thấy file tồn tại và ném `LockError`; `timeout_seconds` không được dùng để khôi phục.

Probe: tiến trình con lấy SessionLock rồi `os._exit(23)`. Tiến trình cha gọi `resume_session`: kết quả **LockError** dù tiến trình con đã chết.

Test fault injection hiện ném `RuntimeError`; exception vẫn thoát context manager và xóa khóa. Vì vậy test đó chứng minh retry sau exception được cleanup, chưa chứng minh phục hồi sau hard crash.

Yêu cầu sửa:

- Dùng khóa OS được giải phóng khi tiến trình chết hoặc transaction SQLite phù hợp; nếu giữ lockfile, thiết kế phục hồi ownership an toàn, không chỉ xóa khóa theo tuổi/PID đơn lẻ.
- Kiểm tra bằng tiến trình con bị tắt thật tại các điểm: sau khi lấy lock, sau commit log trước cache session và trong lúc giao media.
- Hai tiến trình đang sống vẫn phải không ghi đồng thời; khôi phục không mất/trùng quyết định và không cấp prefix trước quyết định đã commit.
- Dòng JSONL cuối ghi dở hiện bị từ chối toàn bộ. Ghi rõ quy trình phục hồi bảo toàn byte lỗi và các record đã commit; không tuyên bố tự phục hồi mọi crash khi chưa có xử lý này.

## 2. Replay chưa xác minh log theo queue và hợp đồng đầy đủ — cao

`_read_and_verify_log()` kiểm tra step liên tục và gọi `validate_transition` cho các operation được nhận diện. Hàm không đối chiếu session/assignment/annotator, cutoff, checkpoint hash với phiên; không kiểm tra lại evidence và decision bằng `validate_decision`. WAIT bị bỏ qua; action không nhận diện cũng không có nhánh từ chối.

Probe sau một WAIT hợp lệ: đổi trong bản log giả `assignment_id` thành `WRONG`, `cutoff_ms` thành `999999`, `checkpoint_sha256` thành 64 số 0. **Resume vẫn thành công, current_step_index=1**. Không sửa log thật trong phép kiểm tra này.

Yêu cầu sửa:

- Replay nhận metadata phiên và queue đã khóa; kiểm tra số entry không vượt checkpoint, ID/identity, cutoff và checkpoint hash đúng từng step.
- Kiểm tra lại envelope, evidence registry, từng decision và phiên bản/tham chiếu sự kiện; từ chối action lạ, EMIT đè event ID có sẵn, WAIT trộn event update.
- Tái tính operations từ payload hợp lệ, đối chiếu operations/snapshot được lưu; không chỉ tin snapshot hoặc payload riêng rẽ.
- Có test làm sai từng trường, future evidence, operation không khớp payload, bản ghi của phiên khác và record thừa. Fail closed trước khi cấp media tiếp theo.

## 3. Retry tại checkpoint cuối chưa idempotent

Trong `submit_decision`, kiểm tra `curr_idx >= total_steps` xảy ra trước nhánh idempotent retry. Nếu đã commit quyết định cuối nhưng chưa nhận được phản hồi, nộp lại payload giống hệt vẫn bị từ chối “already completed”. Resume có thể hoàn tất việc giao thông báo, nhưng tuyên bố retry idempotent hiện chưa bao phủ bước cuối.

Đưa nhận diện retry hợp lệ trước nhánh từ chối phiên hoàn tất; trả lại kết quả commit cũ và đồng bộ handoff, không append thêm. Payload khác vẫn bị từ chối. Bổ sung kiểm tra crash sau commit checkpoint cuối.

## 4. Tình trạng Git cần ghi đúng

Tại thời điểm review, `git status --short` báo `??` cho cả `src/eventcaption_ai/dispatch.py` và `tests/test_coordinator_dispatch.py`. File đã nằm ở vị trí có thể theo dõi trong package nhưng **chưa được Git theo dõi**, khác câu “git-tracked” trong báo cáo.

Không khẳng định checkout sạch đã có module cho tới khi file được đưa vào thay đổi bàn giao. Không tự commit/push hoặc thêm media/secrets. Khi bàn giao thay đổi, cần có đủ module/test và kiểm tra packaging/import trong môi trường chỉ chứa nguồn bàn giao; không dựa vào file ignored.

## Phạm vi nghiệm thu tiếp theo

Không cần mở rộng sang UI, training hoặc GPU. Tập trung đóng các lỗi khôi phục và replay bên trên. Các bước duyệt cohort, quyền sử dụng, protocol, nguồn trùng và tách quyền truy cập vẫn độc lập với việc test dispatcher pass.

## Lời giao việc tiếp cho Antigravity

> Đọc `docs/antigravity-stage05-review.md`. Giữ artifact phiên 01–05, sửa module package và tạo bằng chứng phiên mới. Dùng test tiến trình chết thật để xử lý stale lock/crash recovery; xác minh đầy đủ log với queue/phiên/evidence/payload; hỗ trợ retry checkpoint cuối. Ghi rõ quy trình với log ghi dở. Chạy test regression và fault injection CPU, lưu lệnh cùng kết quả từng tình huống. Báo đúng trạng thái Git của file bàn giao. Không chạy GPU hoặc tự nghiệm thu nhãn/cohort. Chỉ kết luận những trường hợp đã có bằng chứng.
