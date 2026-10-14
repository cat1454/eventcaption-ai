# Review phiên 04 — chưa nghiệm thu dispatcher

Ngày: 2026-10-10. Đã đọc code, test, metadata và biên nhận phiên 04. Đã chạy tái hiện lỗi với file giả trong thư mục tạm; không sửa video/log thật, không dùng GPU. Chưa chạy lại toàn bộ pytest hoặc giải mã lại 311 video trong lượt review này.

## Kết luận và phần đã có

CLI đã có triển khai thật, không còn là stub. Có kiểm tra quyết định và cutoff, ghi log rồi cấp prefix tiếp theo trong luồng bình thường. Tuy nhiên, còn lỗi về bảo toàn lịch sử, khôi phục và toàn vẹn media; chưa giao cho annotator thật.

Biên nhận hiện ghi 311 prefix. Tính lại trên các giá trị trong biên nhận: không có `max_pts_ms > cutoff_ms`; chênh lớn nhất là -67 ms. Đây là đối chiếu biên nhận, không phải chứng nhận độc lập nội dung hoặc ánh xạ khung nguồn.

## 1. Crash rồi retry tạo log trùng và làm resume thất bại — cao

`submit_decision()` đọc session JSON, append/fsync log rồi mới cập nhật session. Nếu crash sau append nhưng trước `_save_session`, lần submit lại vẫn đọc step cũ và append lần thứ hai. Không có transaction/lock ngăn hai tiến trình xử lý cùng step.

Đã tái hiện bằng cách làm `_save_session` ném lỗi sau append rồi gọi lại submit: log có step `[0, 0]`; `resume_session()` từ chối với `Log integrity error`. Test hiện tại chỉ tạo lại dispatcher sau một submit thành công, chưa tiêm lỗi vào khoảng ghi này.

Yêu cầu: trạng thái bền vững phải là nguồn sự thật cho mọi submit; dùng transaction với ràng buộc duy nhất session/step hoặc khóa và replay/đối chiếu log trước submit. Retry phải idempotent hoặc từ chối mà không append trùng. Định nghĩa xử lý dòng JSONL ghi dở; không tự mất lịch sử. Kiểm tra crash trước/sau commit, retry, submit đồng thời và restart.

## 2. `--force` xóa lịch sử — cao

`init_session(force_clean=True)` cho phép dùng lại session rồi gọi `log_file.write_text("")`. Đã tái hiện: log có quyết định trở thành 0 byte. Điều này trái yêu cầu append-only.

Bỏ reset phá hủy; luôn từ chối session/log đã tồn tại hoặc tạo phiên mới có liên kết supersedes. Nếu log tồn tại mà session JSON thiếu cũng không được truncate log.

## 3. Hardlink cho phép bên nhận sửa media nguồn — cao

`_deliver_prefix()` ưu tiên `os.link(src_path, dest_path)`, trong khi tài liệu cho annotator quyền đọc/ghi handoff. Đã tái hiện: ghi vào file handoff làm thay đổi file nguồn tương ứng (`source_changed_via_handoff=True`).

Dùng bản copy độc lập, công bố nguyên tử và kiểm tra digest; tách nơi nộp quyết định khỏi media chỉ đọc. Không dùng hardlink cho bản bàn giao có thể bị sửa. Thư mục handoff vẫn cần tách quyền khỏi kho điều phối.

## 4. Hash được lưu nhưng chưa ràng buộc phiên/media — cao

Code tính hash queue lúc khởi tạo và lưu vào session nhưng không so sánh lại khi submit/resume. `_deliver_prefix()` lấy đường dẫn từ checkpoint cũ với base directory của queue hiện tại; không tính hash nguồn hoặc file bàn giao trước khi công bố. `video_sha256` chỉ sao chép giá trị khai báo.

Yêu cầu: xác minh queue đúng phiên đã khóa, kiểm tra media digest trước khi giao, từ chối file/queue thay đổi và đường dẫn vượt kho cho phép. Kiểm tra checkpoint tăng nghiêm ngặt, ID duy nhất và cutoff trong duration khi đọc queue. Test hiện dùng chuỗi `hash_1000` thay vì SHA-256 thực nên chưa kiểm chứng tính toàn vẹn.

## 5. Log thiếu evidence để tái dựng annotation

