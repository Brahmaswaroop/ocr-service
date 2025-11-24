# Use Python 3.10 slim (Good balance of size and compatibility)
FROM python:3.10-slim

# 1. Install System Dependencies (Fixes "libGL.so.1" and "libgomp" errors)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy requirements and install
# We use --no-cache-dir to keep the image smaller
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the app code
COPY . .

# 5. Run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]