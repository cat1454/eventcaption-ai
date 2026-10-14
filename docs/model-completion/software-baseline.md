# Xác nhận baseline phần mềm S0

Ngày kiểm tra: **14/10/2026 (Asia/Bangkok)**. Phạm vi là implementation và kiểm tra CPU hiện có; đây không phải đánh giá chất lượng model hay nghiệm thu thiết bị.

## Inventory implementation

| Năng lực | Hiện trạng trong repository | Giới hạn đã xác nhận |
|---|---|---|
| Video runner | `streaming.video.video_frames` giải mã tuần tự, yêu cầu PTS và dừng theo giới hạn media; reference inference lấy prefix theo cadence, đưa từng snapshot qua `Engine` rồi ghi trace/ledger. | Desktop reference replay; không đo realtime, camera hay iPhone. S0 không chạy video thật với model weights. |
| Bounded memory | `PrefixBuffer` giới hạn số frame, kích thước frame và chỉ chấp nhận timestamp/index tăng; `Engine` giới hạn event memory theo số event và byte. | Full ledger vẫn lưu lịch sử; giới hạn memory model không làm ledger bị cắt. |
| Contract/ledger | `event-caption-v1.schema.json`, strict decision/record validation, SQLite ledger append-only, event/version links, evidence timestamp identity và consumer replay checks đã có. | Contract validity không chứng minh caption đúng ngữ nghĩa. |
| Trainer A | Offline Option A language-side LoRA có preparation/gates, token-boundary masking, checkpoint identity và resume; tests chạy trên CPU với fixtures/tiny network. | Không có accepted research labels hoặc quality result trong S0; các gate training tiếp tục đóng. |
| Option B / iOS | Chưa có bằng chứng hoàn chỉnh về B feature extraction/parity hoặc runtime iPhone. | Không xem test fixture hay package structure là bằng chứng feasibility. |
| Frozen dispatcher | `src/eventcaption_ai/dispatch.py` được giữ nguyên bytes trong đợt tổ chức code; SHA-256 là `4b02c01fa5cad06f1c80cab13d65c57f7a372111841e677cfe3a897fca8a905a`. | Hash xác định file dispatcher trong baseline; không chứng nhận nội dung dispatch đã được nghiệm thu nghiên cứu. |

Các kiểm tra liên quan trong suite bao gồm causal/future-frame isolation, bounded context, version links, append-only records, malformed model output không repair/retry, budget reservation khi lỗi, timeout receipt, trainer resume và dispatcher resume/replay. Các test dùng fixture, synthetic pixels hoặc tiny CPU models; chúng xác minh hành vi phần mềm.

## Cách tái lập

Từ thư mục gốc repository, trên Windows PowerShell, đặt `testRunDir` thành một đường dẫn mới mỗi lần chạy để pytest chỉ xóa thư mục tạm của chính lần chạy đó:

```powershell
$testRunDir = 'runs/s0-software-baseline-rerun-20261015-v1'
New-Item -ItemType Directory -Path $testRunDir
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:CUDA_VISIBLE_DEVICES = ''
.\.venv-train\Scripts\python.exe -m pytest -q --cov=eventcaption_ai --cov-report=term-missing -p no:cacheprovider --basetemp="$testRunDir/pytest-tmp"
```

Kết quả hiện tại: **122 passed**, coverage **85.85%**, gate **80%**, exit code `0`; chạy với Python 3.12.7, pytest 8.3.3 trên Windows. Offline flags được bật và CUDA bị vô hiệu hóa. Bản sao bằng chứng được commit để nhóm mở được trên GitHub: [pytest-cpu.log](evidence/s0-software-baseline-20261014/pytest-cpu.log) và [software-baseline-receipt.json](evidence/s0-software-baseline-20261014/software-baseline-receipt.json). Bản output gốc vẫn được giữ tại `runs/s0-software-baseline-20261014-v1/`.

Receipt ghi HEAD `718de8e7c4ec8daad908baf9b7705da7bd04a99a`, SHA-256 của tracked diff `b25d9f7780281d1c6ddfee6436ad9ab9558a251440354458a997f0c00172127e` và hash inventory các file đã thay đổi/chưa track `9798b0acf363293fb2bb1509bf843f47d2aa181943dc6926c95114a93399b381`. Đây là identity của worktree được kiểm tra; các chỉnh sửa tài liệu S0 được thực hiện sau khi chụp inventory và không làm thay đổi code đã test.

## Kết luận và giới hạn

S0 hoàn tất: inventory, CPU regression check và chỉ dẫn tái lập đều có bằng chứng. Không cần refactor hoặc sửa lỗi phần mềm để đóng S0. Kết quả này **không** chứng minh real-model replay, policy đã học, semantic quality, B parity, iPhone readiness, camera latency hay an toàn sử dụng. S1 vẫn bị chặn bởi source/session grouping, exposure/protocol và số dư compute chưa xác minh; không có budget hay training gate nào được mở trong bước này.
