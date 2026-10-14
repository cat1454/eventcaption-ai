# Bàn giao cho Antigravity: hoàn thiện pilot và chuẩn bị gán nhãn

Ngày bàn giao: 2026-10-10. Workspace: `H:\EventCaption-AI`.

## 1. Nhiệm vụ và phạm vi

Tiếp tục từ dữ liệu và công cụ đã có để hoàn thiện danh sách pilot 30 video, chuẩn bị bộ tài liệu gán nhãn theo thời gian và xác định rõ các điều kiện còn thiếu trước huấn luyện. Làm việc trên CPU cho giai đoạn tuyển chọn và chuẩn bị dữ liệu này.

Chỉ làm phần AI: dữ liệu, tiền xử lý, hợp đồng sự kiện, công cụ kiểm tra và tài liệu bàn giao. Không thêm backend, frontend, ứng dụng hay giao diện gán nhãn. Không khởi chạy huấn luyện chính từ tài liệu này.

Đọc theo thứ tự trước khi làm:

1. `AGENTS.md`, `docs/plan.md`, `docs/status.md`.
2. `docs/data.md`, `docs/architecture.md`, `docs/evaluation.md`.
3. `docs/handoff.md`, `docs/running.md`.
4. Các tài liệu và danh sách trong `runs/pilot-selection-01/`.

Nếu tài liệu bàn giao khác với hợp đồng hoặc trạng thái thực tế trong repo, ghi rõ chỗ khác và kiểm tra trước khi tiếp tục phần phụ thuộc. Không xem kế hoạch như bằng chứng công việc đã hoàn tất.

## 2. Trạng thái đã có

| Hạng mục | Trạng thái |
|---|---|
| Inventory Drive | 19.998 video ID riêng biệt; 44 trang API; không có lỗi được báo trong lần chạy |
| Metadata thời lượng | Có cho 19.961 video, thiếu cho 37 video |
| Danh sách pilot đề xuất | 30 nguồn khác nhau; đoạn đề xuất 30–60 giây; tổng 1.517 giây |
| Nhóm đồ ăn/đồ uống | 10 ứng viên ưu tiên |
| Nhóm sắp xếp đồ vật | 6 ứng viên ưu tiên + 4 dự phòng |
| Nhóm thủ công/lắp ráp | 10 ứng viên ưu tiên |
| Video đã tải | Đủ 30 nguồn của danh sách; tổng 170.129.184 byte, khoảng 162 MiB; SHA-256 khớp danh sách |
| Mức sàng lọc hình ảnh | Đã xem 6 khung mẫu mỗi đoạn đề xuất; chưa xem liên tục toàn đoạn, chưa có người duyệt |
| Nhãn và quyền sử dụng | Chưa có bộ nhãn event-caption được con người chấp nhận; quyền sử dụng còn cần xác minh |
| Mô hình | Chọn họ SmolVLM2; kích thước chưa được kiểm chứng; chưa có kết quả huấn luyện chính |

Video local là **nguồn đầy đủ**, chưa phải file đã cắt đúng đoạn pilot. Thư mục `review-media/` có thể chứa thêm nguồn từng sàng lọc nhưng bị loại; lấy danh sách 30 nguồn từ CSV, không lấy mọi MP4 trong thư mục làm cohort.

Các nguồn đề xuất được đối chiếu với reference train cũ. Đây là phân vùng của dữ liệu nguồn, không phải phân vùng nghiên cứu mới: pilot thuộc development. Annotation cũ có chỗ không khớp hình ảnh và chỉ được dùng để truy tìm ứng viên.

## 3. Đường dẫn cần dùng

| Đường dẫn tương đối với workspace | Vai trò |
|---|---|
| `runs/drive-inventory-01/videos.csv` | Inventory mở được bằng Excel |
| `runs/drive-inventory-01/inventory.jsonl` | Metadata gốc đã đọc |
| `runs/drive-inventory-01/summary.json` | Trạng thái hoàn tất inventory |
| `runs/pilot-selection-01/pilot-candidates.csv` | 30 ứng viên, ID P01–P30, nhóm, link, mốc, hash và trạng thái |
| `runs/pilot-selection-01/pilot-candidates.json` | Bản JSON của danh sách |
| `runs/pilot-selection-01/video-links.md` | Link Drive và link local từng video |
| `runs/pilot-selection-01/review-media/` | Video nguồn đã tải |
| `runs/pilot-selection-01/selection-summary.json` | Tổng hợp và hash các đầu vào sàng lọc |
| `runs/pilot-selection-01/screening-receipt*.json` | Biên nhận tải/hash/lấy khung của các vòng sàng lọc |
| `runs/pilot-selection-01/rejections.json` | Các đoạn đã loại và lý do |
| `runs/pilot-selection-01/curator-only*/` | Ảnh nhiều thời điểm, chỉ dành cho người tuyển chọn |
| `runs/pilot-selection-01/reference-train.json` | Annotation train cũ, chỉ dùng truy tìm |

