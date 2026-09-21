FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ARG HY_MOTION_CODE_REVISION=4e426f5a1021cbcf7f375458c37b840ee7225229

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone https://github.com/Tencent-Hunyuan/HY-Motion-1.0.git \
    && cd HY-Motion-1.0 \
    && git checkout "${HY_MOTION_CODE_REVISION}" \
    && grep -v '^fbxsdkpy' requirements.txt > /tmp/hymotion-requirements.txt \
    && pip install --no-cache-dir -r /tmp/hymotion-requirements.txt

WORKDIR /opt/cutsceneai-provider

COPY providers /opt/cutsceneai-provider/providers

RUN pip install --no-cache-dir \
    fastapi==0.116.1 \
    "uvicorn[standard]==0.35.0"

ENV PYTHONPATH=/opt/cutsceneai-provider:/opt/HY-Motion-1.0
ENV HY_MOTION_ROOT=/opt/HY-Motion-1.0
ENV HY_MOTION_MODEL_CACHE=/models/tencent
ENV HY_MOTION_VERIFY_CHECKPOINT_SHA256=true
ENV PORT=8080

WORKDIR /opt/HY-Motion-1.0

EXPOSE 8080

CMD ["python", "-m", "providers.hymotion.service"]
