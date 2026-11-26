import copy
import datetime
import re
import numpy as np
import cv2
from PIL import Image, ExifTags, ImageOps
from typing import Optional, Tuple, List, Dict, Any, Union
from exceptions import (
    BadCaptureError,
    CardDetectionError,
    BadBoxError,
    ModelNotLoadedError,
    IdNotFoundError,
    OCRBaseException
)
from configs import settings
from src.logger import logger
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))
from schemas import (
    format_res,
    cccd_map,
    cc_map
)
def validate_image_quality(image: Image.Image) -> None:
    """
    Validate the quality of the input image.

    Args:
        image: Input image in PIL format.

    Raises:
        ValueError: If the image is None or not an RGB image.
        BadCaptureError: If the image is too small, blurry, dark, or has low contrast.
    """
    if image is None:
        logger.error("Input image is None")
        raise ValueError("Input image cannot be empty.")
        
    # Convert PIL image to numpy array
    try:
        image_np = np.array(image)
    except Exception as e:
        logger.error(f"Failed to convert PIL image to numpy array: {e}")
        raise BadCaptureError(f"Invalid image format: {e}")
        
    image_shape = image_np.shape
    
    # Check image dimensions
    height, width = image_shape[:2]
    if width < 200 or height < 200:
        logger.warning(f"Image dimensions too small: {width}x{height}")
        raise BadCaptureError(f"Image is too small ({width}x{height}). Minimum size is 200x200 pixels.")
    
    # Check image format
    if len(image_shape) != 3 or image_shape[2] != 3 or image.mode != 'RGB':
        logger.warning(f"Invalid image format: shape={image_shape}, mode={image.mode}")
        raise ValueError(f"Input image must be in RGB format. Got shape={image_shape}, mode={image.mode}")
    
    try:
        # Check blur using Laplacian variance
        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY) if len(image_shape) == 3 else image_np
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Check brightness
        brightness = np.mean(gray) 
        
        # Check contrast
        contrast = gray.max() - gray.min()
        
        logger.info(f"Image quality metrics - blur: {laplacian_var:.2f}, brightness: {brightness:.2f}, contrast: {contrast:.2f}")
        
        if laplacian_var < 100:  # Adjustable threshold
            raise BadCaptureError(f"Image is too blurry (blur score: {laplacian_var:.2f})")
            
        if brightness < 50:  # Adjustable threshold
            raise BadCaptureError(f"Image is too dark (brightness: {brightness:.2f})")
            
        if contrast < 50:  # Adjustable threshold
            raise BadCaptureError(f"Image has low contrast (contrast: {contrast:.2f})")
    
    except OCRBaseException:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.error(f"Error during image quality validation: {e}")
        raise BadCaptureError(f"Failed to validate image quality: {e}")
    finally:
        del image_np  # Clean up numpy array to free memory
    
def correct_image_orientation(image: Image.Image) -> Image.Image:
    """
    Correct the orientation of an image based on EXIF data.

    ImageOps.exif_transpose xử lý đủ 8 giá trị EXIF orientation (xoay và lật gương)
    và xoá tag orientation sau khi xoay. Không xoay thủ công trước đó, vì ảnh vẫn giữ
    tag EXIF cũ nên exif_transpose sẽ xoay thêm lần nữa (lỗi xoay hai lần với
    orientation 3, 6, 8).

    Args:
        image: Input image in PIL format.

    Returns:
        Orientation-corrected image in PIL format (RGB).
    """
    if image is None:
        logger.error("Input image is None")
        raise ValueError("Input image cannot be empty.")

    try:
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        logger.warning(f"Failed to auto-orient image: {e}")

    # Ensure image is in RGB format
    if image.mode != 'RGB':
        logger.info(f"Converting image from {image.mode} to RGB")
        image = image.convert('RGB')

    return image

