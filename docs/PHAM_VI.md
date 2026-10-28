# Phạm vi đối chiếu bản mô tả

Đây là bản chạy local có AI pretrained thật và mã thực nghiệm. Không coi việc có mã training là đã có mô hình FER2013 được kiểm chứng.

| Use Case | Phạm vi bàn giao |
|---|---|
| UC01–03 Đăng ký/nhập/xuất | Giao diện + API + token có thu hồi |
| UC04 Hồ sơ | Sửa tên, đổi mật khẩu; email không đổi qua giao diện |
| UC05 Đồng ý | Ghi lịch sử policy/purpose và thu hồi; dừng tác vụ khi thu hồi |
| UC06 Quyền dữ liệu | Tải JSON/xóa toàn bộ dữ liệu phân tích của tài khoản; chưa có cổng xử lý yêu cầu chủ thể bên ngoài không có tài khoản |
| UC07 Ảnh | Phát hiện đa mặt, chất lượng, 7 scores, UNCERTAIN/NO_FACE |
| UC08 Video | Worker local, progress/cancel, sampling, kết quả theo thời gian |
| UC09 Webcam | WebSocket, preview/start/stop, IoU+EMA và timeout |
| UC10 Chọn khuôn mặt | Chọn mặt để hiển thị điểm chi tiết; inference vẫn xử lý tối đa 10 mặt |
| UC11 Điểm chi tiết | Hiển thị 7 điểm, ghi rõ giới hạn softmax |
| UC12 Dừng/hủy | Dừng stream/camera, hủy job video và dọn file |
| UC13 Tùy chọn | Ngưỡng 0.30–0.95 và lưu; video 2 FPS cố định, chưa có bộ chỉnh mọi tham số trên UI |
| UC14–17 Lưu/lịch sử/chi tiết/lọc | MongoDB, sở hữu riêng, lọc tên/nguồn/nhãn/ngày, phân trang |
| UC18 Xuất | CSV + JSON cá nhân, PDF qua hộp In của trình duyệt |
| UC19 Xóa phiên | Xóa document kết quả nhúng và feedback liên quan |
| UC20 Phản hồi | Gửi nhãn đề xuất từ chi tiết; admin/annotator review qua API, admin có UI |
| UC21 Thống kê | Phân bố nhãn trên dữ liệu đã lưu và thống kê nguồn/frame/mặt |
| UC22 Dataset | Đăng ký nguồn/license/version/path qua API nghiên cứu; dữ liệu tải hợp lệ ngoài app |
| UC23 Kiểm tra dataset | CLI/API audit ảnh lỗi, phân bố, ảnh trùng pixel giữa split, fingerprint |
| UC24 Hiệu chỉnh nhãn | Queue review feedback; chưa có trình duyệt ảnh/gán nhãn dataset cộng tác |
| UC25 Chia dữ liệu | Converter FER2013 giữ split chuẩn; nhận ImageFolder đã chia; chưa có UI biên tập split |
| UC26 Training | CLI đủ ba kiến trúc + API job khi bật bản nghiên cứu; không tự tải dataset |
| UC27 Đánh giá | CLI test, per-class metrics, confusion matrix PNG/JSON, checksum |
| UC28 So sánh | CLI CSV từ báo cáo thật; xem metrics model trên UI |
| UC29 Phiên bản | Đăng ký TorchScript + báo cáo test và metadata |
| UC30 Kích hoạt | Phê duyệt, smoke-forward, chuyển model và audit |
| UC31 Rollback | Kích hoạt lại bản approved cũ |
| UC32–33 User/roles | Admin UI + kiểm tra backend; không tự sửa/khóa chính mình |
| UC34 Cấu hình | .env / Settings; chưa có trình chỉnh cấu hình live qua UI |
| UC35 Tổng hợp | Admin thống kê usage của toàn hệ thống |
| UC36 Nhật ký | Audit đăng nhập/consent/user/model/training; UI 100 sự kiện mới nhất |
| UC37 Quyền dữ liệu | Xóa kết quả tự phục vụ và ghi request completed; chưa có workflow pháp lý/định danh chủ thể ngoài app |

Giới hạn vận hành: một app process, worker video local, tối đa 4 video queued/processing; không phải hàng đợi phân tán/HA. Sau restart, job chưa xong được đánh dấu failed; người dùng tải lại. Training checkpoint không tự resume. Chưa có dataset trong dự án vì điều kiện truy cập và dữ liệu nghiên cứu chưa được người dùng cung cấp.
