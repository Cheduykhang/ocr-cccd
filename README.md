# Hệ thống OCR cho Thẻ Căn Cước Công Dân

## 📋 Tổng quan

Hệ thống trích xuất thông tin tự động từ thẻ căn cước và căn cước công dân sử dụng công nghệ OCR (Optical Character Recognition) và Deep Learning.

### Tính năng chính:
- ✅ Phát hiện và định vị thẻ căn cước trong ảnh
- ✅ Trích xuất các vùng text quan trọng
- ✅ Nhận dạng ký tự và chuyển đổi thành text
- ✅ Hỗ trợ cả thẻ căn cước và căn cước công dân
- ✅ API RESTful với Swagger UI
- ✅ Hỗ trợ cả CPU và GPU

## 🛠️ Yêu cầu hệ thống

### Phần cứng tối thiểu:
- **RAM**: 8GB trở lên
- **CPU**: Intel i5 hoặc tương đương
- **GPU** (tùy chọn): NVIDIA GTX 1060 trở lên với CUDA support

### Phần mềm:
- **Python**: 3.10+
- **Conda** hoặc **Docker**
- **CUDA Toolkit** (nếu sử dụng GPU)

## 🚀 Cách triển khai

### Phương pháp 1: Sử dụng Conda Environment

#### Bước 1: Clone source code
```bash
# Di chuyển vào đúng nhánh, đúng thư mục cha của dự án.
```

#### Bước 2: Tạo và kích hoạt môi trường Conda
```bash
# Tạo môi trường mới
conda create -n venv_name python=3.11.13

# Kích hoạt môi trường
conda activate venv_name

# Cài đặt thư viện
pip install -r requirements.txt
# Có options cho GPU và CPU trong file này.
```

#### Bước 3: Cấu hình models
Chỉnh sửa file `configs.yml` để cấu hình đường dẫn đến các models:

```yaml
# Model paths configuration
model_paths:
  yolo_det_4cornercard_model_path: "model/det4corner/best.onnx"
  yolo_det_textcc_model_path: "model/textdet/cc/best.onnx"
  yolo_det_textcccd_model_path: "model/textdet/cccd/best.onnx"
  vietocr_rec_textregion_model_path: "model/vietocr"
```
**Hiện tại sử dụng 4 model.**
- Model yolov11n to 4 corner and card detection, format onnx.
- 2 model yolov11n to text regions detection lần lượt cho thẻ căn cước và căn cước công dân, format onnx.
- model VietOCR to text recognition, gồm 3 file ONNX (CNN, encoder, decoder).

**Cấu hình nâng cao** trong file `src/configs.py`:
- Threshold cho IoU và Confidence
- Định dạng, kích thước và hình dạng ảnh cho phép
- Tên các class
- Lựa chọn CPU/GPU cho từng model

#### Bước 4: Chạy ứng dụng
```bash
export PYTHONPATH="$(pwd)/src:$(pwd)"
python main.py
```

#### Bước 5: Truy cập Swagger UI
Mở trình duyệt và truy cập: `http://localhost:9930/docs`

### Phương pháp 2: Sử dụng Docker

Các lệnh dưới đây sử dụng Bash. Thư mục `model/` cần chứa đủ các file model theo `configs.yml`; nếu dùng gói triển khai có thư mục `weight/`, xem `DEPLOY.md` để tạo liên kết model trước khi chạy.

```bash
# Build image (basic setup, no proxy username/password required)
docker build -t ocr-app .
# RUN CONTAINER COMMAND
docker run --gpus all \
  -e PYTHONPATH=/app/src:/app \
  -v $(pwd)/model:/app/model \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/main.py:/app/main.py \
  -v $(pwd)/configs.yml:/app/configs.yml \
  -p 9930:9930 \
  --name ocr-container \
  ocr-app

# OR RUN WITH DOCKER COMPOSE
docker compose up
```

> **Lưu ý**: Xem chi tiết trong file `Dockerfile` để biết thêm các tùy chọn cấu hình.

Docker run và Docker Compose ở trên yêu cầu GPU NVIDIA được Docker hỗ trợ. Dockerfile hiện cài ONNX Runtime CPU; để inference trên GPU cần thay `onnxruntime` bằng `onnxruntime-gpu` và có các thư viện CUDA/cuDNN tương ứng.

## 🔌 API endpoints

URL gốc mặc định: `http://localhost:9930`

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Thông báo chào mừng của ứng dụng |
| GET | `/health/live` | API còn phản hồi: HTTP 200 |
| GET | `/health/ready` | OCR đã nạp xong: HTTP 200; chưa sẵn sàng: HTTP 503 |
| POST | `/ocr` | Trích xuất thông tin thẻ từ ảnh Base64 |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | OpenAPI schema |

`POST /ocr` nhận JSON (`Content-Type: application/json`):

```json
{
  "base64": "<chuỗi Base64 đầy đủ của ảnh>",
  "request_id": "12345"
}
```

`base64` bắt buộc, chấp nhận Base64 thuần hoặc có tiền tố `data:image/jpeg;base64,`. `request_id` không bắt buộc, có thể là string hoặc null. Loại thẻ và mặt thẻ được tự động phát hiện.

