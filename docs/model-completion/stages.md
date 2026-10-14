# Lộ trình S0–S7 — ưu tiên demo policy trên PC

Mục tiêu đầu tiên: đưa video vào, model xử lý tuần tự và tự quyết định WAIT/EMIT/REVISE/WITHDRAW bằng policy đã học, có caption và lịch sử để kiểm tra. Mục tiêu cuối giữ nguyên: hoàn thiện nghiên cứu và chạy trực tiếp trên iPhone 16 Pro.

Snapshot khởi tạo **14/10/2026 (Asia/Bangkok)**, dựa trên mục “Replacement recruitment intake checked” trong [status](../status.md). Lần khởi tạo chỉ tạo tài liệu theo dõi, chưa thực hiện stage hay mở gate. Đọc [plan](../plan.md) và status mới nhất trước khi hành động.

## Bảng tiến độ chính

| Stage | Mốc đầu ra | Trạng thái | Hoàn tất / tổng | Phụ trách theo vai trò | Cập nhật |
|---|---|---|---|---|---|
| [S0](#s0) | Xác nhận baseline phần mềm | Hoàn tất | 3/3 | AI | 14/10/2026 |
| [S1](#s1) | Dữ liệu và tài nguyên đủ điều kiện | Bị chặn | 0/4 | Coordinator + compute | 14/10/2026 |
| [S2](#s2) | Batch nhãn thật train/dev | Chưa bắt đầu | 0/4 | Annotator + reviewer + AI | 14/10/2026 |
| [S3](#s3) | Demo policy đã học trên PC | Chưa bắt đầu | 0/4 | AI + reviewer | 14/10/2026 |
| [S4](#s4) | Feasibility iOS và recipe lock | Chưa bắt đầu | 0/4 | AI + nhóm iOS | 14/10/2026 |
| [S5](#s5) | Main training A/B và baseline | Chưa bắt đầu | 0/4 | Nhóm dữ liệu + AI | 14/10/2026 |
| [S6](#s6) | Chọn và đóng băng model trên dev | Chưa bắt đầu | 0/4 | AI + evaluator | 14/10/2026 |
| [S7](#s7) | Final test và nghiệm thu iPhone | Chưa bắt đầu | 0/4 | Reviewer độc lập + iOS + AI | 14/10/2026 |

S0 “Hoàn tất” xác nhận baseline implementation và CPU checks cho scope phần mềm; không có nghĩa model đã được train, đạt chất lượng hay chạy được trên iPhone. Vai trò chưa nêu tên là chưa phân công danh tính, không phải người đã nhận việc.

**Đường ưu tiên: S0 → S1 → S2 → S3 (demo PC đầu tiên).** S4 chuẩn bị song song S1–S3. S5 chỉ mở main training sau S4 và khi dữ liệu, recipe, ngân sách đủ gate. Có thể chuẩn bị dữ liệu mở rộng/tooling B sớm; phần độc lập không phải chờ nhánh đang bị chặn.

## Quy ước cập nhật

- **Chưa bắt đầu:** chưa triển khai stage, ghi dependency còn chờ. **Đang làm:** đang có phần việc thực hiện. **Bị chặn:** thiếu đầu vào cần thiết để hoàn tất bước hiện tại. **Hoàn tất:** mọi checklist và điều kiện đạt có bằng chứng. **Không đạt:** đã đánh giá nhưng thất bại tiêu chí; giữ kết quả.
- Đếm checkbox hoàn tất từng stage, không cộng thành “% model hoàn thiện”. Chạy xong thí nghiệm không tự đồng nghĩa đạt chất lượng.
- Mỗi phiên cập nhật stage bị ảnh hưởng: trạng thái, số đếm, danh tính thực, evidence, blocker, bước tiếp và ngày. Dùng [mẫu báo cáo](progress-checklist.md); thêm lịch sử vào [status](../status.md), ghi phạm vi supersedes nếu có.
- Bằng chứng được tái dùng khi input/config/phạm vi khớp. Link code/hướng dẫn không tự là receipt nghiệm thu. Chưa có artifact ghi “chưa có”, không tạo đường dẫn giả.
- Không mở gate bằng checkbox hoặc đánh dấu hoàn tất vì đã viết báo cáo. Raw artifacts ở output mới; không nhúng media/log dài vào bảng.

<a id="s0"></a>
## S0 — Chốt nền phần mềm

**Phụ trách:** AI. **Điều kiện hoàn tất:** baseline hiện tại có kiểm kê, kiểm tra CPU và lệnh tái lập. Không refactor nền khi không có lỗi cần sửa.

- [x] Kiểm kê video runner, bounded memory, contract/ledger và trainer A; ghi đã có/chưa có, revision hoặc diff nhận diện baseline.
- [x] Chạy kiểm tra CPU liên quan: future-frame isolation, version links, append-only, malformed output, budget/timeout và resume; lưu lệnh, môi trường và kết quả.
- [x] Lưu hướng dẫn tái lập, giới hạn phần mềm và phần B chưa hoàn thiện; phân biệt fixture với real-model replay.

**Bằng chứng nền:** [architecture](../reference/architecture.md), [training](../guides/training.md), [running](../guides/running.md), [báo cáo baseline](software-baseline.md), [receipt JSON](evidence/s0-software-baseline-20261014/software-baseline-receipt.json) và [log CPU](evidence/s0-software-baseline-20261014/pytest-cpu.log).

**Blocker:** không còn blocker trong scope S0. **Bước tiếp:** S1 xử lý grouping/exposure/protocol và đối soát compute; các gate sau vẫn giữ nguyên.

<a id="s1"></a>
## S1 — Mở đường cho dữ liệu và tài nguyên

**Phụ trách:** coordinator + người phụ trách compute. **Điều kiện hoàn tất:** cohort, handoff, ledger và môi trường đủ căn cứ cho bước tương ứng.

- [ ] Chốt cohort đầu tiên, grouping nguồn/session/family, content acceptance và split; kế thừa usage coursework đã PASS đúng phạm vi.
- [ ] Chốt protocol, exposure từng người × clip và cách ly hai máy thực tế; xác minh causal prefixes trước dispatch.
- [ ] Đối soát lịch sử GPU vào ledger chung, gồm reservation chưa đóng, số dư study và quota khả dụng.
- [ ] Ghi môi trường compute/GPU/dependency và checkpoint/revision được phép dùng; checkpoint local được xác minh trước real-model run.

**Bằng chứng nền:** [snapshot blocker](progress-checklist.md), [data gates](data-gates.md), mục “Replacement recruitment intake checked” trong status, dẫn tới `runs/train-recruit-intake-20261014-v1/`. Intake integrity không phải split PASS. **Receipt đóng S1:** chưa có.

**Blocker:** F06 còn adjudication với P08/P09; C08 giữ assistant proposal; các slot chưa đóng source/session grouping, gồm O01. Chibi exposure chưa xác minh; số dư GPU chưa biết. **Bước tiếp:** giải quyết grouping từ hồ sơ hiện có và giao người đối soát ledger; không tuyển lại sáu nguồn hoặc mở lại content review đã đóng.

<a id="s2"></a>
## S2 — Batch nhãn thật đầu tiên

**Phụ trách:** annotator + reviewer + AI. **Điều kiện hoàn tất:** train nhỏ và dev độc lập có nhãn nghiệm thu, chuẩn bị đúng schema. Phụ thuộc nhánh dữ liệu/handoff S1; không bắt gán nhãn chờ GPU nếu đã đủ điều kiện riêng.

- [ ] Thực hiện Pass 1 theo prefix tăng dần, giữ quyết định/evidence append-only và exposure hợp lệ.
- [ ] Thực hiện Pass 2 riêng sau khi khóa Pass 1; reviewer chấp nhận nhãn thật, lưu bất đồng và căn cứ.
- [ ] Kiểm tra split leakage, source/media hashes, timeline/cutoff và provenance; validate rồi prepare train/dev vào output mới.
- [ ] Lưu thống kê action/action-pair, chỗ thiếu nhãn và chuỗi prefix minh họa đã nghiệm thu; không chế nhãn để đủ bốn action.

**Bằng chứng đầu ra:** chưa có; nhãn nghiên cứu được chấp nhận hiện là 0 theo snapshot. Quy trình: [data gates](data-gates.md), [annotation](../guides/annotation-next-step-vi.md), [training](../guides/training.md).

**Blocker/dependency:** cohort, protocol/exposure/handoff S1. **Bước tiếp:** sau khi đủ điều kiện, gán nhãn batch đầu bằng người hợp lệ; không dùng pilot thuộc dev để train.

<a id="s3"></a>
## S3 — Pilot học policy và demo PC đầu tiên

**Phụ trách:** AI + reviewer. **Điều kiện hoàn tất:** checkpoint hoàn chỉnh và demo policy tự vận hành trên video có review rõ; đây chỉ là tính khả thi ban đầu, chưa là chất lượng nghiên cứu đạt chuẩn.

- [ ] Kiểm tra pilot/dev gate và ngân sách theo dataset/config thực; chạy pretrained đối chiếu với điều kiện đã ghi.
- [ ] Chạy pilot LoRA A bằng train được chấp nhận; lưu loss, checkpoint hoàn chỉnh, config/data identity và failures.
- [ ] Replay tuần tự với adapter trên video dev đủ điều kiện, dùng memory/active state do model tự tạo; không dùng target hoặc accepted future context.
- [ ] Đóng gói demo và review: caption/decision timeline, record/version, thời gian xử lý, tài nguyên và lỗi; kết luận có căn cứ về output có ý nghĩa của policy đã học, không chỉ pipeline chạy được.

**Gói bạn xem:** video local/ignored, lệnh replay, checkpoint identity, JSONL/ledger/raw trace và bảng Markdown `cutoff → quyết định → caption → record/version → thời điểm phát → nhận xét reviewer`. Tách cutoff, đủ bằng chứng và wall-clock emission; replay PC không chứng minh realtime/iPhone.

**Bằng chứng đầu ra:** chưa có. Tham chiếu [training gates](training-gates.md), [reference inference](../guides/running.md).

**Blocker/dependency:** S0, batch S2, môi trường/budget S1. **Bước tiếp:** chuẩn bị pilot config từ dữ liệu đủ điều kiện; không chạy trước gate. Nếu chỉ WAIT, sai contract hoặc caption thiếu căn cứ, ghi **“pipeline đã chạy nhưng demo policy chưa đạt”**; không dùng scripted output thay thế. Không buộc một clip phải có đủ bốn action.

<a id="s4"></a>
## S4 — Feasibility iOS và khóa thí nghiệm

**Phụ trách:** AI + nhóm iOS. **Điều kiện hoàn tất:** feasibility iPhone 16 Pro và recipe/rubric khóa trước main training.

- [ ] Ghi device/iOS, Mac/Xcode, runtime; kiểm tra size/load/memory, preprocessing, tokenizer/template, frame ordering/timestamp và context bounds.
- [ ] Kiểm chứng B feature extraction/parity: layer/token pooling, feature shape/dtype/value so với Python.
- [ ] Chọn size/revision trên dev và device feasibility; khóa module targets, loss masking, hyperparameters và generation settings từ resource pilot.
- [ ] Khóa semantic rubric, event matching, time tolerance và thủ tục chọn model; lưu evidence/recipe lock cho main gate.

**Bằng chứng đầu ra:** chưa có feasibility/parity xác thực. Tham chiếu [handoff](../reference/handoff.md), [evaluation](../reference/evaluation.md).

**Blocker/dependency:** lịch nhóm iOS, môi trường/checkpoint và dev; recipe lock chờ resource pilot. **Bước tiếp:** chuẩn bị checklist thiết bị và phân công kiểm tra song song S1–S3. Nếu thiết bị không khả thi, báo không đạt và xem lại scope rõ ràng; không thay bằng server.

<a id="s5"></a>
## S5 — Hoàn thiện dữ liệu và main training A/B

**Phụ trách:** nhóm dữ liệu + AI. **Điều kiện hoàn tất:** dữ liệu, tooling và các run so sánh đủ bằng chứng trong gate/ngân sách.

- [ ] Hoàn thiện cohort 150 video 30–60 giây, 50 mỗi nhóm; split 90/30/30, pilot ở dev, nhãn/nguồn đủ điều kiện. Giữ kín final test khỏi lựa chọn model.
- [ ] Hoàn thiện tooling B và kiểm tra CPU phù hợp; giữ frozen vision ban đầu, đối chiếu feature interface đã kiểm chứng ở S4.
- [ ] Xác minh main receipts bind đúng data/config/ledger và recipe lock; chạy A/B cùng pretrained periodic và fine-tuned periodic baseline trong điều kiện so sánh tương ứng.
- [ ] Lưu checkpoint, raw traces, config, thời gian/GPU ledger và báo cáo dev; giữ run thất bại và kết quả âm tính.

**Bằng chứng đầu ra:** chưa có main runs nghiệm thu; trainer A có theo [training](../guides/training.md), không suy ra B hoàn tất.

**Blocker/dependency:** dữ liệu mở rộng, S3/S4 và main gate. **Bước tiếp:** sau pilot, xác định dữ liệu còn thiếu và hoàn thiện B; chỉ main training khi đủ data/iOS/recipe/budget.

<a id="s6"></a>
## S6 — Chọn model và kiểm tra trên PC

**Phụ trách:** AI + evaluator. **Điều kiện hoàn tất:** chọn model trên dev với semantic review/ablation và đóng băng cấu hình cuối.

- [ ] Chạy autonomous sequential rollout trên dev với input/generation/budget so sánh tương ứng; tách teacher-forced diagnostics.
- [ ] Ablation policy được chọn có/không memory; khai báo active state tối thiểu của no-history, giữ 16 events / 16 KiB cho điều kiện có memory.
- [ ] Review mọi phiên bản đã phát; báo unsupported captions, coverage, duplicates, revision/withdrawal đúng/sai, interval, tài nguyên và bất định theo video/source.
- [ ] Chọn model bằng dev, lưu bảng baseline/candidate, ví dụ đúng/sai và cấu hình đóng băng trước khi mở final test.

**Bằng chứng đầu ra:** chưa có. Tham chiếu [acceptance](acceptance.md). **Blocker/dependency:** S5. **Bước tiếp:** dùng rubric đã khóa chuẩn bị bảng so sánh và cohort dev; không xem final test để điều chỉnh.

<a id="s7"></a>
## S7 — Final test và nghiệm thu thiết bị

**Phụ trách:** reviewer độc lập + nhóm iOS + AI. **Điều kiện hoàn tất:** đạt các ngưỡng và bàn giao bằng chứng. Đo xong nhưng không đạt thì stage là “Không đạt”.

- [ ] Mở final test sau freeze; hai reviewer độc lập, ẩn tên model/config, giữ phán xét/bất đồng/adjudication. Không tái dùng test chọn model.
- [ ] Đo iPhone replay và camera run ≥10 phút; log capture/arrival, sufficient evidence, enqueue/inference completion, record/render time, memory, thermal, errors và clock mapping.
- [ ] Đạt unsupported-caption rate giảm tương đối ≥20%; coverage ≥80% và giảm không quá 5 điểm phần trăm; p95 first-correct-display ≤5.000 ms từ đủ bằng chứng.
- [ ] Bàn giao model/adapter, revision/config, preprocessing/memory, contract/reference inference, báo cáo và giới hạn cùng provenance.

**Bằng chứng đầu ra:** chưa có. **Blocker/dependency:** S6, tích hợp và lịch đo nhóm iOS. **Bước tiếp:** sau freeze, thực hiện protocol test/device đã khóa theo [handoff](../reference/handoff.md).

Tính mọi phiên bản caption; correction không xóa lỗi trước. Báo missing events riêng. Baseline error bằng 0 làm relative reduction không xác định, không tự báo đạt. Không hạ ngưỡng hoặc lấy desktop generation latency thay display latency.

## Lịch, ngân sách và phạm vi kết luận

- Chưa gán hạn hoàn thành khi lịch annotator/compute/iOS chưa rõ. Sau S1 lập lịch dự kiến S2–S4; sau S3 dùng tốc độ thực đo cập nhật S5–S7. Plan 8–12 tuần là dự trù toàn nghiên cứu, không phải thời gian còn lại từ hôm nay.
- Một ngân sách study 40 giờ: feasibility 4h, A 10h, B 10h, ablation 8h, final 4h, reserve 4h; ≤4 giờ/run kể cả load. S0–S7 là stage theo dõi, không phải tám quota mới. Pretrained/pilot feasibility chia chung quota tương ứng.
- Số dư lịch sử chưa xác minh. Reservation chưa đóng vẫn tính; không tự retry, tiêu reserve hoặc tải model. Không GPU/model download trong CI. Mỗi run/resume dùng output mới.
- Không đổi API/schema, không xây backend/frontend/UI. Chỉ mô tả sự kiện quan sát được; WAIT trace-only; không bịa probabilities/keyword repair hoặc dùng che khuất/hoàn tất để tự withdraw.
- Phạm vi người khiếm thị là hiểu hoạt động xung quanh. Caption hiện theo plan là tiếng Anh. Nghiệm thu nghiên cứu chưa chứng nhận trải nghiệm nghe, tính hữu ích với người dùng hoặc an toàn di chuyển.
