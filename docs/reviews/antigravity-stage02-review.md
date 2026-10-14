# Review kết quả Antigravity — pilot-selection-02

Ngày: 2026-10-10. Đối chiếu báo cáo bàn giao với artifact local, hướng dẫn dự án và `src/eventcaption_ai/data.py`. Đây là review tài liệu/cấu trúc, không phải nghiệm thu nội dung video hay xác nhận quyền sử dụng. Không chạy lại pytest hoặc model trong review này.

## Kết luận

Phiên 02 đã tạo các artifact staging và tài liệu gán nhãn, nhưng chưa hoàn thành toàn bộ kế hoạch. Gói hiện tại chưa sẵn sàng giao người gán nhãn prefix. Giữ kết quả phiên 02 làm lịch sử; sửa trong phiên mới, ví dụ `runs/pilot-selection-03/` nếu đường dẫn chưa tồn tại.

Việc giữ quyền ở trạng thái chưa xác minh, không đặt human acceptance và ghi rõ thiếu bốn ứng viên organizing là phù hợp. Quyết định loại P19/P20 được ghi nhận trong kết quả phiên 02; review này chưa độc lập chứng nhận các kết luận thị giác đó.

## Các vấn đề phải sửa

### 1. Hướng dẫn sai về che khuất — ưu tiên cao

File `runs/pilot-selection-02/labeling-package/instructions-vi.md`, mục II.2, yêu cầu cập nhật `ended` khi sự kiện kết thúc **hoặc bị tay che khuất**.

Che khuất không phải bằng chứng sự kiện đã kết thúc. Sửa hướng dẫn: chỉ cập nhật `ended` và `end_ms` khi có bằng chứng kết thúc; nếu chỉ mất quan sát, giữ bản ghi được hỗ trợ trước đó và WAIT khi chưa đủ bằng chứng cập nhật. Không tự rút lại hay kết thúc sự kiện vì che khuất.

### 2. Queue chưa có media và chưa bảo đảm giới hạn prefix — ưu tiên cao

Kiểm tra `neutral-prefix-queue.json`: có 28 mục; cả 28 `media_ref` không tồn tại khi resolve tương đối với thư mục gói. Không thấy cơ chế resolver hoặc thư mục media đi kèm trong gói. Queue vẫn đánh dấu `ready_for_annotator_pass_1`.

Danh sách checkpoint và lời dặn không tự chặn quyền truy cập tương lai. Không khắc phục bằng cách đưa nguyên video vào gói người gán nhãn rồi vẫn tuyên bố prefix đã được cô lập.

Yêu cầu:

- Đổi trạng thái thành draft/not ready cho đến khi đường dẫn và quy trình phát prefix hoạt động.
- Chuẩn bị media giới hạn đúng cutoff hoặc quy trình bàn giao lần lượt từng prefix, ghi lại quyết định trước khi mở prefix tiếp theo. Không giao toàn bộ các prefix tương lai cùng lúc.
- Người gán nhãn chỉ được truy cập phần đã cấp; mapping nguồn, video đầy đủ và thư mục curator nằm ở phía điều phối.
- Kiểm tra media đầu ra không chứa khung hình sau cutoff; xác định chính sách audio. Không thêm application UI vào repo.
- Chuyển P17/P18 còn nghi vấn sang queue dự phòng riêng; không trình bày như các đoạn đã được duyệt.

### 3. Timeline đang không tương thích trực tiếp với exporter

Ví dụ P02: đoạn nguồn 20–80 giây, duration 60 giây, checkpoints 25–80 giây. `training_examples()` kiểm tra `context.cutoff_ms <= source.duration_ms`; dùng trực tiếp checkpoint 80.000 ms với duration 60.000 ms sẽ bị từ chối.

Quy định rõ timeline nguồn và timeline clip. Với exporter hiện tại, chuẩn bị annotation trên timeline clip 0–duration và lưu mapping riêng:

`source_time_ms = segment_start_ms + clip_time_ms`.

Ánh xạ cả cutoff, evidence, frame timestamps và event intervals nhất quán. Không thêm trường ngoài schema vào manifest chính thức. Giữ hash nguồn và hash clip tách biệt nếu xuất clip mới.

### 4. Chưa thể xác định thời điểm đủ bằng chứng “chính xác” bằng checkpoint 5 giây

