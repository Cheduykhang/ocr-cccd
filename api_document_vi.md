# Tài liệu API OCR Thẻ Căn cước

## Tổng quan
API này cung cấp chức năng OCR (Nhận dạng ký tự quang học) cho thẻ căn cước Việt Nam (CCCD và CC). Nó có thể xử lý hình ảnh được tải lên dưới dạng chuỗi mã hóa base64 và trích xuất thông tin văn bản từ thẻ.

## URL gốc
```
http://localhost:9930
```

## Endpoints

### POST /ocr

Xử lý hình ảnh thẻ căn cước và trích xuất thông tin sử dụng công nghệ OCR tiên tiến.

#### Tham số yêu cầu

API chấp nhận yêu cầu JSON (`Content-Type: application/json`) với các tham số sau:

| Tham số | Kiểu | Bắt buộc | Mô tả | Mặc định |
|---------|------|----------|-------|----------|
| `base64` | string | Có | Chuỗi hình ảnh mã hóa Base64 | Không có |
| `request_id` | string hoặc null | Không | Định danh yêu cầu để theo dõi | null |

*Lưu ý: `base64` chấp nhận chuỗi Base64 thuần hoặc có tiền tố `data:image/jpeg;base64,`. Loại thẻ và mặt thẻ được tự động phát hiện.

#### Ví dụ yêu cầu

**Tải lên Base64:**
```bash
curl -X POST "http://localhost:9930/ocr" \
  -H "Content-Type: application/json" \
  -d '{"base64":"data:image/jpeg;base64,/9j/4AAQSkZJRgABA...","request_id":"12345"}'
```

*Lưu ý: Thay chuỗi Base64 rút gọn trong ví dụ bằng chuỗi Base64 đầy đủ của hình ảnh.

#### Định dạng phản hồi

API trả về phản hồi JSON với cấu trúc sau:

```json
{
  "errorCode": "0",
  "errorMessage": "string", 
  "data": [
    {
    }
  ]
}
```

`errorCode` là chuỗi. `data` là danh sách chứa thông tin thẻ được trích xuất.

#### Phản hồi thành công (errorCode: "0")

```json
{
  "errorCode": "0",
  "errorMessage": "Success",
  "data": [
    {    
        "id": "",
    
        "id_prob": "",
    
        "name": "",
    
        "name_prob": "",
    
        "dob": "",
    
        "dob_prob": "",
    
        "sex": "",
    
        "sex_prob": "",
    
        "nationality": "",
    
        "nationality_prob": "",
    
        "home": "",
    
        "home_prob": "",
    
        "address": "",
    
        "address_prob": "",
    
        "doe": "",
    
        "doe_prob": "",
    
        "religion": "",
    
        "religion_prob": "",
    
        "ethnicity": "",
    
        "ethnicity_prob": "",
    
        "features": "",
    
        "features_prob": "",
    
        "issue_date": "",
    
        "issue_date_prob": "",
    
        "issue_loc": "",
    
        "issue_loc_prob": "",
    
        "back_type": "N/A",
    
        "overall_score": "",
    
        "type": "",
    
        "type_new": "",
    
        "mrz": [],
    
        "mrz_prob": "N/A",
    
        "mrz_details": {
    
            "id": "N/A",
    
            "name": "N/A",
    
            "doe": "N/A",
    
            "dob": "N/A",
    
            "nationality": "N/A",
    
            "sex": "N/A"
    
        },
    
        "custAddress": {
    
            "province": "",
    
            "district": "",
    
            "ward": "",
    
            "street": ""
    
        }
    }
  ]
}
```

Trường `mrz` trả về mảng các chuỗi, theo thứ tự các dòng MRZ đọc được trên thẻ. Khi đọc đầy đủ, mảng gồm 3 dòng. Khi không có dữ liệu MRZ, trả về `[]`. Chỉ phân tích `mrz_details` khi có đủ ít nhất 3 dòng.

Giá trị `type` và `type_new` theo loại thẻ và mặt thẻ:

| Loại thẻ | Mặt thẻ | `type` | `type_new` |
|---|---|---|---|
| CCCD Chip | Trước | `chip_front` | `cccd_chip_front` |
| CCCD Chip | Sau | `chip_back` | `chip_back` |
| CC mới | Trước | `cc_front` | `cccd_chip_front` |
| CC mới | Sau | `cc_back` | `chip_back` |

#### Phản hồi lỗi

