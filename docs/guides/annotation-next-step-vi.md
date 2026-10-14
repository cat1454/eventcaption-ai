# Hướng dẫn bắt đầu nhãn thật cho fine-tuning

Ngày 2026-10-12. Hiện chưa có nhãn được nghiệm thu. Đây là hướng dẫn thực hiện và
yêu cầu đầu ra, không phải biên bản mở cổng. Không cần thêm chữ ký khoa/giảng viên;
cần bằng chứng kỹ thuật và người chịu trách nhiệm cho dữ liệu, nhãn của nhóm.

**Việc trước mắt:** chuẩn bị một phiên prefix hợp lệ, thực hiện Pass 1 rồi Pass 2,
nghiệm thu nhãn và xuất dữ liệu đúng schema. Chưa train chỉ vì đã có video hoặc JSON.
Trainer phương án A đã có; xem [training.md](training.md).

## 1. Phân vai và xác định người được xem

| Vai trò | Việc làm | Được xem |
|---|---|---|
| Coordinator | Quản lý nguồn, split, cắt prefix, phát checkpoint, giữ log/version | Toàn bộ nguồn và hồ sơ |
| Người Pass 1 | Quyết định WAIT/EMIT/REVISE/WITHDRAW theo prefix | Chỉ prefix đã cấp, trạng thái trước đó được phép |
| Người Pass 2/reviewer | Kiểm tra nội dung, interval, căn cứ, bất đồng và nghiệm thu | Toàn clip sau khi Pass 1 của clip đó đã khóa |

Coordinator có thể kiêm reviewer trong phạm vi bài môn học. Người đã xem toàn clip
không được quay lại đóng vai người Pass 1 chưa biết tương lai cho clip đó.
Final test vẫn giữ yêu cầu hai reviewer độc lập theo [data.md](../reference/data.md).

“Chưa phơi nhiễm” nghĩa là trước Pass 1, người đó chưa xem đoạn sau checkpoint đầu,
video đầy đủ, đoạn kết, tiêu đề tiết lộ hành động/kết quả, caption cũ hay ghi chú curator
của clip. Xét **từng người × từng clip**, không tự gán đủ điều kiện cho toàn bộ cohort.
Một người đã xem clip A vẫn có thể phù hợp với clip B chưa từng tiếp xúc.

Cách làm:

1. Coordinator dùng mã trung tính hỏi người được đề xuất về việc đã xem clip/hồ sơ;
   không gửi toàn clip hoặc tên nguồn để “kiểm tra có nhớ không”. Không chắc thì ghi `unknown`.
2. Đối chiếu lịch sử chia sẻ/quyền truy cập sẵn có. Lời tự khai là một căn cứ, không chứng minh cách ly.
3. Ghi kết quả tối thiểu: `person_id, packet_id, exposure_status, basis, checked_at`.
   Các trạng thái là `unexposed`, `exposed`, `unknown`; chỉ `unexposed` có căn cứ mới đưa vào phân công.
4. Nếu không có người phù hợp với bộ cũ: giữ bộ cũ làm tài liệu curator/dev đang chờ;
   chọn người khác hoặc cohort mới có nguồn đủ điều kiện. Không giả vờ “quên nội dung”.

Trạng thái hiện có: Tuấn đã xem bộ cũ; Mạnh đã đọc metadata bộ cũ; phạm vi Phú chưa xác minh.
Chưa tự phân công ba người này làm Pass 1 bộ cũ. Mạnh tiếp tục tránh nội dung cohort mới:
không gửi tiêu đề, source ID, mô tả hành động hay đoạn kết của cohort mới cho Mạnh.

## 2. Nguồn đủ điều kiện và chia tập trước khi tạo mẫu

Nguồn đủ điều kiện là có căn cứ cụ thể cho cách nhóm định dùng: tạo nhãn, đánh giá,
và nếu thuộc train thì fine-tuning. Có đường dẫn tải hoặc xem được video chưa đủ.
Người phụ trách nguồn ghi đường dẫn căn cứ, phạm vi sử dụng và quyết định theo từng nguồn.
Không suy quyền train từ quyền eval; không tự bật các cờ vì đây là dự án môn học.

