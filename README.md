# Expression Lab — Phân loại biểu cảm khuôn mặt

Ứng dụng đồ án tiếng Việt: **React + TypeScript · FastAPI · MediaPipe · MongoDB**. Nhận diện 7 lớp biểu cảm từ ảnh, video và webcam; có đăng nhập, lưu lịch sử, thống kê, CSV, phản hồi, quyền riêng tư và quản trị.

## Chạy dễ nhất trên Windows

1. Cài và mở [Docker Desktop](https://www.docker.com/products/docker-desktop/), dùng **Linux containers**.
2. Giải nén dự án, nhấp đúp **`RUN.bat`**.
3. Chờ lần đầu tải thư viện/model và build. Trình duyệt tự mở **http://localhost:8010**.
4. Chọn **Đăng ký ngay** để tạo tài khoản. Tài khoản quản trị được in trong cửa sổ khởi động và ghi trong `.env`.

**Không cần cài riêng Python, Node hoặc MongoDB.** Lần đầu cần Internet, các lần sau dùng lại image và dữ liệu đã có. Có thể nhấp `RUN.bat` lại để cập nhật mã mới; `STOP.bat` để dừng và giữ dữ liệu.

Tài khoản quản trị mặc định: `admin@expressionlab.com`; mật khẩu được tạo ngẫu nhiên trong `.env`. Đổi mật khẩu tại Cài đặt sau lần đăng nhập đầu. Mật khẩu `.env` chỉ khởi tạo tài khoản lần đầu, không ghi đè mật khẩu đã đổi trong database.

## Chạy bằng lệnh

```powershell
# Windows, không yêu cầu Python trên host
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

```bash
# macOS / Linux
sh start.sh
```

Nếu đã có Python và muốn chạy thủ công:

```bash
python scripts/setup.py
docker compose up -d --build --wait --wait-timeout 240
```

## Sử dụng

- **Ảnh:** đồng ý xử lý → chọn JPG/PNG/WebP → tùy chọn lưu → phân tích. Có khung mặt và điểm của cả 7 lớp; chọn từng mặt để xem.
- **Video:** MP4/WebM/MOV/AVI, tối đa 50 MB / 3 phút. Lấy mẫu 2 FPS, xem tiến độ, hủy tác vụ và chọn mốc thời gian sau khi hoàn thành. MP4 H.264 tương thích tốt nhất.
- **Webcam:** bật camera để xem trước → bắt đầu phân tích → dừng & đóng camera. Giới hạn 600 khung hình/phiên, gửi khung tiếp theo sau khi nhận phản hồi, EMA theo IoU để giảm dao động. Chọn Dừng để lưu; rời trang hoặc mất kết nối sẽ kết thúc phiên mà không lưu.
- **Lịch sử:** tìm tên, lọc nguồn/nhãn/ngày, xem chi tiết, xuất CSV UTF-8 cho Excel, in/lưu PDF bằng trình duyệt, gửi nhãn phản hồi, xóa phiên.
- **Tổng quan:** thống kê từ dữ liệu thật đã lưu của chính tài khoản. Không tạo sẵn số liệu minh họa.
- **Cài đặt:** sửa tên, đổi mật khẩu, thu hồi đồng ý, tải dữ liệu JSON và xóa toàn bộ dữ liệu phân tích.
- **Quản trị:** xem người dùng, khóa/mở khóa, gán `user/admin/engineer/annotator`, xem nhật ký và xử lý phản hồi.
- **Mô hình:** xem phiên bản, đăng ký TorchScript + báo cáo test có checksum, phê duyệt và kích hoạt/rollback.

Ngưỡng mặc định 0.60 và margin 0.10 là cấu hình thử nghiệm. Các trạng thái `NO_FACE`, `LOW_QUALITY`, `UNCERTAIN` không phải lớp biểu cảm mới. Hệ thống phân loại **biểu hiện quan sát được**, không xác định danh tính hay chẩn đoán tâm lý.

## AI chạy ngay và AI nghiên cứu

Để có dự đoán thật ngay mà chưa cần tải FER2013 và huấn luyện nhiều giờ:

- Face detection: **MediaPipe BlazeFace**.
- Classifier sẵn có: **MobileFaceNet / Progressive Teacher của OpenCV Zoo**, Apache-2.0, 7 đầu ra.
- Mã huấn luyện riêng: **CNN baseline, ResNet18, MobileNetV3-Small**, PyTorch.
- Binary pretrained được kèm trong bản ZIP, có SHA-256 trong `models/manifest.json`. Nếu clone từ Git, Docker tự tải và kiểm tra.
- Không tự sinh nhãn khi model lỗi; `/api/health` trả trạng thái AI/MongoDB.

**Chưa có kết quả nghiên cứu FER2013 của dự án.** Huấn luyện/đánh giá bộ dữ liệu thật là bước riêng và không được thay bằng kết quả smoke test. Đọc [hướng dẫn nghiên cứu](docs/NGHIEN_CUU.md) để thực hiện ba thí nghiệm.

## MongoDB

MongoDB 8 chạy cùng Docker Compose, có xác thực, dữ liệu bền vững trong volume `expression-lab_mongo-data`. Không mở cổng MongoDB ra host. Các collection: `users`, `auth_sessions`, `sessions`, `jobs`, `feedback`, `consents`, `model_versions`, `datasets`, `training_runs`, `audit_logs`, `data_requests`, `system`.

- Email unique; index chủ sở hữu + thời gian cho lịch sử.
- TTL tự xóa phiên/kết quả/phản hồi sau 30 ngày, job tạm sau 1 giờ và phiên đăng nhập sau 7 ngày. TTL chạy bất đồng bộ; API lịch sử cũng lọc `expires_at`.
- Kết quả được nhúng trong document phiên; xóa phiên sẽ xóa kết quả nhúng và feedback.
- Mật khẩu hash bằng scrypt; token phiên ngẫu nhiên 256 bit, database chỉ lưu hash; cookie HttpOnly, SameSite=Strict, logout thu hồi token.

MongoDB Atlas cũng dùng được: thay `MONGO_URI` trong `compose.yaml` bằng `${MONGO_URI}` rồi đặt URI trong `.env`; bỏ `depends_on` của app nếu không dùng Mongo local. Không đưa URI/mật khẩu vào Git.

## Lệnh vận hành

```bash
docker compose ps
docker compose logs --tail 80 app
docker compose stop             # dừng, giữ dữ liệu
docker compose start            # chạy lại, không build
docker compose down            # gỡ container, giữ volume dữ liệu
```

Không dùng `docker compose down -v` nếu cần giữ dữ liệu; `-v` xóa volume MongoDB.

- Web: http://localhost:8010
- Swagger API: http://localhost:8010/docs
- Health: http://localhost:8010/api/health

**Cổng 8010 bị chiếm:** đổi `APP_PORT=8011` trong `.env`, chạy lại `RUN.bat`, mở http://localhost:8011. Launcher tự đọc cổng. Cổng 8010 được chọn để tránh backend khác đang dùng 8000 trên máy hiện tại. Không sửa `MONGO_PASSWORD` sau khi database đã khởi tạo nếu chưa cập nhật mật khẩu MongoDB tương ứng.

**Camera không mở:** dùng localhost hoặc HTTPS; cấp quyền camera và đóng ứng dụng đang chiếm camera. Truy cập qua IP LAN HTTP không bảo đảm quyền webcam.

**Ứng dụng chưa healthy:** xem log. Kiểm tra Docker còn RAM/dung lượng, Internet lần đầu và thư mục `models`. Bản local gợi ý RAM 8 GB, trống 5 GB, CPU x64. Huấn luyện cần thêm tài nguyên.

## Phát triển không qua Docker

Python 3.11, Node 24, pnpm 12.6, MongoDB đang hoạt động:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
python scripts/download_models.py
# Tạo .env từ .env.example, đặt MONGO_URI trỏ đến MongoDB thật.
cd frontend
pnpm install
pnpm dev
```

Terminal thứ hai ở thư mục gốc:

```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Vite http://localhost:5173 proxy `/api` và `/ws` tới backend. `pnpm build` tạo frontend production, FastAPI tự phục vụ thư mục `frontend/dist`. Không chạy nhiều worker Uvicorn ở bản này: hàng đợi video/training và model đang dùng chung một tiến trình.

## Kiểm thử

Sau khi ứng dụng healthy:

```bash
python -m pip install httpx websockets
python -m unittest discover -s tests -p "test_*.py" -v
cd frontend
pnpm exec playwright test
```

Kiểm thử API dùng MongoDB thật, inference thật và video tạo từ ảnh mẫu NASA. E2E dùng camera giả của Chromium để kiểm tra luồng webcam; cần kiểm tra thêm với webcam vật lý trên máy trình diễn. Xem `docs/KIEM_THU.md` và `docs/PHAM_VI.md`.

## Tài liệu

- [Phân tích, kiến trúc và thiết kế MongoDB](docs/THIET_KE.md)
- [Dữ liệu, huấn luyện, đánh giá và so sánh mô hình](docs/NGHIEN_CUU.md)
- [Phạm vi các Use Case](docs/PHAM_VI.md)
- [Kiểm thử và giới hạn](docs/KIEM_THU.md)

Nguồn chính: [MediaPipe Face Detector](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector/python), [OpenCV pretrained classifier](https://github.com/opencv/opencv_zoo/tree/main/models/facial_expression_recognition), [PyTorch transfer learning](https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html), [MongoDB TTL](https://www.mongodb.com/docs/manual/core/index-ttl/). Thư viện và model giữ giấy phép tương ứng; xem `THIRD_PARTY.md`.
