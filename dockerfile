# Use a lightweight Python base image
FROM python:3.10-slim

# 1. Install System Dependencies (UPDATED)
# 'libgl1-mesa-glx' is removed in modern Debian. 
# We use 'libgl1' and 'libglib2.0-0' which are required for OpenCV/OCR.
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the app code
COPY . .

# 5. Run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]