Đọc đúng header CSV hiện tại; ghi chú sàng lọc dùng cột `review_notes`, tiêu đề dùng `title_vi`. Không giả định schema từ phiên bản cũ. Một số bản nháp/spec/receipt cũ có thể còn lỗi tiếng Việt; dùng ID, hash, timestamp để đối chiếu, không tự đoán lại nội dung bị hỏng.

Credential và token nằm ngoài Git tại `%LOCALAPPDATA%\EventCaption-AI\google-drive\`. Không in nội dung, không chép vào tài liệu, không yêu cầu người dùng gửi token. Scope OAuth hiện tại là `drive.metadata.readonly`; không tự mở rộng quyền. Các video hiện có đã được tải từ liên kết công khai, độc lập với token metadata.

## 4. Kế hoạch thực hiện theo thứ tự

### Bước 1 — Lập phiên làm việc mới

- Kiểm tra trạng thái Git và bảo toàn thay đổi hiện có của người dùng.
- Đọc CSV, đối chiếu file local và provenance sẵn có; chỉ tải lại nếu thiếu/hỏng và ghi nhận lý do.
- Tạo thư mục output mới, ví dụ `runs/pilot-selection-02/`; nếu đã tồn tại, chọn tên mới. Không ghi đè bản 01 hoặc kết quả của lần khác.
- Ghi `progress.md` nêu đầu vào, việc đang làm, việc xong, việc bị chặn và hành động kế tiếp. Lưu hash của danh sách đầu vào; tham chiếu phiên trước.

### Bước 2 — Duyệt nội dung và chốt đoạn

- Duyệt đủ thời gian của từng đoạn dự kiến bằng khả năng xem video thực tế đang có. Ghi rõ cách duyệt: phát liên tục, lấy khung ở mật độ nào, hoặc chỉ kiểm tra metadata. Không tuyên bố đã xem toàn đoạn nếu chỉ xem khung mẫu.
- Đánh giá thao tác nhìn thấy, thời lượng, cắt cảnh, phần giới thiệu/quảng cáo, che khuất, phụ đề mô tả hành động và chi tiết quá nhỏ.
- Ưu tiên xử lý P17–P20: tìm đoạn thay thế rõ hơn cho nhóm `organizing`, hoặc đưa bằng chứng để người duyệt quyết định giữ. Không gộp thao tác chơi thể thao/chơi bài vào sắp xếp chỉ để đủ số lượng.
- P03 còn hình món hoàn thiện/chữ ở đầu mốc hiện tại; kiểm tra và điều chỉnh mốc trong bản mới nếu cần.
- Các clip có chữ hướng dẫn phải được đánh dấu. Ưu tiên nguồn không có chữ làm lộ hành động; nếu giữ, phải có quyết định xử lý trong protocol trước đánh giá. Không tự sửa hình rồi coi đó là nguồn gốc.
- Có thể dùng annotation train cũ để tìm ứng viên bổ sung; mỗi ứng viên phải được kiểm tra hình ảnh. Không dùng nguồn final test để chọn hoặc thay pilot.
- Mục tiêu: 30 đoạn từ 30 nguồn, mỗi đoạn 30–60 giây, 10 đoạn mỗi nhóm `food_drink`, `organizing`, `craft_assembly`.
- Nếu chưa tìm đủ nguồn phù hợp, báo số thiếu và lý do; giữ trạng thái đề xuất. Không tự chứng nhận đạt chỉ để đủ 30.

Đầu ra: CSV/JSON phiên mới với nguồn, link, hash thực tế, mốc đoạn, phương pháp duyệt, quyết định giữ/thay/loại, lý do, liên kết với ứng viên trước. Giữ cả quyết định loại làm bằng chứng.

### Bước 3 — Quyền sử dụng, nguồn trùng và phân vùng

- Ghi nguồn gốc, capture session, scenario family và bằng chứng quyền sử dụng. Quyền đánh giá và quyền huấn luyện phải được xét riêng.
- Link công khai, khả năng tải và việc nằm trong dataset cũ không tự chứng minh quyền huấn luyện.
- Kiểm tra bản dựng lại/cắt lại từ cùng nguồn. ID và hash khác nhau chưa chứng minh độc lập. Nhóm các nguồn liên quan trước khi chia train/dev/test.
- Pilot thuộc development; trong manifest chính thức dùng giá trị `dev`. Kế hoạch mở rộng là 150 video: 50 mỗi nhóm, tổng train/dev/test = 90/30/30.
- Khi thiếu bằng chứng quyền hoặc nhóm nguồn, lưu trong bảng staging với trạng thái chưa xác minh. Không tự đặt các cờ quyền thành true hoặc tạo license evidence giả để qua validator.

Đầu ra: bảng staging về quyền và quan hệ nguồn, cùng danh sách nội dung còn cần người dùng/chủ dữ liệu xác nhận.

### Bước 4 — Chuẩn bị gói gán nhãn

- Viết rubric tiếng Anh cho caption và hướng dẫn tiếng Việt cho người gán nhãn, dựa trên hợp đồng hiện có.
- Tách hai lượt theo `docs/data.md`: (1) xem prefix tăng dần để ghi thời điểm đủ bằng chứng và quyết định; (2) xem toàn chuỗi để xác định khoảng sự kiện và mô tả tham chiếu.
- Người đã xem toàn clip, caption cũ hoặc montage có tương lai không được xem là người gán nhãn prefix chưa biết kết thúc. Nếu dùng cùng người, phải làm lượt prefix trước, giữ nguyên các quyết định đã ghi; với người đã bị lộ kết thúc, bố trí người khác chưa xem cho lượt prefix.
- Gói prefix chỉ chứa mã trung tính, media/prefix hợp lệ và hướng dẫn. Không đưa `title_vi`, caption cũ, ghi chú tuyển chọn hay ảnh curator nhiều thời điểm vào gói này.
- Giữ các mốc riêng: source cutoff, thời điểm bằng chứng đủ, và wall-clock emission/display. Không suy ra độ trễ hiển thị từ thời gian video hoặc tốc độ sinh văn bản.
- Mọi nhãn AI chỉ là draft. Không đặt `verified_by_human=true`, không giả danh annotator và không tự điền chữ ký người duyệt.
- Nếu cần xuất đoạn video, dùng output mới và lưu ánh xạ offset clip với timeline nguồn, hash nguồn và hash clip. Làm rõ timeline của annotation trước khi export; không thêm trường tùy ý vào schema manifest chính thức.

Đầu ra: rubric, mẫu annotation đúng schema hiện tại, queue trung tính chưa chấp nhận và hướng dẫn cho người gán nhãn. Có thể chuẩn bị những đầu ra này trong khi quyền/cohort còn chờ, nhưng không xuất chúng như dữ liệu đã được duyệt.

### Bước 5 — Kiểm tra dữ liệu và cập nhật trạng thái

- Đọc `src/eventcaption_ai/data.py`, `src/eventcaption_ai/contract.py` và CLI hiện có trước khi viết công cụ mới. Tái sử dụng validator/exporter nếu phù hợp.
- Manifest chính thức là mảng JSON với đúng các trường: `source_id`, `sha256`, `origin_id`, `session_id`, `scenario_group`, `split`, `scene`, `duration_ms`, `training_allowed`, `evaluation_allowed`, `license_evidence`, `pilot`.
- Metadata staging có thể phong phú hơn nhưng phải lưu riêng. Chưa có đủ dữ liệu thì để manifest chính thức ở trạng thái chưa hoàn thành, không bịa giá trị bắt buộc.
- Khi đủ điều kiện, dùng `python -m eventcaption_ai validate-manifest <path>` và các công cụ kiểm tra có sẵn. Export theo mục đích/split hợp lệ; không biến pilot dev thành train để chạy thử huấn luyện.
- Kiểm tra hash/path thực tế, giới hạn đoạn, nguồn trùng và tương lai vượt cutoff. Validator schema không chứng minh ý nghĩa caption, quyền sử dụng hay chất lượng model.
- Nếu sửa code, chạy kiểm tra CPU phù hợp với thay đổi; CI không đăng nhập Google, gọi API thật, tải model hoặc dùng GPU.
- Cập nhật `docs/status.md` bằng bằng chứng mới; giữ rõ các mục còn chờ. Kết thúc bằng đường dẫn artifact, số lượng theo trạng thái và bước tiếp theo cụ thể.

## 5. Ràng buộc xuyên suốt

- Hợp đồng `event-caption/1` mô tả khoảng sự kiện đã quan sát, không phải dự báo.
- `WAIT` chỉ xuất hiện trong trace. Che khuất hoặc sự kiện kết thúc không tự làm caption trước đó sai.
- Giữ lịch sử append-only, record/version links và raw model traces. Sửa sau không xóa lỗi đã công bố trước đó.
- Không dựng xác suất commit, dùng keyword repair để chứng nhận semantics, hoặc sửa đầu ra lỗi rồi báo như đầu ra model nguyên bản.
- Khung hình tương lai phải không truy cập được từ đầu vào tại cutoff sớm hơn. Nhãn toàn chuỗi chỉ ở phía target/tham chiếu phù hợp.
- Context phải hữu hạn; kế hoạch memory ban đầu là 16 events / 16 KiB. Không nhét toàn bộ lịch sử vào prompt.
- Giữ dữ liệu, video, trọng số, token và bằng chứng quyền ngoài Git. Không xóa kết quả âm tính, môi trường cũ hoặc thay đổi của người dùng.
- Dùng môi trường Python riêng phù hợp; không thay dependency inference hay Python toàn máy chỉ để xử lý CSV/video. Ghi file tiếng Việt bằng UTF-8, CSV Excel bằng UTF-8 BOM. Tránh truyền mã chứa tiếng Việt qua PowerShell pipe có encoding mặc định làm mất ký tự.
- Không gửi email/tin nhắn cho nhóm hoặc bên ngoài khi chưa được người dùng giao việc đó.

## 6. Điều kiện trước khi chuyển sang model/GPU

Giai đoạn tiếp theo ngay sau bàn giao này là hoàn thiện dữ liệu pilot và protocol. Chỉ chuẩn bị kế hoạch feasibility, chưa khởi chạy model hoặc GPU bằng nhiệm vụ này.

Trước huấn luyện chính cần có nhãn event-caption được con người chấp nhận, quyền dùng đúng mục đích, phân vùng được khóa và kiểm tra feasibility iOS theo kế hoạch. SmolVLM2 family đã chọn, kích thước chưa được chứng minh phù hợp.

Thiết bị đích: iPhone 16 Pro. Phối hợp bàn giao kỹ thuật cho nhóm thiết bị về preprocessing, tokenizer/template, timestamp, context và feature parity của phương án head riêng. Không tự triển khai ứng dụng trong repo này và không tự thay bằng inference server.

Ngân sách nghiên cứu là **40 giờ GPU dùng chung**, tối đa **4 giờ mỗi run**, tính cả load. Phải đọc ledger thực tế trước bất kỳ run được phép nào; không giả định toàn bộ 40 giờ còn lại. Quota kế hoạch: feasibility 4h, A 10h, B 10h, ablation 8h, final 4h, reserve 4h. Không tạo ledger mới để nhân ngân sách; reservation chưa đóng vẫn được tính.

Các mục tiêu nghiên cứu vẫn là mục tiêu chưa đạt: giảm ít nhất 20% tương đối unsupported captions so với baseline phù hợp; coverage ít nhất 80%, giảm không quá 5 điểm phần trăm; iPhone p95 first-correct-display latency không quá 5 giây từ đủ bằng chứng. Không dùng fixture, test phần mềm, desktop timing hoặc vài ảnh mẫu để tuyên bố đạt.

## 7. Tiêu chí bàn giao lại

- Có thư mục kết quả mới, provenance và tiến độ rõ ràng; bản 01 được giữ nguyên.
- Danh sách ghi đúng số lượng ưu tiên/dự phòng/loại và mốc đã kiểm tra; không che giấu phần thiếu.
- Quyền sử dụng và quan hệ nguồn được ghi nhận trung thực, có danh sách chờ nếu chưa đủ.
- Gói prefix không chứa dữ liệu tương lai hay gợi ý từ người tuyển chọn; draft và human acceptance được phân biệt.
- `docs/status.md` phản ánh công việc thật; không báo cohort/nhãn/feasibility đã được chấp nhận khi còn thiếu bằng chứng.

## 8. Lời giao việc ngắn để dán vào Antigravity

> Làm tiếp dự án tại `H:\EventCaption-AI`. Đọc `AGENTS.md`, `docs/plan.md`, `docs/status.md`, rồi thực hiện `docs/antigravity-next-stage.md`. Bắt đầu từ 30 ứng viên và video đã tải trong `runs/pilot-selection-01/`. Ưu tiên duyệt nội dung, xử lý bốn dự phòng P17–P20, chuẩn bị staging quyền/nguồn và gói gán nhãn prefix đúng hợp đồng. Dùng output mới và bảo toàn dữ liệu cũ. Tiếp tục các việc CPU có thể làm; báo cụ thể những bằng chứng cần người cung cấp. Không giả lập human acceptance, không tự khởi chạy GPU/huấn luyện, không thêm backend/frontend/UI. Kết thúc bằng artifact và trạng thái thực tế.
