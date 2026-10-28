# Expression Lab — Phân loại biểu cảm khuôn mặt

Ứng dụng đồ án tiếng Việt: **React + TypeScript · FastAPI · MediaPipe · MongoDB**. Nhận diện 7 lớp biểu cảm từ ảnh, video và webcam; có đăng nhập, lưu lịch sử, thống kê, CSV, phản hồi, quyền riêng tư và quản trị.

## Chạy local bằng terminal — không cần Docker

Cài **Node.js 22/24 có npm**, **Python 3.11** (Windows chọn Add Python to PATH), và **MongoDB Community Server** hoặc dùng Atlas. MongoDB Compass là giao diện quản lý; dùng `mongodb://127.0.0.1:27017` vẫn cần MongoDB Server đang chạy.

### 1. Cài backend một lần

Từ thư mục gốc dự án:

```powershell
cd backend
npm install
npm run setup
```

`setup` tự tìm Python 3.11, tạo `.venv` ở gốc, cài thư viện Python, tạo `.env` nếu chưa có và tải model pretrained có kiểm tra SHA-256. Không cần kích hoạt venv. Backend vẫn dùng Python để chạy AI; npm khởi động đúng Python trong venv.

Mở `.env` ở **thư mục gốc**, kiểm tra:

```dotenv
MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB=expression_lab
APP_PORT=8010
```

Nếu dùng Atlas, thay `MONGO_URI` bằng URI `mongodb+srv://...` của bạn, cấu hình database user và quyền truy cập mạng Atlas. `setup` giữ nguyên `.env` đã có; không đưa URI/mật khẩu vào Git.

### 2. Terminal backend

```powershell
cd backend
npm run dev
```

API: **http://127.0.0.1:8010**, Swagger: **http://127.0.0.1:8010/docs**. Backend reload khi sửa code. `npm start` chạy không reload. Khi thiếu model hoặc MongoDB không kết nối, terminal hướng dẫn cách xử lý.

### 3. Terminal frontend

```powershell
cd frontend
npm install
npm start
```

Mở **http://127.0.0.1:5173**. `npm run dev` cũng dùng được. Frontend proxy API và WebSocket tới backend, đọc `APP_PORT` từ `.env` gốc. Nếu đổi port, restart cả hai terminal. Cổng frontend 5173 cố định để cookie, Origin và webcam hoạt động đúng.

Đăng ký tài khoản ở giao diện. Tài khoản quản trị: `admin@expressionlab.com`, mật khẩu ngẫu nhiên trong `.env`; đổi sau lần đăng nhập đầu. `.env` chỉ khởi tạo tài khoản lần đầu, không ghi đè mật khẩu đã đổi trong database.

Nhấn **Ctrl+C** trong mỗi terminal để dừng. Lần sau chỉ cần `npm run dev` và `npm start`; dữ liệu vẫn ở MongoDB.

Nếu MongoDB đã cài nhưng chưa chạy dạng service, mở terminal riêng từ thư mục gốc (cần `mongod` trong PATH):

```powershell
New-Item -ItemType Directory -Force data/mongo
mongod --dbpath ./data/mongo --bind_ip 127.0.0.1 --port 27017
```

Nếu MongoDB đã chạy dạng Windows Service thì không chạy thêm lệnh trên.

## Lệnh train dataset

Gõ các lệnh npm sau trong **backend**. Mọi đường dẫn dataset/output được tính từ **gốc dự án**.

```powershell
# Cài thêm PyTorch CPU và bộ nghiên cứu, một lần
npm run setup:ai

# Nếu dùng FER2013 CSV, đặt file ở data/fer2013.csv
npm run data:prepare -- data/fer2013.csv --output data/datasets/fer2013
npm run data:audit -- data/datasets/fer2013 --output data/fer2013-audit.json

# Huấn luyện và đánh giá MobileNetV3-Small
npm run train -- --dataset data/datasets/fer2013 --model mobilenet_v3_small --output ai/runs/mobile-v1 --epochs 30 --batch-size 16
npm run evaluate -- --dataset data/datasets/fer2013 --model ai/runs/mobile-v1/model.pt --output ai/runs/mobile-v1/test.json
```

Dataset đã chia `train/val/test` với đủ nhãn `angry, disgust, fear, happy, neutral, sad, surprise` thì bỏ `data:prepare` và trỏ `--dataset` tới thư mục đó. Dataset chỉ có `train/test` cần tách validation từ train trước; không dùng test chọn model. Xem báo cáo audit nếu có ảnh lỗi hoặc ảnh trùng giữa split.

Hai mô hình đối chứng:

```powershell
npm run train -- --dataset data/datasets/fer2013 --model cnn --output ai/runs/cnn-v1 --epochs 30 --batch-size 16
npm run train -- --dataset data/datasets/fer2013 --model resnet18 --output ai/runs/resnet-v1 --epochs 30 --batch-size 16
```

Kết quả: `ai/runs/<version>/model.pt`, checkpoint, config và history. Không ghi đè run cũ; lần train tiếp theo đổi `mobile-v1` thành `mobile-v2`. Training CLI không cần MongoDB/backend chạy. Xem [hướng dẫn nghiên cứu](docs/NGHIEN_CUU.md) để lấy dữ liệu đúng nguồn và kích hoạt model sau khi train.

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
- Binary pretrained được kèm trong bản ZIP ban đầu, có SHA-256 trong `models/manifest.json`. Nếu clone Git, `npm run setup` tự tải và kiểm tra.
- Không tự sinh nhãn khi model lỗi; `/api/health` trả trạng thái AI/MongoDB.