def validate_and_crop_card(xywh: np.ndarray,
                           conf: np.ndarray,
                           cls: np.ndarray,
                           image: np.ndarray,
                           expand: float = 1.1):
    """
    Validate detections: ensure 4 required corners and 1 card type. Optionally expand
    the corner geometry before perspective cropping.

    Args:
        xywh: (N,4) boxes [x_center, y_center, width, height]
        conf: (N,) confidences
        cls:  (N,) class ids
        image: source image array
        expand: scale factor to radially push corner centers away from card center (>1 enlarges)

    Returns:
        (cropped_image, w_ratio, h_ratio, card_type) or None if card type == 'other_card'

    Raises:
        CardDetectionError, BadBoxError
    """
    try:
        if any(v is None for v in (xywh, conf, cls, image)): # kiểm tra xem có giá trị nào là None không
            raise ValueError("Inputs cannot be None")
        if len(xywh) == 0:
            raise CardDetectionError("No detections found")

        corner_names = {'top_left', 'top_right', 'bottom_left', 'bottom_right'}
        card_type_classes = {'cc_front', 'cc_back', 'cccd_front', 'cccd_back', 'other_card'}

        # Keep highest confidence per relevant class
        best: Dict[str, Dict[str, Any]] = {}
        for i in range(len(xywh)):
            name = settings.CLASS_NAMES.get(int(cls[i]))
            if name is None:
                continue
            if name in corner_names or name in card_type_classes:
                if name not in best or conf[i] > best[name]['conf']: # chưa có thì thêm, có rồi thì so sánh xem có cập nhật lại k
                    best[name] = {
                        'box': xywh[i],
                        'conf': float(conf[i]),
                        'name': name
                    }

        # Check if we have exactly 5 required detections (4 corners + 1 card type)
        detected_corners = [name for name in corner_names if name in best]
        detected_card_types = [name for name in card_type_classes if name in best]
        
        # Must have exactly 4 corners
        if len(detected_corners) != 4:
            missing_corners = [c for c in corner_names if c not in best]# kiểm tra 4 góc thằng nào k có trong best thì thêm vào missing_corners
            if missing_corners:
                raise CardDetectionError(f"Missing corner detections: {missing_corners}")
            else:
                raise CardDetectionError("Unexpected corner detection issue")
        
        # Must have at least 1 card type
        if len(detected_card_types) == 0:
            raise CardDetectionError("Missing card type detection")

        # Select card type (highest conf among detected card-type classes)
        card_type_det = None
        for name in card_type_classes:
            if name in best:
                if card_type_det is None or best[name]['conf'] > card_type_det['conf']:
                    card_type_det = best[name]
        
        card_type_name = card_type_det['name']
        if card_type_name == 'other_card':
            raise CardDetectionError("Detected 'other_card' please sent another image.")

        def center_point(b):
            x_c, y_c, _, _ = b
            return np.array([float(x_c), float(y_c)], dtype=np.float32)

        # Get corner center coordinates
        corners_raw = {
            'top_left': center_point(best['top_left']['box']),
            'top_right': center_point(best['top_right']['box']),
            'bottom_right': center_point(best['bottom_right']['box']),
            'bottom_left': center_point(best['bottom_left']['box'])
        }

        # Calculate width and height based on corner centers
        # Width = distance from top_left to top_right
        width = float(np.linalg.norm(corners_raw['top_right'] - corners_raw['top_left'])) # tính tọa độ vector nối 2 điểm, xong tính độ dài của nó.
        # Height = distance from top_left to bottom_left  
        height = float(np.linalg.norm(corners_raw['bottom_left'] - corners_raw['top_left']))

        if width <= 0 or height <= 0:
            raise BadBoxError("Non-positive dimension after computation")

        # Validate aspect ratio
        aspect_ratio = max(width, height) / max(1e-6, min(width, height))
        if not (settings.ASPECT_RATIO_MIN <= aspect_ratio <= settings.ASPECT_RATIO_MAX):
            raise BadBoxError(f"Aspect ratio invalid: {aspect_ratio:.3f} not in "
                              f"[{settings.ASPECT_RATIO_MIN}, {settings.ASPECT_RATIO_MAX}]")

        # Validate area ratio
        img_h, img_w = image.shape[:2]
        card_area = width * height
        area_ratio = card_area / max(1, img_w * img_h)
        if area_ratio < settings.MIN_AREA_RATIO:
            raise BadBoxError(f"Card area too small: {area_ratio:.4f} < {settings.MIN_AREA_RATIO}")

        # Apply expansion if needed
        if expand != 1.0:
            # Get image dimensions
            img_h, img_w = image.shape[:2]
            
            # Calculate centroid of all corners
            pts_array = np.vstack([
                corners_raw['top_left'],
                corners_raw['top_right'], 
                corners_raw['bottom_right'],
                corners_raw['bottom_left']
            ])
            centroid = pts_array.mean(axis=0)
            
            # Expand corners away from centroid
            expanded_corners = {}
            for corner_name in corners_raw:
                expanded_corner = centroid + (corners_raw[corner_name] - centroid) * float(expand)
                
                # Clamp coordinates to image boundaries with small margin
                margin = 5  # pixels
                expanded_corner[0] = np.clip(expanded_corner[0], margin, img_w - margin)
                expanded_corner[1] = np.clip(expanded_corner[1], margin, img_h - margin)
                
                expanded_corners[corner_name] = expanded_corner
            
            # Update corners_raw with clamped expanded corners
            corners_raw = expanded_corners
            
            logger.debug(f"Applied expansion factor {expand} with image boundary constraints")
        # Prepare source and destination points for perspective transform
        src = np.array([
            corners_raw['top_left'],
            corners_raw['top_right'],
            corners_raw['bottom_right'],
            corners_raw['bottom_left']
        ], dtype=np.float32)

        # Destination rectangle (standard rectangle)
        dst_w = max(1, int(round(width)))
        dst_h = max(1, int(round(height)))
        dst = np.array([
            [0, 0],
            [dst_w - 1, 0],
            [dst_w - 1, dst_h - 1],
            [0, dst_h - 1]
        ], dtype=np.float32)

        logger.debug(
            f"Geometry (expand={expand}) width={width:.1f}, height={height:.1f}, "
            f"aspect_ratio={aspect_ratio:.3f}, area_ratio={area_ratio:.4f}"
        )

        # Perspective transform
        M = cv2.getPerspectiveTransform(src, dst)
        cropped = cv2.warpPerspective(image, M, (dst_w, dst_h))

        w_ratio = width / img_w
        h_ratio = height / img_h
        logger.info(f"Cropped card type={card_type_name}, expand={expand}, w_ratio={w_ratio:.3f}, h_ratio={h_ratio:.3f}")
        return cropped, card_type_name, card_type_det['conf']

    except (BadBoxError, CardDetectionError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error in validate_and_crop_card: {e}")
        raise BadBoxError(f"Failed during card validation/cropping: {e}")

def format_date(date_str: str, code_gender_cen: str, date_type: str) -> str:
    year = date_str[:2]
    month = date_str[2:4]
    day = date_str[4:6]
    century = '20'
    if date_type == "dob":
        if code_gender_cen == '0' or code_gender_cen == '1':
            century = '19'
        elif code_gender_cen == '2'or code_gender_cen == '3':
            century = '20'
        elif code_gender_cen == '4'or code_gender_cen == '5':
            century = '21'
        elif code_gender_cen == '6'or code_gender_cen == '7':
            century = '22'
        elif code_gender_cen == '8'or code_gender_cen == '9':
            century = '23'
 
    return f"{day}/{month}/{century}{year}"
# Nhận diện dòng MRZ (TD1, 3 dòng x 30 ký tự) theo nội dung, không theo thứ tự trong mảng.
MRZ_LINE1_RE = re.compile(r'^ID[A-Z<]{3}')        # IDVNM + số giấy tờ + ...
MRZ_LINE2_RE = re.compile(r'^\d{7}[MF<]')         # ngày sinh (6) + check (1) + giới tính
MRZ_LINE3_RE = re.compile(r'^[A-Z<]+$')           # họ tên, chỉ chữ cái và '<'

def classify_mrz_lines(mrz: List[str]) -> Dict[int, str]:
    """
    Gán từng dòng OCR đọc được vào dòng 1/2/3 của MRZ dựa trên nội dung.
    Dòng không khớp mẫu nào, hoặc trùng loại với dòng đã có, thì bỏ qua.
    """
    lines: Dict[int, str] = {}
    for raw in mrz or []:
        line = (raw or '').replace(' ', '').upper()
        if not line:
            continue
        if MRZ_LINE1_RE.match(line):
            kind = 1
        elif MRZ_LINE2_RE.match(line):
            kind = 2
        elif MRZ_LINE3_RE.match(line):
            kind = 3
        else:
            logger.warning(f"Unrecognized MRZ line (length {len(line)})")
            continue
        if kind in lines:
            logger.warning(f"Duplicate MRZ line {kind}; keeping the first one")
            continue
        lines[kind] = line
    return lines

def parse_mrz(mrz: List) -> Dict[str, str]:
    """
    Parse MRZ TD1. Mỗi dòng được parse độc lập: thiếu dòng nào thì chỉ các trường
    của dòng đó là "N/A", các trường khác vẫn có.

    Dòng 1: [2:5] quốc gia cấp, [5:14] số giấy tờ, [14] check, [15:27] số CCCD 12 số
            ([18] = chữ số thứ 4 của số CCCD: mã thế kỷ sinh + giới tính)
    Dòng 2: [0:6] ngày sinh, [6] check, [7] giới tính, [8:14] ngày hết hạn, [14] check,
            [15:18] quốc tịch
    Dòng 3: họ tên
    """
    res = {
        "id": "N/A",
        "name": "N/A",
        "doe": "N/A",
        "dob": "N/A",
        "nationality": "N/A",
        "sex": "N/A"
    }
    lines = classify_mrz_lines(mrz)
    line1, line2, line3 = lines.get(1), lines.get(2), lines.get(3)

    century_code = None
    if line1:
        if len(line1) >= 27:
            res["id"] = line1[15:27]
            century_code = line1[18]
        res["nationality"] = line1[2:5]

    if line2:
        if century_code is None:
            # Không có dòng 1 nên không biết mã thế kỷ: năm 2 số lớn hơn năm hiện tại thì là 19xx.
            yy = int(line2[0:2])
            century_code = '0' if yy > datetime.date.today().year % 100 else '2'
        res["dob"] = format_date(line2[0:6], century_code, "dob")
        res["sex"] = line2[7]
        if len(line2) >= 14 and line2[8:14].isdigit():
            res["doe"] = format_date(line2[8:14], century_code, "doe")
        if res["nationality"] == "N/A" and len(line2) >= 18:
            res["nationality"] = line2[15:18]

    if line3:
        name = ' '.join(line3.replace('<', ' ').split()) # .split() tự động xóa ' ' dư thừa luôn.
        if name:
            res["name"] = name

    return res
def mrz_check_digit(text: str) -> str:
    """Check digit theo ICAO 9303: trọng số 7-3-1, chữ số giữ nguyên, A-Z = 10-35, '<' = 0."""
    def value(c: str) -> int:
        if c.isdigit():
            return int(c)
        if c == '<':
            return 0
        return ord(c) - ord('A') + 10
    return str(sum(value(c) * w for c, w in zip(text, [7, 3, 1] * 20)) % 10)

def validate_mrz_id(mrz: List[str]) -> Tuple[Optional[str], str]:
    """
    Lấy số CCCD 12 số từ MRZ và kiểm tra trước khi dùng.
    Trả về (id, "") nếu hợp lệ, hoặc (None, lý do) nếu không.

    Dòng 1: [5:14] số giấy tờ (= 9 số cuối của số CCCD), [14] check digit của số giấy tờ,
            [15:27] số CCCD 12 số.
    Kiểm tra:
      1. Số CCCD đủ 12 chữ số.
      2. Check digit của số giấy tờ khớp.
      3. 9 số cuối của số CCCD trùng với số giấy tờ.
      4. Nếu có đủ dòng 2: check digit tổng (dòng 2 [29]) khớp. Bước này phủ cả 3 số đầu
         (mã tỉnh) của số CCCD, phần mà bước 2-3 không kiểm tra được.
    """
    lines = classify_mrz_lines(mrz)
    line1, line2 = lines.get(1), lines.get(2)
    if not line1:
        return None, "MRZ line 1 not detected"
    if len(line1) < 27:
        return None, "MRZ line 1 incomplete"
    doc_number, doc_check, id12 = line1[5:14], line1[14], line1[15:27]
    if not re.fullmatch(r'\d{12}', id12):
        return None, "MRZ id is not 12 digits"
    if mrz_check_digit(doc_number) != doc_check:
        return None, "MRZ document number check digit mismatch"
    if id12[3:] != doc_number:
        return None, "MRZ id does not match document number"
    if line2 and len(line1) >= 30 and len(line2) >= 30:
        composite = line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29]
        if mrz_check_digit(composite) != line2[29]:
            return None, "MRZ composite check digit mismatch"
    return id12, ""

