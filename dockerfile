FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt-get/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

# Pre-install binary wheels for dlib and the model weights
RUN pip install --no-cache-dir dlib-bin face-recognition-models

# Install face_recognition without allowing source builds
RUN pip install --no-cache-dir --no-deps face_recognition

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "--timeout", "120"]