**Chưa có kết quả nghiên cứu FER2013 của dự án.** Huấn luyện/đánh giá bộ dữ liệu thật là bước riêng và không được thay bằng kết quả smoke test. Đọc [hướng dẫn nghiên cứu](docs/NGHIEN_CUU.md) để thực hiện ba thí nghiệm.

## MongoDB

Local dùng MongoDB Community Server hoặc Atlas theo `MONGO_URI`; không cần Docker. Dữ liệu được giữ tại MongoDB của bạn. Các collection: `users`, `auth_sessions`, `sessions`, `jobs`, `feedback`, `consents`, `model_versions`, `datasets`, `training_runs`, `audit_logs`, `data_requests`, `system`.

- Email unique; index chủ sở hữu + thời gian cho lịch sử.
- TTL tự xóa phiên/kết quả/phản hồi sau 30 ngày, job tạm sau 1 giờ và phiên đăng nhập sau 7 ngày. TTL chạy bất đồng bộ; API lịch sử cũng lọc `expires_at`.
- Kết quả được nhúng trong document phiên; xóa phiên sẽ xóa kết quả nhúng và feedback.
- Mật khẩu hash bằng scrypt; token phiên ngẫu nhiên 256 bit, database chỉ lưu hash; cookie HttpOnly, SameSite=Strict, logout thu hồi token.

Atlas: chỉ cần đặt URI trong `.env` khi chạy terminal; không phải sửa Compose. Không đưa URI/mật khẩu vào Git.

## Docker là tùy chọn

Nếu chạy terminal theo hướng dẫn trên thì không cần mở Docker hay chạy `RUN.bat`. Các file Docker được giữ để có thể dùng sau; xem [hướng dẫn riêng](docs/DOCKER.md).

Các lệnh dưới đây chỉ dành cho chế độ Docker:

```bash
docker compose ps
docker compose logs --tail 80 app
docker compose stop             # dừng, giữ dữ liệu
docker compose start            # chạy lại, không build
docker compose down            # gỡ container, giữ volume dữ liệu
```

Không dùng `docker compose down -v` nếu cần giữ dữ liệu; `-v` xóa volume MongoDB.

- Frontend local: http://127.0.0.1:5173
- Swagger API local: http://127.0.0.1:8010/docs
- Health API: http://127.0.0.1:8010/api/health
- Docker phục vụ giao diện tại http://localhost:8010

**Cổng 8010 bị chiếm:** đổi `APP_PORT=8011` trong `.env`, restart backend/frontend. Giao diện local vẫn ở 5173. Nếu dùng Docker thì chạy lại `RUN.bat` và mở localhost:8011. Không sửa `MONGO_PASSWORD` của MongoDB Docker đã khởi tạo nếu chưa cập nhật mật khẩu MongoDB tương ứng.

**Camera không mở:** dùng localhost hoặc HTTPS; cấp quyền camera và đóng ứng dụng đang chiếm camera. Truy cập qua IP LAN HTTP không bảo đảm quyền webcam.

**Ứng dụng chưa healthy:** xem terminal backend, kiểm tra MongoDB, Internet lúc setup và model. Venv/PyTorch vẫn cần dung lượng dù không dùng Docker; có thể đặt dự án ở ổ D trước khi cài. Chỉ cần `setup:ai` nếu train hoặc nạp TorchScript custom.

## Phát triển không qua Docker

Các lệnh npm ở trên dùng được mà không kích hoạt venv. Nếu muốn chạy Python trực tiếp, từ thư mục gốc trên Windows:

```bash
.\.venv\Scripts\python.exe scripts/run_backend.py --reload
```

Trên macOS/Linux:

```bash
.venv/bin/python scripts/run_backend.py --reload
```

`npm run build` trong frontend tạo bundle production; FastAPI tự phục vụ `frontend/dist` nếu có. Không chạy nhiều worker Uvicorn ở bản này: hàng đợi video/training và model dùng chung một tiến trình.

## Kiểm thử

Sau khi ứng dụng healthy:

```bash
.\.venv\Scripts\python.exe -m pip install httpx websockets
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
cd frontend
# Bat ca frontend/backend de kiem thu qua Vite:
$env:TEST_BASE_URL='http://127.0.0.1:5173'
npm run test:e2e
```

Kiểm thử API dùng MongoDB thật, inference thật và video tạo từ ảnh mẫu NASA. E2E dùng camera giả của Chromium để kiểm tra luồng webcam; cần kiểm tra thêm với webcam vật lý trên máy trình diễn. Xem `docs/KIEM_THU.md` và `docs/PHAM_VI.md`.

## Tài liệu

- [Phân tích, kiến trúc và thiết kế MongoDB](docs/THIET_KE.md)
- [Dữ liệu, huấn luyện, đánh giá và so sánh mô hình](docs/NGHIEN_CUU.md)
- [Phạm vi các Use Case](docs/PHAM_VI.md)
- [Kiểm thử và giới hạn](docs/KIEM_THU.md)

Nguồn chính: [MediaPipe Face Detector](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector/python), [OpenCV pretrained classifier](https://github.com/opencv/opencv_zoo/tree/main/models/facial_expression_recognition), [PyTorch transfer learning](https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html), [MongoDB TTL](https://www.mongodb.com/docs/manual/core/index-ttl/). Thư viện và model giữ giấy phép tương ứng; xem `THIRD_PARTY.md`.
