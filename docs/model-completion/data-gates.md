# Ràng buộc dữ liệu và nhãn

Nguồn quy định: [data](../reference/data.md), [hướng dẫn nhãn](../guides/annotation-next-step-vi.md), quyết định mới nhất trong [status](../status.md). Đọc quyết định mới trước khi áp dụng trạng thái cũ trong hướng dẫn.

## Trước khi chia tập và dispatch

- Lưu nguồn gốc, SHA-256 thực, session, họ tình huống và cửa sổ đã chọn. ID/hash khác nhau hoặc không tìm thấy ảnh trùng không chứng minh độc lập.
- Chia nhóm nguồn/session/family và gần trùng trước khi tạo checkpoint. Không bịa metadata còn thiếu hoặc tự chuyển nguồn bị chặn train sang dev/test.
- Pilot thuộc dev. Mục tiêu 150 video, 90/30/30 train/dev/test và ba nhóm cảnh là kế hoạch, chưa phải dữ liệu hiện hữu. Final test không dùng chọn prompt, model hoặc recipe.
- Quyền coursework đã được người dùng xác nhận cho nguồn Drive trong phạm vi nội bộ annotation/train/eval. Kế thừa quyết định này đúng phạm vi; không mở lại giấy tờ đã đóng, không suy ra quyền phân phối công khai/thương mại hoặc quyền cho nguồn mới ngoài phạm vi.
- Content PASS, usage PASS, split hợp lệ, nhãn được chấp nhận và quyền handoff là các điều kiện riêng. Chỉ dispatch khi protocol, exposure từng người × clip, cách ly hai máy thực tế và prefix đã đủ bằng chứng theo hướng dẫn nhãn.

## Causal annotation

- Pass 1 chỉ xem prefix tăng dần cùng trạng thái trước đó được phép. Không đưa tiêu đề tiết lộ, caption cũ, ghi chú curator, full clip hoặc đáp án Pass 2 vào input.
- Người/agent đã xem tương lai không làm blind Pass 1 trên nguồn/cửa sổ đó hoặc bản cắt lại tương đương. Exposure `unknown` không phải `unexposed`; không gửi full clip để kiểm tra trí nhớ.
- Pass 2 xem toàn clip riêng sau khi quyết định Pass 1 đã khóa; không sửa hồi tố quyết định cũ bằng kiến thức tương lai.
- Giữ clip/source timeline mapping và kiểm chứng frame thực không vượt cutoff; timestamp danh nghĩa và hash không thay thế kiểm chứng nội dung/PTS.
- Tách cutoff nguồn, thời điểm đủ bằng chứng và thời điểm phát/hiển thị. Ghi độ phân giải checkpoint và bất định thời gian; không bịa độ chính xác.
- WAIT chỉ là trace. Che khuất tạm thời không tự chứng minh hoàn tất; che khuất hoặc hoàn tất không tự làm caption trước đó sai.

## Trước khi prepare dữ liệu train/dev

- Nhãn có người chấp nhận thật, danh tính và phạm vi rõ ràng; thời gian không nhớ để null/unknown. AI draft, JSON hợp lệ và hash đúng không chứng nhận ngữ nghĩa.
- Giữ context và target riêng; đúng manifest/annotation schema hiện có. Không thêm trường hoặc sửa schema chỉ để vượt validator.
- Kiểm tra quyền đúng split, source/media hash thực, đường dẫn và provenance frame. Chạy validate theo [training](../guides/training.md); prepare sang output mới.
- Kiểm kê action và action-pair để nhận ra thiếu dữ liệu. Bổ sung nhãn thật nếu cần; không chế WAIT/REVISE/WITHDRAW để đủ số lượng.
- Giữ mọi phán xét và bất đồng; final test có hai reviewer độc lập, ẩn tên model/cấu hình. Giữ media và bằng chứng riêng tư ngoài Git.

Khi sự cố xảy ra, bảo toàn phiên cũ và log. Phiên thay thế dùng liên kết supersedes theo quy trình; không sửa log tại chỗ để vượt replay hoặc cho người đã phơi nhiễm gán nhãn lại từ đầu như chưa biết tương lai.
