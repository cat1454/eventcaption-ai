# Làm việc ổn định và tiết kiệm token

Mục đích: giảm đọc lặp và quyết định lại việc đã đóng, đồng thời giữ đủ căn cứ. Đây là quy trình cho coding agent; không thay đổi token/frame budget của SmolVLM2 hoặc làm yếu research gates.

## Đọc và tìm kiếm có phạm vi

1. Đọc plan và status trước theo AGENTS.md. File dài phải đọc theo phần để tránh output bị cắt; không xem phần bị truncate là đã đọc. Khi cùng phiên đã có nội dung, chỉ đọc lại phần thay đổi và các quyết định liên quan.
2. Dùng [README](README.md) để chọn đúng gate. Chỉ đọc tài liệu/code/receipt phục vụ bước hiện tại; liên kết tham khảo không có nghĩa phải tải toàn bộ mọi lần.
3. Tìm bằng `rg -n` trong file/thư mục liên quan, lấy đoạn quanh kết quả; mở rộng phạm vi khi chưa đủ căn cứ. Không dump toàn repo, media/base64, log dài hoặc toàn lịch sử Git vào context.
4. Kiểm tra `git status`/diff trước sửa; giữ thay đổi của người dùng. Sửa tối thiểu, dùng pattern có sẵn; chỉ refactor khi cần cho yêu cầu cụ thể.
5. Sau sửa, chạy kiểm tra phù hợp. Chỉ lặp/bổ sung khi có thay đổi mới, failure hoặc nghi vấn chưa giải quyết; không bỏ preflight runtime bắt buộc vì đã từng chạy thành công.

## Giữ quyết định qua nhiều phiên

- Quy tắc ổn định ở tài liệu chuyên môn; tiến độ/decision mới ở status; raw artifacts ở output riêng. Không nhân bản toàn bộ cùng một nội dung sang nhiều file chỉ dẫn.
- Bàn giao theo [mẫu tiến độ](progress-checklist.md): kết quả, evidence path, blocker và bước tiếp. Không chép transcript; không tóm tắt mất negative evidence hoặc gate đang đóng.
- Tái sử dụng bằng chứng khi input/config/phạm vi vẫn khớp; kiểm tra hash/identity nơi quy trình yêu cầu. Hash đúng không thay semantic review. Bằng chứng bị thay đổi phải được xem xét lại đúng phần bị ảnh hưởng.
- Hoàn tất phần độc lập đã được phép khi chờ đầu vào. Chỉ hỏi thông tin thực sự thiếu và ảnh hưởng bước tiếp theo; không yêu cầu lặp quyết định đã được chấp nhận.
- Không sinh nhiều agent hoặc vòng tự phản biện chỉ để đọc cùng bộ tài liệu. Chỉ dùng delegation khi người dùng/chỉ dẫn áp dụng yêu cầu và công việc có phần độc lập rõ.

## Tham khảo GitHub

Đã tham khảo ngày 14/10/2026; các link dùng nhánh main nên có thể thay đổi. Đây là nguồn ý tưởng tổ chức tài liệu, không phải dependency hay hướng dẫn được cài vào repo.

| Nguồn chính | Cách áp dụng tại dự án |
|---|---|
| [agentsmd/agents.md — README](https://github.com/agentsmd/agents.md/blob/main/README.md) | Một điểm vào rõ cho chỉ dẫn agent; giữ AGENTS.md ngắn và trỏ tới tài liệu tác vụ |
| [anthropics/skills — Progressive Disclosure](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md#progressive-disclosure) | Tách tài liệu tham chiếu và chỉ nạp khi cần; ghi rõ khi nào đọc |

Các quy tắc cụ thể về evidence, gate và bàn giao ở đây là điều chỉnh cho EventCaption-AI. Không sao chép framework, cài dependency hay chạy script của repo ngoài. Khi tái sử dụng code sau này, kiểm tra license, revision, tương thích và kiểm thử trước; không tự đổi stack nghiên cứu.

## Giới hạn của tối ưu

Chưa benchmark mức tiết kiệm token hoặc độ ổn định. Không báo phần trăm giảm nếu chưa có số đo. Khi công cụ cung cấp usage, so cùng tác vụ/đầu vào/model, ghi input/output token, số lần đọc/lặp kiểm tra và chất lượng hoàn thành. Nếu không có usage, ghi chưa đo; kích thước file chỉ là chỉ báo, không phải token thực. Không chạy thêm model/GPU chỉ để chứng minh tài liệu tiết kiệm token.