`evidence_registry` được kiểm tra trong submit nhưng không được lưu trong log. Log giữ `evidence_refs` ở operation mà thiếu mapping ref → timestamp cùng input/frame provenance. Sau restart không thể chỉ từ log tái lập đầy đủ ví dụ annotation đã kiểm tra.

Lưu payload hợp lệ, evidence registry, media/checkpoint hash, danh tính phiên/annotator và tham chiếu frame nếu dùng; phân biệt với record công bố. Resume phải kiểm tra bản ghi với assignment/cutoff/hợp đồng thay vì chỉ đếm step rồi tin `active_events_snapshot`. Human acceptance vẫn phải riêng, không tự nâng cờ.

## 6. Test chính thức phụ thuộc file ignored và ổ H: — cao đối với CI

`tests/test_coordinator_dispatch.py` chèn cứng `H:/EventCaption-AI/runs/pilot-selection-04` vào `sys.path` để import. `git check-ignore` xác nhận module dispatcher nằm trong `runs/` bị bỏ qua. Checkout sạch hoặc Linux CI không có module này.

Đưa công cụ tái sử dụng vào module được theo dõi trong `src/eventcaption_ai/`, test import package bình thường; giữ media/log/queue riêng trong ignored runs. Nếu chỉ giữ script thí nghiệm local, không để test chính thức phụ thuộc nó. Chạy test từ môi trường chỉ có file theo dõi trong Git; không cần Google/model/GPU.

## 7. Handoff có thể xóa file không thuộc phiên

`_deliver_prefix()` xóa mọi `*.mp4` trong đường dẫn được truyền vào và bỏ qua lỗi xóa. Chưa ràng buộc handoff với session hoặc từ chối overlap kho media/coordinator. Truyền nhầm đường dẫn có thể mất media; lỗi xóa có thể để nhiều video còn trong handoff.

Chỉ dùng thư mục mới hoặc thư mục có marker ownership đúng phiên; kiểm tra đường dẫn resolve không chồng lấn kho nguồn/coordinator. Chỉ quản lý file thuộc phiên, từ chối thư mục lạ; dừng khi không dọn được file mà protocol yêu cầu. Dùng ID phiên an toàn cho tên file, không cho path traversal.

## 8. Sửa báo cáo và điều kiện kiểm tra prefix

- Điều kiện `max_pts_ms <= cutoff_ms + 80` không được gọi là “không có tương lai”. Dùng giới hạn cutoff thật; nếu cần đổi cutoff theo frame thì khai báo cutoff thực tế và cập nhật annotation tương ứng. Số trong biên nhận hiện tại vốn đã không vượt cutoff, không cần nới +80 ms.
- Báo cáo mô tả sai P02/P24/P25/P26 thành dưa leo/hạc giấy/máy bay/bàn ghế. JSON hiện vẫn ghi đúng ID của trứng, giấy gói và trang trí giấy. Sửa diễn giải theo nguồn; không đổi video để khớp câu báo cáo.
- Phân tầng chữ trên hình là bước staging hữu ích. Các nguồn còn lại chưa được người duyệt xác nhận không có chữ; dùng trạng thái dự kiến/pending review, tránh coi `visual_unassisted` là chứng nhận đã hoàn tất.
- Tạo SQLite ngân sách mới không tự xác minh số giờ đã dùng trước đây. Cần đối chiếu lịch sử nghiên cứu/ledger có thẩm quyền trước khi mở ngân sách, không tự reset về 40 giờ.

## Lời giao việc tiếp

> Đọc `docs/antigravity-stage04-review.md`. Giữ nguyên phiên 01–04 và triển khai bản sửa mới. Ưu tiên transaction/retry/crash, bỏ force-reset, bỏ hardlink bàn giao, khóa hash queue/media, lưu evidence và bảo vệ ownership/path của handoff. Đưa code tái sử dụng vào package được Git theo dõi để test chạy trên checkout sạch. Thêm kiểm tra CPU đúng các failure case đã nêu; log rõ điều kiện tiêm lỗi và kết quả, không chỉ chạy happy path. Sửa báo cáo và điều kiện cutoff +80 ms. Chưa dùng annotator thật hoặc GPU, không thêm UI. Báo từng lỗi bằng bằng chứng đã sửa hoặc lý do chưa xử lý; không kết luận hoàn tất chỉ từ tổng số test pass.
