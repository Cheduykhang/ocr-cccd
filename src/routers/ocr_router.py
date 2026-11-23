from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from typing import Optional
import asyncio
import base64
import io
from PIL import Image
import time
from src.logger import logger, request_id_context
from uuid import uuid4
from src.load_resources import resources
from schemas import BaseResponse, ResponseMessage
from exceptions import CardDetectionError, BadCaptureError, TextRegionDetectError, TextExtractError , BadBoxError
from pydantic import BaseModel
from dataclasses import asdict

class OCRRequest(BaseModel):
    base64: str
    request_id: Optional[str] = None


router = APIRouter(
    tags=["OCR"]
)

# YOLO wrappers store image dimensions on the shared model instances.
# Keep inference sequential while allowing health probes to use the event loop.
_ocr_lock = asyncio.Lock()

@router.post("/ocr")
async def ocr_id_card(request: OCRRequest, http_request: Request):
    """
    Process an ID card image and extract information.

    Parameters: 
    - request: JSON body containing:
        - base64: Base64 encoded image string
        - request_id: Optional request identifier

    Returns:
    - OCRResponse with status, card information and extracted data
    """
    token = request_id_context.set(request.request_id or uuid4().hex)
    http_request.state.log_request_id = request_id_context.get()
    try:
        logger.info("OCR request started")
        image = None

        try:
            # Remove data URL prefix if present
            if "," in request.base64:
                base64_data = request.base64.split(",")[1]
            else:
                base64_data = request.base64

            # Decode and open image
            image_data = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_data))
        except ValueError as ve:
            logger.warning(f"Input image error: {ve}")
            return asdict(
                BaseResponse(
                    data=[],
                    errorCode="400",
                    errorMessage=ResponseMessage.input_error(str(ve))
                )
            )

        # Predict using the OCR service
        start = time.time()
        async with _ocr_lock:
            result = await run_in_threadpool(resources['ocr_service'].process_id_card, image=image)
        processing_time = time.time() - start

        logger.info(f'OCR request completed, Time: {processing_time:.3f}s')

        return asdict(BaseResponse(
                data=result,
                errorCode="0", 
                errorMessage=ResponseMessage.SUCCESS
            )
        )
    except BadCaptureError as e:
        logger.error(f"Bad Capture issue: {str(e)}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.bad_capture(str(e))
            )
        )
    except CardDetectionError as e:
        logger.error(f"Card Detect issue: {str(e)}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.card_detect_error(str(e))
            )
        )
    except BadBoxError as e:
        logger.error(f"Bad Box issue: {str(e)}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.bad_box(str(e))
            )
        )
    except TextRegionDetectError as e:
        logger.error(f"Text Region Detect issue: {str(e)}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.text_region_det_error(str(e))
            )
        )
    except TextExtractError as e:
        logger.error(f"Text Extract issue: {str(e)}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.text_extract_error(str(e))
            )
        )
    except ValueError as ve:
        logger.warning(f"Error processing image: {ve}")
        return asdict(BaseResponse(
                data=[],
                errorCode="400", 
                errorMessage=ResponseMessage.process_img_error(str(ve))
            )
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return asdict(
            BaseResponse(
                data=[],
                errorCode="500",
                errorMessage=ResponseMessage.error_occurred(e)
            )
        )
    except HTTPException:
        raise
    finally:
        request_id_context.reset(token)