Nếu căn cứ bộ cũ không còn, giữ `unresolved` và có thể dùng nguồn khác mà nhóm có
quyền sử dụng rõ ràng, chẳng hạn video tự quay với phạm vi sử dụng được xác nhận.
Không hỏi lại mục thư mục lời mời/điều kiện của Tuấn đã bỏ qua, cũng không đánh dấu nó đã giải quyết.

- P01–P30 là pilot/dev; R01–R02 còn dự bị, chưa tự kích hoạt. Ba packet hiện có không thành train.
- Muốn fine-tuning cần các nguồn/session **train riêng**, có nhãn được nghiệm thu.
- Chia theo nguồn gốc, phiên quay, họ tình huống và bản gần trùng trước khi cắt checkpoint.
  Hai đoạn cùng video/phiên hoặc gần trùng không được chia sang train và dev/test.
- `scene` là một trong `food_drink`, `organizing`, `craft_assembly`.
  `scenario_group` là họ tình huống dùng kiểm tra leakage, không dùng ba tên scene
  cho mọi nguồn ở mọi split: validator chặn scenario_group xuất hiện ở nhiều split.
- Final test không dùng thử prompt, chọn model/recipe, early stopping hoặc huấn luyện.
- Kế hoạch tổng là 90 train / 30 dev / 30 test; đây là kế hoạch, không phải số dữ liệu đã có.

Kế thừa mapping 32 clip hiện có, không làm lại. Tám trường hợp cần adjudication về chữ:
P09, P10, P16, P23, P27, P28, P30, R02. P30 chưa có mốc số đáng tin;
không tự điền 40–45 giây. Chữ hướng dẫn không chứng minh hành động đã xảy ra.
Ghi chú curator và các tầng chữ cũ giữ nguyên nguồn gốc, không chuyển thành nhãn đã duyệt.

## 3. Cách ly tương lai trước khi mở Pass 1

Tách ba vùng: **master** chứa full clip; **coordinator** chứa queue, mapping và log;
**handoff** chỉ có prefix hiện được giao và vùng nộp câu trả lời. Người Pass 1 dùng
tài khoản hạn chế riêng, không có quyền admin/coordinator hoặc quyền rộng qua nhóm.
Không chia sẻ cả thư mục runs, Drive chứa full clip hay toàn bộ thư mục packets cho người đó.
Kiểm tra cả link cũ, thư mục đồng bộ/cache, thumbnail, tên file, lịch sử chia sẻ và đường dẫn trực tiếp.

Prefix phải được cắt vật lý; thanh phát dừng ở giây 5 trên full video không phải cách ly.
Frame PTS phải tăng, mốc đầu đúng, mọi frame <= cutoff. Lưu hash file được giao.
Hash khớp chỉ xác nhận bytes, không tự chứng minh timestamp hay quyền truy cập.

Diễn tập bằng dữ liệu giả ở boundary mới theo
[ACL_REHEARSAL.md](../../runs/ai-cpu-preparation-20261012-v1/ACL_REHEARSAL.md).
Công cụ là [verify_acl_permissions.ps1](../../runs/pilot-selection-10/rehearsal/verify_acl_permissions.ps1):
coordinator SetupFixture rồi AuditACL; LiveUser phải chạy bằng tài khoản annotator thật.
Chỉ áp quyền trên fixture được chỉ định trong diễn tập; không chạy thử sửa/xóa trên media thật.
Dùng tham số đường dẫn/identity/RunId/receipt mới tường minh, không dùng mặc định run cũ.

