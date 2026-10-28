# Thực nghiệm AI

## Hai phần độc lập

Ứng dụng mặc định dùng trọng số OpenCV đã huấn luyện để chạy ngay. Các thực nghiệm CNN, ResNet18 và MobileNetV3-Small phải dùng tập dữ liệu có quyền sử dụng và tập test cố định. Không lấy Accuracy upstream làm kết quả của đồ án.

## Chuẩn bị môi trường

Python 3.11:

```bash
pip install -r backend/requirements.txt
pip install -r ai/requirements.txt
```

Hoặc build bản Docker có PyTorch CPU:

```bash
docker compose -f compose.yaml -f compose.research.yaml up -d --build --wait
```

Bản mở rộng mount `data/datasets` (đọc), `ai/runs` (ghi) từ máy. CPU build phù hợp chạy thử, huấn luyện đầy đủ nên dùng GPU/Colab và phiên bản torch/torchvision CUDA tương thích. Không tự động tải dataset thay người dùng vì điều kiện truy cập/giấy phép khác nhau.

## Dataset

Nguồn FER2013: https://www.kaggle.com/c/challenges-in-representation-learning-facial-expression-recognition-challenge/data

Tải `fer2013.csv` theo điều kiện sử dụng, đặt ngoài Git:

```bash
python -m ai.prepare_fer2013 data/fer2013.csv --output data/datasets/fer2013
python -m ai.audit_dataset data/datasets/fer2013 --output data/fer2013-audit.json
```

CSV chính thức: `Training` → train, `PublicTest` → val, `PrivateTest` → test. Không trộn test vào train. Thứ tự nhãn runtime được chuẩn hóa:

```text
data/datasets/fer2013/
  train/{angry,disgust,fear,happy,neutral,sad,surprise}/*.png
  val/{angry,disgust,fear,happy,neutral,sad,surprise}/*.png
  test/{angry,disgust,fear,happy,neutral,sad,surprise}/*.png
```

Audit đọc ảnh RGB, kiểm tra lớp trống/ảnh lỗi, thống kê nhãn và ảnh trùng pixel giữa các split, ghi fingerprint của dataset. Nếu gặp trùng giữa train và test, giữ test chuẩn và loại bản sao train theo một phiên bản dataset mới; lưu lại danh sách thay đổi. Công cụ không tự sửa dataset và chưa phát hiện ảnh gần trùng hoặc cùng danh tính. Nếu có ID chủ thể cần tự chia theo người trước khi dùng.

Không dùng bộ ảnh ví dụ `tests/assets` để tính chất lượng nghiên cứu. Đó là dữ liệu kiểm thử phần mềm.

## Huấn luyện ba mô hình

```bash
python -m ai.train --dataset data/datasets/fer2013 --model cnn --output ai/runs/cnn-v1 --epochs 30
python -m ai.train --dataset data/datasets/fer2013 --model resnet18 --output ai/runs/resnet-v1 --epochs 30
python -m ai.train --dataset data/datasets/fer2013 --model mobilenet_v3_small --output ai/runs/mobile-v1 --epochs 30
```

- Augmentation chỉ ở train: resize, horizontal flip, rotation 10°, brightness/contrast.
- RGB 224×224, ImageNet normalization; ImageFolder kiểm tra thứ tự nhãn.
- Seed 42, DataLoader seeded, AdamW, weighted cross-entropy xử lý mất cân bằng lớp, gradient clipping, early stopping.
- Với backbone pretrained: warmup classifier 3 epoch, sau đó fine-tune toàn mạng bằng learning rate nhỏ hơn; BatchNorm giữ statistics trong warmup.
- Checkpoint tốt nhất theo **validation Macro-F1**, không chọn bằng test.
- Mỗi run có `config.json`, `dataset-audit.json`, `history.json`, `checkpoint.pth`, `model.pt` TorchScript.
- `--no-pretrained` chỉ dùng khi chủ đích thử nghiệm từ đầu; không gọi đó là fine-tune.
- Không ghi đè thư mục run đã có để tránh trộn phiên bản.

Ví dụ trong Docker nghiên cứu:

```bash
docker compose exec app python -m ai.train --dataset data/datasets/fer2013 --model cnn --output ai/runs/cnn-v1 --epochs 30
```

API dành cho engineer/admin: `POST /api/research/datasets`, `POST /api/research/datasets/{id}/audit`, `POST /api/research/train`, `GET /api/research/runs`. Schema xem Swagger. Bản local chỉ chạy một training job tại một thời điểm; restart không tự tiếp tục run đang dở.

## Đánh giá test

```bash
python -m ai.evaluate --dataset data/datasets/fer2013 --model ai/runs/cnn-v1/model.pt --output ai/runs/cnn-v1/test.json
python -m ai.evaluate --dataset data/datasets/fer2013 --model ai/runs/resnet-v1/model.pt --output ai/runs/resnet-v1/test.json
python -m ai.evaluate --dataset data/datasets/fer2013 --model ai/runs/mobile-v1/model.pt --output ai/runs/mobile-v1/test.json
python -m ai.compare_models ai/runs/cnn-v1/test.json ai/runs/resnet-v1/test.json ai/runs/mobile-v1/test.json --output ai/runs/comparison.csv
```

Kết quả gồm Accuracy, Macro-F1, precision/recall/F1 từng lớp, confusion matrix JSON/PNG, classifier latency CPU theo batch và model size. Timing này không bao gồm face detection/resize/network, không đồng nghĩa webcam FPS.

Bảng báo cáo phải để “Chờ đo” cho đến khi có thực nghiệm:

| Kiến trúc | Accuracy | Macro-F1 | Latency | Kích thước |
|---|---|---|---|---|
| CNN | Chờ đo | Chờ đo | Chờ đo | Chờ đo |
| ResNet18 | Chờ đo | Chờ đo | Chờ đo | Chờ đo |
| MobileNetV3-Small | Chờ đo | Chờ đo | Chờ đo | Chờ đo |

## Đăng ký và kích hoạt

Copy `model.pt` và báo cáo test JSON tương ứng vào `models/`, đặt tên phiên bản riêng. Ví dụ PowerShell:

```powershell
Copy-Item ai/runs/mobile-v1/model.pt models/mobile-v1.pt
Copy-Item ai/runs/mobile-v1/test.json models/mobile-v1.test.json
# Neu app chay Docker, copy vao volume model cua app:
docker compose cp models/mobile-v1.pt app:/app/models/mobile-v1.pt
docker compose cp models/mobile-v1.test.json app:/app/models/mobile-v1.test.json
```

Ở Mô hình AI, nhập tên, version và hai tên file. Backend đối chiếu SHA-256, split=test, thứ tự nhãn và metric hợp lệ. Người phụ trách xem xét, phê duyệt rồi kích hoạt. Smoke-forward phải có đúng 7 đầu ra. Không tự kích hoạt model sau training. Đổi về model cũ bằng cùng nút Kích hoạt / khôi phục. Tác vụ video đang chạy chặn thay model; phiên webcam phát hiện thay model sẽ kết thúc.

Model TorchScript cần bản Docker nghiên cứu hoặc host có PyTorch. Chỉ nạp file từ nguồn tin cậy. Volume model được khởi tạo từ image; copy model mới vào app bằng `docker compose cp` như trên trước khi đăng ký. File được giữ khi app container tạo lại.

## Điều còn phải đo để bảo vệ đồ án

1. Đánh giá ba model trên cùng test, cùng preprocessing và phiên bản dữ liệu.
2. Đo độ trễ end-to-end, FPS camera và phần cứng thật; thử thiếu sáng, nghiêng, che mặt.
3. Hiệu chỉnh ngưỡng và margin trên validation, kiểm tra calibration/rejection rate.
4. Kiểm tra domain shift: FER2013 ảnh crop 48px và mặt được MediaPipe căn chỉnh lúc triển khai.
5. Đánh giá trên ảnh ngoài dataset với người tham gia tự nguyện, tách khỏi bộ test chuẩn.

Không dùng kết quả để đánh giá tâm lý, trung thực, năng suất hoặc đưa ra quyết định nhân sự.
