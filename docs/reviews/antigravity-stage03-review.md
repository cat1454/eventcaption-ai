# Review phiên 03 và yêu cầu hoàn thiện

Ngày review: 2026-10-10. Đối chiếu báo cáo với file thực tế trong `runs/pilot-selection-03/`. Chưa xem lại toàn bộ nội dung video, chưa giải mã lại toàn bộ prefix và chưa chạy lại bộ pytest; không chứng nhận nội dung hay human acceptance từ review này.

## Kết luận

Phiên 03 sửa được nhiều vấn đề staging, nhưng tuyên bố “đã sửa triệt để” và “đã có điều phối tuần tự ngăn truy cập tương lai” chưa đúng với code hiện có. Chưa giao nguyên gói `labeling-package/` cho người gán nhãn lượt prefix.

## Đã đối chiếu được

- Queue chính có 30 assignment; đường dẫn 30 full clip và mọi prefix resolve được từ `labeling-package/`.
- Có **311** mục prefix trong queue và **311** file MP4 trong `media/prefixes/`, không có file dư so với queue. SHA-256 của 311 file khớp giá trị trong queue.
- Cutoff của từng prefix không vượt `clip_duration_ms`; timeline queue dùng thời gian clip. Việc này chưa chứng minh nội dung frame tương ứng chính xác với thời gian nguồn.
- Có mapping nguồn/clip cùng hash; reserve queue riêng chứa R01/R02 và không nằm trong queue chính.
- Hướng dẫn đã tách che khuất khỏi kết thúc; rubric đã chuyển về draft và không tuyên bố khóa protocol.
- Trạng thái đã bỏ tuyên bố số dư GPU còn nguyên 40 giờ, chuyển thành chưa xác minh ledger.

## 1. Script điều phối hiện là stub — lỗi chặn bàn giao

`coordinator_prefix_dispatch.py` chỉ kiểm tra file queue, đọc JSON và in hai dòng thông báo. Biến `DECISION_LOG` được khai báo nhưng không được dùng. Không có code cấp phát file, đọc quyết định, kiểm tra cutoff, lưu quyết định, chuyển checkpoint hoặc khôi phục phiên.

`docs/status.md` mục phiên 03.5 và `progress.md` đang mô tả chức năng chưa được triển khai. Cần sửa trạng thái ngay thành “stub; chưa có cơ chế điều phối hoạt động”, hoặc triển khai và đưa bằng chứng chạy thực tế trước khi tuyên bố hoàn tất.

Yêu cầu triển khai bản mới, chỉ dùng CLI phía điều phối:

1. Chọn assignment và phiên gán nhãn bằng ID; gắn với phiên bản queue/hash đầu vào.
2. Xuất đúng một prefix hiện tại vào thư mục giao nhận riêng. Không giao queue chứa mọi đường dẫn, toàn bộ thư mục prefix, full clip, mapping nguồn hoặc curator notes.
3. Nhận quyết định đúng assignment/cutoff; kiểm tra cấu trúc, evidence và tham chiếu bản ghi theo hợp đồng. Giữ trạng thái active events và version links cần thiết. Lưu quyết định bền vững trước khi cấp prefix kế tiếp; WAIT chỉ ở trace.
4. Chặn bỏ qua checkpoint, nộp sai cutoff, nộp trùng hoặc sửa đè quyết định cũ. Sửa sai về sau bằng bản ghi có liên kết, không xóa lịch sử.
5. Khôi phục sau khi thoát/crash mà không mở trước checkpoint. Không tự đặt human acceptance từ một lần nhập CLI.
6. Nêu rõ ranh giới truy cập: script không thể ngăn người có quyền đọc toàn bộ workspace tự mở video tương lai. Thư mục điều phối phải không được giao cho annotator; dùng giao nhận thủ công hoặc phân quyền thực tế phù hợp. Không tuyên bố script tự tạo được cô lập bảo mật nếu chưa có cơ chế đó.