| TestID LiveUser | Phép thử | Kết quả cần có |
|---|---|---|
| T1 | Đọc prefix được giao | ALLOW |
| T2a | Tạo submission mới | ALLOW |
| T2b | Cập nhật submission chưa nộp khóa | ALLOW |
| T3a, T3b | Sửa, xóa prefix | ACCESS_DENIED |
| T4a, T4b | Sửa, xóa session marker | ACCESS_DENIED |
| T5a, T5b | Sửa, xóa checkpoint metadata | ACCESS_DENIED |
| T6a, T6b | Liệt kê master, đọc trực tiếp full clip | ACCESS_DENIED |
| T6c, T6d | Liệt kê coordinator, đọc trực tiếp decisions | ACCESS_DENIED |

Đủ đúng **13 ID**, mỗi ID một lần; không FAIL/ERROR/UNVERIFIED; exit code 0.
Thiếu file không phải ACCESS_DENIED. ReadOnly không thay thế NTFS ACL.
Lưu manifest fixture, SID thực thi, hash script/engine/manifest, receipts AuditACL/LiveUser,
stdout/stderr và exit code. AuditACL có bộ ID riêng, không thay LiveUser.

Fixture PASS chỉ chứng minh fixture đó. Trước media thật, kiểm tra boundary/kênh giao thực tế
dưới đúng tài khoản: đọc được prefix hiện tại, không đọc được master/coordinator/future prefix,
không thay dữ liệu đã khóa. Kiểm tra thao tác phá hủy bằng bản sao giả trong boundary tương đương;
không sửa/xóa bản thật để chứng minh. Không có bằng chứng boundary thật thì chưa mở phiên.
Hướng dẫn này không thực hiện đổi ACL hay chuyển tài khoản.

## 4. Một phiên gán nhãn thực hiện như thế nào

**Trước phiên:** coordinator ghi phiên bản rubric, quy tắc event matching và tolerance
timestamp nhóm sẽ dùng; chưa thống nhất thì chưa nghiệm thu. Dùng quy tắc hiện có,
không tự thêm ngưỡng chấp nhận. Tạo session/output mới, ghi người xem và hash nguồn.
Ba packet [staging hiện có](../../runs/annotation-input-staging-20261012-v1/README.md)
chỉ dùng coordinator kiểm tra, chưa phải session đã được phép hoạt động.

**Pass 1 — từng checkpoint theo thứ tự:**

1. Giao prefix đầu đến 5000 ms với mã trung tính. Đầu phiên chưa có record hay memory.
2. Người xem chỉ dựa trên phần được cấp và trạng thái trước: đang quan sát được sự kiện gì,
   có đủ căn cứ phát/sửa/thu hồi không? Chỉ ra frame/timestamp hỗ trợ, không suy từ tiêu đề.
3. Nộp một quyết định đúng schema. Ghi lý do/bất định vào sidecar review, không nhét vào target JSON.
4. Coordinator kiểm tra JSON, cutoff, evidence và record link; lưu payload gốc, kết quả kiểm tra,
   thời điểm nộp/khóa và hash. Payload lỗi giữ lại. Chưa được chấp nhận thì chưa cấp prefix tiếp.
5. Sau khi quyết định được ghi bền vững/khóa, mới giao prefix 10000 ms, rồi 15000 ms…
   đến đúng thời lượng clip, kể cả checkpoint cuối ngắn hơn 5 giây. Giữ append-only.
6. Lặp tới hết clip rồi khóa Pass 1. Nếu lộ tương lai: dừng, giữ log/sự cố; không tiếp tục
   tính là mù. Phiên thay thế dùng ID mới và liên kết supersedes; đổi người khi cần làm lại.

Dispatcher hiện có API `CoordinatorDispatcher` trong `src/eventcaption_ai/dispatch.py`;
không có CLI dispatch để tự suy ra lệnh `python -m ... dispatch`. Khi vận hành dùng wrapper
đã kiểm tra/API hiện có; chuẩn bị wrapper nếu môi trường chưa có. Không phát thủ công toàn
queue để thay quy tắc khóa trước khi cấp tiếp. Hướng dẫn không tuyên bố staging đã tích hợp dispatch.