def validate_front_id(text: Optional[str]) -> Tuple[Optional[str], str]:
    """Số CCCD đọc từ mặt trước phải đúng 12 chữ số (Luật Căn cước 2023, Điều 12)."""
    id_text = re.sub(r'\s+', '', text or '')
    if not id_text:
        return None, "id not detected"
    if not re.fullmatch(r'\d{12}', id_text):
        return None, "id is not 12 digits"  # không đưa số CCCD vào message/log
    return id_text, ""

def ensure_valid_id(data: Dict[str, Any], require_side: str) -> None:
    """
    Bảo đảm response có số CCCD 12 số hợp lệ; nếu không thì ném IdNotFoundError
    để router trả errorCode 400 và người dùng chụp lại.
    - Mặt trước: id do OCR đọc phải đúng 12 chữ số.
    - Mặt sau: id chỉ lấy từ MRZ và phải qua validate_mrz_id.
    """
    if require_side == 'front':
        valid_id, reason = validate_front_id(data.get('id'))
        if valid_id is None:
            raise IdNotFoundError(f"front side: {reason}, please recapture the card")
        data['id'] = valid_id
        return
    valid_id, reason = validate_mrz_id(data.get('mrz') or [])
    if valid_id is None:
        raise IdNotFoundError(f"back side: {reason}, please recapture the card")
    data['id'] = valid_id
    data['id_prob'] = 1.0

