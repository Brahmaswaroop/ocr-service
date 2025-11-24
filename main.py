from fastapi import FastAPI, UploadFile, File, HTTPException
import openbharatocr
import shutil
import os
import uuid

app = FastAPI()

@app.get("/")
def home():
    return {"status": "OCR Service is Running"}

@app.post("/verify-dl")
async def verify_dl(file: UploadFile = File(...)):
    # 1. Save upload to a temp file
    file_ext = file.filename.split(".")[-1]
    temp_filename = f"temp_{uuid.uuid4()}.{file_ext}"
    
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Run OpenBharatOCR
        # The library returns a dict like {'name': '...', 'license_number': '...'}
        data = openbharatocr.driving_licence(temp_filename)
        
        # 3. Basic Validation Logic
        if not data or not data.get('license_number'):
            return {"valid": False, "message": "Could not read License Number"}
            
        return {
            "valid": True,
            "data": data,
            "source": "OpenBharatOCR"
        }

    except Exception as e:
        return {"valid": False, "error": str(e)}
    
    finally:
        # 4. Cleanup: Delete temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)