Phản hồi OCR gồm `errorCode`, `errorMessage` và `data` (danh sách thông tin thẻ). Thành công có `errorCode: "0"`, `errorMessage: "Success"`; lỗi xử lý có `errorCode: "400"` hoặc `"500"`, `data: []`. Các phản hồi này đều trả HTTP 200, nên backend cần kiểm tra `errorCode` trong JSON. Thiếu `base64` hoặc sai kiểu dữ liệu trả HTTP 422 với trường `detail`.

Xem chi tiết request/response trong [Tài liệu API OCR](api_document_vi.md).

## Application logs

Log ứng dụng được xuất ra console (stderr) và ghi UTF-8 vào `logs/ocr.log` với định dạng:

```text
2026-10-07 14:30:00.123456 [INFO] [services:180] [idRequest: req-123] - Message: Extracted text for field name: NGUYEN VAN A
```

Mỗi dòng có thời gian đến microsecond, mức log, tên file Python (không có `.py`), số dòng và ID request. `request_id` trong JSON được truyền xuyên suốt router, xử lý ảnh và các thread OCR. Nếu không gửi ID hoặc gửi chuỗi rỗng, server tự tạo UUID để tra log. Log khởi động/tắt ứng dụng có ID rỗng. Có thể ghi log thủ công với `logger.info("message", extra={"id": "req-123"})`.

Mỗi JSON response được ghi thêm một dòng ở mức INFO vào cả console và file log. Phần sau `Message:` là nguyên văn JSON body đã serialize gửi cho client (giữ nguyên các trường, giá trị, Unicode và kiểu dữ liệu), không phải chuỗi biểu diễn dict Python. Áp dụng cho response thành công, lỗi OCR, lỗi validation HTTP 422, HTTP 404 và các endpoint health. Response OCR dùng cùng ID với log xử lý; response bị validation từ chối trước khi vào router có ID rỗng.

```text
2026-10-23 10:30:00.123456 [INFO] [response_logging:28] [idRequest: req-123] - Message: {"data":[],"errorCode":"400","errorMessage":"Input image error: Incorrect padding"}
```

| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `LOG_DIR` | `logs/` trong thư mục dự án | Thư mục lưu file log |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` hoặc `CRITICAL` |
| `LOG_BACKUP_COUNT` | `5` | Số file log cũ giữ lại, phải >= 1 |

Docker Compose mount `./logs` trên host vào `/app/logs` và đặt `LOG_DIR=/app/logs`; `LOG_LEVEL` và `LOG_BACKUP_COUNT` có thể đặt trong môi trường hoặc file `.env` của Compose. File log xoay hằng ngày lúc 00:00 theo giờ hệ thống của tiến trình/container, tên file cũ là `ocr.log.YYYYMMDD` (ví dụ `ocr.log.20261007`). Nếu không có log đúng lúc 00:00, file được xoay ở lần ghi tiếp theo. Giữ tối đa `LOG_BACKUP_COUNT` file cũ ngoài file hiện tại; các file số `.1`–`.5` từ cấu hình trước không được tự xóa. Logger `ocr_app` ghi vào file; log truy cập Uvicorn vẫn xem qua console. Nội dung OCR từng trường vẫn được log nguyên văn ở mức INFO.

Log console của container dùng driver `json-file`, giới hạn 10 MB mỗi file và giữ tối đa 5 file. Xem bằng `docker logs -f ocr-container`. Sau khi thay đổi cấu hình, chạy `docker compose up -d --build` để tạo lại container.


## Health check

```bash
curl -i http://localhost:9930/health/live
curl -i http://localhost:9930/health/ready
docker compose ps
docker inspect --format '{{json .State.Health}}' ocr-container
```

`/health/live` trả `{"status":"alive"}` khi API phản hồi. `/health/ready` trả `{"status":"ready"}` chỉ sau khi khởi tạo xong dịch vụ OCR; khi dịch vụ chưa sẵn sàng hoặc đã dọn tài nguyên, trả HTTP 503 với `{"status":"not_ready"}`. Các probe không chạy inference, không nạp lại model và không tiết lộ đường dẫn model. Readiness xác nhận dịch vụ đã được khởi tạo, không đảm bảo mọi lần inference đều thành công. FastAPI chỉ nhận request sau khi hoàn tất startup; trong lúc nạp model, probe có thể chưa kết nối được.

Dockerfile và Compose kiểm tra `/health/ready` mỗi 30 giây, timeout 5 giây (HTTP timeout 3 giây), đánh dấu `unhealthy` sau 3 lần thất bại liên tiếp. `start_period` là 120 giây để chờ nạp model; tăng giá trị này nếu máy triển khai khởi động lâu hơn. Docker Compose cấu hình lại các tham số để dễ chỉnh theo môi trường. Build lại image bằng `docker compose up -d --build` để áp dụng.

Docker health check cung cấp trạng thái `starting`/`healthy`/`unhealthy`; nó không tự khởi động lại container khi `unhealthy`. Nếu dùng Kubernetes, cấu hình liveness probe với `/health/live`, readiness probe với `/health/ready` và startup probe có thời gian chờ phù hợp cho model.

Inference chạy trong thread pool để health check vẫn phản hồi khi xử lý ảnh. Các request OCR được xử lý lần lượt bằng khóa để bảo vệ trạng thái dùng chung trong model YOLO.
