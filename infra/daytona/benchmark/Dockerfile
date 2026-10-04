FROM python:3.12.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libgomp1 git curl ca-certificates nodejs npm procps && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.154.0
COPY science.lock torch.lock configure_cuda.py /opt/bootstrap/
RUN uv venv --python /usr/local/bin/python /opt/venvs/science && uv pip install --no-cache --python /opt/venvs/science/bin/python --require-hashes -r /opt/bootstrap/science.lock && /opt/venvs/science/bin/python /opt/bootstrap/configure_cuda.py
RUN uv venv --python /usr/local/bin/python /opt/venvs/torch && uv pip install --no-cache --python /opt/venvs/torch/bin/python --require-hashes -r /opt/bootstrap/torch.lock
COPY stardist /opt/checkpoints/stardist
RUN useradd --create-home --uid 1000 researcher && mkdir -p /app /data /work /output /logs/agent /logs/verifier /opt/checkpoints/cellpose && chown -R researcher:researcher /app /data /work /output /logs /opt/venvs /opt/checkpoints/cellpose
ENV PATH=/opt/venvs/science/bin:$PATH PYTHONPATH=/app/src:/app MPLCONFIGDIR=/tmp/matplotlib TF_CPP_MIN_LOG_LEVEL=2 TF_FORCE_GPU_ALLOW_GROWTH=true OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 CELLPOSE_LOCAL_MODELS_PATH=/opt/checkpoints/cellpose
WORKDIR /app
# Daytona's toolbox must bootstrap Harbor directories as root. Harbor explicitly
# runs the agent as the unprivileged researcher declared in task.toml.
USER root
