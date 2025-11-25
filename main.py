from fastapi import FastAPI, UploadFile, File, Form
# FIX: Import from starlette, as it was removed from fastapi.concurrency
from starlette.concurrency import run_in_executor 
import openbharatocr
import shutil
import os
import uuid
import tempfile
import cv2
import numpy as np

app = FastAPI()

def get_skew_angle(cv_image) -> float:
    """
    Calculate the skew angle of the text in the image.
    """
    # Convert to grayscale and invert
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Dilate to connect text characters into lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilate = cv2.dilate(thresh, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    if not contours:
        return 0.0

    # Find largest contour (assumed to be the card or text block)
    largest_contour = contours[0]
    min_area_rect = cv2.minAreaRect(largest_contour)
    angle = min_area_rect[-1]

    # Correct angle logic
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    # Ignore small deviations (less than 1 degree)
    if abs(angle) < 1.0:
        return 0.0
        
    return angle

def rotate_image(cv_image, angle: float):
    """
    Rotates the image around its center.
    """
    if angle == 0.0:
        return cv_image
        
    (h, w) = cv_image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def preprocess_image_optimized(input_path: str) -> str:
    """
    Optimized Pipeline:
    1. Read
    2. Resize (Standardize DPI)
    3. Deskew (Fix rotation)
    4. Denoise & CLAHE (Enhance Contrast without full binary)
    """
    img = cv2.imread(input_path)
    if img is None:
        raise RuntimeError(f"Could not read image: {input_path}")

    # 1. Smart Resizing: Limit max dimension to 1800px to speed up OCR
    height, width = img.shape[:2]
    max_dim = 1800
    if max(height, width) > max_dim:
        scale = max_dim / max(height, width)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    
    # 2. Deskewing (Fix Rotation)
    try:
        angle = get_skew_angle(img)
        if angle != 0.0:
            img = rotate_image(img, angle)
    except Exception as e:
        print(f"Deskew failed, skipping: {e}")

    # 3. Convert to Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 4. Denoise (Faster than Bilateral)
    denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

    # 5. CLAHE (Contrast Enhancement)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    processed_path = f"{input_path}_proc.png"
    cv2.imwrite(processed_path, enhanced)
    return processed_path

@app.get("/")
def home():
    return {"status": "OCR Service is Running"}

@app.post("/verify")
async def verify_document(
    file: UploadFile = File(...), 
    document_type: str = Form(...)
):
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"{uuid.uuid4()}.{file_ext}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, safe_filename)
    processed_path = None

    try:
        # Save file
        # shutil.copyfileobj is synchronous, but okay for small files in this context.
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # --- CPU BOUND OPERATION ---
        processed_path = await run_in_executor(None, preprocess_image_optimized, temp_file_path)
        
        doc_type_upper = document_type.upper().strip()
        
        # Select function
        ocr_func = None
        key_check = None
        
        if doc_type_upper in ["DL", "DRIVING_LICENSE", "LICENSE"]:
            ocr_func = openbharatocr.driving_licence
            key_check = 'Driving Licence Number'
        elif doc_type_upper == "PAN":
            ocr_func = openbharatocr.pan
            key_check = 'Pan Number'
        elif doc_type_upper == "AADHAAR":
            ocr_func = openbharatocr.front_aadhaar
            key_check = 'Aadhaar Number'
        else:
            return {"valid": False, "error": "Unsupported document type."}

        # --- CPU BOUND OPERATION ---
        data = await run_in_executor(None, ocr_func, processed_path)

        print(f"Extracted: {data}")

        if not data or not data.get(key_check):
            return {
                "valid": False, 
                "message": f"Could not verify {doc_type_upper}. Ensure image is clear and flat.",
                "data": data
            }

        return {
            "valid": True,
            "document_type": doc_type_upper,
            "data": data
        }

    except Exception as e:
        import traceback
        traceback.print_exc() # Print full error to logs
        return {"valid": False, "error": str(e), "err": "Exception occurred during processing."}

    finally:
        # Cleanup
        for path in [temp_file_path, processed_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass