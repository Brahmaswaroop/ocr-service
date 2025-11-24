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
        # NOTE: The library uses British spelling 'licence' with a 'c'
        data = openbharatocr.driving_licence(temp_filename)
        
        # Check if data was actually found
        # The library returns 'license_number' (with 's') in the dictionary keys
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