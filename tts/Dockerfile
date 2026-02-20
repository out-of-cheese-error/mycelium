FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clone vibevoice and add to Python path (pip install fails with old setuptools)
RUN git clone --depth 1 https://github.com/microsoft/VibeVoice.git /opt/vibevoice

ENV PYTHONPATH="/opt/vibevoice:${PYTHONPATH}"

COPY server.py .
COPY download_voices.py .

ENV MODEL_PATH=microsoft/VibeVoice-Realtime-0.5B
ENV MODEL_DEVICE=cuda
ENV VOICES_DIR=/app/voices/streaming_model
ENV HF_HOME=/app/hf_cache

EXPOSE 8100

CMD python download_voices.py && uvicorn server:app --host 0.0.0.0 --port 8100
