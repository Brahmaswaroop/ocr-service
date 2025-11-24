from fastapi import FastAPI, UploadFile, File
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
    # 1. Create an ABSOLUTE path in the /tmp folder
    # This fixes the "No such file" error on Render/Linux
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"{uuid.uuid4()}.{file_ext}"
    temp_file_path = os.path.join("/tmp", safe_filename)
    
    try:
        # 2. Save the uploaded file to the absolute path
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Verify file exists before calling the library (Debugging)
        if not os.path.exists(temp_file_path):
            return {"valid": False, "error": "File failed to save to disk"}

        # 4. Run OpenBharatOCR with the FULL PATH
        # Note: 'driving_licence' is the British spelling used by the library
        data = openbharatocr.driving_licence(temp_file_path)
        
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
        # 5. Cleanup: Delete the temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)