# Từ 01/07/2025 bỏ cấp huyện: địa chỉ trên thẻ CC cấp từ ngày này chỉ còn tỉnh / xã.
TWO_LEVEL_ADDRESS_FROM = datetime.date(2025, 7, 1)

def parse_issue_date(text: str) -> Optional[datetime.date]:
    """
    Đọc ngày cấp dạng dd/mm/yyyy từ chuỗi OCR (chấp nhận dấu phân cách / - . hoặc dấu cách).
    Trả về None nếu không đọc được, ngày không hợp lệ, hoặc ngày ở tương lai.
    """
    match = re.search(r'(\d{1,2})\s*[/\-. ]\s*(\d{1,2})\s*[/\-. ]\s*(\d{4})', text or '')
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        issue_date = datetime.date(year, month, day)
    except ValueError:
        return None
    if issue_date > datetime.date.today():
        return None
    return issue_date

def _is_two_level_address(require_type: str, issue_date_text: str) -> bool:
    """
    Quyết định tách địa chỉ theo 2 cấp (tỉnh / xã) hay 3 cấp (tỉnh / huyện / xã).
    - CCCD gắn chip (chỉ cấp đến 30/06/2024): luôn 3 cấp.
    - CC cấp từ 01/07/2025: 2 cấp. CC cấp trước đó: 3 cấp.
    - Không đọc được ngày cấp: tách 3 cấp như cũ, ghi warning.
    """
    if require_type != 'cc':
        return False
    issue_date = parse_issue_date(issue_date_text)
    if issue_date is None:
        logger.warning(f"Cannot parse issue_date {issue_date_text!r}; splitting address as 3-level")
        return False
    return issue_date >= TWO_LEVEL_ADDRESS_FROM

