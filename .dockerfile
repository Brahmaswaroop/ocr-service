# Use a lightweight Python base image
FROM python:3.10-slim

# 1. Install System Dependencies (Tesseract & OpenGL for OpenCV)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the app code
COPY . .

# 5. Run the API (Port 10000 is default for Render)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]