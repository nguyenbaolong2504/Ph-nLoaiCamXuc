# Chạy Docker (tùy chọn)

Nếu chạy frontend bằng `npm start` và backend bằng `npm run dev` thì không cần Docker.

Để dùng Docker sau này: mở Docker Desktop ở Linux containers, nhấp `RUN.bat` hoặc chạy `scripts/start.ps1`. Script tạo `.env` nếu chưa có, build app/MongoDB và mở http://localhost:8010 (hoặc APP_PORT). Cần dung lượng trống và Internet lần build đầu.

```powershell
docker compose up -d --build --wait --wait-timeout 240
docker compose logs --tail 80 app
docker compose stop
docker compose start
docker compose down
```

`down` giữ volume; `down -v` xóa dữ liệu. MongoDB có xác thực, không publish port host. Compose mặc định dùng MongoDB container, không dùng MONGO_URI Atlas của chế độ local trừ khi sửa Compose.

Không chạy backend local và Docker app trên cùng APP_PORT. `STOP.bat` dừng Docker, không dừng terminal local.

Bản Docker có PyTorch CPU:

```powershell
docker compose -f compose.yaml -f compose.research.yaml up -d --build --wait
```

Chép model custom vào container trước khi đăng ký tại UI:

```powershell
docker compose cp models/mobile-v1.pt app:/app/models/mobile-v1.pt
docker compose cp models/mobile-v1.test.json app:/app/models/mobile-v1.test.json
```

Model TorchScript cần bản nghiên cứu có PyTorch. ADMIN_EMAIL/ADMIN_PASSWORD chỉ khởi tạo tài khoản mới; sửa MONGO_PASSWORD không tự đổi mật khẩu database đã khởi tạo.
