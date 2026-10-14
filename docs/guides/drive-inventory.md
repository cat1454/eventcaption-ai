# Kiểm kê video Google Drive trên Windows

Công cụ chỉ đọc metadata bằng Google Drive API, không tải video hoặc đọc nội dung
annotation, không sửa Drive, không gọi model/GPU. Phân trang cho phép kiểm kê hơn
1.000 file và tự duyệt thư mục con. Danh sách này phục vụ chọn nguồn pilot;
không chứng nhận nhãn, quyền sử dụng, chất lượng model hoặc tính khả thi iOS.

## 1. Tạo cấu hình Google một lần

1. Mở [Google Cloud Console](https://console.cloud.google.com/), tạo hoặc chọn project
   riêng, ví dụ `EventCaption Inventory`.
2. Vào **APIs & Services → Library**, tìm **Google Drive API**, bấm **Enable**.
3. Vào **Google Auth Platform → Branding**, cấu hình tên ứng dụng, email hỗ trợ
   và email liên hệ. Với Gmail cá nhân, chọn **External** trong **Audience**,
   giữ chế độ **Testing**, thêm chính tài khoản sẽ đọc folder vào **Test users**.
4. Trong **Data Access**, thêm duy nhất scope:
   `https://www.googleapis.com/auth/drive.metadata.readonly`.
5. Vào **Clients → Create client → Desktop app**. Tải JSON cấu hình OAuth.
6. Tạo thư mục riêng bằng PowerShell:

   ```powershell
   $driveAuthDir = Join-Path $env:LOCALAPPDATA 'EventCaption-AI\google-drive'
   New-Item -ItemType Directory -Force -Path $driveAuthDir
   ```

   Dùng File Explorer đặt file tải về tại
   `%LOCALAPPDATA%\EventCaption-AI\google-drive\credentials.json`.
   `token.json` sẽ được tạo cùng thư mục sau khi đăng nhập. Không gửi hai file này
   vào chat hoặc đưa vào Git. Nếu đã có cấu hình ở đây, giữ nguyên và chọn tên
   khác rồi truyền `--credentials` / `--token`.

Scope metadata có thể đọc metadata của các file tài khoản được phép truy cập;
đây không phải quyền OAuth giới hạn vào một folder. Công cụ tự giới hạn truy vấn
vào root đã chọn và các thư mục con. Scope không cấp quyền đọc nội dung hay sửa file.
Không cần mount Drive hoặc cấp scope `drive` / `drive.readonly`.

Tham khảo [Python quickstart](https://developers.google.com/workspace/drive/api/quickstart/python)
và [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## 2. Cài và chạy

Mở PowerShell tại `H:\EventCaption-AI`. Dùng môi trường riêng, không thay môi trường
thí nghiệm lịch sử. Nếu `.venv-drive` đã có, dùng lại; không tạo đè:

```powershell
Set-Location H:\EventCaption-AI
py -3.12 -m venv .venv-drive
.\.venv-drive\Scripts\python.exe -m pip install -e ".[drive]"
.\.venv-drive\Scripts\python.exe -m eventcaption_ai.drive_inventory --help
```

Kiểm kê folder đã chọn trong phiên này, bao gồm các thư mục con:

```powershell
.\.venv-drive\Scripts\python.exe -m eventcaption_ai.drive_inventory --folder "https://drive.google.com/drive/folders/1sOdWrfxWjxr9vQdAaj3fnMxJGChyYS5v" --output runs/drive-inventory-01
```

Đây cũng là folder mặc định nếu bỏ `--folder`. Muốn kiểm kê cả thư mục cha đã gửi
trước đó, dùng ID `1tZT0JEjc9oBnkdA7l2OXSCJ06ZNWk26z` và output mới.

Lần đầu, trình duyệt mở trang đăng nhập Google. Chọn tài khoản có quyền xem folder,
kiểm tra ứng dụng và quyền metadata rồi chấp thuận. Script nhận phản hồi qua
localhost, chờ tối đa 5 phút; không cần sao chép mã/token vào terminal hoặc chat.

Có thể chỉ định đường dẫn cấu hình khác:

```powershell
.\.venv-drive\Scripts\python.exe -m eventcaption_ai.drive_inventory --credentials "$env:LOCALAPPDATA\EventCaption-AI\google-drive\credentials.json" --token "$env:LOCALAPPDATA\EventCaption-AI\google-drive\token.json" --output runs/drive-inventory-02
```

Không cần bật GPU hay cài inference dependencies.

## 3. Đọc kết quả

| File | Nội dung |
| --- | --- |
| `inventory.jsonl` | Metadata nguyên bản của root và các mục duy nhất đã gặp; mỗi dòng một file/folder, không sửa tên hay điền dữ liệu thiếu. |
| `videos.csv` | Chỉ file MIME `video/*`; UTF-8 BOM để mở trong Excel. Có ID, tên, link, parent IDs, byte, thời gian sửa, duration tính bằng ms, kích thước khung hình và checksum nếu Drive cung cấp. |
| `summary.json` | Phiên bản `drive-inventory/1`, root, thời gian UTC, số trang/folder/file/video, trùng ID, shortcut, lỗi và `complete`. |

Trường thiếu được để trống, không suy ra duration từ tên hoặc dung lượng. CSV thêm
dấu nháy đơn trước giá trị có thể bị Excel hiểu thành công thức; JSONL giữ bản gốc.
Khử trùng bằng **file ID**, không bằng tên; hai file khác ID cùng tên vẫn được giữ.
`files` là số mục không phải folder; `folders_discovered` tính cả root.
Shortcut được ghi metadata và đếm riêng, không duyệt đích, kể cả shortcut tới video.

`complete=true` nghĩa là duyệt hết mọi trang của cây folder thật mà API cho tài khoản
thấy, không còn lỗi hoặc `incompleteSearch`; không bao gồm đích shortcut hay file
không được chia sẻ cho tài khoản. Kiểm kê không phải snapshot nguyên tử: tránh thay
đổi cấu trúc folder trong lúc chạy. Mỗi lần chạy dùng output mới, không ghi đè hoặc
tiếp tục nối vào lần trước.

Mã thoát: **0** hoàn tất; **1** chưa hoàn tất (đọc kết quả một phần và lỗi trong
summary); **2** sai tham số, thiếu cấu hình ban đầu hoặc không thể tạo/ghi output.
Kết quả được flush sau từng record. Ctrl+C thông thường vẫn ghi summary chưa hoàn
tất; nếu tắt tiến trình cưỡng bức hoặc mất điện thì có thể thiếu summary. Không có
summary hoàn tất thì không coi là kiểm kê xong.

Sau khi chạy, có thể đưa `videos.csv` và `summary.json` cho bước lựa video. Chúng
không chứa token nhưng có tên/ID/link file, nên vẫn giữ local trong `runs/` (đã ignore).
Việc đối chiếu caption cũ và xem nội dung video là bước riêng; công cụ này chưa làm.

## 4. Xử lý lỗi

- `ModuleNotFoundError`: chạy lại lệnh cài `.[drive]` bằng đúng Python của `.venv-drive`.
- `FileNotFoundError` lúc xác thực: kiểm tra file OAuth JSON, loại Desktop app và
  đường dẫn; cache token hết hạn có thể cần OAuth client để đăng nhập lại.
- `access_denied`: kiểm tra đúng tài khoản, Test users và chính sách Workspace.
- `RefreshError`: token có thể đã hết hạn hoặc bị thu hồi. Giữ bản cũ riêng và chạy
  với `--token` trỏ tới tên file mới để đăng nhập lại; không mở rộng scope.
- `ValueError` lúc xác thực: kiểm tra token dành riêng cho scope metadata; không
  tái sử dụng token quyền rộng hơn. Tạo đường dẫn token mới nếu cần.
- HTTP **403/404**: kiểm tra tài khoản có quyền đọc folder. Công cụ ghi lỗi và giữ
  phần đã đọc; lỗi quyền không được tự coi là thư mục trống.
- HTTP **429**, **5xx**, hoặc **403 rateLimitExceeded/userRateLimitExceeded**:
  tối đa 5 lần thử/request, backoff lũy thừa có jitter. Hết lượt thì báo chưa hoàn tất.
- `incompleteSearch` hoặc `repeatedPageToken`: giữ kết quả nhưng không đánh dấu hoàn
  tất; chạy lại với output mới sau khi kiểm tra nguồn. Token phân trang không hợp
  lệ cũng kết thúc folder với lỗi, không bỏ qua trang.
- `summary.json` không ghi nguyên thông báo OAuth/HTTP hoặc request URL để tránh
  lộ thông tin xác thực; chỉ ghi loại lỗi, HTTP status, reason và folder liên quan.

Thiết kế phân trang theo [files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list),
retry theo [hướng dẫn lỗi Drive](https://developers.google.com/workspace/drive/api/guides/handle-errors).

## Kiểm thử phần mềm

`tests/test_drive_inventory.py` dùng API/OAuth giả lập, bao gồm hơn 2.000 video,
trang rỗng có token, thư mục con, trùng ID, metadata thiếu, retry và lỗi truy cập.
Không đăng nhập, gọi API thật, tải model hoặc dùng GPU trong CI. Passing tests
không thay thế việc chạy inventory thật sau khi người dùng hoàn tất OAuth.
