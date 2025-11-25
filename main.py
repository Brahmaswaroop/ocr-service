from fastapi import FastAPI, UploadFile, File, Form
from starlette.concurrency import run_in_threadpool
import shutil, os, uuid, tempfile, cv2
from donut_engine import infer_image_to_json

app = FastAPI()

def get_skew_angle(cv_image) -> float:
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilate = cv2.dilate(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return 0.0
    largest = max(contours, key=cv2.contourArea)
    angle = cv2.minAreaRect(largest)[-1]
    if angle < -45: angle = -(90 + angle)
    else: angle = -angle
    if abs(angle) < 1.0: return 0.0
    return angle

def rotate_image(cv_image, angle: float):
    if angle == 0.0: return cv_image
    (h, w) = cv_image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def preprocess_image_optimized(input_path: str) -> str:
    img = cv2.imread(input_path)
    if img is None: raise RuntimeError(f"Could not read image: {input_path}")
    h, w = img.shape[:2]
    max_dim = 1800
    if max(h, w) > max_dim:
        s = max_dim / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    try:
        angle = get_skew_angle(img)
        if angle != 0.0: img = rotate_image(img, angle)
    except Exception:
        pass
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    processed_path = f"{input_path}_proc.png"
    cv2.imwrite(processed_path, enhanced)
    return processed_path

@app.get("/")
def home():
    return {"status": "OCR Service is Running"}

@app.post("/verify")
async def verify_document(file: UploadFile = File(...), document_type: str = Form(...)):
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"{uuid.uuid4()}.{file_ext}"
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, safe_filename)
    processed_path = None
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        processed_path = await run_in_threadpool(preprocess_image_optimized, temp_file_path)
        doc_type_upper = document_type.upper().strip()
        if doc_type_upper not in ["DL", "DRIVING_LICENSE", "LICENSE", "PAN", "AADHAAR"]:
            return {"valid": False, "error": "Unsupported document type."}
        data = await run_in_threadpool(infer_image_to_json, processed_path)
        key_checks = {
            "DL": ["driving_license_number", "Driving Licence Number", "DL Number"],
            "PAN": ["pan_number", "Pan Number", "PAN"],
            "AADHAAR": ["aadhaar_number", "Aadhaar Number", "Aadhaar"]
        }
        checks = key_checks.get(doc_type_upper, [])
        found = False
        if isinstance(data, dict):
            for k in checks:
                if any(k.lower() in str(k2).lower() or (isinstance(data.get(k2), str) and data.get(k2)) for k2 in data.keys()):
                    found = True
                    break
            if not found:
                if any(data.get(c) for c in checks):
                    found = True
        if not data or (isinstance(data, dict) and not found):
            return {"valid": False, "message": f"Could not verify {doc_type_upper}. Ensure image is clear and flat.", "data": data}
        return {"valid": True, "document_type": doc_type_upper, "data": data}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"valid": False, "error": str(e)}
    finally:
        for path in [temp_file_path, processed_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