**Pass 2 — chỉ sau khi Pass 1 của clip đã khóa:** reviewer xem full clip, đánh dấu sự kiện,
interval, tính đúng của caption, mức đủ bằng chứng và lỗi. Giữ riêng nhãn tham chiếu full-video.
Không sửa ngược quyết định Pass 1 cho “đẹp” sau khi biết kết quả. Ghi bất đồng và quyết định
nghiệm thu riêng. Chỉ mẫu được chấp nhận dựa trên context nhân quả tương ứng mới vào export;
mẫu không đạt giữ trong hồ sơ loại trừ, không gán `verified_by_human=true`.

## 5. Quy tắc cho bốn hành động và thời gian

| Action | Khi dùng | Ràng buộc |
|---|---|---|
| WAIT | Chưa đủ căn cứ hoặc không cần cập nhật có căn cứ | Chỉ `{"action":"WAIT"}`; không caption hiển thị |
| EMIT | Nhận ra một sự kiện mới đủ căn cứ quan sát | Caption tiếng Anh; `previous_record_id=null` |
| REVISE | Có căn cứ sửa nội dung/interval/trạng thái của cùng sự kiện | Trỏ record hiện hành mới nhất, tạo version mới |
| WITHDRAW | Có bằng chứng khẳng định trước đó sai/không được hỗ trợ | Trỏ record hiện hành; giữ start/end/status của record đó |

Caption ngắn, trung tính theo rubric, thường 1–2 mệnh đề và tối đa 25 từ;
validator cấu trúc còn giới hạn text 500 ký tự. Không dự báo hoặc suy ý định.
Không bắt buộc chờ sự kiện kết thúc mới EMIT. Occlusion không chứng minh kết thúc;
kết thúc hoặc ra khỏi khung hình không tự là lý do WITHDRAW. Khi chưa có cập nhật
được hỗ trợ thì WAIT và giữ lịch sử; không kéo dài interval qua khoảng bị che/cắt cảnh.

`previous_record_id` là **Record ID**, không phải Event ID. REVISE/WITHDRAW không
được trỏ phiên bản cũ hay record đã withdraw. Thiếu record trước thì không tạo mẫu cập nhật.

| Trường/mốc | Nghĩa | Chưa biết xử lý thế nào |
|---|---|---|
| cutoff_ms | Giới hạn thời gian clip đã cấp | Phải có và kiểm chứng |
| start_ms/end_ms | Khoảng sự kiện quan sát được | ongoing: end_ms=null; ended: start<=end<=cutoff |
| sufficient evidence | Lúc có đủ bằng chứng, không phải lúc sự kiện bắt đầu | Ghi khoảng bất định ở sidecar |
| emission | Lúc hệ thống phát bản ghi trên đồng hồ phiên | Chưa chạy hệ thống thì chưa đo |
| display | Lúc bản ghi thực sự hiển thị | Không thay bằng emission hoặc thời gian nộp nhãn |

Nếu checkpoint 5s chưa đủ và 10s đủ, chỉ biết mốc đủ bằng chứng trong (5000,10000].
Không tự lấy 7500. Checkpoint đầu dùng [0,5000]; chưa kiểm tra checkpoint trước thì
không tự khẳng định cận dưới. Giữ quy ước mở/đóng cận trong sidecar. Không chèn các
trường này vào hợp đồng. Đo latency sau này cần ánh xạ M(t) giữa clip và đồng hồ phiên;
thiếu display thì chưa kết luận p95 <=5s. Mẫu gán nhãn không phải phép đo iPhone.

## 6. Yêu cầu đầu ra bàn giao

Mỗi đợt tạo thư mục mới dưới `runs/annotation-<batch>-v1/`, không ghi đè staging hoặc
gói cũ. Đây là bố cục bàn giao đề xuất; không phải tất cả tên tệp đều do tool tự sinh.

| Tệp/thư mục | Nội dung bắt buộc | Ai được nhận |
|---|---|---|
| coordinator/eligibility.csv | person/packet, trạng thái phơi nhiễm, căn cứ, thời điểm | Coordinator/reviewer |
| coordinator/source-review.json | Nguồn, segment, hash, căn cứ sử dụng, phạm vi train/eval, quyết định thực | Coordinator/reviewer |
| coordinator/isolation/ | Fixture và kiểm tra boundary thực tế; SID/hash/receipt/log/exit code | Coordinator |
| coordinator/protocol.json | Phiên bản rubric, event matching, tolerance đã thống nhất | Coordinator/reviewer; hướng dẫn trung tính cho Pass 1 |
| sessions/ | Session metadata, log phát/nhận/khóa, raw submissions, mọi record/version/link, sự cố | Coordinator |
| handoff/ | Chỉ đầu vào hiện tại được cấp và vùng nộp | Người Pass 1 tương ứng |
| review/pass2.json | Reference full-video, interval/bất định, nhận xét ngữ nghĩa | Reviewer/coordinator |
| review/acceptance.json | Reviewer, sample/session/checkpoint, accept/reject/pending, lý do, hash bản duyệt | Reviewer/coordinator |
| export/sources.json | Manifest đúng trường của data.py, nguồn đủ điều kiện, split cố định | Pipeline có quyền |
| export/dev-labels.json hoặc train-labels.json | Chỉ annotation đã nghiệm thu của một split | Pipeline có quyền |
| export/media.json + sources/ + prefixes/ | Media index, nguồn thực, PNG có hash và provenance timestamp | Pipeline có quyền |
| report.json | Số nguồn/mẫu theo split, bốn action, chuyển trạng thái, thiếu/loại/lỗi | Nhóm; lọc thông tin gây phơi nhiễm |
| hashes.json | Đường dẫn tương đối và SHA-256 tệp đầu vào/đầu ra đã khóa | Coordinator |

Không gửi cả gói coordinator/export cho người Pass 1 đang làm dở. Hash được đo từ
tệp thật; chưa có thì ghi pending ở hồ sơ chuẩn bị, không điền hash giả vào export.
Không đưa media/nhãn cá nhân/căn cứ riêng tư vào Git.

**Schema export chính xác:**

- `sources.json`: mảng object có đúng `source_id, sha256, origin_id, session_id,
  scenario_group, split, scene, duration_ms, training_allowed, evaluation_allowed,
  license_evidence, pilot`. Media nguồn phải khớp hash; segment 30–60 giây.
- `*-labels.json`: mảng object có đúng `source_id, verified_by_human, annotator, context, target`.
  Reviewer/acceptance nằm sidecar; không thêm vào annotation khiến validator từ chối.
- `context`: đúng `cutoff_ms, evidence, frames, memory, active_events`.
  `evidence` là map ID→timestamp clip; frame có `evidence_id, media_ms, path`.
  Memory có `text, evidence`; active event có `record_id, text, start_ms, end_ms,
  event_status, evidence_refs`. Target đặt riêng, không lọt vào prompt.
- Tối đa 4 PNG trong một input, cùng kích thước, mỗi ảnh không quá 1920×1080 RGB bytes;
  context hữu hạn tối đa 16 events / 16 KiB theo pipeline. PNG thật và timestamp phải có
  provenance giải mã, không chỉ hash. Mọi evidence <=cutoff và ID phải khớp registry.
- Nhãn nhìn toàn prefix không tự tương đương nhãn trên bốn frame cuối. Reviewer kiểm tra
  target được hỗ trợ bởi frame + memory + active state thực sự cấp cho mô hình.
  Không chép hiểu biết tương lai từ Pass 2 vào memory; thiếu evidence thì giữ mẫu ngoài export.

Target ví dụ dưới đây chỉ minh họa schema, **không phải nhãn ba packet hiện có**.
Ví dụ giả định evidence `frame:15` đã được cấp tại 1000 ms, cutoff >=1000 ms;
record `r001`/`r002` chỉ là ID minh họa, không được sao chép vào dữ liệu thật.

```json
{"action":"WAIT"}
```