def split_address(address: str, two_level: bool) -> Dict[str, str]:
    """
    Tách chuỗi địa chỉ (các phần cách nhau bằng dấu phẩy) thành custAddress.
    Thiếu phần nào thì để chuỗi rỗng, không ném lỗi.

    2 cấp: "Số 2 nguyễn trãi, Phú Xuân, Tp.Huế"
        -> province=Tp.Huế, district="", ward=Phú Xuân, street=Số 2 nguyễn trãi
    3 cấp: "Ấp Kim Quí A, Vân Khánh, An Minh, Kiên Giang"
        -> province=Kiên Giang, district=An Minh, ward=Vân Khánh, street=Ấp Kim Quí A
    """
    parts = [part.strip() for part in address.split(',') if part.strip()]
    parts.reverse()  # đi từ cấp lớn nhất (tỉnh) xuống
    n_admin = 2 if two_level else 3
    admin = parts[:n_admin] + [''] * (n_admin - len(parts[:n_admin]))
    street_parts = parts[n_admin:]
    street_parts.reverse()
    if two_level:
        province, ward = admin
        district = ''
    else:
        province, district, ward = admin
    return {
        "province": province,
        "district": district,
        "ward": ward,
        "street": ', '.join(street_parts),
    }

def map_text2card(fieldname_text: Dict[str, Dict[str, Any]], require_type: str, require_side: str) -> Dict[str, Any]:
    """
    Map extracted text fields to card structure.
   
    Args:
        fieldname_text: Dictionary of field names and extracted text.
        require_type: Card type ('cccd' or 'cc').
        require_side: Card side ('front' or 'back').
       
    Returns:
        Dictionary with structured card information.
       
    Raises:
        ValueError: If the required card type or side is invalid.
    """
    # Validate inputs
    if not isinstance(fieldname_text, dict):
        logger.error(f"Invalid fieldname_text: {type(fieldname_text)}")
        raise ValueError("fieldname_text must be a dictionary")
       
    if require_type not in ['cccd', 'cc']:
        logger.error(f"Invalid card type: {require_type}")
        raise ValueError("require_type must be 'cccd' or 'cc'")
       
    if require_side not in ['front', 'back']:
        logger.error(f"Invalid card side: {require_side}")
        raise ValueError("require_side must be 'front' or 'back'")
   
    # print(fieldname_text)
   
    # Deep copy: format_res chứa dict lồng nhau (custAddress, mrz_details); copy nông
    # sẽ khiến các request ghi đè lên template dùng chung và rò dữ liệu sang nhau.
    data = copy.deepcopy(format_res)
    if require_type == 'cc':
        field_mapping = cc_map.copy()
    elif require_type == 'cccd':
        field_mapping = cccd_map.copy()
    else:
        raise ValueError("Invalid require_type or require_side. Use 'cc' or 'cccd' for type and 'front' for side.")
   
    try:
        logger.info(f"Mapping text for {require_type} {require_side} side")
        logger.debug(f"Input fields: {list(fieldname_text.keys())}")
       
        # Duyệt qua fieldname_text để gán giá trị vào dictionary đầu ra
        average_score = 0
        cnt = 0
        for field, value in fieldname_text.items():
           
            if field in field_mapping:
                # Chọn tên trường tương ứng dựa trên require_type
                target_field = field_mapping[field]
                if target_field == 'mrz':
                    # Preserve the separate OCR lines in the API response.
                    data[target_field] = list(value['text'] or [])
                else:
                    data[target_field] = value['text'] if isinstance(value['text'], str) else ''.join(value['text'])
                score = round(float(value['score']),2)
                data[target_field+'_prob'] = score
                average_score+=score
                cnt+=1
                # Parse cả khi thiếu dòng: parse_mrz tự nhận diện từng dòng theo nội dung.
                if target_field == 'mrz' and len(data['mrz']) >= 1:
                    data['mrz_details'] = parse_mrz(data['mrz'])
        # Tách custAddress sau vòng lặp, vì cần cả address lẫn issue_date,
        # mà thứ tự các trường trong fieldname_text không cố định.
        if data['address']:
            two_level = _is_two_level_address(require_type, data['issue_date'])
            data['custAddress'] = split_address(data['address'], two_level)
        if require_side == 'back' and not (data['id'] or '').strip():
            # Chỉ điền id từ MRZ khi đã qua kiểm tra check digit (xem validate_mrz_id).
            mrz_id, _ = validate_mrz_id(data['mrz'])
            if mrz_id:
                data['id'] = mrz_id
                data['id_prob'] = 1.0
        if require_type == "cc" and require_side == 'front':
            data['type'] = 'cc_front'
            data['type_new'] = 'cccd_chip_front'
        elif require_type == "cc" and require_side == 'back':
            data['type'] = 'cc_back'
            data['type_new'] = 'chip_back'
        elif require_type == "cccd" and require_side == 'front':
            data['type'] = 'chip_front'
            data['type_new'] = 'cccd_chip_front'
        elif require_type == "cccd" and require_side == 'back':
            data['type'] = 'chip_back'
            data['type_new'] = 'chip_back'
        data['overall_score'] = round(average_score/cnt,2)
        logger.info(f"Successfully mapped {len(data)} fields")
        return data
       
    except Exception as e:
        logger.error(f"Error mapping text to card: {e}")
        # Trả kết quả dở dang (các trường đã đọc được như id, name, address) thay vì {}.
        # Điều kiện cũ `'street' in locals()` gần như luôn sai nên vứt cả kết quả.
        return data