*Lưu ý: Phản hồi thành công và lỗi xử lý OCR (`errorCode` "400" hoặc "500") đều trả về HTTP 200. Cần kiểm tra `errorCode` trong JSON để xác định kết quả xử lý. Nội dung chi tiết trong `errorMessage` phụ thuộc vào lỗi thực tế.

**Mã lỗi 400 - Vấn đề chất lượng/xử lý hình ảnh:**
```json
{
  "errorCode": "400", 
  "errorMessage": "Bad Capture issue: Image is too small (100x100). Minimum size is 200x200 pixels.",
  "data": []
}
```

**Mã lỗi 400 - Vấn đề phát hiện thẻ:**
```json
{
  "errorCode": "400",
  "errorMessage": "Card Detect issue: ...", 
  "data": []
}
```

**Mã lỗi 400 - Vấn đề trích xuất văn bản:**
```json
{
  "errorCode": "400",
  "errorMessage": "Text Extract issue: ...",
  "data": []
}
```

Các lỗi đầu vào, vùng cắt thẻ, phát hiện vùng văn bản và xử lý hình ảnh cũng trả về `errorCode` "400", với `errorMessage` lần lượt có tiền tố `Input image error:`, `Bad Box issue:`, `Text Region Detect issue:` và `Error processing image:`.

**Mã lỗi 500 - Lỗi xử lý máy chủ:**
```json
{
  "errorCode": "500",
  "errorMessage": "An unexpected error occurred: ...",
  "data": []
}
```

**HTTP 422 - Dữ liệu yêu cầu không hợp lệ:**

Khi thiếu `base64` hoặc dữ liệu yêu cầu không đúng kiểu, API trả về HTTP 422 với cấu trúc `detail` của FastAPI, thay vì `errorCode`, `errorMessage` và `data`.

### GET /

Trả về thông báo chào mừng của ứng dụng.

```json
{
  "message": "Welcome to OCR identification card application"
}
```

## Loại thẻ được hỗ trợ

- **CCCD (Căn cước công dân)**: Thẻ căn cước quốc gia Việt Nam
- **CC (Căn cước)**: Thẻ căn cước Việt Nam

## Mặt thẻ được hỗ trợ

- **Mặt trước (Front)**: Chứa thông tin cá nhân
- **Mặt sau (Back)**: Chứa thông tin bổ sung và chữ ký

## Yêu cầu hình ảnh

- **Định dạng**: JPEG, PNG, hoặc các định dạng hình ảnh phổ biến khác
- **Chất lượng**: Khuyến nghị độ phân giải cao để độ chính xác OCR tốt hơn
- **Hướng**: Bất kỳ hướng nào (tự động điều chỉnh)
- **Kích thước**: Kích thước file tối đa phụ thuộc vào cấu hình máy chủ

## Quy trình xử lý

1. **Xác thực hình ảnh**: Kiểm tra chất lượng và định dạng hình ảnh
2. **Phát hiện thẻ**: Phát hiện và cắt thẻ căn cước từ hình ảnh
3. **Phát hiện vùng văn bản**: Xác định các trường văn bản trên thẻ
4. **Trích xuất văn bản**: Trích xuất văn bản sử dụng OCR (VietOCR cho văn bản tiếng Việt và MRZ)
5. **Ánh xạ trường**: Ánh xạ văn bản được trích xuất tới các trường thẻ tương ứng
6. **Tạo phản hồi**: Trả về dữ liệu có cấu trúc

## Hiệu suất

- **Thời gian xử lý trung bình**: 0.2-1 giây mỗi hình ảnh
- **Xử lý vùng văn bản đồng thời**: Được hỗ trợ với xử lý thread pool

## Xử lý lỗi

API bao gồm xử lý lỗi toàn diện cho:
- Định dạng hình ảnh không hợp lệ
- Chất lượng hình ảnh kém
- Thất bại phát hiện thẻ
- Vấn đề trích xuất văn bản
- Lỗi xử lý máy chủ

## Cân nhắc bảo mật

- Hình ảnh được xử lý trong bộ nhớ và không được lưu trữ vĩnh viễn
- Request ID có thể được sử dụng để theo dõi yêu cầu

## Giới hạn tốc độ

Giới hạn tốc độ có thể áp dụng tùy thuộc vào cấu hình máy chủ. Liên hệ với quản trị viên để biết giới hạn cụ thể.

## Hỗ trợ

Để được hỗ trợ kỹ thuật hoặc báo cáo vấn đề, vui lòng kiểm tra log máy chủ hoặc liên hệ với nhóm phát triển.
