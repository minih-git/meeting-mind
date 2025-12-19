FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
# libsndfile1 is required for audio processing (soundfile/torchaudio)
# ffmpeg might be needed for audio conversion
RUN apt-get update && apt-get install -y \
    build-essential \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --default-timeout=1000

# Copy application code
COPY . .



# Expose port
EXPOSE 9528

# Run command
# Ensuring python path includes the current directory
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9528"]
