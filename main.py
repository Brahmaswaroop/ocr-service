from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import openbharatocr
import shutil
import os
import uuid

app = FastAPI()

@app.get("/")
def home():
    return {"status": "OCR Service is Running"}

@app.post("/verify")
async def verify_document(
    file: UploadFile = File(...), 
    document_type: str = Form(...) # New parameter for 'PAN', 'AADHAAR', or 'DL'
):
    # 1. Setup paths
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"{uuid.uuid4()}.{file_ext}"
    temp_file_path = os.path.join("/tmp", safe_filename)
    
    try:
        # 2. Save file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(temp_file_path):
            return {"valid": False, "error": "File save failed"}

        # 3. Route logic based on Document Type
        data = {}
        doc_type_upper = document_type.upper().strip()
        
        print(f"Processing {doc_type_upper}...") # Log for debugging

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
            return {
                "valid": False, 
                "error": f"Unsupported document type: {document_type}. Use 'PAN', 'AADHAAR', or 'DL'."
            }

        # 4. Validation
        print(f"Raw Data: {data}") # Debug log

        # If data is empty or the specific ID number is missing
        if not data or not data.get(key_check):
            return {
                "valid": False, 
                "message": f"Could not read {doc_type_upper} Number. Image might be blurry.",
                "extracted_raw": data 
            }

        return {
            "valid": True,
            "document_type": doc_type_upper,
            "data": data,
            "source": "OpenBharatOCR"
        }

    except Exception as e:
        return {"valid": False, "error": str(e), "err": "Exception occurred during processing."}

    finally:
        # 5. Cleanup
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)