Rubric và hướng dẫn yêu cầu thời điểm chính xác, trong khi queue chủ yếu lấy checkpoint cách nhau 5 giây. Quan sát chỉ chứng minh thời điểm đủ bằng chứng đã được ghi nhận tại checkpoint, không mặc nhiên chứng minh thời điểm đầu tiên chính xác giữa hai checkpoint.

Ghi rõ độ phân giải và sự không chắc chắn; ví dụ khoảng giữa checkpoint trước chưa đủ và checkpoint đầu đủ. Nếu cần độ phân giải khác, thiết kế trước lượt gán nhãn. Không cho cùng người xem tương lai rồi quay lại tạo nhãn prefix như chưa biết kết thúc. Không đồng nhất thời điểm đủ bằng chứng với wall-clock phát/hiển thị.

### 5. Một số tuyên bố vượt bằng chứng hiện có

Trong `docs/status.md` và `progress.md`:

- Đổi “verified preferred”/“đạt chuẩn” thành ứng viên ưu tiên sau sàng lọc khung mẫu, chưa được con người chấp nhận.
- Giải mã video và OCR mỗi 2 giây không tương đương xem liên tục toàn đoạn hoặc chứng minh ý nghĩa hành động. OCR không phát hiện chữ ở một khung cũng không chứng minh toàn đoạn không có chữ.
- P03 đổi sang 6–36 giây là mốc đề xuất đã được kiểm tra bằng khung mẫu. Không dùng “loại bỏ triệt để” hoặc “confirmed ... onwards” nếu chưa có bằng chứng đủ bao phủ tuyên bố đó.
- “Phiên này không chạy GPU” không chứng minh ngân sách toàn nghiên cứu còn nguyên 40 giờ. Chưa thấy ledger ngân sách trong phạm vi `runs/` đã kiểm tra. Chỉ ghi số dư khi đối chiếu ledger nghiên cứu thực tế; thiếu ledger thì để số dư chưa xác minh.
- 58 test pass là kết quả do phiên 02 báo cáo; lưu lệnh, môi trường, log nếu muốn dùng làm bằng chứng tái lập. Các test không chứng minh cohort hay gói gán nhãn đã sẵn sàng.

### 6. Schema/template và phần công việc còn thiếu

`annotation-template.json` có `verified_by_human=false` và đường dẫn frame minh họa. Đây là draft minh họa, không phải annotation đã được chấp nhận hay bộ media thực thi được. Ghi rõ các frame còn là placeholder; không đưa template có caption gợi ý theo nguồn thực vào lượt prefix của chính nguồn đó.

Staging có `evaluation_allowed=false`; validator manifest chính thức sẽ từ chối theo thiết kế. Phân biệt kiểm tra cấu trúc riêng với việc vượt toàn bộ cổng `validate_manifest`/`training_examples`. Không đổi cờ quyền hoặc human acceptance chỉ để làm kiểm tra pass.

Rubric đang ghi “Locked for Pilot Staging”, nhưng chưa có quyết định khóa protocol sau pilot. Đổi thành draft/versioned proposal; việc khóa phải có cơ sở và người duyệt.

Còn thiếu bốn ứng viên organizing ưu tiên, kiểm tra quan hệ nguồn/near-duplicates và bằng chứng quyền. Tìm thêm ứng viên trong inventory train đã có là việc có thể tiếp tục trên CPU; không tự coi toàn bộ việc tìm nguồn bị chặn vì cần human acceptance ở bước sau.

## Lời giao việc tiếp cho Antigravity

> Đọc `docs/antigravity-stage02-review.md` và xử lý từng phát hiện trong phiên output mới. Giữ nguyên phiên 01/02. Ưu tiên sửa hướng dẫn che khuất, trạng thái queue, khả năng truy cập media, cơ chế cấp prefix và mapping timeline. Tách dự phòng khỏi queue chính. Sửa các tuyên bố vượt bằng chứng trong `docs/status.md`, giữ liên kết đến kết quả cũ. Tiếp tục tìm bốn ứng viên organizing trong nguồn train đã có. Chuẩn bị artifact và kiểm tra CPU phù hợp; không tự chấp nhận nhãn/quyền, không chạy GPU, không thêm UI. Báo từng mục đã sửa bằng đường dẫn và bằng chứng; mục chưa làm được phải nêu điều kiện cụ thể còn thiếu.
