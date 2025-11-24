from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import openbharatocr
import requests
import os
import uuid

app = FastAPI()

# --- 1. DATA MODEL (The Receptionist) ---
class OcrRequest(BaseModel):
    file_url: str          # Supabase Storage Public URL
    callback_url: str      # The Supabase Edge Function URL to notify
    callback_token: str    # The Job ID (passed as Bearer token)
    document_type: str     # 'DL', 'PAN', or 'AADHAAR'

# --- 2. THE BACKGROUND WORKER (The Heavy Lifter) ---
def run_ocr_and_callback(file_url: str, callback_url: str, token: str, doc_type: str):
    print(f"🔄 [Background] Starting Job for token: {token}")
    
    # Generate unique filename to avoid collisions
    safe_filename = f"{uuid.uuid4()}.jpg"
    temp_file_path = os.path.join("/tmp", safe_filename)
    
    result_payload = {}

    try:
        # A. DOWNLOAD FILE
        print(f"⬇️ Downloading: {file_url}")
        response = requests.get(file_url, stream=True, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to download image. Status: {response.status_code}")
            
        with open(temp_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # B. RUN OCR LOGIC
        data = {}
        doc_type_upper = doc_type.upper().strip()
        print(f"⚙️ Processing {doc_type_upper}...")

        if doc_type_upper in ["DL", "DRIVING_LICENSE", "LICENSE"]:
            data = openbharatocr.driving_licence(temp_file_path)
            key_check = 'Driving Licence Number'
            
        elif doc_type_upper == "PAN":
            data = openbharatocr.pan(temp_file_path)
            key_check = 'Pan Number'
            
        elif doc_type_upper == "AADHAAR":
            data = openbharatocr.front_aadhaar(temp_file_path)
            key_check = 'Aadhaar Number'
            
        else:
            raise Exception(f"Unsupported document type: {doc_type}")

        # C. VALIDATION
        if not data or not data.get(key_check):
            # Valid processing, but no data found (blurry image)
            result_payload = {
                "status": "failed",
                "error": f"Could not extract {doc_type_upper} number. Image might be blurry.",
                "data": data 
            }
        else:
            # Success!
            result_payload = {
                "status": "success",
                "data": data,
                "document_type": doc_type_upper
            }

    except Exception as e:
        print(f"❌ Error: {e}")
        result_payload = {
            "status": "failed",
            "error": str(e)
        }

    finally:
        # D. CLEANUP
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    # --- 3. THE CALLBACK (The Boomerang) ---
    print(f"📞 Sending results to: {callback_url}")
    try:
        # We assume the receiver expects { status, data, error }
        cb_response = requests.post(
            callback_url, 
            json=result_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"✅ Callback response: {cb_response.status_code}")
    except Exception as e:
        print(f"🚨 Callback Failed: {e}")


# --- 4. THE ENDPOINT (Fast & Dumb) ---
@app.get("/")
def home():
    return {"status": "OCR Service is Running"}

@app.post("/verify_async")
async def verify_document_async(
    req: OcrRequest, 
    background_tasks: BackgroundTasks
):
    """
    Receives the job, replies INSTANTLY, and processes in background.
    """
    
    # Fire and Forget
    background_tasks.add_task(
        run_ocr_and_callback, 
        req.file_url, 
        req.callback_url, 
        req.callback_token,
        req.document_type
    )
    
    # Return 202 Accepted (Standard for async jobs)
    return {"status": "accepted", "message": "Job queued for processing"}