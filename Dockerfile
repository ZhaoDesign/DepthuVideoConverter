# ------------------------------------------------------------------
# DepthuVideoConverter — Docker image
#
# Build:  docker build -t depth-video-converter .
# Run:    docker compose up
# ------------------------------------------------------------------

FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

# System deps — ffmpeg for video encoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (layer cache: requirements.txt changes less often than code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY depth_converter/ depth_converter/
COPY depth_anything_v2/ depth_anything_v2/
COPY depth_video_converter.py .

# Volume mount points for persistent data
VOLUME ["/app/models", "/app/examples"]

EXPOSE 7860

ENV DEPTH_HOST=0.0.0.0
ENV DEPTH_PORT=7860

CMD ["python", "depth_video_converter.py"]
