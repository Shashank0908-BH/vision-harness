FROM vision-adaptive-stardist:latest AS scientific
FROM python:3.12.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libgomp1 git curl ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/*
# Reuse scientific packages, never the previous experiment's /app or /data.
COPY --from=scientific /usr/local /usr/local
RUN pip uninstall -y vision-harness && npm install -g @openai/codex@0.154.0
RUN pip install --no-cache-dir beautifulsoup4==4.14.3 tifffile==2026.3.3
COPY models/stardist /opt/checkpoints/stardist
RUN useradd --create-home --uid 1000 researcher && mkdir -p /work /output /logs/agent /logs/verifier && chown -R researcher:researcher /work /output /logs
ENV MPLCONFIGDIR=/tmp/matplotlib TF_CPP_MIN_LOG_LEVEL=2 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /work
USER researcher
