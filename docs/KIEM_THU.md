# Kiểm thử và tình trạng xác minh

Ngày thực hiện: 28/10/2026.

## Bổ sung chế độ npm local

- Hai file model pretrained được bổ sung vào Git để clone/pull không phụ thuộc DNS tên miền tải model. 3 kiểm thử xác nhận file hợp lệ không gọi mạng, file tải hỏng không thay file có sẵn và lỗi DNS có hướng dẫn lấy model từ Git.
- Đã kiểm tra cú pháp Node bridge, Python runner, JSON package scripts và biến APP_PORT từ môi trường.
- 4 kiểm thử subprocess thật đã pass: chuẩn bị dataset từ đường dẫn có dấu cách trong backend, kiểm tra path luôn tính từ gốc; truyền lỗi Python thành mã thoát khác 0; giữ nguyên `.env` có sẵn; chuyển `train --help` tới CLI PyTorch thật trong venv.
- Không cài lại toàn bộ dependency hoặc chạy train dataset thật trong lần cập nhật này vì dung lượng máy còn hạn chế và chưa có dataset. Native startup với MongoDB và browser E2E vẫn cần xác minh trên máy đã cài đủ môi trường.
- Frontend build ghi ở phần dưới là kết quả trước khi bổ sung npm scripts; chưa ghi nhận build mới sau thay đổi cấu hình Vite.

## Đã chạy thành công

- Frontend: TypeScript type-check và Vite production build.
- Python: compile tất cả module backend và AI.
- Import ứng dụng và sinh OpenAPI thành công: 31 đường dẫn REST; Docker Compose qua kiểm tra cấu hình.
- Hai unit test: hash mật khẩu có salt, verify đúng/sai; ghép mặt bằng IoU, thứ tự mặt đổi và reset sau frame không có mặt.
- Load MediaPipe + OpenCV ONNX thật, smoke-forward 7 đầu ra.
- Ảnh mẫu NASA: phát hiện 1 khuôn mặt, trả phân bố đủ 7 lớp, nhãn `happy`; đây chỉ là kiểm thử chạy mô hình, không dùng để tính accuracy nghiên cứu.
- Ảnh đen không có người: trả `NO_FACE`, không tạo nhãn.
- CNN, ResNet18, MobileNetV3-Small: tạo kiến trúc, forward tensor → shape `(1,7)`.

## Chưa xác minh trọn vẹn trên máy hiện tại

Build Docker đã tải được base image/thư viện nhưng dừng khi cài Python dependencies do **ổ C hết dung lượng**, Docker báo `Input/output error` và `read-only file system`. Đây là lỗi môi trường trong lần kiểm thử, chưa có app container mới chạy healthy.

Vì vậy chưa xác nhận bộ integration API với MongoDB thật, E2E trình duyệt, video qua HTTP, webcam vật lý và startup Docker từ đầu. Bộ test đã được cung cấp để chạy sau khi máy đủ dung lượng. Không ghi các kịch bản chưa chạy là đã pass.

Phương án MongoDB portable tạm trên ổ D cũng bị Windows Application Control chặn chạy binary tải mới; không thay đổi hay vô hiệu chính sách đó. Chưa có kết quả kiểm thử database thật để báo cáo.

Không có FER2013 được cấp trong lần bàn giao nên chưa huấn luyện ba mô hình trên dataset thật, chưa đo Accuracy/Macro-F1, calibration hoặc FPS trên phần cứng đích.

## Bộ integration đã viết

`tests/test_system.py` dùng app đang chạy, MongoDB và inference thật:

1. Health + frontend trả thành công.
2. Ảnh có mặt, đủ 7 scores, không chọn save thì không tạo lịch sử.
3. Lưu, kiểm tra sở hữu, feedback, xuất CSV và xóa phiên.
4. Không có mặt không sinh nhãn.
5. Ảnh ghép hai mặt trả nhiều khuôn mặt.
6. File giả, ảnh quá lớn, ngưỡng sai bị từ chối.
7. Consent bị thiếu/thu hồi chặn inference.
8. Xác thực, RBAC, duplicate email, mật khẩu sai và Origin không hợp lệ.
9. Video tạo từ ảnh mẫu → job hoàn thành, timestamp có thứ tự.
10. Video hỏng → FAILED, video bị hủy → CANCELLED.
11. WebSocket gửi ảnh thật → kết quả → stop/save.
12. Logout vô hiệu token ở server.

Unit test tự chạy độc lập. Integration tạo tài khoản test riêng, xóa kết quả của các tài khoản test trong tearDown; không sửa dữ liệu người dùng hiện có. Tài khoản test và audit có thể còn để phục vụ kiểm tra.

```powershell
python -m pip install httpx websockets
python -m unittest discover -s tests -p test_core.py -v
python -m unittest discover -s tests -p test_system.py -v
```

Nếu đổi port:

```powershell
$env:TEST_BASE_URL='http://127.0.0.1:8010'
python -m unittest discover -s tests -p test_system.py -v
```

## E2E desktop / mobile

`frontend/e2e/app.spec.ts` đăng ký, đồng ý, lưu và phân tích ảnh, xem lịch sử, bật camera giả Chromium, phân tích và dừng. Kiểm tra không lỗi JavaScript và không tràn ngang ở 390px.

```powershell
cd frontend
npm install
# Kiem thu qua Vite: bat frontend va backend truoc
$env:TEST_BASE_URL='http://127.0.0.1:5173'
npm run test:e2e
```

Dùng Chrome đã cài. Nếu không có Chrome, đổi `channel` trong config hoặc cài Chrome theo Playwright. Camera giả chỉ kiểm tra luồng phần mềm, không thay việc thử webcam thật.

## Tiêu chí cần xác minh tiếp

- Chạy `npm run setup`, bật MongoDB, mở `backend/npm run dev` và `frontend/npm start` trên máy có đủ dung lượng cho thư viện. Docker vẫn có thể kiểm thử riêng, không bắt buộc.
- Đăng nhập admin, đổi password, kiểm tra user không có quyền admin.
- Cho phép và thu hồi quyền camera thật; kiểm tra camera tắt sau stop/rời trang.
- Upload video ở giới hạn dung lượng/thời lượng và thử hủy.
- Lưu phiên, restart app và kiểm tra MongoDB giữ lịch sử.
- Train/val/test trên dataset hợp lệ, so sánh model và đo hiệu năng thật.