Nghiệm thu bằng media giả/synthetic và log riêng: trước quyết định hợp lệ chỉ có prefix hiện tại; quyết định sai không mở tiếp; quyết định hợp lệ được lưu trước khi mở tiếp; restart không làm mất/ghi đè quyết định hoặc nhảy checkpoint. Không dùng các kết quả này để chứng nhận nhãn/model.

## 2. Số lượng prefix trong báo cáo sai

Báo cáo, `progress.md` và `docs/status.md` ghi 313 prefix; artifact hiện tại có 311. Cập nhật số liệu theo queue/files thực tế. Nếu có kết quả của lần trước, ghi rõ phạm vi và phiên bản thay vì gộp số.

Hash khớp chứng minh file đúng với manifest hiện tại, không chứng minh file không chứa tương lai. Lưu biên nhận kiểm tra PTS/frame gắn hash và phiên bản code/lệnh xuất; khi chuyển FPS hoặc timestamp, cần kiểm tra cả ánh xạ khung nguồn. PTS đầu ra sau rebase đơn thuần chưa chứng minh không có frame nguồn vượt cutoff.

## 3. Chữ hướng dẫn vẫn có thể làm lộ hành động

`instructions-vi.md` yêu cầu annotator “không đọc phụ đề”. Lời dặn này không ngăn người hoặc model nhìn thấy chữ, đặc biệt với các clip đã có cờ action leakage. Bỏ audio không loại bỏ chữ trên hình.

Trước khi khóa protocol, chọn và ghi rõ phương án: thay nguồn không có chữ mô tả hành động, tách thành nhóm đánh giá có chữ, hoặc tạo bản xử lý được duyệt có provenance và kiểm tra không che thao tác. Không tự gọi các clip còn chữ hướng dẫn là bằng chứng nhận biết thao tác thuần túy. Không tự mask/crop rồi thay thế âm thầm video gốc.

## 4. Các ứng viên bổ sung vẫn cần duyệt ngữ nghĩa

Bốn nguồn mới là ứng viên sau sàng lọc, chưa tự giải quyết việc chấp nhận nhóm organizing. Các clip có là/ủi cần xác định thao tác chính và đoạn phù hợp; “không có chữ đè” cũng không được chứng minh chỉ từ OCR không phát hiện chữ. Giữ trạng thái đề xuất cho đến khi người duyệt kiểm tra toàn đoạn.

Không cần tìm thêm nguồn chỉ để tăng số lượng nếu 30 ứng viên hiện tại phù hợp sau duyệt. Tuy nhiên, không biến số lượng đủ 10/10/10 thành kết luận nội dung đã được chấp nhận. Quyền, near-duplicates và hai lượt gán nhãn vẫn là các bước riêng.

## 5. Làm rõ WAIT khi một sự kiện bị che khuất

Giữ quy tắc: che khuất đơn thuần không làm kết thúc hay rút lại sự kiện. Nhưng không ép WAIT cho toàn bộ cutoff chỉ vì một sự kiện cũ bị che: nếu có sự kiện khác với đủ bằng chứng, vẫn có thể EMIT/REVISE theo hợp đồng. WAIT áp dụng khi không có quyết định cập nhật được hỗ trợ, không phải trạng thái khóa toàn cảnh.

## Giao việc tiếp cho Antigravity

> Đọc `docs/antigravity-stage03-review.md`. Tạo phiên sửa mới và giữ phiên 01–03. Triển khai thật CLI điều phối prefix với log bền vững, resume và kiểm tra quyết định; không thêm UI. Chứng minh bằng kiểm tra CPU với media giả và thư mục giao nhận tách khỏi kho curator. Sửa số prefix thành số thực tế, cập nhật các tuyên bố về chức năng trong status/progress, làm rõ chính sách chữ trên hình và WAIT theo sự kiện. Giữ quyền và human acceptance ở trạng thái chưa xác minh khi thiếu bằng chứng. Không chạy GPU. Khi bàn giao, dẫn đường dẫn code, lệnh kiểm tra, log và những mục còn chờ người duyệt; không chỉ báo “đã hoàn tất”.