```json
{"action":"EMIT","text":"A person moves a cup.","start_ms":1000,"end_ms":null,"event_status":"ongoing","evidence_refs":["frame:15"],"previous_record_id":null}
```

```json
{"action":"REVISE","text":"A person lifts a cup.","start_ms":1000,"end_ms":null,"event_status":"ongoing","evidence_refs":["frame:15"],"previous_record_id":"r001"}
```

```json
{"action":"WITHDRAW","text":"The earlier cup-lifting claim is unsupported.","start_ms":1000,"end_ms":null,"event_status":"ongoing","evidence_refs":["frame:15"],"previous_record_id":"r002"}
```

Các ví dụ là độc lập về tình huống bằng chứng, không chứng minh frame đó đủ căn cứ
cho cả chuỗi. WITHDRAW chỉ hợp lệ về interval khi record trước cũng có start=1000,
end=null, status=ongoing. Reviewer phải kiểm tra ý nghĩa, lý do và evidence thật.

## 7. Kiểm tra bàn giao và bước sau đó

Coordinator/reviewer chỉ chấp nhận mẫu khi: nguồn và split đúng; người Pass 1 đủ điều kiện;
cách ly có bằng chứng; log cho thấy khóa trước phát tiếp; JSON và version links hợp lệ;
caption/interval có căn cứ trong input; người nghiệm thu đã ghi quyết định thực.
Không tự cân bằng bốn action bằng cách đổi WAIT sang REVISE/WITHDRAW.

Báo đủ số WAIT/EMIT/REVISE/WITHDRAW, số thiếu, chuỗi action liền nhau và kiểm tra
chuyển trạng thái theo event/version. Action-pair counts do trainer báo chỉ là thống kê
liền nhau, không tự chứng minh mọi transition hợp lệ. Báo số lỗi link, interval, semantic,
số mẫu pending/reject và lý do; không tính pending vào accepted.

Sau khi đã có export hợp lệ, kiểm tra CPU từ repo root (môi trường đã có):

```powershell
$env:PYTHONPATH = 'src'
$env:CUDA_VISIBLE_DEVICES = ''
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Thay BATCH bằng đường dẫn đợt đã nghiệm thu; chưa có thì không chạy các lệnh dưới.
.\.venv-train\Scripts\python.exe -m eventcaption_ai.training validate --manifest runs/BATCH/export/sources.json --annotations runs/BATCH/export/dev-labels.json --media-index runs/BATCH/export/media.json --split dev
# Chỉ prepare khi validate thành công; output phải là thư mục chưa tồn tại.
.\.venv-train\Scripts\python.exe -m eventcaption_ai.training prepare --manifest runs/BATCH/export/sources.json --annotations runs/BATCH/export/dev-labels.json --media-index runs/BATCH/export/media.json --split dev --output runs/prepared-dev-BATCH-v1
```

`validate` không tải model hay gọi GPU. Nó kiểm tra cấu trúc/gates/hashes nhưng không
chứng nhận ngữ nghĩa, quyền sử dụng hoặc danh tính reviewer. Không chỉ sửa boolean để qua kiểm tra.
Đối với train, dùng nguồn train riêng và `train-labels.json`, `--split train`; không đổi
cờ split của pilot. Resource pilot chỉ mở khi có train hợp lệ và ngân sách đã đối soát.
Main training thêm recipe khóa và kiểm tra iOS tối thiểu. Mỗi GPU run có reservation riêng,
tối đa 4 giờ gồm load, chung 40 giờ; lịch sử chưa rõ vẫn để unknown, không giả định số dư.

Kết quả cần đạt của đợt nhãn đầu là **nhãn thật có thể truy nguyên và export CPU hợp lệ**.
Ba prefix đầu chưa có record trước nên chưa đủ kiểm tra học REVISE/WITHDRAW;
cần chuỗi checkpoint thực và các trường hợp cập nhật có căn cứ. Chưa có bằng chứng đó
thì báo thiếu. JSON hợp lệ/loss giảm không thay cho chất lượng caption hoặc khả thi iOS.
